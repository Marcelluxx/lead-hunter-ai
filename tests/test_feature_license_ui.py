import io
import json
import os
import runpy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from src.application.container import ApplicationContainer
from src.settings import ApplicationSettings
from tests.license_helpers import FakeClock, license_claims, signed_test_license, test_key_pair

SCRIPT = """
import streamlit as st
from unittest.mock import patch
from src.ui.feature_license_panel import render_feature_license_panel
with patch('streamlit.file_uploader', return_value=st.session_state.get('upload')):
    render_feature_license_panel(scope=st.session_state['scope'],
        licenses=st.session_state['licenses'], access=st.session_state['access'])
"""


class FeatureLicenseUiTests(unittest.TestCase):
    def setUp(self):
        # AppTest installs its script as __main__; restore unittest's entry module
        # so later Windows spawn tests do not replay a UI script without state.
        original_main = sys.modules['__main__']
        self.addCleanup(lambda: sys.modules.__setitem__('__main__', original_main))
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        private, public = test_key_pair()
        trust = Path(tmp.name) / 'trust.json'
        trust.write_text(json.dumps({'version': 1, 'issuer': 'test-owner', 'keys': {'test-key': public.decode()}}))
        environment = patch.dict(os.environ, {'LEADHUNTER_LICENSE_ISSUER': 'test-owner',
            'LEADHUNTER_LICENSE_TRUST_FILE': str(trust), 'LEADHUNTER_LICENSE_STATE_DIR': str(Path(tmp.name) / 'state')})
        environment.start()
        self.addCleanup(environment.stop)
        self.clock = FakeClock(10)
        timer = patch('src.application.license_clock.SystemClock.now_epoch', side_effect=self.clock.now_epoch)
        timer.start()
        self.addCleanup(timer.stop)
        self.scope, self.licenses, self.access = ApplicationContainer(ApplicationSettings()).build_local_license_service()
        self.token = signed_test_license(license_claims(scope=self.scope), private)

    def app(self):
        app = AppTest.from_string(SCRIPT)
        app.session_state['scope'] = self.scope
        app.session_state['licenses'] = self.licenses
        app.session_state['access'] = self.access
        return app

    def text(self, app):
        return ' '.join(str(item.value) for group in (app.markdown, app.caption, app.info, app.warning,
                                                       app.success, app.error) for item in group)

    def test_planned_feature_shows_granted_but_unavailable(self):
        from src.application.feature_access import FeatureAccessService
        from tests.test_feature_access import PlannedDiagnosticCatalog
        self.access = FeatureAccessService(self.licenses, PlannedDiagnosticCatalog())
        self.licenses.import_license(self.scope, self.token)
        app = self.app().run()
        self.assertEqual(len(app.exception), 0)
        text = self.text(app)
        self.assertIn('Autorizzato, modulo non ancora disponibile', text)
        self.assertIn('Europe/Rome', text)
        self.assertNotIn(self.token, text)
        self.assertFalse(any('Esegui' in item.label for item in app.button))

    def test_gui_import_and_expiry_use_common_service(self):
        app = self.app()
        app.session_state['upload'] = io.BytesIO(self.token.encode())
        app.run()
        app.button(key='license_import').click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(self.licenses.summary(self.scope).license_status, 'valid')
        app.session_state['upload'] = io.BytesIO(b'invalid')
        app.button(key='license_import').click().run()
        self.assertEqual(self.licenses.summary(self.scope).license_status, 'valid')
        self.clock.set(100)
        app.run()
        self.assertIn('expired', self.text(app))
        self.assertNotIn('Autorizzato, modulo non ancora disponibile', self.text(app))

    def test_gui_launch_and_direct_config_bind_loopback(self):
        with patch.object(sys, 'argv', ['main.py', '--gui']), patch('subprocess.run') as launch:
            with self.assertRaises(SystemExit) as caught:
                runpy.run_path('main.py', run_name='__main__')
        self.assertEqual(caught.exception.code, 0)
        self.assertEqual(launch.call_args.args[0][-2:], ['--server.address', '127.0.0.1'])
        from streamlit import config
        config.get_config_options(force_reparse=True)
        self.assertEqual(config.get_option('server.address'), '127.0.0.1')
