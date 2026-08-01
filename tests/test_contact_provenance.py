import unittest
from datetime import datetime, timezone

from src.domain.contacts import ContactExtractionMethod, ContactPoint


class ContactProvenanceTests(unittest.TestCase):
    def test_contact_requires_source_timestamp_and_evidence(self):
        collected_at = datetime(2026, 8, 1, 10, tzinfo=timezone.utc)
        contact = ContactPoint.from_email(
            "mario.rossi@example.it",
            source_url="https://example.it/team",
            collected_at=collected_at,
            extraction_method=ContactExtractionMethod.REGEX,
            evidence_sha256="b" * 64,
        )
        self.assertEqual(contact.source_url, "https://example.it/team")
        self.assertEqual(contact.collected_at, collected_at)
        self.assertEqual(contact.evidence_sha256, "b" * 64)
        self.assertEqual(contact.confidence, 0.85)

    def test_naive_timestamp_and_missing_source_are_rejected(self):
        for source_url, collected_at in (
            ("", datetime.now(timezone.utc)),
            ("https://example.it", datetime(2026, 8, 1)),
        ):
            with self.subTest(source_url=source_url, collected_at=collected_at):
                with self.assertRaises(ValueError):
                    ContactPoint.from_email(
                        "info@example.it",
                        source_url=source_url,
                        collected_at=collected_at,
                        extraction_method=ContactExtractionMethod.REGEX,
                        evidence_sha256="c" * 64,
                    )


if __name__ == "__main__":
    unittest.main()
