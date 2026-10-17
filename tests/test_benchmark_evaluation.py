import copy
import importlib
import json
import unittest

from src.benchmark.contracts import BenchmarkError
from src.benchmark.dataset import build_dataset
from src.benchmark.reviews import build_review_packet
from tests.benchmark_helpers import snapshot, reviewed_packet


class BenchmarkEvaluationTests(unittest.TestCase):
    def evaluate(self, dataset, packets):
        try:
            evaluate = importlib.import_module('src.benchmark.evaluation').evaluate
        except (ImportError, AttributeError):
            self.fail('Human comparison metrics are missing')
        return evaluate(dataset, packets)

    def test_hand_computed_ai_errors_are_in_quality_units_not_priority_units(self):
        dataset = build_dataset([snapshot(1, ai=2), snapshot(2, ai=6), snapshot(3, ai=8)], 'v1')
        packet = reviewed_packet(dataset)
        values = {'https://site1.test/': (1, 3), 'https://site2.test/': (7, 0), 'https://site3.test/': (8, 1)}
        for row in packet['reviews']:
            row['quality_score'], row['intervention_priority'] = values[row['source_url']]
        result = self.evaluate(dataset, [packet])
        metric = result['overall']['ai_vs_quality']
        self.assertEqual(metric, {'n': 3, 'mae': 0.666667, 'rmse': 0.816497, 'bias': 0.0, 'spearman': 1.0})
        self.assertEqual(set(result['overall']['ai_vs_priority']), {'n', 'spearman'})
        self.assertEqual(result['calibration_status'], 'uncalibrated')
        self.assertEqual(result['reference_status'], 'provisional_human_ratings')
        for private in ['https://', 'rater_a', 'source_url']:
            self.assertNotIn(private, json.dumps(result))

    def test_ranks_include_ties_inverse_relationships_and_constants(self):
        for ai_values, qualities, expected in [([1, 2, 3], [3, 2, 1], -1.0),
                ([1, 1, 3], [1, 2, 3], 0.866025), ([1, 1, 1], [1, 2, 3], None)]:
            dataset = build_dataset([snapshot(i, ai=ai_values[i-1]) for i in (1, 2, 3)], 'v1')
            packet = reviewed_packet(dataset)
            for row in packet['reviews']:
                index = int(row['source_url'].split('site')[1].split('.')[0]) - 1
                row['quality_score'] = qualities[index]
            with self.subTest(ai=ai_values):
                result = self.evaluate(dataset, [packet])
                self.assertEqual(result['overall']['ai_vs_quality']['spearman'], expected)
                self.assertIsNone(result['overall']['markup_vs_quality']['spearman'])

    def test_missing_reviews_and_unassessable_are_counted_never_imputed(self):
        dataset = build_dataset([snapshot(1, ai=None, markup=False), snapshot(2, markup=False)], 'v1')
        packet = build_review_packet(dataset, 'rater_a')
        packet['reviews'][0].update(status='unassessable', reason='changed_site',
            reviewed_at='2026-10-15T11:00:00+00:00')
        result = self.evaluate(dataset, [packet])
        self.assertEqual(result['counts'], {'samples': 2, 'reviewers': 1, 'reviewed_ratings': 0,
            'pending_ratings': 1, 'unassessable_ratings': 1, 'reviewed_samples': 0,
            'unreviewed_samples': 2, 'missing_ai_samples': 1, 'missing_markup_samples': 2})
        self.assertEqual(result['overall']['ai_vs_quality'],
            {'n': 0, 'mae': None, 'rmse': None, 'bias': None, 'spearman': None})
        self.assertEqual(result['agreement']['quality'], {'pairs': 0, 'mean_absolute_distance': None})
        self.assertEqual(result['coverage'], {'complete': 0, 'partial': 0, 'unavailable': 2})
        self.assertTrue(all(row['human_quality_mean'] is None for row in result['samples']))

    def test_means_weight_sites_once_and_agreement_uses_within_site_pairs(self):
        dataset = build_dataset([snapshot(1, ai=5), snapshot(2, ai=7)], 'v1')
        packets = []
        for reviewer, quality, priority in [('a', 2, 0), ('b', 4, 1), ('c', 6, 3)]:
            packet = build_review_packet(dataset, reviewer)
            for row in packet['reviews']:
                if row['source_url'] == 'https://site1.test/' or reviewer == 'a':
                    row.update(status='reviewed', reviewed_at='2026-10-15T11:00:00+00:00',
                        quality_score=quality if row['source_url'] == 'https://site1.test/' else 8,
                        intervention_priority=priority)
            packets.append(packet)
        result = self.evaluate(dataset, packets)
        self.assertEqual(result['overall']['ai_vs_quality']['mae'], 1.0)
        self.assertEqual(result['overall']['ai_vs_quality']['bias'], 0.0)
        self.assertEqual(result['agreement']['quality'], {'pairs': 3, 'mean_absolute_distance': 2.666667})
        self.assertEqual(result['agreement']['priority'], {'pairs': 3, 'mean_absolute_distance': 2.0})
        self.assertEqual(result, self.evaluate(dataset, list(reversed(packets))))

    def test_coverage_strata_expose_partial_data_and_missing_legacy_index(self):
        from src.domain.markup_score import build_score_report, empty_score_report
        rows = [snapshot(1), snapshot(2), snapshot(3)]
        partial = rows[1]['dom_report']
        partial['status'] = 'partial'
        partial['coverage']['eligible_pages'] = 2; partial['coverage']['omitted_pages'] = 1
        rows[1]['score_report'] = build_score_report(partial)
        rows[2]['score_report'] = empty_score_report()
        dataset = build_dataset(rows, 'v1')
        result = self.evaluate(dataset, [reviewed_packet(dataset)])
        self.assertEqual(result['coverage'], {'complete': 2, 'partial': 1, 'unavailable': 0})
        self.assertEqual(result['by_dom_status']['partial']['ai_vs_quality']['n'], 1)
        self.assertEqual(result['by_dom_status']['complete']['markup_vs_quality']['n'], 1)
        self.assertEqual(result['by_dom_status']['unavailable']['ai_vs_quality']['n'], 0)
        self.assertEqual(result['counts']['missing_markup_samples'], 1)

    def test_duplicate_reviewers_foreign_packets_and_limit_fail_safely(self):
        dataset = build_dataset([snapshot()], 'v1'); packet = reviewed_packet(dataset)
        for packets in [[packet, copy.deepcopy(packet)], [packet] * 501,
                        [reviewed_packet(build_dataset([snapshot(2)], 'v1'))], 'invalid']:
            with self.assertRaises(BenchmarkError): self.evaluate(dataset, packets)
        self.assertEqual(self.evaluate(dataset, [])['counts']['unreviewed_samples'], 1)
