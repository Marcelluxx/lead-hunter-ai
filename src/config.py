import os
import sys
from typing import Final
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
# Field Mask esatto come richiesto, senza dati superflui (risparmio banda/costi)
FIELD_MASK: Final[str] = (
    "places.id,"
    "places.displayName,"
    "places.formattedAddress,"
    "places.nationalPhoneNumber,"
    "places.websiteUri,"
    "places.rating,"
    "places.reviews,"
    "places.types" 
)
