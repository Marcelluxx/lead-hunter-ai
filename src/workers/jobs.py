"""Worker-side validation for UUID-loaded job data."""

from __future__ import annotations

from typing import Any

from ..domain.discovery import ensure_provider_payload_absent


def validate_persistent_job_parameters(parameters: dict[str, Any]) -> None:
    """Defense in depth: provider response documents never enter worker jobs."""
    ensure_provider_payload_absent(parameters)
