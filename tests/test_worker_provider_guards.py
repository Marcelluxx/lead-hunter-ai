import asyncio
import json
import unittest
from decimal import Decimal
from unittest.mock import patch

import httpx
import requests
from openai import OpenAI
from sqlalchemy import select

from src.auditor import LeadAuditor
from src.crawler import HybridCrawler
from src.application.job_execution import JobExecutionError
from src.domain.discovery import DiscoveryQuery
from src.infrastructure.models import UsageBudgetModel, JobModel
from src.providers.discovery.google_places import GooglePlacesDiscoveryProvider
from src.config import FIELD_MASK
from tests import test_job_execution as job_tests
from tests.test_dependency_injection import _FakePromptProvider
from tests.test_crawler_network_guard import FakeRequest, FakeRoute


class WorkerProviderGuardTests(unittest.TestCase):
    def setUp(self):
        self.fx = job_tests.JobExecutionTests()
        self.fx.setUp()
        self.addCleanup(self.fx.doCleanups)

    def guard(self, kind='discover.no_website', payload=None):
        self.job_id = self.fx.job(kind=kind, payload=payload)
        return self.fx.service.guard(self.fx.service.claim(self.job_id, worker_id='fixture'))

    def cancel(self):
        self.fx.service.cancel(self.job_id, workspace_id=self.fx.workspace.id, auth=self.fx.auth)

    def test_google_cancel_during_timeout_stops_retry_and_charges_one_attempt(self):
        calls = []
        guard = self.guard()
        testcase = self
        class Http:
            def post(self, *args, **kwargs):
                calls.append(kwargs)
                testcase.cancel()
                raise requests.Timeout('private provider payload')
        provider = GooglePlacesDiscoveryProvider(api_key='fixture', places_url='https://places.test/',
            field_mask=FIELD_MASK, http_client=Http(), execution_guard=guard, sleep=lambda _: None)
        with self.assertRaisesRegex(JobExecutionError, '^job_cancelled$'):
            provider.discover(DiscoveryQuery('dentista', 0, 0))
        self.assertEqual(len(calls), 1)
        with self.fx.database.session(self.fx.workspace.id) as session:
            self.assertEqual(session.scalar(select(UsageBudgetModel)).spent, Decimal('0.1'))

    def test_real_sdk_cancel_during_429_never_retries_or_falls_back(self):
        guard = self.guard('audit.website', {'urls': ['https://site.test/'], 'max_pages': 2})
        calls = []
        def respond(request):
            calls.append(json.loads(request.content))
            self.cancel()
            return httpx.Response(429, headers={'retry-after-ms': '1'}, json={'error': {'message': 'retry'}})
        with httpx.Client(transport=httpx.MockTransport(respond)) as http_client:
            client = OpenAI(api_key='fixture', base_url='https://llm.test/', http_client=http_client)
            auditor = LeadAuditor(api_key='fixture', base_url='https://llm.test/', model='audit', model_free='clean',
                client=client, prompt_provider=_FakePromptProvider(), execution_guard=guard)
            with self.assertRaisesRegex(JobExecutionError, '^job_cancelled$'):
                auditor.audit_website({'https://site.test/': 'content ' * 80,
                    'https://site.test/about': 'about ' * 80}, 'Official site', 'dentista', 0, 0)
        self.assertEqual(len(calls), 1)
        self.assertLessEqual(calls[0]['max_tokens'], 2000)
        with self.fx.database.session(self.fx.workspace.id) as session:
            self.assertEqual(session.get(JobModel, self.job_id).call_counts, {'openrouter': 1})

    def test_browser_cancel_blocks_route_and_propagates_after_callback(self):
        guard = self.guard('audit.website', {'urls': ['https://site.test/']})
        crawler = HybridCrawler(execution_guard=guard)
        self.cancel()
        route = FakeRoute(FakeRequest('https://93.184.216.34/'))
        asyncio.run(crawler._secure_route(route))
        self.assertFalse(route.continued)
        with self.assertRaisesRegex(JobExecutionError, '^job_cancelled$'):
            crawler._check_diagnostic_failure()

    def test_browser_cancel_during_dns_check_prevents_continuing_request(self):
        guard = self.guard('audit.website', {'urls': ['https://site.test/']})
        crawler = HybridCrawler(execution_guard=guard)
        async def validate(_): self.cancel()
        with patch.object(crawler.url_policy, 'validate_async', side_effect=validate):
            route = FakeRoute(FakeRequest('https://93.184.216.34/'))
            asyncio.run(crawler._secure_route(route))
        self.assertFalse(route.continued)

    def test_server_provider_failure_cannot_become_successful_fallback_audit(self):
        guard = self.guard('audit.website', {'urls': ['https://site.test/']})
        calls = []
        def respond(request):
            calls.append(request)
            return httpx.Response(500, json={'error': {'message': 'private provider payload'}})
        with httpx.Client(transport=httpx.MockTransport(respond)) as http_client:
            client = OpenAI(api_key='fixture', base_url='https://llm.test/', http_client=http_client)
            auditor = LeadAuditor(api_key='fixture', base_url='https://llm.test/', model='audit', model_free='clean',
                client=client, prompt_provider=_FakePromptProvider(), execution_guard=guard)
            with self.assertRaisesRegex(JobExecutionError, '^provider_unavailable$'):
                auditor.audit_website({'https://site.test/': 'content ' * 80}, 'Official site', 'dentista', 0, 0)
        self.assertEqual(len(calls), 1)
