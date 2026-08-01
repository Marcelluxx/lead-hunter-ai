"""Append-only audit event writer with bounded metadata."""

from __future__ import annotations

import uuid
from typing import Any, Mapping

from sqlalchemy.orm import Session

from ..infrastructure.models import AuditEventModel


_ALLOWED_DETAIL_KEYS = frozenset(
    {
        "role",
        "provider",
        "reason",
        "result",
        "count",
        "old_limit",
        "new_limit",
        "source",
        "scope",
        "policy_version",
        "request_type",
        "classification",
    }
)


def append_audit_event(
    session: Session,
    *,
    action: str,
    workspace_id: uuid.UUID | None = None,
    actor_user_id: uuid.UUID | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    details: Mapping[str, Any] | None = None,
    correlation_id: str | None = None,
) -> AuditEventModel:
    safe_details = {
        key: _bounded_scalar(value)
        for key, value in (details or {}).items()
        if key in _ALLOWED_DETAIL_KEYS
    }
    event = AuditEventModel(
        workspace_id=workspace_id,
        actor_user_id=actor_user_id,
        action=action[:120],
        target_type=(target_type or "")[:80] or None,
        target_id=(target_id or "")[:100] or None,
        details=safe_details,
        correlation_id=(correlation_id or "")[:100] or None,
    )
    session.add(event)
    return event


def _bounded_scalar(value: Any) -> str | int | float | bool | None:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)[:500]
