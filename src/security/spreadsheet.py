"""Spreadsheet output guards for untrusted lead and LLM values."""

from __future__ import annotations

from numbers import Number
from typing import Any


_FORMULA_PREFIXES = ("=", "+", "-", "@")
_LEADING_IGNORABLE = " \t\r\n"


def sanitize_spreadsheet_value(value: Any) -> Any:
    """Neutralize formula-like text while preserving intentional numeric cells.

    Excel hides a leading apostrophe while treating the remaining value as text.
    Numeric Python values are safe to preserve as numbers; booleans and all other
    values are serialized as explicit strings.
    """

    if value is None:
        return ""
    if isinstance(value, Number) and not isinstance(value, bool):
        return value

    text = str(value)
    candidate = text.lstrip(_LEADING_IGNORABLE)
    if candidate.startswith(_FORMULA_PREFIXES):
        return f"'{text}"
    return text


def is_text_cell(value: Any) -> bool:
    """Return whether an exported value must be forced to Excel string type."""

    return not (isinstance(value, Number) and not isinstance(value, bool))
