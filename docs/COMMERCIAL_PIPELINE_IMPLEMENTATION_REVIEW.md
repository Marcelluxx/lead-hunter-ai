# Pipeline commerciale — review e verifica

11 ottobre 2026. Base `1a8f0dc`, implementazione `2202a08`, PR #12 verso develop.
Revisore indipendente gpt-6-astra/high, contesto pulito e checkout read-only;
specifica, piano, intero diff e ruling esaminati. Il revisore ha eseguito 53 test
mirati PASS. Nessun rilascio in produzione o richiesta provider reale.

## Risultato della review e correzioni

Nessun Critical. Tre Important confermati con riproduzioni prima delle correzioni:

1. Worker perso dopo cancel: recupero escludeva le lease scadute con cancel flag;
   job running e prenotazione restavano bloccati. Ora il recupero consegna l'UUID
   e claim chiude cancellazione prima di accesso/provider; spesa consumata conservata,
   residuo liberato. Test RED→GREEN, anche app/worker PostgreSQL dopo logout.
2. Ripresa discovery: azzerava contatore/dedupe; un checkpoint già completo poteva
   acquistare nuove ricerche/audit e superare max_leads. Ora risultati e identificatori
   già commessi contano prima del primo provider. Test RED→GREEN per entrambe le
   modalità e batch cambiato dopo checkpoint parziale.
3. Privacy di job estranei: validava tutti i contatti workspace prima di filtrare
   quelli del report, producendo HTTP500 su report generici validi. Ora query e
   gate sono limitati agli ID lead richiesti; blocchi pertinenti diventano
   `403/job_contact_policy_denied`. Streaming si arresta al prossimo blocco.
   HTTP/XLSX riaperto e revoca fra blocchi: test RED→GREEN.

Un Minor confermato e rinviato alla fase correttezza funzionale: budget insufficiente
su resume restituisce HTTP500; rollback conserva correttamente stato cancellato e
contabilità. Serve risposta controllata409 come admission. Non è entrato nel pass
di correzione della review. Nessuna seconda review: correzioni verificate da TDD.

## Verifiche

Prima della review: suite318/318 PASS senza skip, CI38124486621 e
Security38124486623 PASS su `2202a08`. Chromium nell'immagine non-root effettiva,
esclusione materiali privati/issuer, volume privato leggibile/scrivibile dal worker,
roundtrip migrazioni PostgreSQL, Compose con segreti sintetici: PASS.

Dopo correzioni: suite325/325 PASS senza skip, inclusi PostgreSQL, Chromium e
distribuzione Docker; lock/compile/diff PASS. Gate esatto HEAD richiesto prima
di integrare. Nessun provider live, bundle proprietario inventato
o credenziale del proprietario utilizzata per le verifiche.

## Ruling sulle parti che il revisore ha lasciato fuori giudizio

- Tariffe effettive e riconciliazione fatture: manteniamo solo tetti conservativi,
  dichiarati come stime; fatturazione appartiene alla fase billing. Costo se errato:
  tetti operatore insufficienti possono sottostimare spesa provider.
- Credenziali, bundle privato e deployment produzione: nessun deployment eseguito;
  modulo mancante fallisce prima dell'AI. Costo se errato: setup reale richiede
  intervento operatore prima dell'uso commerciale.
- Qualità risposte live e adeguatezza modello: test SDK/trasporti sintetici; modello
  operatore e validazione qualità nella fase gold set. Costo se errato: drift API
  o modello può richiedere aggiornamento prima dell'uso live.
- Calibrazione audit, robots e limiti per dominio: restano fasi distinte già
  autorizzate; questa integrazione non è autorizzazione alla release clienti.
  Costo se errato: capacità/policy crawler non ancora verificate in produzione.
- Interni predecessore diagnostica: valutati nell'integrazione e già revisionati
  indipendentemente nel report dedicato. Costo se errato: eventuale gap precedente
  richiede regressione mirata successiva, senza duplicare review dell'intero modulo.

## Tutti i ruling del piano

Le righe seguenti preservano anche le decisioni storiche superate: l'assunzione
iniziale Docker non disponibile è stata corretta; RED/GREEN immagine è locale,
nessun commit CI deliberatamente rosso è stato necessario.
- Ruling: written spec/plan self-reviewed under explicit request to execute all autonomously — no repeated procedural approval pauses — cost if wrong: ordinary architecture choices may need revision.
- Task 1: Ruling: URL syntax would otherwise duplicate network policy normalization — extract pure validate_syntax into existing SafeUrlPolicy with distinct UrlSyntax type, keep all network checks in validate — cost if wrong: shared URL normalization regression; existing SSRF tests are the gate.
- Task 2: Ruling: preserve the general terminal state-machine contract — explicit resume is isolated in JobExecutionService and requires owner/session/grants, recoverable code, attempt ceiling and renewed remaining reservation — cost if wrong: future callers must use resume rather than ordinary transition.
- Task 2: Ruling: diagnostic sessions seal/export under VIEW as well as EXECUTE — require both at admission/worker preflight to avoid paid capture that cannot be delivered; built-in server role is admin, local grants unaffected — cost if wrong: server operators need a later permission-role extension for diagnostics.
- Task 2: Ruling: open a draft PR before handlers/API are complete — local PostgreSQL is unavailable and the mandatory CI service verifies migration/RLS/concurrency before Task2 completion — cost if wrong: extra CI runs and an explicitly unfinished draft.
- Task 3: Ruling: server cleaning runs sequentially with SDK retries disabled, 20s request timeout, 2000 output tokens and 200KB request ceiling — a callback that revokes/cancels must prevent sibling/hidden requests and bound operator cost assumptions — cost if wrong: lower throughput or oversized custom prompts rejected; local workflow retains concurrency.
- Task 3: Ruling: diagnostic checkpoint uses a UUID in lead_ids for the diagnostic kind, with expiry read from the bounded archive manifest — avoids a redundant artifact table and never stores a path or private payload in jobs — cost if wrong: kind-aware consumers required; crash before checkpoint can leave a private archive until TTL cleanup.
- Task 3: Ruling: worker composes crawler/auditor directly from encrypted workspace credentials and uses JobExecutionService origin context instead of the old helper/container globals — those existing local/legacy helpers cannot supply trusted sessions or workspace credentials — cost if wrong: two composition roots to maintain; protected checks remain shared.
- Task 4: Ruling: use durable queued/running jobs as the dispatch source and add a bounded 30s recovery service with Redis leader TTL — after_commit publication alone loses jobs on broker outage or process death; UUID redelivery is safe under leases — cost if wrong: extra idempotent queue messages and one required recovery service.
- Task 4: Ruling: shared private archive volume for API/worker/recovery, with periodic cleanup even for inactive workspace directories — transient container files cannot support delivery/retention — cost if wrong: deployment must secure and back up this dedicated volume separately.
- Task 4: Ruling: add actual Chromium launch gate for shipped worker image; local Docker unavailable, candidate CI is the failing-test environment before adding missing browser installation — worker fixtures/host Chromium cannot prove container readiness — cost if wrong: larger image/build and an intermediate draft CI failure.
- Task 4: correction to browser ruling: Docker engine29.8.2 is now available (read-only docker info), so the actual image RED/GREEN is run locally; no intentionally failing draft CI commit is necessary. Earlier availability assumption was unverified.
- Task 4: Ruling: reject a report/export snapshot if governed contacts change while it renders, and recheck grants/TTL before each 64KB chunk — stale prepared bytes cannot override a new opposition or revocation — cost if wrong: clients retry a changed report or receive a truncated download when access disappears after delivery began.
- Task 4: Ruling: choose the workspace-active lookup according to actual PostgreSQL function privilege, without granting worker enumeration to API — shared authorization now serves app and worker roles — cost if wrong: custom runtime roles must have one supported lookup; otherwise authorization fails closed.
- Task 4: Ruling: explicit worker prompt module and safe missing-bundle code — customer images intentionally exclude proprietary prompts, so deployment must mount the owner bundle through the existing public contract — cost if wrong: operator must supply compatible private bundle; no fabricated prompts or silent fallback.
- Task 4: Ruling: native whole-branch review follows the implementation completion ledger line, per executing-plans final-review flow — code/task verification is recorded first, review/CI still gate integration — cost if wrong: a corrective commit may be required before merge.
