# Diagnostica completa Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recuperare il tester completo con licenza a scadenza e archivi protetti GUI/CLI.
**Architecture:** Sessione runtime comune con access/context factory, collector limitato e thread-safe, ZIP isolato. Hook opt-in crawler/auditor, runner comune e presentazioni separate dai report cliente.
**Tech Stack:** Python 3.10–3.13, libreria standard ZIP/atomic files, licensing esistente, Crawl4AI 0.9.2, Streamlit.
**Spec:** docs/superpowers/specs/2026-10-10-diagnostica-completa-design.md

## Global Constraints

- Retention intera 1–168 ore, default 24; 1 MiB/record, 8 MiB/run, 256 record.
- EXECUTE START_JOB; VIEW VIEW_AUDIT_LOG; MFA server obbligatoria per entrambi.
- Opt-in, niente provider payload/metriche, niente campi diagnostici pubblici.
- Nessuna nuova dipendenza/migrazione; permessi locali invariati.
- Nome file generato UUID, file atomico; nessun payload in media/session_state.
- Metodo native e decisioni ordinarie autonome delegati dal proprietario.

## Review Focus

1. Licenza revocata nel callback browser/LLM: nessun tentativo seguente o fallback che assorba LicenseError (Task 2).
2. Capture parallele: nessuna perdita, contaminazione tra run o superamento del limite aggregato (Task 1/2).
3. Segreti in JSON, query URL, HTML o prompt: ZIP redatto, nessuna esposizione nei messaggi errore (Task 1/2).
4. Accesso perso dentro ZIP/fsync/HTML: nessuna sostituzione di file né nuovo download inline (Task 1/3).
5. Input invalido o license_missing: zero crawler/LLM/files e base diagnostica ancora utilizzabile (Task 3).

### Task 1: Sessione diagnostica comune e archivio atomico

**Files:** creare src/application/diagnostics.py, tests/test_full_diagnostics.py.
**Interfaces:** `DiagnosticSession(access, context_factory, *, retention_hours=24, secrets=())`; `require_execute()`, `require_view()`, `capture(kind: str, payload: dict)`, `export_bytes() -> bytes`, `save(destination: Path) -> Path`; `DiagnosticError.code`; runtime non serializzabile.

- [ ] **Step 1:** Scrivere test licenze firmate reali e catalogo solo-test disponibile. Assert ZIP manifest/schema/expire, redazione ricorsiva segreti, rifiuto provider payload; limiti/concorrenti; revoca in serializzazione/fsync conserva vecchio file e nega bytes; server MFA/ruoli correnti; base nessuna dipendenza dal collector.
- [ ] **Step 2:** RED `python -m unittest tests.test_full_diagnostics -v`: interfaccia assente.
- [ ] **Step 3:** Implementare sessione/JSON/ZIP con lock, redazione e budget, autorizzazioni per ogni fase, salvataggio atomico e cleanup esclusivamente temporaneo creato dal servizio.
- [ ] **Step 4:** GREEN stessi test, poi contratti licensing/export esistenti.
- [ ] **Step 5:** Commit `feat: add protected diagnostic sessions and atomic archives`.

### Task 2: Hook opt-in crawler/auditor e runner comune

**Files:** modificare src/crawler.py, src/auditor.py, src/application/container.py; creare src/application/diagnostic_runner.py, tests/test_diagnostic_runtime.py.
**Interfaces:** constructor crawler/auditor `diagnostics: DiagnosticSession | None = None`; `run_full_diagnostic(url, *, session, crawler, auditor) -> dict` riusa i servizi e chiude crawler sempre; container `build_local_diagnostic_session(*, retention_hours=24)`.

- [ ] **Step 1:** Test capture HTML/testo/CSS caricati senza fetch extra, prompt/risposta completa esclusi dal DTO pubblico; preflight prima di API/prompt; LicenseError attraverso fallback/retry/cleaning, revoca durante callbacks, due run separati e cleanup crawler su errore.
- [ ] **Step 2:** RED `python -m unittest tests.test_diagnostic_runtime -v`.
- [ ] **Step 3:** Implementare hook browser e capture dei prompt/output con check esterni alle catch generiche; runner registra evidenze e summary, errori redatti e pulizia in finally. Base senza sessione invariata.
- [ ] **Step 4:** GREEN test nuovi e test crawler/audit/injection/provenienza esistenti.
- [ ] **Step 5:** Commit/push `feat: recover licensed crawl and AI diagnostic capture`.

### Task 3: CLI/GUI, attivazione e gate

**Files:** modificare main.py, src/gui.py, src/licensing/catalog.py, tests/test_feature_license_contract.py, src/ui/inline_download.py; creare src/ui/diagnostic_panel.py, tests/test_diagnostic_delivery.py; aggiornare README/milestone/report.
**Interfaces:** `--full-diagnostics --test-url URL [--diagnostic-output PATH]`; pannello GUI URL dedicato; helper inline MIME generico compatibile con XLSX; catalogo diagnostica available.

- [ ] **Step 1:** Test CLI invalidi/negati exit2 prima di effetti; archive real ZIP e revoca prima commit preserva vecchio; GUI controllo senza licenza, ZIP inline, revoca dentro HTML no iframe, niente bytes session/media. Catalogo reale e MFA invariati.
- [ ] **Step 2:** RED `python -m unittest tests.test_diagnostic_delivery -v`.
- [ ] **Step 3:** Implementare preflight, runner comune, output sicuro/atomic; pannello GUI e attivazione produttiva dopo i flussi. Documentare limiti CSS/retention/offline e stato autonoma.
- [ ] **Step 4:** GREEN test, suite completa, uv lock --check/compileall/diff/Gitleaks; browser crawler reale. Review fresca whole branch base c231e8c (gpt-6-astra/high), un passaggio fix RED→GREEN se necessario.
- [ ] **Step 5:** Commit/push, PR develop, attach, CI/Security esatto HEAD; integrare dopo verde sotto la delega autonoma. Aggiornare report e continuare il sottoprogetto pipeline server.

Piano autorevisionato sotto la delega autonoma; tutte le interfacce dei tre task
sono coerenti. Le approvazioni procedurali intermedie sono sostituite dalla
richiesta esplicita di procedere autonomamente, senza fermarsi ai singoli moduli.
