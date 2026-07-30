"""
Lead Hunter V3 — CLI URL Testing Module
Persegue il testing completo di un singolo sito web, mostrando e salvando
i passaggi intermedi già prodotti dal crawler protetto e dall'Audit AI.
"""

import os
import re
import json
import asyncio
from typing import Dict, Any
from urllib.parse import urlparse

import sys
import logging

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding='utf-8')

logger = logging.getLogger(__name__)

from src.crawler import HybridCrawler
from src.auditor import LeadAuditor
from src.filters import extract_domain
from src.prompts import SYSTEM_WEBSITE_AUDIT, build_website_audit_prompt

def run_url_test(
    url: str,
    max_pages: int = 5,
    token_mode: str = "high_fidelity",
    headless: bool = True,
) -> None:
    """
    Funzione principale che orchestra il test di un sito web e scrive i risultati
    sia nel terminale che in file temporanei dentro 'test_output/'.
    """
    print(f"\n🧪 INIZIO TEST DI DIAGNOSTICA SITO: {url}")
    print(f"   Max Pagine: {max_pages} | Token Mode: {token_mode} | Headless: {headless}")
    print("=" * 60)

    # 1. Setup Cartella di Output
    output_dir = "test_output"
    html_dir = os.path.join(output_dir, "html")
    proc_dir = os.path.join(output_dir, "processed")

    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(html_dir, exist_ok=True)
    os.makedirs(proc_dir, exist_ok=True)

    report_lines = []
    def log_both(msg: str):
        print(msg)
        report_lines.append(msg)

    log_both(f"📁 Directory di output creata: {os.path.abspath(output_dir)}")
    log_both(f"   - Pagine HTML grezze: {html_dir}")
    log_both(f"   - Testo elaborato per LLM: {proc_dir}\n")

    # 2. Inizializzazione Crawler
    crawler = HybridCrawler(max_pages=max_pages, token_mode=token_mode, headless=headless)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    log_both("🕷️ FASE 1: Crawling e Analisi Struttura...")
    try:
        # Esegui il crawl
        crawl_res = loop.run_until_complete(crawler.crawl(url))
        loop.run_until_complete(crawler.close())
    except Exception as e:
        log_both(f"❌ Errore critico nel crawler: {e}")
        return
    finally:
        loop.close()

    if not crawl_res.pages:
        log_both("❌ Nessuna pagina recuperata dal crawler.")
        if crawl_res.error:
            log_both(f"   Errore: {crawl_res.error}")
        return

    log_both(f"✅ Crawling completato. Trovate {len(crawl_res.pages)} pagine.")
    log_both(f"📧 E-mail estratte da codice: {crawl_res.emails}\n")

    # 3. Salvataggio dei contenuti già recuperati dal crawler protetto.
    # Fetch diagnostici secondari aggirerebbero la URL policy del browser.
    page_idx = 1

    for page_url, processed_text in crawl_res.pages.items():
        parsed_page = urlparse(page_url)
        page_name = parsed_page.path.strip("/").replace("/", "_") or "homepage"
        
        log_both(f"📄 Elaborazione Pagina [{page_idx}]: {page_url}")

        # Salva testo processato per LLM
        txt_path = os.path.join(proc_dir, f"page_{page_idx}_{page_name}_processed.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(processed_text)
        log_both(f"   💾 Testo inviato a LLM salvato in: {txt_path}")

        # CrawlResult conserva l'HTML grezzo della sola homepage.
        if page_idx == 1 and crawl_res.raw_html_home:
            html_path = os.path.join(html_dir, f"page_{page_idx}_{page_name}.html")
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(crawl_res.raw_html_home)
            log_both(f"   💾 HTML grezzo salvato in: {html_path}")

        page_idx += 1
        print("-" * 40)

    log_both(f"\n📂 Totale file salvati:")
    log_both(f"   - HTML homepage: {'sì' if crawl_res.raw_html_home else 'no'}")
    log_both(f"   - {page_idx - 1} File di testo pronti per l'LLM")

    # 4. Fase AI Website Audit
    log_both("🧠 FASE 2: Simulazione Audit AI tramite LLM...")
    auditor = LeadAuditor()

    # Prepara payload fittizio per l'auditor
    domain = extract_domain(url)
    business_name = domain.split(".")[0].title()
    category = "Testing & Diagnostics"
    
    log_both(f"   Chiamata LLM per: '{business_name}' ({category})")
    
    try:
        audit_res = auditor.audit_website(
            crawl_pages=crawl_res.pages,
            business_name=business_name,
            category=category,
            rating=4.5,
            review_count=10,
        )

        log_both("\n🤖 RISPOSTA AI AUDIT:")
        log_both("=" * 60)
        log_both(f"📊 website_score: {audit_res.get('website_score')}/10")
        log_both(f"🛠️ framework: {audit_res.get('framework')}")
        log_both(f"🔬 diagnosis: {audit_res.get('diagnosis')}")
        log_both(f"📝 site_brief: {audit_res.get('site_brief')}")
        log_both(f"💬 cold_message (hook): {audit_res.get('cold_message')}")
        log_both("=" * 60)

        # Salva il prompt compilato reale comprensivo di impaginazione e pulizia LLM
        full_prompt = audit_res.get("full_prompt", "")
        prompt_path = os.path.join(output_dir, "ai_prompt_sent.txt")
        with open(prompt_path, "w", encoding="utf-8") as f:
            f.write(full_prompt)
        log_both(f"💾 Prompt completo reale inviato a LLM (con XML e pulizia) salvato in: {prompt_path}")

        # Salva la risposta grezza dell'AI
        raw_resp = audit_res.get("raw_response", "")
        raw_path = os.path.join(output_dir, "ai_raw_response.txt")
        with open(raw_path, "w", encoding="utf-8") as f:
            f.write(raw_resp)
        log_both(f"💾 Risposta AI grezza salvata in: {raw_path}")

        # Salva i testi puliti dall'LLM gratuito per diagnostica
        cleaned_pages = audit_res.get("cleaned_pages", {})
        c_idx = 1
        for page_url, clean_text in cleaned_pages.items():
            parsed_page = urlparse(page_url)
            page_name = parsed_page.path.strip("/").replace("/", "_") or "homepage"
            cleaned_txt_path = os.path.join(proc_dir, f"page_{c_idx}_{page_name}_cleaned.txt")
            with open(cleaned_txt_path, "w", encoding="utf-8") as f:
                f.write(clean_text)
            log_both(f"   💾 Testo pulito da LLM salvato in: {cleaned_txt_path}")
            c_idx += 1

        # Salva l'audit in JSON (escludendo i campi di debug interni)
        audit_export = {
            "website_score": audit_res.get("website_score"),
            "diagnosis": audit_res.get("diagnosis"),
            "site_brief": audit_res.get("site_brief"),
            "framework": audit_res.get("framework"),
            "cold_message": audit_res.get("cold_message"),
        }
        json_path = os.path.join(output_dir, "ai_audit_test.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(audit_export, f, indent=4, ensure_ascii=False)
        log_both(f"\n💾 Risposta AI salvata in: {json_path}")

    except Exception as e:
        log_both(f"❌ Errore durante l'Audit AI: {e}")

    # Salva il report di log completo in test_output/test_report.txt
    report_path = os.path.join(output_dir, "test_report.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))
    print(f"\n📜 Report completo di diagnostica salvato in: {os.path.abspath(report_path)}")
    print("=" * 60)
