# Licensed Rating Filters Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recuperare i filtri rating/numero recensioni in entrambe le modalità, con accesso a scadenza e senza trasferire le metriche Google nei risultati o negli export.

**Architecture:** Criteri immutabili descrivono soltanto le soglie utente. Un servizio applicativo con verificatore reale autorizza il percorso privato dell'adapter Google; un controllo operativo accompagna l'origine dei risultati fino alla consegna. GUI, CLI ed eventuali chiamanti server usano queste stesse interfacce, mentre la discovery base resta indipendente dal licensing.

**Tech Stack:** Python 3.10–3.13, unittest, requests, Streamlit/AppTest, openpyxl, FeatureAccessService/Ed25519 e SQLAlchemy esistenti; uv 0.11.15 e lock corrente.

**Spec:** [Specifica approvata](../specs/2026-10-10-filtri-rating-recensioni-design.md).

Stato: piano preparato, autorevisionato e approvato dal proprietario il 10 ottobre 2026; implementazione e verifiche finali in corso. Esecuzione **native** già scelta: stesso implementer, una review indipendente finale. Task 1–5 implementati; completamento Task 6 subordinato a review e gate finali.

## Global Constraints

- Entrambe le modalità: `no_website` e `with_website`; filtro opzionale, inizialmente disattivato.
- Feature `discovery.rating_filters`; rimane `planned` fino alla verifica dei flussi, poi `available`. `diagnostics.full` resta `planned`.
- Default soltanto all'attivazione: `min_rating=3.9`, `max_reviews=100`; passa `rating > min_rating` e `1 <= userRatingCount <= max_reviews`.
- Rating utente finito 0–5, booleani esclusi; massimo recensioni intero esatto 1–2.147.483.647, booleani esclusi. Parametri invalidi prima di qualsiasi I/O della richiesta.
- Metriche provider mancanti/invalide escludono il candidato; niente conversioni da stringhe, arrotondamenti o `minRating` server.
- Mask base invariato; aggiungere soltanto `places.rating` e `places.userRatingCount` per tentativi filtrati autorizzati. Header per richiesta, nessuna mutazione condivisa.
- Metriche grezze escluse da candidati, lead, prompt, log, sessione, database, code e ZIP/metadata Excel. Nessun nuovo campo nei DTO discovery/provenienza.
- Contesto corrente a ogni EXECUTE/VIEW; EXECUTE prima delle dipendenze esterne e di ciascun tentativo HTTP; VIEW prima di ritorno e consegna, anche degli artefatti derivati.
- Scadenza/revoca: interrompere, nessun fallback base o successo parziale. File già consegnati validamente restano validamente consegnati.
- Server: START_JOB per EXECUTE, VIEW_RESULTS per VIEW, nessun nuovo MFA; contesto ricostruito con `server_feature_context`.
- Export filtrato senza sito: entrambe le concessioni filtro/export; soltanto Place ID e link Maps. Destinazione preesistente preservata in caso di consegna negata.
- Nessuna dipendenza, migrazione, paginazione, Place Details, modifica firma licenze o nuovo endpoint/worker. `pipeline_not_configured` resta invariato.
- Branch `codex/licensed-rating-filters`, worktree già isolato; base funzionale `6491f66da0f7fd956b88626a02dfca609ca7437e`. Commit selettivi, push dei cambiamenti major già autorizzati; PR draft contro `codex/remove-unused-nltk`, senza merge/release.

## Review Focus

1. Revoca dentro una callback di avanzamento o tra errore HTTP e retry: nessun altro POST autorizzato con stato precedente (Task 2).
2. Una prima occorrenza esclusa seguita da un duplicato valido, anche in un'altra keyword: prevale la prima occorrenza qualificata (Task 2/3).
3. Accesso perso durante serializzazione/fsync oppure HTML: nessuna sostituzione del file né nuova consegna inline, anche per lead derivati dal sito (Task 3/5).
4. Toggle spento o modalità cambiata dopo una ricerca filtrata: gli ID precedenti mantengono l'origine protetta; un errore/risultato vuoto li cancella (Task 5).
5. Interruzione o eccezione contenente identificativi/provider payload: niente salvataggio d'emergenza filtrato, risultato parziale o dettagli sensibili in console/log (Task 3/4).

---

## File e responsabilità

| File | Responsabilità e intervento |
|---|---|
| Nuovo `src/domain/rating_filters.py` | Criteri immutabili e validazione delle soglie utente |
| Nuovo `src/application/rating_filters.py` | `RatingFilterGuard` operativo e `RatingFilteredDiscoveryService` comune |
| `src/providers/discovery/google_places.py` | Percorso filtrato privato, confronto effimero, mask per richiesta e guard sui retry |
| `src/application/container.py` | Composizione locale guard/discovery; percorso base indipendente |
| `main.py` | Origine dell'orchestrazione, propagazione dei rifiuti e opzioni CLI esplicite |
| `src/exporter.py`, `src/application/reference_exports.py` | Consegna bytes/file con origine filtrata e salvataggio atomico protetto |
| Nuovo `src/ui/rating_filter_controls.py` | Controlli condivisi tra le due modalità, default off |
| Nuovo `src/ui/inline_download.py` | HTML download in memoria e controllo immediatamente prima dell'iframe |
| `src/ui/reference_export_panel.py`, `src/gui.py` | Origine in sessione, reset/rerun, rendering e download autorizzati |
| `src/licensing/catalog.py`, `README.md`, milestone/spec/piano | Disponibilità finale, uso e limiti documentati |
| Nuovo `tests/rating_filter_helpers.py` | Chiavi effimere, licenze firmate, clock e catalogo disponibile solo nei test intermedi |
| Nuovi `tests/test_rating_filter_criteria.py`, `tests/test_rating_filter_discovery.py` | Validazione, provider, servizio e contesto server |
| Nuovi `tests/test_rating_filter_delivery.py`, `tests/test_rating_filter_cli.py`, `tests/test_rating_filter_ui.py` | Pipeline, artefatti e flussi utente |
| Test esistenti discovery/compliant/export/licensing/DI | Regressioni dei confini e del percorso base |

Non ristrutturare crawler/auditor né recuperare gli altri filtri legacy. `src/filters.py::filter_by_reviews`, funzione pura non usata dalla pipeline, non abilita il modulo e non viene collegata come percorso alternativo.

## Preparazione dell'esecuzione

Leggere spec e piano approvati; verificare worktree/branch puliti. Conservare brief, BASE di ogni task, decisioni ed esiti RED/GREEN nel ledger di executing-plans, sotto un nuovo workspace ignorato `.superpowers/`; non toccare gli scratch dei sottoprogetti precedenti. Ogni decisione necessaria è una `Ruling` motivata; non chiedere conferma tra task già autorizzati.

Nei comandi seguenti inizializzare in PowerShell:

```powershell
$ratingUv = 'C:/Users/marce/AppData/Local/uv/cache/archive-v0/b2Pe658-N5aE5i8C/uv-0.11.15.data/scripts/uv.exe'
```

Non usare uv globale 0.12.20. Le prove intermediamente disponibili usano un catalogo di test, non un bypass di `FeatureAccessService`.

### Task 1: Criteri e controllo operativo comune

**Files:** creare `src/domain/rating_filters.py`, `src/application/rating_filters.py`, `tests/rating_filter_helpers.py`, `tests/test_rating_filter_criteria.py`.

**Interfaces:**
- Produce `RatingFilterCriteria(min_rating: float = 3.9, max_reviews: int = 100)`, dataclass frozen; rating int/float normalizzato a float, count con `type(value) is int`. Invalidità: `ValueError('rating_filter_invalid')`, nessun valore ricevuto nel messaggio.
- Produce `RatingFilterGuard(access: FeatureAccessService, context_factory: Callable[[], FeatureContext])`, con `require_execute() -> None`, `require_view() -> None`. Entrambi ricostruiscono il contesto e richiedono `discovery.rating_filters` con l'azione corrispondente.
- Guard = origine operativa fidata, non una concessione in cache. Non serializzabile (`__reduce_ex__` rifiuta il pickle), repr neutro, nessun campo di metriche/token/claims; mantiene riferimenti ai servizi necessari alla verifica corrente.
- Fixture `RatingFilterFixture(testcase, *, features=('discovery.rating_filters',), available=True)` espone `scope`, `claims`, `clock`, `licenses`, `access`, `guard`, `activate(claims=None)`; usare gli helper Ed25519 esistenti e catalogo di test che cambia soltanto disponibilità dei moduli necessari. Nessuna chiave privata permanente.

- [x] **Step 1: Scrivere le prove di criteri e guard** in `RatingFilterCriteriaTests`; includere queste asserzioni:

```python
# test_defaults_and_exact_types
self.assertEqual(RatingFilterCriteria(), RatingFilterCriteria(3.9, 100))
self.assertIs(type(RatingFilterCriteria(0, 1).min_rating), float)
self.assertEqual(RatingFilterCriteria(5, 2147483647).max_reviews, 2147483647)
# test_invalid_input_never_creates_dependencies (parameterizzare ciascun campo)
for value in [True, False, '3.9', None, float('nan'), float('inf'), -0.1, 5.1, 10**1000]:
    with self.assertRaisesRegex(ValueError, '^rating_filter_invalid$'):
        RatingFilterCriteria(value, 100)
for value in [True, False, '100', None, 1.0, 0, -1, 2147483648]:
    with self.assertRaisesRegex(ValueError, '^rating_filter_invalid$'):
        RatingFilterCriteria(3.9, value)
dependency_factory.assert_not_called()
# test_guard_rechecks_real_license_and_is_not_serializable
guard.require_execute(); fx.clock.set(fx.claims.expires_at)
with self.assertRaises(LicenseError) as caught:
    guard.require_view()
self.assertEqual(caught.exception.code, 'license_expired')
with self.assertRaises(TypeError):
    pickle.dumps(guard)
```

Aggiungere immutabilità, aggiornamento del context factory a ogni azione e licenze assenti/non concesse/alterate/revocate/installazione diversa; verificare i codici del contratto esistente, senza mock della decisione autorizzativa.

- [x] **Step 2: RED**: `& $ratingUv run --frozen --group test python -m unittest tests.test_rating_filter_criteria -v`; atteso fallimento per nuove interfacce mancanti.
- [x] **Step 3: Implementare** criteri e guard con le firme sopra; guard senza I/O provider né flag di autorizzazione. La disponibilità produttiva resta `planned`.
- [x] **Step 4: GREEN**: stesso comando, tutti PASS.
- [x] **Step 5: Commit** solo i quattro file del task: `feat: add validated rating criteria and runtime access guard`.

### Task 2: Discovery filtrata autorizzata dentro Google

**Files:** modificare `src/application/rating_filters.py`, `src/providers/discovery/google_places.py`; creare `tests/test_rating_filter_discovery.py`; estendere `tests/test_discovery_contract.py`.

**Interfaces:**
- Consuma `RatingFilterCriteria`, `RatingFilterGuard` del Task 1 e DTO discovery esistenti.
- Produce `RatingFilteredDiscoveryService(provider: GooglePlacesDiscoveryProvider, criteria: RatingFilterCriteria, guard: RatingFilterGuard)`, con `attribution` del provider e `discover(query: DiscoveryQuery, *, on_progress: Callable[[int, int], None] | None = None) -> DiscoveryBatch`.
- L'adapter mantiene `discover(query, *, on_progress=None)` esclusivamente base. Aggiunge il privato `_discover_filtered(query: DiscoveryQuery, *, criteria: RatingFilterCriteria, guard: RatingFilterGuard, on_progress=None) -> DiscoveryBatch`, richiamato dal servizio; niente parametro pubblico booleano o criteri senza verificatore.
- Privato `_matches_rating_criteria(raw: Mapping[str, Any], criteria: RatingFilterCriteria) -> bool` nell'adapter. Estendere `_fetch(text, language, lat, lng, *, criteria: RatingFilterCriteria | None = None, guard: RatingFilterGuard | None = None) -> list[TransientCandidate]`; criteri/guard devono essere entrambi presenti oppure assenti.
- Conservare il mask base validato come dato privato: il parametro constructor accetta soltanto sottoinsiemi non vuoti di `places.id`, `places.displayName`, `places.websiteUri`, `places.attributions`, mantenendo l'ordine. Campi protetti/wildcard/altri campi: `ValueError('provider_field_mask_invalid')` prima di I/O. Gli header effettivi ricompongono sempre questo mask, anche se i metadati pubblici `headers` vengono modificati. Usare TYPE_CHECKING/import locali dove necessario per evitare il ciclo servizio→adapter→guard.

- [x] **Step 1: Scrivere prove con HTTP fixture completo**, adapter reale, clock e licenze firmate. Asserzioni in `RatingFilterDiscoveryTests`:

```python
# test_strict_boundaries_and_missing_metrics
self.assertEqual(ids(batch), ('above-threshold', 'at-max-count'))
# Fixture: rating 3.9 escluso, 4.0 con count 100 incluso; count 0/101 escluso.
# Rating 0/5: threshold 0 ammette un rating positivo; threshold 5 non ammette nulla.
# Parameterizzare rating/count mancanti, stringhe, bool, NaN/inf, rating -1/6,
# count frazionario/negativo/>2147483647, elementi non mapping: il vicino valido resta.
self.assertEqual(base_mask, provider.headers['X-Goog-FieldMask'])
# test_request_masks_do_not_leak_after_filtered_search_or_concurrently
self.assertEqual(set(filtered_mask.split(',')) - set(base_mask.split(',')),
                 {'places.rating', 'places.userRatingCount'})
self.assertEqual(base_request_mask, base_mask)
self.assertEqual(request_mask_after_public_header_mutation, base_mask)
# test_base_constructor_rejects_protected_or_unbounded_mask
with self.assertRaisesRegex(ValueError, '^provider_field_mask_invalid$'):
    make_provider(field_mask='places.id,places.rating')
http.post.assert_not_called()
self.assertNotIn('minRating', posted_json)
self.assertNotIn('rating', vars(batch.candidates[0]))
self.assertNotIn('userRatingCount', vars(batch.candidates[0]))
# test_first_qualifying_duplicate_wins
self.assertEqual(ids(batch), ('duplicate', 'second'))
self.assertEqual(batch.candidates[0].display_name, 'qualifying-occurrence')
# test_expiry_between_cells_retries_and_progress_callback
self.assertEqual(http.post.call_count, 1)  # revoca/scadenza dopo primo tentativo
self.assertEqual(caught.exception.code, expected_license_code)
self.assertEqual(delivered_batches, [])
```

Testare mask concorrenti con barriera/thread e stessa istanza, sequenza filtered→base→filtered, mask `*`/review testi/indirizzi/telefoni rifiutati, input `places.id` ancora valido. Se la prima callback di progresso revoca l'accesso, zero POST; alla seconda callback o tra retry dopo primo POST, un POST. Testare risposta in volo che fa scadere/revocare la licenza prima del ritorno: errore VIEW, nessun batch, nessun fallback; mantenere errori provider globali sicuri e retry timeout/429/5xx già esistenti.

Aggiungere `test_server_context_is_current_per_attempt_and_delivery` usando DB/helper correnti, SQL repository e firma reale: ruolo viewer impedisce il prossimo EXECUTE ma conserva VIEW_RESULTS; membership rimossa, utente/workspace inattivo impediscono consegna; scope errato non concede nulla. Mutare da una seconda sessione per verificare il refresh effettivo, non un context fake in cache.

- [x] **Step 2: RED**: `& $ratingUv run --frozen --group test python -m unittest tests.test_rating_filter_discovery -v`; nuove interfacce/behavior assenti.
- [x] **Step 3: Implementare** servizio EXECUTE→adapter→VIEW; adapter filtra prima di costruire candidati, poi deduplica. Costruire una copia degli header per ogni richiesta; guard EXECUTE immediatamente prima di ogni POST effettivo, fuori dal catch generico provider o con `LicenseError` esplicitamente propagato. Le callback ricevono solo stato/avanzamento, mai raw/candidati. Nessun salvataggio delle metriche.
- [x] **Step 4: GREEN**: `& $ratingUv run --frozen --group test python -m unittest tests.test_rating_filter_discovery tests.test_discovery_contract -v`; tutti PASS, contratti base invariati.
- [x] **Step 5: Commit** file del task: `feat: filter Places results behind fresh per-attempt authorization`.

### Task 3: Origine protetta nella pipeline e negli export

**Files:** modificare `src/application/container.py`, `main.py`, `src/application/reference_exports.py`, `src/exporter.py`; creare `tests/test_rating_filter_delivery.py`; estendere `tests/test_compliant_pipeline.py`, `tests/test_dependency_injection.py`, `tests/test_reference_exports.py`, `tests/test_export_policy.py`.

**Interfaces:**
- Produce `ApplicationContainer.build_local_rating_filter_guard() -> RatingFilterGuard` e `build_scraper(*, rating_criteria: RatingFilterCriteria | None = None, rating_guard: RatingFilterGuard | None = None) -> LeadScraper`. Percorso filtrato richiede la coppia e EXECUTE prima di costruire Google/scraper; percorso base non costruisce servizi licenze.
- Estende `create_orchestrator(mode: str, settings: ApplicationSettings | None = None, *, rating_criteria: RatingFilterCriteria | None = None, rating_guard: RatingFilterGuard | None = None) -> LeadHunterOrchestrator`: per criteri validi costruisce guard locale se non passato, verifica EXECUTE, quindi dipendenze; guard server esplicito è riutilizzabile. Criteri di tipo errato o guard senza criteri: `ValueError('rating_filter_invalid')` prima di settings/storage/provider I/O.
- Estende constructor dell'orchestratore con `result_origin: RatingFilterGuard | None = None`, proprietà omonima e `require_result_view() -> None`; su base è no-op. Entrambi i metodi `run_no_website`/`run_with_website` controllano prima di restituire, anche vuoto; errori cancellano risultati della nuova operazione. Eliminare i vecchi parametri inutilizzati `min_rating`/`max_reviews` da `run_with_website` e aggiornare tutti i chiamanti esplicitamente.
- Estende `ReferenceExportService.export_bytes(references, *, origin: RatingFilterGuard | None = None) -> bytes` e `save(references, destination, *, origin=None) -> int`: guard VIEW all'ingresso e prima della consegna/replace, oltre agli EXECUTE/VIEW export esistenti.
- Aggiunge `DataExporter.export_bytes(leads, mode='with_website', privacy_policy=None, suppression_checker=None, *, origin: RatingFilterGuard | None = None) -> bytes`; stessa ExportPolicy/formattazione/sanitizzazione, workbook in memoria, guard VIEW prima di lavorare e prima del ritorno. Estende `export_to_excel` con keyword-only `origin=None`, usando lo stesso serializer: per origine filtrata temp sul filesystem destinazione, flush/fsync, nuova VIEW, `os.replace`, cleanup anche su interrupt. Il percorso base conserva il comportamento pubblico. Il percorso protetto propaga `LicenseError`; errori scrittura `OSError('website_export_write_failed')` senza path/payload sensibili.

- [x] **Step 1: Scrivere prove end-to-end di servizio/pipeline con trasporto e auditor fixture**, non matcher/decisione licenze mockati:

```python
# test_denial_precedes_google_auditor_crawler_and_geocoding
google_factory.assert_not_called(); auditor_factory.assert_not_called()
geocoding.assert_not_called(); crawler_factory.assert_not_called()
# test_both_modes_preserve_order_and_first_qualifying_keyword_duplicate
self.assertEqual(no_site_ids, ('qualified-no-site',))
self.assertEqual(verified_websites, ['https://official.example/'])
self.assertEqual(auditor.call_args.kwargs['rating'], 0)
self.assertEqual(auditor.call_args.kwargs['review_count'], 0)
# test_derived_exports_recheck_after_serialization_and_fsync
self.assertEqual(destination.read_bytes(), b'previous-export')
self.assertEqual(list(destination.parent.glob('.reference-export-*')), [])
self.assertEqual(list(destination.parent.glob('.website-export-*')), [])
self.assertEqual(delivered_bytes, [])
# test_filter_and_reference_export_permissions_are_independent
self.assertEqual(caught.exception.code, 'feature_not_granted')
self.assertEqual(zip_column_names(reference_bytes), ['Place ID', 'Link Google Maps'])
# test_filtered_failure_clears_results_and_never_emits_partial_leads
self.assertEqual(orchestrator.all_leads, {})
self.assertEqual(orchestrator.transient_results, [])
self.assertNotIn('provider-secret-sentinel', console_and_logs)
self.assertEqual(candidate_callbacks, [])
```

Copertura: entrambe le combinazioni feature mancanti, rifiuto in chiamata diretta ai servizi, scadenza durante crawl/audit e prima di ritorno/esportazione; social/site classification invariati; base senza trust/store; workbook sito riaperto con sanitizzazione e policy privacy/suppression esistenti. Ispezionare tutti gli entry del ZIP, DTO, payload auditor, log catturati e messaggi: nessun valore sentinel rating/conteggio né risposta grezza. Controllare che nessuna nuova scrittura DB/queue riceva payload provider; aggiungere ai test boundary esistenti i campi proibiti, senza inventare un nuovo percorso di persistenza.

- [x] **Step 2: RED**: `& $ratingUv run --frozen --group test python -m unittest tests.test_rating_filter_delivery -v`; wiring/origine/export protetto mancanti.
- [x] **Step 3: Implementare composizione e origine** con firme sopra; stessa dipendenza discovery per entrambe le modalità. Rifiuti licenze non vengono assorbiti dai catch generici. Progresso solo aggregato; errori audit non stampano Place ID, eccezioni grezze o risultati parziali. Conservare ordine e confini Google/sito; ai risultati derivati si associa il guard della ricerca, non i valori provider.
- [x] **Step 4: Implementare serializer e consegna protetta** nelle due classi export, condividendo il serializer esistente tra bytes/file; VIEW subito prima di return/replace. Non indebolire ExportPolicy né aggiungere `export.no_website` al report sito.
- [x] **Step 5: GREEN**: `& $ratingUv run --frozen --group test python -m unittest tests.test_rating_filter_delivery tests.test_compliant_pipeline tests.test_dependency_injection tests.test_reference_exports tests.test_export_policy tests.test_privacy_export_gate -v`; tutti PASS.
- [x] **Step 6: Commit e push major** selettivi: `feat: preserve rating-filter authorization through pipeline and exports`; `git push -u origin codex/licensed-rating-filters`. Modulo produttivo ancora `planned`.

### Task 4: CLI esplicita e consegna controllata

**Files:** modificare `main.py`; creare `tests/test_rating_filter_cli.py`; estendere `tests/test_reference_export_cli.py`.

**Interfaces:** consuma criteri/guard e `create_orchestrator(..., rating_criteria=...)` Task 3. `main(argv: Sequence[str] | None = None) -> int` mantiene la firma; nuovo flag `--rating-filters`, argomenti soglia default `None` per distinguere presenza esplicita, valori 3.9/100 applicati soltanto quando abilitato.

- [x] **Step 1: Scrivere le prove CLI**, per entrambe le modalità e le combinazioni export:

```python
# test_explicit_flag_applies_defaults_in_both_modes
self.assertEqual(criteria, RatingFilterCriteria(3.9, 100))
self.assertEqual(main(valid_filtered_argv), 0)
# test_thresholds_without_flag_or_special_modes_fail_before_any_io
self.assertEqual(caught.exception.code, 2)  # argparse SystemExit
settings_loader.assert_not_called(); orchestrator_factory.assert_not_called()
diagnostic_runner.assert_not_called(); gui_launcher.assert_not_called()
# test_invalid_criteria_and_license_prevent_all_side_effects
self.assertEqual(exit_code, 2)
http.post.assert_not_called(); llm.assert_not_called(); writer.assert_not_called()
# test_delivery_denied_or_interrupted_has_no_partial_export
self.assertNotIn('protected-business', stdout.getvalue())
self.assertEqual(destination.read_bytes(), b'previous-export')
self.assertFalse(emergency_destination.exists())
self.assertNotEqual(exit_code, 0)
# test_base_needs_no_license_configuration
self.assertEqual(main(base_argv), 0)
license_factory.assert_not_called()
```

Parametrizzare `--min-rating`/`--max-reviews` senza flag (anche esplicitamente pari ai default), NaN/inf/negative/oltre limite e combinazioni rating con `--test-url`, `--gui`, `--examples`. Testare revoca immediatamente prima della stampa e save, e eccezione provider con sentinel: fallimento redatto senza file. I test base export già esistenti devono continuare a passare.

- [x] **Step 2: RED**: `& $ratingUv run --frozen --group test python -m unittest tests.test_rating_filter_cli -v`; flag/preflight/delivery mancanti.
- [x] **Step 3: Implementare parsing/preflight**: parse e validazione rating prima di `ApplicationSettings.from_environment()` (carica `.env`). Per `--token-mode` usare sentinel e applicare il default settings dopo parsing; preservare i default runtime. Soglie isolate/combinazioni speciali: `parser.error`, code 2. Invalidità/licenza/config: code 2; altri fallimenti runtime filtrati: code 1, redatti. Verificare EXECUTE prima di dipendenze/geocoding e inoltrare origine a ogni export; preparare il blocco completo di risultati console in memoria e chiamare `require_result_view` immediatamente prima della stampa unica, senza streaming di singoli candidati. Interruzione filtrata: niente export d'emergenza né successo parziale, codice non zero; base conserva il comportamento esistente. Aggiornare help/esempi con `--rating-filters`; niente vecchie soglie noop.
- [x] **Step 4: GREEN**: `& $ratingUv run --frozen --group test python -m unittest tests.test_rating_filter_cli tests.test_reference_export_cli tests.test_dependency_injection -v`; tutti PASS.
- [x] **Step 5: Commit** file del task: `feat(cli): expose licensed rating filters for both search modes`.

### Task 5: GUI, rerun e download senza concessioni in cache

**Files:** creare `src/ui/rating_filter_controls.py`, `src/ui/inline_download.py`, `tests/test_rating_filter_ui.py`; modificare `src/gui.py`, `src/ui/reference_export_panel.py`, `tests/test_reference_export_ui.py`.

**Interfaces:**
- `render_rating_filter_controls(*, guard_factory: Callable[[], RatingFilterGuard]) -> RatingFilterCriteria | None`: toggle «Filtra per rating e recensioni», off inizialmente; disabled se EXECUTE non consentito/config non disponibile. Soglie visibili solo se attivo, default 3.9/100; messaggio sul confronto stretto e dati mancanti. Preflight visuale non sostituisce verifica del motore.
- `render_inline_xlsx_download(data: bytes, *, filename: str, label: str, before_delivery: Callable[[], None]) -> None`: HTML link data-URI con label/filename escaped e base64; chiamare guard dopo costruzione HTML e subito prima di `components.html`. Nessun static media URL/session bytes.
- `render_reference_export_panel(*, place_ids, service_factory, origin: RatingFilterGuard | None = None) -> None`: origine VIEW prima di mostrare riferimenti/preparare, inoltrarla a `export_bytes`; callback finale ricontrolla export VIEW e origine VIEW. Mantenere la semantica reference-only e gli errori sicuri esistenti.
- Stato aggiuntivo `no_website_result_origin: RatingFilterGuard | None`, scritto soltanto dalla pipeline fidata insieme a `no_website_place_ids`. Non ricostruire origine dal toggle corrente; non salvare claim, token, risposta provider, criteri di matching ricevuti o workbook. Su nuova ricerca cancellare entrambi prima di eseguire; su rifiuto/fallimento cancellare entrambi. Su rerun verificare VIEW prima di esporre riferimenti/export filtrati.

- [x] **Step 1: Scrivere AppTest sulla GUI reale e sui componenti**, con licenze reali fixture e provider trasporto controllato:

```python
# test_default_off_and_controls_in_both_modes
self.assertFalse(rating_toggle.value)
self.assertEqual(active_min_rating.value, 3.9)
self.assertEqual(active_max_reviews.value, 100)
# test_unlicensed_option_disabled_but_base_search_still_works
self.assertTrue(rating_toggle.disabled)
self.assertEqual(len(app.dataframe), 1)
# test_toggle_off_does_not_reclassify_filtered_ids_after_revocation
self.assertEqual(app.session_state['no_website_place_ids'], ())
self.assertIsNone(app.session_state['no_website_result_origin'])
self.assertEqual(len(app.get('iframe')), 0)
# test_failed_or_empty_new_search_clears_ids_and_origin
self.assertEqual(app.session_state['no_website_place_ids'], ())
self.assertIsNone(app.session_state['no_website_result_origin'])
# test_revocation_during_html_blocks_both_report_and_reference_delivery
self.assertEqual(len(app.get('iframe')), 0)
self.assertEqual(len(app.get('download_button')), 0)  # percorso filtrato
self.assertNotIn('provider-secret-sentinel', repr(app.session_state))
# test_valid_download_contains_real_xlsx_and_no_provider_metrics
self.assertEqual(reference_columns(decoded_iframe_bytes), ['Place ID', 'Link Google Maps'])
self.assertTrue(website_report_reopens_with_expected_columns)
```

Testare modalità cambiata/rerun/prepare dopo scadenza o rimozione permesso, preflight UI valido seguito da rifiuto al click Avvia, e VIEW negato subito prima del dataframe. Dopo toggle off gli ID rimangono protetti finché accesso valido; nuova ricerca base sostituisce origine con `None`. Verificare ZIP/metadata e stato sessione senza metriche; guard runtime non è serializzato né rappresentato come claim/token. Mantenere i test base dei riferimenti invalidi/>10.000 senza nascondere il dataframe.

- [x] **Step 2: RED**: `& $ratingUv run --frozen --group test python -m unittest tests.test_rating_filter_ui -v`; nuovi controlli/guard/rerun mancanti.
- [x] **Step 3: Implementare controlli e gestione origine**: chiamata comune fuori dal blocco solo-with-site, niente attivazione al cambio modalità; passare criteri al factory, memorizzare origine soltanto dai risultati del motore. VIEW prima di ogni rendering/consegna; `LicenseError` con messaggio sicuro, reset su nuovo avvio o rifiuto, nessun fallback. Rerun base non richiede licensing discovery.
- [x] **Step 4: Implementare consegne inline**: reference panel usa helper e verifica doppia; report sito filtrato usa `DataExporter.export_bytes(..., origin=...)` e helper con `origin.require_view`, senza scrivere un file statico/download_button. Report sito base mantiene il percorso corrente. Non conservare bytes nei rerun; una pagina/file già validamente consegnata non viene revocata retroattivamente.
- [x] **Step 5: GREEN**: `& $ratingUv run --frozen --group test python -m unittest tests.test_rating_filter_ui tests.test_reference_export_ui tests.test_feature_license_ui -v`; tutti PASS. Verifica browser locale con fixture e licenza effimera: toggle nelle due modalità, risultati attesi, download XLSX riaperto, scadenza e nuova ricerca base. Nessuna API Google/LLM a pagamento per lo smoke; registrare eventuali limiti dell'effettivo salvataggio browser.
- [x] **Step 6: Commit e push major** selettivi: `feat(gui): expose guarded rating filters and derived downloads`; `git push origin codex/licensed-rating-filters`.

### Task 6: Attivazione, verifica completa e pubblicazione della PR draft

**Files:** modificare `src/licensing/catalog.py`, `tests/test_feature_license_contract.py`, `README.md`, `docs/RIPRESA_MODERNIZZAZIONE_2026-10-08.md`, spec/piano; creare `docs/RATING_FILTER_IMPLEMENTATION_REVIEW.md`; aggiornare i test integrazione GUI/CLI del modulo per usare il catalogo produttivo.

**Interfaces:** catalogo produttivo `discovery.rating_filters.module_status == 'available'`; ID, permissions e MFA restano come nella spec. `export.no_website` disponibile, `diagnostics.full` pianificato; nessun altro cambio dei contratti licensing/server.

- [x] **Step 1: Scrivere gate di disponibilità reale**:

```python
# test_catalog_exposes_completed_rating_filters_and_reference_export
self.assertEqual(catalog.get('discovery.rating_filters').module_status, 'available')
self.assertEqual(catalog.get('export.no_website').module_status, 'available')
self.assertEqual(catalog.get('diagnostics.full').module_status, 'planned')
self.assertEqual(filters.execute_permissions, (Permission.START_JOB,))
self.assertEqual(filters.view_permissions, (Permission.VIEW_RESULTS,))
self.assertFalse(filters.execute_mfa or filters.view_mfa)
# test_gui_cli_use_real_catalog_and_signed_license (nessun override available)
self.assertEqual(filtered_cli_exit_code, 0)
self.assertFalse(filtered_gui_toggle.disabled)
self.assertTrue(server_worker_remains_pipeline_not_configured)
```

Adattare il test esistente che considera entrambi i moduli ancora planned; conservare una prova esplicita che diagnostics pianificato non sia eseguibile.

- [x] **Step 2: RED**: `& $ratingUv run --frozen --group test python -m unittest tests.test_feature_license_contract tests.test_rating_filter_cli tests.test_rating_filter_ui -v`; disponibilità reale fallisce finché planned.
- [x] **Step 3: Attivare e documentare** il solo modulo completato. README con base/filtrato e flag, confronti/default, campi effimeri, doppio permesso export, limiti di scadenza/offline, costi Google secondo deployment e roadmap legale già aperta; nessuna dichiarazione di release commerciale. Report persistente con evidenze, decisioni/limiti, review e SHA; stato milestone/spec/piano aggiornato alle prove effettive.
- [x] **Step 4: Verifica locale finale**: eseguire e leggere `& $ratingUv lock --check`, `& $ratingUv run --frozen --group test python -m compileall -q src tests main.py`, `& $ratingUv run --frozen --group test python -m unittest discover -s tests -v`, `git diff --check`, secret scan Gitleaks. Tutto PASS; skip locali PostgreSQL/container esplicitati, non contati come prove passate. Conservare assenza NLTK e test browser crawler della base; niente nuove esclusioni o rigenerazione lock immotivata.
- [x] **Step 5: Review indipendente fresca** dell'intero diff dalla base `6491f66da0f7fd956b88626a02dfca609ca7437e`, secondo executing-plans/requesting-code-review; modello disponibile più capace `gpt-6-astra`, effort high, contesto fresco. Fornire spec/piano, evidenze e superfici guard/provider/artefatti/rerun. Valutare ogni rilievo; correzioni motivate con RED→GREEN e controlli interessati, poi suite completa se codice cambiato. Registrare rilievi minori/decisioni nel report, senza nascondere limiti.
- [x] **Step 6: Commit/push e PR draft**: commit selettivo `feat: enable verified licensed rating filters`, push branch autorizzato; creare PR draft base `codex/remove-unused-nltk`, corpo in file UTF-8 con problemi/risultato/test/limiti attuali, poi allegarla alla chat con `attach_artifact`. Nessun merge o rilascio.
- [x] **Step 7: Gate GitHub dell'HEAD finale**: controllare CI Python 3.10–3.13, PostgreSQL, container, browser crawler e Security (Gitleaks, audit vulnerabilità/SBOM/licenze). Se falliscono, diagnosticare/correggere/riverificare e attendere nuovi gate sul nuovo SHA; non attribuire al nuovo codice il verde di una base precedente. Completare il report e la consegna soltanto con evidenza precisa; se una prova esterna non è ottenibile, lasciare esplicito il lavoro residuo senza dichiarare completamento.

## Autorevisione e approvazione

Autorevisione inline completata il 10 ottobre 2026: criteri/confine dati (Task 1/2), autorizzazione fresca e server (Task 1/2), origine/pipeline/export (Task 3), CLI (Task 4), UI/sessione/consegna (Task 5), disponibilità/gate/documentazione (Task 6). Le cinque condizioni Review Focus hanno prove nei task proprietari. Firme e proprietà sono uniformi; nessun passaggio richiede un nuovo consenso sulle scelte di prodotto già approvate. Il piano contiene interfacce, asserzioni e comandi, senza trascrivere corpi di implementazione.

- [x] Specifica scritta approvata dal proprietario.
- [x] Piano scritto e autorevisionato.
- [x] Piano revisionato e approvato dal proprietario (10 ottobre 2026); metodo native mantenuto.
- [x] Esecuzione dei sei task, review e gate finali (PR draft #10).
