"""Operator-configured conservative call ceilings; not customer billing or provider tariffs."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Mapping

from .job_parameters import JobParameters
from .usage import normalized_cost, InvalidCost


class JobPriceError(ValueError):
    def __init__(self, code='job_price_invalid'):
        self.code = code
        super().__init__(code)


def _price(value):
    if value is None or value == '':
        return None
    if type(value) not in (str, int, float, Decimal):
        raise JobPriceError()
    try:
        raw = Decimal(str(value))
        if not raw.is_finite() or raw <= 0 or raw > 100000:
            raise JobPriceError()
        result = normalized_cost(raw)
        if result != raw or result <= 0:
            raise JobPriceError()
        return result
    except (InvalidOperation, InvalidCost, ValueError):
        raise JobPriceError() from None


@dataclass(frozen=True)
class JobQuote:
    version: str
    currency: str
    google_calls: int
    llm_calls: int
    google_request_ceiling: Decimal
    llm_request_ceiling: Decimal

    @property
    def total(self):
        return normalized_cost(self.google_calls * self.google_request_ceiling + self.llm_calls * self.llm_request_ceiling)

    def to_record(self):
        return {'version': self.version, 'currency': self.currency,
                'google_calls': self.google_calls, 'llm_calls': self.llm_calls,
                'google_request_ceiling': str(self.google_request_ceiling),
                'llm_request_ceiling': str(self.llm_request_ceiling)}


@dataclass(frozen=True)
class JobPricePolicy:
    version: str
    google_request_ceiling: Decimal | str | None = None
    llm_request_ceiling: Decimal | str | None = None
    currency: str = 'EUR'

    def __post_init__(self):
        if type(self.version) is not str or not self.version.strip() or len(self.version) > 80:
            raise JobPriceError()
        if type(self.currency) is not str or len(self.currency) != 3 or not self.currency.isascii() or not self.currency.isupper() or not self.currency.isalpha():
            raise JobPriceError()
        object.__setattr__(self, 'google_request_ceiling', _price(self.google_request_ceiling))
        object.__setattr__(self, 'llm_request_ceiling', _price(self.llm_request_ceiling))

    @classmethod
    def from_mapping(cls, values: Mapping[str, str]):
        return cls(version=values.get('LEADHUNTER_JOB_PRICE_VERSION', 'unconfigured'),
            google_request_ceiling=values.get('LEADHUNTER_JOB_GOOGLE_CALL_CEILING'),
            llm_request_ceiling=values.get('LEADHUNTER_JOB_LLM_CALL_CEILING'),
            currency=values.get('LEADHUNTER_JOB_COST_CURRENCY', 'EUR'))

    def quote(self, parsed: JobParameters) -> JobQuote:
        parameters = parsed.payload
        google_calls = 18 * len(parameters['keywords']) if parsed.kind.startswith('discover.') else 0
        if parsed.kind == 'discover.no_website':
            llm_calls = 0
        else:
            sites = parameters['max_leads'] if parsed.kind == 'discover.with_website' else len(parameters['urls']) if parsed.kind == 'audit.website' else 1
            llm_calls = 3 * sites * (parameters['max_pages'] + 1)
        if (google_calls and self.google_request_ceiling is None) or (llm_calls and self.llm_request_ceiling is None):
            raise JobPriceError('job_price_missing')
        return JobQuote(self.version, self.currency, google_calls, llm_calls,
                        self.google_request_ceiling or Decimal(0), self.llm_request_ceiling or Decimal(0))
