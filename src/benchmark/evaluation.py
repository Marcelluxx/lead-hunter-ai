"""Descriptive comparisons only: no fitted weights, significance or quality claims."""
from math import fsum, sqrt

from .contracts import HUMAN_RUBRIC, MAX_SAMPLES, bounded, contract, require
from .dataset import validate_dataset
from .reviews import _validate_packet


def _rounded(value):
    return None if value is None else round(value, 6)


def _ranks(values):
    ordered = sorted(range(len(values)), key=values.__getitem__)
    ranks = [0.0] * len(values)
    start = 0
    while start < len(ordered):
        end = start + 1
        while end < len(ordered) and values[ordered[end]] == values[ordered[start]]:
            end += 1
        rank = (start + 1 + end) / 2
        for index in ordered[start:end]:
            ranks[index] = rank
        start = end
    return ranks


def _spearman(pairs):
    if len(pairs) < 2:
        return None
    x = _ranks([row[0] for row in pairs]); y = _ranks([row[1] for row in pairs])
    mean_x = fsum(x) / len(x); mean_y = fsum(y) / len(y)
    centered = [(a - mean_x, b - mean_y) for a, b in zip(x, y)]
    denominator = sqrt(fsum(a*a for a, _ in centered) * fsum(b*b for _, b in centered))
    if denominator == 0:
        return None
    return max(-1.0, min(1.0, fsum(a*b for a, b in centered) / denominator))


def _comparison(rows, prediction, human, *, errors=False):
    pairs = [(row[prediction], row[human]) for row in rows
             if row[prediction] is not None and row[human] is not None]
    result = {'n': len(pairs), 'spearman': _rounded(_spearman(pairs))}
    if errors:
        differences = [a-b for a, b in pairs]
        result.update(mae=_rounded(fsum(abs(d) for d in differences) / len(pairs)) if pairs else None,
            rmse=_rounded(sqrt(fsum(d*d for d in differences) / len(pairs))) if pairs else None,
            bias=_rounded(fsum(differences) / len(pairs)) if pairs else None)
    return result


def _metrics(rows):
    return {'ai_vs_quality': _comparison(rows, 'ai_score', 'human_quality_mean', errors=True),
        'markup_vs_quality': _comparison(rows, 'markup_score', 'human_quality_mean'),
        'ai_vs_priority': _comparison(rows, 'ai_score', 'human_priority_mean'),
        'markup_vs_priority': _comparison(rows, 'markup_score', 'human_priority_mean')}


@contract('evaluation_invalid')
def evaluate(dataset, packets):
    checked = validate_dataset(dataset)
    require(type(packets) is list and len(packets) <= MAX_SAMPLES)
    bounded(packets)
    reviews = [_validate_packet(packet, checked) for packet in packets]
    reviewer_ids = [packet['reviewer_id'] for packet in reviews]
    require(len(set(reviewer_ids)) == len(reviewer_ids))
    reviews.sort(key=lambda packet: packet['reviewer_id'])
    counts = {'samples': len(checked['samples']), 'reviewers': len(reviews),
        'reviewed_ratings': 0, 'pending_ratings': 0, 'unassessable_ratings': 0,
        'reviewed_samples': 0, 'unreviewed_samples': 0,
        'missing_ai_samples': 0, 'missing_markup_samples': 0}
    coverage = dict.fromkeys(('complete', 'partial', 'unavailable'), 0)
    distances = {'quality': [0, 0], 'priority': [0, 0]}
    rows = []
    for index, sample in enumerate(checked['samples']):
        ratings = []
        for packet in reviews:
            review = packet['reviews'][index]
            counts[review['status'] + '_ratings'] += 1
            if review['status'] == 'reviewed':
                ratings.append(review)
        row = {'sample_id': sample['sample_id'], 'human_ratings': len(ratings),
            'human_quality_mean': (fsum(item['quality_score'] for item in ratings) / len(ratings)) if ratings else None,
            'human_priority_mean': (fsum(item['intervention_priority'] for item in ratings) / len(ratings)) if ratings else None,
            'ai_score': sample['website_score'], 'markup_score': sample['score_report']['score'],
            'dom_status': sample['dom_report']['status']}
        counts['reviewed_samples' if ratings else 'unreviewed_samples'] += 1
        counts['missing_ai_samples'] += row['ai_score'] is None
        counts['missing_markup_samples'] += row['markup_score'] is None
        coverage[row['dom_status']] += 1
        for dimension, field in (('quality', 'quality_score'), ('priority', 'intervention_priority')):
            values = sorted(item[field] for item in ratings)
            # Sum |x_j-x_i| over i<j without materializing quadratic pairs.
            distances[dimension][0] += len(values) * (len(values) - 1) // 2
            distances[dimension][1] += sum((2*i - len(values) + 1) * value for i, value in enumerate(values))
        rows.append(row)
    result = {'schema_version': 1, 'metric_version': 'human-audit-comparison-1',
        'rubric_version': HUMAN_RUBRIC, 'dataset_sha256': checked['dataset_sha256'],
        'prediction_version': checked['prediction_version'], 'calibration_status': 'uncalibrated',
        'reference_status': 'provisional_human_ratings', 'counts': counts, 'coverage': coverage,
        'overall': _metrics(rows),
        'by_dom_status': {status: _metrics([row for row in rows if row['dom_status'] == status]) for status in coverage},
        'agreement': {dimension: {'pairs': count,
            'mean_absolute_distance': _rounded(total / count) if count else None}
            for dimension, (count, total) in distances.items()},
        'samples': [{key: _rounded(value) if type(value) is float else value for key, value in row.items()} for row in rows]}
    bounded(result)
    return result
