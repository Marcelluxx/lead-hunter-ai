import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from main import LeadHunterOrchestrator
from src.domain.crawl import CrawlResult, CrawlStatus, PageEvidence
from src.domain.discovery import (
    DiscoveryBatch,
    ProviderAttribution,
    ProviderRetentionRule,
    TransientCandidate,
)
from src.domain.provenance import VerifiedLead
from src.scraper import LeadScraper


class _Provider:
    attribution = ProviderAttribution("fake", "Fake", "terms", "privacy")
    retention = ProviderRetentionRule(365, None)

    def discover(self, query, *, on_progress=None):
        if on_progress:
            on_progress(1, 1)
        return DiscoveryBatch(
            (
                TransientCandidate(
                    "fake",
                    "reference-1",
                    "Provider Listing Name",
                    "https://official.example.test",
                    datetime.now(timezone.utc),
                    self.attribution,
                ),
            ),
            self.attribution,
        )


class _Crawler:
    async def crawl(self, url):
        content = "Official site content " * 20
        evidence = PageEvidence.from_content(
            requested_url=url,
            final_url="https://official.example.test/",
            status_code=200,
            content_type="text/html",
            content=content,
        )
        return CrawlResult(
            url="https://official.example.test/",
            pages={"https://official.example.test/": content},
            evidence=[evidence],
            emails=["sales@official.example.test"],
            raw_html_home="<html><head><title>Official Clinic</title></head><body></body></html>",
            status=CrawlStatus.SUCCESS,
            is_dynamic=False,
        )

    async def close(self):
        return None


class _Auditor:
    def __init__(self):
        self.payload = None

    def audit_website(self, **payload):
        self.payload = payload
        return {
            "website_score": 7,
            "diagnosis": "Independent diagnosis",
            "site_brief": "Independent brief",
            "framework": "Unknown",
            "cold_message": "Independent message",
        }


class CompliantPipelineTests(unittest.TestCase):
    def test_provider_content_never_reaches_llm_or_verified_report(self):
        auditor = _Auditor()
        orchestrator = LeadHunterOrchestrator(
            "with_website",
            scraper=LeadScraper(provider=_Provider()),
            auditor=auditor,
        )
        with (
            patch("main.HybridCrawler", return_value=_Crawler()),
            patch("main.filter_by_business_age", return_value=True),
            patch("main.filter_franchise", return_value=False),
        ):
            results = orchestrator.run_with_website(
                45.0,
                9.0,
                ["dentista"],
                max_pages=1,
            )

        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], VerifiedLead)
        self.assertEqual(results[0].business_name, "Official Clinic")
        self.assertNotIn("Provider Listing Name", str(results[0]))
        self.assertEqual(auditor.payload["business_name"], "Official Clinic")
        self.assertEqual(auditor.payload["category"], "dentista")
        self.assertEqual(auditor.payload["rating"], 0)
        self.assertEqual(auditor.payload["review_count"], 0)


if __name__ == "__main__":
    unittest.main()
