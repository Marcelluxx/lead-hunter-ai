# `<p align="center">`🎯 Lead Hunter V3`</p>`

<p align="center">
  <strong>Enterprise-Grade AI-Powered B2B Lead Generation & Web Auditing Agent</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10+-blue.svg?style=for-the-badge&logo=python&logoColor=white" alt="Python Version" />
  <img src="https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=Streamlit&logoColor=white" alt="Streamlit UI" />
  <img src="https://img.shields.io/badge/Playwright-2EAD33?style=for-the-badge&logo=Playwright&logoColor=white" alt="Playwright Crawler" />
  <img src="https://img.shields.io/badge/LLM-OpenRouter-orange?style=for-the-badge" alt="OpenRouter LLM" />
  <img src="https://img.shields.io/badge/license-MIT-green.svg?style=for-the-badge" alt="License MIT" />
</p>

---

## 📖 Overview

**Lead Hunter V3** is an advanced, enterprise-ready B2B sales intelligence agent designed to find, qualify, crawl, and audit commercial leads. By combining the high-density geofencing capabilities of **Google Places API** with a dynamic, hybrid **static/Playwright crawler** and state-of-the-art **large language models (LLMs)**, it builds fully audited, cold-outreach-ready lead pipelines with zero manual effort.

Whether targeting local businesses that lack a digital presence or performing deep, technical compliance audits of complex business websites, Lead Hunter V3 delivers clean, validated, and highly structured commercial insights.

---

## 🏗️ Pipeline Architecture

```
[1] GEO-GRID SCANNERS ────────> [2] PRE-QUALIFICATION FILTERS
    - Google Places API V1          - Rating (> 3.9) & Review volume thresholds
    - Custom geofencing (3x3 grid)  - Domain-based social media filtering
            │                               │
            ▼                               ▼
[4] CORE PIPELINE FILTERS <───── [3] HYBRID CRITICAL CRAWLER
    - WHOIS & Copywriting Age check - Fast HTTPX/BS4 parser
    - Scalability (No E-Com)        - Stealth headless Playwright fallback
    - Franchise exclusion list      - Intelligent Link Discovery
            │
            ▼
[5] TWO-TIER AI WEBSITE AUDIT ─────────> [6] PROFESSIONAL EXPORTER
    - Tier-1: Concurrent Preprocessing      - Clean openpyxl Excel reports
    - Tier-2: OpenRouter Auditor            - Alternating rows & Color conditioning
    - XML Structured prompts                - Dedicated outputs/ directory
```

---

## ✨ Key Features

### 🔄 Dual Operational Modes

| Operational Mode                             | Core Objective                                           | Target Prospects                        | Primary AI Insights                                                                                                 |
| :------------------------------------------- | :------------------------------------------------------- | :-------------------------------------- | :------------------------------------------------------------------------------------------------------------------ |
| 🌐**Without Website (`no_website`)** | Target high-potential digital services prospects         | Businesses lacking an active web domain | Business summary, identified core operational weaknesses, tailored digital transformation pitch.                    |
| ⚡**With Website (`with_website`)**  | Conduct automated, deep-dive business & technical audits | Businesses with active websites         | Full Design UX diagnostic, legal compliance audits (VAT/Partita IVA check), email extraction, tailored sales hooks. |

### 🔍 Core Capabilities

* **Hybrid Web Crawler & Playwright Fallback**: Operates in two passes. A fast static parsing layer (`httpx` + `BeautifulSoup`) falls back automatically to a stealth-enabled, headless `Playwright` browser configuration for single-page applications (SPAs) or JavaScript-heavy websites.
* **Intelligent AI Link Discovery**: When traditional regex navigation fails, a secondary lightweight LLM dynamically inspects HTML navigation blocks to find highly critical commercial subpages (e.g., matching regional naming conventions like `attivita.html` or `struttura.html`).
* **Token Optimization Engine**: Minimizes API costs by actively stripping layout boilerplate, collapsing whitespace, merging multi-line empty blocks, and converting raw HTML into pristine, high-density semantical Markdown structure.
* **Two-Tier AI Website Audit**:
  1. *Concurrent Pre-processing*: Clean and summarize multiple subpages simultaneously in background threads using cost-effective models.
  2. *Audit Execution*: A specialized auditor LLM receives the compiled, XML-tagged structural site data to evaluate corporate copywriting, local legal standards (e.g., VAT disclosure in footer), design elegance, and core offerings, generating a 1–10 quality score.
* **Clean Email Extraction**: Runs simultaneous extraction routines using highly permissive regex patterns and active anchor tag (`mailto:`) inspection.
* **Automated Diagnostics**: Writes full intermediate text files (raw API requests, prompt inputs, and preprocessed subpages) directly to a dedicated `test_output/` folder for transparent quality monitoring.
* **Enterprise Excel Export**: Automatically organizes and saves reports into a dedicated, git-ignored `outputs/` directory. Features auto-fitting columns, conditional formatting based on rating scores, freeze-panes, and auto-filters.

---

## 📂 Project Directory Structure

<details>
<summary>📂 Click to view directory hierarchy</summary>

```
agente-lead/
├── main.py                  # CLI Entry point & Core Orchestrator
├── requirements.txt         # Package dependencies
├── .env                     # Local API keys (Git ignored)
├── .env.example             # Configuration template for .env
├── outputs/                 # Dedicated output directory for Excel reports (Git ignored)
├── test_output/             # Debugging logs & compiled prompt files (Git ignored)
├── src/
│   ├── __init__.py          # Source package initialization
│   ├── config.py            # Centralized settings, limits, & constants
│   ├── scraper.py           # Google Places API V1 grid parser
│   ├── crawler.py           # Double-pass hybrid crawler (Playwright/HTTPX)
│   ├── filters.py           # Business filters (Age, Scale, Reviews, Socials)
│   ├── auditor.py           # Multi-threaded AI website preprocessors & main auditor
│   ├── exporter.py          # Professional openpyxl formatting suite
│   ├── prompts.py           # Enterprise system prompts (Git ignored)
│   └── gui.py               # Premium interactive Streamlit Dashboard
└── legacy/                  # Retrospective development references
```

</details>

---

## 🛠️ Installation & Configuration

### 1. Repository Setup & Virtual Environment

```bash
# Clone the repository
git clone https://github.com/Marcellux02/agente-lead.git
cd agente-lead

# Initialize virtual environment
python -m venv venv

# Activate environment
# On Windows:
venv\Scripts\activate
# On macOS / Linux:
source venv/bin/activate
```

### 2. Dependency Installation

```bash
# Install core Python packages
pip install -r requirements.txt

# Install stealth browser binaries for Playwright
playwright install chromium
```

### 3. API Key & Local Environment Configuration

Copy the template configuration file:

```bash
cp .env.example .env
```

Open `.env` and fill out your service credentials:

```ini
# Google Places & Geocoding API keys
GOOGLE_API_KEY=your_google_places_api_key_here

# OpenRouter LLM Access
OPENROUTER_API_KEY=your_openrouter_api_key_here

# System Model Selection
LLM_MODEL=meta-llama/llama-3.1-8b-instruct
LLM_MODEL_FREE=google/gemini-2.5-flash:free

# Audit Quality Selection (high_fidelity | optimized)
TOKEN_MODE=high_fidelity
```

### 4. Setting up Prompt Structures

For security and IP preservation, system-level prompt files are completely excluded from public Git versioning.
Ensure a file exists at `src/prompts.py` exporting the required structural templates:

* `SYSTEM_NO_WEBSITE`: Analysis template for businesses without an online portal.
* `SYSTEM_WEBSITE_AUDIT`: Structured deep audit constraints.
* `build_no_website_prompt()`: Context payload compiler.
* `build_website_audit_prompt()`: Detailed multi-page auditor payload compiler.

---

## 💻 Operational Interface

### 🎨 The Interactive GUI Dashboard (Recommended)

Launch the fully-featured, sleek dashboard powered by Streamlit:

```bash
python main.py --gui
```

The interface includes:

* Interactive **Leaflet maps** for centering geo-coordinate grid scans.
* Toggle filters for Rating thresholds, Review counts, Business age, and Crawler depth.
* Real-time scrolling **System log terminal**.
* Parallel progress bars displaying crawler and AI audit tasks.
* Dynamic dataframes to preview results before downloading custom-named files.

---

### ⚡ The Command Line Interface (CLI)

#### 1. Basic Scanning: "Without Website" Mode

Scan coordinate grids for local businesses lacking websites and generate digital transformation leads:

```bash
python main.py --mode no_website --lat 45.4642 --lng 9.1900 --keywords ristorante
```

#### 2. Advanced Scanning: "With Website" + AI Auditing

Locate qualified businesses with active websites, crawl them, perform an AI design/UX audit, and extract contact details:

```bash
python main.py --mode with_website --lat 45.4642 --lng 9.1900 --keywords "dentista" "estetista"
```

#### 3. Enterprise Crawling with Custom Constraints

Run highly targeted CLI scans with specialized filtering criteria:

```bash
python main.py --mode with_website \
    --lat 45.4642 --lng 9.1900 \
    --keywords "pizzeria" \
    --min-rating 4.0 \
    --max-reviews 75 \
    --min-age 5 \
    --max-pages 4 \
    --token-mode high_fidelity \
    --out lead_report_milano.xlsx
```

#### CLI Parameters Reference

<details>
<summary>📋 Click to view command arguments reference table</summary>

| Flag              | Default Value         | Description                                                          |
| :---------------- | :-------------------- | :------------------------------------------------------------------- |
| `--mode`        | `no_website`        | Active operational pipeline:`no_website` or `with_website`.      |
| `--lat`         | *Required*          | Floating latitude coordinate representing scanning focal point.      |
| `--lng`         | *Required*          | Floating longitude coordinate representing scanning focal point.     |
| `--keywords`    | *Required*          | Space-separated list of target industries or search keywords.        |
| `--out`         | `leads_output.xlsx` | Output filename. Automatically placed inside `outputs/`.           |
| `--min-rating`  | `3.9`               | Excludes leads below this minimum rating.                            |
| `--max-reviews` | `100`               | Excludes massive national franchises or corporate giants.            |
| `--min-age`     | `5`                 | Requires target domain registry to exist for a minimum of N years.   |
| `--token-mode`  | `high_fidelity`     | Selects processing fidelity:`high_fidelity` or `optimized`.      |
| `--max-pages`   | `5`                 | Maximum deep-crawl limit for individual business subpages.           |
| `--no-headless` | `False`             | Disables invisible crawling and opens a headed browser window.       |
| `--gui`         | `False`             | Bypasses CLI processing and boots the interactive web-UI.            |
| `--examples`    | `False`             | Displays typical pipeline execution templates and immediately exits. |

</details>

---

## 🔒 Security, Compliance & Optimization

* **Respectful Crawling**: Crawler requests respect page access latency and follow strict rate limits to avoid triggering anti-bot protections.
* **Privacy-First Exclusions**: Pre-filtering processes exclude highly protective public social media sites (e.g. `facebook.com`, `instagram.com`) automatically to prevent useless network overhead.
* **Secure API Architecture**: Key values, private prompts, and generated results are saved entirely in local storage under `outputs/` to respect enterprise privacy standards.

---

<p align="center">
  Developed with 🎯 by <a href="https://github.com/Marcelluxx">Marcelluxx</a>
</p>
