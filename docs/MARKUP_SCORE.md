# Indice del markup osservato

14 ottobre 2026. Il proprietario ha scelto un indice DOM separato dal voto AI.
Il voto precedente 1–10 rimane un giudizio AI; il nuovo indice 0–100 riassume
i nove [predicati di markup](DOM_CHECKS.md) delle pagine effettivamente osservate.
Non misura qualità complessiva, accessibilità, valore commerciale o probabilità.

## Formula ripetibile

La rubrica `dom-markup-1` assegna peso1 a ciascuna delle nove regole. Per ogni
regola somma matched e total sulle pagine observed, poi divide matched/total.
Immagini/link/controlli vengono quindi aggregati per elemento all'interno della
loro regola; le regole di presenza hanno un elemento per pagina. Infine calcola
100 volte la media dei rapporti delle regole con almeno un elemento osservato.

Una regola not-applicable non entra nel denominatore e non vale un successo
automatico. Unknown e pagine omesse non diventano zero o pass: coverage e stato
partial/unavailable rimangono espliciti. Con zero pagine osservate l'indice è
null, non0. Con pagine osservate e zero corrispondenze l'indice è invece0.

Esempio: otto regole hanno rapporto1, una ha un'immagine conforme su due:
100 × (8 + 1/2) / 9 = **94.44**. Il rapporto di quella componente è50/100.
Se una regola aggrega1/2 su una pagina e1/6 su un'altra, la componente usa2/8,
cioè25%, non la media dei due rapporti. Le regole pesano uguale, ma gli elementi
più numerosi pesano di più all'interno della loro regola.

Il calcolo usa frazioni esatte e arrotondamento half-up a due decimali:3.125%
diventa3.13%. Il totale viene calcolato dalle frazioni originali, senza mediare
componenti già arrotondate. Cambiare l'ordine delle pagine non cambia l'indice.
Un valore maggiore indica più corrispondenze al markup selezionato, non un
giudizio migliore su tutto il sito. Anche100 su una sola pagina mantiene la
copertura limitata alle pagine osservate.

## Report e prove

`score_report` espone schema1, rubric_version dom-markup-1, rules_version1,
method dom_markup_index, scope collected_html_dom, calibration_status
uncalibrated, score, scala, stato e copertura. components contiene esattamente
nove regole con peso, contatori, pagine applicabili/non-applicabili osservate e
rapporto percentuale. I possibili stati delle componenti sono observed,
not_applicable_observed e unknown. applicable_weight indica quante regole
contribuiscono al denominatore; evidence_ids identifica le pagine observed.

dom_report_sha256 lega l'indice all'intero JSON DOM canonico UTF8 (chiavi
ordinate, separatori compatti, Unicode conservato, NaN vietato). Include quindi
copertura, prove e timestamp, anche quando cambiano senza alterare il numero
finale. Il report non duplica URL, HTML, label o dati di contatto; è limitato a
12000 byte UTF8 e contiene soltanto ID, hash, numeri ed enum.

Il builder calcola l'indice dal suo DOM report e ignora score_report proposto
dal modello/custom auditor. Nessun prompt, parametro SDK, fetch o chiamata
provider aggiuntiva. Prima di SQL, lettura API ed export il report viene
ricomputato e confrontato con il DOM corrente: bool, NaN, versioni ignote, campi
aggiuntivi o numeri/hash alterati vengono rifiutati. La provenienza è
website_markup_score, confidence0: non una stima probabilistica.

## Consegna e compatibilità

SQL usa l'attributo JSON nelle tabelle esistenti, senza migrazioni o nuove prove
DOM duplicate. API aggiunge score_report come oggetto separato; gli attributi
precedenti restano stringhe. Corruzione o disaccordo con il DOM produce
job_score_report_invalid senza contenuto SQL nella risposta. Il controllo
DOM/hash delle prove avviene prima. Il database resta una fonte fidata: senza
HTML persistito non si verifica semanticamente un tampering coerente di tutte
le misure e prove SQL.

Excel aggiunge in coda Markup Score/markup_score numerico (anche0) e Score
Report/score_report JSON. Le colonne precedenti mantengono posizione e formato.
Il nuovo indice non ha colori di qualità; null è una cella vuota. Storico senza
score_report produce unavailable/copertura0 anche se conserva un vecchio DOM
report, senza scrivere retroattivamente dati o applicare implicitamente rubriche.

Diagnostica autorizzata include il report derivato nel riepilogo sigillato.
Il vecchio tester mostra indice, stato e conteggi di pagine osservate/eleggibili,
inconclusive e omesse; questi dettagli restano anche nel report testuale. Conserva
il file JSON sintetico a campi selezionati. Gate licenze a scadenza, workspace, privacy, retention, snapshot e
stream continuano a governare tutti i nuovi campi.

## Calibrazione successiva

Pesi e formula sono iniziali e trasparenti, **non calibrati**. I test sintetici
dimostrano implementazione, aritmetica e boundary; non sono un benchmark di
qualità commerciale. La milestone successiva prepara raccolta e valutazione
su un gold set revisionato da persone. Nessun dataset o risultato umano viene
inventato; modifiche future a formula/pesi richiederanno una nuova rubrica.
