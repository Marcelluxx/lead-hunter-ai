"""Build independently verified lead records from crawler evidence."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from bs4 import BeautifulSoup

from ..domain.crawl import CrawlResult
from ..domain.provenance import DataSource, FieldProvenance, VerifiedLead


def build_verified_lead(
    crawl: CrawlResult,
    *,
    search_keyword: str,
    audit: Mapping[str, Any] | None = None,
) -> VerifiedLead:
    if not crawl.is_auditable or not crawl.valid_evidence:
        raise ValueError("Il crawl non contiene evidenza verificabile.")
    evidence = crawl.valid_evidence[0]
    official_url = evidence.final_url
    collected_at = _parse_timestamp(evidence.retrieved_at)
    business_name = _official_site_name(crawl.raw_html_home, official_url)
    site_provenance = FieldProvenance(
        source=DataSource.OFFICIAL_WEBSITE,
        source_url=official_url,
        collected_at=collected_at,
        evidence_sha256=evidence.content_sha256,
    )
    user_provenance = FieldProvenance(
        source=DataSource.USER_INPUT,
        source_url=None,
        collected_at=datetime.now(timezone.utc),
    )
    audit_data = dict(audit or {})
    provenance = {
        "business_name": site_provenance,
        "website": site_provenance,
        "category": user_provenance,
    }
    for field_name in ("website_score", "framework", "diagnosis", "site_brief", "cold_message"):
        if audit_data.get(field_name) not in (None, ""):
            provenance[field_name] = site_provenance
    return VerifiedLead(
        business_name=business_name,
        category=search_keyword.strip(),
        website=official_url,
        contacts=tuple(crawl.contacts),
        website_score=audit_data.get("website_score"),
        framework=str(audit_data.get("framework") or ""),
        diagnosis=str(audit_data.get("diagnosis") or ""),
        site_brief=str(audit_data.get("site_brief") or ""),
        cold_message=str(audit_data.get("cold_message") or ""),
        provenance=provenance,
    )


def _official_site_name(html: str, url: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    meta = soup.find("meta", attrs={"property": "og:site_name"})
    if meta and meta.get("content"):
        return str(meta["content"]).strip()[:200]
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
        for separator in (" | ", " – ", " — ", " - "):
            if separator in title:
                title = title.split(separator, 1)[0]
                break
        if title:
            return title[:200]
    from urllib.parse import urlparse

    return (urlparse(url).hostname or "Sito ufficiale").removeprefix("www.")[:200]


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
