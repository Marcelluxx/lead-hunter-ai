"""Commercial handlers keep provider discovery transient and commits idempotent."""
from __future__ import annotations

import asyncio

from src.application.diagnostic_runner import run_full_diagnostic
from src.application.job_execution import JobExecutionError
from src.application.provenance import build_verified_lead
from src.application.dom_checks import audit_with_dom_report
from src.domain.discovery import DiscoveryQuery


def _audit_site(url, *, key, category, parsed, guard, runtime, candidate=None):
    if runtime.completed(guard, key):
        return
    guard.require_execute()
    crawler = runtime.crawler(parsed, guard)
    loop = asyncio.new_event_loop()
    try:
        crawl = loop.run_until_complete(crawler.crawl(url))
        guard.require_execute()
        if not crawl.is_auditable:
            raise JobExecutionError('job_crawl_not_auditable')
        independent = build_verified_lead(crawl, search_keyword=category)
        auditor = runtime.auditor(guard)
        try:
            audit = audit_with_dom_report(auditor, dom_report=independent.dom_report,
                crawl_pages=crawl.pages, business_name=independent.business_name,
                category=category, rating=0, review_count=0)
        finally:
            runtime.close_auditor(auditor)
        guard.require_execute()
        runtime.persist_lead(guard, key, build_verified_lead(crawl, search_keyword=category, audit=audit), candidate)
    finally:
        try:
            loop.run_until_complete(crawler.close())
        finally:
            loop.close()


def _discovery(parsed, guard, runtime):
    payload = parsed.payload
    seen = set(guard.handle.checkpoint.get('completed_ids', []))
    accepted = len(guard.handle.checkpoint.get('lead_ids', []))
    if accepted >= payload['max_leads']:
        return
    provider = runtime.discovery(parsed, guard)
    for keyword in payload['keywords']:
        if accepted >= payload['max_leads']:
            return
        guard.require_execute()
        batch = provider.discover(DiscoveryQuery(keyword, payload['lat'], payload['lng']))
        guard.require_execute()
        for candidate in batch.candidates:
            key = candidate.provider + ':' + candidate.external_id
            if key in seen:
                continue
            seen.add(key)
            if bool(candidate.website_url) != (parsed.kind == 'discover.with_website'):
                continue
            if accepted >= payload['max_leads']:
                return
            if not runtime.completed(guard, key):
                if parsed.kind == 'discover.no_website':
                    runtime.persist_reference(guard, key, candidate)
                else:
                    _audit_site(candidate.website_url, key=key, category=keyword,
                        parsed=parsed, guard=guard, runtime=runtime, candidate=candidate)
            accepted += 1


def _audit(parsed, guard, runtime):
    for index, url in enumerate(parsed.payload['urls']):
        _audit_site(url, key=f'audit:{index}', category='Website audit', parsed=parsed, guard=guard, runtime=runtime)


def _diagnostic(parsed, guard, runtime):
    if runtime.completed(guard, 'diagnostic:0'):
        return
    session = runtime.diagnostic_session(parsed, guard)
    crawler = runtime.crawler(parsed, guard, diagnostics=session)
    auditor = runtime.auditor(guard, diagnostics=session)
    try:
        run_full_diagnostic(parsed.payload['url'], session=session, crawler=crawler, auditor=auditor)
        runtime.persist_diagnostic(guard, session)
    finally:
        runtime.close_auditor(auditor)


class HandlerRegistry:
    _handlers = {'discover.no_website': _discovery, 'discover.with_website': _discovery,
                 'audit.website': _audit, 'diagnostic.website': _diagnostic}

    def execute(self, parsed, guard, runtime):
        try:
            handler = self._handlers[parsed.kind]
        except KeyError:
            raise JobExecutionError('job_kind_unsupported') from None
        handler(parsed, guard, runtime)
