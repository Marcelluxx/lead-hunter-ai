# Deterministic DOM checks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL superpowers:executing-plans. Native sotto delega autonoma, test mirati per task, suite completa finale e una review indipendente.

**Goal:** Nove misure DOM ripetibili, con prove bounded e consegna locale/server.
**Architecture:** Snapshot privati HTML + MD hash, puro analyzer DOM versionato,
adapter al crawl/LLM, report derivato ricontrollato prima di SQL e proiezione pubblica.
**Tech Stack:** Python3.10–3.13, BeautifulSoup e SDK/SQLAlchemy/openpyxl esistenti.
**Spec:** docs/superpowers/specs/2026-10-13-deterministic-dom-checks-design.md

## Global Constraints

- Snapshot HTML250000 byte, max20000 tag/pagina, analisi2000000 byte/crawl.
- Report schema1/rules1, massimo20 pagine/24000 byte UTF8, matched<=total<=1000000.
- Nessuna nuova dipendenza/fetch/call provider; niente HTML/label/contatti grezzi nei campi pubblici.
- Misure markup soltanto, niente voto nuovo, calibrazione, certificazione o esclusione lead.
- DTO/colonne append-only, firme custom auditor compatibili tramite capability.
- Gate workspace/privacy/licenze/snapshot invariati; vecchie cartelle scratch preservate.

## Review Focus

- DOM parziale, MIME ignoto, limiti byte/nodi: unknown, mai falsa assenza (Task1).
- Testo invisibile/inerto, ID duplicati e label nascoste referenziate: conteggi del predicato corretto, non AccName/computed CSS (Task1).
- Redirect ripetuti/staleness DOM/MD/time: ultimo snapshot coerente, vecchio non falsifica quello corrente (Task2).
- Modello o custom auditor non può attribuire autorità a dom_report; niente HTML/secret echo via nuovo payload (Task2).
- Venti URL Unicode lunghi oltre budget e storico/SQL corrotto: report bounded parziale o errore sicuro, mai perdita silenziosa di lead (Task3).

## Mappa file

Creare src/domain/dom_evidence.py, src/domain/dom_checks.py (capture/analyzer/validator),
src/application/dom_checks.py (binding/helper), tre moduli tests/test_dom_checks.py,
tests/test_dom_checks_runtime.py, tests/test_dom_checks_delivery.py, manuale docs/DOM_CHECKS.md.
Modificare crawler.py/domain/crawl.py; application/provenance.py/domain/provenance.py;
auditor.py/main.py/workers/handlers.py/application/diagnostic_runner.py/tester.py;
application/discovery.py/application/job_results.py/exporter.py, README/roadmap.

### Task 1: snapshot e analyzer puro

**Files:** creare domain/dom_evidence.py, domain/dom_checks.py, tests/test_dom_checks.py.
**Interfaces:** DomPageEvidence.capture(html, page_evidence); inspect_dom(snapshot)->(checks, reason);
RULES_VERSION='1', RULE_IDS nove ID spec; validate_dom_report(report)->dict;
empty_dom_report()->dict; public_evidence_url(url) da domain/audit_evidence.py.
- [ ] RED snapshot limita byte/MIME e conserva hash corretto, HTML repr privato; documento completo misura nove regole.
- [ ] RED missing/partial/over20000tag -> inconclusive; hidden/template/script/comment/Unicode/ID dup, label e alt vuoto, href malformato -> conteggi specifici.
- [ ] RED report strettamente tipizzato, outcome derivato, limiti/count bool/integrità coperti.
- [ ] Run uv run --frozen --group test python -m unittest tests.test_dom_checks -v; Expected FAIL poi PASS.
- [ ] Implementare indicizzazione e text flags O(N), enum e limiti esatti della spec.
- [ ] Commit feat: measure bounded DOM markup with versioned rules, Gitleaks staged; task-done stesso comando.

### Task 2: crawler, binding e contesto auditor

**Files:** creare application/dom_checks.py/test_dom_checks_runtime.py; modificare
domain/crawl.py, crawler.py, domain/provenance.py, application/provenance.py,
auditor.py, main.py, workers/handlers.py, application/diagnostic_runner.py, tester.py.
**Interfaces:** build_dom_report(crawl)->dict; audit_with_dom_report(auditor, *, dom_report, **legacy_arguments)->dict;
VerifiedLead.dom_report in coda; LeadAuditor.supports_dom_report=True e audit_website(..., dom_report=None).
- [ ] RED Chromium homepage/interna -> snapshot con hash/time corretti, metadata indep da modeMarkdown.
- [ ] RED binding snapshot/MD/time alterati rifiutati, ultimo URL duplicato coerente; legacy homepage e pagine non catturate esplicite; budget2MB parziale.
- [ ] RED SDK riceve misure prima del catalogo originale, niente HTML o label/segreti, stesso numero chiamate; vecchio auditor senza capability conserva firma; fake dom_report modello ignorato dal builder.
- [ ] Run uv run --frozen --group test python -m unittest tests.test_dom_checks_runtime tests.test_audit_evidence_runtime tests.test_compliant_pipeline tests.test_diagnostic_runtime tests.test_rating_filter_delivery -v con browser flag1; Expected RED poi PASS.
- [ ] Integrare capture valid pages, helper ai quattro entrypoint; rederive report prima persistence, nessuna nuova operazione provider.
- [ ] Commit feat: bind DOM checks to crawl and audit context; task-done stesso comando.

### Task 3: persistenza, API e workbook

**Files:** creare test_dom_checks_delivery.py, docs/DOM_CHECKS.md; modificare
application/discovery.py, application/job_results.py, exporter.py, README/roadmap.
**Interfaces:** JSON dom_report + EvidenceRows URL/hash DOM, oggetto API separato e colonna finale DOM Report/dom_report.
- [ ] RED SQL/SDK worker/HTTP/workbook locale+server riaperti condividono dati, raw HTML/segreti assenti; snapshot/license/privacy gate regressioni.
- [ ] RED storico senza report -> unavailable; JSON/hash-row corrotto -> job_dom_report_invalid;20 URL Unicode lungo -> omitted_pages esplicito sotto24000 senza perdere lead.
- [ ] Run uv run --frozen --group test python -m unittest tests.test_dom_checks_delivery tests.test_audit_evidence_delivery tests.test_technology_reports tests.test_commercial_job_api tests.test_provenance_retention tests.test_spreadsheet_security -v; Expected RED poi PASS.
- [ ] Implementare JSON bounded e binding multipagina, no nuove tabelle; aggiornare manuale e PR14 merged f5c6c55/gate postmerge.
- [ ] Run suite completa PostgreSQL17/Chromium/distribuzione, lock/compile/diff/Gitleaks; Expected PASS senza skip.
- [ ] Commit feat: deliver traceable DOM measurements in reports; push e draft PR/attachment; task-done mirato.

## Autorevisione e handoff

Requisiti spec coperti1/2/3, nomi/signature coerenti, nove regole e tutte le cinque
classi Review Focus coperte. Reviewer finale fresco modello più capace, read-only;
unico eventuale fix pass Important/Critical TDD, Minor rinviati/ruling persistiti.
Gate GitHub sullo SHA finale, PR pronta. Cleanup scratch già rifiutato dalla policy:
non tentare di eliminare cartelle dei piani precedenti o aggirare il blocco.
