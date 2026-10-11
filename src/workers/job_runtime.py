"""Workspace credentials, short persistence boundaries, and cooperative execution."""
from __future__ import annotations

import os
import socket
import time
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.application.contacts import ContactService
from src.application.diagnostics import DiagnosticSession, DiagnosticError, purge_diagnostic_archives
from src.application.discovery import DiscoveryPersistenceService
from src.application.job_execution import JobExecutionService, JobExecutionError
from src.application.rating_filters import RatingFilterGuard, RatingFilteredDiscoveryService
from src.application.secrets import CredentialService
from src.application.suppression import SuppressionService
from src.auditor import LeadAuditor
from src.config import FIELD_MASK
from src.crawler import HybridCrawler
from src.domain.feature_licenses import LicenseError
from src.domain.job_parameters import parse_job_parameters, JobParameterError
from src.domain.job_pricing import JobPricePolicy, JobPriceError
from src.domain.jobs import JobState
from src.domain.rating_filters import RatingFilterCriteria
from src.infrastructure.models import ProviderReferenceModel
from src.providers.discovery.google_places import GooglePlacesDiscoveryProvider, DiscoveryProviderError
from src.settings import ApplicationSettings
from src.prompting import load_prompt_provider, PromptProviderUnavailable
from .handlers import HandlerRegistry


class _LiveAccess:
    def __init__(self, runtime, guard):
        self.runtime, self.guard = runtime, guard
        self.licenses = SimpleNamespace(clock=runtime.clock)

    def require(self, context, feature, *, action=None):
        with self.guard.service.transaction(self.guard.handle) as (session, job):
            fresh = self.guard.service._origin_context(session, job)
            access = self.guard.service.access_factory(session)
            return access.require(fresh, feature, **({'action': action} if action is not None else {}))


class WorkerRuntime:
    def __init__(self, *, execution, credentials, suppression, diagnostic_root,
                 price_policy, clock, google_http=None, auditor_client=None,
                 crawler_factory=HybridCrawler, prompt_provider=None, llm_model=None,
                 llm_model_free=None, provider_settings=None, sleep=time.sleep, prompt_module='src.prompts'):
        self.execution, self.credentials = execution, credentials
        self.contacts = ContactService(suppression)
        self.persistence = DiscoveryPersistenceService()
        self.diagnostic_root = Path(diagnostic_root)
        self.price_policy, self.clock = price_policy, clock
        self.google_http, self.auditor_client = google_http, auditor_client
        self.crawler_factory, self.prompt_provider = crawler_factory, prompt_provider
        self.prompt_module = prompt_module
        self.settings = provider_settings or ApplicationSettings()
        self.llm_model = llm_model or self.settings.llm_model
        self.llm_model_free = llm_model_free or self.settings.llm_model_free
        self.sleep = sleep

    def execute(self, job_id):
        handle = self.execution.claim(job_id, worker_id=socket.gethostname())
        if handle is None:
            return
        guard = self.execution.guard(handle)
        try:
            with self.execution.transaction(handle) as (_, job):
                parsed = parse_job_parameters(job.kind, job.parameters)
                if self.price_policy.quote(parsed).to_record() != job.cost_policy:
                    raise JobExecutionError('job_price_changed')
            HandlerRegistry().execute(parsed, guard, self)
            self.execution.finish(handle, state=JobState.COMPLETED)
        except (JobExecutionError, LicenseError, DiagnosticError, JobParameterError,
                JobPriceError, DiscoveryProviderError) as exc:
            state = JobState.CANCELLED if exc.code == 'job_cancelled' else JobState.FAILED
            self.execution.finish(handle, state=state, error_code=exc.code)
        except Exception:
            self.execution.finish(handle, state=JobState.FAILED, error_code='job_execution_failed')

    def _credential(self, guard, provider):
        with self.execution.transaction(guard.handle) as (session, job):
            try:
                return self.credentials.resolve(session, workspace_id=job.workspace_id, provider=provider)
            except KeyError:
                raise JobExecutionError('job_credentials_missing') from None

    def discovery(self, parsed, guard):
        key = self._credential(guard, 'google_places')
        kwargs = {'http_client': self.google_http} if self.google_http is not None else {}
        provider = GooglePlacesDiscoveryProvider(api_key=key, places_url=self.settings.google_places_url,
            field_mask=FIELD_MASK, execution_guard=guard, sleep=self.sleep, **kwargs)
        criteria = parsed.payload.get('rating_filters')
        if criteria is not None:
            access = _LiveAccess(self, guard)
            provider = RatingFilteredDiscoveryService(provider, RatingFilterCriteria(**criteria),
                RatingFilterGuard(access, guard.require_execute))
        return provider

    def auditor(self, guard, *, diagnostics=None):
        key = self._credential(guard, 'openrouter')
        try:
            prompt_provider = self.prompt_provider or load_prompt_provider(self.prompt_module)
        except PromptProviderUnavailable:
            raise JobExecutionError('job_prompts_missing') from None
        return LeadAuditor(api_key=key, base_url=self.settings.openrouter_base_url,
            model=self.llm_model, model_free=self.llm_model_free, client=self.auditor_client,
            prompt_provider=prompt_provider, execution_guard=guard, diagnostics=diagnostics)

    def close_auditor(self, auditor):
        if self.auditor_client is None and hasattr(auditor.client, 'close'):
            auditor.client.close()

    def crawler(self, parsed, guard, *, diagnostics=None):
        payload = parsed.payload
        return self.crawler_factory(max_pages=payload['max_pages'], token_mode=payload['token_mode'],
            headless=True, execution_guard=guard, diagnostics=diagnostics)

    def diagnostic_session(self, parsed, guard):
        key = self._credential(guard, 'openrouter')
        return DiagnosticSession(_LiveAccess(self, guard), guard.require_execute,
            retention_hours=parsed.payload['retention_hours'], secrets=(key,))

    def completed(self, guard, key):
        with self.execution.transaction(guard.handle) as (_, job):
            return key in job.checkpoint.get('completed_ids', [])

    def _reference(self, session, job, candidate, lead_id=None):
        if len(candidate.external_id) > 480:
            raise JobExecutionError('job_parameters_invalid')
        query = select(ProviderReferenceModel).where(ProviderReferenceModel.workspace_id == job.workspace_id,
            ProviderReferenceModel.provider == candidate.provider, ProviderReferenceModel.external_id == candidate.external_id)
        reference = session.scalar(query)
        if reference is None:
            try:
                with session.begin_nested():
                    reference = self.persistence.persist_provider_reference(session, workspace_id=job.workspace_id,
                        job_id=job.id, candidate=candidate, lead_id=lead_id)
                    session.flush()
            except IntegrityError:
                reference = session.scalar(query)
                if reference is None:
                    raise
        return reference

    @staticmethod
    def _complete_checkpoint(job, key, record_id, phase):
        checkpoint = dict(job.checkpoint)
        completed = list(checkpoint.get('completed_ids', []))
        leads = list(checkpoint.get('lead_ids', []))
        if len(completed) >= 100 or len(leads) >= 100:
            raise JobExecutionError('job_checkpoint_invalid')
        completed.append(key); leads.append(str(record_id))
        job.checkpoint = {'phase': phase, 'cursor': len(completed), 'completed_ids': completed, 'lead_ids': leads}

    def persist_reference(self, guard, key, candidate):
        with self.execution.transaction(guard.handle) as (session, job):
            if key in job.checkpoint.get('completed_ids', []):
                return
            reference = self._reference(session, job, candidate)
            self._complete_checkpoint(job, key, reference.id, 'discovery')

    def persist_lead(self, guard, key, lead, candidate=None):
        with self.execution.transaction(guard.handle) as (session, job):
            if key in job.checkpoint.get('completed_ids', []):
                return
            record = self.persistence.persist_verified_lead(session, workspace_id=job.workspace_id, job_id=job.id, lead=lead)
            self.contacts.persist(session, workspace_id=job.workspace_id, lead_id=record.id, contacts=lead.contacts)
            if candidate is not None:
                self._reference(session, job, candidate, record.id)
            self._complete_checkpoint(job, key, record.id, 'audit')

    def persist_diagnostic(self, guard, diagnostic):
        root = self.diagnostic_root / str(guard.handle.workspace_id)
        guard.require_execute()
        purge_diagnostic_archives(root, now=self.clock.now_epoch())
        diagnostic.save(root / (str(diagnostic.run_id) + '.zip'))
        with self.execution.transaction(guard.handle) as (_, job):
            self._complete_checkpoint(job, 'diagnostic:0', diagnostic.run_id, 'finalize')

    @classmethod
    def from_environment(cls):
        import base64
        from src.infrastructure.crypto import SecretCipher
        from src.infrastructure.database import Database
        from src.application.feature_access import FeatureAccessService
        from src.application.feature_licenses import LicenseService
        from src.application.license_clock import GuardedClock, SystemClock
        from src.infrastructure.license_repository import SqlLicenseRepository, PostgresClockStore
        from src.licensing.catalog import FeatureCatalog
        from src.licensing.settings import LicenseSettings
        from src.licensing.verification import LicenseVerifier
        settings = LicenseSettings.from_environment()
        database = Database(os.environ['LEADHUNTER_DATABASE_URL'])
        installation = settings.installation_id or UUID(int=0)
        catalog = FeatureCatalog()
        clock = GuardedClock(SystemClock(), PostgresClockStore(database, installation))
        def access(session):
            if settings.trust_file is None or settings.installation_id is None:
                raise LicenseError('license_storage_unavailable')
            return FeatureAccessService(LicenseService(SqlLicenseRepository(session, installation),
                LicenseVerifier(settings.load_trusted_keys(), catalog), clock), catalog)
        try:
            credentials = CredentialService(SecretCipher.from_base64(os.environ['LEADHUNTER_MASTER_KEY_BASE64']))
            suppression = SuppressionService(base64.urlsafe_b64decode(os.environ['LEADHUNTER_SUPPRESSION_HMAC_KEY_BASE64']))
            execution = JobExecutionService(database=database, installation_id=installation, access_factory=access)
            return cls(execution=execution, credentials=credentials, suppression=suppression,
                diagnostic_root=settings.local_state_dir / 'server-diagnostics', clock=clock,
                price_policy=JobPricePolicy.from_mapping(os.environ), provider_settings=ApplicationSettings.from_mapping(os.environ),
                prompt_module=os.getenv('LEADHUNTER_PROMPT_MODULE') or 'src.prompts')
        except Exception:
            database.close_license_clock_pool(); database.engine.dispose()
            raise

    def close(self):
        self.execution.database.close_license_clock_pool()
        self.execution.database.engine.dispose()
