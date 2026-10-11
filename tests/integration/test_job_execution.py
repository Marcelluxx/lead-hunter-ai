import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from dataclasses import replace
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select

from src.application.budgets import BudgetService
from src.application.job_execution import JobExecutionService, JobExecutionError
from src.domain.job_parameters import parse_job_parameters
from src.domain.job_pricing import JobPricePolicy
from src.infrastructure.models import UserModel, WorkspaceModel, WorkspaceMembershipModel, SessionModel, JobModel, UsageBudgetModel, JobAttemptModel, UsageLedgerModel
from tests.integration.postgres_helpers import POSTGRES_AVAILABLE, databases, delete_fixture


@unittest.skipUnless(POSTGRES_AVAILABLE, 'PostgreSQL integration URLs not configured')
class JobExecutionPostgresTests(unittest.TestCase):
    def setUp(self):
        self.owner, self.app, self.worker = databases()
        self.user_id, self.workspace_id, self.session_id, self.job_id = uuid4(), uuid4(), uuid4(), uuid4()
        parameters = parse_job_parameters('discover.no_website', {'lat': 0, 'lng': 0, 'keywords': ['dentista']})
        quote = JobPricePolicy(version='test', google_request_ceiling='0.1').quote(parameters)
        with self.owner.session() as session:
            session.add(UserModel(id=self.user_id, email=f'job-{self.user_id}@example.test', password_hash='integration-only', display_name='Job'))
            session.add(WorkspaceModel(id=self.workspace_id, slug=f'job-{self.workspace_id}', name='Job'))
            session.flush()
            session.add(WorkspaceMembershipModel(workspace_id=self.workspace_id, user_id=self.user_id, role='admin'))
            session.add(SessionModel(id=self.session_id, user_id=self.user_id, refresh_token_hash='x' * 64,
                csrf_token_hash='y' * 64, mfa_verified=True, expires_at=datetime.now(timezone.utc) + timedelta(days=1)))
            session.add(UsageBudgetModel(workspace_id=self.workspace_id, hard_limit=100))
            session.flush()
            session.add(JobModel(id=self.job_id, workspace_id=self.workspace_id, created_by=self.user_id,
                kind=parameters.kind, parameters=parameters.payload, idempotency_key=str(self.job_id),
                estimated_cost=quote.total, auth_session_id=self.session_id, auth_session_version=1, cost_policy=quote.to_record()))
            session.flush()
            BudgetService().reserve(session, workspace_id=self.workspace_id, job_id=self.job_id, amount=quote.total)
        self.service = JobExecutionService(database=self.worker, installation_id=uuid4())

    def tearDown(self):
        delete_fixture(self.owner, self.workspace_id, self.user_id)
        for database in (self.owner, self.app, self.worker): database.engine.dispose()

    def test_concurrent_claim_has_one_owner_and_rls_blocks_cross_workspace(self):
        barrier = threading.Barrier(2)
        def claim(index):
            barrier.wait(timeout=5)
            return self.service.claim(self.job_id, worker_id=f'worker-{index}')
        with ThreadPoolExecutor(max_workers=2) as pool: results = list(pool.map(claim, [1, 2]))
        handles = [result for result in results if result is not None]
        self.assertEqual(len(handles), 1)
        with self.assertRaises(JobExecutionError): self.service.guard(replace(handles[0], workspace_id=uuid4())).require_execute()
        with self.owner.session() as session:
            self.assertEqual(len(session.scalars(select(JobAttemptModel).where(JobAttemptModel.job_id == self.job_id)).all()), 1)

    def test_concurrent_duplicate_charge_is_idempotent(self):
        barrier = threading.Barrier(2)
        def consume(_):
            barrier.wait(timeout=5)
            with self.worker.session(self.workspace_id) as session:
                return BudgetService().consume(session, job_id=self.job_id, amount='0.1', provider='google_places', operation_id=f'{self.job_id}:same-call')
        with ThreadPoolExecutor(max_workers=2) as pool: outcomes = list(pool.map(consume, [1, 2]))
        self.assertCountEqual(outcomes, [True, False])
        with self.owner.session() as session:
            budget = session.scalar(select(UsageBudgetModel).where(UsageBudgetModel.workspace_id == self.workspace_id))
            self.assertEqual(budget.spent, Decimal('0.1')); self.assertEqual(budget.reserved, Decimal('1.7'))
            self.assertEqual(len(session.scalars(select(UsageLedgerModel).where(UsageLedgerModel.operation_id == f'{self.job_id}:same-call')).all()), 1)

    def test_concurrent_commercial_admission_reserves_once_for_same_request(self):
        from src.application.authentication import AuthContext
        from src.application.jobs import JobService
        from tests.test_api_security import Publisher
        publisher = Publisher()
        service = JobService(budgets=BudgetService(), publisher=publisher)
        execution = JobExecutionService(database=self.app, installation_id=uuid4())
        auth = AuthContext(self.user_id, self.session_id, True)
        prices = JobPricePolicy(version='test', google_request_ceiling='0.1')
        barrier = threading.Barrier(2)
        def admit(_):
            barrier.wait(timeout=5)
            with self.app.session(self.workspace_id) as session:
                result = service.create_commercial(session, workspace_id=self.workspace_id, auth=auth,
                    kind='discover.no_website', parameters={'lat': 0, 'lng': 0, 'keywords': ['dentista']},
                    idempotency_key='concurrent-request', prices=prices, execution=execution)
                return result.job.id, result.created
        with ThreadPoolExecutor(max_workers=2) as pool: outcomes = list(pool.map(admit, [1, 2]))
        self.assertEqual(outcomes[0][0], outcomes[1][0])
        self.assertCountEqual([value[1] for value in outcomes], [True, False])
        self.assertEqual(len(publisher.messages), 1)
        with self.owner.session() as session:
            budget = session.scalar(select(UsageBudgetModel).where(UsageBudgetModel.workspace_id == self.workspace_id))
            self.assertEqual(budget.reserved, Decimal('3.6'))

    def test_worker_recovery_observes_scoped_jobs_with_least_privilege_role(self):
        from src.workers.recovery import recover_due_jobs
        from tests.test_api_security import Publisher
        publisher = Publisher()
        recover_due_jobs(self.worker, publisher=publisher)
        self.assertIn(self.job_id, publisher.messages)

    def test_worker_recovery_finalizes_expired_cancellation_after_origin_logout(self):
        from src.application.authentication import AuthContext
        from src.workers.recovery import recover_due_jobs
        from tests.test_api_security import Publisher
        clock = datetime.now(timezone.utc)
        self.service.now = lambda: clock
        handle = self.service.claim(self.job_id, worker_id='crashed')
        self.service.guard(handle).before_provider_call('google_places')
        api = JobExecutionService(database=self.app, installation_id=self.service.installation_id)
        api.cancel(self.job_id, workspace_id=self.workspace_id,
            auth=AuthContext(self.user_id, self.session_id, True))
        clock += timedelta(seconds=61)
        with self.owner.session() as session:
            session.get(SessionModel, self.session_id).revoked_at = clock
        publisher = Publisher()
        recover_due_jobs(self.worker, publisher=publisher, now=clock)
        self.assertIn(self.job_id, publisher.messages)
        self.assertIsNone(self.service.claim(self.job_id, worker_id='recovery'))
        with self.owner.session() as session:
            job = session.get(JobModel, self.job_id)
            budget = session.scalar(select(UsageBudgetModel).where(UsageBudgetModel.workspace_id == self.workspace_id))
            self.assertEqual(job.state, 'cancelled')
            self.assertEqual(job.attempt_count, 1)
            self.assertEqual(budget.spent, Decimal('0.1'))
            self.assertEqual(budget.reserved, Decimal('0'))
