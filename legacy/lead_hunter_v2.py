import requests
import pandas as pd
import time
import math
import os
from typing import List, Dict
from dotenv import load_dotenv

# Carica le variabili d'ambiente dal file .env
load_dotenv()

class LeadHunterScouter:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://places.googleapis.com/v1/places:searchText"
        self.headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.nationalPhoneNumber,places.websiteUri,places.rating"
        }

    def fetch_leads_by_location(self, keyword: str, lat: float, lng: float, radius_metri: float = 2000.0) -> List[Dict]:
        """Cerca lead in un raggio specifico usando le coordinate GPS."""
        leads = []
        payload = {
            "textQuery": keyword,
            "languageCode": "it",
            "pageSize": 20, # Sostituito maxResultCount con pageSize
            "locationBias": { # Sostituito locationRestriction con locationBias
                "circle": {
                    "center": {
                        "latitude": round(lat, 6), # Arrotondamento per evitare errori 400
                        "longitude": round(lng, 6)
                    },
                    "radius": float(radius_metri)
                }
            }
        }
        
        try:
            response = requests.post(self.base_url, json=payload, headers=self.headers)
            response.raise_for_status()
            results = response.json().get("places", [])

            for place in results:
                if "websiteUri" not in place:
                    lead_data = {
                        "ID Univoco": place.get("id"),
                        "Nome": place.get("displayName", {}).get("text", "N/A"),
                        "Categoria": keyword.capitalize(),
                        "Indirizzo": place.get("formattedAddress", "N/A"),
                        "Telefono": place.get("nationalPhoneNumber", "N/A"),
                        "Rating": place.get("rating", "N/A")
                    }
                    leads.append(lead_data)
            return leads

        except requests.exceptions.HTTPError as e:
            # Estraiamo l'errore esatto restituito da Google per un debug preciso
            print(f"Errore API su {keyword} a {lat},{lng}: {e.response.status_code} - Dettaglio: {e.response.text}")
            return []
        except Exception as e:
            print(f"Errore generico su {keyword} a {lat},{lng}: {e}")
            return []

    def generate_grid(self, center_lat: float, center_lng: float, step_km: float, grid_steps: int) -> List[tuple]:
        """Genera una matrice di coordinate attorno a un punto centrale."""
        coords = []
        lat_step = step_km / 111.0
        lng_step = step_km / (111.0 * math.cos(math.radians(center_lat)))

        print(f"\nGenerazione griglia geografica in corso...")
        for i in range(-grid_steps, grid_steps + 1):
            for j in range(-grid_steps, grid_steps + 1):
                new_lat = center_lat + (i * lat_step)
                new_lng = center_lng + (j * lng_step)
                coords.append((new_lat, new_lng))
        
        print(f"Griglia generata: {len(coords)} punti di scansione (radar pronti).")
        return coords

    def run_campaign(self, center_lat: float, center_lng: float, keywords: List[str], grid_steps: int = 1):
        """Esegue l'intera campagna di ricerca ed elimina i duplicati."""
        all_leads = {} 
        
        punti_scansione = self.generate_grid(center_lat, center_lng, step_km=2.0, grid_steps=grid_steps)
        
        print("\nAvvio scansione radar. Potrebbe volerci qualche minuto...")
        
        for idx, (lat, lng) in enumerate(punti_scansione, 1):
            print(f"Scansione quadrante {idx}/{len(punti_scansione)}...")
            
            for keyword in keywords:
                leads_trovati = self.fetch_leads_by_location(keyword, lat, lng)
                
                for lead in leads_trovati:
                    all_leads[lead["ID Univoco"]] = lead
                
                time.sleep(1) 

        lista_finale = list(all_leads.values())
        self._save_to_excel(lista_finale)

    def _save_to_excel(self, leads: List[Dict], filename: str = "database_leads.xlsx"):
        if not leads:
            print("\nNessun lead trovato. Prova ad allargare la zona o cambiare keyword.")
            return

        df = pd.DataFrame(leads)
        df = df.drop(columns=['ID Univoco'])
        df.to_excel(filename, index=False)
        print(f"\n🎯 MISSIONE COMPIUTA! {len(leads)} lead UNICI salvati in '{filename}'")

# --- Esecuzione ---
if __name__ == "__main__":
    API_KEY = os.getenv("GOOGLE_API_KEY")
    
    if not API_KEY:
        print("Errore: GOOGLE_API_KEY non trovata nel file .env")
    else:
        scouter = LeadHunterScouter(API_KEY)
        
        LAT_SCHIO = 45.7145
        LNG_SCHIO = 11.3582
        
        le_mie_keyword = ["ristorante", "pizzeria", "trattoria", "bar"]
        
        scouter.run_campaign(
            center_lat=LAT_SCHIO, 
            center_lng=LNG_SCHIO, 
            keywords=le_mie_keyword, 
            grid_steps=1 
        )