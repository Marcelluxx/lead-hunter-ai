import unittest
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from src.application.privacy_policy import PrivacyExportService, PrivacyPolicyError
from src.application.suppression import SuppressionService
from src.domain.contacts import ContactClassification
from src.infrastructure.database import Database
from src.infrastructure.models import (
    Base,
    ContactModel,
    WorkspacePrivacyPolicyModel,
)


class PrivacyExportGateTests(unittest.TestCase):
    def setUp(self):
        self.database = Database("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.database.engine)
        self.workspace_id = uuid.uuid4()
        self.suppression = SuppressionService(b"x" * 32)
        self.service = PrivacyExportService(self.suppression)

    def tearDown(self):
        self.database.engine.dispose()

    def _contact(self, value, classification, expires_at):
        return ContactModel(
            workspace_id=self.workspace_id,
            kind="email",
            normalized_value=value,
            display_value=value,
            fingerprint=self.suppression.fingerprint("email", value),
            source_url="https://example.it/contatti",
            collected_at=datetime.now(timezone.utc),
            extraction_method="mailto",
            confidence=1.0,
            classification=classification,
            expires_at=expires_at,
            evidence_sha256="f" * 64,
            rules_version="test",
        )

    def test_export_removes_expired_and_suppressed_contacts(self):
        now = datetime.now(timezone.utc)
        with self.database.session() as session:
            session.add(
                WorkspacePrivacyPolicyModel(
                    workspace_id=self.workspace_id,
                    purpose="B2B",
                    legal_basis="Legittimo interesse valutato",
                    privacy_contact="privacy@example.it",
                    market="IT_EU",
                    named_contact_retention_days=90,
                    policy_version="privacy-v1",
                    enabled=True,
                )
            )
            session.add_all(
                [
                    self._contact(
                        "info@example.it",
                        ContactClassification.GENERIC_BUSINESS.value,
                        now + timedelta(days=10),
                    ),
                    self._contact(
                        "expired@example.it",
                        ContactClassification.NAMED_PROFESSIONAL.value,
                        now - timedelta(seconds=1),
                    ),
                    self._contact(
                        "blocked@example.it",
                        ContactClassification.NAMED_PROFESSIONAL.value,
                        now + timedelta(days=10),
                    ),
                ]
            )
            self.suppression.suppress(
                session,
                workspace_id=self.workspace_id,
                kind="email",
                value="blocked@example.it",
                scope="workspace",
                reason="opposition",
            )
        with self.database.session() as session:
            allowed = self.service.exportable_contacts(
                session,
                workspace_id=self.workspace_id,
                now=now,
            )
            self.assertEqual([item.normalized_value for item in allowed], ["info@example.it"])
            remaining = session.scalars(select(ContactModel)).all()
            self.assertEqual(len(remaining), 2)

    def test_named_export_fails_closed_without_policy(self):
        now = datetime.now(timezone.utc)
        with self.database.session() as session:
            session.add(
                self._contact(
                    "person@example.it",
                    ContactClassification.NAMED_PROFESSIONAL.value,
                    now + timedelta(days=10),
                )
            )
        with self.assertRaises(PrivacyPolicyError):
            with self.database.session() as session:
                self.service.exportable_contacts(
                    session,
                    workspace_id=self.workspace_id,
                    now=now,
                )


if __name__ == "__main__":
    unittest.main()
