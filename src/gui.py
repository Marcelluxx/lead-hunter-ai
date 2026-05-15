import streamlit as st
import folium
from streamlit_folium import st_folium
import math
import pandas as pd
import os
import sys

# Aggiunge la root del progetto al path per permettere l'import di main.py
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config import GRID_SIZE, GRID_STEP_KM, RADIUS_M, LAT_DEGREE_KM
from main import LeadHunterOrchestrator
from exporter import DataExporter

# Setup pagina
st.set_page_config(page_title="Lead Hunter V3 UI", layout="wide")
st.title("🎯 Lead Hunter V3 - Enterprise Agent")

# Inizializza stato sessione
if "target_coords" not in st.session_state:
    st.session_state.target_coords = {"lat": 41.9028, "lng": 12.4964} # Roma Default

def calculate_grid_circles(center_lat, center_lng):
    """Calcola le coordinate dei cerchi della griglia per disegnarli sulla mappa"""
    circles = []
    lat_step = GRID_STEP_KM / LAT_DEGREE_KM
    lng_step = GRID_STEP_KM / (LAT_DEGREE_KM * math.cos(math.radians(center_lat)))
    offset = GRID_SIZE // 2

    for i in range(-offset, offset + 1):
        for j in range(-offset, offset + 1):
            circles.append((
                round(center_lat + (i * lat_step), 6),
                round(center_lng + (j * lng_step), 6)
            ))
    return circles

# --- LAYOUT A COLONNE ---
col1, col2 = st.columns([1, 2])

with col1:
    st.markdown("### ⚙️ Parametri di Ricerca")
    
    # 1. Menu a TAG nativo di Streamlit
    available_tags = ["ristorante", "pizzeria", "bar", "gelateria", "dentista", "avvocato", "idraulico", "elettricista", "estetista", "palestra"]
    keywords = st.multiselect("🏷️ Inserisci Tag / Keyword", options=available_tags, default=["ristorante"])
    
    # Possibilità di aggiungere tag personalizzati digitando
    custom_kw = st.text_input("Aggiungi tag personalizzato (opzionale):")
    if custom_kw and custom_kw not in keywords:
        keywords.append(custom_kw)

    st.markdown(f"**Coordinate Selezionate:** \nLat: `{st.session_state.target_coords['lat']}` \nLng: `{st.session_state.target_coords['lng']}`")
    st.info("💡 Clicca su un punto qualsiasi della mappa per aggiornare le coordinate e spostare la griglia di ricerca.")

    start_btn = st.button("🚀 Avvia Ricerca", type="primary", use_container_width=True)

with col2:
    # --- MAPPA INTERATTIVA ---
    # Creazione della base Folium
    m = folium.Map(
        location=[st.session_state.target_coords["lat"], st.session_state.target_coords["lng"]], 
        zoom_start=12
    )

    # Disegna la "Griglia Grigia" (Grey Grids) per visualizzare l'area esatta di ricerca API
    grid_points = calculate_grid_circles(st.session_state.target_coords["lat"], st.session_state.target_coords["lng"])
    
    for pt in grid_points:
        folium.Circle(
            location=pt,
            radius=RADIUS_M, # Il raggio in metri reale inviato all'API di Google
            color="gray",
            weight=1,
            fill_opacity=0.2,
            fill=True,
            tooltip=f"Zona Scansione: {pt[0]}, {pt[1]}"
        ).add_to(m)
    
    # Posiziona il marker centrale
    folium.Marker(
        [st.session_state.target_coords["lat"], st.session_state.target_coords["lng"]],
        icon=folium.Icon(color="red", icon="crosshairs", prefix="fa")
    ).add_to(m)

    # Renderizza Mappa e cattura i click
    map_data = st_folium(m, height=500, width=800, returned_objects=["last_clicked"])

    # Se l'utente clicca la mappa, aggiorna lo stato e ricarica
    if map_data and map_data.get("last_clicked"):
        st.session_state.target_coords = map_data["last_clicked"]
        st.rerun()

# --- ESECUZIONE DELLA PIPELINE ---
if start_btn:
    if not keywords:
        st.error("Inserisci almeno un Tag/Keyword per iniziare.")
    else:
        st.markdown("---")
        st.markdown("### 🔄 Scansione in corso...")
        
        # ProgressBar e Spinner per UI
        progress_bar = st.progress(0)
        
        with st.spinner("Scraping da Google e Generazione AI (potrebbe volerci qualche minuto)..."):
            orchestrator = LeadHunterOrchestrator()
            
            try:
                # Esegue la ricerca tramite la logica disaccoppiata nel main.py
                results = orchestrator.run(
                    st.session_state.target_coords["lat"], 
                    st.session_state.target_coords["lng"], 
                    keywords
                )
                
                if results:
                    st.success(f"🎉 Trovati {len(results)} Leads ad alto potenziale!")
                    
                    # Salva su file locale per sicurezza
                    DataExporter.export_to_excel(results, filename="gui_export.xlsx")
                    
                    # Prepara il dataframe per la visualizzazione Web
                    df = pd.DataFrame(results)
                    cols_to_show = ["displayName.text", "search_keyword", "formattedAddress", "sales_hook", "ideal_product"]
                    # Mostra tabella pulita
                    st.dataframe(df, use_container_width=True)
                    
                    # Bottone per scaricare il file Excel
                    with open("gui_export.xlsx", "rb") as file:
                        st.download_button(
                            label="📥 Scarica Excel Formattato",
                            data=file,
                            file_name="Leads_Premium.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                else:
                    st.warning("Nessun business trovato senza sito web in quest'area. Prova ad allargare la zona o cambiare tag.")

            except Exception as e:
                st.error(f"Errore durante l'elaborazione: {e}")