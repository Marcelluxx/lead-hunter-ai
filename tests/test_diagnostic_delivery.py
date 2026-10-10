import base64
import contextlib
import json
import re
import sys
import unittest
from io import BytesIO, StringIO
from unittest.mock import patch
from zipfile import ZipFile

from streamlit.testing.v1 import AppTest
from main import main
from src.application.container import ApplicationContainer
from src.ui.diagnostic_panel import render_diagnostic_panel
from tests.test_full_diagnostics import diagnostic_fixture
from tests.test_compliant_pipeline import _Crawler, _Auditor


APP = '''
from src.ui.diagnostic_panel import render_diagnostic_panel
from src.application.container import ApplicationContainer
from src.settings import ApplicationSettings
render_diagnostic_panel(container=ApplicationContainer(ApplicationSettings(openrouter_api_key='test-only')))
'''


class DiagnosticDeliveryTests(unittest.TestCase):
    def setUp(self):
        original = sys.modules['__main__']
        self.addCleanup(lambda: sys.modules.__setitem__('__main__', original))
        self.fx = diagnostic_fixture(self, activate=False, available=False)
        self.destination = self.fx.root / 'report.zip'
        self.args = ['--test-url', 'https://official.example.test/', '--full-diagnostics',
                     '--diagnostic-output', str(self.destination)]
        self.output = StringIO()
        redirect = contextlib.redirect_stdout(self.output); redirect.__enter__()
        self.addCleanup(redirect.__exit__, None, None, None)
        environment = patch.dict('os.environ', {'OPENROUTER_API_KEY': 'test-only'})
        environment.start(); self.addCleanup(environment.stop)

    def test_invalid_flags_and_retention_precede_environment_or_files(self):
        for args in [['--full-diagnostics'], ['--diagnostic-output', str(self.destination)],
                     self.args + ['--gui'], self.args + ['--save-diagnostic-artifacts']]:
            with self.subTest(args=args), patch('main.ApplicationSettings.from_environment') as settings, \
                    contextlib.redirect_stderr(StringIO()), self.assertRaises(SystemExit) as error:
                main(args)
            self.assertEqual(error.exception.code, 2); settings.assert_not_called()
        for option, value in [('--diagnostic-retention-hours', '0'), ('--diagnostic-retention-hours', '169'),
                              ('--max-pages', '0'), ('--max-pages', '21')]:
            with patch('main.ApplicationSettings.from_environment') as settings:
                self.assertEqual(main(self.args + [option, value]), 2)
            settings.assert_not_called()
        self.assertFalse(self.destination.exists())

    def test_missing_license_blocks_crawler_auditor_and_output(self):
        with patch('main.HybridCrawler') as crawler, patch.object(ApplicationContainer, 'build_auditor') as auditor:
            self.assertEqual(main(self.args), 2)
            crawler.assert_not_called(); auditor.assert_not_called()
        self.assertFalse(self.destination.exists())

    def test_cli_real_catalog_signed_license_produces_valid_zip(self):
        self.fx.activate()
        with patch('main.HybridCrawler', return_value=_Crawler()), patch.object(ApplicationContainer, 'build_auditor', return_value=_Auditor()):
            self.assertEqual(main(self.args), 0)
        with ZipFile(self.destination) as archive:
            manifest = json.loads(archive.read('manifest.json'))
            self.assertGreater(manifest['record_count'], 0)
            self.assertLessEqual(manifest['expires_at'], 100)

    def test_cli_revocation_at_fsync_preserves_existing_destination(self):
        self.fx.activate(); self.destination.write_bytes(b'previous')
        def revoke(_): self.fx.licenses.revoke_license(self.fx.scope, self.fx.claims.license_id)
        with patch('main.HybridCrawler', return_value=_Crawler()), patch.object(ApplicationContainer, 'build_auditor', return_value=_Auditor()), patch('os.fsync', side_effect=revoke):
            self.assertEqual(main(self.args), 2)
        self.assertEqual(self.destination.read_bytes(), b'previous')
        self.assertNotIn('Diagnostica salvata', self.output.getvalue())

    def test_cli_interrupt_and_runtime_failure_preserve_destination_and_redact(self):
        self.fx.activate(); self.destination.write_bytes(b'previous')
        for error in [KeyboardInterrupt(), RuntimeError('secret-sentinel')]:
            crawler = _Crawler()
            async def failed(url): raise error
            crawler.crawl = failed
            with self.subTest(error=type(error).__name__), patch('main.HybridCrawler', return_value=crawler), patch.object(ApplicationContainer, 'build_auditor', return_value=_Auditor()):
                self.assertEqual(main(self.args), 1)
            self.assertEqual(self.destination.read_bytes(), b'previous')
            self.assertNotIn('secret-sentinel', self.output.getvalue())

    def test_gui_disabled_without_license_and_real_zip_not_retained_in_session(self):
        app = AppTest.from_string(APP, default_timeout=20).run()
        self.assertTrue(app.button(key='diagnostic_run').disabled)
        self.fx.activate()
        app.run(); app.text_input(key='diagnostic_url').set_value('https://official.example.test/').run()
        with patch('src.ui.diagnostic_panel.HybridCrawler', return_value=_Crawler()), patch.object(ApplicationContainer, 'build_auditor', return_value=_Auditor()):
            app.button(key='diagnostic_run').click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.get('iframe')), 1)
        html = app.get('iframe')[0].proto.srcdoc
        self.assertNotIn('/media/', html)
        raw = base64.b64decode(re.search('base64,([A-Za-z0-9+/=]+)', html).group(1))
        with ZipFile(BytesIO(raw)) as archive:
            self.assertEqual(json.loads(archive.read('manifest.json'))['schema_version'], 1)
        self.assertNotIn(raw, [v for v in app.session_state.filtered_state.values() if isinstance(v, bytes)])
        self.assertEqual(len(app.get('download_button')), 0)

    def test_gui_revocation_inside_html_builder_blocks_delivery(self):
        from src.ui.inline_download import _inline_download_html
        self.fx.activate()
        app = AppTest.from_string(APP, default_timeout=20).run()
        app.text_input(key='diagnostic_url').set_value('https://official.example.test/').run()
        def revoke(*args, **kwargs):
            html = _inline_download_html(*args, **kwargs)
            self.fx.licenses.revoke_license(self.fx.scope, self.fx.claims.license_id)
            return html
        with patch('src.ui.diagnostic_panel.HybridCrawler', return_value=_Crawler()), patch.object(ApplicationContainer, 'build_auditor', return_value=_Auditor()), patch('src.ui.inline_download._inline_download_html', side_effect=revoke):
            app.button(key='diagnostic_run').click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.get('iframe')), 0)
        self.assertTrue(any('license_revoked' in x.value for x in app.error))
