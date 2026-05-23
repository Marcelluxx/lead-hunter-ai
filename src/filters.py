"""
Lead Hunter V3 — Modulo Filtri per Qualificazione Lead
Contiene tutti i filtri per la modalità "Con Sito Web + Audit":
- Filtro recensioni (rating + count)
- Filtro età attività (WHOIS + regex copywriting)
- Filtro e-commerce (esclusione shop online)
- Filtro franchise/catene nazionali
"""

import re
import logging
from datetime import datetime
from typing import List, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def filter_by_reviews(place: dict, min_rating: float = 3.9, max_reviews: int = 100) -> bool:
    """
    Verifica che l'attività abbia rating > min_rating e recensioni tra 1 e max_reviews.
    Returns True se il lead PASSA il filtro.
    """
    rating = place.get("rating")
    review_count = place.get("userRatingCount", 0)

    if rating is None:
        return False
    if float(rating) <= min_rating:
        return False
    if review_count < 1 or review_count > max_reviews:
        return False
    return True


def filter_by_business_age(domain: str, html_text: str = "", min_years: int = 5) -> bool:
    """
    Verifica età >= min_years via WHOIS + regex sul copywriting.
    Se ENTRAMBI non trovano dati, il lead PASSA (benefit of the doubt).
    """
    current_year = datetime.now().year
    cutoff_year = current_year - min_years

    whois_result = _check_whois_age(domain, cutoff_year)
    if whois_result is True:
        return True

    regex_result = _check_copywriting_age(html_text, cutoff_year, min_years)
    if regex_result is True:
        return True

    # Benefit of the doubt: nessun dato = passa
    logger.info(f"Filtro età: nessun dato definitivo per {domain}, lead passa per benefit of the doubt.")
    return True


def _check_whois_age(domain: str, cutoff_year: int) -> Optional[bool]:
    """WHOIS lookup. Returns True/False/None."""
    try:
        import whois
        w = whois.whois(domain)
        creation_date = w.creation_date
        if creation_date is None:
            return None
        if isinstance(creation_date, list):
            creation_date = creation_date[0]
        if hasattr(creation_date, 'year'):
            if creation_date.year <= cutoff_year:
                logger.info(f"WHOIS: {domain} registrato {creation_date.year} — PASSA")
                return True
            else:
                logger.info(f"WHOIS: {domain} registrato {creation_date.year} — recente")
                return False
    except Exception as e:
        logger.debug(f"WHOIS fallito per {domain}: {e}")
    return None


def _check_copywriting_age(html_text: str, cutoff_year: int, min_years: int) -> Optional[bool]:
    """Cerca riferimenti all'età nel testo del sito. Returns True/False/None."""
    if not html_text:
        return None

    text_lower = html_text.lower()
    current_year = datetime.now().year

    # Pattern anno esplicito
    year_patterns = [
        r'(?:fondat[aoe]|nata?|costituit[aoe]|attiv[aoi])\s+(?:nel|nel\'?)\s+(\d{4})',
        r'\bdal\s+(\d{4})\b',
        r'\bsince\s+(\d{4})\b',
        r'\bestablished\s+(?:in\s+)?(\d{4})\b',
        r'\bfin\s+dal\s+(\d{4})\b',
    ]
    for pattern in year_patterns:
        for match in re.findall(pattern, text_lower):
            try:
                year = int(match)
                if 1900 <= year <= current_year:
                    return year <= cutoff_year
            except ValueError:
                continue

    # Pattern durata relativa
    duration_patterns = [
        r'da\s+(?:oltre|più\s+di|quasi)\s+(\d+)\s+ann[io]',
        r'(?:over|more\s+than)\s+(\d+)\s+years?',
        r'(\d+)\s+anni?\s+di\s+esperienza',
    ]
    for pattern in duration_patterns:
        for match in re.findall(pattern, text_lower):
            try:
                years = int(match)
                return years >= min_years
            except ValueError:
                continue

    return None


def filter_ecommerce(html_text: str, ecommerce_indicators: List[str]) -> bool:
    """
    Rileva se il sito è un e-commerce. Richiede almeno 2 indicatori per evitare falsi positivi.
    Returns True se È un e-commerce (= deve essere ESCLUSO).
    """
    if not html_text:
        return False
    text_lower = html_text.lower()
    match_count = sum(1 for ind in ecommerce_indicators if ind.lower() in text_lower)
    if match_count >= 2:
        logger.info(f"Filtro e-commerce: RILEVATO ({match_count} indicatori)")
        return True
    return False


def filter_franchise(
    business_name: str,
    all_names_in_dataset: List[str],
    known_franchises: List[str]
) -> bool:
    """
    Rileva catene nazionali / franchise via lista hardcoded + analisi ripetizioni nel dataset.
    Returns True se è franchise (= deve essere ESCLUSO).
    """
    if not business_name:
        return False
    name_lower = business_name.lower().strip()

    # Check 1: Lista hardcoded
    for franchise in known_franchises:
        if franchise.lower() in name_lower:
            logger.info(f"Filtro franchise: '{business_name}' match con '{franchise}'")
            return True

    # Check 2: Brand ripetuto 3+ volte nel dataset
    normalized = _normalize_brand_name(name_lower)
    if normalized and len(normalized) >= 3:
        count = sum(1 for n in all_names_in_dataset if normalized in _normalize_brand_name(n.lower().strip()))
        if count >= 3:
            logger.info(f"Filtro franchise: '{business_name}' appare {count}x nel dataset")
            return True

    return False


def filter_social_media(domain: str, social_domains: List[str]) -> bool:
    """
    Rileva se il dominio appartiene a un social media.
    Returns True se il sito È un social media (= deve essere ESCLUSO).
    """
    if not domain:
        return False
    domain_lower = domain.lower()
    for social in social_domains:
        if social in domain_lower:
            logger.info(f"Filtro social: '{domain}' scartato (match con '{social}')")
            return True
    return False


def _normalize_brand_name(name: str) -> str:
    """Normalizza il nome brand rimuovendo articoli, suffissi, punteggiatura."""
    name = re.sub(r'^(il|la|lo|l\'|i|gli|le|the|a|an)\s+', '', name)
    name = re.sub(r'[\s\-]+\d+$', '', name)
    name = re.sub(r'\s*[\-–—]\s*\w+$', '', name)
    name = re.sub(r'[^\w\s]', '', name)
    return name.strip()


def extract_domain(url: str) -> str:
    """Estrae il dominio puro da un URL (es. 'www.example.com' -> 'example.com')."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return url
