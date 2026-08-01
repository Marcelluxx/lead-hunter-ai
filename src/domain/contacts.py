"""Typed, provenance-aware business contact contracts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from urllib.parse import urlsplit


CONTACT_CLASSIFICATION_RULES_VERSION = "it-eu-business-email-v1"
GENERIC_CONTACT_RETENTION_DAYS = 365
NAMED_CONTACT_RETENTION_DAYS = 90

_EMAIL_PATTERN = re.compile(
    r"^[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
    r"(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$",
    re.IGNORECASE,
)
_GENERIC_LOCAL_PARTS = frozenset(
    {
        "amministrazione",
        "assistenza",
        "booking",
        "commerciale",
        "comunicazione",
        "contact",
        "contatti",
        "customer.care",
        "customerservice",
        "hello",
        "help",
        "info",
        "marketing",
        "office",
        "ordini",
        "pec",
        "prenotazioni",
        "reception",
        "sales",
        "segreteria",
        "service",
        "support",
    }
)


class ContactKind(str, Enum):
    EMAIL = "email"
    PHONE = "phone"


class ContactClassification(str, Enum):
    GENERIC_BUSINESS = "generic_business"
    NAMED_PROFESSIONAL = "named_professional"


class ContactExtractionMethod(str, Enum):
    REGEX = "regex"
    MAILTO = "mailto"
    STRUCTURED_DATA = "structured_data"


def normalize_email(value: str) -> str:
    normalized = value.strip().casefold()
    if len(normalized) > 320 or not _EMAIL_PATTERN.fullmatch(normalized):
        raise ValueError("Indirizzo email non valido.")
    return normalized


def classify_email(value: str) -> ContactClassification:
    """Classify only explicit aliases as generic; ambiguity stays personal."""

    local_part = normalize_email(value).split("@", 1)[0]
    if local_part in _GENERIC_LOCAL_PARTS:
        return ContactClassification.GENERIC_BUSINESS
    return ContactClassification.NAMED_PROFESSIONAL


@dataclass(frozen=True)
class ContactPoint:
    kind: ContactKind
    normalized_value: str
    display_value: str
    source_url: str
    collected_at: datetime
    extraction_method: ContactExtractionMethod
    confidence: float
    classification: ContactClassification
    expires_at: datetime
    evidence_sha256: str
    rules_version: str = CONTACT_CLASSIFICATION_RULES_VERSION

    def __post_init__(self) -> None:
        if self.collected_at.tzinfo is None or self.expires_at.tzinfo is None:
            raise ValueError("I timestamp del contatto devono includere il fuso orario.")
        parsed = urlsplit(self.source_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("Il contatto richiede un URL sorgente HTTP(S).")
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence deve essere compresa tra 0 e 1.")
        if not re.fullmatch(r"[0-9a-f]{64}", self.evidence_sha256):
            raise ValueError("Il contatto richiede un hash SHA-256 dell'evidenza.")
        if self.expires_at <= self.collected_at:
            raise ValueError("La scadenza deve essere successiva alla raccolta.")

    @classmethod
    def from_email(
        cls,
        value: str,
        *,
        source_url: str,
        collected_at: datetime,
        extraction_method: ContactExtractionMethod,
        evidence_sha256: str,
    ) -> "ContactPoint":
        normalized = normalize_email(value)
        classification = classify_email(normalized)
        retention_days = (
            GENERIC_CONTACT_RETENTION_DAYS
            if classification is ContactClassification.GENERIC_BUSINESS
            else NAMED_CONTACT_RETENTION_DAYS
        )
        confidence = 1.0 if extraction_method is ContactExtractionMethod.MAILTO else 0.85
        return cls(
            kind=ContactKind.EMAIL,
            normalized_value=normalized,
            display_value=value.strip(),
            source_url=source_url,
            collected_at=collected_at,
            extraction_method=extraction_method,
            confidence=confidence,
            classification=classification,
            expires_at=collected_at + timedelta(days=retention_days),
            evidence_sha256=evidence_sha256,
        )
