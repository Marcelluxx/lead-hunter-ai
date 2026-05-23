"""
Lead Hunter V3 — Hybrid Web Crawler
Two-pass architecture:
  1. Static fetch (httpx + BeautifulSoup) — fast, low resource
  2. Dynamic fallback (Playwright headless) — for JS-rendered sites
Includes multi-page crawling, email extraction, and token-mode content preparation.
"""

import re
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse

import httpx
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
    pages: Dict[str, str] = field(default_factory=dict)   # URL -> contenuto pulito
    emails: List[str] = field(default_factory=list)
    raw_html_home: str = ""                                 # HTML grezzo homepage (per filtri)
    is_dynamic: bool = False
    error: Optional[str] = None


class HybridCrawler:
    """Crawler ibrido: prima tenta fetch statico, poi fallback Playwright."""

    def __init__(self, max_pages: int = 5, token_mode: str = "high_fidelity"):
        self.max_pages = max_pages
        self.token_mode = token_mode
        self._http_client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(15.0),
                follow_redirects=True,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    )
                }
            )
        return self._http_client

    async def crawl(self, url: str) -> CrawlResult:
        """
        Entry point principale. Crawla un sito fino a max_pages pagine.
        Restituisce un CrawlResult con contenuto, email ed errori.
        """
        result = CrawlResult(url=url)
        all_emails: Set[str] = set()

        try:
            # --- PASS 1: Static fetch homepage ---
            html, is_shell = await self._static_fetch(url)

            if is_shell:
                # --- PASS 2: Playwright fallback ---
                logger.info(f"Shell JS rilevata per {url}, attivo Playwright...")
                result.is_dynamic = True
                html = await self._dynamic_fetch(url)

            if not html:
                result.error = "Impossibile recuperare contenuto HTML"
                return result

            result.raw_html_home = html
            soup = BeautifulSoup(html, "html.parser")

            # Processa homepage
            prepared_content = self._prepare_content(html)
            result.pages[url] = prepared_content
            all_emails.update(self._extract_emails(html))

            # --- Crawl pagine interne prioritarie ---
            priority_links = self._discover_priority_links(url, soup)
            pages_crawled = 1

            for link_url in priority_links:
                if pages_crawled >= self.max_pages:
                    break
                try:
                    if result.is_dynamic:
                        page_html = await self._dynamic_fetch(link_url)
                    else:
                        page_html, _ = await self._static_fetch(link_url)

                    if page_html:
                        result.pages[link_url] = self._prepare_content(page_html)
                        all_emails.update(self._extract_emails(page_html))
                        pages_crawled += 1

                except Exception as e:
                    logger.debug(f"Errore crawling {link_url}: {e}")
                    continue

            result.emails = sorted(all_emails)
            logger.info(f"Crawling completato: {url} — {len(result.pages)} pagine, {len(result.emails)} email")

        except Exception as e:
            result.error = str(e)
            logger.error(f"Errore critico crawling {url}: {e}")

        return result

    async def _static_fetch(self, url: str) -> Tuple[str, bool]:
        """
        Fetch statico con httpx + BeautifulSoup.
        Returns (html_content, is_dynamic_shell).
        """
        try:
            client = await self._get_client()
            response = await client.get(url)
            response.raise_for_status()
            html = response.text

            # Rileva shell JS (SPA senza contenuto server-side)
            is_shell = self._detect_js_shell(html)
            return html, is_shell

        except Exception as e:
            logger.debug(f"Static fetch fallito per {url}: {e}")
            return "", True  # Consideriamo come shell -> triggera Playwright

    async def _dynamic_fetch(self, url: str) -> str:
        """Fallback asincrono con Playwright (headless Chromium)."""
        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    )
                )
                page = await context.new_page()

                try:
                    await page.goto(url, wait_until="networkidle", timeout=20000)
                    html = await page.content()
                    return html
                finally:
                    await context.close()
                    await browser.close()

        except Exception as e:
            logger.error(f"Playwright fallito per {url}: {e}")
            return ""

    def _detect_js_shell(self, html: str) -> bool:
        """
        Rileva se l'HTML è una shell vuota per SPA/JS frameworks.
        Controlla: mount points vuoti, rapporto testo/script basso.
        """
        soup = BeautifulSoup(html, "html.parser")
        body = soup.find("body")
        if not body:
            return True

        body_text = body.get_text(separator=" ", strip=True)

        # Shell indicators: div#app, div#root con poco testo
        shell_ids = {"app", "root", "__next", "__nuxt", "gatsby-focus-wrapper"}
        for div in body.find_all("div", id=True):
            if div.get("id", "").lower() in shell_ids:
                # Se il body ha pochissimo testo, è probabilmente una shell
                if len(body_text) < 200:
                    return True

        # Rapporto script vs testo: troppi script, poco testo
        scripts = soup.find_all("script")
        if len(scripts) > 5 and len(body_text) < 100:
            return True

        return False

    def _discover_priority_links(self, base_url: str, soup: BeautifulSoup) -> List[str]:
        """Scopre link interni prioritari (contatti, chi siamo, servizi, privacy...)."""
        parsed_base = urlparse(base_url)
        base_domain = parsed_base.netloc
        found: Set[str] = set()

        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            full_url = urljoin(base_url, href)
            parsed = urlparse(full_url)

            # Solo link interni (stesso dominio)
            if parsed.netloc and parsed.netloc != base_domain:
                continue

            # Ignora ancoraggi, file, e link esterni
            if parsed.scheme and parsed.scheme not in ("http", "https"):
                continue

            path_lower = parsed.path.lower()

            # Match con pattern prioritari
            for pattern in PRIORITY_PATH_PATTERNS:
                if re.search(pattern, path_lower):
                    clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                    if clean_url != base_url and clean_url not in found:
                        found.add(clean_url)
                    break

        return list(found)[:self.max_pages - 1]  # -1 perché la homepage è già inclusa

    def _extract_emails(self, html: str) -> Set[str]:
        """Estrae email dal testo HTML e dagli attributi mailto."""
        emails: Set[str] = set()
        soup = BeautifulSoup(html, "html.parser")

        # 1. Regex sul testo visibile
        text = soup.get_text(separator=" ")
        for match in EMAIL_REGEX.findall(text):
            emails.add(match.lower())

        # 2. href="mailto:..." 
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            if href.startswith("mailto:"):
                email = href.replace("mailto:", "").split("?")[0].strip().lower()
                if EMAIL_REGEX.match(email):
                    emails.add(email)

        # Filtra falsi positivi
        filtered = set()
        for email in emails:
            domain = email.split("@")[1] if "@" in email else ""
            if domain in EMAIL_BLACKLIST_DOMAINS:
                continue
            ext = "." + email.rsplit(".", 1)[-1] if "." in email else ""
            if ext in EMAIL_BLACKLIST_EXTENSIONS:
                continue
            filtered.add(email)

        return filtered

    def _prepare_content(self, html: str) -> str:
        """
        Prepara il contenuto HTML per l'invio all'LLM in base al token_mode.
        - high_fidelity: HTML semantico con classi CSS layout
        - optimized: Markdown pulito, solo testo e headers
        """
        if self.token_mode == "optimized":
            return self._prepare_optimized(html)
        return self._prepare_high_fidelity(html)

    def _prepare_high_fidelity(self, html: str) -> str:
        """
        High-Fidelity: preserva struttura HTML semantica, classi CSS framework
        (Tailwind, Bootstrap), meta tags, heading hierarchy.
        """
        soup = BeautifulSoup(html, "html.parser")

        # Rimuovi script e style content (ma preserva tag semantici)
        for tag in soup.find_all(["script", "style", "noscript", "iframe"]):
            tag.decompose()

        # Preserva solo classi CSS rilevanti al layout
        layout_patterns = re.compile(
            r'(flex|grid|col-|row-|container|hidden|block|inline|'
            r'md:|lg:|sm:|xl:|justify|items-|gap-|space-|'
            r'text-|font-|bg-|p-|m-|w-|h-|rounded|shadow|border)',
            re.IGNORECASE
        )

        for tag in soup.find_all(True):
            classes = tag.get("class", [])
            if classes:
                relevant = [c for c in classes if layout_patterns.search(c)]
                if relevant:
                    tag["class"] = relevant
                else:
                    del tag["class"]

            # Rimuovi attributi non utili
            attrs_to_keep = {"class", "id", "href", "src", "alt", "title", "name", "content"}
            for attr in list(tag.attrs.keys()):
                if attr not in attrs_to_keep:
                    del tag[attr]

        # Estrai meta tags utili
        meta_info = []
        for meta in soup.find_all("meta"):
            name = meta.get("name", "") or meta.get("property", "")
            content = meta.get("content", "")
            if name and content and name.lower() in (
                "description", "keywords", "og:title", "og:description",
                "author", "generator"
            ):
                meta_info.append(f'<meta name="{name}" content="{content}">')

        body = soup.find("body")
        body_html = str(body) if body else str(soup)

        # Limita dimensione output
        if len(body_html) > 80000:
            body_html = body_html[:80000] + "\n<!-- [TRONCATO] -->"

        header = "\n".join(meta_info) if meta_info else ""
        return f"<!-- META -->\n{header}\n<!-- BODY -->\n{body_html}"

    def _prepare_optimized(self, html: str) -> str:
        """
        Optimized: converte in markdown pulito, solo headers + testo + metadata.
        Minimizza i token consumati.
        """
        try:
            import html2text
            h = html2text.HTML2Text()
            h.ignore_links = False
            h.ignore_images = True
            h.ignore_emphasis = False
            h.body_width = 0  # No wrap

            soup = BeautifulSoup(html, "html.parser")

            # Rimuovi script, style, nav duplicati
            for tag in soup.find_all(["script", "style", "noscript", "iframe"]):
                tag.decompose()

            # Estrai title e meta description
            title = ""
            title_tag = soup.find("title")
            if title_tag:
                title = title_tag.get_text(strip=True)

            desc = ""
            meta_desc = soup.find("meta", attrs={"name": "description"})
            if meta_desc:
                desc = meta_desc.get("content", "")

            body = soup.find("body")
            markdown = h.handle(str(body) if body else str(soup))

            # Limita dimensione
            if len(markdown) > 50000:
                markdown = markdown[:50000] + "\n\n[...TRONCATO...]"

            header = f"# {title}\n> {desc}\n\n" if title else ""
            return header + markdown

        except ImportError:
            # Fallback se html2text non installato
            soup = BeautifulSoup(html, "html.parser")
            return soup.get_text(separator="\n", strip=True)[:8000]

    async def close(self):
        """Chiudi il client HTTP."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
