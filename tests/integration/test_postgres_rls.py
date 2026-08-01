from __future__ import annotations

import unittest
import uuid
from decimal import Decimal

from sqlalchemy import delete, select, text
from sqlalchemy.exc import ProgrammingError

from src.infrastructure.database import resolve_job_workspace
from src.infrastructure.models import JobModel, UserModel, WorkspaceModel
from tests.integration.postgres_helpers import (
    POSTGRES_AVAILABLE,
    databases,
)


@unittest.skipUnless(POSTGRES_AVAILABLE, "PostgreSQL integration URLs not configured")
class PostgresRlsTests(unittest.TestCase):
    def setUp(self):
        self.owner, self.app, self.worker = databases()
        self.user_id = uuid.uuid4()
        self.workspace_a = uuid.uuid4()
        self.workspace_b = uuid.uuid4()
        self.job_a = uuid.uuid4()
        self.job_b = uuid.uuid4()
        with self.owner.session() as session:
            session.add(
                UserModel(
                    id=self.user_id,
                    email=f"rls-{self.user_id}@example.test",
                    password_hash="integration-only",
                    display_name="RLS Test",
                )
            )
            session.add_all(
                [
                    WorkspaceModel(id=self.workspace_a, slug=f"rls-a-{self.workspace_a.hex}", name="A"),
                    WorkspaceModel(id=self.workspace_b, slug=f"rls-b-{self.workspace_b.hex}", name="B"),
                ]
            )
            session.flush()
            session.add_all(
                [
                    self._job(self.job_a, self.workspace_a, "a"),
                    self._job(self.job_b, self.workspace_b, "b"),
                ]
            )

    def tearDown(self):
        with self.owner.session() as session:
            session.execute(
                delete(WorkspaceModel).where(
                    WorkspaceModel.id.in_((self.workspace_a, self.workspace_b))
                )
            )
            session.execute(delete(UserModel).where(UserModel.id == self.user_id))
        for database in (self.owner, self.app, self.worker):
            database.engine.dispose()

    def _job(self, job_id, workspace_id, key):
        return JobModel(
            id=job_id,
            workspace_id=workspace_id,
            created_by=self.user_id,
            kind="integration",
            state="queued",
            idempotency_key=key,
            parameters={},
            estimated_cost=Decimal("1"),
        )

    def test_rls_is_fail_closed_and_scopes_rows_to_workspace(self):
        with self.app.session() as session:
            self.assertEqual(session.scalars(select(JobModel)).all(), [])
        with self.app.session(workspace_id=self.workspace_a) as session:
            jobs = session.scalars(select(JobModel)).all()
            self.assertEqual([job.id for job in jobs], [self.job_a])
            self.assertIsNone(session.get(JobModel, self.job_b))

    def test_uuid_resolver_is_worker_only(self):
        with self.assertRaises(ProgrammingError):
            with self.app.session() as session:
                resolve_job_workspace(session, self.job_a)
        with self.worker.session() as session:
            self.assertEqual(resolve_job_workspace(session, self.job_a), self.workspace_a)

    def test_runtime_roles_cannot_bypass_rls(self):
        with self.owner.session() as session:
            roles = session.execute(
                text(
                    "SELECT rolname, rolsuper, rolbypassrls FROM pg_roles "
                    "WHERE rolname IN ('leadhunter_app', 'leadhunter_worker')"
                )
            ).all()
        self.assertEqual(len(roles), 2)
        self.assertTrue(all(not row.rolsuper and not row.rolbypassrls for row in roles))


if __name__ == "__main__":
    unittest.main()
