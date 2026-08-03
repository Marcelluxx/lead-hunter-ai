import unittest

from src.domain import (
    CrawlEvidenceError,
    CrawlResult,
    CrawlStatus,
    PageEvidence,
    ensure_auditable_pages,
)


class CrawlEvidenceContractTests(unittest.TestCase):
    def test_accepts_only_successful_supported_and_sufficient_evidence(self):
        content = "Servizio professionale. " * 20
        evidence = PageEvidence.from_content(
            requested_url="https://example.com",
            final_url="https://example.com/",
            status_code=200,
            content_type="text/html; charset=utf-8",
            content=content,
        )
        result = CrawlResult(
            url="https://example.com/",
            requested_url="https://example.com",
            pages={"https://example.com/": content},
            evidence=[evidence],
            status=CrawlStatus.SUCCESS,
        )

        self.assertTrue(evidence.valid)
        self.assertTrue(result.is_auditable)
        self.assertEqual(len(evidence.content_sha256), 64)
        self.assertTrue(evidence.retrieved_at.endswith("+00:00"))

    def test_rejects_empty_short_non_html_and_non_success_responses(self):
        cases = [
            (200, "text/html", "troppo corto", "content_too_short"),
            (404, "text/html", "x" * 300, "http_status_not_success"),
            (200, "application/pdf", "x" * 300, "unsupported_content_type"),
            (None, "text/html", "x" * 300, "missing_status_code"),
        ]

        for status, content_type, content, expected_code in cases:
            with self.subTest(expected_code=expected_code):
                evidence = PageEvidence.from_content(
                    requested_url="https://example.com",
                    final_url="https://example.com",
                    status_code=status,
                    content_type=content_type,
                    content=content,
                )
                self.assertFalse(evidence.valid)
                self.assertEqual(evidence.failure_code, expected_code)

    def test_crawl_status_must_be_success_or_partial(self):
        content = "x" * 300
        evidence = PageEvidence.from_content(
            requested_url="https://example.com",
            final_url="https://example.com",
            status_code=200,
            content_type="text/html",
            content=content,
        )

        for status in (CrawlStatus.FAILED, CrawlStatus.BLOCKED, CrawlStatus.EMPTY):
            result = CrawlResult(
                url="https://example.com",
                pages={"https://example.com": content},
                evidence=[evidence],
                status=status,
            )
            self.assertFalse(result.is_auditable)

    def test_requires_minimum_total_content(self):
        with self.assertRaises(CrawlEvidenceError) as raised:
            ensure_auditable_pages({"https://example.com": "x" * 150})

        self.assertEqual(str(raised.exception), "insufficient_total_content")

    def test_requires_matching_page_evidence_not_only_content(self):
        result = CrawlResult(
            url="https://example.com",
            pages={"https://example.com": "x" * 300},
            evidence=[],
            status=CrawlStatus.SUCCESS,
        )

        self.assertFalse(result.is_auditable)


if __name__ == "__main__":
    unittest.main()
