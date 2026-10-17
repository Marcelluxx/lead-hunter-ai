"""Bounded, canonical JSON and strict primitives shared by benchmark files."""
import json
import re
from datetime import datetime, timezone
from functools import wraps
from hashlib import sha256

MAX_JSON_BYTES = 32 * 1024 * 1024
MAX_SAMPLES = 500
HUMAN_RUBRIC = 'human-site-1'


class BenchmarkError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def require(condition):
    if not condition:
        raise BenchmarkError('benchmark_invalid')


def contract(code):
    def decorate(function):
        @wraps(function)
        def checked(*args, **kwargs):
            try:
                return function(*args, **kwargs)
            except (ValueError, TypeError, KeyError, AttributeError, OverflowError, RecursionError):
                raise BenchmarkError(code) from None
        return checked
    return decorate


def canonical(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(',', ':'))


def bounded(value):
    require(len(canonical(value).encode('utf-8')) <= MAX_JSON_BYTES)


def digest(value):
    return sha256(canonical(value).encode('utf-8')).hexdigest()


def keys(value, names):
    require(type(value) is dict and set(value) == set(names))


def identifier(value, maximum=64, *, dots=False):
    require(type(value) is str and 1 <= len(value) <= maximum)
    require(re.fullmatch(r'[A-Za-z0-9_.-]+' if dots else r'[A-Za-z0-9_-]+', value) is not None)
    return value


def integer(value, low, high):
    require(type(value) is int and low <= value <= high)
    return value


def timestamp(value):
    require(type(value) is str and len(value) <= 64)
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(parsed.tzinfo is not None)
    return parsed.astimezone(timezone.utc).isoformat()
