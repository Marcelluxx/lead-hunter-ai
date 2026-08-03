"""Periodic scheduler for workspace-scoped retention actors."""

from __future__ import annotations

import logging
import os
import secrets
import threading
import uuid
from typing import Protocol

from redis import Redis
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ..infrastructure.database import Database
from ..infrastructure.models import WorkspaceModel
from .broker import configure_broker
from .retention import enforce_workspace_retention


logger = logging.getLogger(__name__)
DEFAULT_SCHEDULE_SECONDS = 3600
MINIMUM_SCHEDULE_SECONDS = 300
_LOCK_KEY = "leadhunter:maintenance:retention-scheduler"


class RetentionPublisher(Protocol):
    def publish(self, workspace_id: uuid.UUID) -> None: ...


class DramatiqRetentionPublisher:
    def publish(self, workspace_id: uuid.UUID) -> None:
        enforce_workspace_retention.send(str(workspace_id))


def enqueue_active_workspaces(
    session: Session, *, publisher: RetentionPublisher
) -> int:
    if session.bind is not None and session.bind.dialect.name == "postgresql":
        workspace_ids = session.scalars(
            text("SELECT workspace_id FROM public.app_active_workspace_ids()")
        ).all()
    else:
        workspace_ids = session.scalars(
            select(WorkspaceModel.id)
            .where(WorkspaceModel.is_active.is_(True))
            .order_by(WorkspaceModel.id)
        ).all()
    for workspace_id in workspace_ids:
        publisher.publish(workspace_id)
    return len(workspace_ids)


def run_scheduler() -> None:
    database_url = os.environ.get("LEADHUNTER_DATABASE_URL", "")
    redis_url = os.environ.get("LEADHUNTER_REDIS_URL", "")
    if not database_url or not redis_url:
        raise RuntimeError("Database e Redis sono obbligatori per il retention scheduler.")
    interval = _schedule_interval(
        os.environ.get("LEADHUNTER_RETENTION_SCHEDULE_SECONDS", "")
    )
    database = Database(database_url)
    redis_client = Redis.from_url(redis_url, decode_responses=True)
    configure_broker(redis_url)
    publisher = DramatiqRetentionPublisher()
    try:
        while True:
            token = secrets.token_urlsafe(24)
            acquired = redis_client.set(
                _LOCK_KEY,
                token,
                nx=True,
                ex=interval,
            )
            if acquired:
                with database.session() as session:
                    count = enqueue_active_workspaces(
                        session, publisher=publisher
                    )
                logger.info(
                    "Retention pianificata per %d workspace attivi.", count
                )
            threading.Event().wait(interval)
    finally:
        database.engine.dispose()
        redis_client.close()


def _schedule_interval(raw_value: str) -> int:
    if not raw_value.strip():
        return DEFAULT_SCHEDULE_SECONDS
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError("Intervallo retention non valido.") from exc
    if value < MINIMUM_SCHEDULE_SECONDS:
        raise ValueError(
            f"L'intervallo retention minimo e {MINIMUM_SCHEDULE_SECONDS} secondi."
        )
    return value


if __name__ == "__main__":
    run_scheduler()
