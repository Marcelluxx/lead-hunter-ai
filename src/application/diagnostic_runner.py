"""One isolated website diagnostic execution shared by CLI, GUI and job handlers."""
import asyncio
from dataclasses import asdict

from src.domain.feature_licenses import LicenseError
from .diagnostics import DiagnosticError


def run_full_diagnostic(url, *, session, crawler, auditor) -> dict:
    session.require_execute()
    loop = asyncio.new_event_loop()
    try:
        crawl = loop.run_until_complete(crawler.crawl(url))
        session.require_execute()
        if not crawl.is_auditable:
            raise DiagnosticError('diagnostic_crawl_not_auditable')
        for source, content in crawl.pages.items():
            session.capture('processed_page', {'source': source, 'content': content})
        session.capture('evidence', {'data': [asdict(item) for item in crawl.evidence], 'state': crawl.status.value})
        result = auditor.audit_website(crawl_pages=crawl.pages, business_name='Website diagnostic',
                                       category='Testing & Diagnostics', rating=0, review_count=0)
        session.capture('summary', {'data': result})
        session.seal()
        return result
    except (LicenseError, DiagnosticError):
        raise
    except Exception:
        raise DiagnosticError('diagnostic_run_failed') from None
    finally:
        try:
            loop.run_until_complete(crawler.close())
        except Exception:
            # Cleanup errors must not reveal provider payloads or override access denial.
            pass
        finally:
            loop.close()
