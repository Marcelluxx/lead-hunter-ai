import json
import tempfile
import unittest
from pathlib import Path
from io import BytesIO
from zipfile import ZipFile
from unittest.mock import patch

import httpx
from openai import OpenAI
from sqlalchemy import select

from src.application.secrets import CredentialService
from src.application.suppression import SuppressionService
from src.infrastructure.crypto import SecretCipher
from src.infrastructure.models import JobModel, LeadModel, LeadAttributeModel, ProviderReferenceModel, ContactModel
from src.domain.jobs import JobState
from src.workers.job_runtime import WorkerRuntime
from tests import test_job_execution as job_tests
from tests.test_compliant_pipeline import _Crawler
from tests.test_dependency_injection import _FakePromptProvider


class CommercialWorkerTests(unittest.TestCase):
    def setUp(self):
        self.fx = job_tests.JobExecutionTests(); self.fx.setUp(); self.addCleanup(self.fx.doCleanups)
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.credentials = CredentialService(SecretCipher(SecretCipher.generate_key()))
        for provider in ['google_places', 'openrouter']:
            with self.fx.database.session(self.fx.workspace.id) as session:
                self.credentials.put(session, workspace_id=self.fx.workspace.id, actor_user_id=self.fx.user.id,
                    provider=provider, value='workspace-secret-' + provider)
        self.google_calls, self.llm_calls, self.closed = [], [], []
        testcase = self
        class Http:
            def post(self, url, **kwargs):
                testcase.google_calls.append(kwargs)
                return httpx.Response(200, request=httpx.Request('POST', url), json={'places': [
                    {'id': 'place-1', 'displayName': {'text': 'PRIVATE GOOGLE NAME'},
                     **({'websiteUri': 'https://official.example.test/'} if testcase.with_site else {}),
                     'rating': 4.5, 'userRatingCount': 10}]})
        self.http = Http(); self.with_site = False
        def respond(request):
            body = json.loads(request.content); self.llm_calls.append(body)
            content = 'Official content ' * 30 if body['model'] == 'clean' else json.dumps({
                'website_score': 7, 'diagnosis': 'Verified diagnosis', 'site_brief': 'Verified brief', 'cold_message': 'Hello'})
            return httpx.Response(200, json={'id': 'fixture', 'object': 'chat.completion', 'created': 1,
                'model': body['model'], 'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': content}, 'finish_reason': 'stop'}]})
        self.http_client = httpx.Client(transport=httpx.MockTransport(respond)); self.addCleanup(self.http_client.close)
        self.sdk = OpenAI(api_key='fixture', base_url='https://llm.test/', http_client=self.http_client)
        self.addCleanup(self.sdk.close)
        class Crawler(_Crawler):
            async def close(self): testcase.closed.append(True)
        self.runtime = WorkerRuntime(execution=self.fx.service, credentials=self.credentials,
            suppression=SuppressionService(b'x' * 32), diagnostic_root=Path(self.temp.name),
            price_policy=self.fx.prices, clock=self.fx.clock, google_http=self.http, auditor_client=self.sdk,
            crawler_factory=lambda **_: Crawler(), prompt_provider=_FakePromptProvider(),
            llm_model='audit', llm_model_free='clean', sleep=lambda _: None)

    def test_reference_handler_is_idempotent_and_never_persists_provider_content(self):
        job_id = self.fx.job(payload={'lat': 0, 'lng': 0, 'keywords': ['dentista'], 'max_leads': 1})
        self.runtime.execute(job_id); self.runtime.execute(job_id)
        self.assertEqual(len(self.google_calls), 9)
        self.assertEqual(self.google_calls[0]['headers']['X-Goog-Api-Key'], 'workspace-secret-google_places')
        self.assertEqual(len(self.llm_calls), 0)
        with self.fx.database.session(self.fx.workspace.id) as session:
            job = session.get(JobModel, job_id)
            self.assertEqual(job.state, 'completed')
            self.assertEqual(len(session.scalars(select(ProviderReferenceModel)).all()), 1)
            self.assertEqual(len(session.scalars(select(LeadModel)).all()), 0)
            self.assertNotIn('PRIVATE GOOGLE NAME', json.dumps(job.checkpoint))
        second = self.fx.job(payload={'lat': 0, 'lng': 0, 'keywords': ['dentista'], 'max_leads': 1})
        self.runtime.execute(second)
        with self.fx.database.session(self.fx.workspace.id) as session:
            self.assertEqual(session.get(JobModel, second).state, 'completed')
            self.assertEqual(len(session.scalars(select(ProviderReferenceModel)).all()), 1)

    def test_website_and_audit_handlers_persist_independent_evidence_and_governed_contacts(self):
        self.with_site = True
        for kind, payload in [('discover.with_website', {'lat': 0, 'lng': 0, 'keywords': ['dentista'], 'max_leads': 1, 'max_pages': 1}),
                              ('audit.website', {'urls': ['https://official.example.test/'], 'max_pages': 1})]:
            with self.subTest(kind=kind):
                job_id = self.fx.job(kind=kind, payload=payload); self.runtime.execute(job_id)
                with self.fx.database.session(self.fx.workspace.id) as session:
                    self.assertEqual(session.get(JobModel, job_id).state, 'completed')
                    lead = session.scalar(select(LeadModel).where(LeadModel.job_id == job_id))
                    self.assertIsNotNone(lead)
                    values = session.scalars(select(LeadAttributeModel).where(LeadAttributeModel.lead_id == lead.id)).all()
                    self.assertIn('Official Clinic', [x.value_text for x in values])
                    self.assertNotIn('PRIVATE GOOGLE NAME', repr([x.value_text for x in values]))
                    self.assertEqual(len(session.scalars(select(ContactModel).where(ContactModel.lead_id == lead.id)).all()), 1)
        self.assertNotIn('PRIVATE GOOGLE NAME', json.dumps(self.llm_calls))
        self.assertEqual(len(self.closed), 2)

    def test_diagnostic_handler_saves_only_private_uuid_archive_and_separate_summary(self):
        self.fx.activate()
        job_id = self.fx.job(kind='diagnostic.website', payload={'url': 'https://official.example.test/', 'max_pages': 1})
        self.runtime.execute(job_id)
        with self.fx.database.session(self.fx.workspace.id) as session:
            job = session.get(JobModel, job_id); self.assertEqual(job.state, 'completed')
            artifact_id = job.checkpoint['lead_ids'][0]
            self.assertNotIn('prompt', json.dumps(job.checkpoint))
            self.assertEqual(len(session.scalars(select(LeadModel)).all()), 0)
        archive_path = Path(self.temp.name) / str(self.fx.workspace.id) / (artifact_id + '.zip')
        with ZipFile(archive_path) as archive:
            manifest = json.loads(archive.read('manifest.json'))
            self.assertEqual(manifest['run_id'], artifact_id)
            self.assertGreater(manifest['record_count'], 1)
        self.assertEqual(len(self.closed), 1)

    def test_resume_does_not_duplicate_committed_lead_after_worker_crash(self):
        job_id = self.fx.job(kind='audit.website', payload={'urls': ['https://official.example.test/'], 'max_pages': 1})
        original = self.fx.service.finish
        def crash(handle, **kwargs):
            if kwargs['state'] is JobState.COMPLETED: raise SystemExit('simulated process crash')
            return original(handle, **kwargs)
        with patch.object(self.fx.service, 'finish', side_effect=crash):
            with self.assertRaises(SystemExit): self.runtime.execute(job_id)
        calls = len(self.llm_calls)
        self.fx.now += __import__('datetime').timedelta(seconds=61)
        self.runtime.execute(job_id)
        self.assertEqual(len(self.llm_calls), calls)
        with self.fx.database.session(self.fx.workspace.id) as session:
            self.assertEqual(len(session.scalars(select(LeadModel)).all()), 1)
            self.assertEqual(session.get(JobModel, job_id).state, 'completed')

    def test_actor_executes_real_runtime_instead_of_placeholder_failure(self):
        from src.workers.broker import process_job
        job_id = self.fx.job()
        with patch('src.workers.job_runtime.WorkerRuntime.from_environment', return_value=self.runtime), \
             patch.object(self.runtime, 'close'):
            process_job.fn(str(job_id))
        with self.fx.database.session(self.fx.workspace.id) as session:
            self.assertEqual(session.get(JobModel, job_id).state, 'completed')

    def test_missing_workspace_key_never_uses_global_provider_key(self):
        from sqlalchemy import delete
        from src.infrastructure.models import ProviderCredentialModel
        with self.fx.database.session(self.fx.workspace.id) as session:
            session.execute(delete(ProviderCredentialModel))
        job_id = self.fx.job()
        with patch.dict('os.environ', {'GOOGLE_API_KEY': 'GLOBAL-KEY-MUST-NOT-BE-USED'}):
            self.runtime.execute(job_id)
        self.assertEqual(len(self.google_calls), 0)
        with self.fx.database.session(self.fx.workspace.id) as session:
            self.assertEqual(session.get(JobModel, job_id).error_code, 'job_credentials_missing')

    def test_rating_filters_work_in_both_modes_and_remain_transient(self):
        self.fx.activate(('discovery.rating_filters',))
        for with_site in [False, True]:
            self.with_site = with_site
            kind = 'discover.with_website' if with_site else 'discover.no_website'
            job_id = self.fx.job(kind=kind, payload={'lat': 0, 'lng': 0, 'keywords': ['dentista'],
                'max_leads': 1, 'max_pages': 1, 'rating_filters': {'min_rating': 4.0, 'max_reviews': 20}})
            self.runtime.execute(job_id)
            with self.fx.database.session(self.fx.workspace.id) as session:
                job = session.get(JobModel, job_id)
                self.assertEqual(job.state, 'completed')
                self.assertNotIn('4.5', json.dumps(job.checkpoint))
        self.assertIn('places.rating', self.google_calls[-1]['headers']['X-Goog-FieldMask'])
        self.assertNotIn('userRatingCount', json.dumps(self.llm_calls))
