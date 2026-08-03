"""Governed persistence boundary for typed contacts."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..domain.contacts import ContactPoint
from ..infrastructure.models import ContactModel
from .privacy_policy import PrivacyPolicyError, PrivacyPolicyGate, WorkspacePrivacyPolicyService
from .suppression import SuppressionService


@dataclass(frozen=True)
class ContactPersistenceResult:
    persisted: int
    suppressed: int
    policy_rejected: int
    expired: int


class ContactService:
    def __init__(self, suppression: SuppressionService):
        self.suppression = suppression
        self.policies = WorkspacePrivacyPolicyService()

    def persist(
        self,
        session: Session,
        *,
        workspace_id: uuid.UUID,
        lead_id: uuid.UUID,
        contacts: tuple[ContactPoint, ...] | list[ContactPoint],
        now: datetime | None = None,
    ) -> ContactPersistenceResult:
        cutoff = now or datetime.now(timezone.utc)
        policy = self.policies.get(session, workspace_id=workspace_id)
        counts = {"persisted": 0, "suppressed": 0, "policy_rejected": 0, "expired": 0}
        for contact in contacts:
            if contact.expires_at <= cutoff:
                counts["expired"] += 1
                continue
            try:
                PrivacyPolicyGate.require_contact_allowed(contact, policy)
            except PrivacyPolicyError:
                counts["policy_rejected"] += 1
                continue
            if self.suppression.is_suppressed(
                session,
                workspace_id=workspace_id,
                kind=contact.kind,
                value=contact.normalized_value,
            ):
                counts["suppressed"] += 1
                continue
            session.add(
                ContactModel(
                    workspace_id=workspace_id,
                    lead_id=lead_id,
                    kind=contact.kind.value,
                    normalized_value=contact.normalized_value,
                    display_value=contact.display_value,
                    fingerprint=self.suppression.fingerprint(
                        contact.kind, contact.normalized_value
                    ),
                    source_type="official_website",
                    source_url=contact.source_url,
                    collected_at=contact.collected_at,
                    extraction_method=contact.extraction_method.value,
                    confidence=contact.confidence,
                    classification=contact.classification.value,
                    expires_at=contact.expires_at,
                    evidence_sha256=contact.evidence_sha256,
                    rules_version=contact.rules_version,
                )
            )
            counts["persisted"] += 1
        return ContactPersistenceResult(**counts)
