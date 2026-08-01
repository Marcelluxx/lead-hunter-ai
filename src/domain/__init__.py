"""Modelli di dominio indipendenti da UI e provider esterni."""

from .audit import AuditValidationError, WebsiteAuditResult
from .crawl import (
    CrawlEvidenceError,
    CrawlResult,
    CrawlStatus,
    PageEvidence,
    ensure_auditable_pages,
)

__all__ = [
    "AuditValidationError",
    "CrawlEvidenceError",
    "CrawlResult",
    "CrawlStatus",
    "PageEvidence",
    "WebsiteAuditResult",
    "ensure_auditable_pages",
]
