"""
Lead Hunter V3 — Main Orchestrator & CLI
Supporta due modalità operative:
  - "no_website": Lead senza sito web (funnel originale semplificato)
  - "with_website": Lead con sito web + crawling + audit AI completo
"""

import os
import sys
import asyncio
import argparse
import textwrap
import subprocess
from datetime import datetime
from typing import Dict, List, Callable, Optional

from src.scraper import LeadScraper
from src.auditor import LeadAuditor
from src.application.container import ApplicationContainer
from src.application.provenance import build_verified_lead
from src.domain.discovery import TransientCandidate
from src.domain.provenance import VerifiedLead
from src.exporter import DataExporter
from src.crawler import HybridCrawler
from src.security.privacy import redact_sensitive_text
from src.filters import (
    filter_by_business_age,
    filter_ecommerce,
    filter_franchise,
    extract_domain,
    filter_social_media,
)
from src.config import (
    MIN_RATING, MAX_REVIEWS, MIN_BUSINESS_AGE_YEARS,
    MAX_CRAWL_PAGES, DEFAULT_TOKEN_MODE, ECOMMERCE_INDICATORS, KNOWN_FRANCHISES,
    SOCIAL_MEDIA_DOMAINS, OUTPUT_DIR,
)
from src.settings import ApplicationSettings, SettingsError


class LeadHunterOrchestrator:
    """Core Engine disaccoppiato dalla UI. Può essere invocato da CLI, GUI o API esterne."""

    def __init__(
        self,
        mode: str,
        *,
        scraper: LeadScraper,
        auditor: Optional[LeadAuditor] = None,
    ):
        self.mode = mode
        self.scraper = scraper
        self.auditor = auditor
        self.all_leads: Dict[str, VerifiedLead] = {}
        self.transient_results: List[TransientCandidate] = []

    # ==========================================
    # MODALITÀ 1: LEAD SENZA SITO WEB
    # ==========================================
    def run_no_website(
        self,
        lat: float, lng: float, keywords: List[str],
        on_kw_start=None, on_kw_progress=None, on_kw_end=None
    ) -> List[TransientCandidate]:
        """Risultati transitori mostrabili solo con attribuzione provider."""
        seen: set[tuple[str, str]] = set()
        results: list[TransientCandidate] = []

        print("\n🔍 --- FASE 1: Scraping Google Maps ---")
        for keyword in keywords:
            if on_kw_start:
                on_kw_start(keyword)

            def _grid_progress(current, total):
                if on_kw_progress:
                    on_kw_progress(keyword, current, total)

            places = self.scraper.scrape_entire_grid(keyword, lat, lng, on_progress=_grid_progress)
            new_count = 0
            for place in places:
                key = (place.provider, place.external_id)
                if not place.website_url and key not in seen:
                    seen.add(key)
                    results.append(place)
                    new_count += 1

            if on_kw_end:
                on_kw_end(keyword, new_count)
            print(f"✅ Trovati {new_count} nuovi lead per '{keyword}'.")

        if not results:
            print("⚠️ Nessun lead senza sito web trovato.")
            return []
        self.transient_results = results
        print("\n✅ Tutte le fasi completate.")
        return results

    # ==========================================
    # MODALITÀ 2: LEAD CON SITO WEB + AUDIT
    # ==========================================
    def run_with_website(
        self,
        lat: float, lng: float, keywords: List[str],
        min_rating: float = MIN_RATING,
        max_reviews: int = MAX_REVIEWS,
        min_age: int = MIN_BUSINESS_AGE_YEARS,
        max_pages: int = MAX_CRAWL_PAGES,
        token_mode: str = DEFAULT_TOKEN_MODE,
        headless: bool = True,
        on_phase: Optional[Callable] = None,
        on_progress: Optional[Callable] = None,
        on_crawl_progress: Optional[Callable] = None,
        on_audit_progress: Optional[Callable] = None,
        on_log: Optional[Callable] = None,
    ) -> List[VerifiedLead]:
        """
        Pipeline completa per lead con sito web (Streaming Parallelo).
        on_phase: Callable[[str, str], None] — (fase_id, descrizione)
        on_progress: Callable[[int, int], None] — (corrente, totale) (usato per scraping)
        on_crawl_progress: Callable[[int, int], None]
        on_audit_progress: Callable[[int, int], None]
        on_log: Callable[[str], None] — messaggio di log
        """
        if self.auditor is None:
            raise RuntimeError("Auditor non configurato per la pipeline with_website.")

        def log(msg):
            safe_message = redact_sensitive_text(msg)
            print(safe_message)
            if on_log:
                on_log(safe_message)

        # --- FASE 1: Scraping Google Maps ---
        if on_phase:
            on_phase("scraping", "Scraping Google Maps...")
        log("🔍 FASE 1: Scraping Google Maps")

        all_places: list[tuple[TransientCandidate, str]] = []
        seen_candidates: set[tuple[str, str]] = set()
        for keyword in keywords:
            log(f"   🏷️ Keyword: {keyword}")

            def _progress(current, total):
                if on_progress:
                    on_progress(current, total)

            places = self.scraper.scrape_entire_grid(keyword, lat, lng, on_progress=_progress)

            valid_new = 0
            for place in places:
                key = (place.provider, place.external_id)
                if place.website_url and key not in seen_candidates:
                    seen_candidates.add(key)
                    all_places.append((place, keyword))
                    valid_new += 1

            log(f"   ✅ {len(places)} risultati unici per '{keyword}' -> Aggiunti {valid_new} nuovi lead (Totale parziale: {len(all_places)})")

        if not all_places:
            log("⚠️ Nessun lead con sito web trovato.")
            return []

        # --- FASE 2: Filtro URL social (rating e recensioni non richiesti) ---
        if on_phase:
            on_phase("filtering_reviews", "Filtro domini social...")
        log("\n📊 FASE 2: Filtro domini social")

        filtered_places = []
        for place, keyword in all_places:
            website = place.website_url or ""
            domain = extract_domain(website)
            if filter_social_media(domain, SOCIAL_MEDIA_DOMAINS):
                log("   ❌ Escluso un risultato con dominio social")
                continue
            filtered_places.append((place, keyword))

        log(f"   ✅ {len(filtered_places)}/{len(all_places)} lead superano i filtri preliminari")

        if not filtered_places:
            log("⚠️ Nessun lead supera i filtri preliminari.")
            return []

        # --- FASE 3-6: Pipeline Parallela (Crawling -> Filtraggio -> Audit) ---
        if on_phase:
            on_phase("crawling", "Pipeline Streaming: Crawling & Auditing in parallelo...")
        log(f"\n🕷️🧠 PIPELINE STREAMING: Crawling ({max_pages} pag) -> Auditing AI")

        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        crawler = HybridCrawler(max_pages=max_pages, token_mode=token_mode, headless=headless)
        
        total_to_crawl = len(filtered_places)
        total_to_audit = 0
        audits_completed = 0
        
        audit_executor = ThreadPoolExecutor(max_workers=6)
        audit_futures = {}
        valid_lead_ids: list[str] = []

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            for idx, (place, keyword) in enumerate(filtered_places, 1):
                p_id = place.external_id
                website = place.website_url or ""
                
                # Update Crawl Progress
                if on_crawl_progress:
                    on_crawl_progress(idx, total_to_crawl)
                
                log(f"   🌐 [{idx}/{total_to_crawl}] Verifica sito ufficiale")
                
                try:
                    crawl_res = loop.run_until_complete(crawler.crawl(website))

                    if not crawl_res.is_auditable:
                        reason = crawl_res.audit_rejection_reason or "evidenza_insufficiente"
                        log(f"      ❌ Audit non accodato: crawl non valido ({reason})")
                        continue

                    if crawl_res.emails:
                        log(f"      📧 {len(crawl_res.emails)} email professionali rilevate")
                    if crawl_res.is_dynamic:
                        log(f"      ⚡ JS (Playwright)")
                        
                    # Fase 4: Filtro Età
                    verified = build_verified_lead(crawl_res, search_keyword=keyword)
                    domain = extract_domain(verified.website)
                    if not filter_by_business_age(domain, crawl_res.raw_html_home, min_age):
                        log("   ❌ Escluso: dominio troppo recente")
                        continue
                        
                    # Fase 5: Filtro Scala
                    # if filter_ecommerce(crawl_res.raw_html_home, ECOMMERCE_INDICATORS):
                    #     log(f"   ❌ Escluso (e-commerce): {name}")
                    #     continue
                    if filter_franchise(verified.business_name, [], KNOWN_FRANCHISES):
                        log("   ❌ Escluso: franchise noto")
                        continue
                        
                    # Superati tutti i filtri: accoda per l'AI Audit
                    valid_lead_ids.append(p_id)
                    total_to_audit += 1

                    audit_payload = {
                        "crawl_pages": crawl_res.pages,
                        "business_name": verified.business_name,
                        "category": verified.category,
                        "rating": 0,
                        "review_count": 0,
                    }
                    future = audit_executor.submit(self.auditor.audit_website, **audit_payload)
                    audit_futures[future] = (p_id, crawl_res, keyword)
                    
                    if on_audit_progress:
                        on_audit_progress(audits_completed, total_to_audit)
                        
                except Exception as e:
                    log(f"      ❌ Errore crawling ({type(e).__name__})")

                # Poll per audit completati nel frattempo (non bloccante)
                done_futures = [f for f in audit_futures if f.done()]
                for f in done_futures:
                    pid, crawl_res, keyword = audit_futures.pop(f)
                    try:
                        res = f.result()
                        self.all_leads[pid] = build_verified_lead(
                            crawl_res, search_keyword=keyword, audit=res
                        )
                        audits_completed += 1
                        log("   🧠 Audit completato su dati del sito ufficiale")
                    except Exception as e:
                        log(f"   ❌ Errore Audit per {pid}: {e}")
                        audits_completed += 1
                    if on_audit_progress:
                        on_audit_progress(audits_completed, total_to_audit)

        finally:
            loop.run_until_complete(crawler.close())
            loop.close()
            
        if audit_futures:
            log(f"\n⏳ Attesa completamento di {len(audit_futures)} audit AI in background...")
            for future in as_completed(audit_futures.keys()):
                pid, crawl_res, keyword = audit_futures.pop(future)
                try:
                    res = future.result()
                    self.all_leads[pid] = build_verified_lead(
                        crawl_res, search_keyword=keyword, audit=res
                    )
                    audits_completed += 1
                    log("   🧠 Audit completato su dati del sito ufficiale")
                except Exception as e:
                    log(f"   ❌ Errore Audit per {pid}: {e}")
                    audits_completed += 1
                    
                if on_audit_progress:
                    on_audit_progress(audits_completed, total_to_audit)

        audit_executor.shutdown(wait=True)
        log(f"\n✅ Pipeline completata: {len(self.all_leads)} lead verificati su {len(all_places)}.")
        return [self.all_leads[p_id] for p_id in valid_lead_ids if p_id in self.all_leads]

    # ==========================================
    # DISPATCHER PRINCIPALE
    # ==========================================
    def run(
        self, lat: float, lng: float, keywords: List[str], **kwargs
    ) -> List[VerifiedLead] | List[TransientCandidate]:
        """Dispatcher che smista alla pipeline corretta in base al mode."""
        if self.mode == "with_website":
            if self.auditor is None:
                raise RuntimeError("Auditor non configurato per la pipeline with_website.")
            return self.run_with_website(lat, lng, keywords, **kwargs)
        return self.run_no_website(
            lat, lng, keywords,
            on_kw_start=kwargs.get("on_kw_start"),
            on_kw_progress=kwargs.get("on_kw_progress"),
            on_kw_end=kwargs.get("on_kw_end"),
        )


def create_orchestrator(
    mode: str,
    settings: Optional[ApplicationSettings] = None,
) -> LeadHunterOrchestrator:
    """Build provider dependencies at an explicit application boundary."""
    runtime_settings = settings or ApplicationSettings.from_environment()
    runtime_settings.require_pipeline(mode)
    container = ApplicationContainer(runtime_settings)
    return LeadHunterOrchestrator(
        mode=mode,
        scraper=container.build_scraper(),
        auditor=container.build_auditor() if mode == "with_website" else None,
    )


# ==========================================
# CLI PROFESSIONALE
# ==========================================
def show_examples():
    """Stampa esempi d'uso."""
    examples = """
    ESEMPI DI UTILIZZO - LEAD HUNTER V3:

    1. Avvio Interfaccia Grafica (GUI):
       python main.py --gui

    2. Ricerca base CLI - Senza Sito Web:
       python main.py --mode no_website --lat 45.4642 --lng 9.1900 --keywords ristorante

    3. Ricerca avanzata CLI - Con Sito Web + Audit:
       python main.py --mode with_website --lat 45.4642 --lng 9.1900 --keywords ristorante pizzeria

    4. Audit con parametri personalizzati:
       python main.py --mode with_website --lat 45.4642 --lng 9.1900 --keywords dentista \\
           --min-rating 4.0 --max-reviews 80 --min-age 3 --token-mode optimized --max-pages 3

    Suggerimento: Le coordinate (lat/lng) in formato decimale (es. Google Maps).
    """
    print(textwrap.dedent(examples))
    sys.exit(0)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    try:
        runtime_settings = ApplicationSettings.from_environment()
    except SettingsError as exc:
        print(f"Configurazione non valida: {exc}")
        sys.exit(2)
    parser = argparse.ArgumentParser(
        prog="LeadHunter",
        description="Agente AI B2B per Scraping & Auditing di contatti commerciali.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="Usa il flag --examples per vedere i casi d'uso comuni."
    )

    # Argomenti principali
    parser.add_argument("--lat", type=float, help="Latitudine (es. 45.4642 per Milano)")
    parser.add_argument("--lng", type=float, help="Longitudine (es. 9.1900 per Milano)")
    parser.add_argument("--keywords", type=str, nargs='+', help="Lista di keyword (es. ristorante bar)")
    parser.add_argument("--out", type=str, default="leads_output.xlsx", help="Nome file Excel in uscita")

    # Modalità operativa
    parser.add_argument("--mode", type=str, choices=["no_website", "with_website"],
                        default="no_website", help="Modalità: no_website | with_website")

    # Parametri modalità with_website
    parser.add_argument("--min-rating", type=float, default=MIN_RATING,
                        help=f"Rating minimo Google (default: {MIN_RATING})")
    parser.add_argument("--max-reviews", type=int, default=MAX_REVIEWS,
                        help=f"Max recensioni (default: {MAX_REVIEWS})")
    parser.add_argument("--min-age", type=int, default=MIN_BUSINESS_AGE_YEARS,
                        help=f"Età minima attività in anni (default: {MIN_BUSINESS_AGE_YEARS})")
    parser.add_argument("--token-mode", type=str, choices=["high_fidelity", "optimized"],
                        default=runtime_settings.token_mode,
                        help=f"Modalità token LLM (default: {runtime_settings.token_mode})")
    parser.add_argument("--max-pages", type=int, default=MAX_CRAWL_PAGES,
                        help=f"Max pagine da crawlare per sito (default: {MAX_CRAWL_PAGES})")
    parser.add_argument("--no-headless", action="store_true",
                        help="Disabilita la modalità headless di Playwright (esegue il browser visibile headed)")

    # Flag speciali
    parser.add_argument("--test-url", type=str, help="Esegue un test diagnostico completo su un singolo URL")
    parser.add_argument(
        "--save-diagnostic-artifacts",
        action="store_true",
        help="Salva esplicitamente HTML e testi sensibili del test in test_output/",
    )
    parser.add_argument(
        "--diagnostic-retention-hours",
        type=int,
        default=24,
        help="Retention degli artefatti diagnostici espliciti (default: 24 ore)",
    )
    parser.add_argument("--gui", action="store_true", help="Avvia l'interfaccia grafica Streamlit")
    parser.add_argument("--examples", action="store_true", help="Mostra gli esempi d'uso ed esci")

    args = parser.parse_args()

    if args.examples:
        show_examples()

    if args.test_url:
        from src.tester import run_url_test
        try:
            container = ApplicationContainer(runtime_settings)
            run_url_test(
                args.test_url,
                max_pages=args.max_pages,
                token_mode=args.token_mode,
                headless=not args.no_headless,
                save_artifacts=args.save_diagnostic_artifacts,
                retention_hours=args.diagnostic_retention_hours,
                auditor=container.build_auditor(),
            )
        except SettingsError as exc:
            print(f"Configurazione non valida: {exc}")
            sys.exit(2)
        sys.exit(0)

    if args.gui:
        print("🎨 Avvio interfaccia grafica Streamlit...")
        try:
            subprocess.run([sys.executable, "-m", "streamlit", "run", "src/gui.py"], check=True)
        except (FileNotFoundError, subprocess.CalledProcessError):
            print("❌ Errore: Impossibile avviare Streamlit. Installa con: pip install streamlit")
        except KeyboardInterrupt:
            print("\n👋 GUI chiusa correttamente.")
        sys.exit(0)

    if not args.lat or not args.lng or not args.keywords:
        print("❌ Errore: --lat, --lng e --keywords sono obbligatori.")
        print("Usa 'python main.py --help' per assistenza.")
        sys.exit(1)

    try:
        orchestrator = create_orchestrator(args.mode, runtime_settings)
    except SettingsError as exc:
        print(f"Configurazione non valida: {exc}")
        sys.exit(2)

    print(f"\n🚀 Avvio Lead Hunter V3 CLI — Modalità: {args.mode.upper()}")
    print(f"   Coordinate: {args.lat}, {args.lng}")

    out_file = args.out
    if out_file == "leads_output.xlsx":
        city = orchestrator.scraper.get_city_name(args.lat, args.lng)
        date_str = datetime.now().strftime("%d_%m_%Y")
        out_file = f"Lead_Hunter_{city}_{date_str}.xlsx"

    # Prepend OUTPUT_DIR if it's a bare filename
    if not os.path.dirname(out_file):
        out_file = os.path.join(OUTPUT_DIR, out_file)

    try:
        if args.mode == "with_website":
            results = orchestrator.run(
                args.lat, args.lng, args.keywords,
                min_rating=args.min_rating,
                max_reviews=args.max_reviews,
                min_age=args.min_age,
                max_pages=args.max_pages,
                token_mode=args.token_mode,
                headless=not args.no_headless,
            )
        else:
            results = orchestrator.run(args.lat, args.lng, args.keywords)

        if results and args.mode == "with_website":
            DataExporter.export_to_excel(results, mode=args.mode, filename=out_file)
            print(f"✅ Completato. {len(results)} leads esportati in {out_file}")
        elif results:
            attribution = orchestrator.scraper.attribution
            print(f"✅ {len(results)} risultati transitori trovati — dati {attribution.label}.")
            print(
                "ℹ️ L'esportazione è disabilitata: i risultati senza sito possono "
                "essere consultati solo durante questa sessione con attribuzione."
            )
            for candidate in results:
                print(f"   • {candidate.display_name or 'Attività senza nome'}")
            print(f"   Termini: {attribution.terms_url}")
        else:
            print("⚠️ Nessun lead utile trovato nell'area.")

    except KeyboardInterrupt:
        print("\n⚠️ Interrotto. Esporto dati parziali...")
        if args.mode == "with_website" and orchestrator.all_leads:
            emergency_file = os.path.join(OUTPUT_DIR, "salvataggio_emergenza.xlsx")
            DataExporter.export_to_excel(
                list(orchestrator.all_leads.values()),
                mode=args.mode,
                filename=emergency_file
            )
