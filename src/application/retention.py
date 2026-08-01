"""Workspace-scoped retention enforcement."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import delete
from sqlalchemy.orm import Session

from ..infrastructure.models import LeadAttributeModel, RetentionEventModel


class RetentionService:
    def purge_expired_attributes(
        self,
        session: Session,
        *,
        workspace_id: uuid.UUID,
        now: datetime | None = None,
    ) -> int:
        cutoff = now or datetime.now(timezone.utc)
        result = session.execute(
            delete(LeadAttributeModel).where(
                LeadAttributeModel.workspace_id == workspace_id,
                LeadAttributeModel.expires_at.is_not(None),
                LeadAttributeModel.expires_at <= cutoff,
            )
        )
        deleted_count = int(result.rowcount or 0)
        session.add(
            RetentionEventModel(
                workspace_id=workspace_id,
                entity_type="lead_attributes",
                deleted_count=deleted_count,
                ran_at=cutoff,
            )
        )
        return deleted_count
