import base64
from datetime import datetime, timezone
from io import BytesIO
import os
import re
import sys
import unittest
from unittest.mock import patch

from openpyxl import load_workbook
from streamlit.testing.v1 import AppTest

from src.domain.discovery import ProviderAttribution, TransientCandidate
from src.ui.inline_download import _xlsx_download_html
from tests.reference_export_helpers import ReferenceExportFixture

SCRIPT = '''
import streamlit as st
from src.application.container import ApplicationContainer
from src.settings import ApplicationSettings
from src.ui.reference_export_panel import render_reference_export_panel
render_reference_export_panel(place_ids=st.session_state.get('ids', ('0007',)),
    service_factory=ApplicationContainer(ApplicationSettings()).build_local_reference_export_service)
'''


class ReferenceExportUiTests(unittest.TestCase):
    def setUp(self):
        original_main = sys.modules['__main__']
        self.addCleanup(lambda: sys.modules.__setitem__('__main__', original_main))
        self.fx = ReferenceExportFixture(self, available=False)

    def prepare(self, app):
        app.button(key='reference_export_prepare').click().run()
        self.assertEqual(len(app.exception), 0)
        return app

    def decode_inline(self, html):
        match = re.search(r'data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,([A-Za-z0-9+/=]+)', html)
        self.assertIsNotNone(match)
        return base64.b64decode(match.group(1), validate=True)

    def test_inline_payload_is_real_workbook_without_static_url(self):
        self.fx.activate()
        app = self.prepare(AppTest.from_string(SCRIPT).run())
        html = app.get('iframe')[0].proto.srcdoc
        self.assertNotIn('/media/', html); self.assertNotIn('http://', html)
        self.assertIn('download="riferimenti_google_maps.xlsx"', html)
        self.assertNotIn(self.fx.token, html)
        self.assertEqual(load_workbook(BytesIO(self.decode_inline(html))).active['A2'].value, '0007')

    def test_expired_revoked_or_missing_license_never_emits_iframe(self):
        for scenario in ['missing', 'expired', 'revoked']:
            with self.subTest(scenario=scenario):
                fx = ReferenceExportFixture(self, available=False)
                if scenario != 'missing':
                    fx.activate()
                if scenario == 'expired':
                    fx.clock.set(100)
                if scenario == 'revoked':
                    fx.licenses.revoke_license(fx.scope, fx.claims.license_id)
                app = self.prepare(AppTest.from_string(SCRIPT).run())
                self.assertEqual(len(app.get('iframe')), 0)
                self.assertTrue(app.error)

    def test_delivery_rechecks_after_html_construction(self):
        self.fx.activate()
        def html_and_revoke(data, **kwargs):
            html = _xlsx_download_html(data, **kwargs)
            self.fx.licenses.revoke_license(self.fx.scope, self.fx.claims.license_id)
            return html
        with patch('src.ui.inline_download._xlsx_download_html', side_effect=html_and_revoke):
            app = self.prepare(AppTest.from_string(SCRIPT).run())
        self.assertEqual(len(app.get('iframe')), 0)
        self.assertIn('license_revoked', app.error[0].value)

    def test_rerun_after_revocation_cannot_recreate_delivery(self):
        self.fx.activate()
        app = self.prepare(AppTest.from_string(SCRIPT).run())
        self.assertEqual(len(app.get('iframe')), 1)
        self.fx.licenses.revoke_license(self.fx.scope, self.fx.claims.license_id)
        app.run()
        self.assertEqual(len(app.get('iframe')), 0)
        self.prepare(app)
        self.assertEqual(len(app.get('iframe')), 0)

    def search_app(self, outcome):
        attribution = ProviderAttribution('google_places', 'discard-provider',
                                          'https://example.test/terms', 'https://example.test/privacy')
        class Scraper:
            pass
        scraper = Scraper(); scraper.attribution = attribution
        class Orchestrator:
            def run(self, *args, **kwargs):
                if isinstance(outcome, Exception):
                    raise outcome
                return outcome
        orchestrator = Orchestrator(); orchestrator.scraper = scraper
        for target, value in [('main.create_orchestrator', orchestrator), ('streamlit_folium.st_folium', None)]:
            replacement = patch(target, return_value=value)
            replacement.start(); self.addCleanup(replacement.stop)
        return AppTest.from_file('src/gui.py', default_timeout=15)

    def start_search(self, app):
        button = next(b for b in app.button if 'AVVIA LEAD HUNTER' in b.label)
        button.click().run()
        self.assertEqual(len(app.exception), 0)

    def test_new_empty_or_failed_search_clears_previous_ids(self):
        for outcome in [[], RuntimeError('test-only')]:
            with self.subTest(outcome=type(outcome).__name__):
                app = self.search_app(outcome)
                app.session_state['no_website_place_ids'] = ('old',)
                app.run(); self.start_search(app)
                self.assertEqual(app.session_state['no_website_place_ids'], ())
                self.assertEqual(len(app.get('iframe')), 0)

    def test_successful_search_retains_only_ids_across_reruns_without_trust(self):
        candidate = TransientCandidate('google_places', '0007', 'discard-business', None,
            datetime.now(timezone.utc), ProviderAttribution('google_places', 'discard-provider',
                                                          'https://example.test/terms', 'https://example.test/privacy'))
        with patch.dict(os.environ, {'LEADHUNTER_LICENSE_TRUST_FILE': str(self.fx.root / 'missing-trust')}):
            app = self.search_app([candidate, candidate]).run(); self.start_search(app)
            self.assertEqual(app.session_state['no_website_place_ids'], ('0007',))
            app.run()
            self.assertEqual(app.session_state['no_website_place_ids'], ('0007',))
            self.prepare(app)
            self.assertEqual(len(app.get('iframe')), 0)
            self.assertTrue(app.error)

    def test_search_with_website_clears_previous_reference_ids(self):
        app = self.search_app([])
        app.session_state['no_website_place_ids'] = ('old',)
        app.run(); app.radio[0].set_value('Con Sito Web + Audit').run()
        self.start_search(app)
        self.assertEqual(app.session_state['no_website_place_ids'], ())

    def test_export_validation_does_not_hide_base_results(self):
        from dataclasses import replace
        candidate = TransientCandidate('google_places', 'A/B', 'discard-business', None,
            datetime.now(timezone.utc), ProviderAttribution('google_places', 'discard-provider',
                                                          'https://example.test/terms', 'https://example.test/privacy'))
        for results, code in [([candidate], 'reference_export_invalid'),
                               ([replace(candidate, external_id=f'A{i}') for i in range(10001)],
                                'reference_export_limit')]:
            with self.subTest(code=code):
                app = self.search_app(results)
                app.session_state['no_website_place_ids'] = ('old',)
                app.run(); self.start_search(app)
                self.assertEqual(app.session_state['no_website_place_ids'], ())
                self.assertEqual(len(app.dataframe), 1)
                self.assertEqual(len(app.dataframe[0].value), len(results))
                self.assertEqual(len(app.error), 0)
                self.assertTrue(any(code in warning.value for warning in app.warning))
                self.assertEqual(len(app.get('iframe')), 0)
