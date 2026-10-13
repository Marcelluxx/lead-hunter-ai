# Controlli deterministici DOM — primo insieme

13 ottobre2026. Base developf5c6c55, branch codex/deterministic-dom-checks.
Mandato: implementare il sottoprogetto proposto, sotto delega autonoma già
confermata. Percorso architetturale, autorevisione spec/piano, esecuzione native,
test prima del codice e una review fresca dell'intero branch.

## Intento e scelta

Produrre misure ripetibili di markup, con origine verificata, per i report locali
e server. Non alterare voto AI, filtri, licenze, permessi o quote; calibrazione e
benchmark successivi. L'AI può spiegare osservazioni limitate, non dichiarare
automaticamente verificata una diagnosi o un'assenza sull'intero sito.

Alternative: ricavare struttura dal Markdown (scartata: head/attributi perduti);
effettuare nuove richieste/probe browser per ogni controllo (rinviata: altra fase
operativa); riusare HTML già raccolto con snapshot bounded (scelta).
Nessuna dipendenza nuova, provider reale, richiesta aggiuntiva o prompt privato
pubblicato. Metadata pubblici solo numerici/enum/hash/URL redatti, mai HTML o label.

## Snapshot e ammissione

DomPageEvidence.capture(html, page_evidence) registra source_url originale,
markdown_sha256, dom_sha256, retrieved_at UTC, html privato (repr=False),
failure_code. Hash UTF8 errors=replace. Cap HTML250000 byte per snapshot; fuori
cap mantiene hash ma html=None/failure_code dom_too_large. HTML assente produce
dom_unavailable. MIME diverso da text/html/application/xhtml+xml o vuoto produce
unsupported_content_type; PageEvidence invalida produce page_not_auditable.
Snapshot in CrawlResult.dom_evidence, nuovo campo aggiunto alla fine; solo pagine
con evidenza Markdown valida raccolte dal crawler, homepage e interne.

Un documento da analizzare richiede html/head/body e chiusura html, senza
troncamenti; frammenti sono inconclusive/incomplete_document. Max20000 tag per
pagina, altrimenti dom_node_limit; budget analisi totale2000000 byte per crawl,
altrimenti analysis_budget per quella pagina. Questi limiti non eliminano lead.
Nessuna nuova misura di rete, CSS computato, shadow DOM o iframe.

## Nove regole versione1

Ogni regola restituisce matched/total interi: total0 -> not_applicable;
matched==total -> pass; altrimenti fail. Pass/fail riguarda solo il predicato
di markup specificato e il DOM ammesso, non qualità complessiva/compliance.

- title_text: primo title in head con testo non vuoto; total1.
- meta_description: almeno una meta name=description in head con content non vuoto; total1.
- h1_text: almeno un h1 esposto con testo non vuoto; total1.
- language_declaration: lang non vuoto sul root html; total1, nessuna validazione lingua.
- viewport_declaration: almeno una meta viewport in head con content non vuoto; total1, non prova responsive.
- image_alt_attribute: img esposti con attributo alt presente, anche vuoto decorativo; total numero img, non significato dell'alt.
- link_label_markup: a esposti con href, testo esposto/aria-label/title, aria-labelledby univoco con testo, o immagine discendente con alt non vuoto; total numero a con href.
- text_control_label_markup: input text/email/password/tel/search/url/number (default text), textarea/select esposti con aria-label, aria-labelledby univoco testuale o label esplicito annidato/for su ID univoco; placeholder non conta; total numero controlli selezionati, non tutti i controlli HTML.
- contact_scheme_link: almeno un a esposto con mailto/tel e path non vuoto; total1, presenza sintattica, non validità/deliverability.

Script/style/template/noscript/commenti non forniscono testo. hidden, aria-hidden=true,
display:none e visibility:hidden inline escludono elementi/descendenti dai contatori
esposti; regole CSS esterne non valutate. Target testuali di aria-labelledby e label
for possono essere nascosti; è relazione di markup, non algoritmo AccName completo.
Testo di soli spazi/control/format Unicode non conta. ID duplicati non provano
associazione univoca. Costruire indici e text flags in passaggi O(N), non ricerche
di discendenti/label ripetute per ogni controllo.

## Report pubblico

dom_report schema_version1, rules_version '1', scope collected_html_dom,
method dom_rules, status complete/partial/unavailable, coverage con eligible_pages,
inspected_pages, inconclusive_pages, omitted_pages. Massimo20 pagine eleggibili.
pages: lista di id d_SHA256(URL originale+hashDOM), source_url pubblico,
dom_sha256 opzionale, markdown_sha256, retrieved_at, status observed/inconclusive,
reason (None per observed; reason enum per inconclusive), checks (nove regole
per observed, oggetto vuoto per inconclusive). Record storico senza report usa
coverage0/status unavailable; nessuna prova retroattiva.

Usare la stessa proiezione URL del report citazioni: query/fragment/userinfo
rimossi, path sensibile riconoscibile mascherato. Report UTF8<=24000 byte;
quando pagine aggiuntive non entrano, ometterle esplicitamente tramite coverage,
senza troncare checks o falsificare assenze. Conteggi matched<=total<=1000000,
outcome derivato, tipi e chiavi stretti; metadata/hash/time verificati.

## Binding e runtime

build_dom_report(crawl) seleziona l'ultimo snapshot per URL, confronta MD hash e
timestamp con PageEvidence valida e hash DOM con HTML corrente. Snapshot corrotto
-> AuditValidationError dom_evidence_invalid, non un report falso. Snapshot vecchi
con URL duplicato possono essere superseduti dall'ultimo valido; le pages correnti
restano autorità. Compatibilità: se manca snapshot homepage, raw_html_home e suo
hash (se presente) danno solo quella pagina; altre restano dom_not_collected.
Dato un insieme esplicito di snapshot, non usare raw legacy per sovrascriverlo.

VerifiedLead.dom_report aggiunto in coda; builder lo calcola dal crawl ignorando
dom_report eventualmente scritto dal modello. Provenienza website_dom_checks,
DOM hash della prima pagina disponibile, separato da hash MD delle citazioni.

audit_with_dom_report(auditor, *, dom_report, **legacy_arguments) passa report solo
a auditor.supports_dom_report=True; vecchi adapter senza capability continuano
con la firma precedente. LeadAuditor aggiunge parametro opzionale dom_report,
valida schema e lo inserisce come JSON non fidato prima del catalogo citazioni
(ORIGINAL_AUDIT_EVIDENCE resta ultimo). Prompt provider privato invariato.
Main, handler server, runner diagnostico e tester usano helper e report calcolato.
Nessuna chiamata LLM aggiuntiva; findings AI restano inconclusive.

## Persistenza e consegna

Attributo dom_report JSON bounded nelle tabelle esistenti, senza migrazione.
EvidenceRows per ogni URL/hash DOM disponibile; snapshot HTML mai persistiti.
API espone oggetto dom_report separato, validato e collegato a righe URL/hash.
Corruzione o prova mancante produce errore sicuro job_dom_report_invalid.
Colonna DOM Report/dom_report aggiunta alla fine di XLSX locale/server, senza
spostare campi precedenti. Snapshot/stream, licenze a scadenza, privacy e workspace
continuano a governare tutti i campi nuovi. Nessuna nuova esclusione dei lead.

## Accettazione

TDD fixture complete/incomplete/missing/MIME/oversize/budget, tag inerti/nascosti,
Unicode vuoto, ID duplicati, label/alt, URL malformati, staleness e redirects.
Chromium reale homepage/interna con trasporto fixture. SDK reale con trasporto
mock verifica fatti senza HTML né aumento chiamate e senza autorità al modello.
SQL/API/XLSX riaperti, storico, corruzione e limiti20/24000. Suite completa con
PostgreSQL17/Chromium/distribuzione, commit/push major, PR, review fresca e gate
GitHub esatto HEAD. Merge separato su richiesta del proprietario.
