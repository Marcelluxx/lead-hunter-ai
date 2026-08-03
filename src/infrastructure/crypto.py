"""Cryptographic primitives for secrets, tokens and opaque credentials."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
    load_pem_private_key,
    load_pem_public_key,
)
from pwdlib import PasswordHash


class SecretDecryptionError(ValueError):
    pass


class TokenValidationError(ValueError):
    pass


class SecretCipher:
    VERSION = "v1"

    def __init__(self, key: bytes):
        if len(key) != 32:
            raise ValueError("La master key AES deve contenere esattamente 32 byte.")
        self._key = key
        self._cipher = AESGCM(key)

    @staticmethod
    def generate_key() -> bytes:
        return AESGCM.generate_key(bit_length=256)

    @classmethod
    def from_base64(cls, encoded: str) -> "SecretCipher":
        try:
            key = base64.urlsafe_b64decode(encoded.encode("ascii"))
        except Exception as exc:
            raise ValueError("Master key non valida.") from exc
        return cls(key)

    def encrypt(self, plaintext: str, *, associated_data: str) -> str:
        if not plaintext:
            raise ValueError("Il segreto non puo essere vuoto.")
        nonce = secrets.token_bytes(12)
        ciphertext = self._cipher.encrypt(
            nonce,
            plaintext.encode("utf-8"),
            associated_data.encode("utf-8"),
        )
        payload = base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")
        return f"{self.VERSION}:{payload}"

    def decrypt(self, payload: str, *, associated_data: str) -> str:
        try:
            version, encoded = payload.split(":", 1)
            if version != self.VERSION:
                raise ValueError("version")
            raw = base64.urlsafe_b64decode(encoded.encode("ascii"))
            plaintext = self._cipher.decrypt(
                raw[:12], raw[12:], associated_data.encode("utf-8")
            )
            return plaintext.decode("utf-8")
        except Exception as exc:
            raise SecretDecryptionError("Segreto non autenticabile.") from exc

    def fingerprint(self, value: str) -> str:
        return hmac.new(
            self._key,
            value.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()[:32]


class PasswordService:
    def __init__(self):
        self._hasher = PasswordHash.recommended()
        self._dummy_hash = self._hasher.hash(secrets.token_urlsafe(32))

    def hash(self, password: str) -> str:
        if len(password) < 12:
            raise ValueError("La password deve contenere almeno 12 caratteri.")
        return self._hasher.hash(password)

    def verify(self, password: str, encoded: str | None) -> bool:
        try:
            return self._hasher.verify(password, encoded or self._dummy_hash)
        except Exception:
            self._hasher.verify(password, self._dummy_hash)
            return False


def hash_opaque_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_opaque_token() -> str:
    return secrets.token_urlsafe(48)


@dataclass(frozen=True)
class TokenClaims:
    user_id: str
    session_id: str
    session_version: int
    mfa_verified: bool


class AccessTokenService:
    def __init__(
        self,
        *,
        private_key_pem: bytes,
        public_key_pem: bytes,
        issuer: str,
        audience: str,
        lifetime: timedelta = timedelta(minutes=15),
    ):
        self._private_key = load_pem_private_key(private_key_pem, password=None)
        self._public_key = load_pem_public_key(public_key_pem)
        if not isinstance(self._private_key, Ed25519PrivateKey) or not isinstance(
            self._public_key, Ed25519PublicKey
        ):
            raise ValueError("Le chiavi JWT devono essere Ed25519.")
        self._issuer = issuer
        self._audience = audience
        self._lifetime = lifetime

    @staticmethod
    def generate_key_pair() -> tuple[bytes, bytes]:
        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        return (
            private_key.private_bytes(
                Encoding.PEM,
                PrivateFormat.PKCS8,
                NoEncryption(),
            ),
            public_key.public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo),
        )

    def issue(
        self,
        *,
        user_id: str,
        session_id: str,
        session_version: int,
        mfa_verified: bool,
        now: datetime | None = None,
    ) -> str:
        issued_at = now or datetime.now(timezone.utc)
        payload: dict[str, Any] = {
            "sub": user_id,
            "sid": session_id,
            "sv": session_version,
            "mfa": mfa_verified,
            "iss": self._issuer,
            "aud": self._audience,
            "iat": issued_at,
            "nbf": issued_at,
            "exp": issued_at + self._lifetime,
            "jti": secrets.token_urlsafe(16),
        }
        return jwt.encode(payload, self._private_key, algorithm="EdDSA")

    def decode(self, token: str) -> TokenClaims:
        try:
            payload = jwt.decode(
                token,
                self._public_key,
                algorithms=["EdDSA"],
                issuer=self._issuer,
                audience=self._audience,
                options={"require": ["exp", "iat", "nbf", "iss", "aud", "sub", "sid"]},
            )
            return TokenClaims(
                user_id=str(payload["sub"]),
                session_id=str(payload["sid"]),
                session_version=int(payload["sv"]),
                mfa_verified=bool(payload.get("mfa", False)),
            )
        except Exception as exc:
            raise TokenValidationError("Access token non valido.") from exc
