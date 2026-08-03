"""Runtime settings loaded explicitly by application entry points."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping
from urllib.parse import urlsplit

from dotenv import load_dotenv

from .config import (
    DEFAULT_LLM_MODEL,
    DEFAULT_LLM_MODEL_FREE,
    DEFAULT_TOKEN_MODE,
    GOOGLE_GEOCODING_URL,
    GOOGLE_PLACES_V1_URL,
    OPENROUTER_BASE_URL,
)


class SettingsError(ValueError):
    """Base class for safe runtime configuration errors."""


class SettingsValidationError(SettingsError):
    """Raised at an explicit application boundary when settings are incomplete."""

    def __init__(self, missing: tuple[str, ...]):
        self.missing = missing
        super().__init__(f"Configurazione mancante: {', '.join(missing)}")


class SettingsValueError(SettingsError):
    """Raised when a configured value is outside the supported boundary."""


@dataclass(frozen=True)
class ApplicationSettings:
    google_api_key: str = ""
    openrouter_api_key: str = ""
    google_places_url: str = GOOGLE_PLACES_V1_URL
    google_geocoding_url: str = GOOGLE_GEOCODING_URL
    openrouter_base_url: str = OPENROUTER_BASE_URL
    llm_model: str = DEFAULT_LLM_MODEL
    llm_model_free: str = DEFAULT_LLM_MODEL_FREE
    token_mode: str = DEFAULT_TOKEN_MODE

    @classmethod
    def from_mapping(cls, values: Mapping[str, str]) -> "ApplicationSettings":
        return cls(
            google_api_key=_value(values, "GOOGLE_API_KEY"),
            openrouter_api_key=_value(values, "OPENROUTER_API_KEY"),
            google_places_url=_https_url(
                values, "GOOGLE_PLACES_V1_URL", GOOGLE_PLACES_V1_URL
            ),
            google_geocoding_url=_https_url(
                values, "GOOGLE_GEOCODING_URL", GOOGLE_GEOCODING_URL
            ),
            openrouter_base_url=_https_url(
                values, "OPENROUTER_BASE_URL", OPENROUTER_BASE_URL
            ),
            llm_model=_value(values, "LLM_MODEL", DEFAULT_LLM_MODEL),
            llm_model_free=_value(
                values, "LLM_MODEL_FREE", DEFAULT_LLM_MODEL_FREE
            ),
            token_mode=_choice(
                values,
                "TOKEN_MODE",
                DEFAULT_TOKEN_MODE,
                {"high_fidelity", "optimized"},
            ),
        )

    @classmethod
    def from_environment(cls) -> "ApplicationSettings":
        load_dotenv()
        return cls.from_mapping(os.environ)

    def require_google(self) -> None:
        self._require(("GOOGLE_API_KEY", self.google_api_key))

    def require_openrouter(self) -> None:
        self._require(("OPENROUTER_API_KEY", self.openrouter_api_key))

    def require_pipeline(self, mode: str) -> None:
        required = [("GOOGLE_API_KEY", self.google_api_key)]
        if mode == "with_website":
            required.append(("OPENROUTER_API_KEY", self.openrouter_api_key))
        self._require(*required)

    @staticmethod
    def _require(*required: tuple[str, str]) -> None:
        missing = tuple(name for name, value in required if not value)
        if missing:
            raise SettingsValidationError(missing)


def _value(values: Mapping[str, str], name: str, default: str = "") -> str:
    value = values.get(name, default)
    return value.strip() if isinstance(value, str) else default


def _choice(
    values: Mapping[str, str],
    name: str,
    default: str,
    allowed: set[str],
) -> str:
    value = _value(values, name, default)
    if value not in allowed:
        raise SettingsValueError(
            f"{name} non valido; valori consentiti: {', '.join(sorted(allowed))}"
        )
    return value


def _https_url(values: Mapping[str, str], name: str, default: str) -> str:
    value = _value(values, name, default)
    parsed = urlsplit(value)
    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise SettingsValueError(f"{name} deve essere un URL HTTPS senza credenziali.")
    return value
