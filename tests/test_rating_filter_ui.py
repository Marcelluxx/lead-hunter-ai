import base64
import contextlib
from io import BytesIO, StringIO
import re
import sys
import unittest
from unittest.mock import patch

from openpyxl import load_workbook
from streamlit.testing.v1 import AppTest

from src.application.container import ApplicationContainer
from src.application.rating_filters import RatingFilterGuard
from src.scraper import LeadScraper
from tests.rating_filter_helpers import RatingFilterFixture
from tests.test_rating_filter_discovery import Transport, make_provider, place
from tests.test_compliant_pipeline import _Crawler, _Auditor


class RatingFilterUiTests(unittest.TestCase):
    def setUp(self):
        original_main = sys.modules['__main__']
        self.addCleanup(lambda: sys.modules.__setitem__('__main__', original_main))
        self.fx = RatingFilterFixture(self, features=('discovery.rating_filters', 'export.no_website'))
        self.http = Transport()
        self.output = StringIO()
        redirect = contextlib.redirect_stdout(self.output); redirect.__enter__()
        self.addCleanup(redirect.__exit__, None, None, None)
        for target, kwargs in [('streamlit_folium.st_folium', {'return_value': None}),
            ('src.application.container.LeadScraper', {'side_effect': lambda **_: LeadScraper(provider=make_provider(self.http))})]:
            item = patch(target, **kwargs); item.start(); self.addCleanup(item.stop)
        env = patch.dict('os.environ', {'GOOGLE_API_KEY': 'test-only', 'OPENROUTER_API_KEY': 'test-only'})
        env.start(); self.addCleanup(env.stop)

    def app(self):
        app = AppTest.from_file('src/gui.py', default_timeout=20).run()
        self.assertEqual(len(app.exception), 0)
        return app

    def toggle(self, app):
        return app.toggle(key='rating_filters_enabled')

    def start(self, app):
        next(b for b in app.button if 'AVVIA LEAD HUNTER' in b.label).click().run()
        self.assertEqual(len(app.exception), 0)
        return app

    def filtered(self):
        self.fx.activate()
        app = self.app(); self.toggle(app).set_value(True).run()
        return self.start(app)

    def decode(self, app):
        html = app.get('iframe')[0].proto.srcdoc
        self.assertNotIn('/media/', html)
        encoded = re.search('base64,([A-Za-z0-9+/=]+)', html).group(1)
        return base64.b64decode(encoded, validate=True)

    def test_default_off_and_controls_in_both_modes(self):
        self.fx.activate(); app = self.app()
        self.assertFalse(self.toggle(app).value)
        self.toggle(app).set_value(True).run()
        self.assertEqual(app.number_input(key='rating_filter_min_rating').value, 3.9)
        self.assertEqual(app.number_input(key='rating_filter_max_reviews').value, 100)
        app.radio[0].set_value('Con Sito Web + Audit').run()
        self.assertTrue(self.toggle(app).value)
        self.toggle(app).set_value(False).run()
        app.radio[0].set_value('Senza Sito Web').run()
        self.assertFalse(self.toggle(app).value)

    def test_unlicensed_option_disabled_but_base_search_still_works(self):
        app = self.app(); self.assertTrue(self.toggle(app).disabled)
        self.start(app)
        self.assertEqual(len(app.dataframe), 1)
        self.assertIsNone(app.session_state['no_website_result_origin'])

    def test_toggle_off_does_not_reclassify_filtered_ids_after_revocation(self):
        app = self.filtered()
        self.assertIsInstance(app.session_state['no_website_result_origin'], RatingFilterGuard)
        self.toggle(app).set_value(False).run()
        self.assertIsInstance(app.session_state['no_website_result_origin'], RatingFilterGuard)
        self.fx.licenses.revoke_license(self.fx.scope, self.fx.claims.license_id)
        app.run()
        self.assertEqual(app.session_state['no_website_place_ids'], ())
        self.assertIsNone(app.session_state['no_website_result_origin'])
        self.assertEqual(len(app.get('iframe')), 0)

    def test_failed_or_empty_new_search_clears_ids_and_origin(self):
        for fail in [False, True]:
            with self.subTest(fail=fail):
                fx = RatingFilterFixture(self, features=('discovery.rating_filters', 'export.no_website')); fx.activate()
                app = self.app(); self.toggle(app).set_value(True).run(); self.start(app)
                self.http.places = []
                if fail:
                    def error(*_): raise RuntimeError('provider-secret-sentinel')
                    self.http.hook = error
                self.start(app)
                self.assertEqual(app.session_state['no_website_place_ids'], ())
                self.assertIsNone(app.session_state['no_website_result_origin'])
                self.assertEqual(len(app.get('iframe')), 0)
                self.http.hook = None; self.http.places = [place()]

    def test_preflight_valid_then_expired_at_start_never_falls_back(self):
        app = self.filtered(); self.http.calls.clear()
        self.fx.clock.set(100); self.start(app)
        self.assertEqual(len(self.http.calls), 0)
        self.assertEqual(len(app.dataframe), 0)
        self.assertTrue(any('license_expired' in error.value for error in app.error))
        # An explicit choice restores the base path even when the selected toggle is disabled.
        app.button(key='rating_filter_use_base').click().run(); self.start(app)
        self.assertEqual(len(app.dataframe), 1)
        self.assertIsNone(app.session_state['no_website_result_origin'])

    def test_valid_download_contains_real_xlsx_and_no_provider_metrics(self):
        app = self.filtered()
        app.button(key='reference_export_prepare').click().run()
        self.assertEqual([cell.value for cell in load_workbook(BytesIO(self.decode(app))).active[1]], ['Place ID', 'Link Google Maps'])
        self.assertNotIn('provider-secret-sentinel', repr(app.session_state))
        self.assertNotIn('userRatingCount', repr(app.session_state))
        self.assertEqual(len(app.get('download_button')), 0)

    def test_revocation_during_html_blocks_both_report_and_reference_delivery(self):
        from src.ui.inline_download import _xlsx_download_html
        for mode in ['no_website', 'with_website']:
            with self.subTest(mode=mode):
                fx = RatingFilterFixture(self, features=('discovery.rating_filters', 'export.no_website')); fx.activate()
                def revoke(*args, **kwargs):
                    html = _xlsx_download_html(*args, **kwargs)
                    fx.licenses.revoke_license(fx.scope, fx.claims.license_id)
                    return html
                app = self.app(); self.toggle(app).set_value(True).run()
                if mode == 'no_website':
                    self.start(app)
                    with patch('src.ui.inline_download._xlsx_download_html', side_effect=revoke):
                        app.button(key='reference_export_prepare').click().run()
                else:
                    self.http.places = [place(websiteUri='https://official.example.test')]
                    app.radio[0].set_value('Con Sito Web + Audit').run()
                    crawler = _Crawler(); original = crawler.crawl
                    async def no_contacts(url):
                        result = await original(url); result.contacts = []; return result
                    crawler.crawl = no_contacts
                    with patch.object(ApplicationContainer, 'build_auditor', return_value=_Auditor()), patch('main.HybridCrawler', return_value=crawler), patch('main.filter_by_business_age', return_value=True), patch('main.filter_franchise', return_value=False), patch('src.ui.inline_download._xlsx_download_html', side_effect=revoke):
                        self.start(app)
                self.assertEqual(len(app.get('iframe')), 0)
                self.assertEqual(len(app.get('download_button')), 0)
                self.assertEqual(len(app.exception), 0)
