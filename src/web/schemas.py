from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=1024)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class MfaCodeRequest(BaseModel):
    code: str = Field(min_length=6, max_length=64)


class MfaEnrollmentResponse(BaseModel):
    provisioning_uri: str
    recovery_codes: list[str]


class SecretWriteRequest(BaseModel):
    value: str = Field(min_length=1, max_length=8192)


class SecretStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    provider: str
    fingerprint: str
    updated_at: Any


class JobCreateRequest(BaseModel):
    kind: str = Field(min_length=1, max_length=80)
    parameters: dict[str, Any] = Field(default_factory=dict)
    estimated_cost: Decimal = Field(ge=0)


class JobResponse(BaseModel):
    id: uuid.UUID
    state: str
    created: bool | None = None


class BudgetResponse(BaseModel):
    hard_limit: Decimal
    spent: Decimal
    reserved: Decimal
    warning: bool


class BudgetOverrideRequest(BaseModel):
    hard_limit: Decimal = Field(ge=0)
    reason: str = Field(min_length=1, max_length=500)
