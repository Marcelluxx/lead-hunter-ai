import copy
import json
import unittest
from hashlib import sha256

from src.application.dom_checks import build_dom_report
from src.domain.audit import AuditValidationError
from src.domain.dom_checks import empty_dom_report, metric, RULE_IDS
from tests.test_dom_checks_runtime import dom_crawl


class MarkupScoreTests(unittest.TestCase):
    def api(self):
        try:
            from src.domain.markup_score import build_score_report, empty_score_report, validate_score_report
        except ImportError:
            self.fail('Versioned markup score contract is not implemented')
        return build_score_report, empty_score_report, validate_score_report

    def dom(self, count=1):
        return build_dom_report(dom_crawl(count))

    def test_complete_score_has_nine_explained_components_and_exact_dom_binding(self):
        build, _, validate = self.api(); dom = self.dom(); report = build(dom)
        self.assertEqual(report['score'], 100.0)
        self.assertEqual(report['applicable_weight'], 9)
        self.assertEqual(report['rubric_version'], 'dom-markup-1')
        self.assertEqual(report['calibration_status'], 'uncalibrated')
        self.assertEqual(report['coverage'], dom['coverage'])
        self.assertEqual(set(report['components']), set(RULE_IDS))
        self.assertTrue(all(item['weight'] == 1 and item['score'] == 100.0 for item in report['components'].values()))
        canonical = json.dumps(dom, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(',', ':'))
        self.assertEqual(report['dom_report_sha256'], sha256(canonical.encode()).hexdigest())
        self.assertEqual(report['evidence_ids'], [dom['pages'][0]['id']])
        self.assertEqual(validate(report, dom), report)
        self.assertNotIn('PRIVATE_', json.dumps(report)); self.assertNotIn('https://', json.dumps(report))

    def test_zero_null_and_not_applicable_are_distinct(self):
        build, empty, _ = self.api()
        self.assertEqual(build(empty_dom_report()), empty())
        self.assertIsNone(empty()['score'])
        self.assertEqual(empty()['applicable_weight'], 0)
        self.assertIsNone(empty()['dom_report_sha256'])
        dom = build_dom_report(dom_crawl(1, html='<html><head></head><body></body></html>'))
        report = build(dom)
        self.assertEqual(report['score'], 0.0)
        self.assertEqual(report['applicable_weight'], 6)
        self.assertEqual(report['components']['image_alt_attribute']['status'], 'not_applicable_observed')
        self.assertIsNone(report['components']['image_alt_attribute']['score'])
        self.assertEqual(report['components']['title_text']['score'], 0.0)

    def test_unknown_and_omitted_pages_do_not_become_zero_or_pass(self):
        build, _, _ = self.api(); dom = self.dom(2)
        page = dom['pages'][1]; page.update(status='inconclusive', reason='dom_unavailable', checks={})
        dom['status'] = 'partial'; dom['coverage'].update(inspected_pages=1, inconclusive_pages=1)
        report = build(dom)
        self.assertEqual(report['score'], 100.0); self.assertEqual(report['status'], 'partial')
        self.assertEqual(report['coverage']['inconclusive_pages'], 1)
        self.assertEqual(len(report['evidence_ids']), 1)
        dom['pages'].pop(); dom['coverage'].update(inconclusive_pages=0, omitted_pages=1)
        self.assertEqual(build(dom)['score'], 100.0)
        dom['pages'].clear(); dom['coverage'].update(inspected_pages=0, omitted_pages=2); dom['status'] = 'unavailable'
        report = build(dom)
        self.assertIsNone(report['score']); self.assertEqual(report['coverage']['eligible_pages'], 2)
        self.assertIsNotNone(report['dom_report_sha256'])
        self.assertTrue(all(item['status'] == 'unknown' for item in report['components'].values()))

    def test_aggregation_is_per_element_within_rule_and_independent_of_page_order(self):
        build, _, _ = self.api(); dom = self.dom(2)
        dom['pages'][0]['checks']['image_alt_attribute'] = metric(1, 2)
        dom['pages'][1]['checks']['image_alt_attribute'] = metric(1, 6)
        report = build(dom)
        component = report['components']['image_alt_attribute']
        self.assertEqual((component['matched'], component['total'], component['applicable_pages']), (2, 8, 2))
        self.assertEqual(component['score'], 25.0); self.assertEqual(report['score'], 91.67)
        dom['pages'].reverse(); reordered = build(dom)
        self.assertEqual(reordered['score'], report['score'])
        self.assertEqual(reordered['components'], report['components'])
        self.assertEqual(reordered['evidence_ids'], report['evidence_ids'])
        self.assertNotEqual(reordered['dom_report_sha256'], report['dom_report_sha256'])

    def test_half_up_rounding_is_exact_and_total_uses_unrounded_ratios(self):
        build, _, _ = self.api(); dom = build_dom_report(dom_crawl(1, html='<html><head></head><body></body></html>'))
        dom['pages'][0]['checks']['image_alt_attribute'] = metric(1, 32)
        report = build(dom)
        self.assertEqual(report['components']['image_alt_attribute']['score'], 3.13)
        self.assertEqual(report['score'], 0.45)
        self.assertEqual(report['applicable_weight'], 7)

    def test_twenty_pages_and_large_counts_stay_bounded(self):
        build, _, _ = self.api(); dom = self.dom(20)
        for page in dom['pages']:
            page['checks']['image_alt_attribute'] = metric(500000, 1000000)
        report = build(dom)
        self.assertEqual(report['components']['image_alt_attribute']['total'], 20000000)
        self.assertEqual(report['score'], 94.44)
        self.assertEqual(len(report['evidence_ids']), 20)
        self.assertLessEqual(len(json.dumps(report, ensure_ascii=False).encode()), 12000)

    def test_corrupt_score_types_version_fields_hash_and_dom_metadata_are_rejected(self):
        build, _, validate = self.api(); dom = self.dom(); report = build(dom)
        mutations = [('score', True), ('score', float('nan')), ('score', 99), ('rubric_version', 'future'),
            ('dom_report_sha256', 'a' * 64), ('extra', 'PRIVATE_' + 'x' * 12000)]
        for key, value in mutations:
            bad = copy.deepcopy(report); bad[key] = value
            with self.subTest(key=key, value=str(value)[:10]), self.assertRaisesRegex(AuditValidationError, '^score_report_invalid$'):
                validate(bad, dom)
        bad = copy.deepcopy(report); bad['components']['title_text']['weight'] = True
        with self.assertRaisesRegex(AuditValidationError, '^score_report_invalid$'): validate(bad, dom)
        changed = copy.deepcopy(dom); changed['pages'][0]['retrieved_at'] = '2000-01-01T00:00:00+00:00'
        with self.assertRaisesRegex(AuditValidationError, '^score_report_invalid$'): validate(report, changed)

    def test_invalid_dom_preserves_its_validation_code_and_copies_are_independent(self):
        build, _, _ = self.api(); dom = self.dom()
        bad = copy.deepcopy(dom); bad['pages'][0]['checks']['title_text']['matched'] = True
        with self.assertRaisesRegex(AuditValidationError, '^dom_report_invalid$'): build(bad)
        report = build(dom); report['coverage']['eligible_pages'] = 0
        self.assertEqual(dom['coverage']['eligible_pages'], 1)
