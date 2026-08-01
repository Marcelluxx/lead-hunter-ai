import unittest
from datetime import datetime, timedelta, timezone

from src.domain.contacts import (
    CONTACT_CLASSIFICATION_RULES_VERSION,
    ContactClassification,
    ContactExtractionMethod,
    ContactPoint,
    classify_email,
)


class ContactClassificationTests(unittest.TestCase):
    def test_generic_business_aliases_are_explicit_and_versioned(self):
        for value in ("info@example.it", "commerciale@example.it", "sales@example.eu"):
            with self.subTest(value=value):
                self.assertEqual(classify_email(value), ContactClassification.GENERIC_BUSINESS)

        contact = ContactPoint.from_email(
            " INFO@Example.IT ",
            source_url="https://example.it/contatti",
            collected_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
            extraction_method=ContactExtractionMethod.MAILTO,
            evidence_sha256="a" * 64,
        )
        self.assertEqual(contact.normalized_value, "info@example.it")
        self.assertEqual(contact.rules_version, CONTACT_CLASSIFICATION_RULES_VERSION)
        self.assertEqual(
            contact.expires_at - contact.collected_at,
            timedelta(days=365),
        )

    def test_ambiguous_local_parts_fail_closed_as_named_professional(self):
        for value in ("m.rossi@example.it", "direzione.roma@example.it", "hello-team@example.it"):
            with self.subTest(value=value):
                self.assertEqual(
                    classify_email(value),
                    ContactClassification.NAMED_PROFESSIONAL,
                )


if __name__ == "__main__":
    unittest.main()
