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


if __name__ == "__main__":
    unittest.main()
