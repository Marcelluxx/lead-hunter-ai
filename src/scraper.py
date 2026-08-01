"""Backward-compatible discovery facade.

The provider adapter owns raw Google responses. Callers only receive transient,
typed candidates and cannot accidentally persist a provider JSON document.
"""

from __future__ import annotations

from typing import Any, Callable

from .domain.discovery import DiscoveryProvider, DiscoveryQuery, TransientCandidate
from .providers.discovery import GooglePlacesDiscoveryProvider


class LeadScraper:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        places_url: str | None = None,
        geocoding_url: str | None = None,
        field_mask: str | None = None,
        http_client: Any = None,
        provider: DiscoveryProvider | None = None,
    ):
        if provider is None:
            if not places_url or not field_mask:
                raise ValueError("Configurazione Google Places incompleta.")
            kwargs: dict[str, Any] = {
                "api_key": api_key or "",
                "places_url": places_url,
                "field_mask": field_mask,
            }
            if http_client is not None:
                kwargs["http_client"] = http_client
            provider = GooglePlacesDiscoveryProvider(**kwargs)
        self.provider = provider
        # Kept as non-secret compatibility metadata for diagnostics/tests.
        self.places_url = places_url
        self.geocoding_url = geocoding_url
        self.http_client = http_client
        self.headers = getattr(provider, "headers", {})

    @property
    def attribution(self):
        return self.provider.attribution

    def scrape_entire_grid(
        self,
        query: str,
        center_lat: float,
        center_lng: float,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> list[TransientCandidate]:
        batch = self.provider.discover(
            DiscoveryQuery(query, center_lat, center_lng),
            on_progress=on_progress,
        )
        return list(batch.candidates)

    def get_city_name(self, lat: float, lng: float) -> str:
        """No provider-derived location is persisted in output filenames."""
        return f"area_{lat:.4f}_{lng:.4f}".replace("-", "m").replace(".", "_")
