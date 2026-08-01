"""Persistent job state-machine contracts."""

from __future__ import annotations

from enum import Enum


class JobState(str, Enum):
    QUEUED = "queued"
    VALIDATING = "validating"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    FAILED = "failed"


TERMINAL_JOB_STATES = frozenset(
    {JobState.COMPLETED, JobState.PARTIAL, JobState.CANCELLED, JobState.FAILED}
)

ALLOWED_JOB_TRANSITIONS: dict[JobState, frozenset[JobState]] = {
    JobState.QUEUED: frozenset({JobState.VALIDATING, JobState.CANCELLED}),
    JobState.VALIDATING: frozenset(
        {JobState.RUNNING, JobState.CANCELLED, JobState.FAILED}
    ),
    JobState.RUNNING: frozenset(
        {
            JobState.COMPLETED,
            JobState.PARTIAL,
            JobState.CANCELLED,
            JobState.FAILED,
        }
    ),
    JobState.COMPLETED: frozenset(),
    JobState.PARTIAL: frozenset(),
    JobState.CANCELLED: frozenset(),
    JobState.FAILED: frozenset(),
}


class InvalidJobTransition(ValueError):
    pass


def ensure_job_transition(current: JobState | str, target: JobState | str) -> None:
    source_state = current if isinstance(current, JobState) else JobState(current)
    target_state = target if isinstance(target, JobState) else JobState(target)
    if target_state not in ALLOWED_JOB_TRANSITIONS[source_state]:
        raise InvalidJobTransition(f"{source_state.value}->{target_state.value}")
