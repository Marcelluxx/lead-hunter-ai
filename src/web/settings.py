from __future__ import annotations

import base64
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ServerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LEADHUNTER_",
        env_file=".env",
        extra="ignore",
    )

    database_url: str
    redis_url: str = "redis://localhost:6379/0"
    master_key_base64: str
    suppression_hmac_key_base64: str
    jwt_private_key_file: Path
    jwt_public_key_file: Path
    jwt_issuer: str = "lead-hunter"
    jwt_audience: str = "lead-hunter-api"
    license_issuer: str = "lead-hunter-owner"
    license_trust_file: Path | None = None
    license_state_dir: Path = Path(".leadhunter-state")
    installation_id: str | None = None

    @field_validator("license_trust_file", mode="before")
    @classmethod
    def optional_license_trust_path(cls, value):
        return None if value == "" else value

    def license_configuration(self):
        from uuid import UUID
        from ..licensing.settings import LicenseSettings
        from ..settings import SettingsError
        try:
            settings = LicenseSettings(self.license_issuer, self.license_trust_file,
                self.license_state_dir.resolve(), UUID(self.installation_id) if self.installation_id else None)
            settings.validate_server()
            return settings
        except ValueError:
            raise SettingsError("Configurazione licenze server non valida.") from None

    @field_validator("database_url")
    @classmethod
    def production_database(cls, value: str) -> str:
        if not value.startswith("postgresql+psycopg://"):
            raise ValueError("Il server richiede PostgreSQL tramite psycopg.")
        return value

    def master_key(self) -> bytes:
        key = base64.urlsafe_b64decode(self.master_key_base64.encode("ascii"))
        if len(key) != 32:
            raise ValueError("LEADHUNTER_MASTER_KEY_BASE64 deve decodificare 32 byte.")
        return key

    def suppression_hmac_key(self) -> bytes:
        key = base64.urlsafe_b64decode(self.suppression_hmac_key_base64.encode("ascii"))
        if len(key) != 32:
            raise ValueError(
                "LEADHUNTER_SUPPRESSION_HMAC_KEY_BASE64 deve decodificare 32 byte."
            )
        return key

    def private_key(self) -> bytes:
        return self.jwt_private_key_file.read_bytes()

    def public_key(self) -> bytes:
        return self.jwt_public_key_file.read_bytes()
