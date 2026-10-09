"""Encrypted Ed25519 key generation, with exclusive file creation."""
import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.domain.feature_licenses import LicenseError


def write_new_file(path: Path, data: bytes):
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def generate_issuer_keys(*, private_path: Path, public_path: Path, passphrase: bytes) -> None:
    private_created = False
    try:
        if not passphrase or private_path.resolve() == public_path.resolve():
            raise ValueError()
        key = Ed25519PrivateKey.generate()
        encrypted = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                       serialization.BestAvailableEncryption(passphrase))
        public = key.public_key().public_bytes(serialization.Encoding.PEM,
                                               serialization.PublicFormat.SubjectPublicKeyInfo)
        write_new_file(private_path, encrypted)
        private_created = True
        write_new_file(public_path, public)
    except (ValueError, TypeError, OSError):
        if private_created:
            private_path.unlink(missing_ok=True)
        raise LicenseError("license_invalid") from None
