"""Local file boundaries and minimal projection of an authorized job result."""
import json
import os
from pathlib import Path
import re

from .contracts import (BenchmarkError, MAX_JSON_BYTES, MAX_SAMPLES, contract,
                        integer, require)
from .dataset import build_dataset
from src.domain.dom_checks import empty_dom_report
from src.domain.markup_score import empty_score_report


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result)
        result[key] = value
    return result


def _reject_constant(_value):
    raise BenchmarkError('benchmark_json_invalid')


def _read_bytes(path, byte_limit):
    try:
        with Path(path).open('rb') as handle:
            data = handle.read(byte_limit + 1)
    except OSError:
        raise BenchmarkError('benchmark_file_unavailable') from None
    if len(data) > byte_limit:
        raise BenchmarkError('benchmark_json_invalid')
    return data


def _decode(data):
    try:
        return json.loads(data.decode('utf-8'), object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    except (ValueError, UnicodeError, RecursionError):
        raise BenchmarkError('benchmark_json_invalid') from None


def load_json(path):
    return _decode(_read_bytes(path, MAX_JSON_BYTES))


def load_review_packets(paths):
    require(type(paths) is list and len(paths) <= MAX_SAMPLES)
    remaining = MAX_JSON_BYTES
    packets = []
    for path in paths:
        data = _read_bytes(path, remaining)
        remaining -= len(data)
        packets.append(_decode(data))
    return packets


def write_json_new(path, value):
    target = Path(path)
    created = False
    try:
        data = (json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + '\n').encode('utf-8')
        require(len(data) <= MAX_JSON_BYTES)
        descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        created = True
        with os.fdopen(descriptor, 'wb') as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except (OSError, ValueError, UnicodeError, RecursionError, TypeError):
        if created:
            try:
                target.unlink()
            except OSError:
                pass
        raise BenchmarkError('benchmark_file_unavailable') from None


@contract('job_snapshot_invalid')
def dataset_from_job(result, *, prediction_version, captured_at):
    require(type(result) is dict and result.get('state') == 'completed')
    require(result.get('references') == [] and result.get('diagnostic_available') is False)
    leads = result['leads']
    require(type(leads) is list and 1 <= len(leads) <= MAX_SAMPLES)
    records = []
    for lead in leads:
        require(type(lead) is dict and type(lead.get('attributes')) is dict)
        attributes = lead['attributes']
        score = attributes.get('website_score')
        if type(score) is str:
            require(re.fullmatch(r'\s*(10|[1-9])(?:\s*/\s*10)?\s*', score) is not None)
            score = int(score.strip().split('/')[0].strip())
        if score is not None:
            integer(score, 1, 10)
        records.append({'source_url': attributes['website'], 'captured_at': captured_at,
            'website_score': score, 'dom_report': lead.get('dom_report', empty_dom_report()),
            'score_report': lead.get('score_report', empty_score_report())})
    return build_dataset(records, prediction_version)
