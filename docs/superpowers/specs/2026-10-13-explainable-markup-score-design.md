# Indice DOM spiegabile, affiancato al voto AI

13 ottobre 2026. Base develop `3a8c3df`, PR15 integrata con otto gate postmerge
PASS. Branch codex/explainable-markup-score nel worktree isolato già allegato.
Mandato autonomo confermato; il proprietario ha scelto esplicitamente di
affiancare un indice DOM al voto AI. Scelte ordinarie di design auto-revisionate,
senza ulteriori conferme. Esecuzione inline e una review finale indipendente.

## Intento e alternative

Mostrare un indice ripetibile del markup osservato, spiegato dai nove contatori
DOM e dalla copertura delle pagine. Il voto AI 1–10 rimane separato, così come
filtri/opportunità, prompt, chiamate provider, licenze e policy. Il prodotto
non deve chiamare questo indice qualità complessiva, compliance o probabilità.

Scelta: rubrica iniziale con nove pesi uguali e rapporti di elementi conformi,
senza dichiarazioni di calibrazione. Sostituire il voto AI è escluso dalla scelta
del proprietario; una rubrica commerciale con pesi appresi richiede prima un
gold set revisionato da persone. Raccolta gold set e calibrazione costituiscono
il sottoprogetto successivo; fixture sintetiche non sono un benchmark validato.

## Formula versione dom-markup-1

Usare solo pagine `observed` del `dom_report` validato, regole versione1.
Per ciascuna delle nove regole sommare matched e total delle pagine osservate.
Il rapporto della regola è matched/total; aggregazione per elemento all'interno
di una regola, peso1 per ciascuna regola applicabile. Presenza ha un elemento
per pagina; immagini/link/controlli possono avere molti elementi.

Indice = 100 * media dei rapporti delle regole con total>0. Una regola senza
elementi osservati non entra nel denominatore e non è un pass automatico.
Pagine inconclusive/omesse non sono zeri o successi: la copertura resta esplicita.
Nessuna pagina osservata -> score=null, non0/100. Con pagine osservate ma
nessun predicato soddisfatto -> score=0. Sei regole di presenza assicurano un
denominatore positivo quando c'è una pagina osservata.

Calcolo razionale con Fraction, arrotondamento half-up esatto a due decimali
tramite interi: round_percent(r) = ((r.numerator*20000+r.denominator)//
(2*r.denominator))/100. Non mediare valori già arrotondati. Componenti e totale
sono numeri finiti0–100; cambiando l'ordine delle pagine l'indice non cambia.
Un numero maggiore significa più corrispondenze ai predicati, non sito migliore.

## Contratto pubblico

score_report schema_version1, rubric_version `dom-markup-1`, rules_version `1`,
method `dom_markup_index`, scope `collected_html_dom`, calibration_status
`uncalibrated`, status complete/partial/unavailable copiato dal report DOM;
score numero o null, scale {minimum:0, maximum:100,
direction:`higher_more_markup_matches`}, coverage come DOM, applicable_weight
intero0–9, evidence_ids ordinati degli observed, dom_report_sha256.

components ha esattamente nove chiavi RULE_IDS, con weight1, matched/total
sommati (massimo20000000), applicable_pages e not_applicable_pages osservati,
status `observed` con total>0, `not_applicable_observed` senza elementi ma almeno
una pagina osservata, `unknown` senza pagine osservate; score percentuale o null.

dom_report_sha256 è SHA256 del JSON DOM canonico UTF8 ensure_ascii=False,
allow_nan=False, sort_keys=True, separators=(',', ':'). Hash del DOM report
lega anche copertura, tempi e prove, non solo il valore numerico dell'indice.
Report vuoto storico: coverage0, score=null, applicable_weight0, evidence_ids[],
hash=null, tutte le componenti unknown con contatori0. Un DOM unavailable ma
con pagine eleggibili conserva invece hash e copertura effettivi.

Cap score_report12000 byte UTF8. Nessun URL/HTML/label/contatto nuovo: solo ID,
hash, enum e numeri. build_score_report(dom_report)->dict valida DOM e deriva
dati; empty_score_report()->dict; validate_score_report(report, dom_report)->dict
ricomputa e confronta JSON canonico esatto, distinguendo bool/int e rifiutando
NaN/extra campi/versioni ignote/hash/outcome/contatori/punteggi alterati. Errore
AuditValidationError `score_report_invalid`; DOM invalido mantiene il suo codice.

## Integrazione

VerifiedLead.score_report aggiunto in coda; builder calcola dal proprio DOM
report ignorando score_report inviato dal modello/custom auditor. Provenienza
website_markup_score con origine/DOM hash/tempo del report DOM e confidence0:
non una probabilità. Nessun nuovo dato Google o nuovo fetch/call/SDK parametro.
Runner diagnostico e tester aggiungono report ricalcolato al risultato; artefatto
storico selezionato del tester rimane invariato.

Persistenza: JSON nelle tabelle esistenti, nessuna migrazione/riga DOM nuova.
Prima di scrivere ricomputare e confrontare con lead.dom_report. API espone
score_report separato dagli attributi stringa precedenti. Lettura dopo verifica
DOM ricalcola indice e binding; corruzione/report diverso -> errore sicuro
job_score_report_invalid senza eco SQL. Assenza storica di score_report -> vuoto
unavailable, anche se esiste un vecchio DOM report: nessuna riscrittura implicita.

XLSX locale/server aggiunge in coda Markup Score/markup_score numerico o cella
vuota, e Score Report/score_report JSON. Colonne precedenti conservano posizione
e tipo; nessuna colorazione di qualità sul nuovo indice. Con score_report=None
produrre report vuoto; con report presente validarlo contro il DOM. Gate
privacy/workspace/retention/licenze/snapshot/stream invariati su tutti i campi.

## Accettazione e limiti

TDD:100/0/null distinti, rapporti parziali, esclusione not-applicable, mixed
complete/partial/unknown/omitted,20 pagine e contatori elevati, arrotondamento
razionale e ordine, hash DOM alterato, bool/NaN/versione/extra campi/cap12000.
Builder non dà autorità al modello; DTO positional compatibile; diagnostica e
tester nel proprio boundary. SDK->worker->SQL->HTTP->XLSX e locale con dati
identici, indice numerico anche0, storico assente, SQL corrotto e DOM modificato
pur con righe hash presenti. Snapshot/licenze/privacy coperti da regressioni.

Suite finale PostgreSQL17/Chromium/distribuzione e gate GitHub su HEAD esatto.
Un reviewer fresco, read-only, nessun child; unico fix pass Important/Critical
con RED->GREEN e suite, Minor rinviati. Commit/push major, PR pronta verso
develop; merge separato su richiesta. Nessuna nuova promessa di calibrazione,
provider live o anonimizzazione universale; database fidato, HTML non persistito.
