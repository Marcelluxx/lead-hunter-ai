"""Locally configured public keys; tokens cannot nominate remote key sources."""
from types import MappingProxyType
from typing import Mapping
import re

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from src.domain.feature_licenses import LicenseError


class TrustedLicenseKeys:
    def __init__(self, issuer: str, public_keys: Mapping[str, bytes]):
        if type(issuer) is not str or not issuer or len(issuer) > 200:
            raise LicenseError("license_invalid")
        keys = {}
        try:
            for kid, pem in public_keys.items():
                if type(kid) is not str or not kid or len(kid) > 128:
                    raise ValueError()
                # The parser otherwise accepts extra PEM blocks, including private keys.
                if (type(pem) is not bytes or not re.fullmatch(
                        rb"\s*-----BEGIN PUBLIC KEY-----\r?\n[A-Za-z0-9+/=\r\n]+-----END PUBLIC KEY-----\s*", pem)):
                    raise ValueError()
                key = serialization.load_pem_public_key(pem)
                if not isinstance(key, Ed25519PublicKey):
                    raise ValueError()
                keys[kid] = key
        except (TypeError, ValueError, AttributeError):
            raise LicenseError("license_invalid") from None
        self.issuer = issuer
        self._keys = MappingProxyType(keys)

    def resolve(self, kid: str) -> Ed25519PublicKey:
        try:
            return self._keys[kid]
        except (KeyError, TypeError):
            raise LicenseError("license_invalid") from None
