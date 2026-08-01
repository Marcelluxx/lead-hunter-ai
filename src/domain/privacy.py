"""Privacy, retention and data-subject request domain contracts."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import Enum


PRIVACY_POLICY_VERSION = "it-eu-b2b-v1"
RETENTION_DAYS = {
    "raw_html": 7,
    "intermediate_screenshot": 30,
    "named_professional": 90,
    "generic_business": 365,
    "selected_report_evidence": 365,
    "operational_log": 30,
    "minimal_audit_log": 365,
}


class SuppressionScope(str, Enum):
    WORKSPACE = "workspace"
    GLOBAL = "global"


class DataSubjectRequestKind(str, Enum):
    ACCESS = "access"
    RECTIFICATION = "rectification"
    ERASURE = "erasure"
    OPPOSITION = "opposition"


@dataclass(frozen=True)
class WorkspacePrivacyPolicy:
    workspace_id: uuid.UUID
    purpose: str
    legal_basis: str
    privacy_contact: str
    market: str = "IT_EU"
    named_contact_retention_days: int = 90
    policy_version: str = PRIVACY_POLICY_VERSION
    enabled: bool = True

    def __post_init__(self) -> None:
        if not self.purpose.strip() or not self.legal_basis.strip():
            raise ValueError("Finalita e base giuridica sono obbligatorie.")
        if "@" not in self.privacy_contact or len(self.privacy_contact) > 320:
            raise ValueError("Referente privacy non valido.")
        if self.market != "IT_EU":
            raise ValueError("La prima versione supporta esclusivamente Italia/UE.")
        if not 1 <= self.named_contact_retention_days <= 90:
            raise ValueError("La retention dei contatti nominativi non puo superare 90 giorni.")
        if not self.policy_version.strip():
            raise ValueError("La policy deve essere versionata.")

    @property
    def is_complete(self) -> bool:
        return self.enabled and bool(
            self.purpose.strip()
            and self.legal_basis.strip()
            and self.privacy_contact.strip()
            and self.market == "IT_EU"
            and self.named_contact_retention_days <= 90
        )
