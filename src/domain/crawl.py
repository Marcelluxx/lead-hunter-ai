"""Contratti di evidenza e stato per il crawling."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional

from .contacts import ContactPoint


MIN_AUDIT_PAGE_CHARS = 120
MIN_AUDIT_TOTAL_CHARS = 200


class CrawlStatus(str, Enum):
    PENDING = "pending"
    SUCCESS = "success"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    FAILED = "failed"
    EMPTY = "empty"
    INVALID_RESPONSE = "invalid_response"


class CrawlEvidenceError(ValueError):
    """Le pagine disponibili non sono sufficienti per un audit attendibile."""


@dataclass(frozen=True)
class PageEvidence:
    requested_url: str
    final_url: str
    status_code: Optional[int]
    content_type: str
    content_length: int
    content_sha256: str
    retrieved_at: str
    valid: bool
    failure_code: Optional[str] = None

    @classmethod
    def from_content(
        cls,
        *,
        requested_url: str,
        final_url: str,
        status_code: Optional[int],
        content_type: str,
        content: str,
        failure_code: Optional[str] = None,
    ) -> "PageEvidence":
        encoded = content.encode("utf-8", errors="replace")
        valid = (
            failure_code is None
            and status_code is not None
            and 200 <= status_code < 300
            and _is_supported_content_type(content_type)
            and len(content.strip()) >= MIN_AUDIT_PAGE_CHARS
        )
        return cls(
            requested_url=requested_url,
            final_url=final_url,
            status_code=status_code,
            content_type=content_type,
            content_length=len(content.strip()),
            content_sha256=hashlib.sha256(encoded).hexdigest(),
            retrieved_at=datetime.now(timezone.utc).isoformat(),
            valid=valid,
            failure_code=failure_code or (None if valid else _failure_code(status_code, content_type, content)),
        )


@dataclass
class CrawlResult:
    """Risultato applicativo del crawl, separato dal modello del provider."""

    url: str
    requested_url: str = ""
    pages: Dict[str, str] = field(default_factory=dict)
    evidence: List[PageEvidence] = field(default_factory=list)
    contacts: List[ContactPoint] = field(default_factory=list)
    raw_html_home: str = ""
    is_dynamic: bool = True
    status: CrawlStatus = CrawlStatus.PENDING
    error_code: Optional[str] = None
    error: Optional[str] = None
    blocked_request_codes: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.requested_url:
            self.requested_url = self.url

    @property
    def valid_evidence(self) -> List[PageEvidence]:
        return [item for item in self.evidence if item.valid]

    @property
    def emails(self) -> List[str]:
        """Presentation compatibility view; governance uses typed contacts."""

        return [item.display_value for item in self.contacts if item.kind.value == "email"]

    @property
    def is_auditable(self) -> bool:
        if self.status not in {CrawlStatus.SUCCESS, CrawlStatus.PARTIAL}:
            return False
        try:
            ensure_auditable_pages(self.pages)
        except CrawlEvidenceError:
            return False
        return bool(self.valid_evidence)

    @property
    def audit_rejection_reason(self) -> str:
        if self.is_auditable:
            return ""
        if self.error_code:
            return self.error_code
        try:
            ensure_auditable_pages(self.pages)
        except CrawlEvidenceError as exc:
            return str(exc)
        return self.status.value


def ensure_auditable_pages(pages: Dict[str, str]) -> None:
    """Fail-closed: richiede almeno una pagina e contenuto totale significativo."""

    if not isinstance(pages, dict) or not pages:
        raise CrawlEvidenceError("crawl_pages_empty")
    valid_lengths = [
        len(content.strip())
        for url, content in pages.items()
        if isinstance(url, str)
        and url.startswith(("http://", "https://"))
        and isinstance(content, str)
        and len(content.strip()) >= MIN_AUDIT_PAGE_CHARS
    ]
    if not valid_lengths:
        raise CrawlEvidenceError("no_valid_page_evidence")
    if sum(valid_lengths) < MIN_AUDIT_TOTAL_CHARS:
        raise CrawlEvidenceError("insufficient_total_content")


def _is_supported_content_type(content_type: str) -> bool:
    if not content_type:
        return True
    normalized = content_type.split(";", 1)[0].strip().lower()
    return normalized in {
        "text/html",
        "application/xhtml+xml",
        "text/plain",
    }


def _failure_code(status_code: Optional[int], content_type: str, content: str) -> str:
    if status_code is None:
        return "missing_status_code"
    if not 200 <= status_code < 300:
        return "http_status_not_success"
    if not _is_supported_content_type(content_type):
        return "unsupported_content_type"
    if len(content.strip()) < MIN_AUDIT_PAGE_CHARS:
        return "content_too_short"
    return "invalid_page_evidence"
