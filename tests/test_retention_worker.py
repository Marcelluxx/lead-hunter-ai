import unittest
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from src.infrastructure.database import Database
from src.infrastructure.models import (
    Base,
    ContactModel,
    JobModel,
    LeadModel,
    RetentionEventModel,
    UserModel,
    WorkspaceModel,
)
from src.workers.retention import run_retention_batch


class RetentionWorkerTests(unittest.TestCase):
    def setUp(self):
        self.database = Database("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.database.engine)
        self.workspace_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        with self.database.session() as session:
            user = UserModel(
                email="retention@example.test",
                password_hash="hash",
                display_name="Retention",
            )
            workspace = WorkspaceModel(id=self.workspace_id, slug="retention", name="Retention")
            session.add_all([user, workspace])
            session.flush()
            job = JobModel(
                workspace_id=self.workspace_id,
                created_by=user.id,
                kind="audit",
                idempotency_key="retention",
                parameters={},
                estimated_cost=Decimal("0"),
            )
            session.add(job)
            session.flush()
            lead = LeadModel(workspace_id=self.workspace_id, job_id=job.id)
            session.add(lead)
            session.flush()
            for index in range(3):
                session.add(
                    ContactModel(
                        workspace_id=self.workspace_id,
                        lead_id=lead.id,
                        kind="email",
                        normalized_value=f"person{index}@example.it",
                        display_value=f"person{index}@example.it",
                        fingerprint=f"{index:064x}",
                        source_url="https://example.it/team",
                        collected_at=now - timedelta(days=100),
                        extraction_method="regex",
                        confidence=0.85,
                        classification="named_professional",
                        expires_at=now - timedelta(days=1),
                        evidence_sha256="e" * 64,
                        rules_version="test",
                    )
                )

    def tearDown(self):
        self.database.engine.dispose()

    def test_worker_uses_bounded_restartable_batches_and_logs_counts_only(self):
        now = datetime.now(timezone.utc)
        with self.database.session() as session:
            result = run_retention_batch(
                session,
                workspace_id=self.workspace_id,
                now=now,
                batch_size=2,
            )
            self.assertEqual(result.deleted_by_category, {"contact": 2})
            self.assertTrue(result.has_more)
        with self.database.session() as session:
            self.assertEqual(len(session.scalars(select(ContactModel)).all()), 1)
            event = session.scalar(select(RetentionEventModel))
            self.assertEqual(event.deleted_count, 2)
            self.assertNotIn("@example.it", str(event.__dict__))


if __name__ == "__main__":
    unittest.main()
