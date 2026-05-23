"""
Lead Hunter V3 — AI Auditor Module
Due modalità:
  1. "No Website" — analisi lead senza sito (rimossi ideal_product e sales_hook)
  2. "With Website" — audit completo sito web con LLM via OpenRouter

I prompt di sistema sono centralizzati in src/prompts.py (escluso dal repo pubblico).
"""

import json
import re
import time
import random
import logging
from typing import Dict, List, Any
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

from openai import OpenAI
import openai

from .config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, LLM_MODEL
from .prompts import (
    SYSTEM_NO_WEBSITE,
    SYSTEM_WEBSITE_AUDIT,
    build_no_website_prompt,
    build_website_audit_prompt,
)

logger = logging.getLogger(__name__)


class LeadAuditor:
    def __init__(self):
        self.client = OpenAI(
            base_url=OPENROUTER_BASE_URL,
            api_key=OPENROUTER_API_KEY,
        )

    def _clean_json_output(self, raw_content: str) -> str:
        """Estrae e ripulisce il JSON dal testo generato dall'LLM."""
        match = re.search(r'\{.*\}', raw_content, re.DOTALL)
        if match:
            return match.group(0)
        return raw_content.strip()

    # ==========================================
    # MODALITÀ 1: LEAD SENZA SITO WEB
    # ==========================================
    def audit_lead_no_website(self, lead: Dict, category: str, competitor: str, max_retries: int = 3) -> Dict[str, str]:
        """
        Analisi base per lead senza sito web.
        Output: solo info contestuali utili per il commerciale.
        """
        business_name = lead.get("displayName", {}).get("text", "Azienda Locale")
        reviews = lead.get("reviews", [])
        extracted_reviews = [
            r.get("text", {}).get("text", "")
            for r in reviews[:3] if r.get("text", {}).get("text")
        ]

        review_text = "\n".join([f"- {t}" for t in extracted_reviews]) if extracted_reviews else "Nessuna recensione."

        prompt = build_no_website_prompt(business_name, category, competitor, review_text)

        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=LLM_MODEL,
                    messages=[
                        {"role": "system", "content": SYSTEM_NO_WEBSITE},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7
                )
                raw = response.choices[0].message.content
                data = json.loads(self._clean_json_output(raw))
                return {
                    "business_summary": data.get("business_summary", ""),
                    "key_weakness": data.get("key_weakness", ""),
                }
            except openai.RateLimitError:
                wait = (3 ** attempt) + random.uniform(1, 3)
                if attempt < max_retries - 1:
                    logger.warning(f"Rate limit per '{business_name}', attendo {wait:.1f}s...")
                    time.sleep(wait)
            except json.JSONDecodeError as e:
                logger.warning(f"JSON malformato per {business_name}: {e}")
                if attempt == max_retries - 1:
                    break
            except Exception as e:
                logger.error(f"Errore API per {business_name}: {e}")
                break

        return {
            "business_summary": f"Attività locale nel settore {category}.",
            "key_weakness": "Assenza di presenza web proprietaria.",
        }

    # ==========================================
    # MODALITÀ 2: AUDIT SITO WEB COMPLETO
    # ==========================================
    def audit_website(
        self,
        crawl_pages: Dict[str, str],
        business_name: str,
        category: str,
        rating: float,
        review_count: int,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Audit completo del sito web tramite LLM.
        Output: website_score, diagnosis, site_brief, cold_message.
        """
        # Componi il contenuto delle pagine crawlate
        pages_content = ""
        for page_url, content in crawl_pages.items():
            label = self._label_page(page_url)
            truncated = content[:4000] if len(content) > 4000 else content
            pages_content += f"\n\n--- PAGINA: {label} ({page_url}) ---\n{truncated}"

        prompt = build_website_audit_prompt(
            business_name, category, rating, review_count, pages_content
        )

        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=LLM_MODEL,
                    messages=[
                        {"role": "system", "content": SYSTEM_WEBSITE_AUDIT},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7
                )

                raw = response.choices[0].message.content
                data = json.loads(self._clean_json_output(raw))

                score = data.get("website_score", 5)
                if isinstance(score, str):
                    score = int(re.search(r'\d+', score).group()) if re.search(r'\d+', score) else 5
                score = max(1, min(10, int(score)))

                return {
                    "website_score": score,
                    "diagnosis": data.get("diagnosis", "Analisi non disponibile."),
                    "site_brief": data.get("site_brief", ""),
                    "cold_message": data.get("cold_message", ""),
                }

            except openai.RateLimitError:
                wait = (3 ** attempt) + random.uniform(1, 3)
                if attempt < max_retries - 1:
                    logger.warning(f"Rate limit audit sito '{business_name}', attendo {wait:.1f}s...")
                    time.sleep(wait)
            except json.JSONDecodeError as e:
                logger.warning(f"JSON malformato audit sito {business_name}: {e}")
                if attempt == max_retries - 1:
                    break
            except Exception as e:
                logger.error(f"Errore audit sito {business_name}: {e}")
                break

        return {
            "website_score": 0,
            "diagnosis": "Errore durante l'analisi AI del sito web.",
            "site_brief": "",
            "cold_message": "",
        }

    def _label_page(self, url: str) -> str:
        """Assegna un'etichetta leggibile a un URL (es. 'Homepage', 'Contatti')."""
        path = urlparse(url).path.lower().rstrip("/")
        if not path or path == "/":
            return "Homepage"
        labels = {
            "contatt": "Contatti", "contact": "Contatti",
            "chi-siamo": "Chi Siamo", "about": "Chi Siamo",
            "servi": "Servizi", "service": "Servizi",
            "privacy": "Privacy Policy", "cookie": "Cookie Policy",
            "legal": "Note Legali", "team": "Team",
        }
        for key, label in labels.items():
            if key in path:
                return label
        return path.split("/")[-1].replace("-", " ").title()

    # ==========================================
    # BATCH PROCESSING (comune a entrambe le modalità)
    # ==========================================
    def audit_leads_batch(
        self,
        leads_payloads: List[Dict[str, Any]],
        max_workers: int = 5
    ) -> Dict[str, Dict[str, str]]:
        """Elabora lead senza sito in parallelo (modalità No Website)."""
        results = {}
        total = len(leads_payloads)
        logger.info(f"Avvio AI Auditing Parallelo per {total} leads (Workers: {max_workers})")

        def worker(payload: Dict) -> tuple:
            time.sleep(random.uniform(0.5, 2.0))
            res = self.audit_lead_no_website(
                lead=payload["place_data"],
                category=payload["keyword"],
                competitor=payload["competitor"]
            )
            return payload["id"], res

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(worker, p): p for p in leads_payloads}
            completed = 0
            for future in as_completed(futures):
                p_id, audit_res = future.result()
                results[p_id] = audit_res
                completed += 1
                print(f"      [{completed}/{total}] Analisi in corso...", end="\r", flush=True)

        print(f"\n      Analisi di {total} lead completata.")
        return results

    def audit_websites_batch(
        self,
        website_payloads: List[Dict[str, Any]],
        max_workers: int = 3,
        on_progress: Any = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Audit parallelo di siti web (modalità With Website).
        website_payloads: lista di dict con keys: id, crawl_pages, business_name, category, rating, review_count
        """
        results = {}
        total = len(website_payloads)
        logger.info(f"Avvio AI Website Auditing per {total} siti (Workers: {max_workers})")

        def worker(payload: Dict) -> tuple:
            time.sleep(random.uniform(0.5, 1.5))
            res = self.audit_website(
                crawl_pages=payload["crawl_pages"],
                business_name=payload["business_name"],
                category=payload["category"],
                rating=payload.get("rating", 0),
                review_count=payload.get("review_count", 0),
            )
            return payload["id"], res

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(worker, p): p for p in website_payloads}
            completed = 0
            for future in as_completed(futures):
                p_id, audit_res = future.result()
                results[p_id] = audit_res
                completed += 1
                if on_progress:
                    on_progress(completed, total)
                print(f"      [{completed}/{total}] Audit siti in corso...", end="\r", flush=True)

        print(f"\n      Audit di {total} siti completato.")
        return results