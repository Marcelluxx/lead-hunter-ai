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
import json
from datetime import datetime, date, timezone
from typing import List, Optional
from urllib.parse import urlparse, parse_qs
import whois
from bs4 import BeautifulSoup, Comment

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

    if whois_result is False or regex_result is False:
        return False
    logger.info('Filtro età: stato unknown, consentito dalla policy locale.')
    return True


def _check_whois_age(domain: str, cutoff_year: int) -> Optional[bool]:
    """WHOIS lookup. Returns True/False/None."""
    try:
        hostname = extract_domain(domain)
        if not hostname:
            return None
        creation = whois.whois(hostname, timeout=10).creation_date
        candidates = creation if isinstance(creation, (list, tuple)) else [creation]
        dates = []
        now = datetime.now(timezone.utc)
        for value in candidates:
            if isinstance(value, str):
                try:
                    value = datetime.fromisoformat(value.replace('Z', '+00:00'))
                except ValueError:
                    continue
            if isinstance(value, date) and not isinstance(value, datetime):
                value = datetime.combine(value, datetime.min.time())
            if not isinstance(value, datetime):
                continue
            value = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
            if 1900 <= value.year and value <= now:
                dates.append(value)
        if dates:
            return min(dates).year <= cutoff_year
    except Exception as e:
        logger.debug('WHOIS non disponibile (%s)', type(e).__name__)
    return None


def _check_copywriting_age(html_text: str, cutoff_year: int, min_years: int) -> Optional[bool]:
    """Cerca riferimenti all'età nel testo del sito. Returns True/False/None."""
    if not html_text:
        return None

    soup = _visible_dom(html_text)
    for element in soup(['script', 'head']):
        element.decompose()
    text_lower = soup.get_text(' ', strip=True).casefold()
    current_year = datetime.now().year
    decisions = []

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
                    decisions.append(year <= cutoff_year)
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
                decisions.append(years >= min_years)
            except ValueError:
                continue

    return True if True in decisions else (False if False in decisions else None)


def _visible_dom(html_text):
    soup = BeautifulSoup(html_text or '', 'html.parser')
    for comment in soup.find_all(string=lambda item: isinstance(item, Comment)):
        comment.extract()
    for tag in soup.find_all(['style', 'template', 'noscript']):
        tag.decompose()
    for tag in soup.find_all(lambda item: item.has_attr('hidden') or
            str(item.get('aria-hidden', '')).lower() == 'true' or
            re.search(r'(?:display\s*:\s*none|visibility\s*:\s*hidden)', str(item.get('style', '')), re.I)):
        tag.decompose()
    return soup


def filter_ecommerce(html_text: str, ecommerce_indicators: List[str]) -> bool:
    """
    Richiede un'azione DOM di acquisto e struttura commerciale indipendente.
    La lista indicatori legacy resta compatibile; il testo libero non è un segnale.
    Returns True se È un e-commerce (= deve essere ESCLUSO).
    """
    if not html_text:
        return False
    soup = _visible_dom(html_text)
    action = False
    for tag in soup.find_all(['a', 'button', 'input', 'form']):
        target = str(tag.get('href') or tag.get('action') or '')
        parsed = urlparse(target)
        path = parsed.path.casefold()
        labels = ' '.join([str(tag.get('id', '')), ' '.join(tag.get('class', [])),
            str(tag.get('name', '')), str(tag.get('aria-label', '')), tag.get_text(' ', strip=True)])
        if (re.match(r'^/(?:[a-z]{2}/)?(?:cart|checkout|carrello)(?:/|$)', path) or
                'add-to-cart' in parse_qs(parsed.query) or
                re.search(r'\badd[-_]to[-_]cart\b|\baggiungi\s+al\s+carrello\b', labels, re.I)):
            action = True
            break
    if not action:
        return False
    structured = False
    def product_schema(value):
        if isinstance(value, dict):
            kinds = value.get('@type', [])
            kinds = [kinds] if isinstance(kinds, str) else kinds
            if isinstance(kinds, list) and any(str(x).rsplit('/', 1)[-1] in ('Product', 'Offer') for x in kinds):
                return True
            return any(product_schema(item) for item in value.values())
        return isinstance(value, list) and any(product_schema(item) for item in value)
    for tag in soup.find_all('script', attrs={'type': 'application/ld+json'}):
        try:
            if product_schema(json.loads(tag.string or tag.get_text())):
                structured = True
                break
        except (ValueError, TypeError, RecursionError):
            continue
    if not structured:
        structured = any(re.search(r'(?:schema\.org/)(?:Product|Offer)\b', str(tag.get('itemtype', '')))
            for tag in soup.find_all(attrs={'itemtype': True}))
    if not structured:
        for tag in soup.find_all(['script', 'link', 'span']):
            asset = urlparse(str(tag.get('src') or tag.get('href') or ''))
            classes = ' '.join(tag.get('class', []))
            if (asset.hostname == 'cdn.shopify.com' or
                    re.search(r'/plugins/woocommerce/|/prestashop/|/magento/', asset.path, re.I) or
                    'woocommerce-Price-amount' in classes.split()):
                structured = True
                break
    return structured


def filter_franchise(
    business_name: str,
    all_names_in_dataset: List[str],
    known_franchises: List[str]
) -> bool:
    """
    Match di marchi noti per token completi. Nomi ripetuti da soli non provano una catena.
    Returns True se è franchise (= deve essere ESCLUSO).
    """
    if not business_name:
        return False
    name_tokens = re.findall(r'\w+', business_name.casefold())
    for franchise in known_franchises:
        tokens = re.findall(r'\w+', franchise.casefold())
        if tokens and any(name_tokens[index:index + len(tokens)] == tokens
                for index in range(len(name_tokens) - len(tokens) + 1)):
            logger.info('Filtro franchise: marchio noto completo rilevato.')
            return True

    return False


def filter_social_media(domain: str, social_domains: List[str]) -> bool:
    """
    Rileva se il dominio appartiene a un social media.
    Returns True se il sito È un social media (= deve essere ESCLUSO).
    """
    if not domain:
        return False
    hostname = extract_domain(domain)
    for social in social_domains:
        social = extract_domain(social)
        if social and (hostname == social or hostname.endswith('.' + social)):
            logger.info('Filtro social: hostname social rilevato.')
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
        if not isinstance(url, str) or not url or any(char.isspace() for char in url):
            return ''
        parsed = urlparse(url if '://' in url or url.startswith('//') else '//' + url)
        domain = (parsed.hostname or '').rstrip('.').encode('idna').decode('ascii').lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return ''


# --- TRADUZIONE E UNIFICAZIONE CATEGORIE ---
CATEGORY_TRANSLATIONS = {
    "restaurant": "Ristorante",
    "italian_restaurant": "Ristorante Italiano",
    "pizza_restaurant": "Pizzeria",
    "pizza": "Pizzeria",
    "pizzeria": "Pizzeria",
    "bar": "Bar",
    "bar_or_pub": "Bar",
    "pub": "Pub/Bar",
    "cafe": "Bar",
    "cafe_or_coffee_shop": "Bar",
    "coffee_shop": "Bar",
    "gelateria": "Gelateria",
    "ice_cream_parlor": "Gelateria",
    "bakery": "Panificio/Pasticceria",
    "bakery_or_pastry_shop": "Panificio/Pasticceria",
    "pastry_shop": "Pasticceria",
    "dentist": "Dentista",
    "dental_clinic": "Studio Dentistico",
    "lawyer": "Avvocato",
    "plumber": "Idraulico",
    "electrician": "Elettricista",
    "beauty_salon": "Centro Estetico",
    "hair_care": "Parrucchiere",
    "hair_salon": "Parrucchiere",
    "spa": "Centro Benessere",
    "gym": "Palestra",
    "fitness_center": "Palestra",
    "hotel": "Hotel",
    "lodging": "Hotel/Alloggio",
    "store": "Negozio",
    "clothing_store": "Negozio di Abbigliamento",
    "supermarket": "Supermercato",
    "grocery_or_supermarket": "Supermercato",
    "pharmacy": "Farmacia",
    "drugstore": "Farmacia",
    "medical_clinic": "Poliambulatorio",
    "doctor": "Medico",
    "physiotherapist": "Fisioterapista",
    "veterinary_care": "Veterinario",
    "real_estate_agency": "Agenzia Immobiliare",
    "travel_agency": "Agenzia di Viaggi",
    "car_repair": "Officina Meccanica",
    "car_dealer": "Concessionario Auto",
    "car_wash": "Autolavaggio",
    "car_rental": "Noleggio Auto",
    "laundry": "Lavanderia",
    "dry_cleaning": "Lavanderia",
    "florist": "Fioraio",
    "jewelry_store": "Gioielleria",
    "book_store": "Libreria",
    "pet_store": "Negozio per Animali",
    "electronics_store": "Negozio di Elettronica",
    "furniture_store": "Negozio di Mobili",
    "hardware_store": "Ferramenta",
    "bicycle_store": "Negozio di Biciclette",
    "school": "Scuola",
    "university": "Università",
    "amusement_park": "Parco Divertimenti",
    "art_gallery": "Galleria d'Arte",
    "museum": "Museo",
    "night_club": "Discoteca",
    "cinema": "Cinema",
    "movie_theater": "Cinema",
    "stadium": "Stadio",
    "accounting": "Studio Commercialista",
    "insurance_agency": "Agenzia Assicurativa",
    "bank": "Banca",
    "finance": "Servizi Finanziari",
    "post_office": "Ufficio Postale",
    "police": "Polizia",
    "hospital": "Ospedale",
    "funeral_home": "Impresa Funebre",
    "moving_company": "Ditta di Traslochi",
    "painter": "Imbianchino",
    "roofing_contractor": "Coperture Edili",
    "locksmith": "Fabbro",
    "park": "Parco",
    "parking": "Parcheggio",
    "cemetery": "Cimitero",
    "church": "Chiesa",
    "place_of_worship": "Luogo di Culto",
}

IGNORED_TYPES = {
    "point_of_interest",
    "establishment",
    "food",
    "store",
    "health",
    "general_contractor",
    "local_business",
    "political",
    "finance",
    "lodging",
}


def clean_and_translate_categories(raw_types: list, search_kw: str = "") -> str:
    """
    Pulisce e traduce le categorie in italiano.
    Ritorna una stringa di tag separati da virgola.
    """
    clean_tags = []
    seen = set()
    
    # Processa i tipi di Google Maps
    for t in raw_types if isinstance(raw_types, (list, tuple)) else []:
        if not isinstance(t, str):
            continue
        t_lower = t.strip().casefold()
        if not t_lower:
            continue
        if t_lower in IGNORED_TYPES:
            continue
            
        # Se è nella mappa delle traduzioni, lo traduciamo
        if t_lower in CATEGORY_TRANSLATIONS:
            tag = CATEGORY_TRANSLATIONS[t_lower]
        else:
            # Altrimenti facciamo una pulizia di base
            tag = t_lower.replace("_", " ").title()
            
        if tag not in seen:
            seen.add(tag)
            clean_tags.append(tag)
            
    search_kw_clean = search_kw.strip().title() if isinstance(search_kw, str) else ""
    
    # Se non abbiamo nessun tag, usiamo la keyword di ricerca
    if not clean_tags and search_kw_clean:
        clean_tags.append(search_kw_clean)
        
    # Limitiamo al massimo a 2 tag per non affollare Excel
    return ", ".join(clean_tags[:2]) if clean_tags else "N/A"


def extract_address_details(lead: dict) -> tuple:
    """Presentation helper: missing locality remains unknown, never the search term."""
    if not isinstance(lead, dict):
        return 'N/A', 'N/A'
    def text(value):
        return value.strip() if isinstance(value, str) and value.strip().casefold() != 'n/a' else ''
    components = lead.get('addressComponents')
    components = components if isinstance(components, (list, tuple)) else []
    values = {}
    for comp in components:
        if not isinstance(comp, dict) or not isinstance(comp.get('types'), (list, tuple)):
            continue
        for kind in ('route', 'street_number', 'locality', 'postal_town'):
            if kind in comp['types'] and text(comp.get('longText')):
                values.setdefault(kind, text(comp['longText']))
    street = ', '.join(filter(None, (values.get('route', ''), values.get('street_number', ''))))
    locality = values.get('locality') or values.get('postal_town') or ''
    parts = [part.strip() for part in text(lead.get('formattedAddress')).split(',') if part.strip()]
    if not street and parts:
        street = parts[0]
        if len(parts) > 1 and re.fullmatch(r'(?:\d+[a-z]?(?:\s*[/\-]\s*[\da-z]+)?|snc|s\.n\.c\.)', parts[1], re.I):
            street += ', ' + parts[1]
    if not locality:
        for part in parts[1:]:
            postal = re.match(r'^\d{4,6}\s+(.+)$', part)
            if postal:
                locality = re.sub(r'\s*\([A-Z]{2}\)\s*$', '', postal.group(1)).strip()
                break
        if not locality and len(parts) >= 3 and parts[-1].casefold() in (
                'italia', 'italy', 'usa', 'united states', 'uk', 'united kingdom',
                'canada', 'france', 'germany', 'deutschland', 'spain', 'brasil', 'brazil'):
            candidate = parts[-2]
            if any(char.isalpha() for char in candidate):
                locality = candidate
    return street or 'N/A', locality or 'N/A'
