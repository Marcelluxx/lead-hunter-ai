import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx

from src.crawler import HybridCrawler
from src.domain import CrawlStatus
from src.security import SafeUrlPolicy
from tests.test_crawler_network_guard import FakeRequest, FakeRoute


HOME = "https://93.184.216.34/"
OTHER = "https://1.1.1.1/"


def operation_types(test):
    try:
        from src.crawl_runtime import CrawlControlError, CrawlLimits
        from src.robots_policy import RobotsPolicy, RobotsResponse
    except ImportError:
        test.fail("Crawler operational policy is not implemented")
    return CrawlControlError, CrawlLimits, RobotsPolicy, RobotsResponse


def page(url=HOME, status=200, links=(), final=None):
    return SimpleNamespace(url=url, redirected_url=final, success=status == 200,
        status_code=status, response_headers={"Content-Type": "text/html"},
        markdown="Servizi e contatti aziendali sul sito ufficiale. " * 12,
        html="<html><head></head><body>Pagina ufficiale</body></html>",
        links={"internal": [{"href": item} for item in links]}, error_message="raw diagnostic detail")


class RobotsOperationsTests(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_uses_pinned_ip_original_host_and_does_not_follow_redirect(self):
        from src.robots_policy import fetch_robots
        from src.security.url_policy import UrlDecision

        requests = []
        def handle(request):
            requests.append(request)
            return httpx.Response(302, headers={"Location": "https://other.test/rules.txt"})

        client = httpx.AsyncClient
        with patch("src.robots_policy.httpx.AsyncClient", side_effect=lambda **kw: client(
                transport=httpx.MockTransport(handle), **kw)) as factory:
            decision = UrlDecision("https://origin.test/robots.txt", "origin.test", 443, ("1.1.1.1",))
            result = await fetch_robots(decision)
        self.assertFalse(factory.call_args.kwargs["trust_env"])
        self.assertEqual(result.status, 302)
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0].url.host, "1.1.1.1")
        self.assertEqual(requests[0].headers["host"], "origin.test")
        self.assertEqual(requests[0].extensions["sni_hostname"], "origin.test")

    async def test_specific_groups_longest_match_and_path_encoding(self):
        error, _, robots_type, response = operation_types(self)
        fetch = AsyncMock(return_value=response(200, b"""
User-agent: *
Disallow: /
User-agent: LeadHunter
Disallow: /private*
Allow: /private/public$
Disallow: /caf%C3%A9
User-agent: leadhunter
Disallow: /team?secret=
"""))
        urls = SafeUrlPolicy()
        policy = robots_type(urls, fetch=fetch)
        for path in ("private/index", "private/public/more", "caf\u00e9", "team?secret=1"):
            with self.subTest(path=path), self.assertRaisesRegex(error, "robots_disallowed"):
                await policy.require(await urls.validate_async(HOME + path), lambda: None)
        await policy.require(await urls.validate_async(HOME + "private/public"), lambda: None)
        await policy.require(await urls.validate_async(HOME), lambda: None)
        self.assertEqual(fetch.await_count, 1)
        self.assertEqual(fetch.await_args.args[0].normalized_url, HOME + "robots.txt")

    async def test_missing_allows_and_transient_error_gets_one_retry(self):
        error, _, robots_type, response = operation_types(self)
        urls = SafeUrlPolicy()
        fetch = AsyncMock(side_effect=[response(503), response(410)])
        policy = robots_type(urls, fetch=fetch)
        await policy.require(await urls.validate_async(HOME), lambda: None)
        self.assertEqual(fetch.await_count, 2)
        fetch = AsyncMock(return_value=response(503))
        policy = robots_type(urls, fetch=fetch)
        for _ in range(2):
            with self.assertRaisesRegex(error, "robots_unavailable"):
                await policy.require(await urls.validate_async(HOME), lambda: None)
        self.assertEqual(fetch.await_count, 2)

    async def test_redirect_rechecks_destination_before_second_request(self):
        _, _, robots_type, response = operation_types(self)
        from src.security import UrlPolicyError
        urls = SafeUrlPolicy()
        fetch = AsyncMock(return_value=response(302, location="https://127.0.0.1/robots.txt"))
        policy = robots_type(urls, fetch=fetch)
        with self.assertRaises(UrlPolicyError):
            await policy.require(await urls.validate_async(HOME), lambda: None)
        self.assertEqual(fetch.await_count, 1)


class BrowserOperationsTests(unittest.IsolatedAsyncioTestCase):
    def crawler(self, *, limits=None, robots=None, visits=()):
        _, _, _, response = operation_types(self)
        fetch = robots or AsyncMock(return_value=response(404))
        crawler = HybridCrawler(limits=limits, robots_fetch=fetch)
        crawler._crawler = SimpleNamespace(arun=AsyncMock(side_effect=visits), close=AsyncMock())
        return crawler, fetch

    async def test_missing_robots_preserves_evidence_and_denied_home_never_navigates(self):
        _, _, _, response = operation_types(self)
        crawler, fetch = self.crawler(visits=[page()])
        result = await crawler.crawl(HOME)
        self.assertEqual(result.status, CrawlStatus.SUCCESS)
        self.assertTrue(result.is_auditable)
        self.assertEqual(fetch.await_count, 1)
        crawler, _ = self.crawler(robots=AsyncMock(return_value=response(200, b"User-agent: *\nDisallow: /")))
        result = await crawler.crawl(HOME)
        self.assertEqual((result.status, result.error_code), (CrawlStatus.BLOCKED, "robots_disallowed"))
        self.assertFalse(result.browser_used)
        crawler._crawler.arun.assert_not_awaited()

    async def test_internal_denial_preserves_homepage_and_skips_navigation(self):
        _, _, _, response = operation_types(self)
        crawler, _ = self.crawler(robots=AsyncMock(return_value=response(200, b"User-agent: *\nDisallow: /contact")),
            visits=[page(links=["/contact"])])
        result = await crawler.crawl(HOME)
        self.assertEqual(result.status, CrawlStatus.PARTIAL)
        self.assertTrue(result.is_auditable)
        self.assertEqual(result.evidence[-1].failure_code, "robots_disallowed")
        self.assertEqual(crawler._crawler.arun.await_count, 1)

    async def test_retry_consumes_budget_and_other_hosts_continue(self):
        _, limits, _, _ = operation_types(self)
        crawler, _ = self.crawler(limits=limits(navigations_per_host=2),
            visits=[page(status=503), page(), page(OTHER)])
        self.assertTrue((await crawler.crawl(HOME)).is_auditable)
        self.assertEqual(crawler._crawler.arun.await_count, 2)
        self.assertEqual((await crawler.crawl(HOME)).error_code, "domain_budget_exhausted")
        self.assertTrue((await crawler.crawl(OTHER)).is_auditable)
        self.assertEqual(crawler._crawler.arun.await_count, 3)

    async def test_429_and_repeated_transient_failures_open_only_one_domain(self):
        for failures in ([page(status=429)], [page(status=503), page(status=503)]):
            with self.subTest(attempts=len(failures)):
                crawler, _ = self.crawler(visits=[*failures, page(OTHER)])
                self.assertFalse((await crawler.crawl(HOME)).is_auditable)
                self.assertEqual((await crawler.crawl(HOME)).error_code, "domain_cooldown")
                self.assertTrue((await crawler.crawl(OTHER)).is_auditable)
                self.assertEqual(crawler._crawler.arun.await_count, len(failures) + 1)

    async def test_redirected_429_cools_responding_host_not_requested_host(self):
        limited = page(status=429, final=OTHER)
        limited.response_headers["Retry-After"] = "120"
        crawler, _ = self.crawler(visits=[limited, page(), page(OTHER)])
        now = 1000
        crawler._runtime.clock = lambda: now
        self.assertEqual((await crawler.crawl(HOME)).error_code, "domain_rate_limited")
        now += 61
        self.assertEqual((await crawler.crawl(OTHER)).error_code, "domain_cooldown")
        self.assertTrue((await crawler.crawl(HOME)).is_auditable)
        now += 60
        self.assertTrue((await crawler.crawl(OTHER)).is_auditable)
        self.assertEqual(crawler._crawler.arun.await_count, 3)

    async def test_late_document_change_cannot_reuse_earlier_response_metadata(self):
        crawler, _ = self.crawler()
        async def visit(*args, **kwargs):
            await crawler._remember_response(SimpleNamespace(url=HOME), None,
                response=SimpleNamespace(url=HOME, status=200, headers={"Content-Type": "text/html"}))
            return page(final=OTHER)
        crawler._crawler.arun.side_effect = visit
        result = await crawler.crawl(HOME)
        self.assertEqual(result.error_code, "navigation_response_unverified")
        self.assertFalse(result.is_auditable)
        self.assertEqual(result.pages, {})
        self.assertEqual(result.dom_evidence, [])

    async def test_late_reload_at_same_url_cannot_supply_evidence_using_old_200(self):
        crawler, _ = self.crawler()
        listeners = {}
        frame = object()
        browser_page = SimpleNamespace(url=HOME, main_frame=frame, on=listeners.__setitem__,
            remove_listener=lambda event, callback: listeners.pop(event))
        def response(status):
            request = SimpleNamespace(frame=frame, is_navigation_request=lambda: True)
            return SimpleNamespace(url=HOME, status=status, request=request,
                                   headers={"Content-Type": "text/html"})
        async def visit(*args, **kwargs):
            await crawler._validate_navigation(browser_page, None, HOME)
            await crawler._remember_response(browser_page, None, response=response(200))
            listeners["response"](response(429))
            # Crawl4AI translates exceptions from hooks into failed results.
            try:
                await crawler._before_return_html(browser_page, None, html="<html>late page</html>")
            except ValueError:
                return page(status=500)
            return page()
        crawler._crawler.arun.side_effect = visit
        result = await crawler.crawl(HOME)
        self.assertEqual(result.error_code, "domain_rate_limited")
        self.assertFalse(result.is_auditable)
        self.assertEqual((await crawler.crawl(HOME)).error_code, "domain_cooldown")
        self.assertEqual(listeners, {})

    async def test_page_timeout_cancels_provider_without_creating_evidence(self):
        _, limits, _, _ = operation_types(self)
        cancelled = asyncio.Event()
        async def hang(*args, **kwargs):
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()
        crawler, _ = self.crawler(limits=limits(page_seconds=0.03, retries=0))
        crawler._crawler.arun.side_effect = hang
        result = await crawler.crawl(HOME)
        self.assertEqual(result.error_code, "browser_timeout")
        self.assertTrue(cancelled.is_set())
        self.assertFalse(result.is_auditable)

    async def test_browser_request_budget_refuses_extra_routes(self):
        _, limits, _, _ = operation_types(self)
        crawler, _ = self.crawler(limits=limits(browser_requests=1))
        a, b = [FakeRoute(FakeRequest(HOME + name)) for name in ("one", "two")]
        await crawler._secure_route(a)
        await crawler._secure_route(b)
        self.assertTrue(a.continued)
        self.assertEqual(b.aborted_with, "blockedbyclient")
        self.assertIn("browser_request_budget", crawler._blocked_requests)

    async def test_final_destination_denied_by_robots_is_not_auditable(self):
        _, _, _, response = operation_types(self)
        async def fetch(decision):
            if decision.hostname == "1.1.1.1":
                return response(200, b"User-agent: *\nDisallow: /")
            return response(404)
        crawler, _ = self.crawler(robots=fetch, visits=[page(final=OTHER)])
        result = await crawler.crawl(HOME)
        self.assertEqual(result.error_code, "robots_disallowed")
        self.assertFalse(result.is_auditable)
        self.assertEqual(result.pages, {})
        self.assertEqual(result.dom_evidence, [])

    async def test_revocation_during_robots_prevents_browser_start(self):
        from src.application.job_execution import JobExecutionError
        _, _, _, response = operation_types(self)
        revoked = False
        async def fetch(_decision):
            nonlocal revoked
            revoked = True
            return response(404)
        def require_execute():
            if revoked:
                raise JobExecutionError("job_cancelled")
        crawler, _ = self.crawler(robots=fetch)
        crawler.execution_guard = SimpleNamespace(require_execute=require_execute)
        with self.assertRaisesRegex(JobExecutionError, "job_cancelled"):
            await crawler.crawl(HOME)
        crawler._crawler.arun.assert_not_awaited()
