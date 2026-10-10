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
from pathlib import Path
from typing import Dict, List, Callable, Optional, Sequence

from src.scraper import LeadScraper
from src.auditor import LeadAuditor
from src.application.container import ApplicationContainer
from src.application.provenance import build_verified_lead
from src.domain.discovery import TransientCandidate
from src.domain.feature_licenses import LicenseError
from src.domain.place_references import ReferenceExportError, project_google_place_references
from src.domain.provenance import VerifiedLead
from src.exporter import DataExporter
from src.crawler import HybridCrawler
from src.security.presentation import normalize_console_text
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
from functools import wraps
from src.application.rating_filters import RatingFilterGuard
from src.domain.rating_filters import RatingFilterCriteria


def _result_operation(method):
    @wraps(method)
    def guarded(self, *args, **kwargs):
        self.all_leads.clear()
        self.transient_results.clear()
        try:
            if self.result_origin is not None:
                self.result_origin.require_execute()
            result = method(self, *args, **kwargs)
            self.require_result_view()
            return result
        except BaseException:
            if self.result_origin is not None:
                self.all_leads.clear()
                self.transient_results.clear()
            raise
    return guarded


class LeadHunterOrchestrator:
    """Core Engine disaccoppiato dalla UI. Può essere invocato da CLI, GUI o API esterne."""

    def __init__(
        self,
        mode: str,
        *,
        scraper: LeadScraper,
        auditor: Optional[LeadAuditor] = None,
        result_origin: RatingFilterGuard | None = None,
    ):
        self.mode = mode
        self.scraper = scraper
        self.auditor = auditor
        if result_origin is not None and not isinstance(result_origin, RatingFilterGuard):
            raise ValueError('rating_filter_invalid')
        self.result_origin = result_origin
        self.all_leads: Dict[str, VerifiedLead] = {}
        self.transient_results: List[TransientCandidate] = []

    def require_result_view(self) -> None:
        if self.result_origin is not None:
            self.result_origin.require_view()

    # ==========================================
    # MODALITÀ 1: LEAD SENZA SITO WEB
    # ==========================================
    @_result_operation
    def run_no_website(
        self,
        lat: float, lng: float, keywords: List[str],
        on_kw_start=None, on_kw_progress=None, on_kw_end=None
    ) -> List[TransientCandidate]:
        """Risultati transitori mostrabili solo con attribuzione provider."""
        seen: set[tuple[str, str]] = set()
        results: list[TransientCandidate] = []

        print(normalize_console_text("\n🔍 --- FASE 1: Scraping Google Maps ---"))
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
            print(normalize_console_text(f"✅ Trovati {new_count} nuovi lead per '{keyword}'."))

        if not results:
            print(normalize_console_text("⚠️ Nessun lead senza sito web trovato."))
            return []
        self.transient_results = results
        print(normalize_console_text("\n✅ Tutte le fasi completate."))
        return results

    # ==========================================
    # MODALITÀ 2: LEAD CON SITO WEB + AUDIT
    # ==========================================
    @_result_operation
    def run_with_website(
        self,
        lat: float, lng: float, keywords: List[str],
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
            print(normalize_console_text(safe_message))
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

        def authorized_audit(**payload):
            if self.result_origin is not None:
                self.result_origin.require_execute()
            return self.auditor.audit_website(**payload)
        
        try:
            for idx, (place, keyword) in enumerate(filtered_places, 1):
                if self.result_origin is not None:
                    self.result_origin.require_execute()
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
                    future = audit_executor.submit(authorized_audit, **audit_payload)
                    audit_futures[future] = (p_id, crawl_res, keyword)
                    
                    if on_audit_progress:
                        on_audit_progress(audits_completed, total_to_audit)
                        
                except LicenseError:
                    raise
                except Exception as e:
                    log(f"      ❌ Errore crawling ({type(e).__name__})")
                    if self.result_origin is not None:
                        raise RuntimeError('pipeline_failed') from None

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
                    except LicenseError:
                        raise
                    except Exception as e:
                        log(f"   ❌ Errore Audit ({type(e).__name__})")
                        if self.result_origin is not None:
                            raise RuntimeError('pipeline_failed') from None
                        audits_completed += 1
                    if on_audit_progress:
                        on_audit_progress(audits_completed, total_to_audit)

        finally:
            try:
                loop.run_until_complete(crawler.close())
            finally:
                loop.close()
                audit_executor.shutdown(wait=True)
            
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
                except LicenseError:
                    raise
                except Exception as e:
                    log(f"   ❌ Errore Audit ({type(e).__name__})")
                    if self.result_origin is not None:
                        raise RuntimeError('pipeline_failed') from None
                    audits_completed += 1
                    
                if on_audit_progress:
                    on_audit_progress(audits_completed, total_to_audit)

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
    *,
    rating_criteria: RatingFilterCriteria | None = None,
    rating_guard: RatingFilterGuard | None = None,
) -> LeadHunterOrchestrator:
    """Build provider dependencies at an explicit application boundary."""
    if ((rating_criteria is not None and not isinstance(rating_criteria, RatingFilterCriteria)) or
        (rating_guard is not None and (rating_criteria is None or not isinstance(rating_guard, RatingFilterGuard)))):
        raise ValueError('rating_filter_invalid')
    runtime_settings = settings or ApplicationSettings.from_environment()
    container = ApplicationContainer(runtime_settings)
    if rating_criteria is not None:
        rating_guard = rating_guard or container.build_local_rating_filter_guard()
        rating_guard.require_execute()
    runtime_settings.require_pipeline(mode)
    return LeadHunterOrchestrator(
        mode=mode,
        scraper=(container.build_scraper(rating_criteria=rating_criteria, rating_guard=rating_guard)
                 if rating_criteria is not None else container.build_scraper()),
        auditor=container.build_auditor() if mode == "with_website" else None,
        result_origin=rating_guard,
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
           --rating-filters --min-rating 4.0 --max-reviews 80 --min-age 3 --token-mode optimized --max-pages 3

    Suggerimento: Le coordinate (lat/lng) in formato decimale (es. Google Maps).
    """
    print(textwrap.dedent(examples))
    sys.exit(0)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

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
    parser.add_argument("--export-references", action="store_true",
                        help="Esporta soltanto Place ID e link Maps; richiede la licenza export.no_website")

    # Modalità operativa
    parser.add_argument("--mode", type=str, choices=["no_website", "with_website"],
                        default="no_website", help="Modalità: no_website | with_website")

    parser.add_argument('--rating-filters', action='store_true',
                        help='Filtra per rating e recensioni in entrambe le modalità; richiede discovery.rating_filters')
    parser.add_argument("--min-rating", type=float, default=None,
                        help=f"Rating strettamente superiore alla soglia, con --rating-filters (default: {MIN_RATING})")
    parser.add_argument("--max-reviews", type=int, default=None,
                        help=f"Recensioni da 1 al massimo, con --rating-filters (default: {MAX_REVIEWS})")
    parser.add_argument("--min-age", type=int, default=MIN_BUSINESS_AGE_YEARS,
                        help=f"Età minima attività in anni (default: {MIN_BUSINESS_AGE_YEARS})")
    parser.add_argument("--token-mode", type=str, choices=["high_fidelity", "optimized"],
                        default=None,
                        help=f"Modalità token LLM (default: TOKEN_MODE configurato oppure {DEFAULT_TOKEN_MODE})")
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

    args = parser.parse_args(argv)
    thresholds_present = args.min_rating is not None or args.max_reviews is not None
    if (args.rating_filters or thresholds_present) and (args.test_url or args.gui or args.examples):
        parser.error('Le opzioni rating non sono compatibili con --test-url, --gui o --examples')
    if thresholds_present and not args.rating_filters:
        parser.error('--min-rating e --max-reviews richiedono --rating-filters')
    rating_criteria = None
    if args.rating_filters:
        try:
            rating_criteria = RatingFilterCriteria(MIN_RATING if args.min_rating is None else args.min_rating,
                                                  MAX_REVIEWS if args.max_reviews is None else args.max_reviews)
        except ValueError:
            print('Parametri del filtro non validi: rating_filter_invalid')
            return 2
    if args.export_references and args.mode != "no_website":
        parser.error("--export-references richiede --mode no_website")
    try:
        runtime_settings = ApplicationSettings.from_environment()
    except SettingsError as exc:
        print(f"Configurazione non valida: {exc}")
        return 2
    if args.token_mode is None:
        args.token_mode = runtime_settings.token_mode

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
            return 2
        return 0

    if args.gui:
        print("🎨 Avvio interfaccia grafica Streamlit...")
        try:
            subprocess.run([sys.executable, "-m", "streamlit", "run", "src/gui.py",
                            "--server.address", "127.0.0.1"], check=True)
        except (FileNotFoundError, subprocess.CalledProcessError):
            print("❌ Errore: Impossibile avviare Streamlit. Installa con: pip install streamlit")
        except KeyboardInterrupt:
            print("\n👋 GUI chiusa correttamente.")
        return 0

    if not args.lat or not args.lng or not args.keywords:
        print("❌ Errore: --lat, --lng e --keywords sono obbligatori.")
        print("Usa 'python main.py --help' per assistenza.")
        return 1

    reference_export = None
    try:
        if args.export_references:
            reference_export = ApplicationContainer(runtime_settings).build_local_reference_export_service()
            reference_export.require_access()
        orchestrator = (create_orchestrator(args.mode, runtime_settings, rating_criteria=rating_criteria)
                        if rating_criteria is not None else create_orchestrator(args.mode, runtime_settings))
    except LicenseError as exc:
        print(f"Operazione riservata non autorizzata: {exc.code}")
        return 2
    except SettingsError as exc:
        print(f"Configurazione non valida: {exc}")
        return 2

    except Exception:
        if rating_criteria is not None:
            print('Ricerca filtrata non completata: pipeline_failed')
            return 1
        raise

    print(f"\n🚀 Avvio Lead Hunter V3 CLI — Modalità: {args.mode.upper()}")
    print(f"   Coordinate: {args.lat}, {args.lng}")

    try:
        if rating_criteria is not None:
            orchestrator.result_origin.require_execute()
        out_file = args.out
        if out_file == "leads_output.xlsx":
            city = orchestrator.scraper.get_city_name(args.lat, args.lng)
            date_str = datetime.now().strftime("%d_%m_%Y")
            out_file = f"Lead_Hunter_{city}_{date_str}.xlsx"

        # Prepend OUTPUT_DIR if it's a bare filename
        if not os.path.dirname(out_file):
            out_file = os.path.join(OUTPUT_DIR, out_file)

        if args.mode == "with_website":
            results = orchestrator.run(
                args.lat, args.lng, args.keywords,
                min_age=args.min_age,
                max_pages=args.max_pages,
                token_mode=args.token_mode,
                headless=not args.no_headless,
            )
        else:
            results = orchestrator.run(args.lat, args.lng, args.keywords)

        origin = orchestrator.result_origin if rating_criteria is not None else None
        origin_args = {'origin': origin} if origin is not None else {}
        if origin is not None:
            orchestrator.require_result_view()

        if results and args.mode == "with_website":
            DataExporter.export_to_excel(results, mode=args.mode, filename=out_file, **origin_args)
            if origin is not None:
                origin.require_view()
            print(f"✅ Completato. {len(results)} leads esportati in {out_file}")
        elif results and reference_export is not None:
            references = project_google_place_references(results)
            if references:
                count = reference_export.save(references, Path(out_file), **origin_args)
                if origin is not None:
                    origin.require_view()
                print(f"✅ Completato. {count} riferimenti esportati in {out_file}")
            else:
                print("⚠️ Nessun riferimento Google senza sito da esportare.")
        elif results:
            attribution = orchestrator.scraper.attribution
            lines = [f"✅ {len(results)} risultati transitori trovati — dati {attribution.label}.",
                "ℹ️ I contenuti Google sono transitori. Con --export-references e una "
                "licenza valida puoi esportare soltanto Place ID e link Google Maps."]
            lines.extend(f"   • {candidate.display_name or 'Attività senza nome'}" for candidate in results)
            lines.append(f"   Termini: {attribution.terms_url}")
            message = '\n'.join(lines)
            if origin is not None:
                origin.require_view()
            print(message)
        else:
            print("⚠️ Nessun lead utile trovato nell'area.")

    except (LicenseError, ReferenceExportError) as exc:
        print(f"Operazione riservata non completata: {exc.code}")
        return 2
    except SettingsError as exc:
        print(f"Configurazione non valida: {exc}")
        return 2
    except KeyboardInterrupt:
        if rating_criteria is not None:
            print('Ricerca filtrata interrotta; nessun risultato parziale consegnato.')
            return 1
        print("\n⚠️ Interrotto. Esporto dati parziali...")
        if args.mode == "with_website" and orchestrator.all_leads:
            emergency_file = os.path.join(OUTPUT_DIR, "salvataggio_emergenza.xlsx")
            DataExporter.export_to_excel(
                list(orchestrator.all_leads.values()),
                mode=args.mode,
                filename=emergency_file
            )
    except Exception:
        if rating_criteria is not None:
            print('Ricerca filtrata non completata: pipeline_failed')
            return 1
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
