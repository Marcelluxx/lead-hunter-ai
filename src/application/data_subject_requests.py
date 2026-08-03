"""Idempotent, minimally audited data-subject request use cases."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..domain.contacts import ContactExtractionMethod, ContactKind, ContactPoint
from ..domain.privacy import DataSubjectRequestKind, SuppressionScope
from ..infrastructure.models import ContactModel, DataSubjectRequestModel
from .audit_log import append_audit_event
from .suppression import SuppressionService
from .privacy_policy import PrivacyPolicyGate, WorkspacePrivacyPolicyService


class DataSubjectRequestService:
    def __init__(self, suppression: SuppressionService):
        self.suppression = suppression
        self.policies = WorkspacePrivacyPolicyService()

    def erase_and_suppress(
        self,
        session: Session,
        *,
        request_id: uuid.UUID,
        workspace_id: uuid.UUID,
        actor_user_id: uuid.UUID | None,
        kind: str | ContactKind,
        value: str,
        scope: str | SuppressionScope,
        request_kind: str | DataSubjectRequestKind = DataSubjectRequestKind.ERASURE,
    ) -> DataSubjectRequestModel:
        normalized_kind = ContactKind(kind)
        normalized_request_kind = DataSubjectRequestKind(request_kind)
        if normalized_request_kind not in {
            DataSubjectRequestKind.ERASURE,
            DataSubjectRequestKind.OPPOSITION,
        }:
            raise ValueError("Tipo di richiesta non compatibile con cancellazione/suppression.")
        fingerprint = self.suppression.fingerprint(normalized_kind, value)
        existing = self._existing_request(
            session,
            request_id=request_id,
            workspace_id=workspace_id,
            request_kind=normalized_request_kind,
            identifier_kind=normalized_kind,
            fingerprint=fingerprint,
        )
        if existing is not None:
            return existing
        matched_ids = session.scalars(
            select(ContactModel.id).where(
                ContactModel.workspace_id == workspace_id,
                ContactModel.kind == normalized_kind.value,
                ContactModel.fingerprint == fingerprint,
            )
        ).all()
        deleted_count = 0
        if matched_ids:
            result = session.execute(
                delete(ContactModel).where(ContactModel.id.in_(matched_ids))
            )
            deleted_count = int(result.rowcount or 0)
        self.suppression.suppress(
            session,
            workspace_id=workspace_id,
            kind=normalized_kind,
            value=value,
            scope=scope,
            reason="data_subject_erasure",
            actor_user_id=actor_user_id,
        )
        completed_at = datetime.now(timezone.utc)
        request = DataSubjectRequestModel(
            id=request_id,
            workspace_id=workspace_id,
            actor_user_id=actor_user_id,
            request_kind=normalized_request_kind.value,
            identifier_kind=normalized_kind.value,
            subject_fingerprint=fingerprint,
            status="completed",
            deleted_count=deleted_count,
            completed_at=completed_at,
        )
        session.add(request)
        append_audit_event(
            session,
            action="privacy.request.completed",
            workspace_id=workspace_id,
            actor_user_id=actor_user_id,
            target_type="data_subject_request",
            target_id=str(request_id),
            details={"result": "completed", "count": deleted_count},
        )
        session.flush()
        return request

    def record_access(
        self,
        session: Session,
        *,
        request_id: uuid.UUID,
        workspace_id: uuid.UUID,
        actor_user_id: uuid.UUID | None,
        kind: str | ContactKind,
        value: str,
    ) -> DataSubjectRequestModel:
        normalized_kind = ContactKind(kind)
        fingerprint = self.suppression.fingerprint(normalized_kind, value)
        existing = self._existing_request(
            session,
            request_id=request_id,
            workspace_id=workspace_id,
            request_kind=DataSubjectRequestKind.ACCESS,
            identifier_kind=normalized_kind,
            fingerprint=fingerprint,
        )
        if existing is not None:
            return existing
        request = DataSubjectRequestModel(
            id=request_id,
            workspace_id=workspace_id,
            actor_user_id=actor_user_id,
            request_kind=DataSubjectRequestKind.ACCESS.value,
            identifier_kind=normalized_kind.value,
            subject_fingerprint=fingerprint,
            status="completed",
            deleted_count=0,
            completed_at=datetime.now(timezone.utc),
        )
        session.add(request)
        append_audit_event(
            session,
            action="privacy.request.completed",
            workspace_id=workspace_id,
            actor_user_id=actor_user_id,
            target_type="data_subject_request",
            target_id=str(request_id),
            details={"result": "completed", "request_type": "access", "count": 0},
        )
        session.flush()
        return request

    def rectify(
        self,
        session: Session,
        *,
        request_id: uuid.UUID,
        workspace_id: uuid.UUID,
        actor_user_id: uuid.UUID | None,
        kind: str | ContactKind,
        value: str,
        replacement_value: str,
    ) -> DataSubjectRequestModel:
        normalized_kind = ContactKind(kind)
        if normalized_kind is not ContactKind.EMAIL:
            raise ValueError("La rettifica automatica iniziale supporta soltanto email.")
        old_fingerprint = self.suppression.fingerprint(normalized_kind, value)
        existing = self._existing_request(
            session,
            request_id=request_id,
            workspace_id=workspace_id,
            request_kind=DataSubjectRequestKind.RECTIFICATION,
            identifier_kind=normalized_kind,
            fingerprint=old_fingerprint,
        )
        if existing is not None:
            return existing
        contacts = session.scalars(
            select(ContactModel).where(
                ContactModel.workspace_id == workspace_id,
                ContactModel.kind == normalized_kind.value,
                ContactModel.fingerprint == old_fingerprint,
            )
        ).all()
        policy = self.policies.get(session, workspace_id=workspace_id)
        now = datetime.now(timezone.utc)
        request = DataSubjectRequestModel(
            id=request_id,
            workspace_id=workspace_id,
            actor_user_id=actor_user_id,
            request_kind=DataSubjectRequestKind.RECTIFICATION.value,
            identifier_kind=normalized_kind.value,
            subject_fingerprint=old_fingerprint,
            status="completed",
            deleted_count=0,
            completed_at=now,
        )
        session.add(request)
        session.flush()
        for item in contacts:
            replacement = ContactPoint.from_email(
                replacement_value,
                source_url=item.source_url,
                collected_at=now,
                extraction_method=ContactExtractionMethod.STRUCTURED_DATA,
                evidence_sha256=item.evidence_sha256,
            )
            PrivacyPolicyGate.require_contact_allowed(replacement, policy)
            if self.suppression.is_suppressed(
                session,
                workspace_id=workspace_id,
                kind=normalized_kind,
                value=replacement.normalized_value,
            ):
                raise ValueError("Il valore corretto e presente nella suppression list.")
            item.normalized_value = replacement.normalized_value
            item.display_value = replacement.display_value
            item.fingerprint = self.suppression.fingerprint(
                normalized_kind, replacement.normalized_value
            )
            item.source_type = "data_subject_request"
            item.source_url = None
            item.source_request_id = request.id
            item.collected_at = replacement.collected_at
            item.extraction_method = replacement.extraction_method.value
            item.confidence = replacement.confidence
            item.classification = replacement.classification.value
            item.expires_at = replacement.expires_at
            item.evidence_sha256 = item.fingerprint
            item.rules_version = replacement.rules_version
        self.suppression.suppress(
            session,
            workspace_id=workspace_id,
            kind=normalized_kind,
            value=value,
            scope=SuppressionScope.WORKSPACE,
            reason="rectified_identifier",
            actor_user_id=actor_user_id,
        )
        append_audit_event(
            session,
            action="privacy.request.completed",
            workspace_id=workspace_id,
            actor_user_id=actor_user_id,
            target_type="data_subject_request",
            target_id=str(request_id),
            details={
                "result": "completed",
                "request_type": "rectification",
                "count": len(contacts),
            },
        )
        session.flush()
        return request

    def subject_data(
        self,
        session: Session,
        *,
        workspace_id: uuid.UUID,
        kind: str | ContactKind,
        value: str,
    ) -> list[dict[str, str]]:
        normalized_kind = ContactKind(kind)
        fingerprint = self.suppression.fingerprint(normalized_kind, value)
        contacts = session.scalars(
            select(ContactModel).where(
                ContactModel.workspace_id == workspace_id,
                ContactModel.kind == normalized_kind.value,
                ContactModel.fingerprint == fingerprint,
            )
        ).all()
        return [
            {
                "kind": item.kind,
                "value": item.display_value,
                "source_type": item.source_type,
                "source_url": item.source_url or "",
                "collected_at": item.collected_at.isoformat(),
                "classification": item.classification,
                "expires_at": item.expires_at.isoformat(),
            }
            for item in contacts
        ]

    @staticmethod
    def _existing_request(
        session: Session,
        *,
        request_id: uuid.UUID,
        workspace_id: uuid.UUID,
        request_kind: DataSubjectRequestKind,
        identifier_kind: ContactKind,
        fingerprint: str,
    ) -> DataSubjectRequestModel | None:
        existing = session.get(DataSubjectRequestModel, request_id)
        if existing is None:
            return None
        if (
            existing.workspace_id != workspace_id
            or existing.request_kind != request_kind.value
            or existing.identifier_kind != identifier_kind.value
            or existing.subject_fingerprint != fingerprint
        ):
            raise ValueError("request_id gia utilizzato con parametri differenti.")
        return existing
