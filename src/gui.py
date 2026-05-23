"""
Lead Hunter V3 — Streamlit GUI Premium
Interfaccia grafica con:
  - Selettore modalità (Senza Sito / Con Sito + Audit)
  - Controlli condizionali per filtri e crawler
  - Progress bar, tempo trascorso, log in tempo reale
  - Visualizzazione risultati mode-aware
"""

import streamlit as st
import folium
from streamlit_folium import st_folium
import math
import pandas as pd
import os
import sys
import time
import requests
from datetime import datetime

# Path setup per import dal progetto root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config import (
    GRID_SIZE, GRID_STEP_KM, RADIUS_M, LAT_DEGREE_KM,
    MIN_RATING, MAX_REVIEWS, MIN_BUSINESS_AGE_YEARS, MAX_CRAWL_PAGES,
)
from main import LeadHunterOrchestrator
from exporter import DataExporter

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="Lead Hunter V3 | Enterprise AI Agent",
    layout="wide",
    page_icon="🎯"
)

# --- CUSTOM CSS PREMIUM ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .main { background-color: #fcfcfd; }

    .stButton>button {
        border-radius: 10px; font-weight: 600;
        transition: all 0.3s; text-transform: uppercase; letter-spacing: 0.02em;
    }

    .keyword-card {
        background-color: white; padding: 24px; border-radius: 20px;
        box-shadow: 0 10px 25px -5px rgba(0,0,0,0.05);
        border: 1px solid #f1f5f9; text-align: center;
        margin-bottom: 15px; transition: all 0.3s ease;
    }
    .keyword-card:hover { box-shadow: 0 20px 25px -5px rgba(0,0,0,0.1); transform: translateY(-2px); }
    .card-title { color: #64748b; font-size: 0.8rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 12px; }
    .card-value { font-size: 2.8rem; font-weight: 800; line-height: 1; margin: 15px 0; color: #1e293b; }
    .card-footer { color: #94a3b8; font-size: 0.85rem; font-weight: 500; }

    .status-idle { border-top: 6px solid #e2e8f0; }
    .status-running { border-top: 6px solid #3b82f6; animation: pulse 2s infinite; }
    .status-success { border-top: 6px solid #10b981; background-color: #f0fdf4; }
    .status-fail { border-top: 6px solid #ef4444; background-color: #fef2f2; }

    @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.7; } 100% { opacity: 1; } }

    .log-container {
        background-color: #0f172a; color: #38bdf8; padding: 20px;
        border-radius: 14px; font-family: 'SFMono-Regular', Consolas, monospace;
        font-size: 0.85rem; border: 1px solid #1e293b;
        height: 300px; overflow-y: auto; line-height: 1.5;
    }
    .log-container::-webkit-scrollbar { width: 8px; }
    .log-container::-webkit-scrollbar-track { background: #1e293b; border-radius: 10px; }
    .log-container::-webkit-scrollbar-thumb { background: #334155; border-radius: 10px; }

    .phase-card {
        background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
        color: white; padding: 16px 24px; border-radius: 14px;
        margin-bottom: 10px; display: flex; align-items: center; gap: 12px;
    }
    .phase-icon { font-size: 1.5rem; }
    .phase-text { font-size: 0.95rem; font-weight: 600; }
    .phase-time { font-size: 0.8rem; color: #94a3b8; margin-left: auto; }

    .param-hint {
        font-size: 0.75rem; color: #94a3b8; font-style: italic;
        margin-top: -8px; margin-bottom: 12px;
    }
    </style>
""", unsafe_allow_html=True)


# --- HELPERS ---
def render_kw_card(placeholder, keyword, count, status, footer):
    status_map = {"idle": "status-idle", "running": "status-running", "done": "status-success", "fail": "status-fail"}
    if status == "done" and count == 0:
        status = "fail"
    color_class = status_map.get(status, "status-idle")
    icons = {"done": "✅", "fail": "❌", "running": "🛰️"}
    icon = icons.get(status, "⏳")
    placeholder.markdown(f"""
        <div class="keyword-card {color_class}">
            <div class="card-title">{keyword}</div>
            <div class="card-value">{count}</div>
            <div class="card-footer">{icon} {footer}</div>
        </div>
    """, unsafe_allow_html=True)


def render_phase_card(placeholder, icon, text, elapsed_str=""):
    time_html = f'<span class="phase-time">⏱️ {elapsed_str}</span>' if elapsed_str else ""
    placeholder.markdown(f"""
        <div class="phase-card">
            <span class="phase-icon">{icon}</span>
            <span class="phase-text">{text}</span>
            {time_html}
        </div>
    """, unsafe_allow_html=True)


def format_elapsed(seconds: float) -> str:
    """Formatta secondi in stringa leggibile."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes}m {secs}s"


def calculate_grid_circles(center_lat, center_lng):
    circles = []
    lat_step = GRID_STEP_KM / LAT_DEGREE_KM
    lng_step = GRID_STEP_KM / (LAT_DEGREE_KM * math.cos(math.radians(center_lat)))
    offset = GRID_SIZE // 2
    for i in range(-offset, offset + 1):
        for j in range(-offset, offset + 1):
            circles.append((round(center_lat + (i * lat_step), 6), round(center_lng + (j * lng_step), 6)))
    return circles


# --- SESSION STATE ---
def get_approximate_location():
    """Tenta di ottenere la posizione approssimativa dell'utente tramite IP."""
    try:
        # Timeout breve (3s) per non bloccare la GUI se non c'è rete o l'API è lenta
        response = requests.get("http://ip-api.com/json/", timeout=3)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success":
                return {"lat": data["lat"], "lng": data["lon"]}
    except Exception:
        pass
    
    # Fallback su Roma se fallisce
    return {"lat": 41.9028, "lng": 12.4964}

if "target_coords" not in st.session_state:
    st.session_state.target_coords = get_approximate_location()

# --- HEADER ---
st.markdown("<h1 style='text-align: center; color: #1e293b; margin-bottom: 0;'>🎯 Lead Hunter V3</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #64748b; font-size: 1.2rem;'>Enterprise AI Agent for B2B Lead Generation</p>", unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)

# --- LAYOUT PRINCIPALE ---
col1, col2 = st.columns([1, 2.2], gap="large")

with col1:
    st.markdown("### ⚙️ Configurazione")

    # --- SELETTORE MODALITÀ ---
    mode = st.radio(
        "🔄 Modalità Operativa",
        options=["Senza Sito Web", "Con Sito Web + Audit"],
        index=0,
        help="**Senza Sito**: Trova attività senza sito web.\n\n**Con Sito + Audit**: Trova attività CON sito web, analizzale e genera outreach.",
        horizontal=True
    )
    mode_key = "with_website" if mode == "Con Sito Web + Audit" else "no_website"

    st.markdown("<hr style='margin: 12px 0; border: none; border-top: 1px solid #e2e8f0;'>", unsafe_allow_html=True)

    # --- KEYWORDS ---
    available_tags = ["ristorante", "pizzeria", "bar", "gelateria", "dentista", "avvocato", "idraulico", "elettricista", "estetista", "palestra"]
    keywords = st.multiselect("🏷️ Keyword di ricerca", options=available_tags, default=["ristorante"])
    custom_kw = st.text_input("➕ Aggiungi keyword personalizzata:")
    if custom_kw and custom_kw not in keywords:
        keywords.append(custom_kw)

    # --- PARAMETRI MODALITÀ CON SITO WEB ---
    if mode_key == "with_website":
        st.markdown("<hr style='margin: 12px 0; border: none; border-top: 1px solid #e2e8f0;'>", unsafe_allow_html=True)
        st.markdown("#### 🎯 Filtri Lead")

        wm_col1, wm_col2 = st.columns(2)
        with wm_col1:
            min_rating = st.number_input("⭐ Rating minimo", min_value=1.0, max_value=5.0, value=MIN_RATING, step=0.1)
            st.markdown('<p class="param-hint">Solo attività con rating superiore a questa soglia</p>', unsafe_allow_html=True)
        with wm_col2:
            max_reviews = st.number_input("📝 Max recensioni", min_value=1, max_value=500, value=MAX_REVIEWS, step=10)
            st.markdown('<p class="param-hint">Esclude catene con centinaia di recensioni</p>', unsafe_allow_html=True)

        min_age = st.number_input("📅 Età minima attività (anni)", min_value=1, max_value=30, value=MIN_BUSINESS_AGE_YEARS, step=1)
        st.markdown('<p class="param-hint">Verifica WHOIS e copywriting del sito (se nessun dato: passa)</p>', unsafe_allow_html=True)

        st.markdown("#### 🕷️ Configurazione Crawler")

        max_pages = st.slider(
            "📄 Pagine da crawlare per sito",
            min_value=1, max_value=10, value=MAX_CRAWL_PAGES, step=1
        )
        # Etichette esplicative per numero pagine
        pages_labels = {
            1: "🟡 Solo Homepage — Velocissimo ma analisi limitata",
            2: "🟡 Homepage + 1 pagina interna — Minimo per trovare email",
            3: "🟢 3 pagine — Buon compromesso velocità/profondità",
            4: "🟢 4 pagine — Copre le sezioni principali",
            5: "🟢 5 pagine — ⭐ CONSIGLIATO — Copre Home, Contatti, Chi Siamo, Servizi, Privacy",
            6: "🔵 6 pagine — Analisi approfondita",
            7: "🔵 7 pagine — Molto dettagliato, tempi più lunghi",
            8: "🟠 8+ pagine — Deep scan, consuma più token e tempo",
            9: "🟠 8+ pagine — Deep scan, consuma più token e tempo",
            10: "🔴 10 pagine — Scan completo, tempi significativi"
        }
        st.markdown(f'<p class="param-hint">{pages_labels.get(max_pages, "")}</p>', unsafe_allow_html=True)

        token_mode = st.toggle("🔬 Modalità High-Fidelity (più token, analisi migliore)", value=True)
        token_mode_str = "high_fidelity" if token_mode else "optimized"

        if token_mode:
            st.markdown('<p class="param-hint">Invia struttura HTML semantica + classi CSS al LLM per valutazione design</p>', unsafe_allow_html=True)
        else:
            st.markdown('<p class="param-hint">Converte in Markdown pulito — meno token, analisi solo su contenuti testuali</p>', unsafe_allow_html=True)

    # --- POSIZIONE ---
    st.markdown("<hr style='margin: 12px 0; border: none; border-top: 1px solid #e2e8f0;'>", unsafe_allow_html=True)
    st.markdown("#### 📍 Centro Scansione")
    coord_c1, coord_c2 = st.columns(2)
    coord_c1.metric("Latitudine", f"{st.session_state.target_coords['lat']:.5f}")
    coord_c2.metric("Longitudine", f"{st.session_state.target_coords['lng']:.5f}")
    st.caption("💡 Clicca sulla mappa per aggiornare le coordinate.")
    st.markdown("<br>", unsafe_allow_html=True)

    start_btn = st.button("🚀 AVVIA LEAD HUNTER ENGINE", type="primary", use_container_width=True)

with col2:
    m = folium.Map(
        location=[st.session_state.target_coords["lat"], st.session_state.target_coords["lng"]],
        zoom_start=13, control_scale=True
    )
    grid_points = calculate_grid_circles(st.session_state.target_coords["lat"], st.session_state.target_coords["lng"])
    for pt in grid_points:
        folium.Circle(
            location=pt, radius=RADIUS_M, color="#3b82f6",
            weight=1.5, fill_opacity=0.15, fill=True, tooltip="Area di scansione API"
        ).add_to(m)
    folium.Marker(
        [st.session_state.target_coords["lat"], st.session_state.target_coords["lng"]],
        icon=folium.Icon(color="red", icon="crosshairs", prefix="fa")
    ).add_to(m)
    map_data = st_folium(m, height=600, use_container_width=True, returned_objects=["last_clicked"])
    if map_data and map_data.get("last_clicked"):
        st.session_state.target_coords = map_data["last_clicked"]
        st.rerun()


# ==========================================
# ESECUZIONE PIPELINE
# ==========================================
if start_btn:
    if not keywords:
        st.error("⚠️ Seleziona almeno una keyword per procedere.")
    else:
        st.markdown("---")

        # --- TIMER GLOBALE ---
        pipeline_start = time.time()

        # --- PHASE TRACKER ---
        st.markdown("### 🔄 Pipeline in Esecuzione")
        phase_placeholder = st.empty()
        progress_container = st.container()
        progress_bar = progress_container.progress(0, text="Inizializzazione...")
        elapsed_placeholder = st.empty()

        # --- KEYWORD CARDS (per modalità no_website) ---
        if mode_key == "no_website":
            st.markdown("### 📊 Monitoraggio per Keyword")
            kw_placeholders = {}
            rows = math.ceil(len(keywords) / 4)
            for r in range(rows):
                row_kws = keywords[r*4 : (r+1)*4]
                kw_cols = st.columns(len(row_kws))
                for idx, kw in enumerate(row_kws):
                    kw_placeholders[kw] = kw_cols[idx].empty()
                    render_kw_card(kw_placeholders[kw], kw, 0, "idle", "In coda")

        # --- SYSTEM LOGS ---
        st.markdown("#### 📜 System Logs")
        log_container = st.empty()

        def update_log(msg):
            if "logs" not in st.session_state:
                st.session_state.logs = []
            elapsed = format_elapsed(time.time() - pipeline_start)
            st.session_state.logs.append(f"<span style='color:#64748b'>[{elapsed}]</span> {msg}")
            log_html = "<br>".join(st.session_state.logs[::-1])
            log_container.markdown(f'<div class="log-container">{log_html}</div>', unsafe_allow_html=True)

        def update_elapsed():
            elapsed = format_elapsed(time.time() - pipeline_start)
            elapsed_placeholder.markdown(
                f"<p style='text-align:right; color:#64748b; font-size:0.85rem;'>⏱️ Tempo trascorso: <b>{elapsed}</b></p>",
                unsafe_allow_html=True
            )

        st.session_state.logs = []
        update_log("🚀 Inizializzazione Engine V3...")

        orchestrator = LeadHunterOrchestrator(mode=mode_key)

        try:
            if mode_key == "no_website":
                # === PIPELINE NO WEBSITE ===
                def on_kw_start(kw):
                    update_log(f"🔍 Scansione grid per: <b>{kw}</b>")
                    render_kw_card(kw_placeholders[kw], kw, 0, "running", "Ricerca in corso...")
                    update_elapsed()

                def on_kw_progress(kw, current, total):
                    if kw == "AI_AUDIT":
                        render_phase_card(phase_placeholder, "🧠", f"AI Auditing — {total} lead da analizzare", format_elapsed(time.time() - pipeline_start))
                        progress_bar.progress(0, text=f"AI Auditing: 0/{total}")
                        update_log(f"🧠 <b>FASE 2:</b> AI Auditing per {total} lead...")
                        return
                    pct = current / total if total > 0 else 0
                    progress_bar.progress(pct, text=f"Keyword: {kw} — Zona {current}/{total}")
                    render_kw_card(kw_placeholders[kw], kw, 0, "running", f"Zona {current}/{total}")
                    update_elapsed()

                def on_kw_end(kw, count):
                    update_log(f"✅ {kw} → <b>{count}</b> lead trovati")
                    render_kw_card(kw_placeholders[kw], kw, count, "done", "Completato" if count > 0 else "Nessun lead")
                    update_elapsed()

                render_phase_card(phase_placeholder, "🔍", "FASE 1: Scraping Google Maps", "0s")

                with st.spinner("Pipeline AI in esecuzione..."):
                    results = orchestrator.run(
                        st.session_state.target_coords["lat"],
                        st.session_state.target_coords["lng"],
                        keywords,
                        on_kw_start=on_kw_start,
                        on_kw_progress=on_kw_progress,
                        on_kw_end=on_kw_end
                    )

            else:
                # === PIPELINE WITH WEBSITE ===
                phase_icons = {
                    "scraping": "🔍", "filtering_reviews": "📊",
                    "crawling": "🕷️", "filtering_age": "📅",
                    "filtering_scale": "🏢", "auditing": "🧠",
                }
                phase_names = {
                    "scraping": "FASE 1: Scraping Google Maps",
                    "filtering_reviews": "FASE 2: Filtro Recensioni",
                    "crawling": "FASE 3: Crawling Siti Web",
                    "filtering_age": "FASE 4: Filtro Età Attività",
                    "filtering_scale": "FASE 5: Filtro Scala (no e-commerce/franchise)",
                    "auditing": "FASE 6: AI Website Audit",
                }

                def on_phase(phase_id, desc):
                    icon = phase_icons.get(phase_id, "⚙️")
                    name = phase_names.get(phase_id, desc)
                    elapsed = format_elapsed(time.time() - pipeline_start)
                    render_phase_card(phase_placeholder, icon, name, elapsed)
                    update_elapsed()

                progress_container.empty()
                pc_cols = progress_container.columns(2)
                crawl_progress_bar = pc_cols[0].progress(0, text="🕷️ Crawling in attesa...")
                audit_progress_bar = pc_cols[1].progress(0, text="🧠 AI Auditing in attesa...")

                def on_progress(current, total):
                    pct = current / total if total > 0 else 0
                    crawl_progress_bar.progress(pct, text=f"🔍 Scraping Maps: {current}/{total}")
                    update_elapsed()

                def on_crawl_progress(current, total):
                    pct = current / total if total > 0 else 0
                    crawl_progress_bar.progress(pct, text=f"🕷️ Crawling: {current}/{total}")
                    update_elapsed()

                def on_audit_progress(current, total):
                    pct = current / total if total > 0 else 0
                    audit_progress_bar.progress(pct, text=f"🧠 Auditing: {current}/{total}")
                    update_elapsed()

                def on_log(msg):
                    # Rimuovi emoji duplicati dal messaggio CLI
                    update_log(msg)
                    update_elapsed()

                with st.spinner("Pipeline AI in esecuzione..."):
                    results = orchestrator.run(
                        st.session_state.target_coords["lat"],
                        st.session_state.target_coords["lng"],
                        keywords,
                        min_rating=min_rating,
                        max_reviews=max_reviews,
                        min_age=min_age,
                        max_pages=max_pages,
                        token_mode=token_mode_str,
                        on_phase=on_phase,
                        on_progress=on_progress,
                        on_crawl_progress=on_crawl_progress,
                        on_audit_progress=on_audit_progress,
                        on_log=on_log,
                    )

            # --- RISULTATI ---
            total_elapsed = format_elapsed(time.time() - pipeline_start)
            
            if mode_key == "with_website":
                crawl_progress_bar.progress(1.0, text="✅ Crawling completato")
                audit_progress_bar.progress(1.0, text="✅ AI Auditing completato")
            else:
                progress_bar.progress(1.0, text=f"✅ Completato in {total_elapsed}")
                
            render_phase_card(phase_placeholder, "✅", f"Pipeline completata — {total_elapsed}", total_elapsed)

            if results:
                st.balloons()
                st.success(f"🎊 Pipeline completata! **{len(results)}** lead qualificati in **{total_elapsed}**.")

                city = orchestrator.scraper.get_city_name(
                    st.session_state.target_coords["lat"],
                    st.session_state.target_coords["lng"]
                )
                date_str = datetime.now().strftime("%d_%m_%Y")
                filename = f"Lead_Hunter_{city}_{date_str}.xlsx"
                DataExporter.export_to_excel(results, mode=mode_key, filename=filename)

                st.markdown("### 💎 Database Lead Premium")
                df = pd.DataFrame(results)
                st.dataframe(df, use_container_width=True)

                with open(filename, "rb") as f:
                    st.download_button(
                        label=f"📥 SCARICA REPORT: {filename}",
                        data=f,
                        file_name=filename,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
            else:
                st.warning("⚠️ La ricerca è terminata ma non sono stati trovati lead idonei in quest'area.")

        except Exception as e:
            st.error(f"❌ Errore durante l'esecuzione: {e}")
            update_log(f"<span style='color:#ef4444'>CRITICAL ERROR: {str(e)}</span>")