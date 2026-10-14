"""Fresh delivery authorization, provenance, governed contacts and bounded archives."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from uuid import UUID
from urllib.parse import urlencode
from zipfile import ZipFile, BadZipFile

from openpyxl import Workbook
from sqlalchemy import select

from src.domain.feature_licenses import FeatureAction, LicenseError
from src.domain.identity import Permission
from src.domain.job_parameters import parse_job_parameters
from src.domain.place_references import GooglePlaceReference
from src.infrastructure.models import JobModel, ProviderReferenceModel, LeadModel, LeadAttributeModel, EvidenceModel
from .job_execution import JobExecutionError
from .privacy_policy import PrivacyExportService, PrivacyPolicyError
from .reference_exports import ReferenceExportService
from .diagnostics import DiagnosticError, MAX_TOTAL_BYTES
from src.domain.audit import AuditValidationError
from src.domain.audit_evidence import validate_public_report, MAX_REPORT_BYTES
from src.domain.dom_checks import validate_dom_report, empty_dom_report, MAX_REPORT_BYTES as MAX_DOM_REPORT_BYTES
from src.domain.markup_score import validate_score_report, empty_score_report, MAX_SCORE_REPORT_BYTES

_FIELDS = frozenset({'business_name', 'website', 'category', 'website_score', 'framework',
                     'diagnosis', 'site_brief', 'cold_message', 'technology_signals', 'technology_rules_version', 'audit_report', 'dom_report', 'score_report'})


class JobResultError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class _DeliveryAccess:
    def __init__(self, service, job_id, workspace_id, auth, permission):
        self.service, self.job_id, self.workspace_id = service, job_id, workspace_id
        self.auth, self.permission = auth, permission

    def require(self, context, feature, *, action=FeatureAction.EXECUTE):
        with self.service.execution.database.session(self.workspace_id) as session:
            job, fresh = self.service._authorize(session, job_id=self.job_id, workspace_id=self.workspace_id,
                                                auth=self.auth, permission=self.permission)
            return self.service.execution.access_factory(session).require(fresh, feature, action=action)


class JobResultService:
    def __init__(self, *, execution, suppression=None, diagnostic_root=None):
        self.execution, self.suppression = execution, suppression
        self.diagnostic_root = Path(diagnostic_root) if diagnostic_root is not None else None

    def _authorize(self, session, *, job_id, workspace_id, auth, permission=Permission.VIEW_RESULTS, features=True):
        context = self.execution._context(session, workspace_id=workspace_id, user_id=auth.user_id, session_id=auth.session_id)
        if permission not in context.permissions:
            raise JobExecutionError('job_authorization_denied')
        job = session.scalar(select(JobModel).where(JobModel.id == job_id, JobModel.workspace_id == workspace_id)
                             .execution_options(populate_existing=True))
        if job is None:
            raise JobResultError('job_not_found')
        if features:
            parsed = parse_job_parameters(job.kind, job.parameters)
            for feature in parsed.required_features:
                if self.execution.access_factory is None:
                    raise LicenseError('license_storage_unavailable')
                self.execution.access_factory(session).require(context, feature, action=FeatureAction.VIEW)
            if permission == Permission.EXPORT_RESULTS and job.kind == 'discover.no_website':
                if self.execution.access_factory is None:
                    raise LicenseError('license_storage_unavailable')
                self.execution.access_factory(session).require(context, 'export.no_website', action=FeatureAction.VIEW)
        return job, context

    def authorize(self, *, job_id, workspace_id, auth, permission=Permission.VIEW_RESULTS, features=True):
        with self.execution.database.session(workspace_id) as session:
            return self._authorize(session, job_id=job_id, workspace_id=workspace_id, auth=auth,
                                   permission=permission, features=features)[1]

    def status(self, *, job_id, workspace_id, auth):
        with self.execution.database.session(workspace_id) as session:
            job, _ = self._authorize(session, job_id=job_id, workspace_id=workspace_id, auth=auth, features=False)
            return {'id': job.id, 'state': job.state, 'error_code': job.error_code, 'attempts': job.attempt_count}

    def results(self, *, job_id, workspace_id, auth):
        with self.execution.database.session(workspace_id) as session:
            job, _ = self._authorize(session, job_id=job_id, workspace_id=workspace_id, auth=auth)
            result = {'job_id': str(job.id), 'state': job.state, 'references': [], 'leads': [], 'diagnostic_available': False}
            if job.kind == 'diagnostic.website':
                result['diagnostic_available'] = bool(job.checkpoint.get('lead_ids'))
            elif job.kind == 'discover.no_website':
                ids = [UUID(value) for value in job.checkpoint.get('lead_ids', [])]
                references = session.scalars(select(ProviderReferenceModel).where(
                    ProviderReferenceModel.workspace_id == workspace_id, ProviderReferenceModel.id.in_(ids),
                    ProviderReferenceModel.provider == 'google_places')).all()
                for reference in references:
                    place_id = GooglePlaceReference(reference.external_id).place_id
                    result['references'].append({'place_id': place_id, 'maps_url': 'https://www.google.com/maps/search/?' +
                        urlencode({'api': '1', 'query': 'attività', 'query_place_id': place_id})})
            else:
                leads = session.scalars(select(LeadModel).where(LeadModel.workspace_id == workspace_id,
                                                               LeadModel.job_id == job_id)).all()
                ids = {lead.id for lead in leads}
                try:
                    contacts = [] if self.suppression is None else PrivacyExportService(self.suppression).exportable_contacts(
                        session, workspace_id=workspace_id, lead_ids=ids)
                except PrivacyPolicyError:
                    raise JobResultError('job_contact_policy_denied') from None
                for lead in leads:
                    attributes = session.scalars(select(LeadAttributeModel).where(
                        LeadAttributeModel.workspace_id == workspace_id, LeadAttributeModel.lead_id == lead.id)).all()
                    evidence = session.scalars(select(EvidenceModel).where(EvidenceModel.workspace_id == workspace_id,
                                                                          EvidenceModel.lead_id == lead.id)).all()
                    allowed = [row for row in attributes if row.field_name in _FIELDS and row.source in ('official_website', 'user_input')
                        and (row.expires_at is None or _utc(row.expires_at) > self.execution.now())]
                    report_rows = [row for row in allowed if row.field_name == 'audit_report']
                    report = _read_audit_report(report_rows, evidence)
                    dom_report = _read_dom_report([row for row in allowed if row.field_name == 'dom_report'], evidence)
                    score_report = _read_score_report([row for row in allowed if row.field_name == 'score_report'], dom_report)
                    result['leads'].append({'id': str(lead.id), 'attributes': {row.field_name: row.value_text for row in allowed
                        if row.field_name not in ('audit_report', 'dom_report', 'score_report')},
                        'audit_report': report, 'dom_report': dom_report, 'score_report': score_report,
                        'provenance': {row.field_name: {'source': row.source, 'source_url': row.source_url,
                            'collected_at': _utc(row.collected_at).isoformat(), 'evidence_id': str(row.evidence_id) if row.evidence_id else None}
                            for row in allowed},
                        'evidence': [{'id': str(row.id), 'source_url': row.source_url, 'content_sha256': row.content_sha256,
                            'collected_at': _utc(row.collected_at).isoformat()} for row in evidence],
                        'contacts': [{'kind': row.kind, 'value': row.display_value, 'source_url': row.source_url}
                            for row in contacts if row.lead_id == lead.id and row.lead_id in ids]})
        self.authorize(job_id=job_id, workspace_id=workspace_id, auth=auth)
        return result

    def render_results(self, *, job_id, workspace_id, auth):
        result = self.results(job_id=job_id, workspace_id=workspace_id, auth=auth)
        content = json.dumps(result, ensure_ascii=False, allow_nan=False).encode('utf-8')
        self._verify_snapshot(result, job_id=job_id, workspace_id=workspace_id, auth=auth)
        return content

    def _verify_snapshot(self, snapshot, *, job_id, workspace_id, auth):
        current = self.results(job_id=job_id, workspace_id=workspace_id, auth=auth)
        if current['leads'] != snapshot['leads'] or current['references'] != snapshot['references']:
            raise JobResultError('job_result_changed')

    def export(self, *, job_id, workspace_id, auth):
        result = self.results(job_id=job_id, workspace_id=workspace_id, auth=auth)
        with self.execution.database.session(workspace_id) as session:
            job, context = self._authorize(session, job_id=job_id, workspace_id=workspace_id, auth=auth)
            kind = job.kind
            artifact_ids = job.checkpoint.get('lead_ids', []) if kind == 'diagnostic.website' else []
        permission = Permission.VIEW_RESULTS if kind == 'diagnostic.website' else Permission.EXPORT_RESULTS
        self.authorize(job_id=job_id, workspace_id=workspace_id, auth=auth, permission=permission)
        if kind == 'discover.no_website':
            access = _DeliveryAccess(self, job_id, workspace_id, auth, permission)
            content = ReferenceExportService(access, lambda: self.authorize(job_id=job_id,
                workspace_id=workspace_id, auth=auth, permission=permission)).export_bytes(
                    GooglePlaceReference(row['place_id']) for row in result['references'])
        elif kind == 'diagnostic.website':
            content = self._diagnostic_bytes(job_id, workspace_id, auth, artifact_ids)
        else:
            content = _verified_workbook(result['leads'])
            self._verify_snapshot(result, job_id=job_id, workspace_id=workspace_id, auth=auth)
        self.authorize(job_id=job_id, workspace_id=workspace_id, auth=auth, permission=permission)
        return content, ('application/zip' if kind == 'diagnostic.website' else
                         'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'), permission, result

    def _diagnostic_bytes(self, job_id, workspace_id, auth, artifact_ids):
        if self.diagnostic_root is None or len(artifact_ids) != 1:
            raise JobResultError('job_artifact_unavailable')
        try:
            identity = str(UUID(artifact_ids[0]))
            root = self.diagnostic_root / str(workspace_id)
            path = root / (identity + '.zip')
            if root.is_symlink() or path.is_symlink() or not path.is_file() or path.stat().st_size > 16 * 1024 * 1024:
                raise JobResultError('job_artifact_unavailable')
            content = path.read_bytes()
            with ZipFile(BytesIO(content)) as archive:
                if archive.getinfo('manifest.json').file_size > 4096 or sum(x.file_size for x in archive.infolist()) > MAX_TOTAL_BYTES + 4096:
                    raise JobResultError('job_artifact_unavailable')
                manifest = json.loads(archive.read('manifest.json'))
            with self.execution.database.session(workspace_id) as session:
                self._authorize(session, job_id=job_id, workspace_id=workspace_id, auth=auth)
                now = self.execution.access_factory(session).licenses.clock.now_epoch()
            if (manifest.get('classification') != 'PRIVATE_REDACTED_DIAGNOSTICS' or manifest.get('schema_version') != 1
                    or manifest.get('run_id') != identity or type(manifest.get('expires_at')) is not int):
                raise JobResultError('job_artifact_unavailable')
            if manifest['expires_at'] <= now:
                raise DiagnosticError('diagnostic_expired')
            return content
        except (OSError, ValueError, KeyError, BadZipFile) as exc:
            if isinstance(exc, (JobResultError, DiagnosticError)):
                raise
            raise JobResultError('job_artifact_unavailable') from None

    def stream(self, content, *, job_id, workspace_id, auth, permission, snapshot=None):
        try:
            with self.execution.database.session(workspace_id) as session:
                job, _ = self._authorize(session, job_id=job_id, workspace_id=workspace_id, auth=auth, permission=permission)
                diagnostic = job.kind == 'diagnostic.website'
            deadline = None
            if diagnostic:
                with ZipFile(BytesIO(content)) as archive:
                    deadline = json.loads(archive.read('manifest.json'))['expires_at']
        except (LicenseError, JobExecutionError, JobResultError, BadZipFile, ValueError, KeyError):
            return
        for offset in range(0, len(content), 65536):
            try:
                self.authorize(job_id=job_id, workspace_id=workspace_id, auth=auth, permission=permission)
                if snapshot is not None and snapshot['leads']:
                    self._verify_snapshot(snapshot, job_id=job_id, workspace_id=workspace_id, auth=auth)
                if deadline is not None:
                    with self.execution.database.session(workspace_id) as session:
                        if self.execution.access_factory(session).licenses.clock.now_epoch() >= deadline:
                            return
            except (LicenseError, JobExecutionError, JobResultError):
                return
            yield content[offset:offset + 65536]


def _utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _read_audit_report(rows, evidence):
    if not rows:
        return {'schema_version': 1, 'status': 'legacy_uncited', 'findings': [], 'evidence': []}
    try:
        if len(rows) != 1 or len(rows[0].value_text.encode('utf-8')) > MAX_REPORT_BYTES:
            raise AuditValidationError('audit_evidence_invalid')
        report = validate_public_report(json.loads(rows[0].value_text))
        bound = {(item.source_url, item.content_sha256) for item in evidence}
        if any((item['source_url'], item['content_sha256']) not in bound for item in report['evidence']):
            raise AuditValidationError('audit_evidence_invalid')
        return report
    except (AuditValidationError, ValueError, TypeError, UnicodeError, RecursionError):
        raise JobResultError('job_audit_report_invalid') from None


def _read_dom_report(rows, evidence):
    if not rows:
        return empty_dom_report()
    try:
        if len(rows) != 1 or len(rows[0].value_text.encode('utf-8')) > MAX_DOM_REPORT_BYTES:
            raise AuditValidationError('dom_report_invalid')
        report = validate_dom_report(json.loads(rows[0].value_text))
        bound = {(item.source_url, item.content_sha256) for item in evidence}
        if any((item['source_url'], item['dom_sha256']) not in bound
                for item in report['pages'] if item['dom_sha256'] is not None):
            raise AuditValidationError('dom_report_invalid')
        return report
    except (AuditValidationError, ValueError, TypeError, UnicodeError, RecursionError):
        raise JobResultError('job_dom_report_invalid') from None


def _read_score_report(rows, dom_report):
    if not rows:
        return empty_score_report()
    try:
        if len(rows) != 1 or len(rows[0].value_text.encode('utf-8')) > MAX_SCORE_REPORT_BYTES:
            raise AuditValidationError('score_report_invalid')
        return validate_score_report(json.loads(rows[0].value_text), dom_report)
    except (AuditValidationError, ValueError, TypeError, UnicodeError, RecursionError):
        raise JobResultError('job_score_report_invalid') from None


def _verified_workbook(leads):
    book = Workbook(); sheet = book.active; sheet.title = 'Lead verificati'
    fields = ('business_name', 'category', 'website', 'website_score', 'framework', 'diagnosis', 'site_brief', 'cold_message',
              'technology_signals', 'technology_rules_version')
    sheet.append([*fields, 'contacts', 'provenance', 'audit_report', 'dom_report', 'markup_score', 'score_report'])
    for lead in leads:
        sheet.append([*(lead['attributes'].get(field, '') for field in fields),
            json.dumps(lead['contacts'], ensure_ascii=False), json.dumps(lead['provenance'], ensure_ascii=False),
            json.dumps(lead['audit_report'], ensure_ascii=False, allow_nan=False),
            json.dumps(lead['dom_report'], ensure_ascii=False, allow_nan=False), lead['score_report']['score'],
            json.dumps(lead['score_report'], ensure_ascii=False, allow_nan=False)])
        for cell in sheet[sheet.max_row]:
            if cell.column != len(fields) + 5:
                cell.data_type = 's'
    output = BytesIO(); book.save(output)
    return output.getvalue()
