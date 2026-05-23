import os
import sys
from typing import Final, List
from dotenv import load_dotenv

# Carica variabili d'ambiente
load_dotenv()

# --- API KEYS (con Fail-Fast per robustezza) ---
GOOGLE_API_KEY: Final[str] = os.getenv("GOOGLE_API_KEY", "")
OPENROUTER_API_KEY: Final[str] = os.getenv("OPENROUTER_API_KEY", "")

# Se mancano le chiavi, blocca l'app immediatamente invece di fallire durante le chiamate HTTP
if not GOOGLE_API_KEY or not OPENROUTER_API_KEY:
    sys.exit("CRITICAL ERROR: GOOGLE_API_KEY or OPENROUTER_API_KEY missing in .env file.")

# --- API ENDPOINTS ---
GOOGLE_PLACES_V1_URL: Final[str] = "https://places.googleapis.com/v1/places:searchText"
GOOGLE_GEOCODING_URL: Final[str] = "https://maps.googleapis.com/maps/api/geocode/json"
OPENROUTER_BASE_URL: Final[str] = "https://openrouter.ai/api/v1"

# --- LLM CONFIG ---
LLM_MODEL: Final[str] = os.getenv("LLM_MODEL", "meta-llama/llama-3.1-8b-instruct")

# --- GRID SEARCH CONFIG ---
GRID_SIZE: Final[int] = 3            # Griglia 3x3
GRID_STEP_KM: Final[float] = 2.0     # Spostamento centro di 2 km
RADIUS_M: Final[float] = 2000.0      # Raggio per locationBias (obbligatorio per Places V1)
LAT_DEGREE_KM: Final[float] = 111.32 # Valore esatto per i calcoli GPS

# --- GOOGLE PLACES CONFIG ---
# Field Mask con userRatingCount per filtro recensioni (Places V1 API)
FIELD_MASK: Final[str] = (
    "places.id,"
    "places.displayName,"
    "places.formattedAddress,"
    "places.nationalPhoneNumber,"
    "places.websiteUri,"
    "places.rating,"
    "places.userRatingCount,"
    "places.reviews,"
    "places.types"
)

# --- FILTRI LEAD (Modalità "Con Sito Web") ---
MIN_RATING: Final[float] = 3.9       # Rating minimo Google
MAX_REVIEWS: Final[int] = 100        # Numero massimo recensioni (filtra catene/franchise)
MIN_BUSINESS_AGE_YEARS: Final[int] = 5  # Età minima attività (anni)

# --- CRAWLER CONFIG ---
MAX_CRAWL_PAGES: Final[int] = 5      # Pagine interne max da esplorare
TOKEN_MODE: Final[str] = os.getenv("TOKEN_MODE", "high_fidelity")  # "high_fidelity" | "optimized"

# --- INDICATORI E-COMMERCE (per esclusione automatica) ---
ECOMMERCE_INDICATORS: Final[List[str]] = [
    "cart", "checkout", "shopify", "woocommerce", "add-to-cart",
    "add_to_cart", "stripe", "snipcart", "bigcommerce", "prestashop",
    "magento", "opencart", "wc-add-to-cart", "product-price",
    "shop-now", "buy-now", "carrello", "acquista"
]

# --- FRANCHISE / CATENE NAZIONALI NOTE ---
KNOWN_FRANCHISES: Final[List[str]] = [
    # Fast Food & Ristorazione
    "mcdonald", "burger king", "kfc", "subway", "domino's pizza",
    "starbucks", "autogrill", "old wild west", "roadhouse", "alice pizza",
    "la piadineria", "spontini", "rossopomodoro", "billy tacos",
    # GDO & Retail
    "eurospin", "lidl", "aldi", "conad", "coop", "esselunga", "carrefour",
    "penny market", "md discount", "iper", "bennet", "pam", "despar",
    # Bricolage & Casa
    "leroy merlin", "bricoman", "ikea", "mondo convenienza", "maisons du monde",
    # Servizi & Cura persona
    "jean louis david", "naturhouse", "mail boxes etc", "kipoint",
    # Fitness
    "virgin active", "anytime fitness", "mcfit",
    # Ottica & Salute
    "salmoiraghi", "grand vision", "fielmann",
    # Automotive
    "norauto", "midas", "euromaster",
]

# --- DOMINI SOCIAL MEDIA (per esclusione immediata) ---
SOCIAL_MEDIA_DOMAINS: Final[List[str]] = [
    "facebook.com", "instagram.com", "linkedin.com", "twitter.com", 
    "x.com", "tiktok.com", "youtube.com", "pinterest.com", 
    "wa.me", "linktr.ee", "msha.ke", "lnk.bio"
]
