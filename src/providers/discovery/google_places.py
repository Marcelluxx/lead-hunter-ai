"""Google Places adapter. Full provider responses never leave this module."""

from __future__ import annotations

import math
import time
from datetime import datetime, timezone
from typing import Any, Callable

import requests

from ...domain.discovery import (
    DiscoveryBatch,
    DiscoveryQuery,
    ProviderAttribution,
    ProviderRetentionRule,
    TransientCandidate,
    unique_candidates,
)


GOOGLE_ATTRIBUTION = ProviderAttribution(
    provider="google_places",
    label="Google Maps",
    terms_url="https://cloud.google.com/terms/maps-platform/eea",
    privacy_url="https://policies.google.com/privacy",
)


class DiscoveryProviderError(RuntimeError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class GooglePlacesDiscoveryProvider:
    attribution = GOOGLE_ATTRIBUTION
    retention = ProviderRetentionRule(
        reference_refresh_days=365,
        coordinate_ttl_days=30,
        raw_payload_ttl_seconds=0,
    )

    def __init__(
        self,
        *,
        api_key: str,
        places_url: str,
        field_mask: str,
        http_client: Any = requests,
        grid_size: int = 3,
        grid_step_km: float = 2.0,
        radius_m: float = 2000.0,
        request_timeout_s: float = 15.0,
        inter_request_delay_s: float = 1.0,
        max_attempts: int = 2,
        sleep: Callable[[float], None] = time.sleep,
    ):
        if not api_key.strip():
            raise ValueError("GOOGLE_API_KEY mancante.")
        self.places_url = places_url
        self.http_client = http_client
        self.grid_size = grid_size
        self.grid_step_km = grid_step_km
        self.radius_m = radius_m
        self.request_timeout_s = request_timeout_s
        self.inter_request_delay_s = inter_request_delay_s
        self.max_attempts = max(1, max_attempts)
        self.sleep = sleep
        self.headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key.strip(),
            "X-Goog-FieldMask": field_mask,
        }

    def discover(
        self,
        query: DiscoveryQuery,
        *,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> DiscoveryBatch:
        candidates: list[TransientCandidate] = []
        grid = self._generate_grid(query.center_lat, query.center_lng)
        for index, (lat, lng) in enumerate(grid, 1):
            if on_progress:
                on_progress(index, len(grid))
            candidates.extend(self._fetch(query.text, query.language, lat, lng))
            if index < len(grid) and self.inter_request_delay_s > 0:
                self.sleep(self.inter_request_delay_s)
        return DiscoveryBatch(unique_candidates(candidates), self.attribution)

    def _generate_grid(self, center_lat: float, center_lng: float) -> list[tuple[float, float]]:
        lat_step = self.grid_step_km / 111.32
        cosine = max(abs(math.cos(math.radians(center_lat))), 0.01)
        lng_step = self.grid_step_km / (111.32 * cosine)
        offset = self.grid_size // 2
        return [
            (round(center_lat + i * lat_step, 6), round(center_lng + j * lng_step, 6))
            for i in range(-offset, offset + 1)
            for j in range(-offset, offset + 1)
        ]

    def _fetch(self, text: str, language: str, lat: float, lng: float) -> list[TransientCandidate]:
        payload = {
            "textQuery": text,
            "languageCode": language,
            "pageSize": 20,
            "locationBias": {
                "circle": {
                    "center": {"latitude": lat, "longitude": lng},
                    "radius": self.radius_m,
                }
            },
        }
        response = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                response = self.http_client.post(
                    self.places_url,
                    json=payload,
                    headers=self.headers,
                    timeout=self.request_timeout_s,
                )
                response.raise_for_status()
                break
            except requests.Timeout as exc:
                if attempt == self.max_attempts:
                    raise DiscoveryProviderError("provider_timeout") from exc
            except requests.HTTPError as exc:
                status = getattr(getattr(exc, "response", None), "status_code", 0)
                if attempt == self.max_attempts or (status and status < 500 and status != 429):
                    raise DiscoveryProviderError("provider_http_error") from exc
            except requests.RequestException as exc:
                if attempt == self.max_attempts:
                    raise DiscoveryProviderError("provider_unavailable") from exc
            except Exception as exc:
                raise DiscoveryProviderError("provider_protocol_error") from exc
            if self.inter_request_delay_s > 0:
                self.sleep(self.inter_request_delay_s)
        if response is None:
            raise DiscoveryProviderError("provider_unavailable")
        try:
            payload_data = response.json()
            raw_places = payload_data.get("places", [])
            if not isinstance(raw_places, list):
                raise TypeError("places")
        except Exception as exc:
            raise DiscoveryProviderError("provider_invalid_response") from exc
        collected_at = datetime.now(timezone.utc)
        result: list[TransientCandidate] = []
        for raw in raw_places:
            external_id = str(raw.get("id") or "").strip()
            if not external_id:
                continue
            display_name = str((raw.get("displayName") or {}).get("text") or "").strip()
            website_url = str(raw.get("websiteUri") or "").strip() or None
            result.append(
                TransientCandidate(
                    provider="google_places",
                    external_id=external_id,
                    display_name=display_name,
                    website_url=website_url,
                    collected_at=collected_at,
                    attribution=self.attribution,
                )
            )
        return result
