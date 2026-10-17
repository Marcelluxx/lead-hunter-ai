"""Minimal snapshots bound to validated DOM reports and exact predictions."""
from .contracts import (bounded, canonical, contract, digest, identifier, integer,
                        keys, MAX_SAMPLES, require, timestamp)
from src.domain.audit_evidence import public_evidence_url
from src.domain.dom_checks import validate_dom_report
from src.domain.markup_score import empty_score_report, validate_score_report

INPUT_FIELDS = ('source_url', 'captured_at', 'website_score', 'dom_report', 'score_report')


@contract('dataset_invalid')
def build_dataset(records, prediction_version):
    identifier(prediction_version, 100, dots=True)
    require(type(records) is list and 1 <= len(records) <= MAX_SAMPLES)
    bounded(records)
    samples = []
    seen = set()
    for record in records:
        keys(record, INPUT_FIELDS)
        score = record['website_score']
        if score is not None:
            integer(score, 1, 10)
        source_url = public_evidence_url(record['source_url'])
        captured = timestamp(record['captured_at'])
        identity = (source_url, captured)
        require(identity not in seen)
        seen.add(identity)
        dom = validate_dom_report(record['dom_report'])
        # Older records can have DOM but no rubric ever applied to them.
        historical = empty_score_report()
        markup = (historical if canonical(record['score_report']) == canonical(historical)
                  else validate_score_report(record['score_report'], dom))
        for page in dom['pages']:
            if page['retrieved_at'] is not None:
                require(timestamp(page['retrieved_at']) <= captured)
        sample = {'source_url': source_url, 'captured_at': captured, 'website_score': score,
                  'dom_report': dom, 'score_report': markup}
        sample['sample_id'] = 's_' + digest(sample)
        samples.append(sample)
    result = {'schema_version': 1, 'prediction_version': prediction_version,
              'samples': sorted(samples, key=lambda item: item['sample_id'])}
    result['dataset_sha256'] = digest(result)
    bounded(result)
    return result


@contract('dataset_invalid')
def validate_dataset(dataset):
    bounded(dataset)
    keys(dataset, ('schema_version', 'prediction_version', 'samples', 'dataset_sha256'))
    require(type(dataset['schema_version']) is int and dataset['schema_version'] == 1)
    require(type(dataset['samples']) is list)
    records = []
    for sample in dataset['samples']:
        keys(sample, (*INPUT_FIELDS, 'sample_id'))
        records.append({key: sample[key] for key in INPUT_FIELDS})
    expected = build_dataset(records, dataset['prediction_version'])
    require(canonical(expected) == canonical(dataset))
    return expected
