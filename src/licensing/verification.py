"""Strict v1 JWS parsing followed by signature, scope, and temporal verification."""
import base64
import binascii
import json
import re
from uuid import UUID

import jwt

from src.domain.feature_licenses import (
    AUDIENCE, LicenseClaims, LicenseError, LicenseScope, SubjectKind, valid_epoch,
)
from src.licensing.catalog import FeatureCatalog
from src.licensing.trust import TrustedLicenseKeys

TOKEN_LIMIT = 16384
LICENSE_TYPE = "LH-FEATURE-LICENSE"
CLAIM_FIELDS = frozenset({"version", "iss", "aud", "jti", "iat", "nbf", "exp",
                          "installation_id", "subject_kind", "sub", "features"})


def strict_json(value: str | bytes):
    def pairs(items):
        result = {}
        for key, item in items:
            if key in result:
                raise ValueError("duplicate")
            result[key] = item
        return result
    def constant(_):
        raise ValueError("constant")
    try:
        return json.loads(value, object_pairs_hook=pairs, parse_constant=constant)
    except RecursionError:
        raise ValueError("nesting") from None


def claims_payload(claims: LicenseClaims) -> dict:
    """Canonical v1 payload shared with the private issuer."""
    data = dict(version=claims.version, iss=claims.issuer, aud=claims.audience,
                jti=str(claims.license_id), iat=claims.issued_at, nbf=claims.not_before,
                exp=claims.expires_at, installation_id=str(claims.scope.installation_id),
                subject_kind=claims.scope.subject_kind.value, sub=str(claims.scope.subject_id),
                features=list(claims.features))
    if claims.scope.workspace_id is not None:
        data["workspace_id"] = str(claims.scope.workspace_id)
    return data


class LicenseVerifier:
    def __init__(self, keys: TrustedLicenseKeys, catalog: FeatureCatalog):
        self.keys = keys
        self.catalog = catalog

    def decode_verified(self, token: str, *, scope: LicenseScope) -> LicenseClaims:
        try:
            if type(token) is not str or not 0 < len(token.encode("ascii")) <= TOKEN_LIMIT:
                raise ValueError()
            parts = token.split(".")
            if len(parts) != 3 or any(not re.fullmatch(r"[A-Za-z0-9_-]+", p) for p in parts):
                raise ValueError()
            def parse(part):
                raw = base64.b64decode(part + "=" * (-len(part) % 4), altchars=b"-_", validate=True)
                return strict_json(raw.decode("utf-8"))
            header, data = parse(parts[0]), parse(parts[1])
            if (type(header) is not dict or set(header) != {"typ", "alg", "kid"} or
                    header["typ"] != LICENSE_TYPE or header["alg"] != "EdDSA" or
                    type(header["kid"]) is not str or not 0 < len(header["kid"]) <= 128):
                raise ValueError()
            key = self.keys.resolve(header["kid"])
            jwt.decode(token, key, algorithms=["EdDSA"], audience=AUDIENCE, issuer=self.keys.issuer,
                       options={"verify_exp": False, "verify_iat": False, "verify_nbf": False,
                                "strict_aud": True, "require": list(CLAIM_FIELDS)})
            if type(data) is not dict:
                raise ValueError()
            kind = SubjectKind(data["subject_kind"])
            expected = CLAIM_FIELDS | ({"workspace_id"} if kind is SubjectKind.WORKSPACE_USER else set())
            if set(data) != expected or type(data["features"]) is not list:
                raise ValueError()
            for field in ("jti", "installation_id", "sub") + (("workspace_id",) if "workspace_id" in data else ()):
                if type(data[field]) is not str:
                    raise ValueError()
            parsed_scope = LicenseScope(UUID(data["installation_id"]), kind, UUID(data["sub"]),
                                        UUID(data["workspace_id"]) if "workspace_id" in data else None)
            claims = LicenseClaims(data["version"], data["iss"], data["aud"], UUID(data["jti"]),
                                   data["iat"], data["nbf"], data["exp"], parsed_scope,
                                   tuple(data["features"]))
            for feature in claims.features:
                self.catalog.get(feature)
        except LicenseError as error:
            if error.code == "license_invalid":
                raise
            raise LicenseError("license_invalid") from None
        except (ValueError, TypeError, KeyError, UnicodeError, binascii.Error, jwt.PyJWTError):
            raise LicenseError("license_invalid") from None
        if claims.scope != scope:
            raise LicenseError("license_subject_mismatch")
        return claims

    def verify(self, token: str, *, scope: LicenseScope, now_epoch: int) -> LicenseClaims:
        claims = self.decode_verified(token, scope=scope)
        if not valid_epoch(now_epoch):
            raise LicenseError("license_clock_regression")
        if now_epoch < claims.not_before:
            raise LicenseError("license_not_yet_valid")
        if now_epoch >= claims.expires_at:
            raise LicenseError("license_expired")
        return claims
