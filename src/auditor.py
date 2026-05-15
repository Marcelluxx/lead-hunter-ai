import json
import re
from typing import Dict, Optional
from openai import OpenAI

# Importazione relativa all'interno del package
from .config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, LLM_MODEL

class LeadAuditor:
    def __init__(self):
        # Inizializza il client una sola volta per riutilizzare la sessione HTTP
        self.client = OpenAI(
            base_url=OPENROUTER_BASE_URL,
            api_key=OPENROUTER_API_KEY,
        )

    def _clean_json_output(self, raw_content: str) -> str:
        """
        [Metodo Privato] Rimuove eventuali wrapper markdown dal testo generato dall'LLM.
        Modelli come LLaMA spesso aggiungono ```json ... ``` anche se si richiede solo l'oggetto.
        """
        cleaned = re.sub(r"```json", "", raw_content, flags=re.IGNORECASE)
        cleaned = re.sub(r"```", "", cleaned)
        return cleaned.strip()

    def audit_lead(self, lead: Dict, category: str, competitor: str) -> Dict[str, str]:
        """
        Analizza un lead tramite LLM, sfruttando il contesto della categoria 
        e la presenza di un competitor per generare FOMO.
        """
        business_name = lead.get("displayName", {}).get("text", "Azienda Locale")
        
        # Estrai il testo delle recensioni (max 3), gestendo eventuali valori None
        reviews = lead.get("reviews", [])
        extracted_reviews = [
            r.get("text", {}).get("text", "") 
            for r in reviews[:3] if r.get("text", {}).get("text")
        ]
        
        # Formattazione recensioni per il prompt
        if extracted_reviews:
            review_text = "\n".join([f"- {text}" for text in extracted_reviews])
        else:
            review_text = "Nessuna recensione testuale disponibile. Punta sull'assenza di presenza digitale in generale."

        # Prompt super-ottimizzato per LLaMA 3
        prompt = f"""Sei un esperto Senior di Vendite B2B. 
Analizza questa attività locale che attualmente NON possiede un sito web.

Dati Aziendali:
- Nome: {business_name}
- Settore/Categoria: {category}
- Competitor Top (con sito web): {competitor}

Recensioni Recenti:
{review_text}

REGOLE DI OUTPUT STRICAMENTE IN JSON:
1. `sales_hook`: Crea una frase di aggancio commerciale aggressiva (max 20 parole). DEVI menzionare che "{competitor}" sta rubando i loro clienti online per creare FOMO (Fear Of Missing Out), e usa un "pain point" preso dalle recensioni, se presente.
2. `ideal_product`: Suggerisci il prodotto digitale esatto e specifico per il loro settore ({category}) (es. "Sito Vetrina + Sistema Prenotazioni", "E-Commerce", ecc.).

Esempio Output:
{{
    "sales_hook": "Il tuo competitor {competitor} ti sta rubando traffico! I clienti si lamentano del menu introvabile. Risolviamo il problema subito.",
    "ideal_product": "Sito Web Mobile + Menu Digitale QR"
}}
"""

        try:
            response = self.client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": "Sei un'AI che restituisce ESCLUSIVAMENTE JSON puro. Niente convenevoli."},
                    {"role": "user", "content": prompt}
                ],
                # Manteniamo il formato JSON, ma puliremo comunque l'output
                response_format={"type": "json_object"},
                temperature=0.7 # Una leggera creatività è ideale per il copywriting
            )
            
            raw_content = response.choices[0].message.content
            clean_content = self._clean_json_output(raw_content)
            
            ai_data = json.loads(clean_content)
            
            return {
                "ideal_product": ai_data.get("ideal_product", f"Pacchetto Digitale per {category}"),
                "sales_hook": ai_data.get("sales_hook", f"{competitor} ti sta superando online. Creiamo il tuo sito web oggi.")
            }
            
        except json.JSONDecodeError as je:
            print(f"[Auditor Error] LLM ha restituito un JSON non valido per {business_name}: {je}")
            # Fallback intelligente
            return {
                "ideal_product": f"Sito Web Ottimizzato per {category}",
                "sales_hook": f"Non lasciare che {competitor} continui a rubarti clienti. Porta la tua attività online."
            }
        except Exception as e:
            print(f"[Auditor Error] Errore di rete o API per {business_name}: {e}")
            return {
                "ideal_product": f"Sito Web Professionale ({category})",
                "sales_hook": f"Il mercato richiede presenza online. Blocca il vantaggio di {competitor}."
            }
