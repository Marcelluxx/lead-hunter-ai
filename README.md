# 🎯 Lead Hunter V3 — AI B2B Lead Generation Agent

Lead Hunter V3 is an AI-powered tool for automated B2B lead generation. It scrapes business data from Google Maps, applies intelligent filtering, optionally crawls and audits their websites using an LLM, and exports professional sales-ready reports.

## 🚀 Features

### Dual Operational Mode

| Mode | Description |
|------|-------------|
| **Senza Sito Web** | Finds businesses *without* a website — high-potential leads for digital services. Generates a business summary and key weakness via AI. |
| **Con Sito Web + Audit** | Finds businesses *with* a website, crawls and audits it with an LLM, filters aggressively, extracts emails, and generates a cold outreach message. |

### Core Capabilities

- **Grid-Based Scraping**: Scans a configurable 3x3 grid (9 API calls per keyword) to bypass Google's 20-result limit and ensure maximum area coverage.
- **Hybrid Web Crawler**: Two-pass architecture — fast static fetch (`httpx` + `BeautifulSoup`) with automatic fallback to headless `Playwright` for JavaScript-rendered sites (Wix, Squarespace, etc.).
- **Smart Filtering Pipeline** (Website Audit mode):
  - **Review Filter**: Rating > 3.9, review count between 1 and 100.
  - **Business Age Filter**: WHOIS domain age + regex copywriting analysis (e.g., "fondata nel 2005", "da oltre 15 anni"). If neither source finds data, the lead passes.
  - **Scale Filter**: Excludes e-commerce sites and known national franchises/chains.
- **AI Website Audit**: Sends crawled content to an LLM (via OpenRouter) for critical evaluation of copywriting, legal compliance, design, UX, and core services. Outputs a score (1–10), detailed diagnosis, site brief, and personalized cold outreach email.
- **Email Extraction**: Automatically detects emails during crawling via regex and `mailto:` attribute inspection.
- **Token Optimization**: Choose between High-Fidelity (semantic HTML + CSS class hints) and Optimized (clean Markdown) modes to control LLM token consumption.
- **Professional Excel Export**: Formatted with `openpyxl` — colored headers, alternating rows, conditional score coloring, freeze panes, and auto-filter.
- **Dual Interface**: Interactive Streamlit GUI with real-time progress tracking, or a full-featured CLI for automation.

---

## 🛠️ Installation & Setup

### 1. Clone the repository
```bash
git clone https://github.com/Marcellux02/agente-lead.git
cd agente-lead
```

### 2. Set up a Virtual Environment (Recommended)
```bash
python -m venv venv

# Windows:
venv\Scripts\activate

# macOS / Linux:
source venv/bin/activate
```

### 3. Install Python Dependencies
```bash
pip install -r requirements.txt
```

### 4. Install Playwright Browser
The hybrid crawler uses Playwright as a fallback for JavaScript-rendered websites. You need to install the Chromium browser binary (one-time setup, ~150 MB):
```bash
playwright install chromium
```

### 5. Configure API Keys
Copy the example environment file and fill in your API keys:
```bash
cp .env.example .env
```

Edit `.env` with your credentials:

| Variable | Source | Description |
|----------|--------|-------------|
| `GOOGLE_API_KEY` | [Google Cloud Console](https://console.cloud.google.com/) | Requires **Places API (New)** enabled |
| `OPENROUTER_API_KEY` | [OpenRouter](https://openrouter.ai/) | For LLM-based auditing |
| `LLM_MODEL` | OpenRouter model ID | Default: `meta-llama/llama-3.1-8b-instruct` |
| `TOKEN_MODE` | `high_fidelity` or `optimized` | Controls how website content is sent to the LLM |

### 6. Setup Prompts File (Required)
The AI system prompts are stored in `src/prompts.py`, which is **excluded from the public repository** via `.gitignore` to protect proprietary prompt engineering.

If you cloned the repo and the file is missing, create it manually:
```bash
# The file must exist at: src/prompts.py
# See the section "Prompt Architecture" below for the required structure.
```

> ⚠️ **Without `src/prompts.py`, the application will fail to start.** If you're a collaborator, request this file from the project owner.

---

## 💻 Usage

### 🎨 GUI Mode (Recommended)
The Streamlit GUI provides an interactive map, real-time progress bars, elapsed time tracking, and detailed system logs.
```bash
python main.py --gui
```

### ⚡ CLI Mode

**No Website Mode** (find businesses without a website):
```bash
python main.py --mode no_website --lat 45.4642 --lng 9.1900 --keywords ristorante
```

**With Website + Audit Mode** (full pipeline):
```bash
python main.py --mode with_website --lat 45.4642 --lng 9.1900 --keywords ristorante pizzeria
```

**Custom Parameters**:
```bash
python main.py --mode with_website \
    --lat 45.4642 --lng 9.1900 \
    --keywords dentista estetista \
    --min-rating 4.0 \
    --max-reviews 80 \
    --min-age 3 \
    --token-mode optimized \
    --max-pages 3 \
    --out leads_milano.xlsx
```

### CLI Arguments Reference

| Argument | Default | Description |
|----------|---------|-------------|
| `--mode` | `no_website` | `no_website` or `with_website` |
| `--lat` | — | Latitude (e.g., `45.4642` for Milan) |
| `--lng` | — | Longitude (e.g., `9.1900` for Milan) |
| `--keywords` | — | Space-separated search keywords |
| `--out` | Auto-generated | Output Excel filename |
| `--min-rating` | `3.9` | Minimum Google rating filter |
| `--max-reviews` | `100` | Maximum review count filter |
| `--min-age` | `5` | Minimum business age in years |
| `--token-mode` | `high_fidelity` | `high_fidelity` or `optimized` |
| `--max-pages` | `5` | Max pages to crawl per website |
| `--gui` | — | Launch the Streamlit GUI |
| `--examples` | — | Show usage examples |

---

## 📂 Project Structure

```
agente-lead/
├── main.py                 # Entry point — orchestrator + CLI
├── requirements.txt        # Python dependencies
├── .env                    # API keys (git-ignored)
├── .env.example            # Template for .env
├── src/
│   ├── __init__.py
│   ├── config.py           # Centralized configuration & constants
│   ├── scraper.py          # Google Places API integration + grid logic
│   ├── crawler.py          # Hybrid web crawler (httpx/BS4 + Playwright)
│   ├── filters.py          # Lead qualification filters (reviews, age, scale)
│   ├── auditor.py          # AI auditing via OpenRouter LLM
│   ├── exporter.py         # Excel export with openpyxl formatting
│   ├── prompts.py          # System prompts (git-ignored, proprietary)
│   └── gui.py              # Streamlit web interface
└── legacy/                 # Previous versions (reference only)
```

---

## 🔐 Prompt Architecture

All LLM system prompts are centralized in `src/prompts.py` for easy maintenance. This file is **git-ignored** to keep prompt engineering private in public repositories.

The file exports:
- `SYSTEM_NO_WEBSITE` — System prompt for the "No Website" analysis mode.
- `SYSTEM_WEBSITE_AUDIT` — System prompt for the full website audit mode.
- `build_no_website_prompt(...)` — Template function for generating lead analysis prompts.
- `build_website_audit_prompt(...)` — Template function for generating website audit prompts.

If `src/prompts.py` is missing (e.g., after a fresh clone of the public repo), the auditor module will fail to import. Either create the file manually following the exports above, or request it from the repository owner.

---

## 🏗️ Pipeline Architecture (Website Audit Mode)

```
Phase 1: Scrape Google Maps (grid 3x3)
    ↓
Phase 2: Filter by Reviews (rating > 3.9, reviews 1–100)
    ↓
Phase 3: Crawl Websites (httpx/BS4 → Playwright fallback)
    ↓
Phase 4: Filter by Business Age (WHOIS + copywriting regex)
    ↓
Phase 5: Filter by Scale (no e-commerce, no franchise)
    ↓
Phase 6: AI Website Audit (OpenRouter LLM)
    ↓
Export: Professional Excel report
```

---

*Created by [Marcellux02](https://github.com/Marcellux02)*
