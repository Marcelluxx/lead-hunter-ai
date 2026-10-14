import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from dataclasses import replace
from io import StringIO
from pathlib import Path
from unittest.mock import AsyncMock, patch

from src.application.provenance import build_verified_lead
from src.application.diagnostic_runner import run_full_diagnostic
from src.application.diagnostics import DiagnosticSession
from src.domain.feature_licenses import LicenseError
from src.domain.markup_score import build_score_report
from src.domain.provenance import VerifiedLead
from tests.test_dom_checks_runtime import dom_crawl
from tests.test_audit_evidence_runtime import LEGACY
from tests.test_compliant_pipeline import _Auditor
from tests.test_diagnostic_runtime import records
from tests.test_full_diagnostics import diagnostic_fixture


class MarkupRuntimeTests(unittest.TestCase):
    def test_builder_ignores_forged_model_index_and_keeps_ai_score_separate(self):
        lead = build_verified_lead(dom_crawl(), search_keyword='Studio', audit={**LEGACY,
            'score_report': {'score': 0, 'PRIVATE_FAKE': True}})
        self.assertEqual(lead.score_report, build_score_report(lead.dom_report))
        self.assertEqual(lead.score_report['score'], 100.0)
        self.assertEqual(lead.website_score, 7)
        self.assertEqual(lead.to_export_record()['score_report'], lead.score_report)
        provenance = lead.provenance['score_report']
        self.assertEqual(provenance.data_classification, 'website_markup_score')
        self.assertEqual(provenance.confidence, 0)
        self.assertEqual(provenance.evidence_sha256, lead.provenance['dom_report'].evidence_sha256)
        self.assertNotIn('PRIVATE_', json.dumps(lead.score_report))

    def test_missing_dom_has_null_index_and_previous_positional_dto_is_preserved(self):
        crawl = dom_crawl(1); crawl.dom_evidence = [replace(crawl.dom_evidence[0], html=None,
            dom_sha256=None, failure_code='dom_unavailable')]
        lead = build_verified_lead(crawl, search_keyword='Studio', audit=LEGACY)
        self.assertIsNone(lead.score_report['score'])
        self.assertEqual(lead.website_score, 7)
        historical = VerifiedLead('Site', 'Studio', 'https://site.test/', (), 7, 'CMS', 'Diagnosis', 'Brief', 'Message', {})
        self.assertEqual(historical.diagnosis, 'Diagnosis'); self.assertIsNone(historical.score_report)

    def test_diagnostic_summary_contains_derived_index_and_seals_without_new_audit_argument(self):
        fx = diagnostic_fixture(self); session = DiagnosticSession(fx.access, lambda: fx.context)
        class Crawler:
            crawl = AsyncMock(return_value=dom_crawl())
            close = AsyncMock()
        # Existing auditor signature remains unchanged; a fake score is never authoritative.
        class Auditor:
            calls = 0
            def audit_website(self, crawl_pages, business_name, category, rating, review_count):
                self.calls += 1
                return {**LEGACY, 'score_report': {'score': -1}}
        auditor = Auditor(); crawler = Crawler()
        result = run_full_diagnostic('https://site.test/', session=session, crawler=crawler, auditor=auditor)
        self.assertEqual(auditor.calls, 1)
        self.assertEqual(result['score_report'], build_score_report(result['dom_report']))
        summary = next(item for item in records(session) if item['kind'] == 'summary')
        self.assertEqual(summary['payload']['data']['score_report'], result['score_report'])
        crawler.close.assert_awaited_once()
        with self.assertRaisesRegex(ValueError, '^diagnostic_closed$'): session.capture('summary', {'data': {}})

    def test_revoked_diagnostic_preflight_prevents_scoring_and_audit_work(self):
        fx = diagnostic_fixture(self); session = DiagnosticSession(fx.access, lambda: fx.context)
        fx.clock.set(100)
        crawler = type('Crawler', (), {'crawl': AsyncMock(), 'close': AsyncMock()})()
        with self.assertRaises(LicenseError):
            run_full_diagnostic('https://site.test/', session=session, crawler=crawler, auditor=_Auditor())
        crawler.crawl.assert_not_called()

    def test_legacy_tester_displays_index_and_preserves_selected_field_artifact(self):
        from src.tester import run_url_test
        crawler = type('Crawler', (), {'crawl': AsyncMock(return_value=dom_crawl()), 'close': AsyncMock()})()
        output = StringIO(); original_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as task_dir:
            try:
                os.chdir(task_dir)
                with patch('src.tester.HybridCrawler', return_value=crawler), redirect_stdout(output):
                    run_url_test('https://site.test/', auditor=_Auditor(), save_artifacts=True)
                artifact = json.loads(Path('test_output/ai_audit_test.json').read_text(encoding='utf-8'))
            finally:
                os.chdir(original_cwd)
        self.assertIn('Indice markup osservato: 100.0/100', output.getvalue())
        self.assertEqual(set(artifact), {'website_score', 'diagnosis', 'site_brief', 'framework', 'cold_message'})
        self.assertEqual(artifact['website_score'], 7)

    def test_tester_prints_and_saves_partial_or_unavailable_observation_coverage(self):
        from src.tester import run_url_test
        for observed, status in [(1, 'parziale'), (0, 'non disponibile')]:
            with self.subTest(observed=observed):
                crawl = dom_crawl(20)
                crawl.dom_evidence = [snapshot if i < observed else replace(snapshot, html=None,
                    dom_sha256=None, failure_code='dom_unavailable') for i, snapshot in enumerate(crawl.dom_evidence)]
                crawler = type('Crawler', (), {'crawl': AsyncMock(return_value=crawl), 'close': AsyncMock()})()
                output = StringIO(); original_cwd = os.getcwd()
                with tempfile.TemporaryDirectory() as task_dir:
                    try:
                        os.chdir(task_dir)
                        with patch('src.tester.HybridCrawler', return_value=crawler), redirect_stdout(output):
                            run_url_test('https://site.test/', auditor=_Auditor(), save_artifacts=True)
                        saved_text = Path('test_output/test_report.txt').read_text(encoding='utf-8')
                        artifact = json.loads(Path('test_output/ai_audit_test.json').read_text(encoding='utf-8'))
                    finally:
                        os.chdir(original_cwd)
                coverage = f'Copertura DOM: {status}; {observed}/20 pagine osservate, {20 - observed} inconclusive, 0 omesse'
                self.assertIn(coverage, output.getvalue()); self.assertIn(coverage, saved_text)
                score = '100.0/100' if observed else 'non disponibile'
                self.assertIn(f'Indice markup osservato: {score}', output.getvalue())
                self.assertNotIn('score_report', artifact)
