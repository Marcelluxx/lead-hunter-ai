"""Validated identifiers; provider content cannot enter the reference export."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
import re

from src.domain.discovery import TransientCandidate

_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,499}', re.ASCII)
_MAX_INPUT = 10000
_ERROR_CODES = frozenset({'reference_export_invalid', 'reference_export_empty',
                          'reference_export_limit', 'reference_export_write_failed'})


class ReferenceExportError(Exception):
    def __init__(self, code: str):
        self.code = code if code in _ERROR_CODES else 'reference_export_invalid'
        super().__init__(self.code)


def _validate_id(value: object) -> None:
    if type(value) is not str or _ID.fullmatch(value) is None:
        raise ReferenceExportError('reference_export_invalid')


@dataclass(frozen=True, slots=True)
class GooglePlaceReference:
    place_id: str

    def __post_init__(self) -> None:
        _validate_id(self.place_id)


def normalize_references(references: Iterable[GooglePlaceReference]) -> tuple[GooglePlaceReference, ...]:
    try:
        iterator = iter(references)
    except TypeError:
        raise ReferenceExportError('reference_export_invalid') from None
    unique: dict[str, GooglePlaceReference] = {}
    for count, reference in enumerate(iterator, 1):
        if count > _MAX_INPUT:
            raise ReferenceExportError('reference_export_limit')
        if type(reference) is not GooglePlaceReference:
            raise ReferenceExportError('reference_export_invalid')
        _validate_id(reference.place_id)
        unique.setdefault(reference.place_id, reference)
    if not unique:
        raise ReferenceExportError('reference_export_empty')
    return tuple(unique.values())


def project_google_place_references(candidates: Iterable[TransientCandidate]) -> tuple[GooglePlaceReference, ...]:
    def selected():
        for candidate in candidates:
            if type(candidate) is not TransientCandidate:
                raise ReferenceExportError('reference_export_invalid')
            if candidate.provider == 'google_places' and candidate.website_url is None:
                yield GooglePlaceReference(candidate.external_id)
    try:
        return normalize_references(selected())
    except ReferenceExportError as exc:
        if exc.code == 'reference_export_empty':
            return ()
        raise
