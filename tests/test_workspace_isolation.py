import unittest

from src.application.workspaces import bootstrap_platform
from src.infrastructure.database import resolve_job_workspace
from src.infrastructure.models import JobModel
from tests.platform_helpers import platform_fixture


class WorkspaceIsolationTests(unittest.TestCase):
    def test_worker_resolves_only_workspace_uuid_from_job_uuid(self):
        database, passwords, _, _ = platform_fixture()
        with database.session() as session:
            user, workspace = bootstrap_platform(
                session,
                email="admin@example.test",
                password="correct horse battery staple",
                display_name="Admin",
                workspace_slug="first-workspace",
                workspace_name="First",
                hard_limit="10",
                passwords=passwords,
            )
            job = JobModel(
                workspace_id=workspace.id,
                created_by=user.id,
                kind="audit",
                state="queued",
                idempotency_key="resolve",
                parameters={"secret": "not returned"},
                estimated_cost="1",
            )
            session.add(job)
            session.flush()
            job_id = job.id
            workspace_id = workspace.id
        with database.session() as session:
            self.assertEqual(resolve_job_workspace(session, job_id), workspace_id)
        database.engine.dispose()


if __name__ == "__main__":
    unittest.main()
