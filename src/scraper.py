import math
import time
import requests
from typing import List, Dict, Any, Optional

# Importazione relativa all'interno del package
from .config import (
    GOOGLE_API_KEY, 
    GOOGLE_PLACES_V1_URL, 
    FIELD_MASK, 
    LAT_DEGREE_KM, 
    GRID_STEP_KM, 
    GRID_SIZE, 
    RADIUS_M
)

class LeadScraper:
    def __init__(self):
        self.headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": GOOGLE_API_KEY,
            "X-Goog-FieldMask": FIELD_MASK
        }

    def _generate_grid(self, center_lat: float, center_lng: float) -> List[Dict[str, float]]:
        """
        [Metodo Privato] Genera la matrice di coordinate in base al GRID_SIZE configurato.
        Se GRID_SIZE è 3, genera esattamente 9 punti (3x3).
        """
        coords = []
        lat_step = GRID_STEP_KM / LAT_DEGREE_KM
        lng_step = GRID_STEP_KM / (LAT_DEGREE_KM * math.cos(math.radians(center_lat)))

        # Calcola l'offset per centrare la griglia (es. per 3x3 offset è 1: va da -1 a +1)
        offset = GRID_SIZE // 2

        for i in range(-offset, offset + 1):
            for j in range(-offset, offset + 1):
                coords.append({
                    "lat": round(center_lat + (i * lat_step), 6),
                    "lng": round(center_lng + (j * lng_step), 6)
                })
        return coords

    def _fetch_places_at_location(self, query: str, lat: float, lng: float) -> List[Dict[str, Any]]:
        """
        [Metodo Privato] Esegue una singola chiamata API per un punto specifico.
        """
        payload = {
            "textQuery": query,
            "languageCode": "it",  # Forza lingua locale
            "pageSize": 20,
            "locationBias": {
                "circle": {
                    "center": {"latitude": lat, "longitude": lng},
                    "radius": RADIUS_M
                }
            }
        }

        try:
            response = requests.post(GOOGLE_PLACES_V1_URL, json=payload, headers=self.headers)
            response.raise_for_status()
            return response.json().get("places", [])
            
        except requests.exceptions.HTTPError as e:
            print(f"[API Error] Status {e.response.status_code} at {lat},{lng}: {e.response.text}")
        except Exception as e:
            print(f"[Generic Error] Failed at {lat},{lng}: {e}")
            
        return []

    def scrape_entire_grid(self, query: str, center_lat: float, center_lng: float) -> List[Dict[str, Any]]:
        """
        [Metodo Pubblico Principale] Orchestra la generazione della griglia, 
        l'interrogazione delle API e applica lo SLEEP per evitare i ban.
        """
        all_leads = []
        grid_coords = self._generate_grid(center_lat, center_lng)
        
        print(f"📍 Griglia generata: {len(grid_coords)} punti di scansione.")

        for idx, coord in enumerate(grid_coords, 1):
            print(f"   ⏳ Scansione punto {idx}/{len(grid_coords)} ({coord['lat']}, {coord['lng']})...")
            
            places = self._fetch_places_at_location(query, coord["lat"], coord["lng"])
            all_leads.extend(places)
            
            # --- RATE LIMITING OBBLIGATORIO ---
            # Pausa di 1 secondo tra le chiamate per rispettare le quote di Google
            if idx < len(grid_coords):
                time.sleep(1)
                
        return all_leads

    @staticmethod
    def identify_top_competitor(places: List[Dict[str, Any]]) -> str:
        """
        Trova il competitor con il rating più alto che possiede un sito web.
        Restituisce una stringa (il nome o un fallback predefinito).
        """
        competitors = [
            p for p in places 
            if p.get("websiteUri") and p.get("rating") is not None
        ]
        
        if not competitors:
            return "Competitor Locale" # Fallback per il prompt LLM
        
        top_comp = max(competitors, key=lambda x: float(x.get("rating", 0.0)))
        return top_comp.get("displayName", {}).get("text", "Competitor Locale")
