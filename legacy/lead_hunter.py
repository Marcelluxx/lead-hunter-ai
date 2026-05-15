import requests
import pandas as pd
from typing import List, Dict
import os
from dotenv import load_dotenv

# Carica le variabili d'ambiente dal file .env
load_dotenv()

class LeadHunterEngine:
    def __init__(self, api_key: str):
        self.api_key = api_key
        # Usiamo l'endpoint "New" delle Google Places API
        self.base_url = "https://places.googleapis.com/v1/places:searchText"
        self.headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            # Chiediamo solo i campi essenziali per non sprecare budget
            "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.nationalPhoneNumber,places.websiteUri,places.rating"
        }

    def fetch_leads(self, query: str) -> List[Dict]:
        """Cerca attività e filtra quelle che non hanno un sito web."""
        leads = []
        payload = {
            "textQuery": query,
            "languageCode": "it",
            "maxResultCount": 20 
        }
        
        print(f"Interrogando Google per: '{query}'...")
        
        try:
            response = requests.post(self.base_url, json=payload, headers=self.headers)
            response.raise_for_status()
            results = response.json().get("places", [])

            for place in results:
                # Se 'websiteUri' non è presente, il business non ha un sito registrato
                if "websiteUri" not in place:
                    lead_data = {
                        "Nome": place.get("displayName", {}).get("text", "N/A"),
                        "Indirizzo": place.get("formattedAddress", "N/A"),
                        "Telefono": place.get("nationalPhoneNumber", "N/A"),
                        "Rating": place.get("rating", "N/A")
                    }
                    leads.append(lead_data)
            
            return leads

        except Exception as e:
            print(f"Errore tecnico: {e}")
            return []

    def save_to_excel(self, leads: List[Dict], filename: str = "leads_fase1.xlsx"):
        """Esporta i dati in un file Excel."""
        if not leads:
            print("Nessun lead trovato senza sito web in questa ricerca.")
            return

        df = pd.DataFrame(leads)
        df.to_excel(filename, index=False)
        print(f"Successo! {len(leads)} lead salvati in '{filename}'")

# --- Esecuzione ---
if __name__ == "__main__":
    # Recupera la chiave dalla variabile d'ambiente
    API_KEY = os.getenv("GOOGLE_API_KEY")
    
    if not API_KEY:
        print("Errore: GOOGLE_API_KEY non trovata nel file .env")
    else:
        hunter = LeadHunterEngine(API_KEY)
    
    # Facciamo un test sulla tua zona
    risultati = hunter.fetch_leads("ristoranti a Schio")
    
    hunter.save_to_excel(risultati)