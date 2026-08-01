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


class PrivacyPolicyRequest(BaseModel):
    purpose: str = Field(min_length=1, max_length=500)
    legal_basis: str = Field(min_length=1, max_length=500)
    privacy_contact: str = Field(min_length=3, max_length=320)
    market: str = Field(default="IT_EU", pattern="^IT_EU$")
    named_contact_retention_days: int = Field(default=90, ge=1, le=90)
    policy_version: str = Field(default="it-eu-b2b-v1", min_length=1, max_length=80)
    enabled: bool = True


class PrivacyPolicyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    workspace_id: uuid.UUID
    purpose: str
    legal_basis: str
    privacy_contact: str
    market: str
    named_contact_retention_days: int
    policy_version: str
    enabled: bool


class SuppressionRequest(BaseModel):
    kind: str = Field(pattern="^(email|phone)$")
    value: str = Field(min_length=3, max_length=500)
    scope: str = Field(default="workspace", pattern="^(workspace|global)$")
    reason: str = Field(default="opposition", min_length=1, max_length=80)


class DataSubjectRequestBody(BaseModel):
    request_id: uuid.UUID
    request_kind: str = Field(pattern="^(access|rectification|erasure|opposition)$")
    identifier_kind: str = Field(pattern="^(email|phone)$")
    value: str = Field(min_length=3, max_length=500)
    replacement_value: str | None = Field(default=None, min_length=3, max_length=500)
    suppression_scope: str = Field(default="global", pattern="^(workspace|global)$")


class DataSubjectRequestResponse(BaseModel):
    request_id: uuid.UUID
    status: str
    deleted_count: int = 0
    data: list[dict[str, str]] = Field(default_factory=list)
