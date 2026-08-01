"""Database engine, transaction and workspace-context helpers."""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from typing import Iterator, Optional

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


class Database:
    def __init__(self, url: str, *, echo: bool = False):
        engine_kwargs = {"pool_pre_ping": True, "echo": echo}
        if url == "sqlite+pysqlite:///:memory:":
            engine_kwargs.update(
                {
                    "connect_args": {"check_same_thread": False},
                    "poolclass": StaticPool,
                }
            )
        self.engine: Engine = create_engine(url, **engine_kwargs)
        self.session_factory = sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
            autoflush=False,
        )

    @contextmanager
    def session(
        self, workspace_id: Optional[uuid.UUID] = None
    ) -> Iterator[Session]:
        with self.session_factory() as session:
            try:
                with session.begin():
                    if workspace_id is not None:
                        set_workspace_context(session, workspace_id)
                    yield session
            except Exception:
                transaction = session.get_transaction()
                if transaction is not None and transaction.is_active:
                    session.rollback()
                raise


def set_workspace_context(session: Session, workspace_id: uuid.UUID) -> None:
    if session.bind is not None and session.bind.dialect.name == "postgresql":
        session.execute(
            text("SELECT set_config('app.workspace_id', :workspace_id, true)"),
            {"workspace_id": str(workspace_id)},
        )


def resolve_job_workspace(session: Session, job_id: uuid.UUID) -> uuid.UUID | None:
    if session.bind is not None and session.bind.dialect.name == "postgresql":
        value = session.scalar(
            text("SELECT public.app_job_workspace(:job_id)"),
            {"job_id": str(job_id)},
        )
        return uuid.UUID(str(value)) if value is not None else None
    from .models import JobModel

    value = session.scalar(
        text("SELECT workspace_id FROM jobs WHERE id = :job_id"),
        {"job_id": job_id.hex},
    )
    return uuid.UUID(str(value)) if value is not None else None
