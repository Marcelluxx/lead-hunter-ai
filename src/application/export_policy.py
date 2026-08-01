"""Central fail-closed report/export policy."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from ..domain.discovery import TransientCandidate
from ..domain.provenance import DataSource, VerifiedLead


class ExportPolicyError(PermissionError):
    pass


class ExportPolicy:
    @staticmethod
    def require_exportable(leads: Iterable[Any], mode: str) -> None:
        items = list(leads)
        if mode == "no_website":
            raise ExportPolicyError(
                "I risultati Google Places senza sito sono transitori e non possono essere esportati."
            )
        for lead in items:
            ExportPolicy._require_verified(lead)

    @staticmethod
    def _require_verified(lead: Any) -> None:
        if isinstance(lead, TransientCandidate) or getattr(
            lead, "is_transient_provider_content", False
        ):
            raise ExportPolicyError("Contenuto del provider non esportabile.")
        if isinstance(lead, VerifiedLead):
            provenance = lead.provenance
        elif isinstance(lead, Mapping) and lead.get("export_classification") == "verified_report":
            provenance = lead.get("provenance", {})
        else:
            raise ExportPolicyError("Record privo di classificazione verificata.")
        if not provenance:
            raise ExportPolicyError("Record privo di provenienza verificabile.")
        forbidden = {
            key
            for key, item in provenance.items()
            if getattr(item, "source", None)
            not in {DataSource.OFFICIAL_WEBSITE, DataSource.USER_INPUT}
        }
        if forbidden:
            raise ExportPolicyError(
                "Campi non esportabili per provenienza: " + ", ".join(sorted(forbidden))
            )
