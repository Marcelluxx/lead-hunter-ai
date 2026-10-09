"""Immutable licensing contracts; no storage, UI, or provider dependencies."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from uuid import UUID

from src.domain.identity import Permission

FEATURE_IDS = frozenset({"export.no_website", "discovery.rating_filters", "diagnostics.full"})
AUDIENCE = "lead-hunter-feature-licenses"
MAX_EPOCH = 253402300799
ERROR_CODES = frozenset({
    "license_missing", "license_invalid", "license_expired", "license_not_yet_valid",
    "license_subject_mismatch", "license_revoked", "license_clock_regression",
    "feature_not_granted", "feature_unavailable", "feature_role_denied",
    "license_storage_unavailable",
})


class LicenseError(Exception):
    def __init__(self, code: str):
        self.code = code if code in ERROR_CODES else "license_invalid"
        super().__init__(self.code)


class SubjectKind(str, Enum):
    INSTALLATION = "installation"
    WORKSPACE_USER = "workspace_user"


class FeatureAction(str, Enum):
    EXECUTE = "execute"
    VIEW = "view"


def valid_epoch(value: object) -> bool:
    return type(value) is int and 0 <= value <= MAX_EPOCH


@dataclass(frozen=True)
class LicenseScope:
    installation_id: UUID
    subject_kind: SubjectKind
    subject_id: UUID
    workspace_id: UUID | None = None

    def __post_init__(self):
        if (not isinstance(self.installation_id, UUID) or
                not isinstance(self.subject_id, UUID) or
                not isinstance(self.subject_kind, SubjectKind)):
            raise LicenseError("license_invalid")
        if self.subject_kind is SubjectKind.INSTALLATION:
            if self.subject_id != self.installation_id or self.workspace_id is not None:
                raise LicenseError("license_invalid")
        elif not isinstance(self.workspace_id, UUID):
            raise LicenseError("license_invalid")


@dataclass(frozen=True)
class LicenseClaims:
    version: int
    issuer: str
    audience: str
    license_id: UUID
    issued_at: int
    not_before: int
    expires_at: int
    scope: LicenseScope
    features: tuple[str, ...]

    def __post_init__(self):
        if (type(self.version) is not int or self.version != 1 or
                type(self.issuer) is not str or not self.issuer or len(self.issuer) > 200 or
                self.audience != AUDIENCE or not isinstance(self.license_id, UUID) or
                not isinstance(self.scope, LicenseScope) or
                not all(valid_epoch(v) for v in (self.issued_at, self.not_before, self.expires_at))):
            raise LicenseError("license_invalid")
        if not self.issued_at <= self.not_before < self.expires_at:
            raise LicenseError("license_invalid")
        if (type(self.features) is not tuple or not self.features or
                any(type(f) is not str or f not in FEATURE_IDS for f in self.features) or
                len(set(self.features)) != len(self.features)):
            raise LicenseError("license_invalid")


@dataclass(frozen=True)
class StoredGrant:
    token: str = field(repr=False)
    license_id: UUID
    revoked: bool


@dataclass(frozen=True)
class LicenseSummary:
    license_id: UUID | None
    scope: LicenseScope
    license_status: str
    not_before: int | None
    expires_at: int | None
    features: tuple[str, ...]


@dataclass(frozen=True)
class FeatureDefinition:
    feature_id: str
    label: str
    module_status: str
    execute_permissions: tuple[Permission, ...]
    view_permissions: tuple[Permission, ...]
    execute_mfa: bool = False
    view_mfa: bool = False


@dataclass(frozen=True)
class FeatureContext:
    scope: LicenseScope
    permissions: frozenset[Permission]
    mfa_verified: bool
    principal_active: bool


@dataclass(frozen=True)
class FeatureStatus:
    feature_id: str
    label: str
    granted: bool
    module_status: str
    license_status: str
    expires_at: int | None
