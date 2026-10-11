from __future__ import annotations

import uuid

import dramatiq
from dramatiq.brokers.redis import RedisBroker


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
    from .job_runtime import WorkerRuntime
    # Only an identifier crosses the queue; all authority is loaded from the database.
    parsed_id = uuid.UUID(job_id)
    runtime = WorkerRuntime.from_environment()
    try:
        runtime.execute(parsed_id)
    finally:
        runtime.close()
