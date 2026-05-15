import pandas as pd
from typing import Union, List, Dict

class DataExporter:
    @staticmethod
    def export_to_excel(leads: Union[List[Dict], Dict[str, Dict]], filename: str = "leads_v3_premium.xlsx") -> None:
        """
        Formatta i dati, pulisce i metadati grezzi e li esporta 
        in un file Excel auto-dimensionato e professionale.
        """
        if not leads:
            print("[Exporter] Nessun lead da esportare.")
            return

        # Rendi il metodo flessibile: accetta sia la Lista grezza che il Dizionario deduplicato
        leads_list = list(leads.values()) if isinstance(leads, dict) else leads

        formatted_data = []
        for lead in leads_list:
            # Pulisce i tipi di Google (es. "beauty_salon" -> "Beauty Salon")
            raw_types = lead.get("types", [])[:2]
            clean_category = ", ".join([t.replace("_", " ").title() for t in raw_types])
            
            # Recupera la keyword di ricerca che avevamo iniettato nell'orchestratore
            search_kw = lead.get("search_keyword", "").title()

            formatted_data.append({
                "Business Name": lead.get("displayName", {}).get("text", "N/A"),
                # Usa la categoria di Google, se vuota usa la tua keyword, altrimenti N/A
                "Category": clean_category or search_kw or "N/A",
                "Address": lead.get("formattedAddress", "N/A"),
                "Phone": lead.get("nationalPhoneNumber", "N/A"),
                "Rating": lead.get("rating", "N/A"),
                "Top Local Competitor": lead.get("competitor", "N/A"),
                "Ideal Digital Product": lead.get("ideal_product", "N/A"),
                "AI Sales Hook": lead.get("sales_hook", "N/A")
            })

        df = pd.DataFrame(formatted_data)
        
        try:
            # Usa ExcelWriter con motore 'openpyxl' per manipolare la formattazione
            with pd.ExcelWriter(filename, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Leads')
                
                # Accedi al foglio di lavoro attivo
                worksheet = writer.sheets['Leads']
                
                # Auto-Fit intelligente delle colonne
                for idx, col in enumerate(df.columns):
                    # Trova la lunghezza massima tra l'intestazione e i valori della colonna
                    max_len = max(
                        df[col].astype(str).map(len).max(),
                        len(str(col))
                    )
                    # Imposta un limite massimo alla larghezza per non avere colonne infinite
                    adjusted_width = min(max_len + 2, 60)
                    
                    # OpenPyXL usa indici basati su lettere (A, B, C...) - Questa è la logica
                    from openpyxl.utils import get_column_letter
                    col_letter = get_column_letter(idx + 1)
                    
                    worksheet.column_dimensions[col_letter].width = adjusted_width

            print(f"\n✅ [OK] Esportazione premium completata: {len(leads_list)} lead in '{filename}'")
            
        except PermissionError:
            print(f"❌ [Errore] Il file '{filename}' è aperto in un altro programma. Chiudilo e riprova.")
        except Exception as e:
            print(f"❌ [Errore] Eccezione generica durante l'esportazione: {e}")
