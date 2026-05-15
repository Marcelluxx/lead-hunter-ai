import json
import re
import time
import random
from typing import Dict, List, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from openai import OpenAI
import openai

# Importazione relativa all'interno del package
from .config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, LLM_MODEL

class LeadAuditor:
    def __init__(self):
        # Inizializza il client una sola volta
        self.client = OpenAI(
            base_url=OPENROUTER_BASE_URL,
            api_key=OPENROUTER_API_KEY,
        )

    def _clean_json_output(self, raw_content: str) -> str:
        """Rimuove eventuali wrapper markdown dal testo generato dall'LLM."""
        cleaned = re.sub(r"```json", "", raw_content, flags=re.IGNORECASE)
        cleaned = re.sub(r"```", "", cleaned)
        return cleaned.strip()

    def audit_lead(self, lead: Dict, category: str, competitor: str, max_retries: int = 3) -> Dict[str, str]:
        """
        Analizza un singolo lead con logica di Retry ed Exponential Backoff.
        Utilizza un Prompt avanzato per Copywriting a Risposta Diretta e Temperatura=1.
        """
        business_name = lead.get("displayName", {}).get("text", "Azienda Locale")
        
        reviews = lead.get("reviews", [])
        extracted_reviews = [
            r.get("text", {}).get("text", "") 
            for r in reviews[:3] if r.get("text", {}).get("text")
        ]
        
        if extracted_reviews:
            review_text = "\n".join([f"- {text}" for text in extracted_reviews])
        else:
            review_text = "Nessuna recensione disponibile. Fai leva sul fatto che oggi 'non esistere su Google significa perdere fatturato'."

        # ==========================================
        # PROMPT ENGINEERING AVANZATO (10/10)
        # ==========================================
        prompt = f"""ANALISI LEAD - MISSIONE: GENERARE FOMO E VENDERE SOLUZIONI DIGITALI.
        Il target è un'attività locale attualmente SPROVVISTA di presenza web proprietaria. 
        L'obiettivo è creare un gancio a freddo (cold outreach) talmente potente, creativo e doloroso da costringerli a risponderci.

        🎯 [DATI DEL TARGET]
        - Nome Azienda: {business_name}
        - Settore: {category}
        - Competitor Diretto (che ha già un sito e domina online): {competitor}

        🗣️ [VOCE DEI CLIENTI (Recensioni Google Reali)]
        {review_text}

        ⚙️ [DIRETTIVE DI OUTPUT - RISPONDI SOLO IN JSON]
        Il tuo output deve contenere ESATTAMENTE queste due chiavi. Nessun commento extra.

        1. "sales_hook": (Stringa, massimo 25 parole). 
        - STILE: Aggressivo, diretto, non convenzionale. Nessuna formula di cortesia.
        - LEVA PSICOLOGICA: Sfrutta brutalmente la FOMO. Fai pesare il fatto che "{competitor}" sta fagocitando i loro clienti e i loro incassi grazie al sito web. 
        - PAIN POINT: Se le recensioni rivelano un problema (es. clienti che non trovano il menu, code, impossibilità di prenotare), usalo come coltello nella piaga.

        2. "ideal_product": (Stringa, massimo 6 parole).
        - Crea il nome di una soluzione "Premium" cucita su misura per il settore {category}.
        - DIVIETO ASSOLUTO: Non usare il banale termine "Sito web". 
        - USA TERMINI COME: "Ecosistema Digitale", "Infrastruttura di Prenotazione", "Funnel Genera-Clienti", "Menu Digitale Interattivo".

        Esempio di JSON perfetto:
        {{
            "sales_hook": "I tuoi clienti impazziscono per prenotare al telefono. Intanto, {competitor} gli ruba il tavolo con le prenotazioni online. Chiudiamo questa falla oggi.",
            "ideal_product": "Ecosistema di Prenotazione Automatica 24/7"
        }}
        """
        # ==========================================
        # RETRY LOOP: EXPONENTIAL BACKOFF
        # ==========================================
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=LLM_MODEL,
                    messages=[
                        # System prompt rafforzato per contenere la Temperatura 1
                        {"role": "system", "content": "Sei un copywriter B2B d'élite. La tua scrittura è tagliente e orientata alla conversione. Restituisci SOLO un oggetto JSON valido."},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=1.0  # <--- CREATIVITÀ MASSIMA
                )
                
                raw_content = response.choices[0].message.content
                clean_content = self._clean_json_output(raw_content)
                ai_data = json.loads(clean_content)
                
                # Pulizia finale in caso la creatività rompa il limite delle parole
                hook = ai_data.get("sales_hook", "")
                prod = ai_data.get("ideal_product", f"Infrastruttura Web Premium ({category})")
                
                return {
                    "ideal_product": prod,
                    "sales_hook": hook if hook else f"Mentre tu non hai un sito, {competitor} ti sta rubando traffico online. Interveniamo."
                }

            except openai.RateLimitError as rle:
                # Exponential backoff più aggressivo (base 3) e jitter maggiore per evitare collisioni
                wait_time = (3 ** attempt) + random.uniform(1, 3)
                if attempt < max_retries - 1:
                    print(f"      ⏳ Rate Limit per '{business_name}'. Attendo {wait_time:.1f}s e riprovo...")
                    time.sleep(wait_time)
                else:
                    print(f"      ❌ Fallito '{business_name}' per continui Rate Limit.")
            
            except json.JSONDecodeError as je:
                print(f"      ⚠️ L'LLM (Temp 1.0) ha generato un JSON malformato per {business_name}: {je}")
                # Poiché Temp 1 aumenta il rischio di allucinazioni di sintassi, il fallback è vitale.
                if attempt == max_retries - 1:
                    break
                
            except Exception as e:
                print(f"      ❌ Errore API per {business_name}: {e}")
                break
                
        # FALLBACK SICURO
        return {
            "ideal_product": f"Ecosistema Digitale per {category}",
            "sales_hook": f"Non lasciare che {competitor} continui a rubarti clienti. Domina il tuo mercato locale oggi."
        }

    def audit_leads_batch(self, leads_payloads: List[Dict[str, Any]], max_workers: int = 5) -> Dict[str, Dict[str, str]]:
        """
        [NOVITÀ] Elabora una lista di lead in parallelo massimizzando la velocità.
        Usa ThreadPoolExecutor per gestire le chiamate concorrenti.
        """
        results = {}
        total_leads = len(leads_payloads)
        
        print(f"   🚀 Avvio AI Auditing Parallelo per {total_leads} leads (Max Workers: {max_workers})...")

        def worker(payload: Dict) -> tuple:
            # Pacing più stringente: spread iniziale per evitare burst di massa su OpenRouter
            time.sleep(random.uniform(0.5, 2.0))
            
            res = self.audit_lead(
                lead=payload["place_data"], 
                category=payload["keyword"], 
                competitor=payload["competitor"]
            )
            return payload["id"], res

        # Avvia il Pool di Thread
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Mappiamo i future ai payload originali
            futures = {executor.submit(worker, p): p for p in leads_payloads}
            
            completed = 0
            for future in as_completed(futures):
                p_id, audit_res = future.result()
                results[p_id] = audit_res
                
                completed += 1
                # Indicatore di progresso in-place per pulizia CLI
                print(f"      ✅ [{completed}/{total_leads}] Analisi in corso...", end="\r", flush=True)

        print(f"\n      ✨ Analisi di {total_leads} lead completata con successo.")

        return results