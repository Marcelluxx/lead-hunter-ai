import unittest
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from src.application.data_subject_requests import DataSubjectRequestService
from src.application.suppression import SuppressionService
from src.infrastructure.database import Database
from src.infrastructure.models import (
    Base,
    ContactModel,
    DataSubjectRequestModel,
    SuppressionEntryModel,
)


class DataSubjectRequestTests(unittest.TestCase):
    def setUp(self):
        self.database = Database("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.database.engine)
        self.workspace_id = uuid.uuid4()
        self.suppression = SuppressionService(b"r" * 32)
        self.service = DataSubjectRequestService(self.suppression)
        with self.database.session() as session:
            session.add(
                ContactModel(
                    workspace_id=self.workspace_id,
                    kind="email",
                    normalized_value="person@example.it",
                    display_value="person@example.it",
                    fingerprint=self.suppression.fingerprint("email", "person@example.it"),
                    source_url="https://example.it/team",
                    collected_at=datetime.now(timezone.utc),
                    extraction_method="regex",
                    confidence=0.85,
                    classification="named_professional",
                    expires_at=datetime.now(timezone.utc) + timedelta(days=30),
                    evidence_sha256="1" * 64,
                    rules_version="test",
                )
            )

    def tearDown(self):
        self.database.engine.dispose()

    def test_erasure_is_idempotent_auditable_and_prevents_reacquisition(self):
        request_id = uuid.uuid4()
        with self.database.session() as session:
            first = self.service.erase_and_suppress(
                session,
                request_id=request_id,
                workspace_id=self.workspace_id,
                actor_user_id=None,
                kind="email",
                value="PERSON@example.it",
                scope="global",
            )
            second = self.service.erase_and_suppress(
                session,
                request_id=request_id,
                workspace_id=self.workspace_id,
                actor_user_id=None,
                kind="email",
                value="person@example.it",
                scope="global",
            )
            self.assertEqual(first.id, second.id)
        with self.database.session() as session:
            self.assertEqual(session.scalars(select(ContactModel)).all(), [])
            self.assertEqual(len(session.scalars(select(SuppressionEntryModel)).all()), 1)
            request = session.scalar(select(DataSubjectRequestModel))
            self.assertEqual(request.deleted_count, 1)
            self.assertNotIn("person@example.it", str(request.__dict__).lower())

    def test_access_and_rectification_are_controlled_and_auditable(self):
        access_id = uuid.uuid4()
        rectify_id = uuid.uuid4()
        with self.database.session() as session:
            data = self.service.subject_data(
                session,
                workspace_id=self.workspace_id,
                kind="email",
                value="person@example.it",
            )
            access = self.service.record_access(
                session,
                request_id=access_id,
                workspace_id=self.workspace_id,
                actor_user_id=None,
                kind="email",
                value="person@example.it",
            )
            self.assertEqual(data[0]["value"], "person@example.it")
            self.assertEqual(access.request_kind, "access")
        with self.database.session() as session:
            request = self.service.rectify(
                session,
                request_id=rectify_id,
                workspace_id=self.workspace_id,
                actor_user_id=None,
                kind="email",
                value="person@example.it",
                replacement_value="info@example.it",
            )
            self.assertEqual(request.request_kind, "rectification")
        with self.database.session() as session:
            contact = session.scalar(select(ContactModel))
            self.assertEqual(contact.normalized_value, "info@example.it")
            self.assertTrue(
                self.suppression.is_suppressed(
                    session,
                    workspace_id=self.workspace_id,
                    kind="email",
                    value="person@example.it",
                )
            )


if __name__ == "__main__":
    unittest.main()
