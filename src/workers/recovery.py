"""Durable queued jobs are the dispatch source; Redis delivery may be repeated safely."""
from __future__ import annotations

import logging
import os
import signal
import threading
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from redis import Redis
from sqlalchemy import select, text, or_, and_

from src.application.diagnostics import purge_diagnostic_archives
from src.infrastructure.database import Database
from src.infrastructure.models import JobModel, WorkspaceModel
from .broker import configure_broker, DramatiqJobPublisher


def recover_due_jobs(database, *, publisher, now=None, limit=500):
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError('job_recovery_limit_invalid')
    cutoff = now or datetime.now(timezone.utc)
    with database.session() as session:
        if session.bind.dialect.name == 'postgresql':
            workspaces = session.scalars(text('SELECT workspace_id FROM public.app_active_workspace_ids()')).all()
        else:
            workspaces = session.scalars(select(WorkspaceModel.id).where(WorkspaceModel.is_active.is_(True))).all()
    ids = []
    for workspace in workspaces:
        if len(ids) >= limit:
            break
        with database.session(workspace) as session:
            ids.extend(session.scalars(select(JobModel.id).where(JobModel.workspace_id == workspace,
                JobModel.cancel_requested.is_(False), or_(JobModel.state == 'queued', and_(JobModel.state == 'running',
                    JobModel.lease_expires_at <= cutoff))).order_by(JobModel.created_at).limit(limit - len(ids))).all())
    # Network/broker operations occur after all SQL transactions have closed.
    for job_id in ids:
        publisher.publish(job_id)
    return len(ids)


def purge_workspace_archives(root, *, now):
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        return 0
    count = 0
    for path in root.iterdir():
        try:
            if str(UUID(path.name)) != path.name or path.is_symlink() or not path.is_dir():
                continue
        except ValueError:
            continue
        count += purge_diagnostic_archives(path, now=now)
    return count


def run_scheduler():
    from src.application.license_clock import GuardedClock, SystemClock
    from src.infrastructure.license_repository import PostgresClockStore
    from src.licensing.settings import LicenseSettings
    database = Database(os.environ['LEADHUNTER_DATABASE_URL'])
    redis_url = os.environ['LEADHUNTER_REDIS_URL']
    redis = Redis.from_url(redis_url, decode_responses=True)
    configure_broker(redis_url)
    settings = LicenseSettings.from_environment()
    clock = GuardedClock(SystemClock(), PostgresClockStore(database, settings.installation_id or UUID(int=0)))
    stopped = threading.Event()
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda *_: stopped.set())
    try:
        while not stopped.is_set():
            try:
                if redis.set('leadhunter:maintenance:job-recovery', 'active', nx=True, ex=25):
                    recover_due_jobs(database, publisher=DramatiqJobPublisher())
                    purge_workspace_archives(settings.local_state_dir / 'server-diagnostics', now=clock.now_epoch())
            except Exception:
                logging.getLogger(__name__).warning('job_recovery_retry_pending')
            stopped.wait(30)
    finally:
        database.close_license_clock_pool(); database.engine.dispose(); redis.close()


if __name__ == '__main__':
    run_scheduler()
