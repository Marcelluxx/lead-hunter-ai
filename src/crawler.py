"""
Lead Hunter V3 — Crawl4AI Web Crawler
Replaces custom HybridCrawler with Crawl4AI, providing clean semantic Markdown
for LLM ingestion, advanced WAF/stealth bypass, and structured link extraction.
"""

import re
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

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


@dataclass
class CrawlResult:
    """Risultato del crawling di un sito web."""
    url: str
    pages: Dict[str, str] = field(default_factory=dict)   # URL -> contenuto pulito (markdown)
    emails: List[str] = field(default_factory=list)
    raw_html_home: str = ""                                 # HTML grezzo homepage (per filtri)
    is_dynamic: bool = True
    error: Optional[str] = None


class HybridCrawler:
    """Crawler basato su Crawl4AI per estrazione di Markdown semantico ottimizzato per LLM."""

    def __init__(self, max_pages: int = 5, token_mode: str = "high_fidelity", headless: bool = True):
        self.max_pages = max_pages
        self.token_mode = token_mode
        self.headless = headless
        self._crawler = None

    async def crawl(self, url: str) -> CrawlResult:
        """
        Crawla la homepage e le pagine interne prioritarie utilizzando Crawl4AI.
        Restituisce un CrawlResult con la mappa delle pagine pulite ed email.
        """
        result = CrawlResult(url=url)
        all_emails: Set[str] = set()

        try:
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
                await self._crawler.start()

            logger.info(f"Crawl4AI: avvio crawling homepage per '{url}'")
            home_result = await self._crawler.arun(url, config=run_config)

            if not home_result or not home_result.success:
                result.error = home_result.error_message if home_result else "Errore sconosciuto durante il crawl."
                logger.error(f"Crawl4AI: crawl homepage fallito per '{url}': {result.error}")
                return result

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

            result.pages[url] = self._clean_whitespace(fit_md)
            all_emails.update(self._extract_emails_from_text_and_html(home_result.html or "", fit_md))

            # --- SCOPERTA LINK INTERNI ---
            internal_links_raw = []
            if home_result.links and "internal" in home_result.links:
                for l in home_result.links["internal"]:
                    href = l.get("href", "")
                    if href:
                        # Risolve percorsi relativi
                        full_link_url = urljoin(url, href)
                        internal_links_raw.append(full_link_url)

            parsed_base = urlparse(url)
            base_domain = parsed_base.netloc

            priority_links = []
            seen_links = {url}

            for l_url in internal_links_raw:
                parsed_link = urlparse(l_url)
                # Solo link interni dello stesso dominio
                if parsed_link.netloc and parsed_link.netloc != base_domain:
                    continue
                if parsed_link.scheme and parsed_link.scheme not in ("http", "https"):
                    continue

                clean_link = f"{parsed_link.scheme}://{parsed_link.netloc}{parsed_link.path}"
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

                        result.pages[p_url] = self._clean_whitespace(page_fit_md)
                        all_emails.update(self._extract_emails_from_text_and_html(page_result.html or "", page_fit_md))
                        pages_crawled += 1
                except Exception as e:
                    logger.debug(f"Errore durante il crawling di '{p_url}': {e}")

            result.emails = sorted(all_emails)

        except Exception as e:
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
