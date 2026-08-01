"""Persistence boundary for discovery references and verified site attributes."""

from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy.orm import Session

from ..domain.discovery import TransientCandidate
from ..domain.provenance import DataSource, VerifiedLead
from ..infrastructure.models import (
    EvidenceModel,
    LeadAttributeModel,
    LeadModel,
    ProviderReferenceModel,
)


class DiscoveryPersistenceError(ValueError):
    pass


class DiscoveryPersistenceService:
    PLACE_ID_REFRESH_DAYS = 365

    def persist_provider_reference(
        self,
        session: Session,
        *,
        workspace_id: uuid.UUID,
        job_id: uuid.UUID,
        candidate: TransientCandidate,
        lead_id: uuid.UUID | None = None,
    ) -> ProviderReferenceModel:
        reference = ProviderReferenceModel(
            workspace_id=workspace_id,
            job_id=job_id,
            lead_id=lead_id,
            provider=candidate.provider,
            external_id=candidate.external_id,
            last_verified_at=candidate.collected_at,
            refresh_after=candidate.collected_at + timedelta(days=self.PLACE_ID_REFRESH_DAYS),
        )
        session.add(reference)
        return reference

    def persist_verified_lead(
        self,
        session: Session,
        *,
        workspace_id: uuid.UUID,
        job_id: uuid.UUID,
        lead: VerifiedLead,
    ) -> LeadModel:
        if not lead.provenance:
            raise DiscoveryPersistenceError("missing_provenance")
        record = LeadModel(workspace_id=workspace_id, job_id=job_id, status="verified")
        session.add(record)
        session.flush()
        evidence_by_key: dict[tuple[str, str], EvidenceModel] = {}
        values = lead.to_export_record()
        for field_name, provenance in lead.provenance.items():
            if provenance.source not in {DataSource.OFFICIAL_WEBSITE, DataSource.USER_INPUT}:
                raise DiscoveryPersistenceError("provider_content_cannot_be_persisted_as_attribute")
            value = values.get(field_name)
            if value in (None, "", [], ()):
                continue
            evidence_id = None
            if provenance.source_url and provenance.evidence_sha256:
                key = (provenance.source_url, provenance.evidence_sha256)
                evidence = evidence_by_key.get(key)
                if evidence is None:
                    evidence = EvidenceModel(
                        workspace_id=workspace_id,
                        lead_id=record.id,
                        source_url=provenance.source_url,
                        content_sha256=provenance.evidence_sha256,
                        collected_at=provenance.collected_at,
                    )
                    session.add(evidence)
                    session.flush()
                    evidence_by_key[key] = evidence
                evidence_id = evidence.id
            serialized = ", ".join(value) if isinstance(value, (list, tuple)) else str(value)
            session.add(
                LeadAttributeModel(
                    workspace_id=workspace_id,
                    lead_id=record.id,
                    evidence_id=evidence_id,
                    field_name=field_name,
                    value_text=serialized,
                    source=provenance.source.value,
                    source_url=provenance.source_url,
                    collected_at=provenance.collected_at,
                    expires_at=provenance.expires_at,
                    confidence=provenance.confidence,
                    data_classification=provenance.data_classification,
                )
            )
        return record
