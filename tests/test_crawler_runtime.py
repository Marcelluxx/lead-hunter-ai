"""Exercise the supported Crawl4AI path without its unused NLP dependency."""

import importlib.metadata
import importlib.util
import os
import tempfile
import unittest
from unittest.mock import patch

from src.crawler import HybridCrawler
from src.domain import CrawlStatus


WEBSITE_HTML = """<html><body><main><h1>Studio Aurora</h1><p>
Studio Aurora offre consulenza professionale alle imprese italiane.
Il nostro team segue ogni progetto con attenzione, trasparenza e cura,
dalla prima analisi alla consegna finale. Contattaci per una consulenza
personalizzata scrivendo a studio@aurora.it oppure visita la nostra sede.
</p><a href="/contatti">Contatti</a><img src="/logo.png"></main></body></html>"""


class CrawlerRuntimeTests(unittest.TestCase):
    def test_vulnerable_nlp_package_is_not_shipped(self):
        with self.assertRaises(importlib.metadata.PackageNotFoundError):
            importlib.metadata.distribution("nltk")
        self.assertIsNone(importlib.util.find_spec("nltk"))

    def test_supported_crawler_configuration_preserves_website_content(self):
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig
        from crawl4ai.content_filter_strategy import PruningContentFilter
        from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

        generator = DefaultMarkdownGenerator(
            content_filter=PruningContentFilter(threshold=0.45, min_word_threshold=15),
            options={"ignore_links": True, "ignore_images": True},
        )
        config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            markdown_generator=generator,
            wait_until="networkidle",
            page_timeout=25000,
        )
        crawler = AsyncWebCrawler(config=BrowserConfig(headless=True))
        self.assertIsNotNone(crawler.crawler_strategy)
        result = config.markdown_generator.generate_markdown(WEBSITE_HTML)
        for text in (result.raw_markdown, result.fit_markdown):
            self.assertIn("Studio Aurora", text)
            self.assertIn("consulenza professionale", text)
            self.assertIn("studio@aurora.it", text)
            self.assertNotIn("/logo.png", text)
            self.assertNotIn("](/contatti)", text)


@unittest.skipUnless(
    os.environ.get("LEADHUNTER_BROWSER_TESTS") == "1",
    "Opt-in Chromium integration; enabled by the Python 3.11 CI job.",
)
class CrawlerBrowserRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_crawler_preserves_evidence_and_contacts_without_nltk(self):
        # Only network transport is replaced. Chromium, Crawl4AI, Markdown,
        # the app's route guard, evidence, and contact extraction remain real.
        class FixtureRoute:
            def __init__(self, route):
                self.route = route
                self.request = route.request

            async def abort(self, reason):
                await self.route.abort(reason)

            async def continue_(self):
                await self.route.fulfill(
                    status=200, content_type="text/html", body=WEBSITE_HTML
                )

        class FixtureCrawler(HybridCrawler):
            async def _install_network_guard(self, page, context, **kwargs):
                async def route_fixture(route):
                    await self._secure_route(FixtureRoute(route))

                await context.route("**", route_fixture)
                return page

        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"CRAWL4_AI_BASE_DIRECTORY": directory}):
                crawler = FixtureCrawler(max_pages=2)
                try:
                    result = await crawler.crawl("https://93.184.216.34/")
                finally:
                    await crawler.close()
        self.assertEqual(result.status, CrawlStatus.SUCCESS)
        self.assertEqual(
            set(result.pages),
            {"https://93.184.216.34/", "https://93.184.216.34/contatti"},
        )
        self.assertTrue(result.is_auditable)
        self.assertEqual(len(result.evidence), 2)
        self.assertTrue(all(item.valid for item in result.evidence))
        self.assertIn("consulenza professionale", result.pages[result.url])
        self.assertIn("studio@aurora.it", [c.normalized_value for c in result.contacts])
        self.assertIsNone(importlib.util.find_spec("nltk"))


if __name__ == "__main__":
    unittest.main()
