from __future__ import annotations

import uuid
import os

import dramatiq
from dramatiq.brokers.redis import RedisBroker
from sqlalchemy import select

from ..application.audit_log import append_audit_event
from ..application.budgets import BudgetService
from ..domain.jobs import JobState, ensure_job_transition
from ..domain.discovery import ProviderPayloadError
from ..infrastructure.database import Database, resolve_job_workspace, set_workspace_context
from ..infrastructure.models import JobModel
from .jobs import validate_persistent_job_parameters


def configure_broker(redis_url: str) -> RedisBroker:
    broker = RedisBroker(url=redis_url)
    dramatiq.set_broker(broker)
    # Actors are created while this module is imported. Rebind and register
    # them explicitly because the default broker may point to localhost.
    process_job.broker = broker
    broker.declare_actor(process_job)
    from .retention import enforce_workspace_retention

    enforce_workspace_retention.broker = broker
    broker.declare_actor(enforce_workspace_retention)
    return broker


class DramatiqJobPublisher:
    def publish(self, job_id: uuid.UUID) -> None:
        process_job.send(str(job_id))


@dramatiq.actor(max_retries=3, min_backoff=1000, max_backoff=30000)
def process_job(job_id: str) -> None:
    # The queue contains only a UUID. Unsupported commercial pipeline kinds
    # remain fail-closed; provider payloads are rejected even if manually added.
    parsed_id = uuid.UUID(job_id)
    database_url = os.environ.get("LEADHUNTER_DATABASE_URL")
    if not database_url:
        raise RuntimeError("LEADHUNTER_DATABASE_URL non configurato nel worker.")
    database = Database(database_url)
    try:
        with database.session() as session:
            workspace_id = resolve_job_workspace(session, parsed_id)
            if workspace_id is None:
                return
            set_workspace_context(session, workspace_id)
            job = session.scalar(
                select(JobModel).where(JobModel.id == parsed_id).with_for_update()
            )
            if job is None or job.state != JobState.QUEUED.value:
                return
            try:
                validate_persistent_job_parameters(job.parameters)
            except ProviderPayloadError:
                ensure_job_transition(job.state, JobState.VALIDATING)
                job.state = JobState.VALIDATING.value
                ensure_job_transition(job.state, JobState.FAILED)
                job.state = JobState.FAILED.value
                job.error_code = "provider_payload_not_allowed"
                BudgetService().release(
                    session,
                    job_id=job.id,
                    reason="provider_payload_not_allowed",
                )
                append_audit_event(
                    session,
                    action="job.failed",
                    workspace_id=workspace_id,
                    target_type="job",
                    target_id=str(job.id),
                    details={"reason": "provider_payload_not_allowed"},
                )
                return
            ensure_job_transition(job.state, JobState.VALIDATING)
            job.state = JobState.VALIDATING.value
            ensure_job_transition(job.state, JobState.FAILED)
            job.state = JobState.FAILED.value
            job.error_code = "pipeline_not_configured"
            BudgetService().release(
                session,
                job_id=job.id,
                reason="pipeline_not_configured",
            )
            append_audit_event(
                session,
                action="job.failed",
                workspace_id=workspace_id,
                target_type="job",
                target_id=str(job.id),
                details={"reason": "pipeline_not_configured"},
            )
    finally:
        database.engine.dispose()
