# Expiring Modular Feature Licenses Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consentire al proprietario di emettere licenze firmate a scadenza per singole funzioni, con lo stesso controllo applicativo in locale e sul server.

**Architecture:** Dominio e catalogo comuni; firma Ed25519 separata dal login; storage locale atomico oppure PostgreSQL con RLS. Un servizio comune combina licenza, destinatario, tempo, disponibilità del modulo e autorizzazioni server. Lo strumento emittente è escluso dalla distribuzione cliente.

**Tech Stack:** Python 3.10–3.13, PyJWT/cryptography già presenti, unittest, FastAPI, SQLAlchemy 2/Alembic, PostgreSQL 17, Streamlit; locking locale tramite libreria standard.

**Spec:** [Specifica approvata il 9 ottobre 2026](../specs/2026-10-08-autorizzazioni-modulari-a-scadenza-design.md).

Stato del piano: approvato il 9 ottobre 2026; nove task implementati con esecuzione native sul branch
`codex/expiring-feature-licenses`, con commit/push dei blocchi principali e review indipendente finale.

Risultati nel [resoconto di implementazione](../../FEATURE_LICENSES_IMPLEMENTATION_REVIEW.md):
158 test passati senza skip, revisione indipendente corretta con regressioni,
gate funzionali CI passati. Release commerciale bloccata dal gate Security per
NLTK senza patch pubblicata; la checklist completata non implica readiness commerciale.

## Global Constraints

- `version = 1`; `typ = LH-FEATURE-LICENSE`; algoritmo consentito esclusivamente `EdDSA` con chiave Ed25519.
- Audience esatta `lead-hunter-feature-licenses`; token massimo 16 KiB; header ammessi esattamente `typ`, `alg`, `kid`.
- Claim richiesti: `version`, `iss`, `aud`, `jti`, `iat`, `nbf`, `exp`, `installation_id`, `subject_kind`, `sub`, `features`; `workspace_id` solo per `workspace_user`.
- Date Unix UTC intere; rifiutare booleani/float/stringhe, chiavi JSON duplicate, campi inattesi; `iat <= nbf < exp`; validità `nbf <= now < exp`.
- Identificatori: `export.no_website`, `discovery.rating_filters`, `diagnostics.full`; niente wildcard; tutti pianificati fino ai successivi recuperi.
- Tutti gli accessi aggiuntivi hanno scadenza, anche nell'installazione del proprietario; le funzioni base perpetue rimangono operative.
- Clock regression oltre cinque minuti: `license_clock_regression`; entro cinque minuti usare il massimo già osservato.
- Console locale solo loopback; utenti remoti usano API autenticata e concessioni per utente/workspace.
- Chiavi firma licensing separate dal login; chiave privata cifrata, passphrase interattiva; mai token completi/chiavi private nei log o nelle risposte API.
- Una concessione attiva per destinatario; rinnovo sostitutivo e atomico, mai unione dei permessi; una `jti` revocata non viene riattivata.
- Preserve `ExportPolicy`, DTO pubblico AI, SSRF, privacy, budget e messaggi coda solo UUID. Il worker commerciale rimane `pipeline_not_configured` in questo piano.
- Nessun servizio centrale, pagamento, plugin SDK o recupero funzionale dei tre moduli in questo primo blocco.
- Usare dipendenze esistenti; nessuna modifica al lockfile senza necessità verificata. Nessuna rete/provider nei test delle licenze.

## Review Focus

1. Un backup ripristinato con lo stesso stato conserva l'identità; una nuova installazione non accetta la vecchia licenza — Task 3.
2. Una chiamata protetta conclusa dopo la scadenza non consegna materiale riservato; una lettura dello stato/base continua a funzionare — Task 5.
3. Due rinnovi concorrenti, oppure revoca concorrente al rinnovo, producono una sola concessione attiva e non perdono le revoche — Task 4.
4. Un modulo pianificato con licenza valida viene descritto come autorizzato ma indisponibile, senza attivare pulsanti/operazioni — Task 1 e Task 8.
5. Un utente disattivato/rimosso dal workspace perde accesso; un `subject_kind=installation` non abilita gli account server — Task 5 e Task 7.

## 0. Preparazione all'esecuzione e mappa dei file

Eseguire questa sezione soltanto dopo approvazione del piano e scelta del metodo.

La base tecnica analizzata è `19c2730`; specifica e nota sono nel commit locale
`aafb42b` sul branch documentale `codex/docs-expiring-feature-licenses`. Al momento
del piano `origin/develop` e questa base hanno codice identico: il delta è solo
documentazione. Verificarlo nuovamente all'esecuzione, senza presumere che persista.

- [ ] Con la skill using-git-worktrees, riutilizzare un worktree adatto o creare isolamento per `codex/expiring-feature-licenses` dalla baseline verificata. Portare specifica/piano approvati nel checkout tramite commit documentali selezionati, senza copiare segreti o altri file locali. Il futuro PR resta destinato a `develop`.
- [ ] Verificare stato Git e confronto con `origin/develop`; se sono intervenuti cambiamenti tecnici, rileggere soltanto le interfacce interessate e adeguare il piano prima del codice.
- [ ] Controllare il runtime `uv` richiesto da `pyproject.toml`; sincronizzare l'ambiente dal lockfile soltanto in fase di esecuzione.
- [ ] Eseguire `uv run --frozen --group test python -m unittest discover -s tests -v`, `uv lock --check` e `git diff --check`. Registrare separatamente gli skip PostgreSQL. Se la baseline fallisce, classificare ambiente o regressione prima di procedere.

| Area/file | Responsabilità | Task |
|---|---|---|
| `src/domain/feature_licenses.py` | Contratti immutabili, errori e destinatario | 1 |
| `src/licensing/catalog.py`, `src/licensing/__init__.py` | Catalogo e metadata pubblici | 1 |
| `src/licensing/verification.py`, `src/licensing/trust.py` | Parsing rigoroso, firme, chiavi pubbliche fidate | 2 |
| `src/infrastructure/license_local_store.py`, `src/infrastructure/file_lock.py` | Stato locale atomico e lock multiprocesso | 3 |
| `src/application/license_clock.py`, `src/application/feature_licenses.py` | Tempo persistente, import/revoke/status comuni | 3 |
| `src/infrastructure/license_models.py`, `src/infrastructure/license_repository.py` | Tabelle e repository SQL | 4 |
| `migrations/versions/0004_feature_licenses.py`, `migrations/env.py`, `src/infrastructure/models.py` | Registrazione metadata e migrazione | 4 |
| `src/application/feature_access.py`, `src/application/managed_licenses.py`, `src/workers/feature_access.py` | Accesso comune, gestione server, contesto job | 5 |
| `src/application/audit_log.py` | Metadata licensing consentiti | 5 |
| `tools/license_issuer/{__init__,keys,issuance,__main__}.py` | Strumento del proprietario | 6 |
| `src/licensing/settings.py`, `src/web/routes/feature_licenses.py` | Configurazione pubblica e API | 7 |
| `src/web/{schemas,dependencies,app,settings}.py`, `src/server.py`, `compose.yml`, `.env.example` | Wiring runtime compatibile | 7 |
| `src/cli/feature_licenses.py`, `src/ui/feature_license_panel.py`, `src/ui/__init__.py`, `.streamlit/config.toml` | CLI e pannello console locale, binding loopback | 8 |
| `src/application/container.py`, `src/gui.py`, `main.py` | Wiring locale e launch loopback | 8 |
| `.dockerignore`, `.gitignore`, `README.md`, `docs/RELEASE_GATES.md`, `.github/workflows/ci.yml` | Distribuzione, manuale e gate | 9 |
| `tests/license_helpers.py` e test indicati sotto | Fixture effimere, unità e integrazioni | 1–9 |

I test nuovi usano unittest, come il repository. Non modificare i moduli di
dominio/export/crawl non elencati. L'integrazione del worker commerciale è un
contratto aggiuntivo testabile, non un handler fittizio che finge di eseguire un audit.

## Task 1: contratti e catalogo delle funzioni

**Files:** Create `src/domain/feature_licenses.py`, `src/licensing/__init__.py`, `src/licensing/catalog.py`, `tests/license_helpers.py`, `tests/test_feature_license_contract.py`.

**Interfaces:**

- `SubjectKind`: `installation`, `workspace_user`; `FeatureAction`: `execute`, `view`.
- `LicenseScope(installation_id: UUID, subject_kind: SubjectKind, subject_id: UUID, workspace_id: UUID | None)` frozen; local scope richiede subject_id uguale a installation_id e workspace_id assente.
- `LicenseClaims(version: int, issuer: str, audience: str, license_id: UUID, issued_at: int, not_before: int, expires_at: int, scope: LicenseScope, features: tuple[str, ...])` frozen.
- `LicenseError(code: str)` per i codici della specifica, con messaggio redatto; nessun token nella rappresentazione.
- `StoredGrant(token: str, license_id: UUID, revoked: bool)` con token escluso da repr; `LicenseSummary(license_id: UUID | None, scope: LicenseScope, license_status: str, not_before: int | None, expires_at: int | None, features: tuple[str, ...])` senza token.
- `FeatureDefinition(feature_id: str, label: str, module_status: str, execute_permissions: tuple[Permission, ...], view_permissions: tuple[Permission, ...], execute_mfa: bool, view_mfa: bool)`; `FeatureCatalog.get(feature_id: str) -> FeatureDefinition`, `.all() -> tuple[FeatureDefinition, ...]`.
- `FeatureContext(scope: LicenseScope, permissions: frozenset[Permission], mfa_verified: bool, principal_active: bool)`; `FeatureStatus(feature_id: str, label: str, granted: bool, module_status: str, license_status: str, expires_at: int | None)`.
- Fixture `license_claims(*, scope: LicenseScope | None = None, issued_at: int = 0, not_before: int = 0, expires_at: int = 100, features: tuple[str, ...] = ("diagnostics.full",)) -> LicenseClaims`; `local_scope()` e `managed_scope()` restituiscono UUID distinti e stabili soltanto nei test.

- [x] **Step 1: scrivere `test_catalog_declares_three_planned_features` e `test_scope_and_claim_types_are_strict`** con subTest e valori espliciti:

```python
catalog = FeatureCatalog()
self.assertEqual({x.feature_id for x in catalog.all()},
    {"export.no_website", "discovery.rating_filters", "diagnostics.full"})
self.assertTrue(all(x.module_status == "planned" for x in catalog.all()))
diag = catalog.get("diagnostics.full")
self.assertEqual(diag.execute_permissions, (Permission.START_JOB,))
self.assertEqual(diag.view_permissions, (Permission.VIEW_AUDIT_LOG,))
self.assertTrue(diag.execute_mfa and diag.view_mfa)
```

Testare inoltre scope locale incoerente, scope server senza workspace, lista vuota,
duplicati/wildcard e `True` invece di intero. Per export usare `EXPORT_RESULTS`
per entrambe le azioni; per filtri `START_JOB` per execute, `VIEW_RESULTS` per view;
MFA specifica soltanto per diagnostica.

- [x] **Step 2:** `uv run --frozen --group test python -m unittest tests.test_feature_license_contract -v`; atteso fallimento per interfacce ancora assenti, non per dipendenze.
- [x] **Step 3:** implementare contratti, invarianti, catalogo e fixture. `LicenseClaims` contiene claim strutturali; il controllo temporale appartiene al verificatore, non al costruttore.
- [x] **Step 4:** ripetere il comando; atteso PASS per tutti i subTest, nessuna rete.
- [x] **Step 5:** commit selettivo dei file del task: `feat(licensing): define feature license contracts and catalog`.

## Task 2: firme e chiavi pubbliche fidate

**Files:** Create `src/licensing/trust.py`, `src/licensing/verification.py`, `tests/test_feature_license_verification.py`; extend `tests/license_helpers.py`.

**Interfaces:**

- Consumes `LicenseClaims`, `LicenseScope`, `LicenseError`, `FeatureCatalog` da Task 1.
- `TrustedLicenseKeys(issuer: str, public_keys: Mapping[str, bytes])` verifica sole chiavi pubbliche Ed25519; `.resolve(kid: str) -> Ed25519PublicKey`.
- `LicenseVerifier(keys: TrustedLicenseKeys, catalog: FeatureCatalog)`; `.verify(token: str, *, scope: LicenseScope, now_epoch: int) -> LicenseClaims` con validità temporale e confronto esatto destinatario.
- `.decode_verified(token: str, *, scope: LicenseScope) -> LicenseClaims` esegue tutti i controlli di firma/schema/destinatario, senza decidere validità rispetto a now. Serve allo stato pubblico per mostrare date autentiche di licenze scadute; non concede privilegi e non sostituisce `.verify` nelle operazioni.
- Fixture `test_key_pair() -> tuple[bytes, bytes]` genera PEM privata/pubblica effimere; `signed_test_license(claims: LicenseClaims, private_pem: bytes, *, kid: str = "test-key") -> str` usa PyJWT solo nei test.

- [x] **Step 1: scrivere `test_validity_has_inclusive_start_exclusive_end`, `test_signature_and_trust_are_strict`, `test_duplicate_and_unexpected_json_fields_are_rejected` e `test_scope_and_features_must_match`** con subTest:

```python
token = signed_test_license(license_claims(not_before=10, expires_at=100), private_pem)
for epoch, code in ((9, "license_not_yet_valid"), (100, "license_expired")):
    with self.subTest(epoch=epoch), self.assertRaises(LicenseError) as raised:
        verifier.verify(token, scope=scope, now_epoch=epoch)
    self.assertEqual(raised.exception.code, code)
self.assertEqual(verifier.verify(token, scope=scope, now_epoch=10).expires_at, 100)
self.assertEqual(verifier.verify(token, scope=scope, now_epoch=99).expires_at, 100)
```

Rifiutare: firma alterata; `none`/HS256/chiave diversa; `kid` sconosciuto; `jku` o
`x5u`; audience array o diversa; issuer errato; chiavi duplicate anche nel payload;
header/claim inattesi; 16.385 byte; date float/stringa/boolean; `iat > nbf`, `nbf >= exp`;
UUID invalidi; scope errato; subject installation su scope server; feature sconosciuta.
Affermare che l'errore non contiene token. Nessun recupero di chiavi via HTTP.
Aggiungere `test_epoch_values_must_be_representable_in_utc`: intervallo accettato
`0..253402300799` (UTC fino al 31 dicembre 9999) per tutti i claim temporali;
numeri oltre questi limiti non arrivano al database o alla conversione UI.
`test_expired_license_metadata_requires_verified_signature` deve mostrare exp
tramite decode_verified per una licenza firmata scaduta e rifiutare la medesima
licenza alterata; verify continua a rifiutare entrambe per l'esecuzione.

- [x] **Step 2:** `uv run --frozen --group test python -m unittest tests.test_feature_license_verification -v`; atteso FAIL sull'interfaccia mancante.
- [x] **Step 3:** implementare parsing JSON con rifiuto duplicati e limiti prima della verifica; selezionare una chiave locale, usare `jwt.decode(..., algorithms=["EdDSA"])` per la firma. Disabilitare soltanto i controlli temporali automatici per applicare l'orologio iniettato, senza disabilitare firma/audience/issuer. Ricontrollare schema, tipo della chiave, invarianti e scope; zero leeway sulla scadenza.
- [x] **Step 4:** ripetere il comando e Task 1; atteso PASS, access token del login rifiutato come licenza.
- [x] **Step 5:** commit dei quattro file: `feat(licensing): verify strict signed expiring grants`.

## Task 3: repository locale, tempo e gestione comune delle licenze

**Files:** Create `src/infrastructure/file_lock.py`, `src/infrastructure/license_local_store.py`, `src/application/license_clock.py`, `src/application/feature_licenses.py`, `tests/test_local_feature_licenses.py`, `tests/test_license_clock.py`.

**Interfaces:**

- `Clock.now_epoch() -> int`; `SystemClock.now_epoch() -> int` usa UTC sistema.
- `ClockStore.advance(observed_epoch: int) -> int` protocol: aggiorna atomicamente il massimo e lo restituisce; `GuardedClock(clock: Clock, store: ClockStore).now_epoch() -> int` nega rollback oltre 300 secondi e usa il massimo per rollback minori.
- `LicenseRepository` protocol: `.read(scope: LicenseScope) -> StoredGrant | None`, `.activate(scope, *, token: str, claims: LicenseClaims, actor_id: UUID | None) -> None`, `.revoke(scope, *, license_id: UUID, actor_id: UUID | None) -> None`.
- `LocalLicenseStore(root: Path)` implementa entrambi i repository; `.installation_id() -> UUID` è persistente e multiprocesso. Solo scope installation; revoche conservate anche dopo il rinnovo.
- `LicenseService(repository: LicenseRepository, verifier: LicenseVerifier, clock: Clock)`; `.import_license(scope, token: str, *, actor_id: UUID | None = None) -> LicenseSummary`, `.revoke_license(scope, license_id: UUID, *, actor_id: UUID | None = None) -> LicenseSummary`, `.summary(scope) -> LicenseSummary`, `.require_valid(scope) -> LicenseClaims`.
- Audit locale amministrativo in `audit.jsonl`; token nello stato, mai nell'audit. File di stato `state.json`, lock separato `state.lock`, formato stato v1; maximum_time e installation_id rimangono quando la licenza scade/revoca.

- [x] **Step 1: scrivere `test_backup_preserves_identity_new_installation_does_not`, `test_invalid_renewal_preserves_active_grant`, `test_renewal_replaces_features_and_revoked_jti_cannot_reactivate`, `test_multiprocess_import_keeps_coherent_state` e `test_clock_rollback_uses_high_watermark`**, con `FakeClock(epoch: int).now_epoch() -> int` e `.set(epoch: int) -> None` in `tests/license_helpers.py`:

```python
original_id = store.installation_id()
self.assertEqual(LocalLicenseStore(root).installation_id(), original_id)
service.import_license(scope, valid_token)
with self.assertRaises(LicenseError):
    service.import_license(scope, tampered_token)
self.assertEqual(service.require_valid(scope).license_id, old_id)
store.advance(1000)
self.assertEqual(GuardedClock(FakeClock(701), store).now_epoch(), 1000)
with self.assertRaises(LicenseError) as raised:
    GuardedClock(FakeClock(699), store).now_epoch()
self.assertEqual(raised.exception.code, "license_clock_regression")
```

Verificare backup/copia stato con stessa identità, nuova root con identità diversa,
rinnovo ridotto senza unione, idempotenza, revoca definitiva di jti, storage corrotto,
write/replace falliti, audit redatto. Un test multiprocessing sincronizzato deve
importare/rinnovare da due processi senza corruzione; usare processi spawn compatibili
Windows, worker di test definiti a livello modulo, join con timeout e cleanup dei soli
processi creati dal test. Verificare che `--status` possa descrivere missing/scaduta.

- [x] **Step 2:** `uv run --frozen --group test python -m unittest tests.test_local_feature_licenses tests.test_license_clock -v`; atteso FAIL per componenti mancanti.
- [x] **Step 3:** implementare lock cross-platform (`msvcrt` Windows, `fcntl` Unix con import condizionale), timeout massimo 5 secondi e `license_storage_unavailable` su lock fallito. Scrivere temp nello stesso filesystem e usare `os.replace`; proteggere con lock anche letture coerenti e prima identità. Il massimo del tempo viene persistito prima di un permesso. `summary` usa decode_verified per conservare date/feature autentiche, calcola lo stato temporale e converte errori in stato leggibile; su firma/scope invalido non espone claim. `require_valid` usa verify e rilancia i dinieghi. Validare nuova licenza prima della sostituzione e, sotto lock, verificare ancora tombstone revocate.
- [x] **Step 4:** ripetere test e Task 1–2; atteso PASS; su Windows non importare `fcntl` e su Unix non importare `msvcrt`.
- [x] **Step 5:** commit dei sei file e fixture modificata: `feat(licensing): persist local grants and guarded time`.

## Task 4: persistenza PostgreSQL con RLS e clock condiviso

**Files:** Create `src/infrastructure/license_models.py`, `src/infrastructure/license_repository.py`, `migrations/versions/0004_feature_licenses.py`, `tests/test_feature_license_repository.py`, `tests/integration/test_feature_license_rls.py`, `tests/integration/test_feature_license_concurrency.py`; modify `src/infrastructure/models.py`, `migrations/env.py`, `tests/test_migrations.py`.

**Interfaces:**

- Consumes repository/clock protocol del Task 3; `SqlLicenseRepository(session: Session, installation_id: UUID)` implementa read/activate/revoke nel workspace già impostato.
- `PostgresClockStore(database: Database, installation_id: UUID).advance(observed_epoch: int) -> int` usa una transazione breve distinta dalla richiesta; implementazione SQLite separata per test unitari, senza pretendere che provi RLS.
- ORM `FeatureLicenseGrantModel(Base)`: UUID id/jti, installation_id, workspace_id/user_id FK, token Text, issued/not_before/expires epoch BigInteger, features JSON, active bool, revoked_at timestamp, imported_by FK, created_at/updated_at UTC. Unique `license_id`; indice univoco parziale su workspace_id/user_id quando active, sia PostgreSQL sia SQLite; vincolo active implica revoked_at NULL.
- ORM `LicenseClockStateModel(Base)`: installation_id PK, maximum_epoch BigInteger >= 0; nessun dato tenant.
- Revision `0004_feature_licenses`, down_revision `0003_contact_privacy_governance`. Registrare i nuovi modelli dopo la definizione di Base evitando import circolari; metadata di test e Alembic devono includerli.
- Function PostgreSQL `public.app_advance_license_clock(p_installation_id uuid, p_observed_epoch bigint) RETURNS bigint`: UPSERT con GREATEST; SECURITY DEFINER e search_path fisso pg_catalog,public; REVOKE da PUBLIC. App/worker EXECUTE, nessun INSERT/UPDATE/DELETE diretto sulla tabella del tempo. Impostare contesto transaction-local `app.installation_id`; rifiutare parameter diverso da quello corrente; si tratta di isolamento applicativo deployment, non di difesa da un amministratore DB.

- [x] **Step 1: scrivere `test_grant_lifecycle_is_atomic`, `test_grants_are_workspace_scoped_and_worker_read_only`, `test_concurrent_renewals_have_one_active_grant`, `test_revoke_and_renew_preserve_tombstones` e `test_license_time_only_advances`**; SQLite per lifecycle, PostgreSQL per permessi/concorrenza:

```python
with app.session(workspace_id=workspace_a) as session:
    self.assertIsNone(SqlLicenseRepository(session, installation_id).read(scope_b))
with self.assertRaises(ProgrammingError), worker.session(workspace_id=workspace_a) as session:
    session.execute(insert(FeatureLicenseGrantModel).values(worker_grant_values))
self.assertEqual(sorted(active_license_ids), [winning_license_id])
self.assertEqual(clock_store.advance(800), 1000)  # altro processo ha osservato 1000
```

Testare worker SELECT soltanto, scope assente fail-closed, cross-workspace insert,
renew/renew e revoke/renew concorrenti (membership row FOR UPDATE come lock
stabile, anche quando non esiste ancora un grant), replay di revoked jti, token
immutato con colonne normalized manomesse, downgrade/upgrade preservando la base.

- [x] **Step 2:** unità `uv run --frozen --group test python -m unittest tests.test_feature_license_repository tests.test_migrations -v`; atteso FAIL su schema/interfacce nuove. PostgreSQL solo con URL owner/app/worker del fixture e `REQUIRE_POSTGRES_TESTS=1` su database effimero.
- [x] **Step 3:** implementare schema/migrazione/repository. Grants: ENABLE e FORCE RLS sul predicato workspace esistente; app SELECT/INSERT/UPDATE, worker SELECT, nessun DELETE runtime. Sotto lock aggiornare active/revoked e conservare tombstone; read preferisce active, altrimenti l'ultimo revocato per stato pubblico. Il token viene sempre riverificato dal servizio, non sostituito dalle colonne estratte.
- [x] **Step 4:** ripetere unità e `uv run --frozen --group test python -m unittest tests.integration.test_feature_license_rls tests.integration.test_feature_license_concurrency -v` con `REQUIRE_POSTGRES_TESTS=1`; atteso PASS senza skip. Verificare upgrade/downgrade/upgrade su PostgreSQL effimero con ruoli runtime reali.
- [x] **Step 5:** commit selettivo dei nove file: `feat(licensing): isolate server grants and persist license time`.

## Task 5: autorizzazione comune e gestione server

**Files:** Create `src/application/feature_access.py`, `src/application/managed_licenses.py`, `src/workers/feature_access.py`, `tests/test_feature_access.py`, `tests/test_managed_feature_licenses.py`, `tests/test_worker_feature_context.py`; modify `src/application/audit_log.py`.

**Interfaces:**

- `FeatureAccessService(licenses: LicenseService, catalog: FeatureCatalog)`; `.require(context: FeatureContext, feature_id: str, *, action: FeatureAction = FeatureAction.EXECUTE) -> LicenseClaims`; `.list_status(context: FeatureContext) -> tuple[FeatureStatus, ...]`.
- `server_feature_context(session: Session, *, auth: AuthContext, workspace_id: UUID, installation_id: UUID) -> FeatureContext`: query UserModel/membership attuali, ROLE_PERMISSIONS, MFA da AuthContext; nessun ruolo accettato dal body.
- `ManagedLicenseService(licenses: LicenseService)`; `.import_for_user(session, *, actor: AuthContext, workspace_id: UUID, user_id: UUID, installation_id: UUID, token: str) -> LicenseSummary`; `.revoke_for_user(session, *, actor, workspace_id, user_id, installation_id, license_id: UUID) -> LicenseSummary`; `.status_for_user(...) -> LicenseSummary` con stessi argomenti tranne token/license_id.
- `job_feature_context(session: Session, *, job_id: UUID, installation_id: UUID) -> FeatureContext`: scope da jobs.workspace_id/created_by, membership corrente; mfa_verified False perché il modello job attuale non conserva una prova MFA verificabile. Nessun aggiramento per diagnostica: un futuro handler deve fornire un contesto MFA attendibile nella propria milestone.
- Audit detail allowlist aggiunge `license_id`, `features`, `expires_at`; features serializzate come stringa bounded con identificatori noti. Audit event `license.imported`, `license.renewed`, `license.revoked`, target_id jti, workspace/attore esistenti, zero token.

- [x] **Step 1: scrivere `test_expiry_blocks_next_step_and_sensitive_delivery`, `test_roles_and_mfa_never_replace_license`, `test_inactive_or_removed_member_is_denied`, `test_planned_feature_is_not_executable`, `test_job_context_ignores_client_supplied_authorization` e `test_license_audit_is_redacted`** con catalogo di test che marca una funzione available soltanto nel fixture:

```python
self.assertEqual(access.require(context, "diagnostics.full").license_id, expected_id)
clock.set(100)
with self.assertRaises(LicenseError) as raised:
    access.require(context, "diagnostics.full", action=FeatureAction.VIEW)
self.assertEqual(raised.exception.code, "license_expired")
self.assertEqual(licenses.summary(scope).license_status, "expired")
self.assertEqual(base_operation(), "base-ok")
```

Copertura: admin senza licenza negato; viewer export negato; MFA diagnostica
assente negata anche a ruolo ammesso; utente inactive/removal workspace; modulo
planned negato pur con grant valido; richiesta diretta al servizio negata senza
grant. Simulare chiamata già iniziata e avanzare FakeClock prima del controllo
di consegna; confermare nessun materiale riservato restituito. Verificare modifiche
token nei parametri job e ruolo dichiarato nel body ignorati; `job_feature_context`
usa creatore persistito e non assume MFA; missing job/workspace genera diniego.

- [x] **Step 2:** `uv run --frozen --group test python -m unittest tests.test_feature_access tests.test_managed_feature_licenses tests.test_worker_feature_context -v`; atteso FAIL sulle interfacce mancanti.
- [x] **Step 3:** implementare accesso con verifica licenza per ogni operazione/consegna, controllo del principal, feature/action, ruolo/MFA e disponibilità. ManagedLicenseService richiede MANAGE_WORKSPACE/MFA per import/revoke/status altrui; self status richiede membership ma non licenza attiva. Concedere solo token firmato esatto per target. Il repository e l'audit condividono la transazione request, il clock resta indipendente.
- [x] **Step 4:** ripetere i tre moduli e `tests.test_authorization tests.test_audit_log tests.test_job_state_machine`; atteso PASS; dispatcher commerciale invariato e nessun permesso derivato dai parametri.
- [x] **Step 5:** commit dei sette file: `feat(licensing): enforce scoped feature access and managed grants`.

## Task 6: strumento privato del proprietario

**Files:** Create `tools/license_issuer/__init__.py`, `tools/license_issuer/keys.py`, `tools/license_issuer/issuance.py`, `tools/license_issuer/__main__.py`, `tests/test_license_issuer.py`.

**Interfaces:**

- `generate_issuer_keys(*, private_path: Path, public_path: Path, passphrase: bytes) -> None`: Ed25519, PKCS8 PEM e BestAvailableEncryption; passphrase non vuota, niente sovrascrittura dei file esistenti.
- `issue_license(claims: LicenseClaims, *, private_path: Path, passphrase: bytes, kid: str, output_path: Path) -> None`: schema/catalogo v1, firma, output file; zero token nel ritorno/log.
- `parse_license_date(value: str) -> int`: ISO-8601 con Z o offset obbligatorio; niente date/ore naive; precisione in secondi interi.
- `main(argv: Sequence[str] | None = None) -> int` con subcommand `keygen`, `issue`, `inspect`; passphrase tramite getpass.getpass, niente flag passphrase/variabile obbligatoria/log. `inspect` usa LicenseVerifier e destinatario/tempo espliciti per il riepilogo verificato.

- [x] **Step 1: scrivere `test_encrypted_key_and_issued_license_round_trip`, `test_keygen_never_overwrites_existing_keys`, `test_bad_passphrase_and_naive_dates_are_rejected` e `test_inspect_never_prints_token`** con temp directory e passphrase effimera:

```python
generate_issuer_keys(private_path=private_path, public_path=public_path, passphrase=b"test-only")
self.assertIn(b"ENCRYPTED PRIVATE KEY", private_path.read_bytes())
with self.assertRaises(ValueError):
    serialization.load_pem_private_key(private_path.read_bytes(), password=None)
issue_license(claims, private_path=private_path, passphrase=b"test-only", kid="owner-test", output_path=output)
self.assertEqual(verifier.verify(output.read_text(), scope=claims.scope, now_epoch=10).features, claims.features)
self.assertNotIn(output.read_text(), captured_output)
```

Testare passphrase errata/vuota, keygen senza sovrascrittura, file pubblici al posto
dei privati, date naive/invalidi, impossibilità di exp assente/permanente, output
failure senza privata nei messaggi, `inspect` che non mostra token.

- [x] **Step 2:** `uv run --frozen --group test python -m unittest tests.test_license_issuer -v`; atteso FAIL sui file mancanti.
- [x] **Step 3:** implementare comandi; flags issue: `--private-key`, `--kid`, `--issuer`, `--installation-id`, `--subject-kind`, `--subject-id`, `--workspace-id` se server, `--feature` ripetibile, `--not-before`, `--expires-at`, `--out`. Generare jti e iat; verificare intervalli e non inserire dati personali. Paths reali rimangono esterni/ignorati; nessuna chiave di produzione generata durante sviluppo.
  `keygen` usa `--private-out` e `--public-out`; `inspect` usa `--license-file`,
  `--public-key`, `--kid`, `--issuer` e gli stessi flags di destinatario, con
  `SystemClock` in produzione e clock iniettato soltanto nei test.
- [x] **Step 4:** ripetere test e prova round-trip issuer/verifier nel test, atteso PASS.
- [x] **Step 5:** commit dei cinque file: `feat(licensing): add private expiring license issuer`.

## Task 7: configurazione e API server

**Files:** Create `src/licensing/settings.py`, `src/web/routes/feature_licenses.py`, `tests/test_feature_license_settings.py`, `tests/test_feature_license_api.py`; modify `src/web/{settings,schemas,dependencies,app}.py`, `src/server.py`, `compose.yml`, `.env.example`.

**Interfaces:**

- `LicenseSettings(issuer: str, trust_file: Path | None, local_state_dir: Path, installation_id: UUID | None)`; `.from_environment() -> LicenseSettings`, `.load_trusted_keys() -> TrustedLicenseKeys`. Trust file v1 JSON `{version, issuer, keys: {kid: public_pem}}`; duplicati/campi inattesi e materiale privato negati. Contenuto letto da file configurato; mai da token.
- Env `LEADHUNTER_LICENSE_ISSUER` default `lead-hunter-owner`, `LEADHUNTER_LICENSE_TRUST_FILE` opzionale, `LEADHUNTER_LICENSE_STATE_DIR` default `.leadhunter-state` assolutizzato dalla configurazione, `LEADHUNTER_INSTALLATION_ID` obbligatorio solo quando il licensing server è configurato. Nessun trust file = tutte le funzioni riservate missing; base/health/auth disponibili.
- WebRuntime aggiunge `license_settings: LicenseSettings | None = None` e `feature_catalog: FeatureCatalog | None = None`; helper `request_license_services(session: Session, app: WebRuntime) -> tuple[LicenseService, FeatureAccessService, ManagedLicenseService]` costruisce repository request e clock PostgreSQL indipendente. La configurazione non valida, quando esplicitamente presente, produce SettingsError sicuro all'avvio.
- Senza licensing server configurato, `GET .../features` restituisce le tre funzioni planned con granted False/license_status missing; i percorsi di import/revoca/status di singola concessione rispondono 503 redatto (`license_storage_unavailable`). Non generare UUID di deployment temporanei per soddisfare il tipo dello scope. Health/auth e operazioni base restano disponibili.
- Routes: `GET /workspaces/{workspace_id}/features` (proprio stato); `PUT /workspaces/{workspace_id}/feature-licenses/{user_id}` body `{token}` (import/rinnovo); `GET` stesso path (self oppure gestione admin); `DELETE .../{user_id}/{license_id}` (revoca idempotente). Non accettare expires/features/ruoli dal body.
- Response schemas `LicenseSummaryResponse`, `FeatureStatusResponse`; epoch -> ISO-8601 UTC e campi tipo/UUID pubblici, nessun token. Request `LicenseImportRequest` extra forbidden e token max 16 KiB.

- [x] **Step 1: scrivere `test_license_import_requires_authenticated_admin_mfa`, `test_signed_target_cannot_be_reassigned`, `test_self_status_survives_expiry`, `test_unconfigured_license_runtime_keeps_base_available` e `test_api_never_echoes_signed_token`** tramite TestClient e fixture piattaforma esistente:

```python
self.assertEqual(client.get(features_url).status_code, 401)
self.assertEqual(client.put(import_url, json={"token": valid_token}, headers=admin_without_mfa).status_code, 403)
response = client.put(import_url, json={"token": valid_token}, headers=admin_with_mfa)
self.assertEqual(response.status_code, 200)
self.assertNotIn(valid_token, response.text)
self.assertEqual(client.put(other_user_url, json={"token": valid_token}, headers=admin_with_mfa).status_code, 422)
```

Verificare 401/403/422/503 specifica, extra body negati, self status dopo expiry,
viewer non può gestire altri, cross-workspace 403/404 senza informazioni altrui,
inactive user negato, local grant su server negato, admin non può inventare grant,
trust key login rifiutata per typ/audience, health/auth senza licensing configurato.

- [x] **Step 2:** `uv run --frozen --group test python -m unittest tests.test_feature_license_settings tests.test_feature_license_api -v`; atteso FAIL su routes/config assenti.
- [x] **Step 3:** implementare wiring e schema. API usa auth esistente e ManagedLicenseService; 401 login, 403 accesso, 422 import invalido, 503 storage. Compose condivide installation ID e path pubblico fidato fra API/worker tramite server-env senza chiavi private licensing. Preservare bootstrap standard senza variabili licenza obbligatorie finché non configurate.
- [x] **Step 4:** ripetere i due moduli e `tests.test_api_security tests.test_authentication tests.test_secret_encryption tests.test_settings`; atteso PASS.
- [x] **Step 5:** commit selettivo dei file del task: `feat(licensing): expose scoped license management APIs`.

## Task 8: CLI e pannello locale

**Files:** Create `src/cli/feature_licenses.py`, `src/ui/__init__.py`, `src/ui/feature_license_panel.py`, `.streamlit/config.toml`, `tests/test_feature_license_cli.py`, `tests/test_feature_license_ui.py`; modify `src/application/container.py`, `src/gui.py`, `main.py`.

**Interfaces:**

- `ApplicationContainer.build_local_license_service() -> tuple[LicenseScope, LicenseService, FeatureAccessService]` usa LicenseSettings e LocalLicenseStore; non richiede GOOGLE_API_KEY/OPENROUTER_API_KEY.
- `src.cli.feature_licenses.main(argv: Sequence[str] | None = None) -> int` per `installation-id`, `status`, `import FILE`, `revoke LICENSE_ID`. Exit 0 per consultazione/import successo/revoca idempotente; 2 per operazione invalida o errore storage; stato missing/expired consultabile con exit 0.
- `render_feature_license_panel(*, scope: LicenseScope, licenses: LicenseService, access: FeatureAccessService) -> None`: consultazione stato, scadenza nel fuso locale, upload licenza e messaggio import; label per `planned`: "Autorizzato, modulo non ancora disponibile" quando granted, altrimenti "Modulo non ancora disponibile". Nessun pulsante di esecuzione per moduli pianificati.
- `main.py --gui` aggiunge `--server.address 127.0.0.1` al lancio Streamlit; introdurre `.streamlit/config.toml` con lo stesso binding per lancio diretto. La UI mantiene esplicite le restrizioni attuali di export/filtri finché i moduli sono pianificati.

- [x] **Step 1: scrivere `test_local_license_commands_need_no_provider_keys`, `test_planned_feature_shows_granted_but_unavailable`, `test_gui_import_and_expiry_use_common_service` e `test_gui_launch_and_direct_config_bind_loopback`**; CLI e Streamlit AppTest sul pannello in fixture isolata:

```python
with patch.dict(os.environ, {"GOOGLE_API_KEY": "", "OPENROUTER_API_KEY": ""}):
    self.assertEqual(cli_main(["installation-id"]), 0)
    self.assertEqual(cli_main(["status"]), 0)
self.assertIn("modulo non ancora disponibile", ui_text.lower())
self.assertFalse(ui_has_protected_execute_button)
self.assertNotIn(valid_token, ui_text)
self.assertEqual(streamlit_launch_args[-2:], ["--server.address", "127.0.0.1"])
```

Verificare renewal invalid/expiry nella UI, niente header token nei messaggi,
import oversize negato prima di read illimitato, locale data/ora con fuso
Europe/Rome tramite timezone di test, CLI senza fetch API/licenze online, launch
diretto `.streamlit/config.toml` coerente. Nessun test dipende da rete o rendering mappa.

- [x] **Step 2:** `uv run --frozen --group test python -m unittest tests.test_feature_license_cli tests.test_feature_license_ui -v`; atteso FAIL sulle interfacce mancanti.
- [x] **Step 3:** implementare pannello come unità isolata e poi inserirlo nella sidebar GUI; CLI dedicata evita refactor non necessario del parser pipeline e suoi P1. Stato licensing errore redatto non impedisce le funzioni base. Label/tempo derivano dal servizio, niente controllo privilegi alternativo in session_state. I file di stato non sono scritti in outputs/test_output.
- [x] **Step 4:** ripetere i due moduli più `tests.test_dependency_injection tests.test_presentation_security`; atteso PASS. Un test di servizio Task 5 continua a negare l'accesso diretto anche senza UI.
- [x] **Step 5:** commit dei file del task, inclusa `.streamlit/config.toml`: `feat(licensing): add local activation and feature status UI`.

## Task 9: distribuzione e verifica complessiva del blocco

**Files:** Create `tests/test_license_distribution.py`, `tests/test_feature_license_lifecycle.py`; modify `.dockerignore`, `.gitignore`, `README.md`, `docs/RELEASE_GATES.md`, `.github/workflows/ci.yml`, [nota di ripresa](../../RIPRESA_MODERNIZZAZIONE_2026-10-08.md).

**Interfaces:** Consumes i servizi e comandi dei Task 1–8; nessuna nuova interfaccia di prodotto.

- [x] **Step 1: scrivere `test_local_offline_expiry_renewal_and_revocation`, `test_managed_grant_lifecycle_is_scoped_and_redacted` e `test_customer_build_excludes_issuer_and_private_state`**. Lifecycle offline/API: issue/import/status, operazione fixture protetta, expiry con clock controllato, rinnovo e revoca; affermare base disponibile e token assente nei report. In `test_license_distribution` verificare esclusioni di `tools/license_issuer`, `.secrets`, `.leadhunter-state`, `*.pem`, `*.key`, `*.p12`, `*.pfx` e che README non contenga chiavi reali. I test source delle esclusioni sono preliminari; il gate immagine reale sotto è la prova finale.
- [x] **Step 2:** `uv run --frozen --group test python -m unittest tests.test_license_distribution tests.test_feature_license_lifecycle -v`; atteso FAIL sulle esclusioni/manuale mancanti o lifecycle non integrato.
- [x] **Step 3:** escludere materiale emittente e stato privato da build/Git, mantenendo fixture test generate a runtime. Nel CI container aggiungere una verifica reale che `tools/license_issuer` e file di chiavi licensing non esistano nell'immagine (file JWT runtime mount esclusi da questa verifica). All'interno del gate Python esistente rendere esplicito il lifecycle; PostgreSQL obbligatorio continua a includere le nuove integrazioni tramite discover.
- [x] **Step 4:** aggiornare manuale con comandi per emittente e cliente, trust bootstrap, backup identità, rinnovo, revoca, correzione orologio, confronto locale/server, scadenza aggiuntiva rispetto alla base perpetua. Documentare limiti offline e moduli pianificati. Esempi usano UUID fittizi, date con offset e path `.secrets`; non emettere una vera licenza del proprietario.
- [x] **Step 5:** verifiche finali sull'esecuzione:

```powershell
uv lock --check
uv run --frozen --group test python -m compileall -q src tests tools main.py
uv run --frozen --group test python -m unittest discover -s tests -v
git diff --check
docker compose config --quiet
```

Per PostgreSQL usare database effimero, i tre `TEST_DATABASE_*_URL` del fixture e
`REQUIRE_POSTGRES_TESTS=1`; effettuare round trip delle migrazioni con i ruoli
runtime. Riutilizzare il gate Docker esistente per build reale, avvio API non-root
e verifica immagine; niente down --volumes contro uno stack reale del proprietario.
I gate CI Python 3.10–3.13/PostgreSQL/container/Security sono prova ulteriore al PR,
non risultati da dichiarare prima che siano eseguiti.

- [x] **Step 6:** verificare che il token completo non compaia nei log catturati e che il corpus Git/build non contenga chiavi private licensing; eseguire pre-commit/Gitleaks nel flusso release esistente. Nessun allargamento dei test oltre i gate richiesti salvo nuovi errori/modifiche.
- [x] **Step 7:** commit dei sette file modificati e due test: `test(licensing): verify expiry lifecycle and customer distribution`.

## Copertura della specifica e handoff

| Requisiti specifica | Attività |
|---|---|
| Intento, modulo disponibile separato da permesso, base perpetua | 1, 5, 8, 9 |
| Catalogo, formato e parsing rigoroso | 1, 2 |
| Emissione cifrata, chiavi separate, trust/rotazione manuale | 2, 6, 7, 9 |
| Installazione/backup, import locale atomico, offline | 3, 8, 9 |
| Utenti/workspace, RLS e rinnovi concorrenti | 4, 5, 7 |
| Scadenza, rinnovo, revoca e massimo tempo condiviso | 2, 3, 4, 5, 9 |
| API/CLI/GUI e contratto futuro worker | 5, 7, 8 |
| Errori, audit redatto e chiavi fuori dalla build | 3, 5, 6, 7, 9 |
| Preservazione boundary e verifiche PostgreSQL reali | 4, 9 |

Revisione del piano effettuata su copertura, firme/tipi, nomi dei file, cinque
Review Focus e proporzione rispetto alla specifica. Prove eseguite e risultati
registrati nel resoconto di implementazione.

Esecuzione adottata: **native**, implementazione da parte dell'agente principale
in questa chat, con verifiche per task e revisione indipendente del branch al termine.
Le attività dipendono strettamente dallo stesso contratto di licenza e contesto;
questa modalità riduce i passaggi di contesto. L'alternativa è subagent-driven,
con implementazione e review indipendenti di ogni task prima del successivo.
Il proprietario ha approvato piano e implementazione il 9 ottobre 2026; metodo native.
