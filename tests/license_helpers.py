from uuid import UUID

from src.domain.feature_licenses import AUDIENCE, LicenseClaims, LicenseScope, SubjectKind


def local_scope():
    return LicenseScope(UUID(int=1), SubjectKind.INSTALLATION, UUID(int=1))


def managed_scope():
    return LicenseScope(UUID(int=2), SubjectKind.WORKSPACE_USER, UUID(int=3), UUID(int=4))


def license_claims(*, scope=None, issued_at=0, not_before=0, expires_at=100,
                   features=("diagnostics.full",)):
    return LicenseClaims(1, "test-owner", AUDIENCE, UUID(int=5), issued_at, not_before,
                         expires_at, scope or local_scope(), features)
