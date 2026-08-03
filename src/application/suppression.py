"""HMAC-based suppression checks without storing the suppressed identifier."""

from __future__ import annotations

import hashlib
import hmac
import re
import uuid

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..domain.contacts import ContactKind, normalize_email
from ..domain.privacy import SuppressionScope
from ..infrastructure.models import SuppressionEntryModel


class SuppressionError(ValueError):
    pass


class SuppressionService:
    def __init__(self, hmac_key: bytes):
        if len(hmac_key) < 32:
            raise ValueError("La chiave HMAC di suppression deve contenere almeno 32 byte.")
        self._hmac_key = hmac_key

    def fingerprint(self, kind: str | ContactKind, value: str) -> str:
        normalized_kind = ContactKind(kind)
        normalized_value = _normalize_identifier(normalized_kind, value)
        message = f"{normalized_kind.value}:{normalized_value}".encode("utf-8")
        return hmac.new(self._hmac_key, message, hashlib.sha256).hexdigest()

    def is_suppressed(
        self,
        session: Session,
        *,
        workspace_id: uuid.UUID,
        kind: str | ContactKind,
        value: str,
    ) -> bool:
        normalized_kind = ContactKind(kind)
        fingerprint = self.fingerprint(normalized_kind, value)
        return session.scalar(
            select(SuppressionEntryModel.id).where(
                SuppressionEntryModel.kind == normalized_kind.value,
                SuppressionEntryModel.fingerprint == fingerprint,
                or_(
                    SuppressionEntryModel.scope_key == "global",
                    SuppressionEntryModel.scope_key == str(workspace_id),
                ),
            ).limit(1)
        ) is not None

    def suppress(
        self,
        session: Session,
        *,
        workspace_id: uuid.UUID,
        kind: str | ContactKind,
        value: str,
        scope: str | SuppressionScope,
        reason: str,
        actor_user_id: uuid.UUID | None = None,
    ) -> SuppressionEntryModel:
        normalized_kind = ContactKind(kind)
        normalized_scope = SuppressionScope(scope)
        fingerprint = self.fingerprint(normalized_kind, value)
        scope_key = "global" if normalized_scope is SuppressionScope.GLOBAL else str(workspace_id)
        existing = session.scalar(
            select(SuppressionEntryModel).where(
                SuppressionEntryModel.scope_key == scope_key,
                SuppressionEntryModel.kind == normalized_kind.value,
                SuppressionEntryModel.fingerprint == fingerprint,
            )
        )
        if existing is not None:
            return existing
        record = SuppressionEntryModel(
            workspace_id=(
                None if normalized_scope is SuppressionScope.GLOBAL else workspace_id
            ),
            scope=normalized_scope.value,
            scope_key=scope_key,
            kind=normalized_kind.value,
            fingerprint=fingerprint,
            reason=reason.strip()[:80] or "privacy_request",
            created_by=actor_user_id,
        )
        session.add(record)
        session.flush()
        return record


def _normalize_identifier(kind: ContactKind, value: str) -> str:
    if kind is ContactKind.EMAIL:
        return normalize_email(value)
    normalized = re.sub(r"[^0-9+]", "", value.strip())
    if not 7 <= len(normalized) <= 20:
        raise SuppressionError("Numero di telefono non valido.")
    return normalized
