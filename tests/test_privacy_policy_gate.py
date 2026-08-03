import unittest
from dataclasses import replace
from datetime import timedelta
import uuid
from datetime import datetime, timezone

from src.application.privacy_policy import PrivacyPolicyError, PrivacyPolicyGate
from src.domain.contacts import ContactExtractionMethod, ContactPoint
from src.domain.privacy import WorkspacePrivacyPolicy


class PrivacyPolicyGateTests(unittest.TestCase):
    def setUp(self):
        self.named = ContactPoint.from_email(
            "mario.rossi@example.it",
            source_url="https://example.it/team",
            collected_at=datetime.now(timezone.utc),
            extraction_method=ContactExtractionMethod.MAILTO,
            evidence_sha256="d" * 64,
        )

    def test_named_contact_requires_complete_italy_eu_policy(self):
        with self.assertRaises(PrivacyPolicyError):
            PrivacyPolicyGate.require_contact_allowed(self.named, None)

        policy = WorkspacePrivacyPolicy(
            workspace_id=uuid.uuid4(),
            purpose="Analisi commerciale B2B documentata",
            legal_basis="Legittimo interesse valutato dal titolare",
            privacy_contact="privacy@example.it",
            market="IT_EU",
            named_contact_retention_days=90,
        )
        PrivacyPolicyGate.require_contact_allowed(self.named, policy)

    def test_retention_over_ninety_days_is_rejected(self):
        with self.assertRaises(ValueError):
            WorkspacePrivacyPolicy(
                workspace_id=uuid.uuid4(),
                purpose="B2B",
                legal_basis="Legittimo interesse",
                privacy_contact="privacy@example.it",
                market="IT_EU",
                named_contact_retention_days=91,
            )

    def test_expired_contact_is_always_rejected(self):
        now = datetime.now(timezone.utc)
        old = ContactPoint.from_email(
            "info@example.it",
            source_url="https://example.it/contatti",
            collected_at=now - timedelta(days=400),
            extraction_method=ContactExtractionMethod.MAILTO,
            evidence_sha256="e" * 64,
        )
        with self.assertRaises(PrivacyPolicyError):
            PrivacyPolicyGate.require_contact_allowed(old, None, now=now)


if __name__ == "__main__":
    unittest.main()
