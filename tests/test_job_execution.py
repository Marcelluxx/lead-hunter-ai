import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select

from src.application.authentication import AuthContext
from src.application.budgets import BudgetService
from src.application.feature_access import FeatureAccessService
from src.application.feature_licenses import LicenseService
from src.application.job_execution import JobExecutionService, JobExecutionError
from src.application.workspaces import bootstrap_platform
from src.domain.feature_licenses import LicenseScope, SubjectKind, LicenseError
from src.domain.job_parameters import parse_job_parameters
from src.domain.job_pricing import JobPricePolicy
from src.domain.jobs import JobState
from src.infrastructure.license_repository import SqlLicenseRepository
from src.infrastructure.models import JobModel, SessionModel, UserModel, WorkspaceMembershipModel, UsageBudgetModel, JobAttemptModel
from src.licensing.catalog import FeatureCatalog
from src.licensing.trust import TrustedLicenseKeys
from src.licensing.verification import LicenseVerifier
from tests.license_helpers import FakeClock, test_key_pair, signed_test_license, license_claims
from tests.platform_helpers import platform_fixture


class JobExecutionTests(unittest.TestCase):
    def setUp(self):
        self.database, passwords, *_ = platform_fixture()
        self.addCleanup(self.database.engine.dispose)
        self.now = datetime(2026, 10, 11, tzinfo=timezone.utc)
        self.installation = uuid4()
        self.clock = FakeClock(10)
        self.private, public = test_key_pair()
        self.verifier = LicenseVerifier(TrustedLicenseKeys('test-owner', {'test-key': public}), FeatureCatalog())
        self.prices = JobPricePolicy(version='test', google_request_ceiling='0.1', llm_request_ceiling='0.02')
        with self.database.session() as session:
            self.user, self.workspace = bootstrap_platform(session, email='operator@example.test',
                password='correct horse battery staple', display_name='Owner', workspace_slug='first',
                workspace_name='First', hard_limit='100', passwords=passwords)
            record = SessionModel(user_id=self.user.id, refresh_token_hash='x' * 64,
                csrf_token_hash='y' * 64, mfa_verified=True, expires_at=self.now + timedelta(days=1))
            session.add(record); session.flush(); self.auth = AuthContext(self.user.id, record.id, True)
        self.service = JobExecutionService(database=self.database, installation_id=self.installation,
            access_factory=self.access, now=lambda: self.now)

    def access(self, session):
        licenses = LicenseService(SqlLicenseRepository(session, self.installation), self.verifier, self.clock)
        return FeatureAccessService(licenses, FeatureCatalog())

    def job(self, *, kind='discover.no_website', payload=None):
        parameters = parse_job_parameters(kind, payload or {'lat': 0, 'lng': 0, 'keywords': ['dentista']})
        quote = self.prices.quote(parameters)
        with self.database.session(self.workspace.id) as session:
            job = JobModel(workspace_id=self.workspace.id, created_by=self.user.id, kind=kind,
                parameters=parameters.payload, idempotency_key=str(uuid4()), estimated_cost=quote.total,
                auth_session_id=self.auth.session_id, auth_session_version=self.user.session_version,
                cost_policy=quote.to_record())
            session.add(job); session.flush()
            BudgetService().reserve(session, workspace_id=self.workspace.id, job_id=job.id, amount=quote.total)
        return job.id

    def activate(self, features=('diagnostics.full',)):
        scope = LicenseScope(self.installation, SubjectKind.WORKSPACE_USER, self.user.id, self.workspace.id)
        claims = license_claims(scope=scope, features=features)
        with self.database.session(self.workspace.id) as session:
            self.access(session).licenses.import_license(scope, signed_test_license(claims, self.private))
        return scope, claims

    def test_claim_is_exclusive_and_guard_checks_current_ownership(self):
        job_id = self.job()
        handle = self.service.claim(job_id, worker_id='test-worker')
        self.assertIsNotNone(handle)
        self.assertIsNone(self.service.claim(job_id, worker_id='duplicate'))
        self.service.guard(handle).require_execute()
        with self.assertRaisesRegex(JobExecutionError, '^job_lease_lost$'):
            self.service.guard(replace(handle, attempt_id=uuid4())).require_execute()
        with self.database.session(self.workspace.id) as session:
            self.assertEqual(session.get(JobModel, job_id).state, 'running')
            self.assertEqual(len(session.scalars(select(JobAttemptModel)).all()), 1)

    def test_provider_call_is_durably_charged_before_return_and_capped(self):
        job_id = self.job(); handle = self.service.claim(job_id, worker_id='worker'); guard = self.service.guard(handle)
        for _ in range(18): guard.before_provider_call('google_places')
        with self.assertRaisesRegex(JobExecutionError, '^job_budget_exhausted$'): guard.before_provider_call('google_places')
        with self.database.session(self.workspace.id) as session:
            budget = session.scalar(select(UsageBudgetModel))
            self.assertEqual(budget.spent, Decimal('1.8')); self.assertEqual(budget.reserved, 0)
            self.assertEqual(session.get(JobModel, job_id).call_counts, {'google_places': 18})

    def test_single_provider_quote_does_not_require_unused_provider_price(self):
        self.prices = JobPricePolicy(version='llm-only', llm_request_ceiling='0.02')
        handle = self.service.claim(self.job(kind='audit.website', payload={'urls': ['https://site.test/']}), worker_id='worker')
        self.service.guard(handle).before_provider_call('openrouter')

    def test_quote_currency_cannot_charge_a_different_budget_currency(self):
        self.prices = JobPricePolicy(version='wrong-currency', google_request_ceiling='0.1', currency='USD')
        handle = self.service.claim(self.job(), worker_id='worker')
        with self.assertRaisesRegex(JobExecutionError, '^job_price_invalid$'):
            self.service.guard(handle).before_provider_call('google_places')
        with self.database.session(self.workspace.id) as session:
            self.assertEqual(session.scalar(select(UsageBudgetModel)).spent, 0)

    def test_cancel_stops_next_operation_and_resume_preserves_consumed_budget(self):
        job_id = self.job(); handle = self.service.claim(job_id, worker_id='worker')
        self.service.guard(handle).before_provider_call('google_places')
        self.service.checkpoint(handle, {'phase': 'discovery', 'cursor': 1, 'completed_ids': ['place-1']})
        self.service.cancel(job_id, workspace_id=self.workspace.id, auth=self.auth)
        with self.assertRaisesRegex(JobExecutionError, '^job_cancelled$'): self.service.guard(handle).require_execute()
        self.service.finish(handle, state=JobState.CANCELLED, error_code='job_cancelled')
        self.service.resume(job_id, workspace_id=self.workspace.id, auth=self.auth)
        next_handle = self.service.claim(job_id, worker_id='resumed')
        self.assertNotEqual(handle.attempt_id, next_handle.attempt_id)
        self.assertEqual(next_handle.checkpoint['completed_ids'], ['place-1'])
        with self.database.session(self.workspace.id) as session:
            budget = session.scalar(select(UsageBudgetModel))
            self.assertEqual(budget.spent, Decimal('0.1')); self.assertEqual(budget.reserved, Decimal('1.7'))

    def test_current_logout_role_account_and_session_version_stop_work(self):
        for change in ['logout', 'role', 'inactive', 'version']:
            with self.subTest(change=change):
                job_id = self.job(); handle = self.service.claim(job_id, worker_id='worker')
                with self.database.session(self.workspace.id) as session:
                    if change == 'logout': session.get(SessionModel, self.auth.session_id).revoked_at = self.now
                    if change == 'role': session.scalar(select(WorkspaceMembershipModel)).role = 'viewer'
                    if change == 'inactive': session.get(UserModel, self.user.id).is_active = False
                    if change == 'version': session.get(UserModel, self.user.id).session_version += 1
                with self.assertRaisesRegex(JobExecutionError, '^job_authorization_denied$'): self.service.guard(handle).require_execute()
                self.service.finish(handle, state=JobState.FAILED, error_code='job_authorization_denied')
                with self.database.session(self.workspace.id) as session:
                    session.get(SessionModel, self.auth.session_id).revoked_at = None
                    session.scalar(select(WorkspaceMembershipModel)).role = 'admin'
                    session.get(UserModel, self.user.id).is_active = True
                    session.get(UserModel, self.user.id).session_version = 1

    def test_diagnostic_requires_real_grant_mfa_and_revocation_at_each_step(self):
        denied = self.job(kind='diagnostic.website', payload={'url': 'https://site.test/'})
        self.assertIsNone(self.service.claim(denied, worker_id='worker'))
        scope, claims = self.activate()
        job_id = self.job(kind='diagnostic.website', payload={'url': 'https://site.test/'})
        handle = self.service.claim(job_id, worker_id='worker')
        with self.database.session(self.workspace.id) as session:
            session.get(SessionModel, self.auth.session_id).mfa_verified = False
        with self.assertRaises(LicenseError): self.service.guard(handle).require_execute()
        with self.database.session(self.workspace.id) as session:
            session.get(SessionModel, self.auth.session_id).mfa_verified = True
            self.access(session).licenses.revoke_license(scope, claims.license_id)
        with self.assertRaisesRegex(LicenseError, '^license_revoked$'): self.service.guard(handle).before_provider_call('openrouter')

    def test_expired_leases_reclaim_three_times_then_dead_letter(self):
        job_id = self.job(); handles = []
        for _ in range(3):
            handles.append(self.service.claim(job_id, worker_id='worker'))
            self.now += timedelta(seconds=61)
        self.assertTrue(all(handle is not None for handle in handles))
        self.assertIsNone(self.service.claim(job_id, worker_id='exhausted'))
        with self.database.session(self.workspace.id) as session:
            job = session.get(JobModel, job_id)
            self.assertEqual(job.state, 'failed'); self.assertEqual(job.error_code, 'job_retry_exhausted')
        with self.assertRaisesRegex(JobExecutionError, '^job_not_resumable$'):
            self.service.resume(job_id, workspace_id=self.workspace.id, auth=self.auth)

    def test_checkpoint_payload_never_accepts_raw_artifacts_or_authority(self):
        handle = self.service.claim(self.job(), worker_id='worker')
        for checkpoint in [{'html': 'secret'}, {'phase': 'audit', 'token': 'secret'},
                           {'phase': 'audit', 'cursor': True}, {'phase': 'audit', 'completed_ids': ['x' * 501]}]:
            with self.subTest(checkpoint=checkpoint), self.assertRaisesRegex(JobExecutionError, '^job_checkpoint_invalid$'):
                self.service.checkpoint(handle, checkpoint)

    def test_cross_workspace_control_and_missing_trusted_session_denied(self):
        job_id = self.job()
        with self.assertRaises(JobExecutionError): self.service.cancel(job_id, workspace_id=uuid4(), auth=self.auth)
        with self.database.session(self.workspace.id) as session:
            session.get(JobModel, job_id).auth_session_id = None
        self.assertIsNone(self.service.claim(job_id, worker_id='worker'))
        with self.database.session(self.workspace.id) as session:
            job = session.get(JobModel, job_id)
            self.assertEqual(job.error_code, 'job_authorization_denied')
            self.assertEqual(session.scalar(select(UsageBudgetModel)).reserved, 0)
