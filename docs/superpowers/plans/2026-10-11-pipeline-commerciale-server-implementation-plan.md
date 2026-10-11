# Pipeline commerciale server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collegare job commerciali ai provider e agli audit con isolamento, budget e consegna autorizzata.
**Architecture:** Catalogo strict, guard per operazione, lease/checkpoint durevoli, handler che riusano i servizi, API risultato/export.
**Tech Stack:** Python 3.10–3.13, Pydantic, SQLAlchemy/Alembic/PostgreSQL, Dramatiq/Redis, licensing e servizi attuali.
**Spec:** docs/superpowers/specs/2026-10-11-pipeline-commerciale-server-design.md

## Global Constraints

- Queue soltanto UUID; credenziali risolte per workspace; autorità solo server.
- Input extra vietati, version 1, coordinate finite/zero valide, keyword 1–5 x 1–100.
- max_pages 1–20, max_leads 1–100 (20 default), lavoro audit <= 200 pagine.
- URL senza credenziali; validazione sintattica prima di effetti e rete distinta.
- Retention diagnostica 1–168 ore, default 24; MFA e grants per execution/view.
- Prezzi configurati lato server e tetti richieste; niente costo client autorevole.
- Tentativi <= 3, transazioni brevi, RLS e migrazione reversibile.

## Review Focus

1. Cancellazione/logout/revoca nel primo callback provider: nessun retry o chiamata successiva.
2. Redelivery simultanea e lease scaduta: nessuna doppia persistenza/spesa, nessun claim orfano.
3. Ripresa con nuova sessione: nessun recupero di autorità/parametri client contraffatti.
4. Workspace incrociato e licenza scaduta alla consegna: zero record/artefatti protetti.
5. Processo muore dopo autorizzazione richiesta ma prima del response: budget conservativo, checkpoint coerente.

### Task 1: Catalogo parametri e quote di lavoro

**Files:** creare src/domain/job_parameters.py, tests/test_job_parameters.py.
**Interfaces:** `parse_job_parameters(kind: str, parameters: dict) -> JobParameters`; immutable dataclass con kind, payload normalizzato, required_features; `JobParameterError.code`; payload version 1.

- [ ] Step 1: Test i quattro kind, normalizzazione unica keyword/URL, zero coordinate, limiti, input non finiti/bool/extra/provider/segreti, URL invalido prima effetti.
- [ ] Step 2: RED `python -m unittest tests.test_job_parameters -v`; Expected: modulo/interfaccia assente.
- [ ] Step 3: Implementare parser pure con Pydantic strict e URL syntax, nessuna risoluzione DNS o side effect.
- [ ] Step 4: GREEN stessi test e contratti discovery/rating; Expected: tutti PASS.
- [ ] Step 5: Commit/push catalogo parametri; Expected: diff verificato e nessun segreto.

### Task 2: Esecuzione durevole, guard e budget

**Files:** src/domain/jobs.py, src/application/jobs.py, src/application/budgets.py, src/infrastructure/models.py, nuova migration 0005_job_execution.py; creare src/application/job_execution.py, src/domain/job_pricing.py, tests/test_job_execution.py, tests/test_job_pricing.py, tests/integration/test_job_execution.py.
**Interfaces:** JobExecutionService claim/checkpoint/cancel/resume/finish; ExecutionGuard.require_execute()/before_provider_call(); catalogo quote lato server; colonne trusted session/lease/checkpoint e contabilità incrementale compatibile.

- [ ] Step 1: Test reali DB sessione/ruoli, lease/redelivery/retry/cancel/resume, spesa atomica e quote mancanti/client non autorevole.
- [ ] Step 2: RED test nuovi; Expected: servizi mancanti.
- [ ] Step 3: Implementare migration/servizi transazionali, limite tentativi3 e guard fresh, budget per tentativo provider. Conservare invarianti BudgetService esistenti.
- [ ] Step 4: GREEN unit, budget concorrente/PostgreSQL e roundtrip migration; Expected: isolamento e contabilità PASS.
- [ ] Step 5: Commit/push infrastruttura esecuzione verificata.

### Task 3: Handler e runtime worker

**Files:** creare src/workers/handlers.py, src/workers/job_runtime.py; modificare src/workers/broker.py, src/workers/feature_access.py, provider discovery, crawler/auditor/container; tests/test_commercial_worker.py, tests/test_worker_provider_guards.py.
**Interfaces:** handler registry.execute(parsed, guard, runtime), runtime credenziali workspace e persistenza; process_job carica UUID e usa servizi nuovi.

- [ ] Step 1: Test quattro handler con provider fixtures HTTP, audit SDK reale, revoca/cancel durante retry, risultati ammessi e contatti sotto policy, ripresa idempotente.
- [ ] Step 2: RED test nuovi; Expected: handler assenti/worker pipeline_not_configured.
- [ ] Step 3: Implementare handler, guard su tentativi esterni e callbacks, checkpoint/provenance, close risorse e codici safe; nessun raw payload in coda/DB.
- [ ] Step 4: GREEN flussi, contratti preesistenti e Chromium; Expected: PASS.
- [ ] Step 5: Commit/push worker commerciale.

### Task 4: API risultati, export, annullamento/ripresa

**Files:** src/web/routes/jobs.py, src/web/schemas.py, src/web/dependencies.py, configurazione runtime; creare src/application/job_results.py, tests/test_commercial_job_api.py; manuale worker/README/roadmap.
**Interfaces:** POST admission quote trusted; GET results, GET export, POST cancel/resume; corrente autorizzazione e grants, artifact path solo UUID generato server.

- [ ] Step 1: Test FastAPI reale da admission fino risultati, costi client ignorati, inter-workspace negato, licenze alla consegna e revoca durante rendering, archivi riaperti.
- [ ] Step 2: RED test nuovi; Expected: endpoint/servizi assenti.
- [ ] Step 3: Implementare API e autorizzazione fresca, report/provenance/privacy, inline stream protetto, manuale operativo e dipendenze esterne reali.
- [ ] Step 4: GREEN suite completa, PostgreSQL, lock/compile/diff/Gitleaks; Expected: PASS. Review indipendente fresca intero branch e un fix pass RED→GREEN.
- [ ] Step 5: Commit/push, PR/attach, CI/Security exact HEAD, integrare verde in develop. Proseguire correttezza funzionale.

Piano autorevisionato sotto delega autonoma. Task1 produce input normalizzati per
Task2/3/4; Task2 produce guard/claim per Task3 e controllo per Task4; Task3 persist
consumata da Task4. Interfacce coerenti, adattamenti concreti registrati nel ledger.
