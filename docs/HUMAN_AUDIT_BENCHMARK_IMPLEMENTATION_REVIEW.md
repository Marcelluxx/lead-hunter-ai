# Benchmark umano offline — implementazione e review

17 ottobre 2026. [PR #17](https://github.com/Marcelluxx/lead-hunter-ai/pull/17),
branch `codex/human-audit-benchmark`, base develop `f477815`.
Specifica/piano del15 ottobre in docs/superpowers; esecuzione native sotto delega
autonoma e scelta esplicita di qualità sito e priorità intervento separate.

## Risultato

Package offline per dataset versionati da snapshot o risultati server già
autorizzati, schede cieche ai voti automatici e confronto descrittivo con voto AI
e indice DOM. Schema rigoroso, hash/versioni, null distinti da zero, rubriche
separate, metriche con ranghi pari e conteggi dei mancanti/copertura.
CLI senza provider, credenziali o DB; output nuovi esclusivi e bounded.
`.benchmark-data` esclusa da Git/Docker, verificata dal gate immagine reale.

Non è stata raccolta una valutazione umana reale né calibrata una rubrica.
Gli input dei test sono sintetici. Il riferimento umano rimane provvisorio;
le metriche non sono certificazioni e le identità revisore non sono autenticate.

## Prove dei tre task

- Dataset/revisioni: RED7 per contratti assenti, GREEN7/7; baseline mirata28/28.
  Suite440 eseguiti,419 passati/21 skip ambientali espliciti,305.387s.
- Metriche: RED6 test/8 assert per modulo assente, GREEN13/13 con contratti.
  Suite446/446 senza skip242.589s con PostgreSQL17, Chromium e distribuzione.
- CLI/consegna: RED8; limite cumulativo lettura e gate dati benchmark
  riprodotti prima dei fix. GREEN24/24, incluso adapter da vera risposta HTTP
  autenticata del server e JSON riaperti. Suite456/456 senza skip390.637s,
  PostgreSQL17 con ruoli owner/app/worker, Chromium e build Docker.
- Lock, compilazione, diff e Gitleaks prima dei commit: PASS. Commit funzionali
  `258455d`, `524d754`, `8033524`. Otto gate sull'esatto8033524 PASS:
  [CI38726517000](https://github.com/Marcelluxx/lead-hunter-ai/actions/runs/38726517000),
  [Security38726517048](https://github.com/Marcelluxx/lead-hunter-ai/actions/runs/38726517048).

## Review indipendente e singolo passaggio correttivo

Il primo avvio del reviewer terminò per limite di utilizzo del servizio, senza
un verdetto. Lo stesso reviewer è stato ripreso il17 ottobre e ha completato
la review fresca read-only dell'intero range `f477815..8033524`, specifica,
piano e tutti i ruling. Nessun sub-reviewer o secondo parere.

Verifica indipendente:22/22 test benchmark PASS13.769s; confronto indipendente
Spearman su729 combinazioni con pari/costanti PASS; roundtrip dataset con URL
redatto PASS. Il reviewer non ha ripetuto la suite completa. Confermati binding,
storico unavailable, scale separate, peso per sito, mancanti/null, proiezione
minima, limite letture e scrittura esclusiva.

Nessun Critical. Il reviewer ha classificato Minor un problema delle date:
`reviewed_at` richiedeva identica rappresentazione testuale dopo normalizzazione,
rifiutando UTC validi come Z e frazioni .123+00:00. L'autore lo ha rivalutato
Important per l'effetto sull'uso: una scheda interamente compilata con date ISO
ordinarie non poteva essere valutata e riceveva un generico errore di contratto.

Root cause: il confronto `normalized == original` imponeva una precisione e un
suffisso non richiesti all'operatore. Riproduzione con
`test_review_dates_normalize_iso_spellings_without_mutating_human_files` e
flusso CLI aggiornato con Z: RED2 test/7 fallimenti (sei sottocasi date e CLI).
Fix: normalizzare le date con fuso esplicito su copia indipendente, mantenendo
binding e controlli temporali. Z, frazioni e offset sono accettati; date naive
o precedenti al campione restano rifiutate; file del revisore non modificato.
GREEN25/25 test contratti/metriche/CLI/gate immagine5.835s. Nessuna seconda review.

Suite completa dopo il fix: **457/457 PASS**, nessuno skip, **128.022s**,
con PostgreSQL17 owner/app/worker, Chromium e distribuzione Docker abilitati.
Lock, compilazione, diff e Gitleaks nuovamente PASS. Nessun cambiamento al
codice dopo questa verifica. Otto gate sull'esatto HEAD finale obbligatori
prima della consegna come pronta; stato corrente consultabile nella PR.

## Tutte le decisioni e i costi residui

| N | Decisione e motivo | Costo se errata / limite |
|---|---|---|
| S1 | Autorevisione spec/piano sotto delega autonoma, scale separate scelte esplicitamente, metodo native | Eventuale revisione ordinaria del design; nessun acquisto/deployment implicito |
| S2 | Strumento offline su file già autorizzati, senza provider/DB o nuovi diritti di licenza | Futura integrazione UI/export richiede progetto e autorizzazioni propri |
| S3 | human-site-1 qualità1–10 e priorità0–3 indipendenti, giudizi provvisori | Modifica delle ancore richiede nuova rubrica; non è gold set adjudicato |
| S4 | Scratch e worktree condiviso preservati dopo precedente rifiuto automatico della pulizia | Cartelle temporanee ignorate restano locali |
| T2 |32MiB anche per insieme packet; distanze pairwise tramite valori ordinati senza lista quadratica | Banche molto grandi richiedono batch minori o formato streaming futuro |
| T3 | Budget cumulativo applicato durante la lettura, prima di caricare tutti i file | Spazi/pretty printing possono richiedere batch più piccoli |
| F1 | Predittività, campionamento rappresentativo, adjudication e calibrazione rinviati ai dati reali | Le metriche attuali non sostengono una promessa di qualità commerciale |
| F2 | Identità reale e rehash coordinato restano sotto fiducia nell'operatore | Falsificazione deliberata della provenienza umana non rilevata dai digest |
| F3 | Nessuna equivalenza provata tra crawl storico e sito live senza originali conservati; changed_site/unassessable e protocollo espliciti | Deriva temporale può alterare il confronto |
| F4 | UI clienti, raccolta provider e nuove superfici licensing fuori dal tool offline | Estensioni richiedono design/controlli dedicati |
| F5 | Date con qualsiasi fuso esplicito normalizzate UTC invece di precisione testuale obbligatoria non documentata | Accettate rappresentazioni più ampie ma non ambigue; chronology check preservato |

Le quattro voci F1–F4 corrispondono a tutte le aree che il reviewer ha lasciato
fuori giudizio; nessuna è omessa. Minor differiti: nessuno; l'unico Minor del
reviewer è entrato nel passaggio correttivo come Important rivalutato.

## Consegna

Manuale: [HUMAN_AUDIT_BENCHMARK.md](HUMAN_AUDIT_BENCHMARK.md).
PR verso develop, merge separato su richiesta del proprietario. Non promossa
in main e nessun deployment produttivo. Dati umani reali, protocollo del campione
e successiva calibrazione sono ancora attività della milestone qualità audit.
