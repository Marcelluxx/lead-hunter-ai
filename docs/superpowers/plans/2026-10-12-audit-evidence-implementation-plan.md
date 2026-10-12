# Audit evidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans, native sotto delega autonoma. Test mirati per task; suite completa finale prima di review/commit finale.

**Goal:** Citazioni verificabili contro crawl originale, report pubblico compatibile e persistito.
**Architecture:** Contratto puro AuditEvidenceSet; LeadAuditor integra catalogo originale senza nuove chiamate; builder ricontrolla prima di SQL/export. JSON bounded nella tabella attributi esistente.
**Tech Stack:** Python3.10–3.13, dataclass, SHA256, SDK OpenAI già presente, SQLAlchemy/PostgreSQL17, openpyxl.
**Spec:** docs/superpowers/specs/2026-10-12-audit-evidence-design.md

## Global Constraints

- Schema supplementare1, max20 pagine/findings, max3 citazioni/finding, quote20–500, description1–1000.
- Catalogo massimo12000 caratteri di contenuto,5000/pagina; report UTF8<=24000 byte.
- Citazione matched non dimostra diagnosi: finding sempre inconclusive/llm_observation.
- Nessuna nuova dipendenza/provider/chiamata o pubblicazione prompt proprietari.
- Colonne/campi DTO append-only; gate licenze/privacy/workspace/retention invariati.
- Esecuzione autonoma autorizzata: autorevisione spec/piano, native; nessun merge di questa nuova PR senza richiesta successiva.

## Review Focus

- Unicode/normalizzazione può far citare testo differente dall'originale: confronto esatto e quote hash originali (Task1).
- Testo oltre catalogo o ID di altra pagina: nessuna citazione fuori evidenza proposta (Task1).
- Modello dichiara verified/source/hash o echo di dati privati: autorità ignorata tramite rifiuto, proiezione redatta (Task1/2).
- Crawl/report mutato dopo audit: builder ricontrolla hash/offset/proiezione (Task3).
- Storico legacy o attributo SQL corrotto: stato legacy esplicito o errore sicuro, nessuna prova creata (Task3).

## Mappa file

Creare src/domain/audit_evidence.py (contratto/validazione), src/application/audit_evidence.py
(binding al CrawlResult); modificare auditor.py (runtime), domain/provenance.py,
application/provenance.py, application/discovery.py, application/job_results.py,
exporter.py (consegna). Test tre moduli audit_evidence, audit_evidence_runtime,
audit_evidence_delivery. Manuale dedicato e roadmap nella Task3.

### Task 1: contratto e catalogo originale

**Files:** creare src/domain/audit_evidence.py, tests/test_audit_evidence.py.
**Interfaces:** produce AuditEvidenceSet.from_pages(pages, *, collected_at=None), .to_prompt_payload()->str,
.validate_findings(payload:Mapping)->dict, .verify_report(report:Mapping)->dict.
- [ ] RED: citazione reale multipagina/Unicode -> matched con hash/offset corretti, finding inconclusive; legacy -> legacy_uncited.
- [ ] RED: ID sconosciuto, quote falsa/fuori catalogo, campi autorità, duplicati,20/21 findings, quote19/501, description1001, tipi errati -> AuditValidationError senza contenuti.
- [ ] RED: redazione email/telefono/segreti/query, assenza fulltext/prompt, byte24000; report alterato -> rifiuto.
- [ ] Run: uv run --frozen --group test python -m unittest tests.test_audit_evidence -v. Expected FAIL prima, PASS dopo.
- [ ] Implementare contratto puro secondo spec e limite payload; nessuna rete.
- [ ] Commit feat: validate audit citations against original crawl evidence, Gitleaks staged; task-done stesso comando.

### Task 2: integrazione auditor e compatibilità privata

**Files:** modificare src/auditor.py, creare tests/test_audit_evidence_runtime.py.
**Interfaces:** consuma Task1; produce audit_website dict cinque campi legacy + audit_report.
- [ ] RED trasporto SDK reale: cleaning inventa parole, audit cita originali -> matched; falso quoting -> retry e failed locale/errore server.
- [ ] RED messaggi contengono catalogo anti-injection; modello tenta verified/private -> rifiuto; vecchio output -> legacy_uncited; fallimento -> scoreNone/failed.
- [ ] Run: uv run --frozen --group test python -m unittest tests.test_audit_evidence_runtime tests.test_diagnostic_runtime tests.test_worker_provider_guards tests.test_audit_contract -v. Expected RED poi PASS.
- [ ] Integrare contratto pubblico supplementare e validare prima del ritorno senza cambiare prompt provider privato o chiamate cleaning esistenti.
- [ ] Commit feat: return cited audit observations with explicit uncertainty; task-done stesso comando.

### Task 3: binding, persistenza e consegna

**Files:** creare src/application/audit_evidence.py/tests/test_audit_evidence_delivery.py,
modificare src/domain/provenance.py, src/application/provenance.py,
src/application/discovery.py, src/application/job_results.py, src/exporter.py,
docs/AUDIT_EVIDENCE.md, docs/MODERNIZZAZIONE_AUTONOMA.md, README.md.
**Interfaces:** consuma verify_report Task1 e dict Task2; produce bind_audit_report(crawl, report)->dict,
VerifiedLead.audit_report append-only; JSON pubblico SQL/API/XLSX.
- [ ] RED builder con timestamp PageEvidence/hash coerenti; quote/hash/offset alterati e crawl mutato rifiutati; legacy record compatibile.
- [ ] RED HTTP worker -> SQL -> risultati/XLSX locali e server riaperti con stesso report e nessun prompt/fulltext/contatto non governato; JSON SQL invalido -> errore sicuro.
- [ ] Run: uv run --frozen --group test python -m unittest tests.test_audit_evidence_delivery tests.test_technology_reports tests.test_commercial_job_api tests.test_provenance_retention tests.test_spreadsheet_security -v. Expected RED poi PASS.
- [ ] Implementare binding e JSON canonical bounded, allowlist server/proiezione, colonna finale, aggiornare manuale/roadmap PR13 merged e prima qualità audit.
- [ ] Run suite completa con PostgreSQL17/Chromium/distribuzione, lock/compile/diff/Gitleaks. Expected PASS senza skip.
- [ ] Commit feat: persist and export traceable audit findings; push branch, draft PR e attachment; task-done mirato.

## Handoff

Autorevisione: requisiti spec coperti da1/2/3, firme coerenti, privacy/injection/limiti
coperti. Una review fresca intero branch (modello più capace) dopo tre task. Unico
fix pass Important/Critical TDD; Minor rinviati e ruling persistiti. Commit/push
finale e gate esatto HEAD; consegna PR pronta senza merge automatico.
