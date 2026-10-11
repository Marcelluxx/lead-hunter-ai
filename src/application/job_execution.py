"""Short, workspace-scoped transactions around cooperative job execution."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import select, text

from src.domain.feature_licenses import FeatureAction, LicenseError, ERROR_CODES
from src.domain.identity import Permission
from src.domain.job_parameters import parse_job_parameters, JobParameterError
from src.domain.job_pricing import JobPricePolicy, JobPriceError
from src.domain.jobs import JobState, ensure_job_transition
from src.infrastructure.database import resolve_job_workspace
from src.infrastructure.models import JobModel, JobAttemptModel, SessionModel, UserModel, WorkspaceModel, UsageReservationModel
from .audit_log import append_audit_event
from .budgets import BudgetService, BudgetExceeded
from .feature_access import principal_feature_context

_CODES = frozenset({'job_cancelled', 'job_authorization_denied', 'job_lease_lost',
    'job_retry_exhausted', 'job_not_resumable', 'job_parameters_invalid',
    'job_checkpoint_invalid', 'job_budget_exhausted', 'job_execution_failed',
    'job_price_invalid', 'job_price_missing', 'job_kind_unsupported',
    'provider_payload_not_allowed', 'provider_timeout', 'provider_unavailable', 'provider_http_error',
    'job_crawl_not_auditable', 'job_credentials_missing', 'job_prompts_missing', 'job_price_changed', 'job_idempotency_conflict'}) | ERROR_CODES
_RECOVERABLE = frozenset({'job_cancelled', 'job_authorization_denied', 'job_lease_lost',
    'provider_timeout', 'provider_unavailable', 'provider_http_error',
    'license_expired', 'license_revoked', 'license_missing', 'feature_role_denied'})


class JobExecutionError(RuntimeError):
    def __init__(self, code='job_execution_failed'):
        self.code = code if code in _CODES else 'job_execution_failed'
        super().__init__(self.code)


def _utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


@dataclass(frozen=True)
class ExecutionHandle:
    job_id: UUID
    workspace_id: UUID
    attempt_id: UUID
    checkpoint: dict


class ExecutionGuard:
    def __init__(self, service, handle):
        self.service, self.handle = service, handle

    def require_execute(self):
        with self.service.transaction(self.handle) as (session, job):
            return self.service._origin_context(session, job)

    def before_provider_call(self, provider):
        with self.service.transaction(self.handle) as (session, job):
            if provider not in ('google_places', 'openrouter'):
                raise JobExecutionError('job_budget_exhausted')
            parsed = parse_job_parameters(job.kind, job.parameters)
            policy = job.cost_policy
            try:
                google_price = policy.get('google_request_ceiling')
                llm_price = policy.get('llm_request_ceiling')
                quote = JobPricePolicy(version=policy['version'], currency=policy['currency'],
                    google_request_ceiling=None if google_price in ('0', '0.000000', None) else google_price,
                    llm_request_ceiling=None if llm_price in ('0', '0.000000', None) else llm_price).quote(parsed)
                if quote.to_record() != policy:
                    raise JobPriceError()
            except (KeyError, TypeError, JobPriceError):
                raise JobExecutionError('job_price_invalid') from None
            cap = quote.google_calls if provider == 'google_places' else quote.llm_calls
            amount = quote.google_request_ceiling if provider == 'google_places' else quote.llm_request_ceiling
            counts = dict(job.call_counts)
            count = counts.get(provider, 0)
            if type(count) is not int or not 0 <= count < cap:
                raise JobExecutionError('job_budget_exhausted')
            try:
                self.service.budgets.consume(session, job_id=job.id, amount=amount, provider=provider,
                    operation_id=f'{job.id}:{provider}:{count + 1}', currency=quote.currency)
            except BudgetExceeded:
                raise JobExecutionError('job_budget_exhausted') from None
            except ValueError:
                raise JobExecutionError('job_price_invalid') from None
            counts[provider] = count + 1
            job.call_counts = counts


class JobExecutionService:
    def __init__(self, *, database, installation_id, access_factory=None, budgets=None,
                 now=None, lease_seconds=60, publisher=None):
        if type(lease_seconds) is not int or not 5 <= lease_seconds <= 300:
            raise ValueError('job_lease_invalid')
        self.database, self.installation_id = database, installation_id
        self.access_factory = access_factory
        self.budgets, self.publisher = budgets or BudgetService(), publisher
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.lease_seconds = lease_seconds

    def guard(self, handle):
        return ExecutionGuard(self, handle)

    def _context(self, session, *, workspace_id, user_id, session_id, session_version=None):
        record = session.scalar(select(SessionModel).where(SessionModel.id == session_id)
                                .execution_options(populate_existing=True))
        user = session.scalar(select(UserModel).where(UserModel.id == user_id)
                              .execution_options(populate_existing=True))
        if (record is None or user is None or record.user_id != user_id or record.revoked_at is not None
                or _utc(record.expires_at) <= self.now() or not user.is_active
                or (session_version is not None and user.session_version != session_version)):
            raise JobExecutionError('job_authorization_denied')
        can_list_active = session.bind.dialect.name == 'postgresql' and session.scalar(text(
            "SELECT has_function_privilege(current_user, 'public.app_active_workspace_ids()', 'EXECUTE')"))
        if can_list_active:
            active = session.scalar(text('SELECT EXISTS (SELECT 1 FROM public.app_active_workspace_ids() WHERE workspace_id = :id)'),
                                    {'id': str(workspace_id)})
        else:
            workspace = session.get(WorkspaceModel, workspace_id, populate_existing=True)
            active = bool(workspace and workspace.is_active)
        context = principal_feature_context(session, user_id=user_id, workspace_id=workspace_id,
            installation_id=self.installation_id, mfa_verified=record.mfa_verified, workspace_active=active)
        if not context.principal_active:
            raise JobExecutionError('job_authorization_denied')
        return context

    def _origin_context(self, session, job):
        if job.auth_session_id is None or job.auth_session_version is None:
            raise JobExecutionError('job_authorization_denied')
        context = self._context(session, workspace_id=job.workspace_id, user_id=job.created_by,
            session_id=job.auth_session_id, session_version=job.auth_session_version)
        if Permission.START_JOB not in context.permissions:
            raise JobExecutionError('job_authorization_denied')
        parsed = parse_job_parameters(job.kind, job.parameters)
        for feature in parsed.required_features:
            if self.access_factory is None:
                raise LicenseError('license_storage_unavailable')
            access = self.access_factory(session)
            access.require(context, feature)
            if feature == 'diagnostics.full':
                access.require(context, feature, action=FeatureAction.VIEW)
        return context

    def _load(self, session, *, job_id, workspace_id):
        job = session.scalar(select(JobModel).where(JobModel.id == job_id, JobModel.workspace_id == workspace_id)
                             .with_for_update().execution_options(populate_existing=True))
        if job is None:
            raise JobExecutionError('job_authorization_denied')
        return job

    def claim(self, job_id, *, worker_id):
        with self.database.session() as session:
            workspace_id = resolve_job_workspace(session, job_id)
        if workspace_id is None:
            return None
        with self.database.session(workspace_id) as session:
            job = self._load(session, job_id=job_id, workspace_id=workspace_id)
            now = self.now()
            if job.state == 'running' and job.lease_expires_at is not None and _utc(job.lease_expires_at) > now:
                return None
            if job.state not in ('queued', 'running'):
                return None
            if job.state == 'running':
                prior = session.get(JobAttemptModel, job.active_attempt_id)
                if prior is not None:
                    prior.finished_at, prior.error_code = now, 'job_lease_lost'
            if job.cancel_requested:
                self._end(session, job, JobState.CANCELLED, 'job_cancelled'); return None
            if job.attempt_count >= 3:
                self._end(session, job, JobState.FAILED, 'job_retry_exhausted'); return None
            try:
                self._origin_context(session, job)
            except (JobExecutionError, LicenseError, JobParameterError) as exc:
                self._end(session, job, JobState.FAILED, exc.code); return None
            if job.state == 'queued':
                ensure_job_transition(job.state, JobState.VALIDATING)
                job.state = 'validating'
                ensure_job_transition(job.state, JobState.RUNNING)
                job.state = 'running'
            attempt_id = uuid4()
            job.active_attempt_id, job.lease_expires_at = attempt_id, now + timedelta(seconds=self.lease_seconds)
            job.attempt_count += 1
            job.started_at = job.started_at or now
            job.error_code = None
            session.add(JobAttemptModel(id=attempt_id, job_id=job.id, attempt_number=job.attempt_count,
                                       worker_id=str(worker_id)[:200], started_at=now, heartbeat_at=now))
            append_audit_event(session, action='job.running', workspace_id=workspace_id,
                               target_type='job', target_id=str(job.id), details={'attempt': job.attempt_count})
            return ExecutionHandle(job.id, workspace_id, attempt_id, dict(job.checkpoint))

    @contextmanager
    def transaction(self, handle):
        with self.database.session(handle.workspace_id) as session:
            job = self._load(session, job_id=handle.job_id, workspace_id=handle.workspace_id)
            if job.state != 'running' or job.active_attempt_id != handle.attempt_id:
                raise JobExecutionError('job_lease_lost')
            if job.cancel_requested:
                raise JobExecutionError('job_cancelled')
            if job.lease_expires_at is None or _utc(job.lease_expires_at) <= self.now():
                raise JobExecutionError('job_lease_lost')
            self._origin_context(session, job)
            now = self.now()
            job.lease_expires_at = now + timedelta(seconds=self.lease_seconds)
            attempt = session.get(JobAttemptModel, handle.attempt_id)
            if attempt is None or attempt.job_id != job.id:
                raise JobExecutionError('job_lease_lost')
            attempt.heartbeat_at = now
            yield session, job

    def checkpoint(self, handle, value):
        if (type(value) is not dict or set(value) - {'phase', 'cursor', 'completed_ids', 'lead_ids'}
                or value.get('phase') not in ('discovery', 'crawl', 'audit', 'finalize')
                or type(value.get('cursor', 0)) is not int or not 0 <= value.get('cursor', 0) <= 1000):
            raise JobExecutionError('job_checkpoint_invalid')
        for key in ('completed_ids', 'lead_ids'):
            values = value.get(key, [])
            if type(values) is not list or len(values) > 100 or not all(type(item) is str and 1 <= len(item) <= 500 for item in values):
                raise JobExecutionError('job_checkpoint_invalid')
        with self.transaction(handle) as (_, job):
            job.checkpoint = dict(value)

    def _end(self, session, job, state, code=None):
        if job.state == 'queued' and state is JobState.FAILED:
            job.state = 'validating'
        ensure_job_transition(job.state, state)
        reservation = session.scalar(select(UsageReservationModel).where(UsageReservationModel.job_id == job.id))
        if reservation is not None and reservation.state == 'active':
            if state is JobState.COMPLETED:
                self.budgets.settle(session, job_id=job.id, actual_amount=reservation.settled_amount or 0)
            else:
                self.budgets.release(session, job_id=job.id, reason=code or state.value)
        now = self.now()
        attempt = session.get(JobAttemptModel, job.active_attempt_id) if job.active_attempt_id else None
        if attempt is not None:
            attempt.finished_at, attempt.error_code = now, code
        job.state, job.error_code, job.finished_at, job.lease_expires_at = state.value, code, now, None
        append_audit_event(session, action=f'job.{state.value}', workspace_id=job.workspace_id,
                           target_type='job', target_id=str(job.id), details={'code': code} if code else None)

    def finish(self, handle, *, state, error_code=None):
        state = JobState(state)
        if state not in (JobState.COMPLETED, JobState.PARTIAL, JobState.FAILED, JobState.CANCELLED):
            raise JobExecutionError()
        code = JobExecutionError(error_code).code if error_code is not None else None
        with self.database.session(handle.workspace_id) as session:
            job = self._load(session, job_id=handle.job_id, workspace_id=handle.workspace_id)
            if job.state != 'running' or job.active_attempt_id != handle.attempt_id:
                return False
            if state in (JobState.COMPLETED, JobState.PARTIAL):
                if job.cancel_requested:
                    raise JobExecutionError('job_cancelled')
                if job.lease_expires_at is None or _utc(job.lease_expires_at) <= self.now():
                    raise JobExecutionError('job_lease_lost')
                self._origin_context(session, job)
            self._end(session, job, state, code)
            return True

    def cancel(self, job_id, *, workspace_id, auth):
        with self.database.session(workspace_id) as session:
            job = self._load(session, job_id=job_id, workspace_id=workspace_id)
            context = self._context(session, workspace_id=workspace_id, user_id=auth.user_id, session_id=auth.session_id)
            if Permission.CANCEL_JOB not in context.permissions:
                raise JobExecutionError('job_authorization_denied')
            if job.state == 'queued':
                job.cancel_requested = True
                self._end(session, job, JobState.CANCELLED, 'job_cancelled')
            elif job.state == 'running':
                job.cancel_requested = True

    def resume(self, job_id, *, workspace_id, auth):
        with self.database.session(workspace_id) as session:
            job = self._load(session, job_id=job_id, workspace_id=workspace_id)
            if (job.created_by != auth.user_id or job.state not in ('failed', 'partial', 'cancelled')
                    or job.error_code not in _RECOVERABLE or job.attempt_count >= 3):
                raise JobExecutionError('job_not_resumable')
            user = session.get(UserModel, auth.user_id, populate_existing=True)
            job.auth_session_id, job.auth_session_version = auth.session_id, user.session_version if user else None
            self._origin_context(session, job)
            self.budgets.reactivate(session, job_id=job.id)
            job.state, job.cancel_requested, job.active_attempt_id = 'queued', False, None
            job.finished_at, job.lease_expires_at, job.error_code = None, None, None
            append_audit_event(session, action='job.resumed', workspace_id=workspace_id,
                               actor_user_id=auth.user_id, target_type='job', target_id=str(job.id))
            if self.publisher is not None:
                from sqlalchemy import event
                event.listen(session, 'after_commit', lambda _: self.publisher.publish(job_id), once=True)
