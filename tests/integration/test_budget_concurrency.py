from __future__ import annotations

import threading
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

from sqlalchemy import func, select

from src.application.budgets import BudgetExceeded, BudgetService
from src.infrastructure.database import Database
from src.infrastructure.models import (
    JobModel,
    UsageBudgetModel,
    UsageReservationModel,
    UserModel,
    WorkspaceModel,
)
from tests.integration.postgres_helpers import (
    POSTGRES_AVAILABLE,
    APP_URL,
    databases,
    delete_fixture,
)


@unittest.skipUnless(POSTGRES_AVAILABLE, "PostgreSQL integration URLs not configured")
class BudgetConcurrencyTests(unittest.TestCase):
    def setUp(self):
        self.owner, self.app, self.worker = databases()
        self.user_id = uuid.uuid4()
        self.workspace_id = uuid.uuid4()
        self.job_ids = (uuid.uuid4(), uuid.uuid4())
        with self.owner.session() as session:
            session.add(
                UserModel(
                    id=self.user_id,
                    email=f"budget-{self.user_id}@example.test",
                    password_hash="integration-only",
                    display_name="Budget Test",
                )
            )
            session.add(
                WorkspaceModel(
                    id=self.workspace_id,
                    slug=f"budget-{self.workspace_id.hex}",
                    name="Budget",
                )
            )
            session.flush()
            session.add(
                UsageBudgetModel(
                    workspace_id=self.workspace_id,
                    hard_limit=Decimal("10"),
                )
            )
            session.add_all(
                [
                    JobModel(
                        id=job_id,
                        workspace_id=self.workspace_id,
                        created_by=self.user_id,
                        kind="integration",
                        state="queued",
                        idempotency_key=f"concurrency-{index}",
                        parameters={},
                        estimated_cost=Decimal("7"),
                    )
                    for index, job_id in enumerate(self.job_ids)
                ]
            )

    def tearDown(self):
        delete_fixture(self.owner, self.workspace_id, self.user_id)
        for database in (self.owner, self.app, self.worker):
            database.engine.dispose()

    def test_two_simultaneous_reservations_cannot_exceed_hard_limit(self):
        barrier = threading.Barrier(2)

        def reserve(job_id: uuid.UUID) -> str:
            database = Database(APP_URL)
            try:
                barrier.wait(timeout=5)
                with database.session(workspace_id=self.workspace_id) as session:
                    BudgetService().reserve(
                        session,
                        workspace_id=self.workspace_id,
                        job_id=job_id,
                        amount=Decimal("7"),
                    )
                return "reserved"
            except BudgetExceeded:
                return "rejected"
            finally:
                database.engine.dispose()

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(reserve, self.job_ids))

        self.assertCountEqual(outcomes, ["reserved", "rejected"])
        with self.owner.session() as session:
            budget = session.scalar(
                select(UsageBudgetModel).where(
                    UsageBudgetModel.workspace_id == self.workspace_id
                )
            )
            reservation_count = session.scalar(
                select(func.count()).select_from(UsageReservationModel).where(
                    UsageReservationModel.workspace_id == self.workspace_id
                )
            )
            self.assertEqual(budget.reserved, Decimal("7.000000"))
            self.assertEqual(reservation_count, 1)


if __name__ == "__main__":
    unittest.main()
