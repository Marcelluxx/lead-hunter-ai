from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.exc import ProgrammingError

from src.application.suppression import SuppressionService
from src.infrastructure.models import (
    ContactModel,
    JobModel,
    LeadModel,
    SuppressionEntryModel,
    UserModel,
    WorkspaceModel,
)
from src.workers.retention import run_retention_batch
from src.workers.retention_scheduler import enqueue_active_workspaces
from tests.integration.postgres_helpers import POSTGRES_AVAILABLE, databases


@unittest.skipUnless(POSTGRES_AVAILABLE, "PostgreSQL integration URLs not configured")
class RetentionDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.owner, self.app, self.worker = databases()
        self.user_id = uuid.uuid4()
        self.workspace_a = uuid.uuid4()
        self.workspace_b = uuid.uuid4()
        self.service = SuppressionService(b"integration-suppression-key-32!!")
        now = datetime.now(timezone.utc)
        with self.owner.session() as session:
            session.add(
                UserModel(
                    id=self.user_id,
                    email=f"retention-{self.user_id}@example.test",
                    password_hash="integration-only",
                    display_name="Retention RLS",
                )
            )
            session.add_all(
                [
                    WorkspaceModel(id=self.workspace_a, slug=f"ret-a-{self.workspace_a.hex}", name="A"),
                    WorkspaceModel(id=self.workspace_b, slug=f"ret-b-{self.workspace_b.hex}", name="B"),
                ]
            )
            session.flush()
            for workspace_id, marker in ((self.workspace_a, "a"), (self.workspace_b, "b")):
                job = JobModel(
                    workspace_id=workspace_id,
                    created_by=self.user_id,
                    kind="integration",
                    idempotency_key=f"retention-{marker}",
                    parameters={},
                    estimated_cost=Decimal("0"),
                )
                session.add(job)
                session.flush()
                lead = LeadModel(workspace_id=workspace_id, job_id=job.id)
                session.add(lead)
                session.flush()
                session.add(
                    ContactModel(
                        workspace_id=workspace_id,
                        lead_id=lead.id,
                        kind="email",
                        normalized_value=f"expired-{marker}@example.test",
                        display_value=f"expired-{marker}@example.test",
                        fingerprint=f"{1 if marker == 'a' else 2:064x}",
                        source_url="https://example.test/team",
                        collected_at=now - timedelta(days=100),
                        extraction_method="regex",
                        confidence=0.85,
                        classification="named_professional",
                        expires_at=now - timedelta(days=1),
                        evidence_sha256="a" * 64,
                        rules_version="integration",
                    )
                )
            self.service.suppress(
                session,
                workspace_id=self.workspace_a,
                kind="email",
                value="global@example.test",
                scope="global",
                reason="integration",
            )

    def tearDown(self):
        with self.owner.session() as session:
            session.execute(
                delete(WorkspaceModel).where(
                    WorkspaceModel.id.in_((self.workspace_a, self.workspace_b))
                )
            )
            session.execute(
                delete(SuppressionEntryModel).where(
                    SuppressionEntryModel.scope_key == "global",
                    SuppressionEntryModel.reason == "integration",
                )
            )
            session.execute(delete(UserModel).where(UserModel.id == self.user_id))
        for database in (self.owner, self.app, self.worker):
            database.engine.dispose()

    def test_retention_and_suppression_are_rls_scoped(self):
        with self.app.session() as session:
            self.assertEqual(session.scalars(select(ContactModel)).all(), [])
        with self.app.session(workspace_id=self.workspace_a) as session:
            self.assertEqual(len(session.scalars(select(ContactModel)).all()), 1)
            self.assertTrue(
                self.service.is_suppressed(
                    session,
                    workspace_id=self.workspace_a,
                    kind="email",
                    value="global@example.test",
                )
            )
            result = run_retention_batch(
                session,
                workspace_id=self.workspace_a,
                now=datetime.now(timezone.utc),
            )
            self.assertEqual(result.deleted_by_category, {"contact": 1})
            # Global suppressions can be read for enforcement but not deleted by tenants.
            deleted = session.execute(
                delete(SuppressionEntryModel).where(
                    SuppressionEntryModel.scope_key == "global"
                )
            )
            self.assertEqual(deleted.rowcount, 0)
        with self.owner.session() as session:
            contacts = session.scalars(select(ContactModel)).all()
            self.assertEqual([item.workspace_id for item in contacts], [self.workspace_b])

    def test_worker_scheduler_gets_only_workspace_uuids_via_narrow_function(self):
        class Publisher:
            def __init__(self):
                self.ids = []

            def publish(self, workspace_id):
                self.ids.append(workspace_id)

        publisher = Publisher()
        with self.worker.session() as session:
            count = enqueue_active_workspaces(session, publisher=publisher)
        with self.assertRaises(ProgrammingError):
            with self.worker.session() as session:
                session.scalars(select(WorkspaceModel)).all()
        self.assertGreaterEqual(count, 2)
        self.assertIn(self.workspace_a, publisher.ids)
        self.assertIn(self.workspace_b, publisher.ids)


if __name__ == "__main__":
    unittest.main()
