"""Persistent, idempotent job orchestration with UUID-only queue messages."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol

from sqlalchemy import event, select
from sqlalchemy.orm import Session

from ..domain.jobs import JobState, ensure_job_transition
from ..domain.discovery import ensure_provider_payload_absent
from ..domain.usage import normalized_cost
from ..infrastructure.models import JobModel
from .audit_log import append_audit_event
from .budgets import BudgetService


class JobPublisher(Protocol):
    def publish(self, job_id: uuid.UUID) -> None: ...


@dataclass(frozen=True)
class JobCreation:
    job: JobModel
    created: bool


class JobService:
    def __init__(self, *, budgets: BudgetService, publisher: JobPublisher):
        self._budgets = budgets
        self._publisher = publisher

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
        publisher = self._publisher
        event.listen(
            session,
            "after_commit",
            lambda _: publisher.publish(job_id),
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
