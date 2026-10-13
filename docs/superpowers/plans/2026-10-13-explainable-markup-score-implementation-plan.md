# Explainable markup score Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL superpowers:executing-plans. Native inline sotto delega autonoma; una review fresca dell'intero branch alla fine.

**Goal:** Indice DOM ripetibile0–100 spiegato da nove componenti, separato dal voto AI.
**Architecture:** Derivazione pura da dom_report validato; builder indipendente dal modello, JSON/provenienza SQL e proiezioni API/XLSX ricontrollate.
**Tech Stack:** Python3.10–3.13, Fraction/hashlib/json, stack SQLAlchemy/openpyxl/SDK esistente.
**Spec:** docs/superpowers/specs/2026-10-13-explainable-markup-score-design.md

## Global Constraints

- Schema1/rubric dom-markup-1/rules1, nove pesi1, cap score_report12000 byte UTF8.
- Solo observed, rapporti matched/total aggregati per regola, media di regole con total>0; Fraction e half-up due decimali esatto, mai media di arrotondati.
- Unknown non è zero, not-applicable non è pass; complete/partial/unavailable e coverage DOM conservati.
- SHA JSON DOM canonico ensure_ascii=False/allow_nan=False/sort_keys=True/separators=(',',':'); bool/extra/versioni rifiutati per confronto esatto.
- DTO/colonne append-only; vote AI/filtri/provider/gate immutati, nessuna nuova dipendenza o migrazione, confidence0/uncalibrated.
- Scratch/worktree condiviso preservati dopo precedente rifiuto cleanup; nessun nuovo tentativo.

## Review Focus

- Unknown, NA e molte pagine omesse: indice dei soli osservati, copertura visibile, null distinto da zero (Task1).
- Rapporti frazionari e conteggi elevati: aggregazione per regola dichiarata, arrotondamento esatto, nessuna dipendenza dall'ordine (Task1).
- Model/custom audit o metadata DOM alterati: indice indipendente e digest legato all'intero report corrente (Task2/3).
- Vecchi record/report, firme DTO e client/workbook: storico unavailable, colonne precedenti ferme, numerico0 non svuotato (Task2/3).
- Corruzione SQL e cambiamenti fra snapshot/stream: errore sicuro, gate licenze/privacy attuali anche sui campi nuovi (Task3).

## Mappa file

Creare domain/markup_score.py e tests/test_markup_score.py, test_markup_score_runtime.py,
test_markup_score_delivery.py, docs/MARKUP_SCORE.md. Modificare domain/provenance.py,
application/provenance.py/diagnostic_runner.py/discovery.py/job_results.py, tester.py,
exporter.py, README, manuale DOM e roadmap. Nessuna modifica auditor/private prompt.

### Task 1: rubrica pura e validazione ricomputata

**Files:** creare src/domain/markup_score.py, tests/test_markup_score.py.
**Interfaces:** build_score_report(dom_report)->dict; empty_score_report()->dict;
validate_score_report(report, dom_report)->dict; RUBRIC_VERSION, MAX_SCORE_REPORT_BYTES.
- [ ] RED100/0/null, unknown/NA/omitted/partial, nove componenti e pesi spiegati, privacy/hash/cap.
- [ ] RED rapporti1/32 half-up3.13 e aggregazione fra pagine, exact total non media di score arrotondati, ordine invariato,20M contatori.
- [ ] RED score/hash/metadata DOM/bool/NaN/extra/versioni alterati rifiutati; DOM invalid conserva codice.
- [ ] Run uv run --frozen --group test python -m unittest tests.test_markup_score -v; Expected RED poi PASS.
- [ ] Implementare Fraction/binding canonico, commit feat: add versioned explainable markup index; Gitleaks staged; task-done stesso comando.

### Task 2: lead e boundary diagnostico

**Files:** domain/provenance.py, application/provenance.py/diagnostic_runner.py, tester.py; nuovo tests/test_markup_score_runtime.py.
**Interfaces:** VerifiedLead.score_report in coda/to_export_record, provenance website_markup_score; runner result score_report.
- [ ] RED builder ignora fake score_report e mantiene website_score AI, null crawl senza DOM, DTO positional compatibile.
- [ ] RED diagnostica sigillata include indice derivato, guard/priva dati immutati; tester context derivato, vecchio artifact invariato.
- [ ] Run uv run --frozen --group test python -m unittest tests.test_markup_score_runtime tests.test_dom_checks_runtime.DomRuntimeTests tests.test_diagnostic_runtime tests.test_dependency_injection tests.test_compliant_pipeline -v; Expected RED poi PASS.
- [ ] Collegare derivazione dopo DOM, nessun nuovo payload AI/chiamata; commit feat: derive markup score independently at runtime; task-done stesso comando.

### Task 3: persistenza e consegna

**Files:** application/discovery.py/job_results.py, exporter.py, tests/test_markup_score_delivery.py, docs/MARKUP_SCORE.md, README/DOM manual/roadmap.
**Interfaces:** API score_report oggetto separato, errore job_score_report_invalid; ultime colonne Markup Score/markup_score, Score Report/score_report.
- [ ] RED locale + SDK/worker/SQL/HTTP/workbook riaperto stesso indice numerico e report, precedente DOM/Audit colonne ferme, no HTML/label nuovi.
- [ ] RED0 numerico/null cella vuota; storico score assente unavailable; score/hash/DOM alterato/JSON/bool invalid safe error; snapshot/gate regressioni.
- [ ] Run uv run --frozen --group test python -m unittest tests.test_markup_score_delivery tests.test_dom_checks_delivery tests.test_audit_evidence_delivery tests.test_commercial_job_api tests.test_provenance_retention tests.test_spreadsheet_security -v; Expected RED poi PASS.
- [ ] Implementare ricomputazione prima SQL/lettura/export e append-only; adeguare precedenti test final-column a verifica posizioni stabili, documentare formula/limiti e PR15 merge3a8c3df/postgate8PASS.
- [ ] Run full suite PostgreSQL17/Chromium/distribuzione, uv lock --check/compile/diff/Gitleaks; Expected PASS senza skip.
- [ ] Commit feat: deliver bound markup scores through API and Excel; push/draftPR/attach; task-done mirato.

## Autorevisione e chiusura

Contratti spec presenti, bounds e nomi coerenti, cinque Review Focus legati ai test.
Spec/piano autorevisionati sotto delega; nessun dataset umano inventato. One fresh
whole-branch review sul modello più capace read-only, senza subagent o rereview;
Important/Critical unico fix pass TDD+suite, minor solo rinviati, rulings tracciati.
Gate exactHEAD8PASS prima PR pronta. Merge separato; scratch ignorato preservato.
