"""Storage-neutral lifecycle; every protected read verifies the signed token again."""
from typing import Protocol
from uuid import UUID

from src.application.license_clock import Clock
from src.domain.feature_licenses import LicenseClaims, LicenseError, LicenseScope, LicenseSummary, StoredGrant
from src.licensing.verification import LicenseVerifier


class LicenseRepository(Protocol):
    def read(self, scope: LicenseScope) -> StoredGrant | None: ...
    def activate(self, scope: LicenseScope, *, token: str, claims: LicenseClaims,
                 actor_id: UUID | None) -> None: ...
    def revoke(self, scope: LicenseScope, *, license_id: UUID, actor_id: UUID | None) -> None: ...


class LicenseService:
    def __init__(self, repository: LicenseRepository, verifier: LicenseVerifier, clock: Clock):
        self.repository, self.verifier, self.clock = repository, verifier, clock

    def import_license(self, scope, token, *, actor_id=None):
        claims = self.verifier.verify(token, scope=scope, now_epoch=self.clock.now_epoch())
        self.repository.activate(scope, token=token, claims=claims, actor_id=actor_id)
        return self.summary(scope)

    def revoke_license(self, scope, license_id, *, actor_id=None):
        self.repository.revoke(scope, license_id=license_id, actor_id=actor_id)
        return self.summary(scope)

    def require_valid(self, scope):
        grant = self.repository.read(scope)
        if grant is None:
            raise LicenseError("license_missing")
        if grant.revoked:
            raise LicenseError("license_revoked")
        claims = self.verifier.verify(grant.token, scope=scope, now_epoch=self.clock.now_epoch())
        if claims.license_id != grant.license_id:
            raise LicenseError("license_invalid")
        return claims

    def summary(self, scope):
        claims = None
        try:
            grant = self.repository.read(scope)
            if grant is None:
                return LicenseSummary(None, scope, "missing", None, None, ())
            claims = self.verifier.decode_verified(grant.token, scope=scope)
            if claims.license_id != grant.license_id:
                claims = None
                raise LicenseError("license_invalid")
            if grant.revoked:
                status = "revoked"
            else:
                self.verifier.verify(grant.token, scope=scope, now_epoch=self.clock.now_epoch())
                status = "valid"
        except LicenseError as error:
            status = error.code.removeprefix("license_")
        return LicenseSummary(claims.license_id if claims else None, scope, status,
                              claims.not_before if claims else None, claims.expires_at if claims else None,
                              claims.features if claims else ())
