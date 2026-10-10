"""Database engine, transaction and workspace-context helpers."""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from typing import Iterator, Optional
from threading import Lock

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
        self._license_clock_lock = Lock()
        self._license_clock_engine = None
        self._license_clock_factory = None

    @contextmanager
    def license_clock_session(self) -> Iterator[Session]:
        # In-memory SQLite fixtures have only one database connection. Production
        # PostgreSQL uses a separate bounded pool: callers may hold every request
        # connection while the monotonic clock commits independently.
        if self.engine.dialect.name == "sqlite" and isinstance(self.engine.pool, StaticPool):
            with self.session() as session:
                yield session
            return
        with self._license_clock_lock:
            if self._license_clock_engine is None:
                self._license_clock_engine = create_engine(
                    self.engine.url, pool_pre_ping=True, pool_size=2,
                    max_overflow=0, pool_timeout=5)
                self._license_clock_factory = sessionmaker(
                    bind=self._license_clock_engine, expire_on_commit=False, autoflush=False)
            factory = self._license_clock_factory
        with factory() as session, session.begin():
            yield session

    def close_license_clock_pool(self) -> None:
        """Close the dedicated pool when the owning API/worker runtime stops."""
        with self._license_clock_lock:
            if self._license_clock_engine is not None:
                self._license_clock_engine.dispose()
                self._license_clock_engine = None
                self._license_clock_factory = None

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
