"""Bounded and restartable contact retention worker."""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session
import dramatiq

from ..infrastructure.database import Database
from ..infrastructure.models import ContactModel, RetentionEventModel


@dataclass(frozen=True)
class RetentionBatchResult:
    deleted_by_category: dict[str, int]
    has_more: bool


def run_retention_batch(
    session: Session,
    *,
    workspace_id: uuid.UUID,
    now: datetime | None = None,
    batch_size: int = 500,
) -> RetentionBatchResult:
    if not 1 <= batch_size <= 5000:
        raise ValueError("batch_size deve essere compreso tra 1 e 5000.")
    cutoff = now or datetime.now(timezone.utc)
    expired_ids = session.scalars(
        select(ContactModel.id)
        .where(
            ContactModel.workspace_id == workspace_id,
            ContactModel.expires_at <= cutoff,
        )
        .order_by(ContactModel.expires_at, ContactModel.id)
        .limit(batch_size)
    ).all()
    deleted_count = 0
    if expired_ids:
        result = session.execute(delete(ContactModel).where(ContactModel.id.in_(expired_ids)))
        deleted_count = int(result.rowcount or 0)
    session.add(
        RetentionEventModel(
            workspace_id=workspace_id,
            entity_type="contact",
            deleted_count=deleted_count,
            ran_at=cutoff,
        )
    )
    return RetentionBatchResult(
        deleted_by_category={"contact": deleted_count},
        has_more=len(expired_ids) == batch_size,
    )


@dramatiq.actor(max_retries=3, min_backoff=1000, max_backoff=30000)
def enforce_workspace_retention(workspace_id: str) -> None:
    """Queue-safe entry point: only a workspace UUID crosses Redis."""

    parsed_workspace_id = uuid.UUID(workspace_id)
    database_url = os.environ.get("LEADHUNTER_DATABASE_URL")
    if not database_url:
        raise RuntimeError("LEADHUNTER_DATABASE_URL non configurato nel worker.")
    database = Database(database_url)
    try:
        with database.session(workspace_id=parsed_workspace_id) as session:
            result = run_retention_batch(
                session,
                workspace_id=parsed_workspace_id,
            )
        if result.has_more:
            enforce_workspace_retention.send(str(parsed_workspace_id))
    finally:
        database.engine.dispose()
