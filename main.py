import sys
import argparse
import textwrap
import subprocess
from typing import Dict, List, Any

# Importiamo i moduli dal package 'src'
from src.scraper import LeadScraper
from src.auditor import LeadAuditor
from src.exporter import DataExporter

class LeadHunterOrchestrator:
    """Core Engine disaccoppiato dalla UI. Può essere invocato da CLI, GUI o API esterne."""
    def __init__(self):
        self.scraper = LeadScraper()
        self.auditor = LeadAuditor()
        self.all_leads: Dict[str, Dict[str, Any]] = {}

    def run(self, lat: float, lng: float, keywords: List[str]) -> List[Dict[str, Any]]:
        """Esegue il funnel di scraping e auditing. Restituisce i lead arricchiti."""
        raw_leads_to_audit = []
        
        # FASE 1: Scraping e Deduplicazione
        for keyword in keywords:
            places = self.scraper.scrape_entire_grid(keyword, lat, lng)
            top_competitor = self.scraper.identify_top_competitor(places)
            
            for place in places:
                place_id = place.get("id")
                if place_id and not place.get("websiteUri") and place_id not in self.all_leads:
                    self.all_leads[place_id] = place
                    raw_leads_to_audit.append({
                        "id": place_id, "place_data": place,
                        "keyword": keyword, "competitor": top_competitor
                    })

        if not raw_leads_to_audit:
            return []

        # FASE 2: AI Auditing
        for item in raw_leads_to_audit:
            p_id, p_data = item["id"], item["place_data"]
            kw, comp = item["keyword"], item["competitor"]
            
            audit_results = self.auditor.audit_lead(p_data, category=kw, competitor=comp)
            
            self.all_leads[p_id].update(audit_results)
            self.all_leads[p_id]["competitor"] = comp
            self.all_leads[p_id]["search_keyword"] = kw

        return list(self.all_leads.values())


# ==========================================
# CLI PROFESSIONALE (Command Line Interface)
# ==========================================
def show_examples():
    """Stampa esempi d'uso per facilitare l'integrazione AI o umana."""
    examples = """
    🛠️  ESEMPI DI UTILIZZO - LEAD HUNTER V3:

    1. Avvio Interfaccia Grafica (GUI):
       python main.py --gui

    2. Ricerca base CLI (Singola Keyword):
       python main.py --lat 45.4642 --lng 9.1900 --keywords ristorante

    3. Ricerca multipla CLI (Tag multipli):
       python main.py --lat 45.4642 --lng 9.1900 --keywords ristorante pizzeria bar
    
    Suggerimento: Le coordinate (lat/lng) in formato decimale (es. Google Maps).
    """
    print(textwrap.dedent(examples))
    sys.exit(0)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="LeadHunter",
        description="Agente AI B2B per Scraping & Auditing di contatti commerciali.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="Usa il flag --examples per vedere i casi d'uso comuni."
    )
    
    # Gruppo argomenti principali
    parser.add_argument("--lat", type=float, help="Latitudine (es. 45.4642 per Milano)")
    parser.add_argument("--lng", type=float, help="Longitudine (es. 9.1900 per Milano)")
    parser.add_argument("--keywords", type=str, nargs='+', help="Lista di tag (es. ristorante bar)")
    parser.add_argument("--out", type=str, default="leads_output.xlsx", help="Nome file Excel in uscita")
    
    # Flag speciali
    parser.add_argument("--gui", action="store_true", help="Avvia l'interfaccia grafica Streamlit")
    parser.add_argument("--examples", action="store_true", help="Mostra gli esempi d'uso ed esci")
    
    args = parser.parse_args()

    if args.examples:
        show_examples()

    # Gestione Avvio GUI
    if args.gui:
        print("🎨 Avvio interfaccia grafica Streamlit...")
        try:
            subprocess.run(["streamlit", "run", "src/gui.py"], check=True)
        except FileNotFoundError:
            print("❌ Errore: Streamlit non è installato. Esegui 'pip install streamlit'.")
        except KeyboardInterrupt:
            print("\n👋 GUI chiusa correttamente.")
        sys.exit(0)

    # Validazione input CLI
    if not args.lat or not args.lng or not args.keywords:
        print("❌ Errore: --lat, --lng e --keywords sono obbligatori (a meno che non usi --gui o --examples).")
        print("Usa 'python main.py --help' per assistenza.")
        sys.exit(1)

    # Esecuzione orchestratore da CLI
    print(f"\n🚀 Avvio Lead Hunter V3 CLI su coordinate {args.lat}, {args.lng}")
    orchestrator = LeadHunterOrchestrator()
    
    try:
        results = orchestrator.run(args.lat, args.lng, args.keywords)
        if results:
            DataExporter.export_to_excel(results, filename=args.out)
            print(f"✅ Completato. {len(results)} leads esportati in {args.out}")
        else:
            print("⚠️ Nessun lead utile trovato nell'area.")
    except KeyboardInterrupt:
        print("\n⚠️ Interrotto. Esporto dati parziali...")
        if orchestrator.all_leads:
            DataExporter.export_to_excel(list(orchestrator.all_leads.values()), filename="salvataggio_emergenza.xlsx")