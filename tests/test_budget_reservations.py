import unittest

from src.application.budgets import BudgetExceeded, BudgetService
from src.application.workspaces import bootstrap_platform
from src.infrastructure.models import JobModel, UsageBudgetModel
from tests.platform_helpers import platform_fixture


class BudgetReservationTests(unittest.TestCase):
    def setUp(self):
        self.database, self.passwords, _, _ = platform_fixture()
        self.service = BudgetService()
        with self.database.session() as session:
            self.user, self.workspace = bootstrap_platform(
                session,
                email="admin@example.test",
                password="correct horse battery staple",
                display_name="Admin",
                workspace_slug="first-workspace",
                workspace_name="First",
                hard_limit="10",
                passwords=self.passwords,
            )

    def tearDown(self):
        self.database.engine.dispose()

    def _job(self, session, key):
        job = JobModel(
            workspace_id=self.workspace.id,
            created_by=self.user.id,
            kind="audit",
            idempotency_key=key,
            parameters={},
            estimated_cost="0",
        )
        session.add(job)
        session.flush()
        return job

    def test_hard_stop_counts_spent_and_reserved(self):
        with self.database.session() as session:
            first = self._job(session, "first")
            self.service.reserve(session, workspace_id=self.workspace.id, job_id=first.id, amount="8")
            second = self._job(session, "second")
            with self.assertRaises(BudgetExceeded):
                self.service.reserve(session, workspace_id=self.workspace.id, job_id=second.id, amount="3")
        with self.database.session() as session:
            budget = session.query(UsageBudgetModel).one()
            self.assertEqual(str(budget.reserved), "8.000000")

    def test_settlement_releases_residual_and_warns_at_eighty_percent(self):
        with self.database.session() as session:
            job = self._job(session, "settle")
            self.service.reserve(session, workspace_id=self.workspace.id, job_id=job.id, amount="9")
            snapshot = self.service.settle(session, job_id=job.id, actual_amount="8")
            self.assertTrue(snapshot.warning)
            self.assertEqual(str(snapshot.reserved), "0.000000")
            self.assertEqual(str(snapshot.spent), "8.000000")


if __name__ == "__main__":
    unittest.main()
