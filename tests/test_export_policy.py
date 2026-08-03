import unittest
from datetime import datetime, timezone

from src.application.export_policy import ExportPolicy, ExportPolicyError
from src.domain.discovery import ProviderAttribution, TransientCandidate
from src.domain.provenance import DataSource, FieldProvenance, VerifiedLead


class ExportPolicyTests(unittest.TestCase):
    def test_transient_provider_candidate_is_rejected(self):
        candidate = TransientCandidate(
            provider="google_places",
            external_id="id",
            display_name="Name",
            website_url=None,
            collected_at=datetime.now(timezone.utc),
            attribution=ProviderAttribution("google_places", "Google Maps", "terms", "privacy"),
        )
        with self.assertRaises(ExportPolicyError):
            ExportPolicy.require_exportable([candidate], "no_website")

    def test_verified_official_site_record_is_allowed(self):
        provenance = FieldProvenance(
            DataSource.OFFICIAL_WEBSITE,
            "https://example.test",
            datetime.now(timezone.utc),
        )
        lead = VerifiedLead(
            business_name="Example",
            category="dentista",
            website="https://example.test",
            provenance={"business_name": provenance, "website": provenance},
        )
        ExportPolicy.require_exportable([lead], "with_website")

    def test_provider_reference_cannot_become_report_attribute(self):
        provenance = FieldProvenance(
            DataSource.PROVIDER_REFERENCE,
            None,
            datetime.now(timezone.utc),
        )
        lead = VerifiedLead(
            business_name="Example",
            category="dentista",
            website="https://example.test",
            provenance={"business_name": provenance},
        )
        with self.assertRaises(ExportPolicyError):
            ExportPolicy.require_exportable([lead], "with_website")

    def test_contact_export_requires_suppression_boundary(self):
        from src.domain.contacts import ContactExtractionMethod, ContactPoint

        now = datetime.now(timezone.utc)
        contact = ContactPoint.from_email(
            "info@example.test",
            source_url="https://example.test",
            collected_at=now,
            extraction_method=ContactExtractionMethod.MAILTO,
            evidence_sha256="a" * 64,
        )
        provenance = FieldProvenance(DataSource.OFFICIAL_WEBSITE, "https://example.test", now)
        lead = VerifiedLead(
            "Example",
            "dentista",
            "https://example.test",
            contacts=(contact,),
            provenance={"business_name": provenance, "website": provenance},
        )
        with self.assertRaises(ExportPolicyError):
            ExportPolicy.require_exportable([lead], "with_website")
        ExportPolicy.require_exportable(
            [lead], "with_website", suppression_checker=lambda _: False
        )
        with self.assertRaises(ExportPolicyError):
            ExportPolicy.require_exportable(
                [lead], "with_website", suppression_checker=lambda _: True
            )


if __name__ == "__main__":
    unittest.main()
