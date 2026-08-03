import unittest
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from src.application.contacts import ContactService
from src.application.suppression import SuppressionService
from src.domain.contacts import ContactExtractionMethod, ContactPoint
from src.infrastructure.database import Database
from src.infrastructure.models import Base, ContactModel


class ContactPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.database = Database("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.database.engine)
        self.workspace_id = uuid.uuid4()
        self.lead_id = uuid.uuid4()
        self.suppression = SuppressionService(b"p" * 32)
        self.service = ContactService(self.suppression)

    def tearDown(self):
        self.database.engine.dispose()

    def _contact(self, value):
        return ContactPoint.from_email(
            value,
            source_url="https://example.it/contatti",
            collected_at=datetime.now(timezone.utc),
            extraction_method=ContactExtractionMethod.MAILTO,
            evidence_sha256="2" * 64,
        )

    def test_named_contact_without_policy_is_not_persisted(self):
        with self.database.session() as session:
            result = self.service.persist(
                session,
                workspace_id=self.workspace_id,
                lead_id=self.lead_id,
                contacts=[self._contact("mario.rossi@example.it")],
            )
            self.assertEqual(result.policy_rejected, 1)
        with self.database.session() as session:
            self.assertEqual(session.scalars(select(ContactModel)).all(), [])

    def test_suppression_blocks_reacquisition_before_persistence(self):
        with self.database.session() as session:
            self.suppression.suppress(
                session,
                workspace_id=self.workspace_id,
                kind="email",
                value="info@example.it",
                scope="workspace",
                reason="opposition",
            )
            result = self.service.persist(
                session,
                workspace_id=self.workspace_id,
                lead_id=self.lead_id,
                contacts=[self._contact("INFO@example.it")],
            )
            self.assertEqual(result.suppressed, 1)
        with self.database.session() as session:
            self.assertEqual(session.scalars(select(ContactModel)).all(), [])


if __name__ == "__main__":
    unittest.main()
