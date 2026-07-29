# Lead Hunter V3 — Dependency Report

**Baseline:** `62e5d9a` + modifiche locali preservate
**Metodo:** parsing AST deterministico di tutti i file Python rilevati da Graphify e confronto con `requirements.txt`.

## Sintesi

- Dipendenze dichiarate: **16**
- Occorrenze di import terzi: **25**
- Occorrenze di import interni: **19**
- Occorrenze standard library: **55**
- Import irrisolti: **0**

## Dipendenze dichiarate e uso diretto

| Pacchetto | Versione bloccata | Import diretti | File sorgente |
|---|---:|---:|---|
| `beautifulsoup4` | no | 2 | src/crawler.py, src/tester.py |
| `crawl4ai` | no | 3 | src/crawler.py |
| `folium` | no | 1 | src/gui.py |
| `html2text` | no | 0 | — |
| `httpx` | no | 1 | src/tester.py |
| `openai` | no | 2 | src/auditor.py |
| `openpyxl` | no | 3 | src/exporter.py |
| `pandas` | no | 3 | legacy/lead_hunter.py, legacy/lead_hunter_v2.py, src/gui.py |
| `playwright` | no | 0 | — |
| `playwright-stealth` | no | 0 | — |
| `python-dotenv` | no | 3 | legacy/lead_hunter.py, legacy/lead_hunter_v2.py, src/config.py |
| `python-whois` | no | 1 | src/filters.py |
| `requests` | no | 4 | legacy/lead_hunter.py, legacy/lead_hunter_v2.py, src/gui.py, src/scraper.py |
| `streamlit` | no | 1 | src/gui.py |
| `streamlit-folium` | no | 1 | src/gui.py |
| `whois` | no | 1 | src/filters.py |

Le dipendenze senza import diretto nel codice corrente sono: `html2text`, `playwright`, `playwright-stealth`. Possono essere transitive o residui del crawler precedente; vanno verificate prima di rimuoverle.

## Rischi rilevati

1. **Nessuna versione è bloccata.** Una nuova installazione può ottenere API o dipendenze transitive differenti.
2. **Collisione WHOIS.** `python-whois` e `whois` sono entrambi dichiarati e possono esporre lo stesso modulo `whois`; i due archi sono marcati `AMBIGUOUS` nel grafo.
3. **Crawl4AI non è bloccato.** Il nuovo crawler dipende fortemente dalla sua API e dal browser sottostante.
4. **Residui potenziali.** `html2text`, `playwright` e `playwright-stealth` non sono importati direttamente dopo la migrazione, ma possono essere transitivi o ancora necessari a procedure esterne.
5. **Ambiente non riproducibile.** Il virtualenv del repository contiene solo `pip` e manca un lockfile.

## Moduli standard più usati

| Modulo | Occorrenze |
|---|---:|
| `typing` | 10 |
| `os` | 7 |
| `sys` | 4 |
| `time` | 4 |
| `re` | 4 |
| `logging` | 4 |
| `urllib` | 4 |
| `asyncio` | 3 |
| `datetime` | 3 |
| `math` | 3 |
| `concurrent` | 2 |
| `json` | 2 |
| `argparse` | 1 |
| `textwrap` | 1 |
| `subprocess` | 1 |
| `random` | 1 |
| `dataclasses` | 1 |

## Dipendenze interne

| Modulo | Occorrenze |
|---|---:|
| `src.filters` | 4 |
| `src.config` | 4 |
| `src.auditor` | 2 |
| `src.exporter` | 2 |
| `src.crawler` | 2 |
| `src.prompts` | 2 |
| `src.scraper` | 1 |
| `src.tester` | 1 |
| `main` | 1 |

## Correzione raccomandata

1. Migrare a `pyproject.toml`.
2. Scegliere un solo provider WHOIS dietro un adapter interno.
3. Generare `uv.lock` o lock equivalente con hash.
4. Dichiarare la versione Python supportata.
5. Separare dipendenze runtime, GUI, test e sviluppo.
6. Verificare e rimuovere i residui non importati direttamente.
7. Generare SBOM e attivare scansione CVE/licenze in CI.
