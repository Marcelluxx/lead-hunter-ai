"""Persistent, idempotent job orchestration with UUID-only queue messages."""

from __future__ import annotations

import uuid
import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol

from sqlalchemy import event, select
from sqlalchemy.orm import Session

from ..domain.jobs import JobState, ensure_job_transition
from ..domain.discovery import ensure_provider_payload_absent
from ..domain.usage import normalized_cost
from ..infrastructure.models import JobModel, UsageBudgetModel, UserModel
from .audit_log import append_audit_event
from .budgets import BudgetService


class JobPublisher(Protocol):
    def publish(self, job_id: uuid.UUID) -> None: ...


@dataclass(frozen=True)
class JobCreation:
    job: JobModel
    created: bool


class JobService:
    def __init__(self, *, budgets: BudgetService, publisher: JobPublisher, durable_dispatch=False):
        self._budgets = budgets
        self._publisher = publisher
        self._durable_dispatch = durable_dispatch

    def publish(self, job_id):
        try:
            self._publisher.publish(job_id)
        except Exception:
            if not self._durable_dispatch:
                raise
            logging.getLogger(__name__).warning('job_dispatch_deferred')

    def create(
        self,
        session: Session,
        *,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        kind: str,
        parameters: dict[str, Any],
        estimated_cost: Decimal | str,
        idempotency_key: str,
        auth_session_id: uuid.UUID | None = None,
        auth_session_version: int | None = None,
        cost_policy: dict | None = None,
    ) -> JobCreation:
        key = idempotency_key.strip()
        if not key or len(key) > 128:
            raise ValueError("Chiave di idempotenza non valida.")
        ensure_provider_payload_absent(parameters)
        existing = session.scalar(
            select(JobModel).where(
                JobModel.workspace_id == workspace_id,
                JobModel.idempotency_key == key,
            )
        )
        if existing is not None:
            return JobCreation(existing, False)
        job = JobModel(
            workspace_id=workspace_id,
            created_by=user_id,
            kind=kind[:80],
            parameters=parameters,
            estimated_cost=normalized_cost(estimated_cost),
            idempotency_key=key,
            auth_session_id=auth_session_id,
            auth_session_version=auth_session_version,
            cost_policy=cost_policy or {},
        )
        session.add(job)
        session.flush()
        self._budgets.reserve(
            session,
            workspace_id=workspace_id,
            job_id=job.id,
            amount=job.estimated_cost,
        )
        session.flush()
        job_id = job.id
        event.listen(
            session,
            "after_commit",
            lambda _: self.publish(job_id),
            once=True,
        )
        append_audit_event(
            session,
            action="job.created",
            workspace_id=workspace_id,
            actor_user_id=user_id,
            target_type="job",
            target_id=str(job.id),
        )
        return JobCreation(job, True)

    def create_commercial(self, session, *, workspace_id, auth, kind, parameters,
                          idempotency_key, prices, execution):
        from ..domain.job_parameters import parse_job_parameters, JobParameterError
        from ..domain.job_pricing import JobPriceError
        from .job_execution import JobExecutionError
        parsed = parse_job_parameters(kind, parameters)
        if prices is None:
            raise JobPriceError('job_price_missing')
        quote = prices.quote(parsed)
        user = session.get(UserModel, auth.user_id, populate_existing=True)
        proposed = JobModel(workspace_id=workspace_id, created_by=auth.user_id, kind=parsed.kind,
            parameters=parsed.payload, auth_session_id=auth.session_id,
            auth_session_version=user.session_version if user else None)
        execution._origin_context(session, proposed)
        key = idempotency_key.strip()
        if not key or len(key) > 128:
            raise JobParameterError()
        # Serialize workspace admissions before the unique idempotency insert and reservation.
        budget = session.scalar(select(UsageBudgetModel).where(UsageBudgetModel.workspace_id == workspace_id)
                                .with_for_update().execution_options(populate_existing=True))
        if budget is None or budget.currency != quote.currency:
            raise JobPriceError()
        existing = session.scalar(select(JobModel).where(JobModel.workspace_id == workspace_id,
                                                        JobModel.idempotency_key == key))
        if existing is not None:
            if existing.created_by != auth.user_id or existing.kind != parsed.kind or existing.parameters != parsed.payload:
                raise JobExecutionError('job_idempotency_conflict')
            return JobCreation(existing, False)
        return self.create(session, workspace_id=workspace_id, user_id=auth.user_id,
            kind=parsed.kind, parameters=parsed.payload, estimated_cost=quote.total, idempotency_key=key,
            auth_session_id=auth.session_id, auth_session_version=user.session_version, cost_policy=quote.to_record())

    def transition(
        self,
        session: Session,
        *,
        job_id: uuid.UUID,
        target: JobState,
        error_code: str | None = None,
    ) -> JobModel:
        job = session.scalar(select(JobModel).where(JobModel.id == job_id).with_for_update())
        if job is None:
            raise KeyError(str(job_id))
        ensure_job_transition(job.state, target)
        job.state = target.value
        job.error_code = error_code[:100] if error_code else None
        return job
