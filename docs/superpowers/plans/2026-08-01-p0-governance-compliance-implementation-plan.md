# Lead Hunter V3 — Piano di implementazione della terza macrocategoria P0

> Stato: piano operativo autorizzato il 1 agosto 2026; implementazione non ancora autorizzata.
>
> Questo file e il design collegato devono restare locali e non tracciati. Non usare `git add .`; durante l'implementazione aggiungere allo staging soltanto i percorsi esplicitamente previsti dal commit corrente.

## 1. Obiettivo del branch

Risolvere, in ordine strutturale, i tre P0 ancora inclusi nella terza macrocategoria:

1. P0-07 — autenticazione, ruoli, workspace, segreti, job e controllo costi;
2. P0-04 — separazione di Google Places, provenienza, TTL, attribuzione e policy di export;
3. P0-05 — governance dei contatti, retention, suppression e diritti privacy.

Il branch preparera le fondazioni server necessarie senza tentare di completare nello stesso lavoro tutti gli elementi della roadmap commerciale.

## 2. Perimetro esplicito

### Incluso

- configurazione runtime iniettata, senza `sys.exit` durante l'import;
- API FastAPI autenticata;
- PostgreSQL e migrazioni Alembic;
- Redis e worker Dramatiq;
- autenticazione locale, MFA amministrativa e predisposizione OIDC;
- ruoli `admin`, `operator`, `viewer`;
- workspace isolati e difesa PostgreSQL RLS;
- segreti cifrati;
- job persistenti;
- budget e prenotazioni atomiche;
- audit log;
- `DiscoveryProvider` e adapter Google;
- provenienza campo per campo;
- blocco della persistenza/esportazione non autorizzata dei contenuti Google;
- contatti tipizzati;
- retention e suppression;
- test unitari, di integrazione e sicurezza;
- ambiente Docker Compose di sviluppo/verifica;
- aggiornamento dell'audit dopo la verifica.

### Escluso e rinviato a branch successivi

- control plane commerciale delle licenze;
- firma e distribuzione delle release;
- compilazione Nuitka;
- updater con rollback completo;
- runtime e SDK dei plugin;
- frontend dedicato che sostituisce Streamlit;
- Kubernetes;
- runtime LLM locale;
- billing e pagamenti;
- marketplace;
- invio automatico di campagne.

Streamlit restera una console interna/transitoria e non verra esposto come frontend pubblico.

## 3. Stack tecnico fissato per il branch

- Python 3.11 come runtime server iniziale, mantenendo i boundary test sulle versioni gia coperte dove compatibile;
- FastAPI per API e contratti OpenAPI;
- SQLAlchemy 2 in stile moderno;
- Alembic per migrazioni esplicite e revisionate;
- PostgreSQL per persistenza e Row-Level Security;
- Redis come broker e rate-limit backend;
- Dramatiq per i job asincroni;
- `pwdlib[argon2]` per password Argon2;
- PyJWT con chiavi asimmetriche per access token brevi;
- sessioni persistenti e revocabili associate al claim `sid`;
- Authlib per OIDC;
- TOTP per MFA amministrativa;
- `cryptography`/AES-GCM per envelope encryption dei segreti;
- Pydantic Settings per validazione della configurazione.

Le versioni verranno scelte entro intervalli compatibili e bloccate nel passaggio di riproducibilita previsto dalla roadmap. Non introdurre dipendenze non necessarie al P0.

## 4. Strategia Git

Branch previsto:

```text
codex/p0-governance-compliance
```

Base:

```text
develop @ f76be20
```

Sequenza dei commit:

1. `refactor(platform): inject runtime settings and provider dependencies`
2. `feat(p0-07): add authenticated workspace jobs and hard cost limits`
3. `fix(p0-04): isolate Places data behind compliant discovery boundaries`
4. `fix(p0-05): enforce contact provenance retention and suppression`
5. `test(platform): verify governance boundaries in CI and compose`
6. `docs(audit): record verified governance P0 resolutions`
7. eventuale `docs(graph): refresh governance architecture` dopo rigenerazione Graphify autorizzata/prevista dal flusso esistente.

I file locali sotto `docs/superpowers/` non devono comparire in alcun commit.

## 5. Gate iniziale

Prima di creare il branch:

1. verificare `develop...origin/develop`;
2. verificare che il worktree non contenga modifiche tracciate non correlate;
3. confermare che `docs/superpowers/` sia l'unica area non tracciata attesa;
4. eseguire la baseline:

```powershell
python -m compileall -q src tests main.py
python -m unittest discover -s tests -v
git diff --check
```

Se la baseline fallisce, fermarsi e distinguere regressioni preesistenti da problemi di ambiente prima di modificare codice.

## 6. Task 1 — Fondazione: configurazione e dependency injection

### Obiettivo

Rimuovere il blocco strutturale per cui `src/config.py` carica chiavi globali e termina il processo durante l'import. Rendere scraper, auditor e orchestratore costruibili con dipendenze esplicite e testabili.

### File da creare

- `src/settings.py`
- `src/application/__init__.py`
- `src/application/container.py`
- `src/providers/__init__.py`
- `tests/test_settings.py`
- `tests/test_dependency_injection.py`

### File da modificare

- `src/config.py`
- `src/scraper.py`
- `src/auditor.py`
- `main.py`
- `src/gui.py`
- `.env.example`

### Passi test-first

1. Scrivere un test che importi `src.config`, scraper e auditor senza API key e verifichi che l'import non termini il processo.
2. Scrivere un test che costruisca `ApplicationSettings` da un mapping esplicito e segnali insieme i campi mancanti al bootstrap, non all'import.
3. Scrivere un test che inietti provider fake in `LeadHunterOrchestrator` senza rete.
4. Eseguire i test e verificare il fallimento iniziale.
5. Separare costanti statiche e settings runtime.
6. Modificare `LeadScraper` e `LeadAuditor` affinche ricevano credenziali/configurazione nel costruttore.
7. Introdurre un application container minimale che costruisca dipendenze reali soltanto all'avvio CLI/GUI.
8. Mantenere compatibilita dei comandi esistenti passando il container dai punti di ingresso.

### Verifica

```powershell
python -m unittest tests.test_settings tests.test_dependency_injection -v
python -m unittest discover -s tests -v
python -m compileall -q src tests main.py
```

### Commit

```text
refactor(platform): inject runtime settings and provider dependencies
```

## 7. Task 2 — P0-07: persistenza, autenticazione e workspace

### Obiettivo

Creare il boundary server autenticato e persistente che impedisce accesso anonimo, commistione dei clienti e consumo incontrollato.

### File da creare

- `pyproject.toml` oppure sezione dipendenze server equivalente coerente con il repository
- `alembic.ini`
- `migrations/env.py`
- `migrations/script.py.mako`
- `migrations/versions/0001_platform_identity_workspace.py`
- `src/domain/identity.py`
- `src/domain/workspace.py`
- `src/domain/jobs.py`
- `src/domain/usage.py`
- `src/infrastructure/__init__.py`
- `src/infrastructure/database.py`
- `src/infrastructure/models.py`
- `src/infrastructure/repositories.py`
- `src/infrastructure/crypto.py`
- `src/infrastructure/redis.py`
- `src/application/authentication.py`
- `src/application/authorization.py`
- `src/application/workspaces.py`
- `src/application/jobs.py`
- `src/application/budgets.py`
- `src/application/audit_log.py`
- `src/web/__init__.py`
- `src/web/app.py`
- `src/web/dependencies.py`
- `src/web/schemas.py`
- `src/web/routes/auth.py`
- `src/web/routes/workspaces.py`
- `src/web/routes/jobs.py`
- `src/web/routes/usage.py`
- `src/workers/__init__.py`
- `src/workers/broker.py`
- `src/workers/jobs.py`
- `Dockerfile`
- `compose.yml`
- `tests/test_authentication.py`
- `tests/test_authorization.py`
- `tests/test_workspace_isolation.py`
- `tests/test_secret_encryption.py`
- `tests/test_budget_reservations.py`
- `tests/test_job_state_machine.py`
- `tests/test_audit_log.py`

### Modello iniziale

Tabelle minime:

- `users`;
- `user_identities`;
- `sessions`;
- `mfa_credentials`;
- `workspaces`;
- `workspace_memberships`;
- `provider_credentials`;
- `jobs`;
- `job_attempts`;
- `usage_budgets`;
- `usage_reservations`;
- `usage_ledger`;
- `audit_events`.

Tutte le tabelle di business devono avere UUID non prevedibili, timestamp UTC e vincoli espliciti. `jobs`, credenziali e ledger devono avere `workspace_id` non nullable.

### 7.1 Migrazione e RLS

1. Scrivere test di schema per chiavi esterne, unique constraint e check constraint.
2. Creare i modelli SQLAlchemy 2.
3. Scrivere manualmente e revisionare la migrazione Alembic; non accettare ciecamente l'autogenerate.
4. Attivare RLS sulle tabelle tenant-scoped.
5. Impostare `SET LOCAL app.workspace_id` all'inizio della transazione applicativa.
6. Usare per l'applicazione un ruolo PostgreSQL che non sia owner e non abbia `BYPASSRLS`.
7. Testare che una query senza contesto non restituisca righe e che un workspace non possa leggere o modificare l'altro.

### 7.2 Autenticazione locale

1. Hash password con Argon2 tramite `pwdlib`.
2. Messaggio di login uniforme e dummy hash per ridurre user enumeration/timing leak.
3. Access token breve firmato asimmetricamente con `sid`, `sub`, `iat`, `exp`, `iss`, `aud`.
4. Verifica server-side della sessione a ogni richiesta protetta per consentire revoca immediata.
5. Refresh token opaco, random, ruotato e memorizzato soltanto come hash.
6. Cookie `Secure`, `HttpOnly`, `SameSite=Lax` per il browser e protezione CSRF sulle operazioni mutative.
7. Rate limit su login, refresh e API costose.
8. Logout e revoca di tutte le sessioni dell'utente.

### 7.3 MFA e OIDC

1. MFA TOTP obbligatoria per `admin` prima delle azioni amministrative.
2. Secret TOTP cifrato e codici di recupero memorizzati come hash monouso.
3. OIDC tramite authorization-code flow con PKCE, discovery document, `state` e `nonce`.
4. Mapping esplicito dell'identita OIDC a un utente e membership locale; nessun ruolo amministrativo derivato implicitamente dall'email.
5. Account locale di emergenza creato tramite comando bootstrap, non tramite endpoint pubblico.

### 7.4 Autorizzazione

1. Definire matrice dei permessi per `admin`, `operator`, `viewer`.
2. Applicare dipendenze FastAPI di autorizzazione a ogni route.
3. Impedire al viewer avvio job, modifica policy, gestione segreti e override budget.
4. Registrare nell'audit log login, logout, ruoli, segreti, export e override.

### 7.5 Segreti

1. Richiedere una master key esterna al database.
2. Cifrare ogni credenziale con AES-GCM, nonce casuale e associated data composta da workspace/provider/versione schema.
3. Non restituire mai il valore tramite API dopo la scrittura.
4. Esporre soltanto stato, provider, ultimo aggiornamento e fingerprint non reversibile.
5. Testare alterazione del ciphertext, workspace mismatch e chiave errata.

### 7.6 Job asincroni

1. Persistenza dello stato `queued`, `validating`, `running`, `completed`, `partial`, `cancelled`, `failed`.
2. API crea il record e pubblica soltanto il suo UUID sulla coda.
3. Il worker ricarica configurazione e contesto dal database; nessun payload sensibile nel messaggio Redis.
4. Chiave di idempotenza per impedire doppio job involontario.
5. Tentativi separati con codici di errore stabili.
6. Retry solo per errori temporanei e con massimo esplicito.
7. Heartbeat/checkpoint per rilevare worker interrotti.

### 7.7 Budget

1. Prenotare il costo massimo stimato con transazione e lock della riga budget.
2. Rifiutare il job se la prenotazione supera il limite.
3. Avviso all'80% e hard stop al 100%.
4. Registrare provider, unita, costo stimato, costo reale e job.
5. Rilasciare il residuo al completamento/fallimento.
6. Rendere l'override atomico, amministrativo, motivato e auditato.
7. Test di concorrenza: due prenotazioni simultanee non devono superare il saldo.

### 7.8 Storage dei risultati

I percorsi non devono dipendere da nomi scelti dall'utente. Usare:

```text
storage/<workspace_uuid>/<job_uuid>/<artifact_uuid>
```

Validare il path risolto, applicare permessi minimi e verificare membership prima del download.

### Verifica P0-07

```powershell
python -m unittest tests.test_authentication tests.test_authorization -v
python -m unittest tests.test_workspace_isolation tests.test_secret_encryption -v
python -m unittest tests.test_budget_reservations tests.test_job_state_machine tests.test_audit_log -v
docker compose config
docker compose up -d postgres redis
alembic upgrade head
python -m unittest discover -s tests -v
```

### Criteri di accettazione P0-07

- nessuna route di prodotto e anonima;
- sessioni revocabili;
- admin con MFA;
- nessun dato leggibile tra workspace;
- segreti mai restituiti o loggati;
- due job concorrenti non superano il budget;
- worker e API condividono stato persistente;
- export e artifact richiedono membership;
- audit log copre tutte le azioni sensibili.

### Commit

```text
feat(p0-07): add authenticated workspace jobs and hard cost limits
```

## 8. Task 3 — P0-04: boundary Google Places e discovery provider

### Obiettivo

Impedire che il modello permanente e gli export siano copie del payload Google e rendere il prodotto indipendente dal provider.

### File da creare

- `src/domain/discovery.py`
- `src/domain/provenance.py`
- `src/providers/discovery/__init__.py`
- `src/providers/discovery/base.py`
- `src/providers/discovery/google_places.py`
- `src/application/discovery.py`
- `src/application/provenance.py`
- `src/application/export_policy.py`
- `src/application/retention.py`
- `migrations/versions/0002_discovery_provenance.py`
- `tests/test_discovery_provider_contract.py`
- `tests/test_google_places_boundary.py`
- `tests/test_provenance.py`
- `tests/test_export_policy.py`
- `tests/test_provider_retention.py`
- `tests/test_google_attribution.py`

### File da modificare

- `src/scraper.py`
- `src/config.py`
- `main.py`
- `src/gui.py`
- `src/exporter.py`
- `src/infrastructure/models.py`
- `src/workers/jobs.py`

### 8.1 Contratto provider

Il contratto espone candidati transitori e riferimenti, non dizionari Places permanenti.

Tipi minimi:

- `DiscoveryQuery`;
- `CandidateReference`;
- `TransientCandidate`;
- `ProviderAttribution`;
- `ProviderRetentionRule`;
- `DiscoveryProvider`.

Ogni adapter deve superare lo stesso contract test per timeout, errori, deduplica, attribution e assenza di segreti.

### 8.2 Adapter Google

1. Spostare le chiamate da `LeadScraper` all'adapter.
2. Ridurre il field mask ai campi strettamente necessari; rimuovere recensioni.
3. Mantenere la risposta completa soltanto nella memoria del worker.
4. Persistire soltanto il riferimento consentito e i metadati di acquisizione ammessi.
5. Non inviare il payload Google a log, code, LLM o audit.
6. Imporre timeout, retry limit e classificazione degli errori.
7. Restituire attribution strutturata alla UI quando il contenuto viene mostrato live.

### 8.3 Provenienza

Aggiungere modelli per:

- `leads`;
- `lead_attributes`;
- `evidence`;
- `provider_references`;
- `retention_events`.

Ogni attributo contiene tipo, valore, fonte, URL/evidenza, `collected_at`, confidence, scadenza e classificazione.

### 8.4 Re-verifica dal sito

Per il flusso `with_website`, il crawler deve estrarre dal sito ufficiale gli attributi permanenti necessari e collegarli a evidenze indipendenti. Non copiare il valore Google cambiando soltanto l'etichetta della fonte.

In assenza di verifica indipendente, il dato rimane transitorio e non entra nel report persistente.

### 8.5 Impatto sulla modalita `no_website`

Con Google come provider, i risultati `no_website` non possono diventare automaticamente un database Excel permanente contenente il payload Places.

Nel P0 adottare il comportamento fail-closed:

- consultazione transitoria con attribution, se consentita;
- export bloccato per i campi Google non autorizzati;
- eventuale export limitato a riferimenti consentiti e metadati propri;
- messaggio esplicito che richiede un provider con diritti di rivendita/persistenza per il report completo.

Non aggirare questa limitazione copiando i dati in un altro modello.

### 8.6 Mappa e attribution

La mappa Folium deve essere soltanto un selettore indipendente del centro di ricerca e non deve mostrare contenuti Places o essere presentata come una visualizzazione dei risultati Google.

Quando vengono mostrati dati Google live:

- separare visivamente la sezione dalla mappa;
- mostrare attribution richiesta;
- non incorporare foto/recensioni;
- includere link e avvisi previsti dalla policy applicabile.

Terms e Privacy Policy del deployment verranno esposte tramite route/configurazione, ma i testi legali definitivi richiedono revisione professionale.

### 8.7 TTL

1. Nessun record per il payload completo.
2. Coordinate Google con `expires_at` non oltre 30 giorni.
3. Job periodico idempotente elimina campi scaduti e registra soltanto il conteggio dell'operazione.
4. `place_id`/riferimento conserva `last_verified_at` e richiede refresh dopo il periodo configurato.

### Verifica P0-04

```powershell
python -m unittest tests.test_discovery_provider_contract tests.test_google_places_boundary -v
python -m unittest tests.test_provenance tests.test_export_policy tests.test_provider_retention -v
python -m unittest tests.test_google_attribution -v
python -m unittest discover -s tests -v
```

### Criteri di accettazione P0-04

- nessun JSON Places nel database, code, log o report;
- recensioni rimosse dal field mask;
- nessun campo Google non autorizzato nell'Excel;
- mappa non associata ai risultati Places;
- attribution presente quando necessaria;
- provider sostituibile con un fake tramite contract test;
- TTL applicato e auditato;
- la rimozione/disattivazione dell'adapter Google non rompe crawler e report basati su dati indipendenti.

### Commit

```text
fix(p0-04): isolate Places data behind compliant discovery boundaries
```

## 9. Task 4 — P0-05: contatti, retention e suppression

### Obiettivo

Trasformare le email da semplici stringhe estratte in contatti governati, con fonte, classificazione, scadenza e blocco della riacquisizione/esportazione.

### File da creare

- `src/domain/contacts.py`
- `src/domain/privacy.py`
- `src/application/contacts.py`
- `src/application/privacy_policy.py`
- `src/application/suppression.py`
- `src/application/data_subject_requests.py`
- `src/workers/retention.py`
- `src/web/routes/privacy.py`
- `migrations/versions/0003_contact_privacy_governance.py`
- `tests/test_contact_classification.py`
- `tests/test_contact_provenance.py`
- `tests/test_privacy_policy_gate.py`
- `tests/test_suppression.py`
- `tests/test_retention_worker.py`
- `tests/test_privacy_export_gate.py`
- `tests/test_data_subject_requests.py`

### File da modificare

- `src/domain/crawl.py`
- `src/crawler.py`
- `main.py`
- `src/exporter.py`
- `src/infrastructure/models.py`
- `src/web/app.py`
- `src/workers/jobs.py`
- `.env.example`

### 9.1 Contatti tipizzati

Sostituire `List[str]` con un DTO che includa:

- tipo;
- valore normalizzato;
- valore di presentazione;
- fonte URL;
- timestamp;
- metodo di estrazione;
- confidence;
- `generic_business` oppure `named_professional`;
- `expires_at`;
- evidence hash/riferimento.

La classificazione usa regole versionate e testate per local-part generici (`info`, `commerciale`, `sales`, ecc.). I casi ambigui vanno classificati in modo prudente come nominativi.

### 9.2 Policy workspace

Per abilitare i contatti nominativi sono obbligatori:

- finalita;
- base giuridica dichiarata dal titolare;
- referente privacy;
- mercato Italia/UE;
- retention non superiore a 90 giorni.

Senza policy completa, i contatti nominativi non vengono persistiti o esportati. I contatti generici hanno default 12 mesi.

### 9.3 Suppression

1. Normalizzare email e telefono.
2. Calcolare un identificatore HMAC con chiave separata, non un semplice SHA enumerabile.
3. Controllare suppression globale e workspace prima di persistenza, arricchimento ed export.
4. Salvare il minimo necessario: fingerprint, tipo, scope, motivo, timestamp e audit metadata.
5. Non esporre la lista completa a operator/viewer.
6. Rendere idempotenti inserimento e richiesta di cancellazione.

### 9.4 Retention

Applicare i default approvati:

- HTML completo: 7 giorni;
- screenshot intermedi: 30 giorni;
- contatto nominativo: 90 giorni;
- contatto generico: 12 mesi;
- report/evidenza selezionata: 12 mesi;
- log operativo: 30 giorni;
- audit log minimale: 12 mesi.

Il worker di retention deve:

- elaborare batch limitati;
- essere riavviabile;
- non inserire PII nei log;
- rispettare legal hold espliciti e autorizzati, se introdotti;
- registrare conteggi per categoria e workspace;
- cancellare artefatti soltanto entro root risolte e validate.

### 9.5 Export

Prima dell'export:

1. verificare ruolo e membership;
2. verificare policy del workspace;
3. rimuovere dati scaduti;
4. applicare suppression;
5. applicare policy del provider;
6. includere provenienza e timestamp;
7. registrare utente, workspace, job, numero di record e policy version.

Il prodotto continua a poter generare suggerimenti commerciali, ma non invia email e non fornisce automazione di campagna.

### 9.6 Diritti dell'interessato

Implementare casi d'uso amministrativi per:

- ricerca controllata del dato;
- esportazione dei dati riferibili al soggetto;
- rettifica;
- cancellazione;
- inserimento in suppression globale o workspace;
- audit della richiesta senza ricreare il dato eliminato.

### Verifica P0-05

```powershell
python -m unittest tests.test_contact_classification tests.test_contact_provenance -v
python -m unittest tests.test_privacy_policy_gate tests.test_suppression -v
python -m unittest tests.test_retention_worker tests.test_privacy_export_gate -v
python -m unittest tests.test_data_subject_requests -v
python -m unittest discover -s tests -v
```

### Criteri di accettazione P0-05

- ogni contatto ha fonte e timestamp;
- contatti nominativi senza policy non vengono conservati/esportati;
- retention 90 giorni/12 mesi applicata;
- suppression blocca riacquisizione ed export;
- nessun invio automatico;
- richieste privacy idempotenti e auditabili;
- nessuna PII nei log del worker di retention.

### Commit

```text
fix(p0-05): enforce contact provenance retention and suppression
```

## 10. Task 5 — Hardening, Compose e CI

### Obiettivo

Verificare i tre P0 come sistema, non soltanto come unita isolate.

### File da creare/modificare

- `.github/workflows/ci.yml`
- `compose.yml`
- `Dockerfile`
- `tests/integration/test_postgres_rls.py`
- `tests/integration/test_budget_concurrency.py`
- `tests/integration/test_job_recovery.py`
- `tests/integration/test_retention_database.py`
- `tests/e2e/test_api_job_flow.py`
- `README.md`
- `.env.example`

### Passi

1. Aggiungere PostgreSQL e Redis come service container in CI per il job integration.
2. Conservare i security boundary test esistenti.
3. Aggiungere compile, unit, integration, migration check e Docker build.
4. Eseguire `alembic upgrade head` su database vuoto.
5. Eseguire upgrade dalla revisione precedente supportata.
6. Verificare che la nuova app possa fare rollback applicativo senza downgrade distruttivo del database; preferire migrazioni additive/expand-contract.
7. Testare perdita e ritorno di Redis durante un job.
8. Testare riavvio del worker e recupero dei job orfani.
9. Testare due workspace attraverso l'intero flusso API-worker-database-export.
10. Verificare che immagini e log non contengano `.env`, token o payload provider.

### Comandi

```powershell
docker compose build
docker compose up -d postgres redis
alembic upgrade head
python -m unittest discover -s tests -v
python -m compileall -q src tests main.py
git diff --check
```

Eseguire inoltre smoke test HTTP su:

- `/health/live`;
- `/health/ready`;
- login + MFA;
- creazione workspace;
- creazione job;
- polling stato;
- export autorizzato;
- export negato cross-workspace;
- revoca sessione.

### Commit

```text
test(platform): verify governance boundaries in CI and compose
```

## 11. Task 6 — Audit e grafo

### Audit

Aggiornare `docs/AUDIT_PRODOTTO_E_ROADMAP_STATO_DELL_ARTE.md` soltanto dopo il superamento dei criteri di accettazione.

Per ciascun P0 indicare:

- stato;
- branch e commit;
- file principali;
- test;
- limiti residui;
- requisiti legali non risolvibili soltanto nel codice.

Commit:

```text
docs(audit): record verified governance P0 resolutions
```

### Graphify

Dopo le modifiche strutturali, rigenerare il grafo e verificare che rappresenti:

- API;
- domain/application/infrastructure;
- worker e queue;
- persistenza;
- discovery provider;
- privacy e retention.

Non includere nel grafo chiavi, `.env`, database locali, artifact o documenti locali esclusi.

Commit separato:

```text
docs(graph): refresh governance architecture
```

## 12. Review prima del merge

### Sicurezza

- auth bypass;
- IDOR/cross-workspace;
- RLS fail-open;
- CSRF/session fixation;
- refresh token reuse;
- MFA recovery;
- secret leakage;
- Redis payload leakage;
- export policy bypass;
- suppression enumeration;
- path traversal;
- retry che duplica costi.

### Dati

- migrazioni reversibili o compatibili con rollback applicativo;
- UTC coerente;
- vincoli database;
- provenance obbligatoria;
- TTL;
- cancellazione nei batch;
- artifact orfani;
- backup e restore.

### Prodotto

- Streamlit chiaramente marcato come console interna;
- messaggi comprensibili per export bloccati;
- admin in grado di configurare provider, policy e budget;
- viewer realmente read-only;
- audit consultabile senza PII superflua.

## 13. Gate di merge in `develop`

Il branch puo essere proposto per il merge soltanto se:

1. tutti i test unitari e di integrazione passano;
2. Docker Compose parte da zero;
3. le migrazioni funzionano su database vuoto e upgrade;
4. i tre criteri P0 sono verificati;
5. nessun segreto compare in Git, immagini o log;
6. `git diff --check` e pulito;
7. audit e grafo corrispondono al codice;
8. il documento locale di design e questo piano non sono staged;
9. viene effettuata una review finale del diff;
10. l'utente autorizza merge e push.

## 14. Principali rischi di esecuzione

### Ampiezza del P0-07

E il cambiamento maggiore. Va mantenuto in un solo commit P0 tematico come richiesto, ma sviluppato internamente per slice testabili e con checkpoint locali prima del commit.

### Compatibilita Streamlit

La GUI attuale esegue la pipeline in-process. Durante il branch va mantenuta come console interna compatibile oppure adattata a chiamare i nuovi servizi, senza usarla come boundary di sicurezza pubblico.

### Modalita `no_website`

Il nuovo confine Google riduce intenzionalmente gli export possibili. Questo non e un bug: e un comportamento fail-closed finche non esiste un provider con diritti contrattuali adeguati.

### RLS e ruoli database

RLS non protegge se l'applicazione usa il proprietario delle tabelle o un ruolo con bypass. I test devono usare lo stesso ruolo operativo del deployment.

### Retry e costi

Le code possono consegnare nuovamente un messaggio. Idempotenza e ledger database sono obbligatori; Redis non e il sistema di record finanziario.

## 15. Punti di arresto obbligatori

Fermarsi e chiedere indicazioni se:

- emergono modifiche tracciate dell'utente sovrapposte ai file del task;
- una policy Google aggiornata rende il caso d'uso non praticabile anche in forma transitoria;
- l'implementazione richiede una scelta commerciale non gia approvata;
- una migrazione rischia perdita di dati;
- non e possibile ottenere isolamento RLS con il deployment scelto;
- un test di sicurezza fallisce ripetutamente senza causa compresa;
- servono credenziali o accessi esterni non disponibili.

## 16. Riferimenti tecnici primari

- FastAPI security e OpenID Connect: <https://fastapi.tiangolo.com/tutorial/security/>
- FastAPI, password Argon2 e token: <https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/>
- SQLAlchemy 2 ORM: <https://docs.sqlalchemy.org/en/20/orm/>
- SQLAlchemy sessioni e transazioni: <https://docs.sqlalchemy.org/en/20/orm/session.html>
- Alembic: <https://alembic.sqlalchemy.org/en/latest/>
- PostgreSQL Row Security: <https://www.postgresql.org/docs/current/ddl-rowsecurity.html>
- Dramatiq e Redis: <https://dramatiq.io/guide.html>

## 17. Prossimo passo

Prima di creare il branch o modificare codice, presentare all'utente un riepilogo breve:

- creazione di `codex/p0-governance-compliance` da `develop`;
- prima modifica limitata alla dependency injection/configurazione;
- test previsti;
- assenza di commit dei documenti locali;
- richiesta di autorizzazione esplicita all'implementazione.
