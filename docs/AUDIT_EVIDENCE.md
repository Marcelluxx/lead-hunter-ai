# Audit con citazioni controllate

13 ottobre2026. Primo blocco della qualità audit: citazioni, binding al crawl,
persistenza e consegna; benchmark e calibrazione rimangono successivi.

L'audit conserva website_score, diagnosis, site_brief, framework e cold_message.
Aggiunge audit_report schema_version1, con status, findings ed evidence. In API
il report è un oggetto separato per lead; gli attributi precedenti restano stringhe.
XLSX locale e server hanno una colonna finale Audit Report/audit_report in JSON,
senza spostare quelle precedenti. Nessuna migrazione DB necessaria: attributo JSON
bounded nelle tabelle esistenti e righe di evidenza per tutte le pagine referenziate.

## Che cosa viene verificato

Il catalogo inviato al modello deriva dal Markdown originale del crawl, prima
della pulizia/parafrasi AI. Ha identificatori stabili, hash UTF8 SHA256 e URL
pubblici; contenuto massimo12000 caratteri totali e5000 per pagina, massimo20 pagine.
Passa dal sanitizzatore anti-injection e rimane JSON non fidato, mai istruzioni.

Il modello può proporre fino a20 findings, ognuno con categoria, severità,
descrizione e1–3 citazioni. Una quote20–500 caratteri deve comparire esattamente,
case-sensitive, sia nel testo originale sia nel catalogo effettivamente inviato.
Quote inventate, ID estranei, citazioni alla pagina sbagliata, duplicati e campi
di autorità inseriti dal modello vengono rifiutati; i tentativi restano quelli
dell'auditor e del budget esistente. Il provider dei prompt privati rimane invariato.

La citazione pubblica contiene evidence_id, status matched, source_url, hash del
contenuto e della quote, offset start/end (caratteri Python, end esclusivo),
retrieved_at UTC ed excerpt con redacted=true. Offset/hash sono dell'originale,
quindi l'estratto redatto può differire dal testo originale. La fonte è Markdown
selezionato dal crawler, non una misura prestazionale, screenshot o prova del backend.

Prima della persistenza il builder ricontrolla tutti gli hash contro PageEvidence
del crawl corrente, quote/offset e proiezione pubblica; assegna timestamp delle
pagine effettivamente raccolte. Un crawl o report alterato è rifiutato.
La lettura SQL valida schema/limiti e corrispondenza URL/hash delle evidenze.
Non dispone del testo originale per una nuova verifica semantica o delle quote;
quest'ultima avviene prima della persistenza. Corruzione/unbound evidence causa
job_audit_report_invalid senza contenuti SQL nella risposta.

## Come interpretare lo stato

| Stato | Significato |
|---|---|
| inconclusive | Osservazioni AI proposte; citazioni eventualmente matched, nessuna diagnosi automaticamente dimostrata |
| legacy_uncited | Output di prompt precedente o record storico senza citazioni; non vengono inventate prove retroattive |
| failed | Audit locale fallito: voto assente, non zero; cella Excel senza colore di qualità |

Ogni finding AI rimane inconclusive, method llm_observation. Un estratto autentico
può essere irrilevante alla diagnosi: matched significa soltanto che il testo
esiste nella pagina. Nessuna confidence numerica o certificazione viene attribuita.
Findings vuoti non significano che il sito è privo di problemi. I campi legacy
di sintesi e il voto restano giudizi AI non calibrati, anche con citazioni.
Il server conserva provider_unavailable sui fallimenti, senza falso job completed.

## Privacy e limiti

Descrizioni ed estratti pubblici oscurano email, numeri telefonici e segreti
riconoscibili. URL pubblici senza query/fragment/userinfo; path con identificatori
riconoscibili, anche percent-encoded, diventa /[REDACTED_PATH]. Hash/ID restano
collegati all'originale. La redazione è a pattern, non anonimizzazione universale:
nomi o identificatori non riconosciuti possono richiedere revisione del report.
Nessun testo completo, prompt privato o risposta grezza è un campo del report.
Gate di contatti/suppression, workspace, scadenza licenze, retention e controllo
fresco dello streaming continuano a governare le consegne.

Report JSON massimo24000 byte UTF8: anche la serializzazione nella cella Excel
resta sotto32767 caratteri. Unicode e ritagli troppo grandi vengono gestiti
con rifiuto esplicito, non troncando una citazione e falsificandone la prova.
La normalizzazione anti-injection/NFKC può rendere una quote diversa dall'originale:
in quel caso non viene ammessa come autentica. Non aumenta il numero di chiamate
provider per un audit riuscito; il catalogo aggiuntivo può aumentare i token.

## Verifiche

Regressioni TDD su originale/parafrasi, Unicode, citazioni fuori catalogo, metadata
falsi, limiti e redazione; trasporto mock del vero SDK OpenAI. Builder, SQL,
HTTP e XLSX riaperti esercitano un report multipagina. Nessun provider reale
o distribuzione in produzione viene usato per queste prove.
