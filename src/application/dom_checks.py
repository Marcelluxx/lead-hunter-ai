"""Fresh crawl binding and backward-compatible delivery of scoped DOM facts."""
import json
from datetime import datetime, timezone
from hashlib import sha256

from src.domain.audit import AuditValidationError
from src.domain.audit_evidence import public_evidence_url
from src.domain.crawl import MIN_AUDIT_PAGE_CHARS
from src.domain.dom_evidence import DomPageEvidence
from src.domain.dom_checks import (empty_dom_report, inspect_dom, validate_dom_report,
    report_status, MAX_ANALYSIS_BYTES, MAX_REPORT_BYTES)


def _need(condition):
    if not condition:
        raise AuditValidationError('dom_evidence_invalid')


def _digest(text):
    return sha256(text.encode('utf-8', errors='replace')).hexdigest()


def _coverage(report, eligible):
    inspected = sum(page['status'] == 'observed' for page in report['pages'])
    report['coverage'] = {'eligible_pages': eligible, 'inspected_pages': inspected,
        'inconclusive_pages': len(report['pages']) - inspected, 'omitted_pages': eligible - len(report['pages'])}
    report['status'] = report_status(report['coverage'])


def build_dom_report(crawl):
    _need(isinstance(crawl.pages, dict))
    pages = {url: text for url, text in crawl.pages.items()
        if isinstance(url, str) and isinstance(text, str) and len(text.strip()) >= MIN_AUDIT_PAGE_CHARS}
    _need(len(pages) <= 20)
    snapshots = getattr(crawl, 'dom_evidence', [])
    _need(isinstance(snapshots, (list, tuple)))
    latest = {}
    for snapshot in snapshots:
        _need(isinstance(snapshot, DomPageEvidence) and isinstance(snapshot.source_url, str))
        latest[snapshot.source_url] = snapshot
    report = empty_dom_report(); used_bytes = 0
    for url, text in pages.items():
        markdown_hash = _digest(text)
        proof = next((item for item in reversed(crawl.valid_evidence)
            if item.final_url == url and item.content_sha256 == markdown_hash), None)
        _need(proof is not None)
        snapshot = latest.get(url)
        if not snapshots and url == crawl.url and proof == crawl.valid_evidence[0]:
            html = crawl.raw_html_home
            claimed = getattr(crawl, 'raw_html_home_sha256', '')
            _need(isinstance(html, str) and (not claimed or claimed == _digest(html)))
            snapshot = DomPageEvidence.capture(html, proof)
        try:
            timestamp = datetime.fromisoformat(proof.retrieved_at.replace('Z', '+00:00'))
            _need(timestamp.tzinfo is not None)
            stamp = timestamp.astimezone(timezone.utc).isoformat()
        except (TypeError, ValueError, AttributeError):
            raise AuditValidationError('dom_evidence_invalid') from None
        checks = {}; reason = 'dom_not_collected'; dom_hash = None
        if snapshot is not None:
            _need(snapshot.markdown_sha256 == markdown_hash and snapshot.retrieved_at == proof.retrieved_at)
            dom_hash = snapshot.dom_sha256
            if snapshot.html is not None:
                _need(isinstance(snapshot.html, str) and _digest(snapshot.html) == dom_hash)
                length = len(snapshot.html.encode('utf-8', errors='replace'))
                if used_bytes + length > MAX_ANALYSIS_BYTES:
                    reason = 'analysis_budget'
                else:
                    used_bytes += length
                    checks, reason = inspect_dom(snapshot)
            else:
                checks, reason = inspect_dom(snapshot)
        item = {'id': 'd_' + _digest(url + '\0' + (dom_hash or '')), 'source_url': public_evidence_url(url),
            'dom_sha256': dom_hash, 'markdown_sha256': markdown_hash, 'retrieved_at': stamp,
            'status': 'observed' if reason is None else 'inconclusive', 'reason': reason, 'checks': checks}
        report['pages'].append(item); _coverage(report, len(pages))
        if len(json.dumps(report, ensure_ascii=False, allow_nan=False).encode('utf-8')) > MAX_REPORT_BYTES:
            report['pages'].pop(); _coverage(report, len(pages))
    _coverage(report, len(pages))
    return validate_dom_report(report)


def audit_with_dom_report(auditor, *, dom_report, **legacy_arguments):
    report = validate_dom_report(dom_report)
    if getattr(auditor, 'supports_dom_report', False) is True:
        legacy_arguments['dom_report'] = report
    return auditor.audit_website(**legacy_arguments)
