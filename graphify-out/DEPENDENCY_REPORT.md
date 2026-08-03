# Lead Hunter V3 — Dependency Report

**Baseline:** branch `codex/p0-data-output-hardening`, commit applicativi fino a `71e5f47`
**Metodo:** parsing AST deterministico dei 31 file Python tracciati, inclusi i test di sicurezza e privacy, e confronto con `requirements.txt`.

## Sintesi

- Dipendenze dichiarate: **16**
- Occorrenze di import terzi: **25**
- Occorrenze di import interni: **44**
- Occorrenze standard library: **111**
- Import locali in stile compatibilità (`filters`, `config`, `exporter`, `security`): **7**

## Dipendenze dichiarate e uso diretto

| Pacchetto | Versione bloccata | Import diretti | File sorgente |
|---|---:|---:|---|
| `beautifulsoup4` | no | 2 | src/crawler.py, src/security/untrusted_content.py |
| `crawl4ai` | no | 3 | src/crawler.py |
| `folium` | no | 1 | src/gui.py |
| `html2text` | no | 0 | — |
| `httpx` | no | 0 | — |
| `openai` | no | 2 | src/auditor.py |
| `openpyxl` | no | 4 | src/exporter.py, tests/test_spreadsheet_security.py |
| `pandas` | no | 3 | legacy/lead_hunter.py, legacy/lead_hunter_v2.py, src/gui.py |
| `playwright` | no | 0 | — |
| `playwright-stealth` | no | 0 | — |
| `python-dotenv` | no | 3 | legacy/lead_hunter.py, legacy/lead_hunter_v2.py, src/config.py |
| `python-whois` | no | 1 | src/filters.py |
| `requests` | no | 4 | legacy/lead_hunter.py, legacy/lead_hunter_v2.py, src/scraper.py, src/security/geolocation.py |
| `streamlit` | no | 1 | src/gui.py |
| `streamlit-folium` | no | 1 | src/gui.py |
| `whois` | no | 1 | src/filters.py |

Le dipendenze senza import diretto nel codice corrente sono: `html2text`, `httpx`, `playwright`, `playwright-stealth`. Possono essere transitive o residui del crawler precedente; vanno verificate prima di rimuoverle.

## Rischi rilevati

1. **Nessuna versione è bloccata.** Una nuova installazione può ottenere API o dipendenze transitive differenti.
2. **Collisione WHOIS.** `python-whois` e `whois` sono entrambi dichiarati e possono esporre lo stesso modulo `whois`; i due archi sono marcati `AMBIGUOUS` nel grafo.
3. **Crawl4AI non è bloccato.** Il crawler dipende fortemente dalla sua API e dal browser sottostante; la versione deve includere le correzioni di sicurezza upstream più recenti.
4. **Residui potenziali.** `html2text`, `httpx`, `playwright` e `playwright-stealth` non sono importati direttamente dopo la migrazione, ma possono essere transitivi o ancora necessari a procedure esterne.
5. **Ambiente non riproducibile.** Il virtualenv del repository contiene solo `pip` e manca un lockfile.
6. **Provider di geolocalizzazione configurabile.** `requests` è ora usato dal boundary HTTPS opt-in in `src/security/geolocation.py`; il provider deve restare nell’inventario dei sub-responsabili ed essere contrattualizzato per la produzione.

## Moduli standard più usati

| Modulo | Occorrenze |
|---|---:|
| `typing` | 17 |
| `os` | 10 |
| `sys` | 4 |
| `time` | 6 |
| `re` | 7 |
| `logging` | 5 |
| `urllib` | 6 |
| `asyncio` | 4 |
| `datetime` | 4 |
| `math` | 3 |
| `concurrent` | 2 |
| `json` | 4 |
| `dataclasses` | 5 |
| `unittest` | 8 |
| `__future__` | 8 |
| `pathlib`, `socket`, `tempfile` | 2 ciascuno |
| `argparse` | 1 |
| `textwrap` | 1 |
| `subprocess` | 1 |
| `random` | 1 |
| `hashlib`, `enum`, `html`, `numbers`, `ipaddress`, `threading`, `types`, `unicodedata` | 1 ciascuno |

## Dipendenze interne

| Modulo | Occorrenze |
|---|---:|
| `src.domain` e relativi fallback | 6 |
| `src.security` e relativi moduli/fallback | 18 |
| `src.crawler` | 3 |
| `src.filters` e fallback | 4 |
| `src.config` e fallback | 4 |
| `src.auditor` | 2 |
| `src.exporter` e fallback | 3 |
| `src.prompts` | 1 |
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
