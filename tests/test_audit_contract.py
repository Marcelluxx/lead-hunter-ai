import unittest

from src.domain import AuditValidationError, WebsiteAuditResult


class WebsiteAuditResultTests(unittest.TestCase):
    def test_accepts_allowlisted_public_fields_and_ignores_unknown_fields(self):
        result = WebsiteAuditResult.from_llm(
            {
                "website_score": "7/10",
                "diagnosis": "Navigazione poco chiara.",
                "site_brief": "Studio professionale locale.",
                "framework": "WordPress",
                "cold_message": "Il percorso contatti può essere semplificato.",
                "full_prompt": "must never be exposed",
            }
        )

        public = result.to_public_dict()

        self.assertEqual(public["website_score"], 7)
        self.assertNotIn("full_prompt", public)
        self.assertEqual(
            set(public),
            {"website_score", "diagnosis", "site_brief", "framework", "cold_message"},
        )

    def test_rejects_missing_wrong_type_and_out_of_range_fields(self):
        invalid_payloads = [
            {},
            {
                "website_score": 11,
                "diagnosis": "x",
                "site_brief": "x",
                "cold_message": "x",
            },
            {
                "website_score": 5,
                "diagnosis": {"nested": "not allowed"},
                "site_brief": "x",
                "cold_message": "x",
            },
        ]

        for payload in invalid_payloads:
            with self.subTest(payload=payload), self.assertRaises(AuditValidationError):
                WebsiteAuditResult.from_llm(payload)


if __name__ == "__main__":
    unittest.main()
