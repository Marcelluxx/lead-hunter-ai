"""Write-only provider credential management."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..infrastructure.crypto import SecretCipher
from ..infrastructure.models import ProviderCredentialModel
from .audit_log import append_audit_event


@dataclass(frozen=True)
class CredentialStatus:
    provider: str
    fingerprint: str
    updated_at: datetime


class CredentialService:
    SCHEMA_VERSION = 1

    def __init__(self, cipher: SecretCipher):
        self._cipher = cipher

    def put(
        self,
        session: Session,
        *,
        workspace_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        provider: str,
        value: str,
    ) -> CredentialStatus:
        normalized = provider.strip().lower()
        aad = self._aad(workspace_id, normalized)
        record = session.scalar(
            select(ProviderCredentialModel).where(
                ProviderCredentialModel.workspace_id == workspace_id,
                ProviderCredentialModel.provider == normalized,
            )
        )
        if record is None:
            record = ProviderCredentialModel(workspace_id=workspace_id, provider=normalized)
            session.add(record)
        record.ciphertext = self._cipher.encrypt(value, associated_data=aad)
        record.fingerprint = self._cipher.fingerprint(value)
        record.key_version = self.SCHEMA_VERSION
        session.flush()
        append_audit_event(
            session,
            action="secret.updated",
            workspace_id=workspace_id,
            actor_user_id=actor_user_id,
            target_type="provider_credential",
            target_id=str(record.id),
            details={"provider": normalized},
        )
        return CredentialStatus(normalized, record.fingerprint, record.updated_at)

    def list_status(self, session: Session, *, workspace_id: uuid.UUID) -> list[CredentialStatus]:
        records = session.scalars(
            select(ProviderCredentialModel).where(
                ProviderCredentialModel.workspace_id == workspace_id
            )
        )
        return [CredentialStatus(row.provider, row.fingerprint, row.updated_at) for row in records]

    def resolve(self, session: Session, *, workspace_id: uuid.UUID, provider: str) -> str:
        normalized = provider.strip().lower()
        record = session.scalar(
            select(ProviderCredentialModel).where(
                ProviderCredentialModel.workspace_id == workspace_id,
                ProviderCredentialModel.provider == normalized,
            )
        )
        if record is None:
            raise KeyError(normalized)
        return self._cipher.decrypt(
            record.ciphertext,
            associated_data=self._aad(workspace_id, normalized),
        )

    @classmethod
    def _aad(cls, workspace_id: uuid.UUID, provider: str) -> str:
        return f"provider:{workspace_id}:{provider}:v{cls.SCHEMA_VERSION}"
