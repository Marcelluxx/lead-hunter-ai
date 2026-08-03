"""Explicit, HTTPS-only approximate IP geolocation."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import urlsplit

import requests

from .url_policy import SafeUrlPolicy, UrlPolicyError


DEFAULT_GEOLOCATION_ENDPOINT = "https://ipwho.is/"
MAX_RESPONSE_BYTES = 32_768


class GeolocationError(RuntimeError):
    """A safe, user-displayable geolocation failure."""


@dataclass(frozen=True)
class ApproximateLocation:
    latitude: float
    longitude: float

    def to_public_dict(self) -> dict[str, float]:
        return {"lat": self.latitude, "lng": self.longitude}


def configured_geolocation_endpoint() -> str:
    """Return the operator-configured provider without exposing credentials."""

    return os.getenv("IP_GEOLOCATION_URL", DEFAULT_GEOLOCATION_ENDPOINT).strip()


def lookup_approximate_location(
    *,
    endpoint: str | None = None,
    http_get: Callable[..., Any] = requests.get,
    url_policy: SafeUrlPolicy | None = None,
) -> ApproximateLocation:
    """Look up the caller connection only after an explicit UI action."""

    target = endpoint or configured_geolocation_endpoint()
    parsed = urlsplit(target)
    if parsed.scheme.lower() != "https":
        raise GeolocationError("Il provider di geolocalizzazione deve usare HTTPS.")
    if not parsed.hostname:
        raise GeolocationError("Provider di geolocalizzazione non valido.")

    policy = url_policy or SafeUrlPolicy(allowed_ports=(443,))
    try:
        decision = policy.validate(target, allowed_hosts={parsed.hostname})
    except UrlPolicyError as exc:
        raise GeolocationError("Provider di geolocalizzazione non raggiungibile in sicurezza.") from exc

    try:
        response = http_get(
            decision.normalized_url,
            params={"fields": "success,latitude,longitude"},
            headers={
                "Accept": "application/json",
                "User-Agent": "LeadHunter/3 geolocation-opt-in",
            },
            timeout=(2, 4),
            allow_redirects=False,
        )
        if response.status_code != 200:
            raise GeolocationError("Il provider non ha restituito una posizione valida.")
        body = getattr(response, "content", b"")
        if body and len(body) > MAX_RESPONSE_BYTES:
            raise GeolocationError("Risposta del provider troppo grande.")
        payload = response.json()
    except GeolocationError:
        raise
    except (requests.RequestException, ValueError, TypeError) as exc:
        raise GeolocationError("Geolocalizzazione temporaneamente non disponibile.") from exc

    if not isinstance(payload, dict) or payload.get("success") is not True:
        raise GeolocationError("Il provider non ha restituito una posizione valida.")
    latitude = _validated_coordinate(payload.get("latitude"), -90, 90)
    longitude = _validated_coordinate(payload.get("longitude"), -180, 180)
    return ApproximateLocation(latitude=latitude, longitude=longitude)


def _validated_coordinate(value: Any, minimum: float, maximum: float) -> float:
    if isinstance(value, bool):
        raise GeolocationError("Coordinate ricevute non valide.")
    try:
        coordinate = float(value)
    except (TypeError, ValueError) as exc:
        raise GeolocationError("Coordinate ricevute non valide.") from exc
    if not minimum <= coordinate <= maximum:
        raise GeolocationError("Coordinate ricevute fuori intervallo.")
    return coordinate
