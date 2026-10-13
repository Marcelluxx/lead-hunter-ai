"""Uncalibrated markup index with exact arithmetic and derivation-bound validation."""
import json
from fractions import Fraction
from hashlib import sha256

from .audit import AuditValidationError
from .dom_checks import RULE_IDS, RULES_VERSION, empty_dom_report, validate_dom_report

RUBRIC_VERSION = 'dom-markup-1'
MAX_SCORE_REPORT_BYTES = 12000


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(',', ':'))


def _percent(ratio):
    # Exact half-up to hundredths of a percentage, without intermediate rounding.
    return ((ratio.numerator * 20000 + ratio.denominator) // (2 * ratio.denominator)) / 100.0


def empty_score_report():
    return {'schema_version': 1, 'rubric_version': RUBRIC_VERSION, 'rules_version': RULES_VERSION,
        'method': 'dom_markup_index', 'scope': 'collected_html_dom', 'calibration_status': 'uncalibrated',
        'status': 'unavailable', 'score': None,
        'scale': {'minimum': 0, 'maximum': 100, 'direction': 'higher_more_markup_matches'},
        'coverage': empty_dom_report()['coverage'], 'applicable_weight': 0, 'evidence_ids': [],
        'dom_report_sha256': None,
        'components': {rule: {'weight': 1, 'matched': 0, 'total': 0, 'applicable_pages': 0,
            'not_applicable_pages': 0, 'status': 'unknown', 'score': None} for rule in RULE_IDS}}


def build_score_report(dom_report):
    dom = validate_dom_report(dom_report)
    report = empty_score_report()
    if dom['coverage']['eligible_pages'] == 0:
        return report
    report['coverage'] = dom['coverage']; report['status'] = dom['status']
    report['dom_report_sha256'] = sha256(_canonical(dom).encode('utf-8')).hexdigest()
    pages = [page for page in dom['pages'] if page['status'] == 'observed']
    report['evidence_ids'] = sorted(page['id'] for page in pages)
    ratios = []
    for rule in RULE_IDS:
        component = report['components'][rule]
        component['matched'] = sum(page['checks'][rule]['matched'] for page in pages)
        component['total'] = sum(page['checks'][rule]['total'] for page in pages)
        component['applicable_pages'] = sum(page['checks'][rule]['total'] > 0 for page in pages)
        component['not_applicable_pages'] = len(pages) - component['applicable_pages']
        if component['total']:
            ratio = Fraction(component['matched'], component['total'])
            ratios.append(ratio)
            component.update(status='observed', score=_percent(ratio))
        elif pages:
            component['status'] = 'not_applicable_observed'
    report['applicable_weight'] = len(ratios)
    if ratios:
        report['score'] = _percent(sum(ratios, Fraction(0)) / len(ratios))
    return report


def validate_score_report(report, dom_report):
    expected = build_score_report(dom_report)
    try:
        encoded = _canonical(report)
        if len(encoded.encode('utf-8')) > MAX_SCORE_REPORT_BYTES or encoded != _canonical(expected):
            raise AuditValidationError('score_report_invalid')
    except (TypeError, ValueError, UnicodeError, RecursionError):
        raise AuditValidationError('score_report_invalid') from None
    return json.loads(encoded)
