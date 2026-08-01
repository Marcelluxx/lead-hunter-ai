"""Workspace privacy policy and fail-closed contact export gates."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..domain.contacts import ContactClassification, ContactPoint
from ..domain.identity import Permission
from ..domain.privacy import WorkspacePrivacyPolicy
from ..infrastructure.models import (
    ContactModel,
    RetentionEventModel,
    WorkspacePrivacyPolicyModel,
)
from .audit_log import append_audit_event
from .authorization import AuthorizationDenied, require_permission
from .suppression import SuppressionService


class PrivacyPolicyError(PermissionError):
    pass


class PrivacyPolicyGate:
    @staticmethod
    def require_contact_allowed(
        contact: ContactPoint,
        policy: WorkspacePrivacyPolicy | None,
        *,
        now: datetime | None = None,
    ) -> None:
        cutoff = now or datetime.now(timezone.utc)
        if contact.expires_at <= cutoff:
            raise PrivacyPolicyError("Contatto scaduto non persistibile o esportabile.")
        if contact.classification is ContactClassification.GENERIC_BUSINESS:
            return
        if policy is None or not policy.is_complete:
            raise PrivacyPolicyError(
                "I contatti nominativi richiedono una policy privacy Italia/UE completa."
            )
        maximum_expiry = contact.collected_at + _days(policy.named_contact_retention_days)
        if contact.expires_at > maximum_expiry:
            raise PrivacyPolicyError("Retention nominativa superiore alla policy del workspace.")


class WorkspacePrivacyPolicyService:
    def get(
        self, session: Session, *, workspace_id: uuid.UUID
    ) -> WorkspacePrivacyPolicy | None:
        model = session.get(WorkspacePrivacyPolicyModel, workspace_id)
        return _domain_policy(model) if model is not None else None

    def put(
        self,
        session: Session,
        *,
        policy: WorkspacePrivacyPolicy,
        actor_user_id: uuid.UUID | None,
    ) -> WorkspacePrivacyPolicyModel:
        model = session.get(WorkspacePrivacyPolicyModel, policy.workspace_id)
        if model is None:
            model = WorkspacePrivacyPolicyModel(workspace_id=policy.workspace_id)
            session.add(model)
        model.purpose = policy.purpose.strip()
        model.legal_basis = policy.legal_basis.strip()
        model.privacy_contact = policy.privacy_contact.strip().casefold()
        model.market = policy.market
        model.named_contact_retention_days = policy.named_contact_retention_days
        model.policy_version = policy.policy_version
        model.enabled = policy.enabled
        model.updated_by = actor_user_id
        session.flush()
        return model


class PrivacyExportService:
    def __init__(self, suppression: SuppressionService):
        self.suppression = suppression
        self.policies = WorkspacePrivacyPolicyService()

    def exportable_contacts(
        self,
        session: Session,
        *,
        workspace_id: uuid.UUID,
        now: datetime | None = None,
    ) -> list[ContactModel]:
        cutoff = now or datetime.now(timezone.utc)
        deletion = session.execute(
            delete(ContactModel).where(
                ContactModel.workspace_id == workspace_id,
                ContactModel.expires_at <= cutoff,
            )
        )
        expired_count = int(deletion.rowcount or 0)
        if expired_count:
            session.add(
                RetentionEventModel(
                    workspace_id=workspace_id,
                    entity_type="contact_export_expiry",
                    deleted_count=expired_count,
                    ran_at=cutoff,
                )
            )
        contacts = session.scalars(
            select(ContactModel)
            .where(ContactModel.workspace_id == workspace_id)
            .order_by(ContactModel.normalized_value)
        ).all()
        policy = self.policies.get(session, workspace_id=workspace_id)
        allowed: list[ContactModel] = []
        for contact in contacts:
            if self.suppression.is_suppressed(
                session,
                workspace_id=workspace_id,
                kind=contact.kind,
                value=contact.normalized_value,
            ):
                continue
            if contact.classification == ContactClassification.NAMED_PROFESSIONAL.value:
                if policy is None or not policy.is_complete:
                    raise PrivacyPolicyError(
                        "Export nominativo bloccato: policy privacy incompleta."
                    )
                maximum_expiry = _aware(contact.collected_at) + _days(
                    policy.named_contact_retention_days
                )
                if _aware(contact.expires_at) > maximum_expiry:
                    raise PrivacyPolicyError(
                        "Export nominativo bloccato: retention oltre la policy."
                    )
            allowed.append(contact)
        return allowed

    def export_for_actor(
        self,
        session: Session,
        *,
        workspace_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        mfa_verified: bool,
        job_id: uuid.UUID | None = None,
        now: datetime | None = None,
    ) -> list[ContactModel]:
        try:
            require_permission(
                session,
                user_id=actor_user_id,
                workspace_id=workspace_id,
                permission=Permission.EXPORT_RESULTS,
                mfa_verified=mfa_verified,
            )
        except AuthorizationDenied as exc:
            raise PrivacyPolicyError("Export non autorizzato per il workspace.") from exc
        contacts = self.exportable_contacts(
            session, workspace_id=workspace_id, now=now
        )
        policy = self.policies.get(session, workspace_id=workspace_id)
        append_audit_event(
            session,
            action="contacts.exported",
            workspace_id=workspace_id,
            actor_user_id=actor_user_id,
            target_type="job" if job_id else "workspace",
            target_id=str(job_id or workspace_id),
            details={
                "count": len(contacts),
                "policy_version": policy.policy_version if policy else "generic-default",
            },
        )
        return contacts


def _domain_policy(model: WorkspacePrivacyPolicyModel) -> WorkspacePrivacyPolicy:
    return WorkspacePrivacyPolicy(
        workspace_id=model.workspace_id,
        purpose=model.purpose,
        legal_basis=model.legal_basis,
        privacy_contact=model.privacy_contact,
        market=model.market,
        named_contact_retention_days=model.named_contact_retention_days,
        policy_version=model.policy_version,
        enabled=model.enabled,
    )


def _days(value: int):
    from datetime import timedelta

    return timedelta(days=value)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
