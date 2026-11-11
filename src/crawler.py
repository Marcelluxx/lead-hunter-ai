"""
Lead Hunter V3 — Crawl4AI Web Crawler
Uses Crawl4AI for semantic Markdown and structured link extraction.
"""

import re
import asyncio
import logging
from hashlib import sha256
from datetime import datetime
from typing import Dict, List, Optional, Set
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from playwright.async_api import Error as BrowserError
from .domain import (
    ContactExtractionMethod,
    ContactPoint,
    CrawlEvidenceError,
    CrawlResult,
    CrawlStatus,
    PageEvidence,
    ensure_auditable_pages,
)
from .security import SafeUrlPolicy, UrlPolicyError
from .domain.crawl import MIN_AUDIT_PAGE_CHARS, MIN_AUDIT_TOTAL_CHARS
from .domain.dom_evidence import DomPageEvidence
from .application.diagnostics import DiagnosticError
from .domain.feature_licenses import LicenseError
from .application.job_execution import JobExecutionError
from .crawl_runtime import CrawlControlError, CrawlLimits, CrawlRuntime
from .robots_policy import RobotsPolicy, USER_AGENT, fetch_robots, retry_delay

logger = logging.getLogger(__name__)

# Pattern URL prioritari per crawling interno
PRIORITY_PATH_PATTERNS = [
    r'/contatt', r'/contact', r'/chi-siamo', r'/about',
    r'/servi', r'/service', r'/privacy', r'/cookie',
    r'/legal', r'/impress', r'/team', r'/azienda',
]

# Regex email robusto
EMAIL_REGEX = re.compile(
    r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}',
    re.IGNORECASE
)

# Domini email da escludere (falsi positivi)
EMAIL_BLACKLIST_DOMAINS = {
    'example.com', 'sentry.io', 'wixpress.com', 'placeholder.com',
    'domain.com', 'email.com', 'yoursite.com', 'test.com',
}

# Estensioni file da escludere dalle email (immagini, asset)
EMAIL_BLACKLIST_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.ico'}


class HybridCrawler:
    """Crawler basato su Crawl4AI per estrazione di Markdown semantico ottimizzato per LLM."""

    def _log_target(self, url):
        return 'private site' if self.diagnostics is not None or self.execution_guard is not None else url

    def __init__(
        self,
        max_pages: int = 5,
        token_mode: str = "high_fidelity",
        headless: bool = True,
        url_policy: Optional[SafeUrlPolicy] = None,
        diagnostics=None,
        execution_guard=None,
        limits: Optional[CrawlLimits] = None,
        robots_fetch=fetch_robots,
    ):
        if token_mode not in ('high_fidelity', 'optimized'):
            raise ValueError('crawler_token_mode_invalid')
        self.max_pages = max_pages
        self.token_mode = token_mode
        self.headless = headless
        self.url_policy = url_policy or SafeUrlPolicy()
        self.limits = limits or CrawlLimits()
        self._runtime = CrawlRuntime(self.limits)
        self._robots = RobotsPolicy(self.url_policy, fetch=robots_fetch)
        self._crawl_lock = asyncio.Lock()
        self._deadline = None
        self._browser_requests = 0
        self._last_response = None
        self._anchor_request = None
        self._late_response = None
        self._response_listener = None
        self._navigation_error = None
        self._attempt_blocked = False
        self._crawler = None
        self._blocked_requests: List[str] = []
        self.diagnostics = diagnostics
        self.execution_guard = execution_guard
        self._diagnostic_error = None
        if diagnostics is not None:
            diagnostics.require_execute()

    def _select_markdown(self, provider_markdown, *, minimum_chars=MIN_AUDIT_PAGE_CHARS) -> str:
        if isinstance(provider_markdown, str) and not hasattr(provider_markdown, 'raw_markdown'):
            return provider_markdown
        raw = getattr(provider_markdown, 'raw_markdown', '')
        fit = getattr(provider_markdown, 'fit_markdown', '')
        raw = raw if isinstance(raw, str) else ''
        fit = fit if isinstance(fit, str) else ''
        if self.token_mode == 'optimized':
            if len(fit.strip()) >= minimum_chars:
                return fit
            if len(raw.strip()) >= MIN_AUDIT_PAGE_CHARS:
                return raw
            return fit or raw
        return raw or fit

    async def _secure_route(self, route) -> None:
        """Blocca redirect e richieste browser dirette a reti non pubbliche."""

        request = route.request
        if self.diagnostics is not None or self.execution_guard is not None:
            try:
                self._check_diagnostic_failure()
            except (LicenseError, DiagnosticError, JobExecutionError) as exc:
                self._diagnostic_error = exc
                await route.abort('blockedbyclient')
                return
        try:
            self._browser_requests += 1
            if self._browser_requests > self.limits.browser_requests:
                raise CrawlControlError("browser_request_budget")
            if getattr(request, "resource_type", None) == "media":
                await route.abort("blockedbyclient")
                return
            decision = await self._bounded(lambda: self.url_policy.validate_async(request.url))
            redirect_depth = 0
            previous = getattr(request, "redirected_from", None)
            while previous is not None:
                redirect_depth += 1
                previous = getattr(previous, "redirected_from", None)
            if redirect_depth > self.url_policy.max_redirects:
                raise UrlPolicyError("too_many_redirects", "Troppi redirect consecutivi.")
            is_navigation = getattr(request, "is_navigation_request", None)
            if is_navigation and is_navigation():
                await self._bounded(lambda: self._robots.require(decision, self._check_diagnostic_failure))
        except (UrlPolicyError, CrawlControlError) as exc:
            self._record_block(exc.code)
            logger.warning("Richiesta browser bloccata dalla URL policy: %s", exc.code)
            await route.abort("blockedbyclient")
            return
        except (LicenseError, DiagnosticError, JobExecutionError) as exc:
            self._diagnostic_error = exc
            await route.abort("blockedbyclient")
            return
        try:
            self._check_diagnostic_failure()
        except (LicenseError, DiagnosticError, JobExecutionError) as exc:
            self._diagnostic_error = exc
            await route.abort('blockedbyclient')
            return
        await route.continue_()

    async def _install_network_guard(self, page, context, **kwargs):
        await context.route("**", self._secure_route)
        return page

    async def _validate_navigation(self, page, context, url, **kwargs):
        self._check_diagnostic_failure()
        await self._bounded(lambda: self.url_policy.validate_async(url))
        self._check_diagnostic_failure()
        def observe(response):
            request = response.request
            if self._last_response is None or request is self._anchor_request:
                return
            try:
                if not request.is_navigation_request() or request.frame != page.main_frame:
                    return
                self._late_response = (self.url_policy.validate_syntax(response.url),
                                       response.status, response.headers)
            except (BrowserError, UrlPolicyError):
                return
        page.on("response", observe)
        self._response_listener = (page, observe)
        return page

    async def _remember_response(self, page, context, *, response, **kwargs):
        try:
            self._check_diagnostic_failure()
            if response is not None:
                syntax = self.url_policy.validate_syntax(response.url)
                self._last_response = (syntax, response.status, response.headers)
                self._anchor_request = getattr(response, "request", None)
                decision = await self._bounded(lambda: self.url_policy.validate_async(response.url))
                await self._bounded(lambda: self._robots.require(decision, self._check_diagnostic_failure))
        except (UrlPolicyError, CrawlControlError) as exc:
            self._navigation_error = exc
            raise
        except (LicenseError, DiagnosticError, JobExecutionError) as exc:
            self._diagnostic_error = exc
            raise
        return page

    def _rate_limit(self, hostname, headers):
        retry = next((value for key, value in (headers or {}).items() if key.lower() == "retry-after"), "")
        self._runtime.outcome(hostname, rate_limited=True, retry_after=retry_delay(retry))
        raise CrawlControlError("domain_rate_limited")

    def _require_response_binding(self, url):
        if self._late_response is not None:
            target, status, headers = self._late_response
            if status == 429:
                self._rate_limit(target.hostname, headers)
            raise CrawlControlError("navigation_response_unverified")
        if (self._last_response is None or self.url_policy.validate_syntax(url).normalized_url
                != self._last_response[0].normalized_url):
            raise CrawlControlError("navigation_response_unverified")

    async def _before_return_html(self, page, context, *, html, **kwargs):
        try:
            self._check_diagnostic_failure()
            self._require_response_binding(page.url)
            if self.diagnostics is not None and 200 <= self._last_response[1] < 300:
                await self._capture_loaded_diagnostics(page, context, html=html, **kwargs)
        except (UrlPolicyError, CrawlControlError) as exc:
            self._navigation_error = exc
            raise
        except (LicenseError, DiagnosticError, JobExecutionError) as exc:
            self._diagnostic_error = exc
            raise
        return page

    def _record_block(self, code):
        self._attempt_blocked = True
        if code not in self._blocked_requests:
            self._blocked_requests.append(code)

    async def _bounded(self, operation, *, seconds=None):
        remaining = (self._deadline - self._runtime.clock()) if self._deadline is not None else None
        if remaining is not None and remaining <= 0:
            raise CrawlControlError("crawl_timeout")
        if seconds is None and remaining is None:
            return await operation()
        limit = remaining if seconds is None else seconds if remaining is None else min(seconds, remaining)
        try:
            return await asyncio.wait_for(operation(), limit)
        except asyncio.TimeoutError:
            if remaining is not None and (seconds is None or remaining <= seconds):
                raise CrawlControlError("crawl_timeout") from None
            raise CrawlControlError("browser_timeout") from None

    async def _visit(self, decision, config):
        host = decision.hostname
        self._runtime.require(host)
        await self._bounded(lambda: self._robots.require(decision, self._check_diagnostic_failure))
        retries = self.limits.retries if self.diagnostics is None else 0
        for attempt in range(retries + 1):
            self._check_diagnostic_failure()
            self._runtime.require(host, consume=True)
            self._browser_requests = 0
            self._last_response = None
            self._anchor_request = None
            self._late_response = None
            self._navigation_error = None
            self._attempt_blocked = False
            try:
                result = await self._bounded(
                    lambda: self._crawler.arun(decision.normalized_url, config=config),
                    seconds=self.limits.page_seconds)
            except CrawlControlError as exc:
                self._check_diagnostic_failure()
                if exc.code != "browser_timeout":
                    raise
                self._runtime.outcome(host, transient=True)
                if attempt == retries:
                    raise
            else:
                self._check_diagnostic_failure()
                if self._navigation_error is not None:
                    raise self._navigation_error
                final_url = self._final_url(result, decision.normalized_url)
                if self._last_response is not None and getattr(result, "success", False):
                    self._require_response_binding(final_url)
                status, _ = self._page_metadata(result)
                response_host = (self._last_response[0].hostname if self._last_response else
                                 self.url_policy.validate_syntax(final_url).hostname) if status is not None else host
                if response_host != host:
                    self._runtime.require(response_host, consume=True)
                if status == 429:
                    headers = self._last_response[2] if self._last_response else getattr(result, "response_headers", {})
                    self._rate_limit(response_host, headers)
                transient = status == 408 or (status is not None and 500 <= status <= 599)
                transient = transient or (status is None and not getattr(result, "success", False)
                                            and not self._attempt_blocked)
                self._runtime.outcome(response_host, transient=transient)
                if not transient or attempt == retries:
                    return result
                if response_host != host:
                    self._runtime.require(response_host)
            finally:
                if self._response_listener is not None:
                    observed_page, listener = self._response_listener
                    self._response_listener = None
                    observed_page.remove_listener("response", listener)
            await self._bounded(lambda: asyncio.sleep(0.2))

    def _check_diagnostic_failure(self):
        if self._diagnostic_error is not None:
            raise self._diagnostic_error
        if self.diagnostics is not None:
            self.diagnostics.require_execute()
        if self.execution_guard is not None:
            self.execution_guard.require_execute()

    async def _capture_loaded_diagnostics(self, page, context, *, html, **kwargs):
        self._check_diagnostic_failure()
        try:
            self.diagnostics.capture('page', {'source': page.url, 'content': html})
            styles = await page.evaluate('''() => ({
                styles: Array.from(document.styleSheets).slice(0,128).map(sheet => {
                    try { const rules = Array.from(sheet.cssRules);
                        return {source: sheet.href || 'inline', accessible: true,
                            rules: rules.slice(0,1024).map(rule => rule.cssText).join('\\n'),
                            omitted_rules: Math.max(0,rules.length-1024)};
                    } catch (_) {return {source: sheet.href || 'inline', accessible: false, rules: ''};}
                }), omitted_styles: Math.max(0,document.styleSheets.length-128)
            })''')
            self.diagnostics.capture('css', {'source': page.url, 'data': styles})
        except (LicenseError, DiagnosticError, JobExecutionError) as exc:
            self._diagnostic_error = exc
            raise
        except Exception:
            self._diagnostic_error = DiagnosticError('diagnostic_capture_failed')
            raise self._diagnostic_error from None
        return page

    def _page_metadata(self, provider_result) -> tuple[Optional[int], str]:
        raw_status = (
            getattr(provider_result, "redirected_status_code", None)
            or getattr(provider_result, "status_code", None)
        )
        try:
            status_code = int(raw_status) if raw_status is not None else None
        except (TypeError, ValueError):
            status_code = None

        headers = getattr(provider_result, "response_headers", None) or {}
        if self._last_response is not None:
            _, status_code, headers = self._last_response
        content_type = ""
        if isinstance(headers, dict):
            content_type = next(
                (
                    str(value)
                    for key, value in headers.items()
                    if str(key).lower() == "content-type"
                ),
                "",
            )
        return status_code, content_type

    @staticmethod
    def _final_url(provider_result, fallback):
        return getattr(provider_result, "redirected_url", None) or getattr(provider_result, "url", None) or fallback

    async def crawl(self, url: str) -> CrawlResult:
        """
        Crawla la homepage e le pagine interne prioritarie utilizzando Crawl4AI.
        Restituisce un CrawlResult con la mappa delle pagine pulite ed email.
        """
        async with self._crawl_lock:
            self._deadline = self._runtime.clock() + self.limits.crawl_seconds
            try:
                return await self._crawl(url)
            finally:
                self._deadline = None

    async def _crawl(self, url: str) -> CrawlResult:
        result = CrawlResult(url=url, requested_url=url)
        all_contacts: Dict[str, ContactPoint] = {}
        self._check_diagnostic_failure()

        try:
            self.url_policy.reset_dns_pins()
            self._blocked_requests.clear()
            initial_decision = await self._bounded(lambda: self.url_policy.validate_async(url))
            safe_url = initial_decision.normalized_url
            result.url = safe_url
            self._runtime.require(initial_decision.hostname)
            await self._bounded(lambda: self._robots.require(initial_decision, self._check_diagnostic_failure))

            # Importa i moduli di Crawl4AI
            from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, BrowserConfig, CacheMode
            from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
            from crawl4ai.content_filter_strategy import PruningContentFilter

            # Configura il filtro dei contenuti (rimuove menu, footer, cookie banner, ecc.)
            content_filter = PruningContentFilter(
                threshold=0.45,
                min_word_threshold=15
            ) if self.token_mode == 'optimized' else None
            markdown_generator = DefaultMarkdownGenerator(
                content_filter=content_filter,
                options={"ignore_links": True, "ignore_images": True}
            )

            # Configura la sessione di crawling
            agent = BrowserConfig().user_agent + " " + USER_AGENT
            run_config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                markdown_generator=markdown_generator,
                wait_until="networkidle",
                page_timeout=max(1, int(self.limits.page_seconds * 1000)),
                max_retries=0,
                user_agent=agent,
                verbose=self.diagnostics is None and self.execution_guard is None,
            )

            # Configura il browser
            browser_config = BrowserConfig(
                headless=self.headless,
                java_script_enabled=True,
                ignore_https_errors=False,
                accept_downloads=False,
                user_agent=agent,
                verbose=self.diagnostics is None and self.execution_guard is None,
            )

            # Inizializza il crawler se non è già attivo
            if self._crawler is None:
                if self.diagnostics is not None or self.execution_guard is not None:
                    from crawl4ai.async_logger import AsyncLogger
                    class PrivateCrawlerLogger(AsyncLogger):
                        def _log(self, *args, **kwargs):
                            # Third-party errors can force verbosity; never expose their raw payloads.
                            return None
                    self._crawler = AsyncWebCrawler(config=browser_config,
                                                   logger=PrivateCrawlerLogger(verbose=False, log_file=None))
                else:
                    self._crawler = AsyncWebCrawler(config=browser_config)
                self._crawler.crawler_strategy.set_hook(
                    "on_page_context_created", self._install_network_guard
                )
                self._crawler.crawler_strategy.set_hook(
                    "before_goto", self._validate_navigation
                )
                self._crawler.crawler_strategy.set_hook("after_goto", self._remember_response)
                self._crawler.crawler_strategy.set_hook('before_return_html', self._before_return_html)
                try:
                    await self._bounded(self._crawler.start, seconds=self.limits.page_seconds)
                except (Exception, asyncio.CancelledError):
                    crawler, self._crawler = self._crawler, None
                    try:
                        await asyncio.wait_for(crawler.close(), 5)
                    except Exception:
                        logger.warning("Chiusura browser incompleta dopo avvio fallito")
                    raise

            logger.info("Crawl4AI: avvio crawling homepage per '%s'", self._log_target(safe_url))
            result.browser_used = True
            result.render_strategy = 'browser'
            home_result = await self._visit(initial_decision, run_config)
            self._check_diagnostic_failure()

            if not home_result or not home_result.success:
                result.blocked_request_codes = list(self._blocked_requests)
                if result.blocked_request_codes:
                    result.status = CrawlStatus.BLOCKED
                    result.error_code = result.blocked_request_codes[-1]
                else:
                    result.status = CrawlStatus.FAILED
                    result.error_code = "homepage_fetch_failed"
                result.error = "La homepage non è stata caricata."
                logger.error("Crawl4AI: crawl homepage fallito per '%s' (%s)", self._log_target(url), result.error_code)
                return result

            final_url = self._final_url(home_result, safe_url)
            final_decision = await self._bounded(lambda: self.url_policy.validate_async(final_url))
            await self._bounded(lambda: self._robots.require(final_decision, self._check_diagnostic_failure))
            allowed_internal_hosts = {initial_decision.hostname, final_decision.hostname}

            # Estrai l'HTML grezzo della homepage (necessario per alcuni filtri di età/e-commerce)
            result.raw_html_home = home_result.html or ""
            result.raw_html_home_sha256 = sha256(result.raw_html_home.encode('utf-8', errors='replace')).hexdigest()

            fit_md = self._select_markdown(home_result.markdown, minimum_chars=MIN_AUDIT_TOTAL_CHARS)

            result.url = final_decision.normalized_url
            home_content = self._clean_whitespace(fit_md)
            home_status, home_content_type = self._page_metadata(home_result)
            home_evidence = PageEvidence.from_content(
                requested_url=safe_url,
                final_url=result.url,
                status_code=home_status,
                content_type=home_content_type,
                content=home_content,
            )
            result.evidence.append(home_evidence)
            if not home_evidence.valid:
                result.status = (
                    CrawlStatus.EMPTY
                    if home_evidence.failure_code == "content_too_short"
                    else CrawlStatus.INVALID_RESPONSE
                )
                result.error_code = home_evidence.failure_code
                result.error = "Homepage priva di evidenza valida per l'audit."
                return result
            result.pages[result.url] = home_content
            result.dom_evidence.append(DomPageEvidence.capture(home_result.html, home_evidence))
            self._merge_contacts(
                all_contacts,
                self._extract_contacts_from_text_and_html(
                    home_result.html or "",
                    fit_md,
                    source_url=result.url,
                    collected_at=datetime.fromisoformat(home_evidence.retrieved_at),
                    evidence_sha256=home_evidence.content_sha256,
                ),
            )

            # --- SCOPERTA LINK INTERNI ---
            internal_links_raw = []
            if home_result.links and "internal" in home_result.links:
                for l in home_result.links["internal"][:256]:
                    href = l.get("href", "")
                    if href:
                        # Risolve percorsi relativi
                        try:
                            full_link_url = urljoin(result.url, href)
                        except (TypeError, ValueError):
                            continue
                        internal_links_raw.append(full_link_url)

            parsed_base = urlparse(result.url)
            base_domain = parsed_base.netloc

            priority_links = []
            seen_links = {result.url}

            for l_url in internal_links_raw:
                try:
                    link_decision = self.url_policy.validate_syntax(l_url)
                except UrlPolicyError as exc:
                    logger.debug("Link interno scartato dalla URL policy: %s", exc.code)
                    continue

                parsed_link = urlparse(link_decision.normalized_url)
                if link_decision.hostname not in allowed_internal_hosts:
                    continue
                # Solo link interni dello stesso dominio
                if parsed_link.netloc and parsed_link.netloc != base_domain:
                    continue
                if parsed_link.scheme and parsed_link.scheme not in ("http", "https"):
                    continue

                clean_link = link_decision.normalized_url
                if clean_link in seen_links:
                    continue

                # Match con i pattern dei percorsi prioritari
                path_lower = parsed_link.path.lower()
                for pattern in PRIORITY_PATH_PATTERNS:
                    if re.search(pattern, path_lower):
                        priority_links.append(clean_link)
                        seen_links.add(clean_link)
                        break

            # Limita al numero di pagine rimanenti
            priority_links = priority_links[:self.max_pages - 1]

            # --- CRAWLING PAGINE INTERNE ---
            pages_crawled = 1
            for p_url in priority_links:
                if pages_crawled >= self.max_pages:
                    break
                logger.info("Crawl4AI: avvio crawling pagina interna '%s'", self._log_target(p_url))
                try:
                    self._check_diagnostic_failure()
                    page_target = await self._bounded(lambda: self.url_policy.validate_async(
                        p_url, allowed_hosts=allowed_internal_hosts))
                    page_result = await self._visit(page_target, run_config)
                    self._check_diagnostic_failure()
                    if page_result and page_result.success:
                        page_final_url = self._final_url(page_result, p_url)
                        page_decision = await self._bounded(lambda: self.url_policy.validate_async(
                            page_final_url, allowed_hosts=allowed_internal_hosts))
                        await self._bounded(lambda: self._robots.require(page_decision, self._check_diagnostic_failure))
                        page_fit_md = self._select_markdown(page_result.markdown)

                        page_content = self._clean_whitespace(page_fit_md)
                        page_status, page_content_type = self._page_metadata(page_result)
                        page_evidence = PageEvidence.from_content(
                            requested_url=p_url,
                            final_url=page_decision.normalized_url,
                            status_code=page_status,
                            content_type=page_content_type,
                            content=page_content,
                        )
                        result.evidence.append(page_evidence)
                        if not page_evidence.valid:
                            continue
                        result.pages[page_decision.normalized_url] = page_content
                        result.dom_evidence.append(DomPageEvidence.capture(page_result.html, page_evidence))
                        self._merge_contacts(
                            all_contacts,
                            self._extract_contacts_from_text_and_html(
                                page_result.html or "",
                                page_fit_md,
                                source_url=page_decision.normalized_url,
                                collected_at=datetime.fromisoformat(page_evidence.retrieved_at),
                                evidence_sha256=page_evidence.content_sha256,
                            ),
                        )
                        pages_crawled += 1
                    else:
                        failed_status, failed_content_type = self._page_metadata(page_result)
                        result.evidence.append(
                            PageEvidence.from_content(
                                requested_url=p_url,
                                final_url=p_url,
                                status_code=failed_status,
                                content_type=failed_content_type,
                                content="",
                                failure_code="page_fetch_failed",
                            )
                        )
                except (LicenseError, DiagnosticError, JobExecutionError):
                    raise
                except (CrawlControlError, UrlPolicyError) as exc:
                    result.evidence.append(PageEvidence.from_content(requested_url=p_url,
                        final_url=p_url, status_code=None, content_type="", content="", failure_code=exc.code))
                    if exc.code in ("crawl_timeout", "domain_budget_exhausted", "domain_cooldown",
                                    "domain_rate_limited", "domain_state_capacity"):
                        break
                except Exception as e:
                    result.evidence.append(
                        PageEvidence.from_content(
                            requested_url=p_url,
                            final_url=p_url,
                            status_code=None,
                            content_type="",
                            content="",
                            failure_code="page_exception",
                        )
                    )
                    logger.debug("Errore durante il crawling di '%s' (%s)", self._log_target(p_url), type(e).__name__)

            result.contacts = sorted(
                all_contacts.values(), key=lambda item: item.normalized_value
            )
            result.blocked_request_codes = list(self._blocked_requests)
            try:
                ensure_auditable_pages(result.pages)
            except CrawlEvidenceError as exc:
                result.status = CrawlStatus.EMPTY
                result.error_code = str(exc)
                result.error = "Contenuto insufficiente per produrre un audit attendibile."
                return result
            result.status = (
                CrawlStatus.PARTIAL
                if result.blocked_request_codes
                or any(not item.valid for item in result.evidence)
                else CrawlStatus.SUCCESS
            )

        except (LicenseError, DiagnosticError, JobExecutionError):
            raise
        except CrawlControlError as exc:
            result.status = CrawlStatus.FAILED if exc.code in ("browser_timeout", "crawl_timeout") else CrawlStatus.BLOCKED
            result.error_code = exc.code
            result.error = "Scansione interrotta da un limite operativo."
            result.blocked_request_codes = list(self._blocked_requests)
        except UrlPolicyError as e:
            result.status = CrawlStatus.BLOCKED
            result.error_code = e.code
            result.error = str(e)
            logger.warning("Crawl bloccato dalla URL policy per '%s': %s", self._log_target(url), e.code)
        except Exception as e:
            result.status = CrawlStatus.FAILED
            result.error_code = "crawler_exception"
            result.error = str(e)
            logger.error("Errore critico durante il crawling di '%s' (%s)", self._log_target(url), type(e).__name__)

        return result

    def _clean_whitespace(self, text: str) -> str:
        """Pulisce gli spazi consecutivi e i ritorni a capo eccessivi per ottimizzare i token."""
        # 1. Rimuove gli spazi bianchi finali da ogni singola riga
        text = "\n".join(line.rstrip() for line in text.splitlines())
        # 2. Sostituisce 3 o più ritorni a capo consecutivi con al massimo 2
        text = re.sub(r'\n{3,}', '\n\n', text)
        # 3. Sostituisce 3 o più spazi consecutivi con un singolo spazio
        text = re.sub(r' {3,}', ' ', text)
        return text.strip()

    def _extract_contacts_from_text_and_html(
        self,
        html: str,
        markdown: str,
        *,
        source_url: str,
        collected_at: datetime,
        evidence_sha256: str,
    ) -> list[ContactPoint]:
        """Extract typed contacts with per-page evidence and source."""
        emails: dict[str, ContactExtractionMethod] = {}

        # 1. Regex su HTML e Markdown
        for match in EMAIL_REGEX.findall(html):
            emails.setdefault(match.lower(), ContactExtractionMethod.REGEX)
        for match in EMAIL_REGEX.findall(markdown):
            emails.setdefault(match.lower(), ContactExtractionMethod.REGEX)

        # 2. Mailto link in HTML
        soup = BeautifulSoup(html, "html.parser")
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            if href.startswith("mailto:"):
                email = href.replace("mailto:", "").split("?")[0].strip().lower()
                if EMAIL_REGEX.match(email):
                    emails[email] = ContactExtractionMethod.MAILTO

        # Filtra email non valide o di sistema
        contacts: list[ContactPoint] = []
        for email, method in emails.items():
            parts = email.split("@")
            if len(parts) != 2:
                continue
            domain = parts[1]
            if domain in EMAIL_BLACKLIST_DOMAINS:
                continue
            ext = "." + email.rsplit(".", 1)[-1] if "." in email else ""
            if ext in EMAIL_BLACKLIST_EXTENSIONS:
                continue
            try:
                contacts.append(
                    ContactPoint.from_email(
                        email,
                        source_url=source_url,
                        collected_at=collected_at,
                        extraction_method=method,
                        evidence_sha256=evidence_sha256,
                    )
                )
            except ValueError:
                continue
        return contacts

    @staticmethod
    def _merge_contacts(
        target: Dict[str, ContactPoint], contacts: list[ContactPoint]
    ) -> None:
        for contact in contacts:
            existing = target.get(contact.normalized_value)
            if existing is None or contact.confidence > existing.confidence:
                target[contact.normalized_value] = contact

    async def close(self):
        """Chiude la sessione attiva del browser Crawl4AI."""
        async with self._crawl_lock:
            if self._crawler:
                crawler, self._crawler = self._crawler, None
                await asyncio.wait_for(crawler.close(), 5)
