# Controlli DOM ripetibili

13 ottobre 2026. Primo insieme di nove misure di markup sulle pagine HTML
raccolte dal crawler. Il voto AI e i filtri di selezione mantengono il comportamento
precedente; benchmark e calibrazione del voto sono i prossimi lavori.

## Lettura dei risultati

Il report `dom_report` usa schema 1, regole versione `1`, metodo `dom_rules` e
scope `collected_html_dom`. Ogni pagina osservata contiene nove contatori
`matched`/`total`: `pass` quando tutti gli elementi esaminati soddisfano il
predicato, `fail` quando almeno uno non lo soddisfa, `not_applicable` con totale
zero. Le regole di presenza hanno totale uno.

| Regola | Che cosa conta |
|---|---|
| `title_text` | Primo title in head con testo non vuoto |
| `meta_description` | Almeno una meta description con content non vuoto |
| `h1_text` | Almeno un H1 esposto con testo non vuoto |
| `language_declaration` | Attributo lang non vuoto sul root html |
| `viewport_declaration` | Almeno una meta viewport con content non vuoto |
| `image_alt_attribute` | Immagini esposte con alt presente, anche vuoto decorativo |
| `link_label_markup` | Link con href e testo, aria-label, title, riferimento testuale univoco o immagine con alt non vuoto |
| `text_control_label_markup` | Input testuali selezionati, textarea e select con label esplicita o associazione aria testuale |
| `contact_scheme_link` | Almeno un link esposto mailto/tel con destinatario non vuoto |

Un alt presente può essere inadeguato; viewport e lang presenti non dimostrano
responsive o correttezza linguistica. Il report non valuta significato dei testi,
validità dei contatti, prestazioni o conformità di accessibilità. Esamina DOM
raccolti, senza nuove richieste e senza certificare assenze sull'intero sito.

Script, style, template, noscript e commenti non forniscono testo. Elementi con
hidden, aria-hidden=true, display:none o visibility:hidden inline e i loro
discendenti sono esclusi dai contatori esposti. Label nascoste referenziate possono
provare un'associazione di markup. ID duplicati non provano associazioni univoche;
placeholder non equivale a label. Gli input coperti sono text, email, password,
tel, search, url e number. CSS esterno/computato, iframe, shadow DOM e l'algoritmo
completo del nome accessibile restano fuori da questo insieme.

## Copertura e limiti

`complete` indica che tutte le pagine eleggibili raccolte sono state osservate;
`partial` indica misure disponibili con pagine mancanti, inconclusive o omesse;
`unavailable` indica nessuna pagina osservata. `coverage` espone pagine eleggibili,
osservate, inconclusive e omesse. I record storici senza report hanno copertura
zero e stato unavailable; non vengono inventate prove retroattive.

Ogni snapshot conserva privatamente al massimo 250000 byte HTML. Documenti
incompleti o senza MIME HTML riconosciuto sono inconclusive, così come quelli
oltre 20000 tag o il budget totale di analisi di 2000000 byte per crawl. Le
cause sono esplicite (`dom_not_collected`, `dom_unavailable`, `dom_too_large`,
`unsupported_content_type`, `page_not_auditable`, `incomplete_document`,
`dom_node_limit`, `analysis_budget`), senza trasformarle in predicati falliti.

Il report copre al massimo venti pagine e 24000 byte UTF8. Le pagine che non
entrano nel JSON vengono omesse interamente e contate in omitted_pages: i limiti
del nuovo report non scartano il lead o troncano le misure.

## Prove e consegna

Il crawler lega ogni snapshot HTML al suo URL originale, hash Markdown e
timestamp di raccolta. Il builder sceglie l'ultimo snapshot per URL, ricontrolla
hash HTML/Markdown e timestamp contro il crawl corrente e ricalcola le misure.
Un report scritto dal modello non sostituisce questi dati. I vecchi crawler
senza snapshot possono fornire soltanto il DOM della homepage; le altre pagine
rimangono dom_not_collected. Gli auditor personalizzati senza capability
`supports_dom_report=True` conservano la firma precedente.

Il report pubblico contiene URL redatti, hash distinti HTML/Markdown, timestamp
UTC, contatori ed enum. Non contiene HTML, title, description, label o destinatari
dei link di contatto. Le regole di proiezione URL sono le stesse delle
[citazioni](AUDIT_EVIDENCE.md): query, fragment e userinfo rimossi, path sensibili
riconoscibili mascherati. Gli altri campi legacy mantengono le proprie policy.

SQL conserva il JSON nelle tabelle esistenti e righe di evidenza URL/hash DOM
per le pagine mantenute con hash disponibile. La lettura verifica schema e
legame alle righe; dati corrotti o prove mancanti producono
`job_dom_report_invalid` senza riportare il contenuto SQL. Il testo HTML privato
non viene persistito; le misure non possono essere ricalcolate dal solo database.

API restituisce dom_report come oggetto separato dagli attributi legacy, che
restano stringhe. Excel aggiunge la colonna DOM Report in locale e
dom_report sul server, senza spostare i campi precedenti. Il successivo
[indice markup separato](MARKUP_SCORE.md) aggiunge altre due colonne in coda.
Licenze a scadenza,
privacy, workspace e controllo dei risultati durante lo streaming continuano a
governare la consegna. L'AI riceve solo queste misure aggiuntive prima del
catalogo delle citazioni, senza nuove chiamate al provider; i findings AI
rimangono inconclusive e il voto non è ancora calibrato.
