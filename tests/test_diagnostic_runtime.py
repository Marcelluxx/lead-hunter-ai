import asyncio
import json
import unittest
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from zipfile import ZipFile

from src.application.diagnostics import DiagnosticSession
from src.application.diagnostic_runner import run_full_diagnostic
from src.auditor import LeadAuditor
from src.crawler import HybridCrawler
from src.domain.feature_licenses import LicenseError
from tests.test_full_diagnostics import diagnostic_fixture
from tests.test_dependency_injection import _FakePromptProvider
from tests.test_compliant_pipeline import _Crawler, _Auditor
from tests.test_crawler_network_guard import FakeRequest, FakeRoute


def records(run):
    with ZipFile(BytesIO(run.export_bytes())) as archive:
        return [json.loads(archive.read(name)) for name in archive.namelist() if name != 'manifest.json']


class DiagnosticRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.fx = diagnostic_fixture(self)
        self.run = DiagnosticSession(self.fx.access, lambda: self.fx.context, secrets=('secret-sentinel',))

    def auditor(self, create):
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        return LeadAuditor(api_key='test', base_url='https://test.invalid', model='audit', model_free='clean',
                           client=client, prompt_provider=_FakePromptProvider(), diagnostics=self.run)

    def test_llm_requests_and_raw_responses_captured_outside_public_dto(self):
        calls = []
        def create(**kwargs):
            calls.append(kwargs)
            raw = 'Clean website content ' * 20 if kwargs['model'] == 'clean' else json.dumps({
                'website_score': 7, 'diagnosis': 'okay', 'site_brief': 'brief',
                'cold_message': 'hello', 'raw_private_field': 'secret-sentinel'})
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=raw))])
        result = self.auditor(create).audit_website({'https://x.test/': 'Website content ' * 40}, 'Clinic', 'test', 0, 0)
        self.assertEqual(len(calls), 2)
        self.assertNotIn('raw_private_field', result)
        captured = records(self.run)
        self.assertEqual(sum(x['kind'] == 'llm_request' for x in captured), 2)
        self.assertEqual(sum(x['kind'] == 'llm_response' for x in captured), 2)
        self.assertNotIn('secret-sentinel', repr(captured))
        self.assertIn('raw_private_field', repr(captured))

    def test_license_revocation_in_response_propagates_through_cleaning_fallback(self):
        calls = []
        def create(**kwargs):
            calls.append(kwargs)
            self.fx.licenses.revoke_license(self.fx.scope, self.fx.claims.license_id)
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='clean text'))])
        with self.assertRaisesRegex(LicenseError, '^license_revoked$'):
            self.auditor(create).audit_website({'https://x.test/': 'Website content ' * 40}, 'Clinic', 'test', 0, 0)
        self.assertEqual(len(calls), 1)

    def test_revoked_preflight_prevents_prompt_and_api_work(self):
        auditor = self.auditor(lambda **_: self.fail('API called'))
        self.fx.licenses.revoke_license(self.fx.scope, self.fx.claims.license_id)
        with patch.object(_FakePromptProvider, 'build_website_audit_prompt') as prompt:
            with self.assertRaises(LicenseError): self.auditor(lambda **_: self.fail('API called'))
            with self.assertRaises(LicenseError): auditor.audit_website({'https://x.test/': 'Website content ' * 40}, 'Clinic', 'test', 0, 0)
            prompt.assert_not_called()

    def test_diagnostic_api_failures_never_log_payload_or_configured_secret(self):
        def failed(**_): raise RuntimeError('secret-sentinel private prompt body')
        with self.assertLogs('src.auditor', level='INFO') as logs:
            self.auditor(failed).audit_website({'https://x.test/secret-sentinel': 'Website content ' * 40}, 'Clinic', 'test', 0, 0)
        self.assertNotIn('secret-sentinel', repr(logs.output))
        self.assertNotIn('private prompt body', repr(logs.output))

    def test_loaded_html_css_capture_uses_dom_without_network_fetch(self):
        crawler = HybridCrawler(diagnostics=self.run)
        page = SimpleNamespace(url='https://x.test/', evaluate=AsyncMock(return_value=[
            {'source': 'inline', 'rules': 'body {color:red}', 'accessible': True},
            {'source': 'https://cdn.test/style.css', 'rules': '', 'accessible': False}]))
        asyncio.run(crawler._capture_loaded_diagnostics(page, None, html='<html>secret-sentinel</html>'))
        page.evaluate.assert_awaited_once()
        data = records(self.run)
        self.assertEqual([x['kind'] for x in data], ['page', 'css'])
        self.assertNotIn('secret-sentinel', repr(data))
        self.assertIn('accessible', repr(data))
        self.fx.clock.set(100)
        route = FakeRoute(FakeRequest('https://93.184.216.34/style.css'))
        asyncio.run(crawler._secure_route(route))
        self.assertFalse(route.continued)
        self.assertIsNotNone(route.aborted_with)
        with self.assertRaises(LicenseError): crawler._check_diagnostic_failure()

    def test_runner_closes_crawler_on_success_and_failure_and_seals(self):
        crawler = _Crawler(); crawler.close = AsyncMock()
        result = run_full_diagnostic('https://x.test/', session=self.run, crawler=crawler, auditor=_Auditor())
        self.assertEqual(result['website_score'], 7)
        crawler.close.assert_awaited_once()
        self.assertIn('processed_page', [x['kind'] for x in records(self.run)])
        with self.assertRaisesRegex(ValueError, '^diagnostic_closed$'):
            self.run.capture('page', {'content': 'new'})
        second = DiagnosticSession(self.fx.access, lambda: self.fx.context)
        crawler.crawl = AsyncMock(side_effect=RuntimeError('secret-sentinel'))
        crawler.close.reset_mock()
        with self.assertRaisesRegex(ValueError, '^diagnostic_run_failed$'):
            run_full_diagnostic('https://x.test/', session=second, crawler=crawler, auditor=_Auditor())
        crawler.close.assert_awaited_once()

    def test_runner_preflight_before_crawler_and_cleanup_always(self):
        crawler = _Crawler(); crawler.crawl = AsyncMock(); crawler.close = AsyncMock()
        self.fx.clock.set(100)
        with self.assertRaises(LicenseError):
            run_full_diagnostic('https://x.test/', session=self.run, crawler=crawler, auditor=_Auditor())
        crawler.crawl.assert_not_called()
