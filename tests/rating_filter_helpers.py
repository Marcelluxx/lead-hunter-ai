"""Real signed ephemeral grants; only module availability is overridden."""
from dataclasses import replace
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor, wait
from threading import Event
from unittest.mock import patch

from src.application.rating_filters import RatingFilterGuard
from src.domain.feature_licenses import FeatureContext
from src.domain.identity import Permission
from src.licensing.catalog import FeatureCatalog
from tests.reference_export_helpers import ReferenceExportFixture


class AvailableRatingCatalog(FeatureCatalog):
    def all(self):
        return tuple(replace(item, module_status='available')
                     if item.feature_id == 'discovery.rating_filters' else item
                     for item in super().all())


class RatingFilterFixture(ReferenceExportFixture):
    def __init__(self, testcase, *, features=('discovery.rating_filters',), available=True):
        if available:
            catalog = patch('src.licensing.catalog.FeatureCatalog', AvailableRatingCatalog)
            catalog.start(); testcase.addCleanup(catalog.stop)
        super().__init__(testcase, available=False)
        self.claims = replace(self.claims, features=features)
        self.context = FeatureContext(self.scope, frozenset(Permission), False, True)
        self.guard = RatingFilterGuard(self.access, lambda: self.context)


@contextmanager
def mixed_website_failure(failure):
    """A successful candidate plus a failing crawl or early/late audit, real futures."""
    from tests.test_compliant_pipeline import _Crawler, _Auditor
    crawler, auditor = _Crawler(), _Auditor()
    closed = Event()
    original_crawl, original_audit = crawler.crawl, auditor.audit_website
    count = 0

    async def crawl(url):
        nonlocal count
        count += 1
        if count == 2 and failure == 'crawl':
            raise RuntimeError('provider-secret-sentinel')
        result = await original_crawl(url)
        result.contacts = []
        result.raw_html_home = f'<html><title>Official Clinic {count}</title></html>'
        return result

    async def close():
        closed.set()

    def audit(**payload):
        if failure == 'audit_late' and not closed.wait(timeout=10):
            raise AssertionError('crawler did not close')
        if payload['business_name'] == 'Official Clinic 2':
            raise RuntimeError('provider-secret-sentinel')
        return original_audit(**payload)

    class EagerExecutor(ThreadPoolExecutor):
        def submit(self, *args, **kwargs):
            future = super().submit(*args, **kwargs)
            wait([future])
            return future

    crawler.crawl, crawler.close, auditor.audit_website = crawl, close, audit
    executor = ThreadPoolExecutor if failure == 'audit_late' else EagerExecutor
    with patch('main.HybridCrawler', return_value=crawler), \
            patch('main.filter_by_business_age', return_value=True), \
            patch('main.filter_franchise', return_value=False), \
            patch('concurrent.futures.ThreadPoolExecutor', executor):
        yield auditor
