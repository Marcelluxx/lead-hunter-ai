"""Modelli di dominio indipendenti da UI e provider esterni."""

from .audit import AuditValidationError, WebsiteAuditResult
from .crawl import (
    CrawlEvidenceError,
    CrawlResult,
    CrawlStatus,
    PageEvidence,
    ensure_auditable_pages,
)
from .contacts import (
    ContactClassification,
    ContactExtractionMethod,
    ContactKind,
    ContactPoint,
)

__all__ = [
    "AuditValidationError",
    "CrawlEvidenceError",
    "CrawlResult",
    "CrawlStatus",
    "ContactClassification",
    "ContactExtractionMethod",
    "ContactKind",
    "ContactPoint",
    "PageEvidence",
    "WebsiteAuditResult",
    "ensure_auditable_pages",
]
