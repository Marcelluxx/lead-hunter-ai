# Review dell'indice markup spiegabile

14 ottobre 2026. [PR #16](https://github.com/Marcelluxx/lead-hunter-ai/pull/16),
base develop `3a8c3df`, branch codex/explainable-markup-score. Il proprietario
ha scelto esplicitamente un indice DOM affiancato al voto AI.
[Specifica](superpowers/specs/2026-10-13-explainable-markup-score-design.md) e
[piano](superpowers/plans/2026-10-13-explainable-markup-score-implementation-plan.md).

## Implementazione e prove

Tre task inline con TDD: rubrica/validator RED8, GREEN22 con regressioni DOM;
runtime RED5 (due failures/due errors, preflight già verde), GREEN29; delivery
RED8, GREEN44 con SDK, SQL, HTTP ed Excel riaperto. I contatori/hashes/data
alterati sono rifiutati; zero resta numerico, null vuoto, storico unavailable.
Le colonne precedenti conservano posizione. Snapshot e gate precedenti restano
attivi sui nuovi dati. Nessuna dipendenza, migrazione o chiamata provider nuova.

Durante Task2 un commit/claim precedette l'ispezione dell'intero output: un test
usava il livello sbagliato dell'envelope diagnostico (`data` invece di
`payload/data`). Il gate task-done fallì senza registrare completamento.
Asserzione corretta dopo aver letto il formato reale, nuova verifica29/29 PASS,
nessuna modifica prodotto necessaria per quel fallimento. Completamento
registrato soltanto dopo la correzione.

Suite prima della review: **432/432 PASS**, nessuno skip, **301.587 secondi**,
PostgreSQL17 con ruoli app/worker, Chromium reale con trasporto fixture e build
di distribuzione. Lock, compileall, diff e Gitleaks PASS. Tutti gli otto gate
GitHub PASS sullo SHA4382eb1, CI38548658094/Security38548658079.

## Review indipendente

Un solo reviewer fresco gpt-6-astra/high, read-only, senza child o seconda
review, sul range3a8c3df..4382eb1. Diff completo e tutti i Ruling esaminati;
cinque classi Review Focus coperte. Verifica indipendente21/21 test score/core/
runtime/delivery PASS40.115 secondi; diff check PASS, checkout pulito. Nessuna
ripetizione della suite completa. Nessun Critical o Minor; un Important P2.

Confermati aritmetica frazionaria/half-up, pesi uguali tra regole applicabili e
contatori per elemento all'interno della regola; zero/null/NA distinti. Binding
canonico include misure e metadata, builder indipendente dal modello,
ricomputazione prima di persistence/API/export e firme DTO/colonne compatibili.
Probe aggiuntivi del reviewer confermano che cambiamenti coerenti di DOM/score
o score corrotto interrompono lo stream prima del secondo chunk.

Important: il tester mostrava100/100 senza stato/copertura. Con20 pagine
eleggibili, una osservata e19 sconosciute, l'operatore poteva associare il
numero a tutte le pagine raccolte. Il tester restituisce None e il JSON storico
a campi selezionati non contiene questi dati: la copertura non era disponibile
nel risultato visibile, nonostante fosse correttamente presente nel report.

Unico fix pass: regressione per1/20 osservate e0/20, output console e report
testuale; RED con entrambi i casi falliti, poi GREEN. Il tester ora mostra
stato completo/parziale/non disponibile, osservate/eleggibili, inconclusive e
omesse tramite log_both. JSON storico preservato; formula, pesi e provider
invariati. Verifica mirata22/22 PASS9.530 secondi. Nessuna seconda review.

## Decisioni e costi

Tutte le decisioni del ledger e tutte le tre voci effettivamente lasciate fuori
giudizio dal reviewer sono riportate in ordine.

| N | Decisione e motivo | Costo/limite residuo |
|---|---|---|
| S1 | Delega ordinaria spec/piano auto-revisionati ed esecuzione inline; scelta esplicita dell'indice separato | Eventuale revisione ordinaria del design; nessun acquisto/deployment |
| S2 | Nove pesi1 e contatori per elemento dentro la regola, media esatta delle applicabili; rubrica iniziale trasparente | Benchmark futuro potrebbe richiedere nuova versione di pesi/formula |
| S3 | Gold set umano e calibrazione sono successivi; fixture non spacciate per dati revisionati | Indice non calibrato, non sostituisce giudizi di qualità |
| S4 | Scratch/worktree preservati dopo precedente rifiuto di cleanup; nessun retry/bypass | Cartelle temporanee ignorate restano locali |
| T3 | Fixture storiche DOM rimuovono anche il nuovo score; un indice presente richiede il report sorgente attuale | Sorgenti mancanti/corrotte bloccano l'indice fino a riparazione |
| F1 | Predittività commerciale/accessibilità di pesi e predicati rinviata al benchmark umano, come dichiarato | Non si promette correlazione con qualità commerciale o compliance |
| F2 | Database fidato e niente HTML persistito; tampering coordinato DOM/score/prove fuori dalla ricomputazione semantica disponibile | Alterazioni coerenti di tutti i dati SQL non dimostrabili dal solo DB |
| F3 | Archivio diagnostico redatto non è input lossless per ricomputazione; percorsi autorevoli sono persistence/API/export | Hash/campi trasformati nella diagnostica non garantiscono ri-validazione da quel solo archivio |

Minori rinviati: nessuno individuato. L'unico Important è corretto con test
RED→GREEN; i limiti del contratto non sono certificazioni o difetti mascherati.

## Chiusura

Suite finale dopo l'unico fix pass: **433/433 PASS**, nessuno skip,
**182.886 secondi**, PostgreSQL17/Chromium/build di distribuzione. Lock,
compileall e diff check nuovamente PASS. Nessun ulteriore cambiamento al codice
dopo questa verifica, né seconda review.

La PR richiede tutti gli otto gate sull'esatto HEAD prima della consegna come
pronta; stato corrente nella PR. Merge separato su richiesta del proprietario.
Ruling persistiti qui, scratch ignorato e worktree condiviso preservati.
