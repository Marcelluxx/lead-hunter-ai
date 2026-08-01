"""Privacy controls for logs and short-lived diagnostic artifacts."""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any


_REDACTIONS = (
    (
        re.compile(r"(?i)\bbearer\s+[a-z0-9._~+/=-]+"),
        "Bearer [REDACTED_TOKEN]",
    ),
    (
        re.compile(
            r"(?i)\b(api[_-]?key|access[_-]?token|refresh[_-]?token|token|secret|password)"
            r"(\s*[:=]\s*)([^\s&,;]+)"
        ),
        r"\1\2[REDACTED_SECRET]",
    ),
    (
        re.compile(r"(?i)([?&](?:key|api_key|token|access_token)=)[^&#\s]+"),
        r"\1[REDACTED_SECRET]",
    ),
    (
        re.compile(r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+"),
        "[REDACTED_EMAIL]",
    ),
    (
        re.compile(
            r"(?<![\d.])(?:25[0-5]|2[0-4]\d|1?\d?\d)"
            r"(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3}(?![\d.])"
        ),
        "[REDACTED_IP]",
    ),
)


def redact_sensitive_text(value: Any, max_length: int = 4_000) -> str:
    """Redact common secrets and personal identifiers from diagnostic text."""

    text = str(value)
    for pattern, replacement in _REDACTIONS:
        text = pattern.sub(replacement, text)
    return text[:max_length]


def purge_expired_diagnostic_files(
    root: str | Path,
    retention_hours: int,
    *,
    now: float | None = None,
) -> int:
    """Delete expired regular files contained by one diagnostic directory.

    Symlinks are never followed or deleted. Directories are retained so an
    operator can inspect the expected artifact layout.
    """

    if retention_hours < 1:
        raise ValueError("retention_hours must be at least 1")

    root_path = Path(root).resolve()
    if not root_path.exists():
        return 0
    if not root_path.is_dir():
        raise ValueError("diagnostic root must be a directory")

    cutoff = (time.time() if now is None else now) - (retention_hours * 3600)
    removed = 0
    for candidate in root_path.rglob("*"):
        if candidate.is_symlink() or not candidate.is_file():
            continue
        resolved = candidate.resolve()
        if root_path not in resolved.parents:
            continue
        if resolved.stat().st_mtime < cutoff:
            resolved.unlink()
            removed += 1
    return removed
