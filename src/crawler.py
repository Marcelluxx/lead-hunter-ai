"""
Lead Hunter V3 — Crawl4AI Web Crawler
Replaces custom HybridCrawler with Crawl4AI, providing clean semantic Markdown
for LLM ingestion, advanced WAF/stealth bypass, and structured link extraction.
"""

import re
import asyncio
import logging
from typing import List, Optional, Set
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from .domain import (
    CrawlEvidenceError,
    CrawlResult,
    CrawlStatus,
    PageEvidence,
    ensure_auditable_pages,
)
from .security import SafeUrlPolicy, UrlPolicyError

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

    def __init__(
        self,
        max_pages: int = 5,
        token_mode: str = "high_fidelity",
        headless: bool = True,
        url_policy: Optional[SafeUrlPolicy] = None,
    ):
        self.max_pages = max_pages
        self.token_mode = token_mode
        self.headless = headless
        self.url_policy = url_policy or SafeUrlPolicy()
        self._crawler = None
        self._blocked_requests: List[str] = []

    async def _secure_route(self, route) -> None:
        """Blocca redirect e richieste browser dirette a reti non pubbliche."""

        request = route.request
        try:
            await self.url_policy.validate_async(request.url)
            redirect_depth = 0
            previous = getattr(request, "redirected_from", None)
            while previous is not None:
                redirect_depth += 1
                previous = getattr(previous, "redirected_from", None)
            if redirect_depth > self.url_policy.max_redirects:
                raise UrlPolicyError("too_many_redirects", "Troppi redirect consecutivi.")
        except UrlPolicyError as exc:
            self._blocked_requests.append(exc.code)
            logger.warning("Richiesta browser bloccata dalla URL policy: %s", exc.code)
            await route.abort("blockedbyclient")
            return
        await route.continue_()

    async def _install_network_guard(self, page, context, **kwargs):
        await context.route("**", self._secure_route)
        return page

    async def _validate_navigation(self, page, context, url, **kwargs):
        await self.url_policy.validate_async(url)
        return page

    @staticmethod
    def _page_metadata(provider_result) -> tuple[Optional[int], str]:
        raw_status = (
            getattr(provider_result, "redirected_status_code", None)
            or getattr(provider_result, "status_code", None)
        )
        try:
            status_code = int(raw_status) if raw_status is not None else None
        except (TypeError, ValueError):
            status_code = None

        headers = getattr(provider_result, "response_headers", None) or {}
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

    async def crawl(self, url: str) -> CrawlResult:
        """
        Crawla la homepage e le pagine interne prioritarie utilizzando Crawl4AI.
        Restituisce un CrawlResult con la mappa delle pagine pulite ed email.
        """
        result = CrawlResult(url=url, requested_url=url)
        all_emails: Set[str] = set()

        try:
            self.url_policy.reset_dns_pins()
            self._blocked_requests.clear()
            initial_decision = await self.url_policy.validate_async(url)
            safe_url = initial_decision.normalized_url
            result.url = safe_url

            # Importa i moduli di Crawl4AI
            from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, BrowserConfig, CacheMode
            from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
            from crawl4ai.content_filter_strategy import PruningContentFilter

            # Configura il filtro dei contenuti (rimuove menu, footer, cookie banner, ecc.)
            content_filter = PruningContentFilter(
                threshold=0.45,
                min_word_threshold=15
            )
            markdown_generator = DefaultMarkdownGenerator(
                content_filter=content_filter,
                options={"ignore_links": True, "ignore_images": True}
            )

            # Configura la sessione di crawling
            run_config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                markdown_generator=markdown_generator,
                wait_until="networkidle",
                page_timeout=25000
            )

            # Configura il browser
            browser_config = BrowserConfig(
                headless=self.headless,
                java_script_enabled=True
            )

            # Inizializza il crawler se non è già attivo
            if self._crawler is None:
                self._crawler = AsyncWebCrawler(config=browser_config)
                self._crawler.crawler_strategy.set_hook(
                    "on_page_context_created", self._install_network_guard
                )
                self._crawler.crawler_strategy.set_hook(
                    "before_goto", self._validate_navigation
                )
                await self._crawler.start()

            logger.info(f"Crawl4AI: avvio crawling homepage per '{safe_url}'")
            home_result = await self._crawler.arun(safe_url, config=run_config)

            if not home_result or not home_result.success:
                result.blocked_request_codes = list(self._blocked_requests)
                if result.blocked_request_codes:
                    result.status = CrawlStatus.BLOCKED
                    result.error_code = result.blocked_request_codes[-1]
                else:
                    result.status = CrawlStatus.FAILED
                    result.error_code = "homepage_fetch_failed"
                result.error = home_result.error_message if home_result else "Errore sconosciuto durante il crawl."
                logger.error(f"Crawl4AI: crawl homepage fallito per '{url}': {result.error}")
                return result

            final_url = getattr(home_result, "url", None) or safe_url
            final_decision = await self.url_policy.validate_async(final_url)
            allowed_internal_hosts = {initial_decision.hostname, final_decision.hostname}

            # Estrai l'HTML grezzo della homepage (necessario per alcuni filtri di età/e-commerce)
            result.raw_html_home = home_result.html or ""

            # Ottieni il markdown fit (semantico pulito) o quello predefinito in caso di assenza
            fit_md = ""
            if home_result.markdown:
                if hasattr(home_result.markdown, "fit_markdown") and home_result.markdown.fit_markdown:
                    fit_md = home_result.markdown.fit_markdown
                
                # Se il fit_markdown è assente o eccessivamente corto, ripiega su raw_markdown
                if len(fit_md.strip()) < 100:
                    if hasattr(home_result.markdown, "raw_markdown") and home_result.markdown.raw_markdown:
                        fit_md = home_result.markdown.raw_markdown
                    else:
                        fit_md = str(home_result.markdown)

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
            all_emails.update(self._extract_emails_from_text_and_html(home_result.html or "", fit_md))

            # --- SCOPERTA LINK INTERNI ---
            internal_links_raw = []
            if home_result.links and "internal" in home_result.links:
                for l in home_result.links["internal"]:
                    href = l.get("href", "")
                    if href:
                        # Risolve percorsi relativi
                        full_link_url = urljoin(result.url, href)
                        internal_links_raw.append(full_link_url)

            parsed_base = urlparse(result.url)
            base_domain = parsed_base.netloc

            priority_links = []
            seen_links = {result.url}

            for l_url in internal_links_raw:
                try:
                    link_decision = await self.url_policy.validate_async(
                        l_url, allowed_hosts=allowed_internal_hosts
                    )
                except UrlPolicyError as exc:
                    logger.debug("Link interno scartato dalla URL policy: %s", exc.code)
                    continue

                parsed_link = urlparse(link_decision.normalized_url)
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
                logger.info(f"Crawl4AI: avvio crawling pagina interna '{p_url}'")
                try:
                    page_result = await self._crawler.arun(p_url, config=run_config)
                    if page_result and page_result.success:
                        page_final_url = getattr(page_result, "url", None) or p_url
                        page_decision = await self.url_policy.validate_async(
                            page_final_url, allowed_hosts=allowed_internal_hosts
                        )
                        page_fit_md = ""
                        if page_result.markdown:
                            if hasattr(page_result.markdown, "fit_markdown") and page_result.markdown.fit_markdown:
                                page_fit_md = page_result.markdown.fit_markdown
                            
                            # Se il fit_markdown è assente o eccessivamente corto, ripiega su raw_markdown
                            if len(page_fit_md.strip()) < 100:
                                if hasattr(page_result.markdown, "raw_markdown") and page_result.markdown.raw_markdown:
                                    page_fit_md = page_result.markdown.raw_markdown
                                else:
                                    page_fit_md = str(page_result.markdown)

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
                        all_emails.update(self._extract_emails_from_text_and_html(page_result.html or "", page_fit_md))
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
                    logger.debug(f"Errore durante il crawling di '{p_url}': {e}")

            result.emails = sorted(all_emails)
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

        except UrlPolicyError as e:
            result.status = CrawlStatus.BLOCKED
            result.error_code = e.code
            result.error = str(e)
            logger.warning(f"Crawl bloccato dalla URL policy per '{url}': {e.code}")
        except Exception as e:
            result.status = CrawlStatus.FAILED
            result.error_code = "crawler_exception"
            result.error = str(e)
            logger.error(f"Errore critico durante il crawling di '{url}': {e}")

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

    def _extract_emails_from_text_and_html(self, html: str, markdown: str) -> Set[str]:
        """Estrae email dall'HTML, dal Markdown e dai tag mailto."""
        emails: Set[str] = set()

        # 1. Regex su HTML e Markdown
        for match in EMAIL_REGEX.findall(html):
            emails.add(match.lower())
        for match in EMAIL_REGEX.findall(markdown):
            emails.add(match.lower())

        # 2. Mailto link in HTML
        soup = BeautifulSoup(html, "html.parser")
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            if href.startswith("mailto:"):
                email = href.replace("mailto:", "").split("?")[0].strip().lower()
                if EMAIL_REGEX.match(email):
                    emails.add(email)

        # Filtra email non valide o di sistema
        filtered = set()
        for email in emails:
            parts = email.split("@")
            if len(parts) != 2:
                continue
            domain = parts[1]
            if domain in EMAIL_BLACKLIST_DOMAINS:
                continue
            ext = "." + email.rsplit(".", 1)[-1] if "." in email else ""
            if ext in EMAIL_BLACKLIST_EXTENSIONS:
                continue
            filtered.add(email)

        return filtered

    async def close(self):
        """Chiude la sessione attiva del browser Crawl4AI."""
        if self._crawler:
            await self._crawler.close()
            self._crawler = None
