import contextlib
import copy
import importlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from src.benchmark.dataset import build_dataset
from tests.benchmark_helpers import snapshot


class BenchmarkCliTests(unittest.TestCase):
    def api(self):
        try:
            return importlib.import_module('src.cli.benchmark'), importlib.import_module('src.benchmark.io')
        except ImportError:
            self.fail('Offline benchmark CLI and safe file adapter are missing')

    def call(self, *args):
        self.api()
        result = subprocess.run([sys.executable, '-m', 'src.cli.benchmark', *map(str, args)],
            capture_output=True, text=True, timeout=30,
            env={k: v for k, v in os.environ.items() if not k.startswith(('LEADHUNTER_', 'GOOGLE_', 'OPENROUTER_'))})
        self.assertNotIn('Traceback', result.stdout + result.stderr)
        return result

    def test_prepare_review_evaluate_real_files_without_provider_settings(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root); source = root/'snapshots.json'; dataset = root/'dataset.json'
            reviews = root/'reviews.json'; report = root/'comparison.json'
            source.write_text(json.dumps({'schema_version': 1, 'samples': [snapshot(ai=7)]}), encoding='utf-8')
            result = self.call('prepare', '--input', source, '--prediction-version', 'code-model-A', '--out', dataset)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(self.call('review-packet', '--dataset', dataset, '--reviewer', 'rater_a', '--out', reviews).returncode, 0)
            packet = json.loads(reviews.read_text(encoding='utf-8'))
            self.assertNotIn('website_score', json.dumps(packet))
            packet['reviews'][0].update(status='reviewed', reviewed_at='2026-10-15T11:00:00+00:00',
                                       quality_score=5, intervention_priority=3)
            reviews.write_text(json.dumps(packet), encoding='utf-8')
            result = self.call('evaluate', '--dataset', dataset, '--reviews', reviews, '--out', report)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            comparison = json.loads(report.read_text(encoding='utf-8'))
            self.assertEqual(comparison['overall']['ai_vs_quality']['mae'], 2)
            self.assertEqual(comparison['samples'][0]['human_priority_mean'], 3)
            self.assertNotIn('https://', report.read_text(encoding='utf-8'))

    def test_job_adapter_strips_contacts_messages_and_unrelated_provenance(self):
        _, adapter = self.api(); row = snapshot()
        payload = {'job_id': '00000000-0000-0000-0000-000000000001', 'state': 'completed',
            'references': [], 'diagnostic_available': False, 'leads': [{
                'id': '00000000-0000-0000-0000-000000000002',
                'attributes': {'website': row['source_url'], 'website_score': '7',
                    'business_name': 'PRIVATE_NAME', 'cold_message': 'PRIVATE_MESSAGE'},
                'contacts': [{'value': 'PRIVATE_CONTACT'}], 'provenance': {'private': 'PRIVATE_PROVENANCE'},
                'dom_report': row['dom_report'], 'score_report': row['score_report'],
                'audit_report': {'description': 'PRIVATE_DIAGNOSIS'}}]}
        original = copy.deepcopy(payload)
        result = adapter.dataset_from_job(payload, prediction_version='v1', captured_at=row['captured_at'])
        self.assertEqual(result['samples'][0]['website_score'], 7)
        self.assertNotIn('PRIVATE_', json.dumps(result)); self.assertEqual(payload, original)
        payload['leads'][0]['contacts'] = [{'value': 'DIFFERENT_PRIVATE_CONTACT'}]
        self.assertEqual(adapter.dataset_from_job(payload, prediction_version='v1', captured_at=row['captured_at']), result)
        for field in ('dom_report', 'score_report'): payload['leads'][0].pop(field)
        historical = adapter.dataset_from_job(payload, prediction_version='v1', captured_at=row['captured_at'])
        self.assertIsNone(historical['samples'][0]['score_report']['score'])

    def test_adapter_accepts_actual_authorized_http_results_envelope(self):
        _, adapter = self.api()
        from datetime import datetime, timedelta, timezone
        from tests.test_dom_checks_delivery import DomServerDeliveryTests
        fixture = DomServerDeliveryTests(); fixture.setUp(); self.addCleanup(fixture.doCleanups)
        url = fixture.dom_job()
        response = fixture.fx.client.get(url + '/results', headers=fixture.fx.headers)
        self.assertEqual(response.status_code, 200, response.text)
        result = adapter.dataset_from_job(response.json(), prediction_version='fixture-only',
            captured_at=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat())
        self.assertEqual(len(result['samples']), 1)
        self.assertEqual(result['samples'][0]['website_score'], 7)
        self.assertEqual(result['samples'][0]['score_report']['score'], 100)

    def test_invalid_job_state_scores_and_missing_source_fail_closed(self):
        _, adapter = self.api()
        from src.benchmark.contracts import BenchmarkError
        base = {'job_id': '00000000-0000-0000-0000-000000000001', 'state': 'completed',
            'references': [], 'diagnostic_available': False,
            'leads': [{'attributes': {'website': 'https://site.test/', 'website_score': '7'}}]}
        for mutate in [lambda x: x.update(state='running'),
            lambda x: x['leads'][0]['attributes'].update(website_score=True),
            lambda x: x['leads'][0]['attributes'].update(website_score='7.5'),
            lambda x: x['leads'][0]['attributes'].pop('website'),
            lambda x: x['leads'][0].update(score_report={'score': 55}),
            lambda x: x.update(diagnostic_available=True),
            lambda x: x.update(references=[{'place_id': 'PRIVATE'}])]:
            value = copy.deepcopy(base); mutate(value)
            with self.assertRaises(BenchmarkError):
                adapter.dataset_from_job(value, prediction_version='v1', captured_at='2026-10-15T12:00:00Z')

    def test_duplicate_keys_nonfinite_deep_and_oversize_input_are_safe(self):
        cli, adapter = self.api()
        from src.benchmark.contracts import BenchmarkError, MAX_JSON_BYTES
        for text in ['{"schema_version":1,"schema_version":1,"PRIVATE_SECRET":7}',
                     '{"PRIVATE_SECRET":NaN}', '[' * 1100 + '"PRIVATE_SECRET"' + ']' * 1100,
                     '{"PRIVATE_SECRET":']:
            with tempfile.TemporaryDirectory() as root:
                source = Path(root)/'PRIVATE_PATH.json'; source.write_text(text, encoding='utf-8')
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    code = cli.main(['prepare', '--input', str(source), '--prediction-version', 'v1', '--out', str(Path(root)/'out.json')])
                self.assertEqual(code, 2)
                self.assertNotIn('PRIVATE', output.getvalue())
        with tempfile.TemporaryDirectory() as root:
            source = Path(root)/'large.json'
            with source.open('wb') as handle: handle.truncate(MAX_JSON_BYTES + 1)
            with self.assertRaises(BenchmarkError): adapter.load_json(source)

    def test_output_is_exclusive_and_write_failure_removes_only_its_new_file(self):
        _, adapter = self.api()
        from src.benchmark.contracts import BenchmarkError
        with tempfile.TemporaryDirectory() as root:
            target = Path(root)/'existing.json'; target.write_text('OLD_PRIVATE', encoding='utf-8')
            with self.assertRaises(BenchmarkError): adapter.write_json_new(target, {'new': 1})
            self.assertEqual(target.read_text(encoding='utf-8'), 'OLD_PRIVATE')
            target = Path(root)/'new.json'
            with patch('os.fsync', side_effect=OSError('PRIVATE_ERROR')):
                with self.assertRaises(BenchmarkError): adapter.write_json_new(target, {'new': 1})
            self.assertFalse(target.exists())
            adapter.write_json_new(target, {'new': 1})
            self.assertEqual(json.loads(target.read_text(encoding='utf-8')), {'new': 1})
            if os.name != 'nt': self.assertEqual(target.stat().st_mode & 0o777, 0o600)

    def test_packet_files_share_a_read_budget_before_evaluation(self):
        _, adapter = self.api()
        from src.benchmark.contracts import BenchmarkError
        if not hasattr(adapter, 'load_review_packets'):
            self.fail('Combined packet read budget is missing')
        with tempfile.TemporaryDirectory() as root:
            first = Path(root)/'first.json'; second = Path(root)/'second.json'
            first.write_text(json.dumps({'data': 'a' * 100}), encoding='utf-8')
            second.write_text(json.dumps({'data': 'b' * 100}), encoding='utf-8')
            with patch.object(adapter, 'MAX_JSON_BYTES', 200):
                self.assertEqual(adapter.load_review_packets([first]), [{'data': 'a' * 100}])
                with self.assertRaises(BenchmarkError): adapter.load_review_packets([first, second])

    def test_cli_input_equals_output_and_missing_from_job_timestamp_preserve_source(self):
        with tempfile.TemporaryDirectory() as root:
            source = Path(root)/'snapshots.json'
            text = json.dumps({'schema_version': 1, 'samples': [snapshot()]})
            source.write_text(text, encoding='utf-8')
            result = self.call('prepare', '--input', source, '--prediction-version', 'v1', '--out', source)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(source.read_text(encoding='utf-8'), text)
            result = self.call('prepare', '--from-job', '--input', source, '--prediction-version', 'v1', '--out', Path(root)/'out.json')
            self.assertEqual(result.returncode, 2)
            self.assertFalse((Path(root)/'out.json').exists())

    def test_review_packet_does_not_overwrite_input_or_accept_foreign_dataset(self):
        cli, _ = self.api()
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)/'dataset.json'
            text = json.dumps(build_dataset([snapshot()], 'v1')); path.write_text(text, encoding='utf-8')
            with contextlib.redirect_stdout(io.StringIO()):
                result = cli.main(['review-packet', '--dataset', str(path), '--reviewer', 'rater', '--out', str(path)])
            self.assertEqual(result, 2); self.assertEqual(path.read_text(encoding='utf-8'), text)
