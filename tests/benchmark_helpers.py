"""Synthetic benchmark inputs; never human-reviewed real-world examples."""
import copy

from src.application.dom_checks import build_dom_report
from src.domain.dom_checks import empty_dom_report
from src.domain.markup_score import build_score_report
from tests.test_dom_checks_runtime import dom_crawl


def snapshot(index=1, *, ai=7, markup=True):
    dom = build_dom_report(dom_crawl(1)) if markup else empty_dom_report()
    for page in dom['pages']:
        page['retrieved_at'] = '2026-10-14T10:00:00+00:00'
    return {'source_url': f'https://site{index}.test/', 'captured_at': '2026-10-15T10:00:00+00:00',
        'website_score': ai, 'dom_report': dom, 'score_report': build_score_report(dom)}


def reviewed_packet(dataset, reviewer='rater_a', scores=None):
    from src.benchmark.reviews import build_review_packet
    packet = build_review_packet(dataset, reviewer)
    scores = scores or [(6, 2)] * len(packet['reviews'])
    for item, (quality, priority) in zip(packet['reviews'], scores):
        item.update(status='reviewed', reviewed_at='2026-10-15T11:00:00+00:00',
                    quality_score=quality, intervention_priority=priority)
    return copy.deepcopy(packet)
