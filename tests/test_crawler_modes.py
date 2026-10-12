import os
import unittest
from types import SimpleNamespace
from src.crawler import HybridCrawler

MODE_HTML = '''<html><body><nav><a href="/menu">NAV_SENTINEL</a></nav><main>
<h1>Studio Aurora</h1><p>Studio Aurora offre consulenza professionale alle imprese italiane.
Il nostro team segue ogni progetto con attenzione, trasparenza e cura,
dalla prima analisi alla consegna finale. Contattaci per una consulenza
personalizzata scrivendo a studio@aurora.it oppure visita la nostra sede.</p>
<a href="/contatti">Contatti</a></main></body></html>'''


class CrawlerModeTests(unittest.TestCase):
    def test_optimized_selection_preserves_page_and_total_evidence_minima(self):
        from crawl4ai.models import MarkdownGenerationResult, StringCompatibleMarkdown
        from src.domain.crawl import PageEvidence, ensure_auditable_pages
        crawler = HybridCrawler(token_mode='optimized')
        for length in [100, 119]:
            md = StringCompatibleMarkdown(MarkdownGenerationResult(raw_markdown='R' * 500,
                markdown_with_citations='', references_markdown='', fit_markdown='F' * length))
            selected = crawler._select_markdown(md)
            self.assertEqual(selected, 'R' * 500)
            self.assertTrue(PageEvidence.from_content(requested_url='https://site.test/',
                final_url='https://site.test/', status_code=200, content_type='text/html', content=selected).valid)
        for length in [120, 199]:
            md = SimpleNamespace(raw_markdown='R' * 500, fit_markdown='F' * length)
            selected = crawler._select_markdown(md, minimum_chars=200)
            self.assertEqual(selected, 'R' * 500)
            ensure_auditable_pages({'https://site.test/': selected})
            self.assertEqual(crawler._select_markdown(md), 'F' * length)
        self.assertEqual(crawler._select_markdown(SimpleNamespace(raw_markdown='short', fit_markdown='F' * 190),
            minimum_chars=200), 'F' * 190)

    def test_modes_select_distinct_content_and_short_fit_falls_back_to_raw(self):
        md = SimpleNamespace(raw_markdown='R' * 500, fit_markdown='F' * 120)
        self.assertEqual(HybridCrawler(token_mode='high_fidelity')._select_markdown(md), 'R' * 500)
        self.assertEqual(HybridCrawler(token_mode='optimized')._select_markdown(md), 'F' * 120)
        md.fit_markdown = 'short'
        self.assertEqual(HybridCrawler(token_mode='optimized')._select_markdown(md), 'R' * 500)
        self.assertEqual(HybridCrawler()._select_markdown(None), '')

    def test_real_generator_optimized_removes_navigation_while_preserving_body_and_contacts(self):
        from crawl4ai.content_filter_strategy import PruningContentFilter
        from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
        from crawl4ai.models import StringCompatibleMarkdown
        generator = DefaultMarkdownGenerator(content_filter=PruningContentFilter(threshold=0.45, min_word_threshold=15),
            options={'ignore_links': True, 'ignore_images': True})
        md = StringCompatibleMarkdown(generator.generate_markdown(MODE_HTML))
        complete = HybridCrawler(token_mode='high_fidelity')._select_markdown(md)
        optimized = HybridCrawler(token_mode='optimized')._select_markdown(md)
        self.assertIn('NAV_SENTINEL', complete)
        self.assertNotIn('NAV_SENTINEL', optimized)
        for content in [complete, optimized]:
            self.assertIn('consulenza professionale', content)
            self.assertIn('studio@aurora.it', content)
        self.assertLess(len(optimized), len(complete))

    def test_invalid_mode_is_rejected_before_crawler_initialization(self):
        with self.assertRaises(ValueError):
            HybridCrawler(token_mode='invalid')


@unittest.skipUnless(os.environ.get('LEADHUNTER_BROWSER_TESTS') == '1', 'Opt-in Chromium integration')
class CrawlerModeBrowserTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_home_and_internal_pages_follow_mode_without_inventing_js_requirement(self):
        class FixtureCrawler(HybridCrawler):
            def _select_markdown(self, md, **kwargs):
                self.selection_metadata.append((self.token_mode, len(md.raw_markdown), len(md.fit_markdown),
                    'NAV_SENTINEL' in md.fit_markdown))
                return super()._select_markdown(md, **kwargs)
            async def _install_network_guard(self, page, context, **kwargs):
                async def fixture(route):
                    class Transport:
                        request = route.request
                        async def abort(self, reason): await route.abort(reason)
                        async def continue_(self): await route.fulfill(status=200, content_type='text/html', body=MODE_HTML)
                    await self._secure_route(Transport())
                await context.route('**', fixture)
                return page
        for mode in ['high_fidelity', 'optimized']:
            crawler = FixtureCrawler(max_pages=2, token_mode=mode)
            crawler.selection_metadata = []
            try:
                result = await crawler.crawl('https://93.184.216.34/')
            finally:
                await crawler.close()
            with self.subTest(mode=mode):
                self.assertTrue(result.is_auditable)
                self.assertEqual(len(result.pages), 2)
                self.assertTrue(result.browser_used)
                self.assertEqual(result.render_strategy, 'browser')
                self.assertIsNone(result.js_required)
                self.assertIsNone(result.is_dynamic)
                for page in result.pages.values():
                    self.assertEqual('NAV_SENTINEL' in page, mode == 'high_fidelity', repr(crawler.selection_metadata))
                    self.assertIn('consulenza professionale', page)
                self.assertIn('studio@aurora.it', [x.normalized_value for x in result.contacts])

    async def test_blocked_url_never_reports_browser_used_or_dynamic_site(self):
        crawler = HybridCrawler()
        result = await crawler.crawl('http://127.0.0.1/')
        self.assertFalse(result.browser_used)
        self.assertEqual(result.render_strategy, 'not_started')
        self.assertIsNone(result.js_required)
