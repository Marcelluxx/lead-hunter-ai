"""Bind an audit projection to freshly checked crawl evidence before persistence."""
from datetime import datetime, timezone
from hashlib import sha256

from src.domain.audit import AuditValidationError
from src.domain.audit_evidence import AuditEvidenceSet
from src.domain.crawl import MIN_AUDIT_PAGE_CHARS


def bind_audit_report(crawl, report):
    pages = {url: content for url, content in crawl.pages.items()
        if isinstance(content, str) and len(content.strip()) >= MIN_AUDIT_PAGE_CHARS}
    timestamps = {}
    for url, content in pages.items():
        content_hash = sha256(content.encode('utf-8', errors='replace')).hexdigest()
        matches = [item for item in crawl.valid_evidence
            if item.final_url == url and item.content_sha256 == content_hash]
        if not matches:
            raise AuditValidationError('audit_evidence_invalid')
        try:
            timestamp = datetime.fromisoformat(matches[0].retrieved_at.replace('Z', '+00:00'))
            if timestamp.tzinfo is None:
                raise ValueError('missing timezone')
            timestamps[url] = timestamp.astimezone(timezone.utc)
        except (ValueError, TypeError):
            raise AuditValidationError('audit_evidence_invalid') from None
    context = AuditEvidenceSet.from_pages(pages, collected_at=next(iter(timestamps.values()), None))
    bound = context.empty_report() if report is None else context.verify_report(report)
    actual_times = {entry.metadata['id']: timestamps[url].isoformat()
        for url, entry in zip(pages, context.pages)}
    for evidence in bound['evidence']:
        evidence['retrieved_at'] = actual_times[evidence['id']]
    for item in bound['findings']:
        for citation in item['citations']:
            citation['retrieved_at'] = actual_times[citation['evidence_id']]
    return bound
