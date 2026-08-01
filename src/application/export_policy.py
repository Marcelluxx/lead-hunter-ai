"""Central fail-closed report/export policy."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Callable

from ..domain.discovery import TransientCandidate
from ..domain.provenance import DataSource, VerifiedLead
from ..domain.privacy import WorkspacePrivacyPolicy
from .privacy_policy import PrivacyPolicyGate


class ExportPolicyError(PermissionError):
    pass


class ExportPolicy:
    @staticmethod
    def require_exportable(
        leads: Iterable[Any],
        mode: str,
        privacy_policy: WorkspacePrivacyPolicy | None = None,
        suppression_checker: Callable[[Any], bool] | None = None,
    ) -> None:
        items = list(leads)
        if mode == "no_website":
            raise ExportPolicyError(
                "I risultati Google Places senza sito sono transitori e non possono essere esportati."
            )
        for lead in items:
            ExportPolicy._require_verified(lead, privacy_policy, suppression_checker)

    @staticmethod
    def _require_verified(
        lead: Any,
        privacy_policy: WorkspacePrivacyPolicy | None,
        suppression_checker: Callable[[Any], bool] | None,
    ) -> None:
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
        if isinstance(lead, VerifiedLead):
            if lead.contacts and suppression_checker is None:
                raise ExportPolicyError(
                    "Export contatti bloccato: verifica suppression non configurata."
                )
            for contact in lead.contacts:
                PrivacyPolicyGate.require_contact_allowed(contact, privacy_policy)
                if suppression_checker and suppression_checker(contact):
                    raise ExportPolicyError("Export bloccato dalla suppression policy.")
