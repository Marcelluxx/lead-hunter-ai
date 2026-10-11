import unittest
from datetime import timedelta
from uuid import UUID

from src.workers.recovery import recover_due_jobs
from tests import test_job_execution as job_tests
from tests.test_api_security import Publisher
from src.infrastructure.models import JobModel


class JobRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.fx = job_tests.JobExecutionTests(); self.fx.setUp(); self.addCleanup(self.fx.doCleanups)

    def test_recovers_queued_and_expired_lease_but_never_cancelled_or_live_work(self):
        queued = self.fx.job(); expired = self.fx.job(); live = self.fx.job(); cancelled = self.fx.job()
        self.fx.service.claim(expired, worker_id='crashed')
        self.fx.now += timedelta(seconds=61)
        self.fx.service.claim(live, worker_id='live')
        self.fx.service.cancel(cancelled, workspace_id=self.fx.workspace.id, auth=self.fx.auth)
        publisher = Publisher()
        count = recover_due_jobs(self.fx.database, publisher=publisher, now=self.fx.now)
        self.assertEqual(count, 2)
        self.assertCountEqual(publisher.messages, [queued, expired])
        self.assertTrue(all(type(message) is UUID for message in publisher.messages))

    def test_broker_outage_does_not_destroy_durable_queued_job(self):
        from src.application.jobs import JobService
        from src.application.budgets import BudgetService
        class Unavailable:
            def publish(self, job_id): raise ConnectionError('broker unavailable')
        service = JobService(budgets=BudgetService(), publisher=Unavailable(), durable_dispatch=True)
        with self.fx.database.session(self.fx.workspace.id) as session:
            created = service.create_commercial(session, workspace_id=self.fx.workspace.id, auth=self.fx.auth,
                kind='discover.no_website', parameters={'lat': 0, 'lng': 0, 'keywords': ['dentista']},
                idempotency_key='outage', prices=self.fx.prices, execution=self.fx.service)
        with self.fx.database.session(self.fx.workspace.id) as session:
            self.assertEqual(session.get(JobModel, created.job.id).state, 'queued')
        publisher = Publisher()
        self.assertEqual(recover_due_jobs(self.fx.database, publisher=publisher, now=self.fx.now), 1)
        self.assertEqual(publisher.messages, [created.job.id])

    def test_expired_cancelled_worker_recovery_releases_only_unused_budget(self):
        from decimal import Decimal
        from src.infrastructure.models import UsageBudgetModel, JobAttemptModel
        from sqlalchemy import select
        job_id = self.fx.job()
        handle = self.fx.service.claim(job_id, worker_id='lost-worker')
        self.fx.service.guard(handle).before_provider_call('google_places')
        self.fx.service.cancel(job_id, workspace_id=self.fx.workspace.id, auth=self.fx.auth)
        publisher = Publisher()
        self.assertEqual(recover_due_jobs(self.fx.database, publisher=publisher, now=self.fx.now), 0)
        self.fx.now += timedelta(seconds=61)
        self.assertEqual(recover_due_jobs(self.fx.database, publisher=publisher, now=self.fx.now), 1)
        self.assertEqual(publisher.messages, [job_id])
        self.assertIsNone(self.fx.service.claim(job_id, worker_id='recovery'))
        with self.fx.database.session(self.fx.workspace.id) as session:
            job = session.get(JobModel, job_id)
            budget = session.scalar(select(UsageBudgetModel))
            self.assertEqual(job.state, 'cancelled')
            self.assertEqual(job.error_code, 'job_cancelled')
            self.assertEqual(job.attempt_count, 1)
            self.assertEqual(budget.spent, Decimal('0.1'))
            self.assertEqual(budget.reserved, Decimal('0'))
            self.assertIsNotNone(session.get(JobAttemptModel, handle.attempt_id).finished_at)

    def test_periodic_cleanup_removes_owned_expired_archives_in_inactive_directories(self):
        import json
        import tempfile
        from pathlib import Path
        from uuid import uuid4
        from zipfile import ZipFile
        from src.workers.recovery import purge_workspace_archives
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); workspace = root / str(uuid4()); workspace.mkdir()
            identity = uuid4(); path = workspace / (str(identity) + '.zip')
            with ZipFile(path, 'w') as archive:
                archive.writestr('manifest.json', json.dumps({'schema_version': 1,
                    'classification': 'PRIVATE_REDACTED_DIAGNOSTICS', 'run_id': str(identity), 'expires_at': 99}))
            ordinary = workspace / 'customer-notes.txt'; ordinary.write_text('keep')
            self.assertEqual(purge_workspace_archives(root, now=100), 1)
            self.assertFalse(path.exists()); self.assertEqual(ordinary.read_text(), 'keep')
