# Export riferimenti senza sito — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recuperare l'Excel dei Place ID e link Maps delle ricerche senza sito, con accessi a scadenza verificati alla generazione e alla consegna.

**Architecture:** Un contratto immutabile separa i riferimenti dal contenuto Google transitorio. Un servizio comune verifica la licenza e genera il workbook; protegge anche il salvataggio atomico. CLI e GUI lo riutilizzano, la GUI consegna byte inline; il backend può usarlo con un contesto ricostruito, senza nuovi endpoint o worker in questa fase.

**Tech Stack:** Python 3.10–3.13, unittest, openpyxl, Streamlit 1.60.0 del lock corrente, Ed25519 e FeatureAccessService esistenti, SQLAlchemy per le prove di contesto server.

**Spec:** [Specifica approvata](../specs/2026-10-09-export-riferimenti-senza-sito-design.md), 9 ottobre 2026.

## Global Constraints

- Esattamente due colonne: `Place ID` e `Link Google Maps`; foglio `Riferimenti`, header, filtro, prima riga bloccata.
- Identificativi stringhe ASCII di 1–500 caratteri: `[A-Za-z0-9][A-Za-z0-9_-]{0,499}`; confronto esatto e deduplicazione nell'ordine della prima occorrenza.
- Massimo 10.000 elementi in ingresso, prima della deduplicazione, anche per iteratori. Batch vuoto o non valido: nessun file consegnato.
- Proiezione soltanto da `provider == "google_places"` e `website_url is None`; il record contiene soltanto `place_id`.
- Link: `https://www.google.com/maps/search/?api=1&query=attivit%C3%A0&query_place_id=PLACE_ID`; testo e target hyperlink uguali, nessuna formula.
- Workbook, ZIP, proprietà, commenti e fogli non contengono altri dati provider, keyword, prompt, credenziali o token. Nessuna chiamata Google per generare il workbook.
- `export.no_website`: EXECUTE prima della generazione, VIEW con contesto fresco prima della consegna e della sostituzione del file. Sul server entrambi richiedono EXPORT_RESULTS; `nbf <= now < exp`.
- GUI: contenuto inline autorizzato, nessun media-manager/static URL; stato dei risultati costituito soltanto da ID normalizzati e azzerato a ogni nuova ricerca.
- CLI: `--export-references` soltanto con `--mode no_website`, verifica prima delle chiamate Google, gestione `--out` esistente, temporaneo nello stesso filesystem e sostituzione atomica.
- ExportPolicy e report con sito preservati; `pipeline_not_configured` resta invariato. Nessun endpoint export job, migrazione, nuovo audit journal o cambiamento dipendenze.
- Solo questo modulo diventa `available` a flusso verificato; rating/recensioni e diagnostica completa restano `planned`. Il gate NLTK della PR #7 non riceve eccezioni.

## Review Focus

1. ID numerici con zeri iniziali, differenze di maiuscole e lunghezza 500: testo e identità preservati (task 1–2).
2. Iteratore infinito di duplicati o record malformato in coda: limite prima della deduplicazione, nessun risultato parziale (task 1–2).
3. Revoca, rinnovo senza funzione o perdita di membership fra generazione e consegna: accesso corrente obbligatorio, file precedente intatto (task 2).
4. Rerun GUI dopo nuova ricerca vuota/fallita o revoca: nessun vecchio report riattivato, nessuna nuova consegna (task 4).
5. File aperto su Windows o errore di sostituzione: errore esplicito, nessun falso successo e temporaneo ripulito (task 2–3).

---

## Esecuzione e mappa dei file

Metodo **native**, già scelto: implementazione in questa sessione, poi una review indipendente dell'intero branch con un reviewer nuovo sul modello più capace disponibile. Riutilizzare il worktree `expiring-feature-licenses` e il branch `codex/no-website-reference-export`; base del diff export `876c839`. La PR #7 resta il prerequisito di integrazione. Piano approvato dal proprietario il 9 ottobre 2026; implementazione autorizzata.

Nuovi file: `src/domain/place_references.py` per contratto/proiezione/validazione; `src/application/reference_exports.py` per licenza, serializer privato e salvataggio; `src/ui/reference_export_panel.py` per consegna inline; quattro moduli di test omonimi alle aree sotto e `tests/reference_export_helpers.py` per fixture condivise. File esistenti: container per il wiring, `main.py` e `src/gui.py` per gli ingressi, catalogo per la disponibilità, README/licensing/milestone per le istruzioni.

Comandi di test sotto: PowerShell, uv **0.11.15**. In questo host definire `$exportUv = 'C:/Users/marce/AppData/Local/uv/cache/archive-v0/b2Pe658-N5aE5i8C/uv-0.11.15.data/scripts/uv.exe'`; in CI usare `uv`. Eseguire ogni RED prima della relativa implementazione, quindi GREEN; non aggiornare snapshot per nascondere regressioni. Commit selettivi e push dopo ciascun task completato.

### Task 1: Contratto minimale e proiezione dei candidati

**Files:** Create `src/domain/place_references.py`; test `tests/test_place_references.py`.

**Interfaces:**
- Consumes: `TransientCandidate` da `src/domain/discovery.py`, con `provider`, `external_id`, `website_url`.
- Produces: `GooglePlaceReference(place_id: str)` dataclass frozen con un solo campo; `ReferenceExportError(code: str)` con `.code` e messaggio uguale al codice.
- Produces: `normalize_references(references: Iterable[GooglePlaceReference]) -> tuple[GooglePlaceReference, ...]`; `project_google_place_references(candidates: Iterable[TransientCandidate]) -> tuple[GooglePlaceReference, ...]`.
- Codici pubblici: `reference_export_invalid`, `reference_export_empty`, `reference_export_limit`, `reference_export_write_failed`; nessun input interpolato nel messaggio.

- [x] **Step 1: Scrivere i test**, con fixture di candidati reali; proiezione vuota restituisce `()`, normalizzazione vuota solleva `reference_export_empty`. Le asserzioni dei test includono:

```python
def test_projection_retains_only_google_without_site(self):
    self.assertEqual(project_google_place_references(self.candidates), (GooglePlaceReference("ChIJ_1"),))
    self.assertEqual(asdict(GooglePlaceReference("ChIJ_1")), {"place_id": "ChIJ_1"})
def test_order_case_numeric_and_max_length(self):
    self.assertEqual(normalize_references(map(GooglePlaceReference, ["0007", "Ab", "ab", "0007", "A" * 500])),
                     tuple(map(GooglePlaceReference, ["0007", "Ab", "ab", "A" * 500])))
def test_invalid_id_grammar(self):
    for value in [None, 7, "", " A", "=1+1", "+1", "@x", "-x", "é", "A\n", "A" * 501]:
        with self.subTest(value=value), self.assertRaises(ReferenceExportError) as caught:
            GooglePlaceReference(value)
        self.assertEqual(str(caught.exception), "reference_export_invalid")
def test_limit_counts_duplicates_and_bounds_iterator(self):
    self.assertEqual(len(normalize_references(repeat(GooglePlaceReference("A"), 10000))), 1)
    with self.assertRaises(ReferenceExportError) as caught:
        normalize_references(self.counted_infinite_duplicates())
    self.assertEqual(caught.exception.code, "reference_export_limit")
    self.assertEqual(self.consumed, 10001)
def test_mixed_tail_and_empty_are_rejected(self):
    for records, code in [([], "reference_export_empty"),
                          ([GooglePlaceReference("A"), {"place_id": "B"}], "reference_export_invalid"),
                          ([self.candidates[0]], "reference_export_invalid")]:
        with self.assertRaises(ReferenceExportError) as caught:
            normalize_references(records)
        self.assertEqual(caught.exception.code, code)
```

Fixture `self.candidates`: Google senza sito `ChIJ_1`, Google con sito, altro provider senza sito e Google con `website_url=""` (quest'ultimo escluso). Aggiungere immutabilità e tentativo di assegnare campi extra al record; non riutilizzare CandidateReference a tre campi.

- [x] **Step 2: RED**: `& $exportUv run --frozen --group test python -m unittest tests.test_place_references -v`; atteso errore per modulo/interfacce mancanti.
- [x] **Step 3: Implementare le interfacce** nel modulo indicato. Validazione in costruzione e nuovamente all'ingresso della normalizzazione; controllare tipo esatto del record e stringa. Consumare al massimo 10.001 riferimenti prima di decidere il limite. La proiezione filtra esplicitamente i candidati, restituisce ID deduplicati e gestisce la selezione vuota senza errore.
- [x] **Step 4: GREEN**: ripetere il comando; tutti i test passano, senza rete né filesystem di prodotto.
- [x] **Step 5: Commit/push**: aggiungere solo i due file; `git commit -m "feat(export): add minimal Google place reference contract"`, poi `git push`.

### Task 2: Servizio autorizzato, workbook reale e scrittura atomica

**Files:** Create `src/application/reference_exports.py`, `tests/reference_export_helpers.py`, `tests/test_reference_exports.py`; modify `src/application/container.py`.

**Interfaces:**
- Consumes: task 1; `FeatureAccessService.require(context, feature_id, *, action=FeatureAction.EXECUTE)`; `FeatureContext`; `ApplicationContainer.build_local_license_service()`.
- Produces: `ReferenceExportService(access: FeatureAccessService, context_factory: Callable[[], FeatureContext])`; `.require_access(*, action: FeatureAction = FeatureAction.EXECUTE) -> None`; `.export_bytes(references: Iterable[GooglePlaceReference]) -> bytes`; `.save(references: Iterable[GooglePlaceReference], destination: Path) -> int` (numero righe uniche).
- Produces: private `_serialize_reference_workbook(references: tuple[GooglePlaceReference, ...]) -> bytes` nello stesso modulo; `ApplicationContainer.build_local_reference_export_service() -> ReferenceExportService`.
- Fixture test: `AvailableExportCatalog(FeatureCatalog)` rende disponibile solo export; gli altri moduli restano planned. Riutilizzare `license_claims`, `signed_test_license`, `FakeClock`, `test_key_pair` da `tests/license_helpers.py`; nessuna chiave permanente.

- [x] **Step 1: Scrivere i test** con LocalLicenseStore reale temporaneo, licenze firmate e contatore delle chiamate alla context factory. Patch del serializer privato solo per introdurre scadenza/revoca durante la generazione; workbook e scrittura sono reali negli altri test.

```python
def test_real_workbook_has_only_reference_content(self):
    data = self.service.export_bytes(self.refs)  # 0007, Ab, ab, 0007, A * 500
    book = load_workbook(BytesIO(data)); sheet = book["Riferimenti"]
    self.assertEqual(book.sheetnames, ["Riferimenti"])
    self.assertEqual(tuple(c.value for c in sheet[1]), ("Place ID", "Link Google Maps"))
    self.assertEqual([sheet.cell(i, 1).value for i in range(2, 6)], ["0007", "Ab", "ab", "A" * 500])
    self.assertEqual(sheet.freeze_panes, "A2"); self.assertEqual(sheet.auto_filter.ref, "A1:B5")
    self.assertEqual(sheet["B2"].value, "https://www.google.com/maps/search/?api=1&query=attivit%C3%A0&query_place_id=0007")
    self.assertTrue(all(c.data_type == "s" and c.comment is None for row in sheet for c in row))
    self.assertTrue(all(sheet.cell(i, 2).hyperlink.target == sheet.cell(i, 2).value for i in range(2, 6)))
    self.assertEqual(sheet.sheet_state, "visible")
def test_delivery_rechecks_after_expiry_revoke_or_renewal(self):
    for change, code in [(self.expire_during_serialization, "license_expired"),
                         (self.revoke_during_serialization, "license_revoked"),
                         (self.renew_without_export_during_serialization, "feature_not_granted")]:
        self.reset_grant(); self.install_serializer_change(change)
        with self.assertRaises(LicenseError) as caught:
            self.service.export_bytes(self.refs)
        self.assertEqual(caught.exception.code, code)
def test_atomic_save_preserves_old_file_on_denial_or_replace_error(self):
    for failure in [self.expire_after_fsync, self.fail_replace]:
        self.reset_grant(); self.destination.write_bytes(b"previous"); failure()
        with self.assertRaises((LicenseError, ReferenceExportError)):
            self.service.save(self.refs, self.destination)
        self.assertEqual(self.destination.read_bytes(), b"previous")
        self.assertEqual(list(self.destination.parent.iterdir()), [self.destination])
def test_server_membership_is_fresh_at_delivery(self):
    self.demote_member_during_serialization()  # committed admin -> viewer; current context factory
    with self.assertRaises(LicenseError) as caught:
        self.server_service.export_bytes(self.refs)
    self.assertEqual(caught.exception.code, "feature_role_denied")
```

Ispezionare tutti i membri ZIP del workbook per marker provider/keyword/token e proprietà/commenti/fogli extra; vietare formule e target diversi da HTTPS www.google.com. Fixture ZIP: marker ASCII distinti nei campi scartati della proiezione; token esatto mai presente. Casi aggiuntivi con nomi espliciti: `test_direct_call_denies_missing_tampered_expired_revoked_other_subject_and_missing_feature`, `test_not_before_and_clock_regression_remain_enforced`, `test_empty_invalid_or_over_limit_never_creates_file`, `test_successful_save_reopens_workbook_and_returns_unique_count` (4), `test_write_failure_is_redacted_and_cleans_temp`. Test server con fixture SQLAlchemy esistente, licenza dello scope server, workspace distinto negato; disattivazione utente/workspace e rimozione membership durante serializer negate. Entrambi i controlli devono usare contesti distinti (assert `.context_calls == 2` per export_bytes riuscito).

- [x] **Step 2: RED**: `& $exportUv run --frozen --group test python -m unittest tests.test_reference_exports -v`; fallimento sulle nuove interfacce.
- [x] **Step 3: Implementare le interfacce**. Normalizzare tutto prima del serializer; openpyxl in BytesIO, celle testo, URL tramite `urllib.parse.urlencode(..., quote_via=quote)`, metadati fissi neutrali. Nessun metodo pubblico di export privo di controllo; GUI/CLI chiamano il servizio. `save` controlla EXECUTE, genera, scrive/flush/fsync un temporaneo nella directory destinazione, controlla VIEW immediatamente prima di `os.replace`, restituisce il conteggio; nessun errore viene trasformato in successo. Cleanup su eccezioni/interrupt, errori OSError redatti con `reference_export_write_failed`. Il wiring locale ricrea FeatureContext a ogni controllo, non conserva un booleano di accesso. I chiamanti server forniscono una factory che rilegge scope/principal tramite gli helper esistenti; nessuna API nuova.
- [x] **Step 4: GREEN**: comando del task 2 insieme a `tests.test_place_references tests.test_feature_access tests.test_dependency_injection`; tutti passano. I test usano catalogo disponibile di fixture, il catalogo di prodotto resta planned fino al task 5.
- [x] **Step 5: Commit/push**: aggiungere i quattro file; `git commit -m "feat(export): protect reference workbooks and atomic delivery"`, poi `git push`.

### Task 3: Export CLI esplicito con verifica preventiva

**Files:** Modify `main.py`; create `tests/test_reference_export_cli.py`.

**Interfaces:**
- Consumes: `ApplicationContainer.build_local_reference_export_service()`, `ReferenceExportService.require_access()`/`.save(...)`, `project_google_place_references(...)`.
- Produces: `main(argv: Sequence[str] | None = None) -> int`; entry point `raise SystemExit(main())`. Flag argparse `--export-references`, default False; combinazione with_website rifiutata con `parser.error` (exit 2).

- [x] **Step 1: Scrivere i test** con orchestrator/provider finti e servizio reale firmato; patch soltanto catalogo di fixture fino al task 5. Testare direttamente main e mantenere prova runpy dell'entry point GUI esistente.

```python
def test_parser_rejects_reference_flag_with_website(self):
    with self.assertRaises(SystemExit) as caught:
        main(["--mode", "with_website", "--export-references"])
    self.assertEqual(caught.exception.code, 2)
def test_denied_preflight_makes_zero_provider_calls(self):
    self.assertEqual(main(self.search_args + ["--export-references"]), 2)
    self.assertEqual(self.provider_calls, 0)  # includes get_city_name
    self.assertFalse(self.destination.exists())
def test_valid_flag_saves_two_column_workbook(self):
    self.activate_export()
    self.assertEqual(main(self.search_args + ["--export-references", "--out", str(self.destination)]), 0)
    self.assertEqual(load_workbook(self.destination).active.max_column, 2)
def test_failed_write_has_no_success_message(self):
    self.activate_export(); self.block_replace()
    self.assertEqual(main(self.search_args + ["--export-references", "--out", str(self.destination)]), 2)
    self.assertNotIn("esportati", self.output.getvalue())
    self.assertIn("reference_export_write_failed", self.output.getvalue())
```

Altri test: no flag senza licenza = ricerca base e nessun XLSX; batch vuoto = nessun file/successo export; bare filename sotto OUTPUT_DIR e path esplicito rispettato; default filename mantiene la gestione corrente. Contenuto provider non passato a save. Report with_website, modalità GUI/test-url/examples e Ctrl-C conservano i percorsi esistenti.

- [x] **Step 2: RED**: `& $exportUv run --frozen --group test python -m unittest tests.test_reference_export_cli -v`; nuovo flag/main mancanti.
- [x] **Step 3: Estrarre main e integrare il flag** senza rifattorizzare le pipeline. Costruire/verificare il servizio se richiesto prima di create_orchestrator e prima di get_city_name. Ricerca completata -> proiezione -> save; se proiezione vuota, messaggio nessun riferimento senza file. Dinieghi/configurazione/errori del modulo restituiscono 2 con messaggio redatto; successo 0. Senza flag, indicare la disponibilità dell'export dei soli riferimenti evitando la vecchia affermazione di export totalmente disabilitato.
- [x] **Step 4: GREEN**: `& $exportUv run --frozen --group test python -m unittest tests.test_reference_export_cli tests.test_feature_license_ui tests.test_dependency_injection -v`; tutti passano.
- [x] **Step 5: Commit/push**: solo main e test; `git commit -m "feat(cli): add licensed no-website reference export"`, poi `git push`.

### Task 4: Stato GUI minimale e consegna inline autorizzata

**Files:** Create `src/ui/reference_export_panel.py`, `tests/test_reference_export_ui.py`; modify `src/gui.py`.

**Interfaces:**
- Consumes: tuple di ID dal task 1, service factory del container dal task 2.
- Produces: `render_reference_export_panel(*, place_ids: tuple[str, ...], service_factory: Callable[[], ReferenceExportService]) -> None`; helper privato `_reference_download_html(data: bytes) -> str`, con MIME XLSX e filename costante `riferimenti_google_maps.xlsx`.
- Integrazione: session_state `no_website_place_ids` contiene soltanto tuple[str, ...], default `()`; pannello fuori dal blocco start_btn, mostrato in modalità no_website.

- [x] **Step 1: Scrivere AppTest** sul pannello reale e sul wiring di `src/gui.py`, con orchestrator finto, firma/store reali e clock controllato. Preservare/restaurare `sys.modules['__main__']` come nei test UI esistenti.

```python
def test_inline_payload_is_real_workbook_without_static_url(self):
    app = self.licensed_app().run(); app.button(key="reference_export_prepare").click().run()
    self.assertEqual(len(app.exception), 0)
    html = app.get("iframe")[0].proto.srcdoc
    self.assertIn("data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,", html)
    self.assertNotIn("/media/", html); self.assertNotIn("http://", html)
    self.assertEqual(load_workbook(BytesIO(self.decode_inline(html))).active["A2"].value, "0007")
def test_new_empty_or_failed_search_clears_previous_ids(self):
    for outcome in [[], RuntimeError("test-only")]:
        app = self.search_app_with_previous_ids(outcome).run(); self.start_search(app)
        self.assertEqual(app.session_state["no_website_place_ids"], ())
        self.assertEqual(len(app.get("iframe")), 0)
def test_expired_revoked_or_missing_license_never_emits_iframe(self):
    for scenario in ["missing", "expired", "revoked"]:
        app = self.denied_app(scenario).run(); self.request_export(app)
        self.assertEqual(len(app.get("iframe")), 0)
        self.assertEqual(len(app.exception), 0)
```

Testare rerun di successo con sole stringhe ID in stato, contenuti provider/token assenti dall'HTML e nuovo search clearing anche cambiando modalità; base search senza trust continua a funzionare. Aggiungere `test_delivery_rechecks_after_html_construction`: revocare dopo export_bytes mentre l'HTML viene costruito, assert nessun iframe. Su rerun successivo al diniego il vecchio iframe non viene ricreato. Un iframe già ricevuto è materiale già consegnato, non una promessa di cancellazione alla scadenza.

- [x] **Step 2: RED**: `& $exportUv run --frozen --group test python -m unittest tests.test_reference_export_ui -v`; pannello/stato mancanti.
- [x] **Step 3: Implementare pannello e wiring**. Bottone `reference_export_prepare`, testo che specifica solo ID e link; factory invocata durante l'operazione, export_bytes, costruzione HTML da costanti e base64, ulteriore require_access(action=VIEW) immediatamente prima di `streamlit.components.v1.html`. Nessun st.download_button per questo export e nessun file pubblico. Azzerare ID a inizio nuova ricerca, popolarli solo dopo successo della proiezione, nessun payload/licenza/permesso booleano in stato. Gestire LicenseError, SettingsError e ReferenceExportError nel pannello; assenza trust non blocca la ricerca.
- [x] **Step 4: GREEN**: comando del task 4 insieme a `tests.test_reference_exports tests.test_feature_license_ui`. Verifica browser su server Streamlit loopback con fixture senza Google: click, decode dei byte inline, nuovo rerun dopo scadenza negato, nessuna registrazione del file nel media manager; non dedurre il requisito solo dal pulsante disabilitato.
- [x] **Step 5: Commit/push**: i tre file; `git commit -m "feat(gui): deliver licensed reference exports inline"`, poi `git push`.

### Task 5: Disponibilità, regressioni e istruzioni per l'utente

**Files:** Modify `src/licensing/catalog.py`, `tests/test_feature_license_contract.py`, `README.md`, `docs/FEATURE_LICENSES.md`, `docs/RIPRESA_MODERNIZZAZIONE_2026-10-08.md` e questo piano. Rimuovere la sostituzione del catalogo nei test degli ingressi CLI/GUI: devono usare quello reale; mantenere la fixture isolata per prove mirate del servizio.

**Interfaces:**
- Consumes: flussi verificati dei task 1–4.
- Produces: `FeatureCatalog.get("export.no_website")` con label `Export riferimenti senza sito`, status `available`, execute/view permissions `(Permission.EXPORT_RESULTS,)`; gli altri moduli mantengono i valori precedenti.

- [x] **Step 1: Aggiornare i test del catalogo**, sostituendo la vecchia aspettativa dei tre moduli planned. Gli ingressi provati con licenze reali non devono dipendere dal catalogo di fixture.

```python
def test_catalog_exposes_only_completed_export(self):
    catalog = FeatureCatalog()
    self.assertEqual(catalog.get("export.no_website").module_status, "available")
    self.assertEqual(catalog.get("export.no_website").label, "Export riferimenti senza sito")
    self.assertEqual(catalog.get("export.no_website").execute_permissions, (Permission.EXPORT_RESULTS,))
    self.assertEqual(catalog.get("export.no_website").view_permissions, (Permission.EXPORT_RESULTS,))
    for feature in ["discovery.rating_filters", "diagnostics.full"]:
        self.assertEqual(catalog.get(feature).module_status, "planned")
```

- [x] **Step 2: RED**: `& $exportUv run --frozen --group test python -m unittest tests.test_feature_license_contract tests.test_reference_export_cli tests.test_reference_export_ui -v`; disponibile atteso, planned corrente.
- [x] **Step 3: Aggiornare catalogo e documentazione** con esempio CLI `python main.py --mode no_website --lat 45.4642 --lng 9.1900 --keywords ristorante --export-references --out riferimenti.xlsx`, passi GUI/licenza, esattamente due colonne, significato snapshot e necessità di accesso corrente. Segnare completato soltanto il modulo export, worker/filtri/diagnostica e NLTK ancora aperti. Non dichiarare vendibile la release mentre i gate aperti persistono.
- [x] **Step 4: Verifica completa e review**: `& $exportUv lock --check`; `& $exportUv run --frozen --group test python -m compileall -q src tests main.py`; `& $exportUv run --frozen --group test python -m unittest discover -s tests -v`; `git diff --check`. PASS, nessuna nuova esclusione; eseguire i test PostgreSQL/container obbligatori con le fixture previste da CI, oppure registrare esplicitamente limiti locali e ottenere le prove CI prima dell'integrazione. Richiedere una review indipendente dell'intero diff export, correggere le osservazioni e ripetere i controlli interessati. Audit dipendenze: registrare il risultato reale, nessuna eccezione al blocco noto NLTK.
- [x] **Step 5: Commit/push e PR draft**: commit selettivo `feat(export): enable licensed reference export and document usage`, push. Creare una PR draft verso `codex/expiring-feature-licenses` per un diff export circoscritto, dichiarando dipendenza dalla PR #7; attach_artifact dopo creazione. Le pull_request attivano CI su ogni base: verificare Python 3.10–3.13, PostgreSQL, container/packaging sul nuovo HEAD. Nessun merge o release. Registrare esiti/limiti, stato milestone e commit nel resoconto finale.

## Esito della revisione interna del piano

Copertura: specifica §§1–4 -> task 1–2; §5 -> task 2 e 4; §6 -> task 3–4; §7 -> task 2 e 5; §8 -> prove per task e gate finali. Cinque Review Focus assegnati ai test indicati; interfacce producer/consumer allineate. Nessun recupero delle vecchie colonne Google e nessuna integrazione worker aggiunta. Piano approvato il 9 ottobre 2026; cinque task implementati e review recepita con RED→GREEN; gate della PR draft #8 da verificare sull’HEAD finale prima dell’integrazione. NLTK resta bloccante per la release.
