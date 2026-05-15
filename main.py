import sys
import time
import argparse
from typing import Dict, List, Any

# Importiamo le versioni "Senior" dei nostri moduli dal package 'src'
from src.scraper import LeadScraper
from src.auditor import LeadAuditor
from src.exporter import DataExporter

class LeadHunterOrchestrator:
    def __init__(self):
        self.scraper = LeadScraper()
        self.auditor = LeadAuditor()
        # Dizionario unificato per la deduplicazione
        self.all_leads: Dict[str, Dict[str, Any]] = {} 

    def run(self, lat: float, lng: float, keywords: List[str]):
        print("\n🚀 === AVVIO LEAD HUNTER V3 (ENTERPRISE) === 🚀")
        print(f"📍 Centro coordinate: {lat}, {lng}")
        print(f"🎯 Nicchie in target: {', '.join(keywords)}\n")

        try:
            # ==========================================
            # FASE 1: DATA EXTRACTION & DEDUPLICAZIONE
            # ==========================================
            print(">>> FASE 1: Scansione Radar Google Maps")
            
            raw_leads_to_audit = [] # Lista temporanea dei lead che necessitano dell'AI
            competitors_by_niche = {}

            for keyword in keywords:
                print(f"\n🔍 Ricerca: '{keyword.upper()}'...")
                
                # Sfruttiamo il metodo orchestrato dello scraper (versione 10/10)
                places = self.scraper.scrape_entire_grid(keyword, lat, lng)
                
                # Estraiamo il top competitor per questa specifica nicchia
                top_competitor = self.scraper.identify_top_competitor(places)
                competitors_by_niche[keyword] = top_competitor
                print(f"   👑 Top Competitor identificato: {top_competitor}")

                # Filtro e Deduplicazione
                for place in places:
                    place_id = place.get("id")
                    
                    if not place_id:
                        continue
                        
                    # Se non ha il sito web ed è un NUOVO lead
                    if not place.get("websiteUri") and place_id not in self.all_leads:
                        # Lo registriamo per elaborarlo dopo
                        self.all_leads[place_id] = place
                        
                        # Salviamo un riferimento veloce per la Fase 2 (con metadati)
                        raw_leads_to_audit.append({
                            "id": place_id,
                            "place_data": place,
                            "keyword": keyword,
                            "competitor": top_competitor
                        })

            print(f"\n✅ FASE 1 Completata. Trovati {len(raw_leads_to_audit)} lead unici sprovvisti di sito web.")

            if not raw_leads_to_audit:
                print("Nessun lead trovato in questa zona. Termino il programma.")
                return

            # ==========================================
            # FASE 2: ENRICHMENT CON LLM (OpenRouter)
            # ==========================================
            print("\n>>> FASE 2: Auditing AI e Generazione Sales Hook")
            
            for idx, item in enumerate(raw_leads_to_audit, 1):
                p_id = item["id"]
                p_data = item["place_data"]
                k_word = item["keyword"]
                comp = item["competitor"]
                
                b_name = p_data.get("displayName", {}).get("text", "Sconosciuto")
                print(f"   ⏳ [{idx}/{len(raw_leads_to_audit)}] Auditing LLM: {b_name} ({k_word})...")
                
                # Chiamata alla versione Senior dell'Auditor (passando la categoria)
                audit_results = self.auditor.audit_lead(p_data, category=k_word, competitor=comp)
                
                # Aggiorniamo il dizionario globale con i dati arricchiti
                self.all_leads[p_id].update(audit_results)
                self.all_leads[p_id]["competitor"] = comp
                self.all_leads[p_id]["search_keyword"] = k_word # Utile per i report

            print("\n✅ FASE 2 Completata.")

        except KeyboardInterrupt:
            print("\n\n⚠️ Interruzione manuale (CTRL+C) rilevata!")
            print("Salvataggio d'emergenza dei dati estratti finora...")
        except Exception as e:
            print(f"\n\n❌ ERRORE CRITICO: {e}")
            print("Salvataggio d'emergenza dei dati estratti finora...")
            
        finally:
            # ==========================================
            # FASE 3: ESPORTAZIONE DATI SICURA
            # ==========================================
            # Questo blocco 'finally' garantisce che l'export avvenga SEMPRE, 
            # anche in caso di crash al 99% del processo.
            print("\n>>> FASE 3: Esportazione Excel")
            if self.all_leads:
                # Usiamo il DataExporter Senior
                DataExporter.export_to_excel(self.all_leads, filename="lead_hunter_output.xlsx")
            else:
                print("Nessun dato da salvare.")
                
            print("\n🏁 --- MISSIONE COMPLETATA ---")

if __name__ == "__main__":
    # Implementazione di argparse per rendere lo script professionale da terminale
    parser = argparse.ArgumentParser(description="Lead Hunter v3 - AI B2B Lead Generation")
    
    # Coordinate di default: Schio (VI)
    parser.add_argument("--lat", type=float, default=45.7145, help="Latitudine del centro di ricerca")
    parser.add_argument("--lng", type=float, default=11.3582, help="Longitudine del centro di ricerca")
    parser.add_argument("--keywords", type=str, nargs='+', default=["ristorante", "pizzeria", "meccanico", "dentista"], 
                        help="Lista di parole chiave separate da spazio (es. --keywords ristorante hotel spa)")
    
    args = parser.parse_args()

    orchestrator = LeadHunterOrchestrator()
    orchestrator.run(args.lat, args.lng, args.keywords)