"""Observed DOM fingerprints, not backend/version claims or model guesses."""
from dataclasses import dataclass
import re
from urllib.parse import urlsplit
from bs4 import BeautifulSoup

TECHNOLOGY_RULES_VERSION = '1'


@dataclass(frozen=True)
class TechnologyMatch:
    name: str
    signals: tuple[str, ...]
    confidence: float
    rules_version: str = TECHNOLOGY_RULES_VERSION


def detect_technologies(html: str) -> tuple[TechnologyMatch, ...]:
    if not isinstance(html, str) or not html:
        return ()
    soup = BeautifulSoup(html, 'html.parser')
    for tag in soup.find_all('template'):
        tag.decompose()
    found: dict[str, set[str]] = {}
    def add(name, signal):
        found.setdefault(name, set()).add(signal)
    for tag in soup.find_all('meta'):
        if str(tag.get('name', '')).casefold() != 'generator':
            continue
        generator = str(tag.get('content', '')).strip()
        for name in ('WordPress', 'Drupal', 'Joomla', 'Shopify', 'Wix', 'Squarespace'):
            if re.match(re.escape(name) + r'\b', generator, re.I):
                add(name, 'generator_meta')
    for tag in soup.find_all(['script', 'link']):
        if tag.name == 'link' and not {'stylesheet', 'preload', 'modulepreload'}.intersection(
                str(rel).casefold() for rel in tag.get('rel', [])):
            continue
        target = tag.get('src') if tag.name == 'script' else tag.get('href')
        if not isinstance(target, str):
            continue
        try:
            parsed = urlsplit(target)
            host, path = (parsed.hostname or '').rstrip('.').casefold(), parsed.path.casefold()
        except ValueError:
            continue
        for name, expression, signal in [
            ('WordPress', r'/(?:wp-content|wp-includes)/', 'asset_wp_content'),
            ('Drupal', r'/core/(?:misc|assets|modules)/.*drupal', 'asset_drupal'),
            ('Joomla', r'/media/(?:system|vendor)/.*joomla', 'asset_joomla'),
            ('Next.js', r'/_next/static/', 'asset_next_static'),
            ('Nuxt', r'/_nuxt/', 'asset_nuxt')]:
            if re.search(expression, path):
                add(name, signal)
        if host == 'cdn.shopify.com' and re.search(r'^/s/(?:assets|files)/.+', path):
            add('Shopify', 'asset_shopify_cdn')
        if host in ('static.parastorage.com', 'static.wixstatic.com') and '/wix-thunderbolt/' in path:
            add('Wix', 'asset_wix_thunderbolt')
        if host in ('static1.squarespace.com', 'static.squarespace.com') and re.search(
                r'^/(?:static|universal|universal-scripts)/.+', path):
            add('Squarespace', 'asset_squarespace')
    # Fixed rules emit at most nine distinct public rule IDs; never source text/URLs.
    return tuple(TechnologyMatch(name, tuple(sorted(signals)), 0.95 if 'generator_meta' in signals else 0.8)
        for name, signals in sorted(found.items()))
