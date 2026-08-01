"""Provenance contracts for data that may cross the persistence boundary."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping

from .contacts import ContactPoint


class DataSource(str, Enum):
    OFFICIAL_WEBSITE = "official_website"
    USER_INPUT = "user_input"
    PROVIDER_REFERENCE = "provider_reference"


@dataclass(frozen=True)
class FieldProvenance:
    source: DataSource
    source_url: str | None
    collected_at: datetime
    evidence_sha256: str | None = None
    expires_at: datetime | None = None
    confidence: float = 1.0
    data_classification: str = "business_contact"

    def __post_init__(self) -> None:
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence deve essere compresa tra 0 e 1")


@dataclass(frozen=True)
class VerifiedLead:
    """Lead made only of independently collected, exportable attributes."""

    business_name: str
    category: str
    website: str
    contacts: tuple[ContactPoint, ...] = ()
    website_score: int | str | None = None
    framework: str = ""
    diagnosis: str = ""
    site_brief: str = ""
    cold_message: str = ""
    provenance: Mapping[str, FieldProvenance] = field(default_factory=dict)

    @property
    def export_classification(self) -> str:
        return "verified_report"

    @property
    def extracted_emails(self) -> tuple[str, ...]:
        return tuple(contact.display_value for contact in self.contacts)

    def to_export_record(self) -> dict[str, Any]:
        return {
            "export_classification": self.export_classification,
            "business_name": self.business_name,
            "category": self.category,
            "website": self.website,
            "extracted_email": list(self.extracted_emails),
            "contacts": list(self.contacts),
            "website_score": self.website_score,
            "framework": self.framework,
            "diagnosis": self.diagnosis,
            "site_brief": self.site_brief,
            "cold_message": self.cold_message,
            "provenance": dict(self.provenance),
        }


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
