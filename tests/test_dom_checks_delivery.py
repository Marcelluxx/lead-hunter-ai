import json
import unittest
from dataclasses import replace
from io import BytesIO
from uuid import UUID

import httpx
from openai import OpenAI
from openpyxl import load_workbook
from sqlalchemy import select

from src.application.provenance import build_verified_lead
from src.domain.dom_checks import empty_dom_report
from src.exporter import DataExporter
from src.infrastructure.models import EvidenceModel, LeadAttributeModel
from tests.test_audit_evidence_runtime import LEGACY
from tests.test_dom_checks_runtime import dom_crawl


def workbook_row(content):
    sheet = load_workbook(BytesIO(content)).active
    return dict(zip([cell.value for cell in sheet[1]], [cell.value for cell in sheet[2]]))


class DomDeliveryTests(unittest.TestCase):
    def test_local_workbook_appends_bounded_dom_report_without_private_text(self):
        lead = build_verified_lead(dom_crawl(), search_keyword='Studio', audit=LEGACY)
        row = workbook_row(DataExporter.export_bytes([lead], suppression_checker=lambda _: False))
        self.assertEqual(list(row)[11:13], ['Audit Report', 'DOM Report'])
        self.assertEqual(json.loads(row['DOM Report']), lead.dom_report)
        self.assertEqual(lead.provenance['dom_report'].data_classification, 'website_dom_checks')
        self.assertEqual(lead.provenance['dom_report'].confidence, 0)
        self.assertNotIn('PRIVATE_', row['DOM Report'])
        self.assertNotIn('mario.rossi', row['DOM Report'])
        historical = replace(lead, dom_report=None, score_report=None)
        row = workbook_row(DataExporter.export_bytes([historical], suppression_checker=lambda _: False))
        self.assertEqual(json.loads(row['DOM Report']), empty_dom_report())

    def test_twenty_long_unicode_urls_omit_whole_pages_without_losing_lead(self):
        crawl = dom_crawl(20, url_factory=lambda i: 'https://site.test/' + '🌐' * 160 + '/' + str(i))
        lead = build_verified_lead(crawl, search_keyword='Studio', audit=LEGACY)
        report = lead.dom_report
        self.assertEqual(report['status'], 'partial')
        self.assertEqual(report['coverage']['eligible_pages'], 20)
        self.assertGreater(report['coverage']['omitted_pages'], 0)
        self.assertEqual(len(report['pages']) + report['coverage']['omitted_pages'], 20)
        self.assertTrue(all(len(page['checks']) == 9 for page in report['pages']))
        row = workbook_row(DataExporter.export_bytes([lead], suppression_checker=lambda _: False))
        self.assertLessEqual(len(row['DOM Report'].encode('utf-8')), 24000)
        self.assertEqual(json.loads(row['DOM Report']), report)


class DomServerDeliveryTests(unittest.TestCase):
    def setUp(self):
        from tests.test_commercial_job_api import CommercialJobApiTests
        self.fx = CommercialJobApiTests(); self.fx.setUp(); self.addCleanup(self.fx.doCleanups)

    def dom_job(self):
        class Crawler:
            async def crawl(self, url):
                return dom_crawl(url_factory=lambda i: 'https://official.example.test/' + ('' if i == 0 else 'about'))
            async def close(self): pass
        self.fx.worker.runtime.crawler_factory = lambda **_: Crawler()
        self.observed = []
        def transport(request):
            body = json.loads(request.content)
            if body['model'] == 'clean': content = 'Cleaning paraphrase ' * 30
            else:
                prompt = body['messages'][1]['content']
                self.observed.append(json.loads(prompt.split('OBSERVED_DOM_CHECKS:\n')[1].split('\nORIGINAL_AUDIT_EVIDENCE:')[0]))
                content = json.dumps({**LEGACY, 'dom_report': {'PRIVATE_FAKE_REPORT': True}})
            return httpx.Response(200, json={'id': 'fixture', 'object': 'chat.completion', 'created': 1,
                'model': body['model'], 'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': content}, 'finish_reason': 'stop'}]})
        client = httpx.Client(transport=httpx.MockTransport(transport)); self.addCleanup(client.close)
        sdk = OpenAI(api_key='fixture', base_url='https://llm.test/', http_client=client, max_retries=0); self.addCleanup(sdk.close)
        self.fx.worker.runtime.auditor_client = sdk
        response = self.fx.create(kind='audit.website', parameters={'urls': ['https://official.example.test/'], 'max_pages': 2})
        self.assertEqual(response.status_code, 202, response.text)
        job_id = UUID(response.json()['id']); self.fx.worker.runtime.execute(job_id)
        return self.fx.url + '/' + str(job_id)

    def test_sdk_worker_sql_http_and_server_workbook_share_dom_proofs(self):
        url = self.dom_job()
        response = self.fx.client.get(url + '/results', headers=self.fx.headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['state'], 'completed')
        lead = response.json()['leads'][0]; report = lead['dom_report']
        self.assertEqual(report['coverage']['inspected_pages'], 2)
        self.assertEqual(self.observed, [report])
        self.assertNotIn('dom_report', lead['attributes'])
        self.assertIsInstance(lead['attributes']['website_score'], str)
        self.assertNotIn('PRIVATE_', json.dumps(report))
        with self.fx.fx.database.session(self.fx.fx.workspace.id) as session:
            attribute = session.scalar(select(LeadAttributeModel).where(LeadAttributeModel.field_name == 'dom_report'))
            self.assertEqual(json.loads(attribute.value_text), report)
            self.assertEqual(attribute.data_classification, 'website_dom_checks')
        for page in report['pages']:
            self.assertTrue(any(item['source_url'] == page['source_url'] and item['content_sha256'] == page['dom_sha256']
                for item in lead['evidence']))
        export = self.fx.client.get(url + '/export', headers=self.fx.headers)
        self.assertEqual(export.status_code, 200, export.text)
        row = workbook_row(export.content)
        self.assertEqual(list(row)[12:14], ['audit_report', 'dom_report'])
        self.assertEqual(json.loads(row['dom_report']), report)

    def test_corrupt_json_or_unbound_dom_hash_is_a_safe_delivery_error(self):
        url = self.dom_job()
        with self.fx.fx.database.session(self.fx.fx.workspace.id) as session:
            attribute = session.scalar(select(LeadAttributeModel).where(LeadAttributeModel.field_name == 'dom_report'))
            self.assertIsNotNone(attribute)
            original = attribute.value_text; attribute.value_text = '{PRIVATE_SQL_SENTINEL'
        response = self.fx.client.get(url + '/results', headers=self.fx.headers)
        self.assertEqual(response.json(), {'detail': 'job_dom_report_invalid'})
        self.assertNotIn('PRIVATE_SQL_SENTINEL', response.text)
        report = json.loads(original)
        with self.fx.fx.database.session(self.fx.fx.workspace.id) as session:
            attribute = session.scalar(select(LeadAttributeModel).where(LeadAttributeModel.field_name == 'dom_report'))
            attribute.value_text = original
            evidence = session.scalar(select(EvidenceModel).where(EvidenceModel.source_url == report['pages'][1]['source_url'],
                EvidenceModel.content_sha256 == report['pages'][1]['dom_sha256']))
            self.assertIsNotNone(evidence); evidence.content_sha256 = 'a' * 64
        response = self.fx.client.get(url + '/export', headers=self.fx.headers)
        self.assertEqual(response.json(), {'detail': 'job_dom_report_invalid'})

    def test_historical_missing_report_is_unavailable_without_changing_legacy_attributes(self):
        url = self.dom_job()
        with self.fx.fx.database.session(self.fx.fx.workspace.id) as session:
            attribute = session.scalar(select(LeadAttributeModel).where(LeadAttributeModel.field_name == 'dom_report'))
            self.assertIsNotNone(attribute); session.delete(attribute)
            score = session.scalar(select(LeadAttributeModel).where(LeadAttributeModel.field_name == 'score_report'))
            if score is not None: session.delete(score)
        response = self.fx.client.get(url + '/results', headers=self.fx.headers)
        self.assertEqual(response.status_code, 200, response.text)
        lead = response.json()['leads'][0]
        self.assertEqual(lead['dom_report'], empty_dom_report())
        self.assertTrue(all(isinstance(value, str) for value in lead['attributes'].values()))

    def test_invalid_typed_dom_measurement_is_not_returned(self):
        url = self.dom_job()
        with self.fx.fx.database.session(self.fx.fx.workspace.id) as session:
            attribute = session.scalar(select(LeadAttributeModel).where(LeadAttributeModel.field_name == 'dom_report'))
            self.assertIsNotNone(attribute)
            report = json.loads(attribute.value_text)
            report['pages'][0]['checks']['title_text']['matched'] = True
            attribute.value_text = json.dumps(report)
        response = self.fx.client.get(url + '/results', headers=self.fx.headers)
        self.assertEqual(response.json(), {'detail': 'job_dom_report_invalid'})
