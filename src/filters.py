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
import whois

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
    for t in raw_types:
        t_lower = t.lower()
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
            
    search_kw_clean = search_kw.strip().title() if search_kw else ""
    
    # Se non abbiamo nessun tag, usiamo la keyword di ricerca
    if not clean_tags and search_kw_clean:
        clean_tags.append(search_kw_clean)
        
    # Limitiamo al massimo a 2 tag per non affollare Excel
    return ", ".join(clean_tags[:2]) if clean_tags else "N/A"


def extract_address_details(lead: dict) -> tuple:
    """
    Estrae 'via_e_civico' e 'paese' (località) da un lead.
    Ritorna una tupla (via_e_civico, paese).
    """
    address_components = lead.get("addressComponents", [])
    
    route = ""
    street_number = ""
    locality = ""
    
    for comp in address_components:
        types = comp.get("types", [])
        if "route" in types:
            route = comp.get("longText", "")
        elif "street_number" in types:
            street_number = comp.get("longText", "")
        elif "locality" in types:
            locality = comp.get("longText", "")
            
    # Se abbiamo trovato la route tramite i componenti strutturati
    if route:
        if street_number:
            via_e_civico = f"{route}, {street_number}"
        else:
            via_e_civico = route
    else:
        # Fallback se non ci sono addressComponents strutturati
        formatted_address = lead.get("formattedAddress", "")
        if formatted_address and formatted_address != "N/A":
            parts = [p.strip() for p in formatted_address.split(",")]
            if len(parts) >= 2:
                p1 = parts[1]
                is_civico = (len(p1) <= 8 and (any(c.isdigit() for c in p1) or p1.lower() in ["snc", "s.n.c."]))
                if is_civico:
                    via_e_civico = f"{parts[0]}, {p1}"
                else:
                    via_e_civico = parts[0]
            else:
                via_e_civico = formatted_address
        else:
            via_e_civico = "N/A"
            
    # Per la località (Paese/Città)
    if not locality:
        formatted_address = lead.get("formattedAddress", "")
        if formatted_address and formatted_address != "N/A":
            parts = [p.strip() for p in formatted_address.split(",")]
            candidate = ""
            for p in parts:
                p_clean = p.lower()
                if "italia" in p_clean or "italy" in p_clean:
                    continue
                if re.search(r'\b\d{5}\b', p):
                    candidate = p
                    break
            
            if candidate:
                city_clean = re.sub(r'\b\d{5}\b', '', candidate).strip()
                city_clean = re.sub(r'\b[A-Z]{2}\b', '', city_clean).strip()
                city_clean = re.sub(r'\([A-Z]{2}\)', '', city_clean).strip()
                locality = city_clean
            elif len(parts) >= 2:
                last_part = parts[-1].lower()
                if last_part in ["italia", "italy"] and len(parts) >= 3:
                    locality = parts[-2]
                else:
                    locality = parts[-1]
                    
    # Pulizia finale della località
    if locality:
        locality = re.sub(r'\b\d{5}\b', '', locality).strip()
        locality = re.sub(r'\b[A-Z]{2}\b', '', locality).strip()
        locality = re.sub(r'\([A-Z]{2}\)', '', locality).strip()
        locality = locality.strip(", ")
        
    if not locality or locality.lower() == "n/a":
        locality = lead.get("search_keyword", "N/A").title()
        
    return via_e_civico, locality
