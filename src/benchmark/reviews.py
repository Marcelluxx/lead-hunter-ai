"""Blind human packets with two independent dimensions and snapshot binding."""
import json

from .contracts import (HUMAN_RUBRIC, bounded, canonical, contract, identifier,
                        integer, keys, require, timestamp)
from .dataset import validate_dataset

REVIEW_FIELDS = ('sample_id', 'source_url', 'captured_at', 'status', 'reviewed_at',
                 'quality_score', 'intervention_priority', 'reason')


@contract('review_invalid')
def build_review_packet(dataset, reviewer_id):
    checked = validate_dataset(dataset)
    identifier(reviewer_id)
    return {'schema_version': 1, 'rubric_version': HUMAN_RUBRIC,
        'dataset_sha256': checked['dataset_sha256'], 'reviewer_id': reviewer_id,
        'reviews': [{**{key: row[key] for key in ('sample_id', 'source_url', 'captured_at')},
            'status': 'pending', 'reviewed_at': None, 'quality_score': None,
            'intervention_priority': None, 'reason': None} for row in checked['samples']]}


@contract('review_invalid')
def _validate_packet(packet, checked_dataset):
    """Internal fast path: caller has already validated the shared dataset."""
    bounded(packet)
    keys(packet, ('schema_version', 'rubric_version', 'dataset_sha256', 'reviewer_id', 'reviews'))
    require(type(packet['schema_version']) is int and packet['schema_version'] == 1)
    require(packet['rubric_version'] == HUMAN_RUBRIC)
    require(packet['dataset_sha256'] == checked_dataset['dataset_sha256'])
    identifier(packet['reviewer_id'])
    # Normalize editable dates on an independent copy, never in the human file.
    normalized = json.loads(canonical(packet))
    rows = normalized['reviews']
    require(type(rows) is list and len(rows) == len(checked_dataset['samples']))
    for row, sample in zip(rows, checked_dataset['samples']):
        keys(row, REVIEW_FIELDS)
        require(all(row[key] == sample[key] for key in ('sample_id', 'source_url', 'captured_at')))
        status = row['status']
        require(type(status) is str and status in ('pending', 'reviewed', 'unassessable'))
        if status == 'pending':
            require(all(row[key] is None for key in ('reviewed_at', 'quality_score', 'intervention_priority', 'reason')))
            continue
        reviewed = timestamp(row['reviewed_at'])
        require(reviewed >= sample['captured_at'])
        row['reviewed_at'] = reviewed
        if status == 'reviewed':
            integer(row['quality_score'], 1, 10)
            integer(row['intervention_priority'], 0, 3)
            require(row['reason'] is None)
        else:
            require(row['quality_score'] is None and row['intervention_priority'] is None)
            require(type(row['reason']) is str and row['reason'] in
                    ('unavailable', 'changed_site', 'insufficient_context', 'other'))
    return normalized


@contract('review_invalid')
def validate_review_packet(packet, dataset):
    return _validate_packet(packet, validate_dataset(dataset))
