import asyncio
import json
import os
import unittest
from dataclasses import replace
from hashlib import sha256

import httpx
from openai import OpenAI

from src.application.provenance import build_verified_lead
from src.domain.audit import AuditValidationError
from src.domain.crawl import CrawlResult, CrawlStatus, PageEvidence
from src.domain.dom_evidence import DomPageEvidence
from tests.test_dom_checks import HTML
from tests.test_audit_evidence_runtime import LEGACY
from tests.test_dependency_injection import _FakePromptProvider


def dom_crawl(count=2, *, explicit=True, html=HTML, url_factory=None):
    pages = {(url_factory(i) if url_factory else f'https://site.test/{i}'): 'Contenuto ufficiale del sito. ' * 20 for i in range(count)}
    evidence = [PageEvidence.from_content(requested_url=url, final_url=url, status_code=200, content_type='text/html', content=text)
        for url, text in pages.items()]
    crawl = CrawlResult(url=next(iter(pages)), pages=pages, evidence=evidence, raw_html_home=html,
        raw_html_home_sha256=sha256(html.encode()).hexdigest(), status=CrawlStatus.SUCCESS)
    if explicit:
        crawl.dom_evidence = [DomPageEvidence.capture(html, item) for item in evidence]
    return crawl


class DomRuntimeTests(unittest.TestCase):
    def build(self, crawl):
        try:
            from src.application.dom_checks import build_dom_report
        except ImportError:
            self.fail('DOM crawl binding is not implemented')
        return build_dom_report(crawl)

    def test_bound_report_uses_independent_dom_hash_and_trusted_collection_time(self):
        crawl = dom_crawl(); report = self.build(crawl)
        self.assertEqual(report['status'], 'complete')
        for item, evidence in zip(report['pages'], crawl.evidence):
            self.assertEqual(item['dom_sha256'], sha256(HTML.encode()).hexdigest())
            self.assertEqual(item['markdown_sha256'], evidence.content_sha256)
            self.assertEqual(item['retrieved_at'], evidence.retrieved_at)
            self.assertNotEqual(item['dom_sha256'], item['markdown_sha256'])
        self.assertNotIn('PRIVATE_', json.dumps(report))

    def test_corrupt_dom_md_or_timestamp_is_rejected(self):
        for changes in [{'html': HTML + 'PRIVATE_CHANGED'}, {'markdown_sha256': 'a' * 64},
                {'retrieved_at': '1990-01-01T00:00:00+00:00'}]:
            crawl = dom_crawl(); crawl.dom_evidence[0] = replace(crawl.dom_evidence[0], **changes)
            with self.subTest(changes=changes), self.assertRaisesRegex(AuditValidationError, '^dom_evidence_invalid$'):
                self.build(crawl)

    def test_last_duplicate_snapshot_matches_latest_page_evidence(self):
        crawl = dom_crawl(); url = crawl.url
        crawl.pages[url] += 'Contenuto aggiornato.'
        latest = PageEvidence.from_content(requested_url=url, final_url=url, status_code=200,
            content_type='text/html', content=crawl.pages[url])
        crawl.evidence.append(latest)
        html = HTML.replace('alt=""', '')
        crawl.dom_evidence.append(DomPageEvidence.capture(html, latest))
        page = self.build(crawl)['pages'][0]
        self.assertEqual(page['dom_sha256'], sha256(html.encode()).hexdigest())
        self.assertEqual(page['checks']['image_alt_attribute']['outcome'], 'fail')

    def test_legacy_homepage_and_missing_internal_snapshot_do_not_invent_absence(self):
        report = self.build(dom_crawl(explicit=False))
        self.assertEqual(report['status'], 'partial')
        self.assertEqual(report['coverage']['inspected_pages'], 1)
        self.assertEqual(report['pages'][1]['reason'], 'dom_not_collected')
        self.assertEqual(report['pages'][1]['checks'], {})

    def test_total_analysis_budget_is_explicitly_partial(self):
        html = '<html><head></head><body>' + 'A' * 200000 + '</body></html>'
        report = self.build(dom_crawl(count=10, html=html))
        self.assertEqual(report['status'], 'partial')
        self.assertEqual(report['coverage']['inspected_pages'], 9)
        self.assertEqual(report['pages'][-1]['reason'], 'analysis_budget')

    def test_model_cannot_overwrite_builder_measurements_or_change_legacy_positional_fields(self):
        crawl = dom_crawl()
        lead = build_verified_lead(crawl, search_keyword='Studio', audit={**LEGACY, 'dom_report': {'website_score': 0, 'raw_html': HTML}})
        self.assertEqual(lead.dom_report, self.build(crawl))
        self.assertEqual(lead.website_score, 7)
        result = CrawlResult('https://site.test/', '', {}, [], [], '', False, CrawlStatus.SUCCESS)
        self.assertIs(result.status, CrawlStatus.SUCCESS)

    def test_strict_legacy_auditor_keeps_old_signature(self):
        try:
            from src.application.dom_checks import audit_with_dom_report
        except ImportError:
            self.fail('Compatible DOM audit helper is not implemented')
        class LegacyAuditor:
            def audit_website(self, crawl_pages, business_name, category, rating, review_count):
                return LEGACY
        result = audit_with_dom_report(LegacyAuditor(), dom_report=self.build(dom_crawl()),
            crawl_pages=dom_crawl().pages, business_name='Studio', category='studio', rating=0, review_count=0)
        self.assertEqual(result, LEGACY)

    def test_real_sdk_receives_scoped_counts_not_html_labels_or_extra_calls(self):
        from src.auditor import LeadAuditor
        try:
            from src.application.dom_checks import audit_with_dom_report
        except ImportError:
            self.fail('Compatible DOM audit helper is not implemented')
        calls = []
        def transport(request):
            body = json.loads(request.content); calls.append(body)
            content = 'Contenuto ripulito ' * 30 if body['model'] == 'clean' else json.dumps(LEGACY)
            return httpx.Response(200, json={'id': 'fixture', 'object': 'chat.completion', 'created': 1,
                'model': body['model'], 'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': content}, 'finish_reason': 'stop'}]})
        with httpx.Client(transport=httpx.MockTransport(transport)) as client, \
                OpenAI(api_key='fixture', base_url='https://llm.test/', http_client=client, max_retries=0) as sdk:
            auditor = LeadAuditor(api_key='fixture', base_url='https://llm.test/', model='audit', model_free='clean',
                client=sdk, prompt_provider=_FakePromptProvider())
            crawl = dom_crawl(count=1); report = self.build(crawl)
            result = audit_with_dom_report(auditor, dom_report=report, crawl_pages=crawl.pages,
                business_name='Studio', category='studio', rating=0, review_count=0)
        self.assertEqual(len(calls), 2)
        prompt = calls[-1]['messages'][1]['content']
        self.assertIn('OBSERVED_DOM_CHECKS:', prompt)
        self.assertLess(prompt.index('OBSERVED_DOM_CHECKS:'), prompt.index('ORIGINAL_AUDIT_EVIDENCE:'))
        self.assertNotIn('PRIVATE_', prompt)
        self.assertNotIn('<html', prompt)
        self.assertEqual(result['audit_report']['status'], 'legacy_uncited')


@unittest.skipUnless(os.environ.get('LEADHUNTER_BROWSER_TESTS') == '1', 'Opt-in Chromium')
class DomBrowserTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_home_and_internal_snapshots_preserve_response_binding(self):
        from src.crawler import HybridCrawler
        from tests.test_crawler_runtime import WEBSITE_HTML
        class FixtureCrawler(HybridCrawler):
            async def _install_network_guard(self, page, context, **kwargs):
                async def route_fixture(route):
                    class Transport:
                        request = route.request
                        async def abort(self, reason): await route.abort(reason)
                        async def continue_(self): await route.fulfill(status=200, content_type='text/html', body=WEBSITE_HTML)
                    await self._secure_route(Transport())
                await context.route('**', route_fixture)
                return page
        for mode in ['high_fidelity', 'optimized']:
            crawler = FixtureCrawler(max_pages=2, token_mode=mode)
            try:
                result = await crawler.crawl('https://93.184.216.34/')
            finally:
                await crawler.close()
            with self.subTest(mode=mode):
                self.assertEqual(len(result.dom_evidence), 2)
                for snapshot, evidence in zip(result.dom_evidence, result.valid_evidence):
                    self.assertEqual(snapshot.markdown_sha256, evidence.content_sha256)
                    self.assertEqual(snapshot.retrieved_at, evidence.retrieved_at)
                    self.assertEqual(snapshot.dom_sha256, sha256(snapshot.html.encode()).hexdigest())
