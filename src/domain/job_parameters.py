"""Strict, side-effect-free job admission; client parameters never confer authority."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from src.domain.discovery import ensure_provider_payload_absent, ProviderPayloadError
from src.security.url_policy import SafeUrlPolicy, UrlPolicyError


class JobParameterError(ValueError):
    def __init__(self, code='job_parameters_invalid'):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class JobParameters:
    kind: str
    _encoded: str = field(repr=False)
    required_features: tuple[str, ...] = ()

    @property
    def payload(self) -> dict:
        return json.loads(self._encoded)


class _Base(BaseModel):
    model_config = ConfigDict(strict=True, extra='forbid', allow_inf_nan=False)
    schema_version: Literal[1] = 1
    max_pages: Annotated[int, Field(ge=1, le=20)] = 5
    token_mode: Literal['high_fidelity', 'optimized'] = 'high_fidelity'

    @field_validator('schema_version', mode='before')
    @classmethod
    def exact_version(cls, value):
        if type(value) is not int:
            raise ValueError('version')
        return value


class _Rating(BaseModel):
    model_config = ConfigDict(strict=True, extra='forbid', allow_inf_nan=False)
    min_rating: Annotated[float, Field(ge=0, le=5)] = 3.9
    max_reviews: Annotated[int, Field(ge=1, le=2147483647)] = 100


class _Discovery(_Base):
    lat: Annotated[float, Field(ge=-90, le=90)]
    lng: Annotated[float, Field(ge=-180, le=180)]
    keywords: Annotated[list[Annotated[str, Field(min_length=1, max_length=100)]], Field(min_length=1, max_length=5)]
    max_leads: Annotated[int, Field(ge=1, le=100)] = 20
    rating_filters: _Rating | None = None

    @field_validator('keywords', mode='before')
    @classmethod
    def strip_keywords(cls, value):
        if type(value) is not list or not all(type(item) is str for item in value):
            raise ValueError('keywords')
        return [item.strip() for item in value]

    @field_validator('keywords')
    @classmethod
    def unique_keywords(cls, value):
        seen, output = set(), []
        for item in value:
            if item.casefold() not in seen:
                seen.add(item.casefold()); output.append(item)
        return output


def _url(value):
    if type(value) is not str:
        raise ValueError('url')
    return SafeUrlPolicy().validate_syntax(value).normalized_url


class _Audit(_Base):
    urls: Annotated[list[str], Field(min_length=1, max_length=20)]

    @field_validator('urls')
    @classmethod
    def normalize_urls(cls, value):
        return list(dict.fromkeys(_url(item) for item in value))

    @model_validator(mode='after')
    def bounded_work(self):
        if len(self.urls) * self.max_pages > 200:
            raise ValueError('work')
        return self


class _Diagnostic(_Base):
    url: str
    retention_hours: Annotated[int, Field(ge=1, le=168)] = 24

    @field_validator('url')
    @classmethod
    def normalize_url(cls, value):
        return _url(value)


_KINDS = {'discover.no_website': _Discovery, 'discover.with_website': _Discovery,
          'audit.website': _Audit, 'diagnostic.website': _Diagnostic}


def parse_job_parameters(kind: str, parameters: dict) -> JobParameters:
    if type(kind) is not str or kind not in _KINDS:
        raise JobParameterError('job_kind_unsupported')
    if type(parameters) is not dict:
        raise JobParameterError()
    try:
        ensure_provider_payload_absent(parameters)
        model = _KINDS[kind].model_validate(parameters)
        if kind == 'discover.with_website' and model.max_leads * model.max_pages > 200:
            raise ValueError('work')
        payload = model.model_dump(mode='json')
        features = ('diagnostics.full',) if kind == 'diagnostic.website' else ()
        if kind.startswith('discover.') and model.rating_filters is not None:
            features = ('discovery.rating_filters',)
        return JobParameters(kind, json.dumps(payload, ensure_ascii=False, allow_nan=False), features)
    except ProviderPayloadError:
        raise JobParameterError('provider_payload_not_allowed') from None
    except (ValidationError, ValueError, TypeError, RecursionError, UrlPolicyError):
        raise JobParameterError() from None
