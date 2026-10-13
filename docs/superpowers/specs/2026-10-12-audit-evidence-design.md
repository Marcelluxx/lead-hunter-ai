# Audit con citazioni controllate — primo blocco

12 ottobre 2026, base develop4f40a6c, branch codex/audit-evidence.
Mandato: prima azione della qualità audit; proprietario autorizza implementazione
autonoma e commit/push major. Esecuzione native, review indipendente finale.

## Risultato e confini

Il risultato esistente conserva i cinque campi legacy e aggiunge audit_report,
un oggetto schema_version1 con status, findings ed evidence. Ogni citazione
proposta dal modello viene confrontata esattamente con il Markdown originale
del crawl, non con la riscrittura LLM. Solo citazioni realmente presenti sono
ammesse. Citazione autentica non prova la diagnosi: finding LLM resta inconclusive,
method llm_observation; nessuna confidence numerica inventata. La verifica semantica
deterministica e la calibrazione appartengono al blocco successivo.

Alternative: usare riscrittura come prova (scartata: può inventare testo); cambiare
immediatamente provider privato e schema legacy (scartata: rompe installazioni);
catalogo originale più contratto supplementare pubblico (scelto: compatibile e verificabile).
Nessun nuovo provider, dependency o prompt proprietario viene creato/pubblicato.

## Contratto

AuditEvidenceSet.from_pages(pages, *, collected_at=None) valida ensure_auditable_pages,
massimo20 pagine; ogni pagina ammessa ha almeno120 caratteri e URL HTTP(S) sintattico
valido. Timestamp UTC server; hash SHA256 sul contenuto UTF8 originale, ID stabile
SHA256(URL originale + hash). Solo pagine ammesse entrano nel catalogo.
Il payload non fidato per il modello ha massimo12000 caratteri di contenuto totale,
massimo5000 per pagina, stesso sanitizzatore anti-injection e nessuna fetch.

AuditEvidenceSet.validate_findings(payload) -> report pubblico:
findings assente: status legacy_uncited e findings vuoti. findings presente deve
essere lista max20 (lista vuota: inconclusive). Ogni finding richiede category
enum content/usability/seo/accessibility/performance/security/commercial/other,
severity info/low/medium/high, description string1–1000, citations lista1–3.
Ogni citazione contiene SOLO evidence_id e quote string20–500, corrispondenza
esatta case-sensitive nella pagina originale e nel catalogo visibile al modello.
ID sconosciuti, quote inventate/alterate, campi di autorità status/source/hash
forniti dal modello, duplicati citation/finding e tipi sbagliati sono rifiutati
con AuditValidationError e codice sicuro, mai payload nell'errore.
Output ID finding f1..f20 deterministici, stato inconclusive, metodo llm_observation.
Citazione matched, offset originali start/end, source_url, hash contenuto e quote,
timestamp. Metadata evidence di tutte le pagine ammesse, nessun testo completo.
Status report inconclusive anche con citazioni: prova del testo, non verità semantica.

La proiezione pubblica oscura email, numeri telefonici e segreti riconoscibili,
elimina query/fragment/userinfo dagli URL di citazione; path con identificatori
riconoscibili, anche percent-encoded, diventa /[REDACTED_PATH]. Anche description viene
sanitizzata/redatta. L'estratto pubblico è dichiarato redacted; hash/offset sono
del testo originale. Non è anonimizzazione universale né certificazione privacy.
Nessun bypass dei gate contatti, licenze, retention o workspace già presenti.

## Runtime e confine persistenza

LeadAuditor costruisce il catalogo PRIMA della pulizia; aggiunge al messaggio
utente JSON originale e al system un contratto pubblico di citazione. Provider
privato e numero massimo di tentativi invariati, nessuna nuova chiamata aggiuntiva.
Valida campi legacy e findings prima del ritorno. Output legacy resta dichiarato
legacy_uncited. Fallimento locale restituisce website_score=None e report failed,
non zero; server mantiene provider_unavailable e nessuna persistenza di successo.

build_verified_lead ricostruisce il catalogo con timestamp di PageEvidence e
controlla nuovamente hash/URL/offset contro crawl corrente; proiezione già redatta
viene verificata confrontandola con la proiezione ricalcolata del testo originale.
Report falso/mutato rifiutato; audit legacy ammesso con rapporto legacy_uncited.
VerifiedLead aggiunge audit_report alla fine dei campi per compatibilità posizionale.

Il report pubblico JSON bounded viene persistito come attributo audit_report nella
tabella esistente, classificazione website_audit, con hash della prima pagina.
Le evidenze multipagina/hash/offset restano nel JSON controllato; nessuna migrazione
necessaria. La lettura server valida struttura bounded JSON prima di esporla come
oggetto separato audit_report; attributi precedenti restano stringhe. Report assente
nei record storici è legacy_uncited, non una prova retroattiva.
XLSX locale e server aggiungono in coda Audit Report/audit_report (JSON pubblico),
senza spostare le colonne precedenti; nessun testo/prompt privato. Limite report
JSON UTF8<=24000 byte, così resta entro limite cella Excel32767 caratteri.
Ogni consegna continua a usare gate freschi e snapshot/stream esistenti.

## Verifica e completamento

TDD su quote inventate, multi-page, Unicode, catalogo troncato, metadata falsi,
limiti/nonfinite, redazione e dati legacy. Runtime tramite trasporto HTTP mock
del vero SDK; zero provider reali. Persistenza/HTTP/XLSX reale e regressioni
RLS/retention/privacy/licenze; PostgreSQL17, Chromium e distribuzione nella suite
finale. Commit/push major e PR draft, review fresca e unico pass di correzione.
Non avviare benchmark, nuovi scorer, crawler operativo o UI clienti in questo blocco.
