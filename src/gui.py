import streamlit as st
import folium
from streamlit_folium import st_folium
import math
import pandas as pd
import os
import sys
from datetime import datetime

# Aggiunge la root del progetto al path per permettere l'import di main.py
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config import GRID_SIZE, GRID_STEP_KM, RADIUS_M, LAT_DEGREE_KM
from main import LeadHunterOrchestrator
from exporter import DataExporter

# Setup pagina
st.set_page_config(
    page_title="Lead Hunter V3 | Enterprise AI Agent",
    layout="wide",
    page_icon="🎯"
)

# --- CUSTOM CSS PREMIUM ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    .main {
        background-color: #fcfcfd;
    }
    
    .stButton>button {
        border-radius: 10px;
        font-weight: 600;
        transition: all 0.3s;
        text-transform: uppercase;
        letter-spacing: 0.02em;
    }
    
    .keyword-card {
        background-color: white;
        padding: 24px;
        border-radius: 20px;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.05);
        border: 1px solid #f1f5f9;
        text-align: center;
        margin-bottom: 15px;
        transition: all 0.3s ease;
    }
    
    .keyword-card:hover {
        box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
        transform: translateY(-2px);
    }
    
    .card-title {
        color: #64748b;
        font-size: 0.8rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin-bottom: 12px;
    }
    
    .card-value {
        font-size: 2.8rem;
        font-weight: 800;
        line-height: 1;
        margin: 15px 0;
        color: #1e293b;
    }
    
    .card-footer {
        color: #94a3b8;
        font-size: 0.85rem;
        font-weight: 500;
    }
    
    .status-idle { border-top: 6px solid #e2e8f0; }
    .status-running { border-top: 6px solid #3b82f6; animation: pulse 2s infinite; }
    .status-success { border-top: 6px solid #10b981; background-color: #f0fdf4; }
    .status-fail { border-top: 6px solid #ef4444; background-color: #fef2f2; }
    
    @keyframes pulse {
        0% { opacity: 1; }
        50% { opacity: 0.7; }
        100% { opacity: 1; }
    }
    
    .log-container {
        background-color: #0f172a;
        color: #38bdf8;
        padding: 20px;
        border-radius: 14px;
        font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
        font-size: 0.9rem;
        border: 1px solid #1e293b;
        height: 250px;
        overflow-y: auto;
        line-height: 1.5;
    }

    /* Stile per scrollbar log */
    .log-container::-webkit-scrollbar {
        width: 8px;
    }
    .log-container::-webkit-scrollbar-track {
        background: #1e293b;
        border-radius: 10px;
    }
    .log-container::-webkit-scrollbar-thumb {
        background: #334155;
        border-radius: 10px;
    }
    </style>
""", unsafe_allow_html=True)

# Helper per renderizzare le card
def render_kw_card(placeholder, keyword, count, status, footer):
    status_map = {
        "idle": "status-idle",
        "running": "status-running",
        "done": "status-success",
        "fail": "status-fail"
    }
    
    # Determinazione stato finale
    if status == "done" and count == 0:
        status = "fail"
    
    color_class = status_map.get(status, "status-idle")
    val_display = str(count)
    icon = "⏳"
    
    if status == "done":
        icon = "✅"
    elif status == "fail":
        icon = "❌"
    elif status == "running":
        icon = "🛰️"
        
    placeholder.markdown(f"""
        <div class="keyword-card {color_class}">
            <div class="card-title">{keyword}</div>
            <div class="card-value">{val_display}</div>
            <div class="card-footer">{icon} {footer}</div>
        </div>
    """, unsafe_allow_html=True)

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
            circles.append((round(center_lat + (i * lat_step), 6), round(center_lng + (j * lng_step), 6)))
    return circles

# --- HEADER ---
st.markdown("<h1 style='text-align: center; color: #1e293b; margin-bottom: 0;'>🎯 Lead Hunter V3</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #64748b; font-size: 1.2rem;'>Enterprise AI Agent for B2B Lead Generation</p>", unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)

# --- LAYOUT PRINCIPALE ---
col1, col2 = st.columns([1, 2.2], gap="large") # Leggermente allargata la colonna mappa

with col1:
    st.markdown("### ⚙️ Configurazione")
    available_tags = ["ristorante", "pizzeria", "bar", "gelateria", "dentista", "avvocato", "idraulico", "elettricista", "estetista", "palestra"]
    keywords = st.multiselect("🏷️ Keyword di ricerca", options=available_tags, default=["ristorante"])
    custom_kw = st.text_input("➕ Aggiungi keyword personalizzata:")
    if custom_kw and custom_kw not in keywords:
        keywords.append(custom_kw)

    # --- NUOVA VISUALIZZAZIONE "POSIZIONE TARGET" ---
    st.markdown("<hr style='margin: 20px 0; border: none; border-top: 1px solid #334155;'>", unsafe_allow_html=True)
    st.markdown("#### 📍 Centro Scansione")
    
    # Utilizzo di st.metric per un design nativo, elegante e compatibile con il Dark Mode
    coord_col1, coord_col2 = st.columns(2)
    coord_col1.metric("Latitudine", f"{st.session_state.target_coords['lat']:.5f}")
    coord_col2.metric("Longitudine", f"{st.session_state.target_coords['lng']:.5f}")
    
    st.caption("💡 Clicca su un punto qualsiasi della mappa per aggiornare le coordinate.")
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Bottone adattato alla larghezza
    start_btn = st.button("🚀 AVVIA LEAD HUNTER ENGINE", type="primary", use_container_width=True)

with col2:
    # Rimosso 'tiles' per ripristinare la bellissima mappa a colori di default (OpenStreetMap)
    m = folium.Map(
        location=[st.session_state.target_coords["lat"], st.session_state.target_coords["lng"]], 
        zoom_start=13, 
        control_scale=True
    )
    
    grid_points = calculate_grid_circles(st.session_state.target_coords["lat"], st.session_state.target_coords["lng"])
    
    for pt in grid_points:
        folium.Circle(
            location=pt, 
            radius=RADIUS_M, 
            color="#3b82f6", 
            weight=1.5, # Bordo leggermente più marcato
            fill_opacity=0.15, # Colore interno più visibile
            fill=True,
            tooltip="Area di scansione API"
        ).add_to(m)
    
    # Marker rosso per il centro, così risalta nettamente sulle aree blu
    folium.Marker(
        [st.session_state.target_coords["lat"], st.session_state.target_coords["lng"]], 
        icon=folium.Icon(color="red", icon="crosshairs", prefix="fa")
    ).add_to(m)
    
    # Altezza aumentata a 600px e use_container_width per eliminare l'effetto "rettangolo stretto"
    map_data = st_folium(
        m, 
        height=600, 
        use_container_width=True, 
        returned_objects=["last_clicked"]
    )
    
    # Cattura click mappa
    if map_data and map_data.get("last_clicked"):
        st.session_state.target_coords = map_data["last_clicked"]
        st.rerun()

# --- MONITORAGGIO E RISULTATI ---
if start_btn:
    if not keywords:
        st.error("⚠️ Seleziona almeno una keyword per procedere.")
    else:
        st.markdown("---")
        st.markdown("### 📊 Monitoraggio Pipeline")
        
        # Grid di card per le keyword (massimo 4 per riga)
        kw_placeholders = {}
        rows = math.ceil(len(keywords) / 4)
        for r in range(rows):
            row_keywords = keywords[r*4 : (r+1)*4]
            kw_cols = st.columns(len(row_keywords))
            for idx, kw in enumerate(row_keywords):
                kw_placeholders[kw] = kw_cols[idx].empty()
                render_kw_card(kw_placeholders[kw], kw, 0, "idle", "In coda")

        st.markdown("#### 📜 System Logs")
        log_container = st.empty()
        
        def update_log(msg):
            if "logs" not in st.session_state: st.session_state.logs = []
            st.session_state.logs.append(f"&gt; {msg}")
            log_container.markdown(f'<div class="log-container">{"<br>".join(st.session_state.logs[::-1])}</div>', unsafe_allow_html=True)

        st.session_state.logs = []
        update_log("🚀 Inizializzazione Engine V3...")
        
        orchestrator = LeadHunterOrchestrator()
        
        # Callbacks per aggiornamento UI real-time
        def on_kw_start(kw):
            update_log(f"🔍 Avvio scansione grid per: <b>{kw}</b>")
            render_kw_card(kw_placeholders[kw], kw, 0, "running", "Ricerca in corso...")

        def on_kw_progress(kw, current, total):
            if kw == "AI_AUDIT":
                update_log(f"🧠 <b>FASE 2:</b> Avvio AI Auditing Parallelo per {total} lead...")
                return
            render_kw_card(kw_placeholders[kw], kw, 0, "running", f"Zona {current}/{total}")

        def on_kw_end(kw, count):
            status_text = "Completato" if count > 0 else "Nessun lead"
            update_log(f"✅ Completato: {kw} -> <b>{count}</b> lead trovati.")
            render_kw_card(kw_placeholders[kw], kw, count, "done", status_text)

        try:
            with st.spinner("Pipeline AI in esecuzione..."):
                results = orchestrator.run(
                    st.session_state.target_coords["lat"], 
                    st.session_state.target_coords["lng"], 
                    keywords,
                    on_kw_start=on_kw_start,
                    on_kw_progress=on_kw_progress,
                    on_kw_end=on_kw_end
                )
            
            if results:
                st.balloons()
                st.success(f"🎊 Pipeline completata con successo! Generati {len(results)} lead ad alto potenziale.")
                
                # Export dinamico basato sulla città e data
                city = orchestrator.scraper.get_city_name(st.session_state.target_coords["lat"], st.session_state.target_coords["lng"])
                date_str = datetime.now().strftime("%d_%m_%Y")
                filename = f"Lead_Hunter_{city}_{date_str}.xlsx"
                DataExporter.export_to_excel(results, filename=filename)
                
                # Visualizzazione risultati Premium
                st.markdown("### 💎 Database Lead Premium")
                df = pd.DataFrame(results)
                # Selezione colonne rilevanti per la visualizzazione pulita
                display_df = df.copy()
                st.dataframe(display_df, width="stretch")
                
                with open(filename, "rb") as f:
                    st.download_button(
                        label=f"📥 SCARICA REPORT: {filename}",
                        data=f,
                        file_name=filename,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        width="stretch"
                    )
            else:
                st.warning("⚠️ La ricerca è terminata ma non sono stati trovati nuovi lead idonei in quest'area.")

        except Exception as e:
            st.error(f"❌ Errore durante l'esecuzione: {e}")
            update_log(f"CRITICAL ERROR: {str(e)}")