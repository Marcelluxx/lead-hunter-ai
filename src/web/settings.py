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
    jwt_private_key_file: Path
    jwt_public_key_file: Path
    jwt_issuer: str = "lead-hunter"
    jwt_audience: str = "lead-hunter-api"

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

    def private_key(self) -> bytes:
        return self.jwt_private_key_file.read_bytes()

    def public_key(self) -> bytes:
        return self.jwt_public_key_file.read_bytes()
