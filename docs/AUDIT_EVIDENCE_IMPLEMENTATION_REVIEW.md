# Audit evidence — review e verifica

13 ottobre2026. PR #14 verso develop, branch codex/audit-evidence.
Base4f40a6c3ae91d600c6e9dea99f46dd21b038111b; implementazione
25bb238bed75b76fcae4d008262b7b9f1bd3f5fe. Tre task native completati,
una review indipendente gpt-6-astra/high dell'intero diff, spec, piano e ledger.
Checkout read-only, nessun sub-revisore, nessun provider reale o deployment.

## Risultato

Nessun Critical, Important o Minor. Il revisore ha eseguito indipendentemente
tutti22 nuovi test: PASS, inclusa la catena SDK/worker/SQL/HTTP/XLSX riaperto.
Ha provato234 sostituzioni malformate di campi:232 rifiuti sicuri,2 accettazioni
valide, nessuna eccezione inattesa; Unicode decomposto/ligature non diventano
citazioni di testo normalizzato assente nell'originale. Diff check PASS e checkout
rimasto pulito. Nessuna correzione richiesta o seconda review.

Le citazioni devono esistere nell'originale e nel catalogo effettivamente inviato;
hash e offset originali conservati, timestamp del crawl assegnati prima della
persistenza. Finding LLM sempre inconclusive; legacy uncited distinto da failed.
Il report aggiuntivo attraversa SQL/API/XLSX con schema e limiti controllati e
gate preesistenti. Contratto e limiti nel [manuale](AUDIT_EVIDENCE.md).

## Evidenze di verifica

- Baseline360/360PASS senza skip378.406s, componenti mirati12/12PASS.
- Task1:7 test RED per contratto assente →7/7GREEN.
- Task2:6 test RED (3failure3error) → runtime/regressioni21/21GREEN;
  vero SDK con trasporto mock, originale distinto dalla parafrasi del cleaner.
- Task3:7 test RED (6failure3error) dopo riparazione fixture asyncio →33/33GREEN;
  altri2 casi su path sensibili/limite JSON: core+delivery16/16GREEN;
  task-done35/35PASS dopo tutte le modifiche.
- Suite finale382/382PASS senza skip169.609s: PostgreSQL17 app/worker,
  Chromium e build distribuzione abilitati. Frozen lock, compile e diff PASS;
  Gitleaks staged prima di ogni commit PASS.
- CI38382104396 e Security38382104416 PASS: tutti8 gate sull'esatto
  implementazione25bb238. Gate sul commit documentale finale controllati prima
  della consegna della PR pronta; nessuna affermazione di merge in develop.

Comando suite: uv0.11.15 run --frozen --group test python -m unittest discover -s tests -v,
con REQUIRE_POSTGRES_TESTS=1, LEADHUNTER_BROWSER_TESTS=1, RUN_DISTRIBUTION_BUILD=1
e tre URL Postgres owner/app/worker dell'ambiente di test isolato. Nessuna chiave
provider reale o prompt proprietario usato per le prove.

## Rulings I made — ordine e costo se errati

1. Mandato autonomo già esplicito: autorevisione spec/piano e metodo native,
   senza ripetere le richieste di autorizzazione ordinarie. Costo: revisione
   ordinaria del design; nessun acquisto/deployment esterno implicato.
2. Primo blocco limitato alle citazioni; diagnosi semantica deterministica e
   scoring calibrato seguono dopo. Finding inconclusive e legacy dichiarato
   uncited. Costo: altra milestone prima di considerare dimostrate le diagnosi.
3. validate_public_report aggiunto per validazione strutturale bounded dopo SQL,
   dove il testo originale non è presente; builder resta l'autorità della quote.
   Costo: per una nuova prova delle citazioni dopo storage serve l'originale.
4. Normalizzazione anti-injection/NFKC non autorizza testo diverso dall'originale:
   confronto esatto, eventuale quote respinta. Costo: alcuni testi Unicode o con
   indicatori injection possono non avere citazioni accettabili.
5. Fallimento locale senza voto richiede anche cella Excel senza rosso implicito:
   int(None) lascia il colore ordinario. Costo: chi trattava vuoto come zero nel
   formatter dovrà adattarsi.
6. URL path può contenere email/segreti anche senza query: path riconoscibile,
   incluso percent-encoded, mascherato con /[REDACTED_PATH]. Costo: link profondo
   perso; hash e identificatore dell'originale conservati.
7. Revisore rinvia correttezza semantica, assenza di elementi e calibrazione:
   scelta confermata, matched prova solo la presenza del testo; sintesi/punteggio
   restano AI non calibrati. Costo: usarli come verità richiederebbe la fase qualità
   successiva e revisione umana.
8. Bundle privato/provider live indisponibili: nessuna compatibilità reale inventata;
   adapter pubblico, legacy fallback e SDK controllati. Costo: comportamento del
   bundle/modello operativo va ancora verificato con credenziali autorizzate.
9. Redazione universale/identificatori offuscati/echo di segreti non etichettati:
   resta garanzia a pattern esplicitamente documentata. Costo: nomi o segreti
   non riconosciuti possono richiedere revisione prima della consegna commerciale.
10. Riprovare quote dopo SQL o riconoscere riscritture maliziose strutturalmente
    valide degli estratti: storage fidato, schema bounded e binding URL/hash,
    nessuna promessa di autenticazione del testo contro un DB manomesso. Costo:
    alterazione valida del testo può non essere rilevata senza originale o firma.
11. Privacy di campi legacy e provenienza URL originali: contratti predecessori
    conservati; il revisore ha cercato nuovi bypass, senza identificarne.
    Costo: un riesame completo di quei dati resta distinto da questa proiezione.
12. URL con userinfo: policy più restrittiva esistente conservata, rifiuto prima
    del crawl. Costo: siti che richiedono credenziali nell'URL necessitano di una
    modalità di autenticazione separata, non inclusa in questo blocco.

## Deferred minors

Nessuno individuato in questa review. Le milestone successive sono la verifica
semantica/deterministica e lo scoring misurabile, seguite da benchmark reale;
non sono state dichiarate complete da questa PR.
