# Review dei controlli DOM

13 ottobre 2026. PR #15, base develop `f5c6c55`, branch
`codex/deterministic-dom-checks`. Piano e specifica:
[implementazione](superpowers/plans/2026-10-13-deterministic-dom-checks-implementation-plan.md),
[contratto](superpowers/specs/2026-10-13-deterministic-dom-checks-design.md).

## Prove dell'implementazione

Tre task eseguiti inline secondo il piano. Capture/analyzer/schema RED11 e
GREEN18 con regressioni citazioni; root inerte e commento finale/falsa chiusura
coperti prima delle correzioni. Binding/runtime RED9, GREEN37 con Chromium
reale; core più integrazione GREEN49. Consegna RED6, GREEN41, comprendendo SDK,
worker, SQL, HTTP ed Excel riaperto. Conservata la precedenza del vecchio errore
`crawl_dom_evidence_changed` nella verifica della homepage.

Suite iniziale: 409/409 PASS, nessuno skip, 151.110 secondi. PostgreSQL17 con
ruoli applicazione/worker, Chromium reale su trasporto fixture e build di
distribuzione. Lock, compileall, diff check e Gitleaks staged PASS. Gli otto gate
GitHub sull'implementazione `0abd6ef` sono PASS, CI38453135587 e
Security38453135489. Nessuna chiamata pagata o credenziale reale inventata.

## Review indipendente

Un solo reviewer fresco `gpt-6-astra/high`, read-only, senza subagent o seconda
review, sul range `f5c6c55..0abd6ef`. Ha letto spec/piano/ledger/diff, esaminato
le cinque classi Review Focus e verificato 20 test mirati PASS. Non ha ripetuto
la suite completa. Valutazione: pronta con correzioni, nessun Critical o Minor.

Punti verificati: capture bounded, regole deterministiche, binding MD/DOM/tempo,
ricomputazione indipendente dal modello, firme degli auditor compatibili, API ed
Excel append-only. Report pubblico con contatori e metadata redatti, esclusioni
inconclusive e controllo delle prove SQL. Gate di esecuzione/licenza/workspace/
privacy/snapshot preservati.

Due Important P2 confermati con riproduzioni:

1. Rimuovere script/style/template/noscript prima dell'indice perdeva i loro ID.
   Un ID condiviso con un target testuale appariva univoco e produceva falsi
   pass in aria-labelledby e label for. Nuova regressione per quattro tipi di
   tag, link e controlli: RED, poi GREEN. Ora tutti gli ID rimangono indicizzati
   e flag separati escludono testo/elementi inerti dai predicati.
2. extract/decompose su molti fratelli causava scansioni quadratiche BS4,
   violando O(N) entro i limiti ammessi. Probe reviewer: 1000/9000 coppie di
   elementi, 0.072/3.148 secondi. Regressione strutturale misura il lavoro di
   attraversamento delle liste della dipendenza, senza soglie temporali fragili:
   RED1408132 letture oltre budget90120; GREEN dopo aver eliminato le rimozioni.
   Probe autore dopo fix: stessi 24039/216039 byte, 0.043/0.425 secondi; tutte
   le nove regole disponibili. Test mirati complessivi28/28 PASS4.126 secondi.

Unico fix pass eseguito dall'autore, nessuna seconda review. Suite e SHA finali
sono registrati nella chiusura sotto.

## Decisioni e costo

Tutte le decisioni del ledger, incluse tutte le voci che il reviewer ha elencato
come Declined to judge, sono riportate in ordine. Le voci già esaminate senza
difetti confermano il contratto: non sono lacune di test o difetti rinviati.

| N | Decisione / motivo | Costo se errata o limite residuo |
|---|---|---|
| S1 | Delega autonoma: autorevisione spec/piano ed esecuzione inline senza ulteriori conferme ordinarie | Eventuale revisione del design; nessun acquisto/deployment |
| S2 | Primo insieme limitato a nove predicati di markup; AI inconclusive | Servono altri controlli e calibrazione per giudizi complessivi |
| S3 | Riutilizzare HTML raccolto, entro limiti, senza nuove richieste | DOM grandi/parziali/nonHTML restano senza misure |
| F1 | Confermata autorizzazione autonoma dal reviewer | Eventuali scelte ordinarie da rivedere |
| F2 | SEO e accessibilità complete rimangono fuori dal contratto | Nessuna certificazione complessiva |
| F3 | Associazioni testuali nascoste ammesse come markup, AccName completo escluso | Il nome accessibile effettivo può differire |
| F4 | CSS esterno/computato e override di visibilità esclusi | Esposizione reale nel browser può differire |
| F5 | Alt vuoto decorativo soddisfa presenza dell'attributo | Qualità semantica alt non determinata |
| F6 | Lang e viewport sono dichiarazioni, non correttezza linguistica/responsive | Lingua e layout mobile restano da verificare |
| F7 | Mailto/tel con path conta solo sintassi | Destinatario potrebbe non essere valido/raggiungibile |
| F8 | DOM mancante/MIME ignoto inconclusive, verificato | Copertura ridotta |
| F9 | Envelope completo e commenti finali verificati; frammenti/falsa chiusura esclusi | Non equivalenza universale a ogni parser browser |
| F10 | Limiti byte/nodi/analisi mantengono unknown; complessità corretta nel fix pass | Pagine escluse richiedono altra raccolta/analisi |
| F11 | Testo hidden/inert gestito; perdita ID trasformata in finding e corretta | Altre semantiche browser richiedono nuove regole |
| F12 | Spazi/control/format Unicode esclusi dai predicati testuali, verificato | Non valuta significato o leggibilità dei glifi |
| F13 | Ultimo snapshot per URL legato al MD/tempo corrente, verificato | Crawl incoerenti rifiutati e da ripetere |
| F14 | Corruzione DOM/MD/tempo rifiutata con test | Dati alterati non consegnabili |
| F15 | Legacy fallback solo homepage, niente override su snapshot espliciti | Pagine interne legacy restano unknown |
| F16 | Misure applicative prevalgono su dom_report del modello, verificato | Il modello non può personalizzare le misure |
| F17 | Auditor custom riceve report solo con capability esplicita, verificato | Adapter precedenti devono optare per il nuovo contesto |
| F18 | Payload nuovo solo contatori/metadata redatti; catalogo originale ultimo | Redazione URL a pattern, non anonimizzazione universale dei campi legacy |
| F19 | Overflow Unicode omette pagine intere senza perdere lead, verificato | Report parziale anche su crawl completo |
| F20 | Record storico senza report unavailable, verificato | Nessuna prova retroattiva |
| F21 | SQL/schema/hash non coerenti producono errore sicuro, verificato | Consegna bloccata fino a nuova prova valida |
| F22 | Database fidato; HTML non persistito per ricomputazione semantica dopo arbitrario tampering SQL | Tampering coerente di report e prove non dimostrabile dal solo DB |
| F23 | API/Excel append-only e attributi precedenti stringhe, verificato | Client con schema/numero colonne rigidamente fissato da aggiornare |
| F24 | Gate licenze/privacy/workspace/snapshot preservati e coperti dalle regressioni | Nessuna nuova valutazione universale delle policy precedenti |
| F25 | Calibrazione e voti futuri del modello rinviati | Voto AI ancora variabile/non calibrato |
| F26 | Tester riceve contesto DOM; file storico a campi selezionati invariato | Quel file non diventa un nuovo report DOM completo |
| F27 | Reviewer non esegue provider live/credenziali/deployment/gate GitHub; autore verifica CI separatamente | Verifica operativa su credenziali reali rimane successiva |
| F28 | Edit concorrente solo manuale citazioni: colonna Audit non più finale; review pinned al suo SHA | Eventuale correzione documentale, nessun effetto sul codice |
| F29 | Scratch e worktree preservati: precedente cleanup rifiutato dalla policy, nessun nuovo tentativo o bypass | Cartelle temporanee ignorate restano locali |

Minori rinviati: nessuno individuato in questo sottoprogetto. I limiti sopra
sono scelte del contratto; i due Important entrano nell'unico fix pass.

## Chiusura

Suite finale dopo l'unico fix pass: **411/411 PASS**, nessuno skip,
**142.394 secondi**, con PostgreSQL17, Chromium e build di distribuzione.
Lock, compileall e diff check nuovamente PASS. Due regressioni nuove provano
entrambe le correzioni, oltre a tutte le regressioni precedenti.

La [PR #15](https://github.com/Marcelluxx/lead-hunter-ai/pull/15) richiede tutti
gli otto gate GitHub sull'esatto HEAD prima della consegna come pronta;
lo stato corrente è disponibile nella PR. Merge separato su richiesta del
proprietario. Decisioni persistite qui, scratch ignorato e worktree preservati.
