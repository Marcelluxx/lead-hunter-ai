# Filtri rating e numero di recensioni con licenza a scadenza

Data: 10 ottobre 2026, Europe/Rome.

Stato: design conversazionale approvato dal proprietario; specifica scritta
in attesa della sua revisione. Nessuna implementazione autorizzata da questa nota.
Metodo native già scelto per i sottoprogetti precedenti; il piano di questo modulo
sarà scritto dopo l'approvazione della presente specifica.

Base: `6491f66`, rimozione NLTK nella PR draft #9, a sua volta basata su export
PR #8 e licensing PR #7. Branch dedicato: `codex/licensed-rating-filters`.
Il gate Security della base è verde; questi prerequisiti non sono ancora integrati.

## 1. Intento e risultato concordato

Recuperare la selezione delle attività tramite voto medio Google e numero di
recensioni, utile al proprietario e ai destinatari da lui autorizzati, senza
perdere le ricerche base della versione vendibile. Il proprietario ha scelto
entrambe le modalità: `no_website` e `with_website`.

I filtri sono opzionali e inizialmente disattivati. Richiedono il permesso
`discovery.rating_filters` in una licenza valida a scadenza. Il possesso della
licenza rende disponibile l'opzione ma non attiva automaticamente il filtro.
GUI e CLI condividono regole e verifiche; il nucleo è riutilizzabile sul server.

La selezione resta dentro l'adapter Google. Rating e conteggio ricevuti non
vengono aggiunti a `TransientCandidate` o `VerifiedLead`, né visualizzati come
colonne aggiuntive. Excel, database, code, log e prompt AI non li ricevono.
L'export senza sito continua a contenere soltanto Place ID e link Maps.

## 2. Criteri e casi limite

Un criterio immutabile contiene esclusivamente parametri inseriti dall'utente:
`min_rating` e `max_reviews`. Non è una concessione di accesso.

- Soglia rating: numero reale finito nell'intervallo chiuso 0–5, booleani esclusi.
- Massimo recensioni: intero esatto tra 1 e 2.147.483.647, booleani esclusi.
- Valori iniziali quando si attiva l'opzione: 3,9 e 100.
- L'attività passa solo se `rating > min_rating` e `1 <= userRatingCount <= max_reviews`.
- L'uguaglianza alla soglia rating esclude; l'uguaglianza al massimo recensioni include.
- Con soglia 5 nessuna attività passa: scelta valida, risultato vuoto comprensibile.
- Rating assente, non numerico, booleano, non finito o fuori da 0–5 esclude
  l'attività dalla ricerca filtrata. Non viene convertito da stringhe.
- Conteggio assente, booleano, non intero, negativo, zero o oltre il massimo
  rappresentabile esclude. Non viene approssimato o sostituito con un valore utile.
- Un elemento privo dei campi necessari non interrompe gli altri elementi validi.
  Risposte provider globalmente invalide mantengono gli errori sicuri esistenti.
- Parametri utente invalidi fanno fallire la richiesta prima di qualsiasi I/O.

Il confronto avviene sui valori ricevuti, senza arrotondamenti e senza dipendere
dal parametro server `minRating` di Google. Non si recupera il testo delle recensioni.

Ogni risposta è filtrata prima di costruire candidati. La deduplicazione conserva
la prima occorrenza che supera il filtro, nell'ordine di griglia e keyword già
utilizzato. Un duplicato escluso non impedisce una successiva occorrenza valida.
Si mantengono la distinzione sito/senza sito e le altre esclusioni esistenti.

## 3. Fonti e limite dei dati

La ricerca base conserva il field mask minimo attuale e non richiede rating o
conteggio. Solo la ricerca filtrata autorizzata aggiunge `places.rating` e
`places.userRatingCount` alla richiesta. Gli header sono costruiti per chiamata,
senza modificare il mask o lo stato condiviso di un'istanza usata dalla ricerca base.
Wildcard, testi di recensioni, indirizzi e telefoni restano esclusi.

La [documentazione Text Search](https://developers.google.com/maps/documentation/places/web-service/text-search)
elenca questi due campi nel livello Enterprise, nel quale rientra anche
`places.websiteUri` già richiesto dall'app. Non si promettono costi invariati:
valgono listino, quota e contratto del deployment. Non si aggiungono chiamate
Place Details, paginazione o recupero storico; la copertura della griglia resta
quella attuale e non garantisce un censimento completo delle attività.

La [policy Places](https://developers.google.com/maps/documentation/places/web-service/policies)
limita caching e conservazione dei contenuti, con l'eccezione dei Place ID.
Gli [usi EEA](https://cloud.google.com/terms/maps-platform/eea-places-api-permitted-uses)
includono gestione di contenuti legati a clienti/opportunità di un team vendite.
Questo orienta il confine tecnico; non costituisce una certificazione contrattuale
del prodotto o del deployment. La verifica Google/privacy già prevista dalla
roadmap commerciale rimane aperta. La licenza dell'app non amplia i diritti Google.

L'adapter tiene i valori soltanto durante l'elaborazione della risposta e li
scarta prima della restituzione. Nessuna cache di rating, risposta grezza,
esito numerico per candidato o copia in session state. Le soglie utente sono
parametri dell'app e possono essere mostrate nell'interfaccia; non sono dati Google.
I conteggi generali di avanzamento non devono rivelare rating o recensioni di
singoli candidati. Attribuzione e separazione dalla mappa restano quelle esistenti.

## 4. Servizio comune e autorizzazione

Un servizio applicativo di ricerca filtrata riceve criteri validati, adapter,
`FeatureAccessService` e una funzione che ricostruisce il `FeatureContext` corrente.
Il percorso base resta indipendente dalla configurazione e dallo storage licenze.
Non si accettano booleani client, token decodificati dal client o autorizzazioni
salvate in cache come prova di accesso.

Il servizio fornisce il controllo all'adapter per ciascuna effettiva richiesta
HTTP: ogni cella della griglia, keyword e retry. Il percorso filtrato pubblico
deve richiedere il verificatore applicativo; non esiste una variante di discovery
che abiliti il mask esteso tramite un semplice flag e senza verifica.
L'adapter conserva il confronto come dettaglio interno e restituisce soltanto
i candidati transitori del contratto esistente.

Controlli obbligatori, sempre con contesto ricostruito:

1. `EXECUTE` prima dell'avvio, della costruzione delle dipendenze esterne e di
   eventuali geocoding/chiamate Google della ricerca richiesta come filtrata.
2. `EXECUTE` immediatamente prima di ogni tentativo HTTP con i campi aggiuntivi.
3. `VIEW` prima che il servizio consegni candidati filtrati al chiamante.
4. `VIEW` prima della consegna finale di risultati o artefatti derivati dalla
   ricerca filtrata: rendering GUI, stampa CLI e scrittura/consegna Excel.

Una richiesta esterna già autorizzata può concludersi dopo la scadenza, ma non
iniziano nuovi tentativi protetti e il risultato non viene consegnato senza
permesso corrente. Le callbacks prima della verifica di consegna possono mostrare
solo stato e avanzamento; non candidati o risultati parziali filtrati.

Una ricerca filtrata conserva un contesto operativo di origine fino alla consegna:
anche i lead ricostruiti dal sito o i soli Place ID conservano il requisito di
accesso della ricerca che li ha selezionati. Tale contesto non contiene valori
rating/conteggio e non è un payload provider o un'autorità fornita dal client.
La perdita dell'accesso impedisce la consegna, senza cancellare file già
consegnati validamente. Il prodotto non può ritirare screenshot o file scaricati.

Sul server si ricostruiscono utente, membership, ruolo, workspace attivo e scope
del deployment tramite gli helper esistenti. `START_JOB` serve per `EXECUTE`,
`VIEW_RESULTS` per `VIEW`, come nel catalogo corrente. Non si aggiunge MFA per
questo modulo. Sono verificati demozione, rimozione membership e disattivazione.
Un servizio invocato direttamente deve applicare gli stessi controlli della UI.

Alla scadenza/revoca o per licenza assente/invalida/non concessa, la ricerca
filtrata termina con un errore sicuro. Non si ripete automaticamente senza filtri
e non si consegnano successi parziali. L'utente può avviare una nuova ricerca base.

## 5. Integrazione CLI e orchestratore

Nuovo flag esplicito `--rating-filters` in entrambe le modalità. `--min-rating` e
`--max-reviews` configurano l'opzione; senza il flag, se forniti esplicitamente,
producono un errore di utilizzo anziché essere ignorati. Senza flag né soglie
esplicite, la ricerca continua esattamente come ricerca base.

I default 3,9/100 vengono applicati solo all'attivazione del modulo. Help ed
esempi distinguono ricerca base e filtrata. Gli argomenti della licenza restano
quelli esistenti. Il percorso diagnostico `--test-url` non usa questi filtri:
le opzioni di rating combinate con diagnostica, `--gui` o `--examples` sono
rifiutate con un messaggio di combinazione non supportata.

L'orchestratore riceve la dipendenza di discovery appropriata alla ricerca;
entrambe le modalità usano lo stesso servizio filtrato. Le vecchie soglie
`run_with_website` non devono restare parametri silenziosamente inoperanti:
il contratto dei chiamanti interni viene aggiornato esplicitamente nel piano.
Il codice della ricerca non inserisce metriche Google nel payload dell'auditor.

Input/licenza invalidi: nessuna chiamata Google, LLM, crawling o scrittura export;
exit code CLI 2. Errori durante l'esecuzione sono redatti e restituiscono un
fallimento, senza risultati parziali o nuovo file. Se la consegna è negata,
un file di destinazione esistente non viene sovrascritto.

L'export no-website da ricerca filtrata richiede entrambe le funzioni:
`discovery.rating_filters` per la consegna dei risultati selezionati e
`export.no_website` per generazione/consegna del file. Le due concessioni restano
indipendenti; l'una non conferisce l'altra.

## 6. Interfaccia locale

Opzione «Filtra per rating e recensioni» disponibile per entrambe le modalità,
disattivata inizialmente. Quando selezionata espone la soglia rating e il massimo
recensioni, con spiegazione del confronto e dei dati mancanti.
L'opzione è disabilitata se il modulo non è autorizzato; il pannello licenze
mostra stato e scadenza. Il servizio ricontrolla l'accesso quando si preme Avvia.

Il cambio modalità non attiva il filtro implicitamente. Una nuova ricerca
cancella i riferimenti della precedente prima dell'esecuzione. Il passaggio
da filtrata a base richiede una nuova ricerca e non riclassifica i vecchi risultati.
Un errore non lascia candidati o artefatti della ricerca fallita nell'interfaccia.

I riferimenti no-website possono restare in sessione come ID, insieme al solo
contesto di origine necessario al controllo di consegna. Nessuna metrica Google,
risposta grezza o concessione di accesso viene conservata in sessione.
Prima di mostrare nuovamente risultati filtrati o preparare un export, il rerun
ricontrolla `VIEW`; se negato, non ripropone i risultati e rende indisponibile
l'export relativo. Una pagina già visualizzata non viene cancellata retroattivamente.
Le ricerche base e il relativo export autorizzato mantengono il comportamento attuale.

## 7. Disponibilità e limiti dello scope

`discovery.rating_filters` passa da `planned` ad `available` soltanto dopo la
verifica dei flussi. `export.no_website` resta disponibile, `diagnostics.full`
resta pianificato. Non cambiano formato/firma delle licenze o strumenti emittenti.
Nessuna migrazione database: non vengono persistite metriche provider.

Il servizio comune viene testato con contesto server corrente, ma non si
introducono endpoint job/export o esecuzione commerciale del worker. Rimane
`pipeline_not_configured` finché sarà affrontata la milestone dedicata.
Diagnostica completa, altri filtri, paginazione Places, provider alternativi e
revisione dei costi globali non sono parte di questo sottoprogetto.

## 8. Verifiche richieste

- Criteri validi/invalidi; soglia esatta, massimo esatto, 0 e 5, NaN/infinito,
  booleani, stringhe, dati mancanti e conteggi non interi.
- Mask base invariato; mask filtrato con soli due campi aggiuntivi; nessuna
  contaminazione dopo ricerche filtrate, compresi tentativi successivi e concorrenti.
- Filtraggio e deduplicazione con fixture provider complete in entrambe le modalità.
- Licenze firmate reali di test: assente, non concessa, alterata, scaduta,
  revocata, installazione errata; nessuna chiamata esterna prima del rifiuto.
- Scadenza/revoca tra celle, tra retry, durante una risposta e prima della
  consegna finale; errore, nessun fallback o successo parziale.
- Server: cambiamento ruolo/membership/stato utente/workspace, senza contesto in cache.
- Parità GUI/CLI/orchestratore, opzione disattivata, soglie senza flag, reset e rerun.
- Assenza delle metriche Google in candidati, prompt, log, queue, database,
  sessione e ZIP/metadata XLSX; destinazione preesistente conservata al rifiuto.
- Combinazioni indipendenti delle licenze filtro/export e accesso base senza trust/store.
- Suite completa, lock check, compilazione, secret scan e gate GitHub dell'HEAD
  finale, inclusi Security, PostgreSQL e container. Nessuna eccezione allo scanner.

## 9. Stato del processo

- [x] Recuperare comportamento precedente e contratto corrente.
- [x] Confermare entrambe le modalità e approvare il design conversazionale.
- [x] Scrivere e autorevisionare questa specifica.
- [ ] Revisione e approvazione del proprietario sulla specifica scritta.
- [ ] Piano operativo scritto e revisionato, poi approvato dal proprietario.
- [ ] Implementazione, test, review indipendente, commit/push e PR draft.

Questa specifica viene salvata e committata per la revisione; il piano e il
codice prodotto verranno affrontati solo dopo i rispettivi passaggi approvati.
