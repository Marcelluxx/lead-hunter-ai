import copy
import importlib
import json
import unittest
from hashlib import sha256

from src.domain.markup_score import empty_score_report
from tests.benchmark_helpers import snapshot, reviewed_packet


class BenchmarkContractsTests(unittest.TestCase):
    def api(self):
        try:
            dataset = importlib.import_module('src.benchmark.dataset')
            reviews = importlib.import_module('src.benchmark.reviews')
            contracts = importlib.import_module('src.benchmark.contracts')
        except ImportError:
            self.fail('Bound human benchmark and blind-review contracts are missing')
        return dataset, reviews, contracts.BenchmarkError

    def test_dataset_order_and_digests_bind_all_predictions_and_metadata(self):
        d, _, error = self.api()
        result = d.build_dataset([snapshot(2), snapshot(1)], 'release-f477815-model-A')
        self.assertEqual(result, d.build_dataset([snapshot(1), snapshot(2)], 'release-f477815-model-A'))
        body = {k: v for k, v in result.items() if k != 'dataset_sha256'}
        encoded = json.dumps(body, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(',', ':'))
        self.assertEqual(result['dataset_sha256'], sha256(encoded.encode()).hexdigest())
        self.assertEqual(d.validate_dataset(result), result)
        for mutate in [lambda x: x['samples'][0].update(website_score=1),
                       lambda x: x.update(prediction_version='changed'),
                       lambda x: x['samples'][0].update(captured_at='2026-10-16T00:00:00+00:00'),
                       lambda x: x.update(schema_version=True),
                       lambda x: x.update(contacts=['PRIVATE_SENTINEL'])]:
            changed = copy.deepcopy(result); mutate(changed)
            with self.subTest(changed=changed.keys()), self.assertRaises(error):
                d.validate_dataset(changed)

    def test_projection_redacts_url_without_network_or_mutating_source(self):
        d, _, _ = self.api(); record = snapshot()
        record['source_url'] = 'https://site.test/contact/person@example.com?key=PRIVATE_QUERY#token'
        original = copy.deepcopy(record)
        result = d.build_dataset([record], 'v1')
        self.assertEqual(result['samples'][0]['source_url'], 'https://site.test/[REDACTED_PATH]')
        self.assertNotIn('PRIVATE_QUERY', json.dumps(result)); self.assertEqual(record, original)

    def test_zero_and_historical_missing_score_remain_distinct(self):
        d, _, _ = self.api(); row = snapshot(ai=None)
        row['score_report'] = empty_score_report()
        historical = d.build_dataset([row], 'v1')['samples'][0]
        self.assertIsNone(historical['website_score'])
        self.assertIsNone(historical['score_report']['score'])
        self.assertEqual(historical['dom_report']['status'], 'complete')
        from src.application.dom_checks import build_dom_report
        from src.domain.markup_score import build_score_report
        from tests.test_dom_checks_runtime import dom_crawl
        row['dom_report'] = build_dom_report(dom_crawl(1, html='<html><head></head><body></body></html>'))
        for page in row['dom_report']['pages']: page['retrieved_at'] = '2026-10-14T10:00:00+00:00'
        row['score_report'] = build_score_report(row['dom_report'])
        self.assertEqual(d.build_dataset([row], 'v1')['samples'][0]['score_report']['score'], 0)

    def test_rejects_invalid_types_corrupt_reports_duplicates_and_limits(self):
        d, _, error = self.api()
        for field, value in [('website_score', True), ('website_score', float('nan')),
                ('website_score', '7'), ('website_score', 0), ('website_score', 11),
                ('captured_at', '2026-10-15'), ('captured_at', '2000-01-01T00:00:00Z'),
                ('source_url', 'https://user:pass@site.test'), ('score_report', {'score': 88}),
                ('dom_report', {'schema_version': 1})]:
            row = snapshot(); row[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(error): d.build_dataset([row], 'v1')
        row = snapshot(); row['secret'] = 'PRIVATE'
        for records in [[], [snapshot()] * 501, [snapshot(), snapshot()], [row]]:
            with self.assertRaises(error): d.build_dataset(records, 'v1')
        for version in ['', 'model key PRIVATE', True, 'v' * 101]:
            with self.assertRaises(error): d.build_dataset([snapshot()], version)

    def test_blind_packet_hides_every_automatic_score_and_is_dataset_bound(self):
        d, r, error = self.api(); dataset = d.build_dataset([snapshot()], 'v1')
        packet = r.build_review_packet(dataset, 'rater_a')
        self.assertEqual(packet['rubric_version'], 'human-site-1')
        self.assertEqual(packet['reviews'][0]['status'], 'pending')
        self.assertEqual(r.validate_review_packet(packet, dataset), packet)
        text = json.dumps(packet)
        for name in ['website_score', 'score_report', 'dom_report', 'diagnosis', 'prediction_version']:
            self.assertNotIn(name, text)
        changed = d.build_dataset([snapshot(ai=8)], 'v1')
        with self.assertRaises(error): r.validate_review_packet(packet, changed)
        for reviewer in ['person@example.com', '', True, 'r' * 65]:
            with self.assertRaises(error): r.build_review_packet(dataset, reviewer)

    def test_two_judgments_are_independent_and_unknown_is_not_zero(self):
        d, r, error = self.api(); dataset = d.build_dataset([snapshot()], 'v1')
        for quality, priority in [(1, 0), (10, 3), (8, 1)]:
            packet = reviewed_packet(dataset, scores=[(quality, priority)])
            self.assertEqual(r.validate_review_packet(packet, dataset), packet)
        packet = r.build_review_packet(dataset, 'rater_a')
        packet['reviews'][0].update(status='unassessable', reason='changed_site',
            reviewed_at='2026-10-15T11:00:00+00:00')
        self.assertEqual(r.validate_review_packet(packet, dataset), packet)
        packet['reviews'][0]['quality_score'] = 0
        with self.assertRaises(error): r.validate_review_packet(packet, dataset)

    def test_rejects_forged_packet_fields_duplicates_and_bad_review_times(self):
        d, r, error = self.api(); dataset = d.build_dataset([snapshot()], 'v1')
        base = reviewed_packet(dataset)
        mutations = [lambda x: x.update(schema_version=True), lambda x: x.update(rubric_version='unknown'),
            lambda x: x['reviews'].append(copy.deepcopy(x['reviews'][0])),
            lambda x: x['reviews'].clear(), lambda x: x['reviews'][0].update(quality_score=True),
            lambda x: x['reviews'][0].update(intervention_priority=4),
            lambda x: x['reviews'][0].update(reviewed_at='2026-10-15'),
            lambda x: x['reviews'][0].update(reviewed_at='2026-10-14T00:00:00Z'),
            lambda x: x['reviews'][0].update(source_url='https://other.test/'),
            lambda x: x['reviews'][0].update(reason='PRIVATE'),
            lambda x: x['reviews'][0].update(status='pending'),
            lambda x: x['reviews'][0].update(notes='PRIVATE_SENTINEL')]
        for mutate in mutations:
            value = copy.deepcopy(base); mutate(value)
            with self.subTest(mutate=mutate), self.assertRaises(error): r.validate_review_packet(value, dataset)
