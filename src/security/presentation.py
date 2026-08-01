"""Safe presentation helpers for values rendered by the Streamlit GUI."""

from __future__ import annotations

import html
import re
from typing import Any


_CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_STATUS_CLASSES = {
    "idle": "status-idle",
    "running": "status-running",
    "done": "status-success",
    "fail": "status-fail",
}
_STATUS_ICONS = {
    "done": "✅",
    "fail": "❌",
    "running": "🛰️",
}


def escape_dynamic_html(value: Any) -> str:
    """Escape a dynamic value before interpolating it into trusted static HTML."""

    return html.escape(str(value), quote=True)


def build_keyword_card_html(
    keyword: Any,
    count: Any,
    status: str,
    footer: Any,
) -> str:
    """Build the keyword card while treating every caller value as untrusted."""

    normalized_status = "fail" if status == "done" and count == 0 else status
    color_class = _STATUS_CLASSES.get(normalized_status, "status-idle")
    icon = _STATUS_ICONS.get(normalized_status, "⏳")

    return f"""
        <div class="keyword-card {color_class}">
            <div class="card-title">{escape_dynamic_html(keyword)}</div>
            <div class="card-value">{escape_dynamic_html(count)}</div>
            <div class="card-footer">{icon} {escape_dynamic_html(footer)}</div>
        </div>
    """


def build_phase_card_html(icon: Any, text: Any, elapsed: Any = "") -> str:
    """Build the phase card with escaped icon, text and elapsed time."""

    safe_elapsed = escape_dynamic_html(elapsed)
    time_html = (
        f'<span class="phase-time">⏱️ {safe_elapsed}</span>'
        if safe_elapsed
        else ""
    )
    return f"""
        <div class="phase-card">
            <span class="phase-icon">{escape_dynamic_html(icon)}</span>
            <span class="phase-text">{escape_dynamic_html(text)}</span>
            {time_html}
        </div>
    """


def normalize_log_message(value: Any, max_length: int = 2_000) -> str:
    """Return bounded plain text suitable for a native Streamlit text widget."""

    text = _CONTROL_CHARACTERS.sub("", str(value))
    return text[:max_length]
