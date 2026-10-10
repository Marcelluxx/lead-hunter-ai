"""Signed grants with explicit timezone-aware second-resolution dates."""
from datetime import datetime

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.domain.feature_licenses import LicenseError, valid_epoch
from src.licensing.catalog import FeatureCatalog
from src.licensing.trust import TrustedLicenseKeys
from src.licensing.verification import LicenseVerifier, claims_payload, LICENSE_TYPE
from tools.license_issuer.keys import write_new_file


def parse_license_date(value: str) -> int:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None or parsed.microsecond:
            raise ValueError()
        epoch = int(parsed.timestamp())
        if not valid_epoch(epoch):
            raise ValueError()
        return epoch
    except (ValueError, TypeError, OverflowError, OSError):
        raise LicenseError("license_invalid") from None


def issue_license(claims, *, private_path, passphrase, kid, output_path) -> None:
    try:
        if not passphrase:
            raise ValueError()
        private = serialization.load_pem_private_key(private_path.read_bytes(), password=passphrase)
        if not isinstance(private, Ed25519PrivateKey):
            raise ValueError()
        public = private.public_key().public_bytes(serialization.Encoding.PEM,
                                                   serialization.PublicFormat.SubjectPublicKeyInfo)
        verifier = LicenseVerifier(TrustedLicenseKeys(claims.issuer, {kid: public}), FeatureCatalog())
        token = jwt.encode(claims_payload(claims), private, algorithm="EdDSA",
                           headers={"typ": LICENSE_TYPE, "kid": kid})
        verifier.decode_verified(token, scope=claims.scope)
        write_new_file(output_path, token.encode("ascii"))
    except (ValueError, TypeError, OSError, jwt.PyJWTError):
        raise LicenseError("license_invalid") from None
