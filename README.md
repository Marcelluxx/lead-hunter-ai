# 🎯 Lead Hunter V3 - AI B2B Lead Generation Agent

Lead Hunter V3 is a powerful AI-driven tool designed to automate the process of finding and auditing B2B leads. It scrapes business data from Google Maps (focusing on those without websites), uses an LLM (via OpenRouter) to analyze their potential, and generates personalized sales hooks.

## 🚀 Features

- **Automated Scraping**: Scans a 3x3 grid around a specific coordinate to ensure maximum coverage and bypass Google's 20-result limit.
- **Smart Filtering**: Specifically targets businesses without a website (high-potential leads for digital services).
- **AI-Powered Auditing**: Analyzes lead data using state-of-the-art LLMs to identify ideal digital products and create tailored sales hooks.
- **Competitor Analysis**: Automatically identifies the top-performing local competitor for each niche.
- **Dual Interface**:
    - **CLI Mode**: Fast, professional terminal interface for power users.
    - **GUI Mode**: Interactive web interface with a map-based selection tool.
- **Professional Export**: Generates beautifully formatted Excel reports with auto-adjusted columns.

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
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configuration
Create a `.env` file in the root directory and add your API keys. You can use `.env.example` as a template:
```bash
cp .env.example .env
```
Edit the `.env` file and fill in your keys:
- **GOOGLE_API_KEY**: Get it from [Google Cloud Console](https://console.cloud.google.com/). Ensure **Places API (New)** is enabled.
- **OPENROUTER_API_KEY**: Get it from [OpenRouter](https://openrouter.ai/).

---

## 💻 Usage

### 🎨 Running the GUI (Recommended)
The GUI provides an interactive map where you can click to select coordinates and start searching with a few clicks.
```bash
python main.py --gui
```

### ⚡ Running the CLI
For automated tasks or batch processing, use the command line:

**Basic Search:**
```bash
python main.py --lat 45.4642 --lng 9.1900 --keywords ristorante
```

**Multiple Keywords & Custom Output:**
```bash
python main.py --lat 41.9028 --lng 12.4964 --keywords ristorante pizzeria bar --out leads_roma.xlsx
```

**Show Help & Examples:**
```bash
python main.py --help
python main.py --examples
```

---

## 📂 Project Structure

- `main.py`: Entry point for both CLI and GUI modes.
- `src/`:
    - `scraper.py`: Handles Google Places API interactions and grid logic.
    - `auditor.py`: Manages LLM analysis via OpenRouter.
    - `exporter.py`: Handles Excel file generation and formatting.
    - `gui.py`: Streamlit-based interactive web interface.
    - `config.py`: Central configuration for API settings and search parameters.
- `.env`: (Hidden) Your private API keys.
- `requirements.txt`: Python package dependencies.

---
*Created by Marcellux02*
