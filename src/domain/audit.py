"""Contratti tipizzati per gli output dell'audit AI."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Mapping


class AuditValidationError(ValueError):
    """L'output del modello non rispetta il contratto applicativo."""


@dataclass(frozen=True)
class WebsiteAuditResult:
    website_score: int
    diagnosis: str
    site_brief: str
    framework: str
    cold_message: str

    @classmethod
    def from_llm(cls, payload: Any) -> "WebsiteAuditResult":
        if not isinstance(payload, Mapping):
            raise AuditValidationError("L'output AI deve essere un oggetto JSON.")

        required = ("website_score", "diagnosis", "site_brief", "cold_message")
        missing = [field for field in required if field not in payload]
        if missing:
            raise AuditValidationError(f"Campi obbligatori mancanti: {', '.join(missing)}")

        raw_score = payload["website_score"]
        if isinstance(raw_score, bool):
            raise AuditValidationError("website_score non valido.")
        if isinstance(raw_score, str):
            match = re.fullmatch(r"\s*(10|[1-9])(?:\s*/\s*10)?\s*", raw_score)
            if not match:
                raise AuditValidationError("website_score non valido.")
            score = int(match.group(1))
        elif isinstance(raw_score, (int, float)) and int(raw_score) == raw_score:
            score = int(raw_score)
        else:
            raise AuditValidationError("website_score non valido.")
        if not 1 <= score <= 10:
            raise AuditValidationError("website_score fuori intervallo.")

        return cls(
            website_score=score,
            diagnosis=_bounded_string(payload["diagnosis"], "diagnosis", 4000),
            site_brief=_bounded_string(payload["site_brief"], "site_brief", 2000),
            framework=_bounded_string(payload.get("framework", "Non rilevato"), "framework", 200),
            cold_message=_bounded_string(payload["cold_message"], "cold_message", 2000),
        )

    def to_public_dict(self) -> dict[str, Any]:
        """Espone esclusivamente i campi di prodotto consentiti."""

        return asdict(self)


def _bounded_string(value: Any, field_name: str, max_length: int) -> str:
    if not isinstance(value, str):
        raise AuditValidationError(f"{field_name} deve essere una stringa.")
    normalized = value.strip()
    if not normalized:
        raise AuditValidationError(f"{field_name} non può essere vuoto.")
    if len(normalized) > max_length:
        raise AuditValidationError(f"{field_name} supera il limite di {max_length} caratteri.")
    return normalized
