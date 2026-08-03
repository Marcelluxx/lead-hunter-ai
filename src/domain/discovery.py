"""Provider-neutral discovery contracts with an explicit transient boundary."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from collections.abc import Mapping
from typing import Any, Callable, Protocol, Sequence


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class ProviderAttribution:
    provider: str
    label: str
    terms_url: str
    privacy_url: str


@dataclass(frozen=True)
class CandidateReference:
    provider: str
    external_id: str
    last_verified_at: datetime


@dataclass(frozen=True)
class ProviderRetentionRule:
    reference_refresh_days: int
    coordinate_ttl_days: int | None
    raw_payload_ttl_seconds: int = 0


@dataclass(frozen=True)
class DiscoveryQuery:
    text: str
    center_lat: float
    center_lng: float
    language: str = "it"

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("La query di discovery non puo essere vuota.")
        if not -90 <= self.center_lat <= 90:
            raise ValueError("Latitudine non valida.")
        if not -180 <= self.center_lng <= 180:
            raise ValueError("Longitudine non valida.")


@dataclass(frozen=True)
class TransientCandidate:
    """Candidate usable only during the current process/request.

    Provider content deliberately has no generic serialization helper. It must
    never cross queues, persistence, LLM prompts or report/export boundaries.
    """

    provider: str
    external_id: str
    display_name: str
    website_url: str | None
    collected_at: datetime
    attribution: ProviderAttribution

    @property
    def is_transient_provider_content(self) -> bool:
        return True

    @property
    def reference(self) -> CandidateReference:
        return CandidateReference(self.provider, self.external_id, self.collected_at)


@dataclass(frozen=True)
class DiscoveryBatch:
    candidates: tuple[TransientCandidate, ...]
    attribution: ProviderAttribution


class DiscoveryProvider(Protocol):
    attribution: ProviderAttribution
    retention: ProviderRetentionRule

    def discover(
        self,
        query: DiscoveryQuery,
        *,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> DiscoveryBatch: ...


def unique_candidates(candidates: Sequence[TransientCandidate]) -> tuple[TransientCandidate, ...]:
    seen: set[tuple[str, str]] = set()
    result: list[TransientCandidate] = []
    for candidate in candidates:
        key = (candidate.provider, candidate.external_id)
        if key not in seen:
            seen.add(key)
            result.append(candidate)
    return tuple(result)


class ProviderPayloadError(ValueError):
    pass


_GOOGLE_PAYLOAD_KEYS = frozenset(
    {
        "places",
        "displayName",
        "formattedAddress",
        "addressComponents",
        "nationalPhoneNumber",
        "rating",
        "userRatingCount",
        "reviews",
        "websiteUri",
    }
)


def ensure_provider_payload_absent(value: Any) -> None:
    """Reject provider response shapes at every persistent/queue input boundary."""
    if isinstance(value, Mapping):
        if _GOOGLE_PAYLOAD_KEYS.intersection(value.keys()):
            raise ProviderPayloadError("provider_payload_not_allowed")
        for nested in value.values():
            ensure_provider_payload_absent(nested)
    elif isinstance(value, (list, tuple)):
        for nested in value:
            ensure_provider_payload_absent(nested)
