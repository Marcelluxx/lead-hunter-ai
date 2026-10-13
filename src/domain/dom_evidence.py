"""Bounded private HTML tied to one admitted Markdown response."""
from dataclasses import dataclass, field
from hashlib import sha256

MAX_DOM_BYTES = 250000


@dataclass(frozen=True)
class DomPageEvidence:
    source_url: str = field(repr=False)
    markdown_sha256: str
    dom_sha256: str | None
    retrieved_at: str
    html: str | None = field(repr=False)
    failure_code: str | None = None

    @classmethod
    def capture(cls, html, page_evidence):
        reason = None; digest = None; retained = None
        if not page_evidence.valid:
            reason = 'page_not_auditable'
        elif page_evidence.content_type.split(';', 1)[0].strip().lower() not in ('text/html', 'application/xhtml+xml'):
            reason = 'unsupported_content_type'
        elif not isinstance(html, str) or not html:
            reason = 'dom_unavailable'
        else:
            encoded = html.encode('utf-8', errors='replace')
            digest = sha256(encoded).hexdigest()
            if len(encoded) > MAX_DOM_BYTES:
                reason = 'dom_too_large'
            else:
                retained = html
        return cls(page_evidence.final_url, page_evidence.content_sha256, digest,
            page_evidence.retrieved_at, retained, reason)
