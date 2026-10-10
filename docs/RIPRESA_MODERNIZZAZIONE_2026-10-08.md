# Ripresa della modernizzazione — 8 ottobre 2026

Aggiornamento del 9 ottobre, dopo il recupero dell'export: il blocco NLTK è stato
rimediato nel branch `codex/remove-unused-nltk`, tramite rimozione della dipendenza
inutilizzata e test del crawler reale. [Causa, limiti e verifiche](NLTK_SECURITY_REMEDIATION.md).
I riferimenti al gate rosso nei resoconti precedenti descrivono le revisioni delle
PR #7/#8 prima di questa correzione; rimangono storici fino all'integrazione del
branch. La versione commerciale conserva le altre milestone aperte.

## Intento del proprietario

Riprendere la trasformazione di Lead Hunter in un prodotto vendibile senza perdere
le funzioni utili della versione personale. Alcune funzioni devono essere disponibili
solo al proprietario in locale o a soggetti da lui autorizzati, eventualmente tramite
chiavi/licenze emesse dal proprietario.

Priorità confermate in questa sessione: recuperare tutte e tre le aree proposte,
ossia export senza sito, filtri rating/recensioni e diagnostica completa. Le ulteriori
funzioni individuate nel crawler/report restano candidate da discutere.

Modello di distribuzione confermato: supportare sia installazioni proprie dei
destinatari sia accesso al server del proprietario, con architettura modulare.
Questa scelta conferma il requisito di distribuzione, non approva automaticamente
il design dettagliato o l'implementazione del licensing.

Durata confermata: gli accessi aggiuntivi devono essere a scadenza. Il proprietario
non ha richiesto una durata predefinita; la proposta è di scegliere la data/ora
quando si emette ogni autorizzazione. La versione base perpetua e la manutenzione
separata rimangono quelle del design commerciale precedente.

Questo file è una ricognizione e una proposta di ordine del lavoro. Il design
conversazionale del primo sottoprogetto è stato approvato dal proprietario.
La [specifica scritta](superpowers/specs/2026-10-08-autorizzazioni-modulari-a-scadenza-design.md)
è stata approvata il 9 ottobre 2026. Il
[piano operativo](superpowers/plans/2026-10-09-autorizzazioni-modulari-a-scadenza-implementation-plan.md)
è stato approvato e implementato il 9 ottobre 2026 con esecuzione native.
Il core delle licenze è nel branch `codex/expiring-feature-licenses`,
[PR draft #7](https://github.com/Marcelluxx/lead-hunter-ai/pull/7).
Il [resoconto di implementazione e verifica](FEATURE_LICENSES_IMPLEMENTATION_REVIEW.md)
registra risultati, decisioni e blocchi di release.
I tre moduli richiesti restano il prossimo sottoprogetto: risultano pianificati,
senza esecuzione concessa dal solo possesso di una licenza. La release commerciale
resta bloccata dalla vulnerabilità NLTK senza versione corretta pubblicata.

## Baseline recuperata

- La copia locale era su `main` al commit `62e5d9a` del 4 luglio 2026, senza
  modifiche tracciate o file non tracciati rilevati da `git status`.
- Verificato GitHub e aggiornato `main` con fast-forward a `19c2730`, senza
  modificare il comportamento applicativo rispetto alla versione remota.
- `origin/develop` è al commit `59e24fa`; `main` contiene inoltre la promozione
  della release, l'aggiornamento cryptography e i documenti di design/piano.
- I workflow CI e Security di GitHub su `19c2730` risultano completati con successo.
  Non è stata eseguita una nuova suite locale durante questa ricognizione.

Fonti del lavoro precedente:

- [Audit e roadmap](AUDIT_PRODOTTO_E_ROADMAP_STATO_DELL_ARTE.md), sezioni 0 e 10.
- [Roadmap operativa corrente](../README.md#roadmap).
- [Design commerciale precedente](superpowers/specs/2026-08-01-architettura-commercializzazione-e-p0-governance-design.md).
- [Piano P0 precedente](superpowers/plans/2026-08-01-p0-governance-compliance-implementation-plan.md).
- [CI della baseline](https://github.com/Marcelluxx/lead-hunter-ai/actions/runs/31087662870).
- [Security della baseline](https://github.com/Marcelluxx/lead-hunter-ai/actions/runs/31087662082).

Le intestazioni del vecchio piano dicono ancora che l'implementazione non era
autorizzata/non iniziata, ma i relativi commit sono già stati integrati. Per lo stato
effettivo fanno fede codice, cronologia e aggiornamenti dell'audit; quel piano non
va rieseguito da zero. I vecchi documenti chiedevano anche di restare locali, mentre
risultano ora tracciati nel commit `19c2730`: questa incongruenza è registrata, senza
intervenire sulla cronologia o sulla visibilità del repository.

## Funzioni da valutare per il recupero

| Area | Comportamento precedente | Stato corrente verificato | Evidenza |
|---|---|---|---|
| Lead senza sito | Export Excel e collegamento al batch AI | Solo risultati transitori; export rifiutato; AI non chiamata dalla pipeline | `99df832`, `main.py`, `src/application/export_policy.py` |
| Qualificazione Google | Soglie rating/numero recensioni | Dati non richiesti; filtro escluso dalla pipeline; parametri CLI ancora presenti | `99df832`, `src/config.py`, `src/gui.py`, `main.py` |
| Campi report | Indirizzo, località, telefono, rating, recensioni; competitor e sintesi per lead senza sito | Colonne ridotte ai dati del sito verificato; campi assenti nel modello `VerifiedLead` | `99df832`, `src/exporter.py`, `src/domain/provenance.py` |
| Diagnostica AI | Prompt completo, risposta grezza, pagine preprocessate salvati | Rimossi dall'output pubblico e dal tester | `71a4a96`, `src/auditor.py`, `src/tester.py` |
| Diagnostica crawl | Download HTML di ogni pagina e CSS inline/esterni | Download secondari rimossi; resta HTML homepage/testo con opt-in e retention | `ac05ccf`, `71e5f47`, `src/tester.py` |
| Link discovery AI | Fallback LLM per trovare pagine rilevanti mancanti | Rimosso nel passaggio a Crawl4AI; restano link prioritizzati per percorso | `e7afdbd`, `src/crawler.py` |
| High-Fidelity | HTML semantico e classi CSS distinti dal Markdown ottimizzato | Parametro/interruttore ancora presenti, ma generazione Markdown comune | `e7afdbd`, `src/crawler.py`, `src/gui.py` |
| Fetch statico/browser | HTTPX rapido con fallback browser | Sostituito dal crawler Crawl4AI basato sul browser | `e7afdbd`, `src/crawler.py` |

Le funzioni non sono tutte state perse durante lo stesso intervento: alcune nel
refactor del crawler di luglio, altre nei boundary di sicurezza e discovery di
fine luglio/agosto. La richiesta di recupero non implica ripristinare integralmente
le vecchie versioni dei file.

## Stato delle milestone precedenti

| Milestone | Stato e punto di ripresa |
|---|---|
| P0 sicurezza/evidenza/output | Implementato e integrato; preservare i controlli nei recuperi |
| P0 piattaforma/governance | Core autenticazione, ruoli, workspace, budget, provenienza e privacy integrato |
| Riproducibilità e gate release | Lockfile, CI, PostgreSQL, Docker e supply-chain checks integrati |
| Esecuzione job commerciali sul server | Aperto: `process_job` termina con `pipeline_not_configured` e libera la prenotazione budget |
| Correttezza funzionale | Aperta: età dominio, e-commerce/franchise/social, High-Fidelity, CMS, normalizzazione e altri P1 |
| Qualità audit misurabile | Aperta: citazioni, scoring calibrato, gold set e benchmark |
| Licensing prodotto | Core di emissione/verifica, scadenze e permessi per funzione implementato nella PR draft #7; gate release NLTK ancora bloccante |
| Interfaccia clienti e operatività | Aperte: frontend, osservabilità, backup/restore e continuità operativa |
| Distribuzione commerciale | Aperte: firme immagini, attestazioni, aggiornamenti firmati e rollback |

Questa tabella descrive la presenza del lavoro nel repository, non certifica una
nuova installazione locale o l'idoneità commerciale di uno specifico deployment.

## Approcci da discutere

1. **Licenze firmate con permessi per funzione — proposta preferita.** Un unico
   prodotto con profilo standard e permessi aggiuntivi assegnabili dal proprietario.
   La chiave privata di emissione resta nel suo ambiente; il prodotto riceve solo
   le informazioni necessarie alla verifica. Il design esistente prevede già online
   e offline. I controlli vanno applicati a GUI, CLI, API e worker; mostrare/nascondere
   i pulsanti è soltanto l'effetto visibile dell'autorizzazione. Servono decisioni su
   destinatario/installazione, scadenza, revoca e relazione con i ruoli workspace.
2. **Permessi associati agli account su un server gestito.** Amministrazione e revoca
   centralizzate, ma richiede il server e non risolve da solo le installazioni offline.
3. **Edizioni separate personale/commerciale.** Separazione esplicita della distribuzione,
   con maggiore costo di manutenzione e rischio di divergenza delle funzioni.

Le autorizzazioni di prodotto e le policy dei dati devono essere valutate separatamente:
una licenza decide chi può eseguire una funzione; il recupero di export e rating
richiede anche una decisione sulla fonte dei dati e sul boundary Google già esistente.
La diagnostica proprietaria dovrebbe avere un canale dedicato, distinto dai report
cliente, con credenziali oscurate e limiti di conservazione.

## Prossimo percorso proposto

1. Confermare l'elenco delle funzioni da recuperare e la loro priorità.
2. Definire il primo sottoprogetto: accesso alle funzioni riservate e licensing minimo,
   oppure un recupero funzionale circoscritto se questa è la priorità del proprietario.
3. Presentare il design concreto con Superpowers e raccogliere il riscontro.
4. Completare specifica e piano secondo il percorso applicabile, senza accorpare
   licensing, tutte le regressioni e l'intera piattaforma in un unico intervento.
5. Integrare i recuperi per area mantenendo le prove dei boundary esistenti.
6. Riprendere il collegamento della pipeline al worker e le successive milestone del README.

## Proposta modulare dopo il chiarimento sulla distribuzione

- Un nucleo comune per pipeline, dominio e autorizzazioni delle funzioni.
- Un catalogo di funzionalità con identificatori stabili: `export.no_website`,
  `discovery.rating_filters`, `diagnostics.full`. Ogni modulo dichiara anche
  dipendenze, disponibilità e policy dei dati; un permesso non crea un modulo assente.
- Un servizio applicativo comune decide gli accessi. In locale riceve una licenza
  firmata associata all'installazione; sul server combina licenza del deployment,
  assegnazioni agli utenti/workspace e ruoli già esistenti. Un ruolo admin cliente
  non diventa automaticamente un emittente di licenze del proprietario.
- Controllo agli ingressi CLI/API e nelle operazioni applicative/worker; la GUI
  riflette gli stessi permessi. Un job accodato viene ricontrollato all'esecuzione.
- Emissione e chiavi private appartengono agli strumenti privati del proprietario;
  la verifica appartiene al prodotto distribuito.
- Diagnostica completa in un canale dedicato agli utenti autorizzati, con redazione
  delle credenziali e retention; non viene aggiunta al DTO pubblico dell'audit.
- Export senza sito richiede un contratto di record adatto a dati senza website e
  provenienza ammissibile. Non si rimuove semplicemente il rifiuto del tipo attuale
  `TransientCandidate`; i limiti della fonte rimangono una decisione distinta dalla licenza.
- Online/offline rimangono previsti come nel design precedente. La durata delle
  autorizzazioni aggiuntive è a scadenza, come confermato dal proprietario. Revoca
  immediata richiede un controllo online; una licenza completamente offline può
  recepire aggiornamenti/revoche solo dopo un nuovo contatto o importazione.
- La continuità della versione base perpetua e la manutenzione separata restano
  coerenti con il design precedente; si discute qui solo degli accessi aggiuntivi.

Verifiche eseguite nel piano licensing: token alterati, funzione non
concessa, installazione diversa, identità/workspace non autorizzati, parità CLI/API/
worker, revoca o scadenza secondo la policy scelta, assenza di diagnostica nei
report pubblici e regressioni sui boundary di rete/export già esistenti.

### Primo sottoprogetto implementato: autorizzazioni modulari a scadenza

Il nucleo è implementato e verificato nel branch della PR #7. Seguono i tre
recuperi funzionali distinti e poi il collegamento al worker commerciale della roadmap.

- Licenza firmata con identificativo, versione del formato, emittente/chiave,
  destinatario, installazione, elenco di funzioni, inizio validità e scadenza.
  La firma del licensing usa chiavi separate da quelle di autenticazione.
- In locale la verifica può operare offline; sul server si aggiungono le
  assegnazioni a identità/workspace e i permessi del ruolo corrente.
- Identificatori e date sono validati in modo rigoroso; le date sono conservate in
  UTC e mostrate nel fuso dell'interfaccia. La licenza scade quando l'istante
  corrente raggiunge la scadenza. Una licenza assente, alterata, non ancora valida,
  scaduta, di emittente sconosciuto o per un'altra installazione non concede accessi.
- Rinnovo tramite una nuova autorizzazione firmata. La nuova autorizzazione è
  validata prima della sostituzione di quella attiva.
- Alla scadenza i controlli impediscono nuove operazioni riservate e nuovi passaggi
  protetti dei job. Un'operazione già autorizzata può terminare; il risultato
  sensibile richiede comunque autorizzazione valida alla consegna. Si preservano
  dati esistenti e funzionalità base perpetue. La UI mostra quali moduli sono
  disponibili, attivi o scaduti e la data di scadenza, senza mostrare contenuti
  diagnostici quando il permesso è scaduto.
- L'emissione appartiene al proprietario. Il prodotto distribuito contiene la
  verifica e le chiavi pubbliche fidate, mai le sue chiavi private di firma.
- Le interfacce permettono in seguito un controllo centralizzato di stato/revoca;
  costruire l'intero servizio online di licensing non fa parte del primo nucleo.
- L'offline dipende dall'orologio del sistema: si prevedono controlli di regressione
  dell'ora rispetto allo stato già osservato, senza promettere resistenza assoluta
  al proprietario della macchina o revoca immediata senza comunicazione.

Il proprietario ha confermato questo design. È stata scritta la specifica del
primo sottoprogetto secondo Superpowers; i recuperi di export/filtri/diagnostica
rimangono nel percorso concordato, ma non risultano implementati da questa nota.

## Checklist di questa sessione

- [x] Recuperare contesto, cronologia remota e documenti.
- [x] Identificare rimozioni e milestone implementate/aperti.
- [x] Verificare lo stato CI remoto e la pulizia del checkout aggiornato.
- [x] Presentare la prima domanda sulle funzioni prioritarie.
- [x] Ricevere le priorità del proprietario.
- [x] Chiarire il modello di accesso: entrambi, con architettura modulare.
- [x] Chiarire la durata degli accessi alle funzioni riservate: a scadenza.
- [x] Preparare la proposta del primo sottoprogetto e il comportamento alla scadenza.
- [x] Approvare il design conversazionale del primo sottoprogetto.
- [x] Scrivere la specifica del primo sottoprogetto.
- [x] Completare la revisione del proprietario sulla specifica scritta (9 ottobre 2026).
- [x] Scrivere il piano operativo e completare la revisione interna.
- [x] Completare la revisione del proprietario sul piano e scegliere il metodo di esecuzione (9 ottobre 2026, native).
- [x] Implementare e verificare il primo sottoprogetto, correggere la review indipendente e pubblicare il branch (PR draft #7).
- [x] Implementare la rimozione di NLTK inutilizzato e verificare il crawler nel branch dedicato; integrare solo dopo i gate GitHub della PR.
- [ ] Recuperare i tre moduli e collegarli ai controlli di accesso comuni.

## Recupero export senza sito — scelta del 9 ottobre 2026

Il proprietario ha scelto i risultati delle ricerche Google Places e usa una
normale chiave API, senza un accordo di export specifico dichiarato. È stata
approvata la variante **Excel dei riferimenti: Place ID e link Google Maps**,
senza duplicati, protetta da `export.no_website`. Questa variante non ripristina
le colonne Google del vecchio report completo. Il servizio comune è riutilizzabile
sul server; il collegamento ai job commerciali resta nella milestone del worker.

La [specifica scritta](superpowers/specs/2026-10-09-export-riferimenti-senza-sito-design.md)
è stata approvata dal proprietario il 9 ottobre 2026. Branch dedicato
`codex/no-website-reference-export`, basato sul core della PR #7.

- [x] Chiarire fonte e variante dell'export.
- [x] Approvare il comportamento conversazionale.
- [x] Scrivere e revisionare internamente la specifica.
- [x] Approvare la specifica scritta (9 ottobre 2026).
- [x] Preparare e revisionare internamente il [piano operativo](superpowers/plans/2026-10-09-export-riferimenti-senza-sito-implementation-plan.md).
- [x] Approvare il piano operativo (9 ottobre 2026); mantenere il metodo native già scelto.
- [x] Implementare, verificare e pubblicare il modulo ([PR draft #8](https://github.com/Marcelluxx/lead-hunter-ai/pull/8)).

Il modulo è implementato nel branch dedicato: contratto ID, servizio comune con
verifica a generazione/consegna, salvataggio atomico CLI e consegna inline GUI.
La review indipendente ha individuato una regressione della ricerca base GUI,
corretta con test prima/dopo: input non esportabile non nasconde i risultati.
I gate Python 3.10–3.13, PostgreSQL e container sono passati sul codice precedente
alla correzione; gli stessi gate devono passare anche sull'HEAD finale prima
dell'integrazione. [Esiti e decisioni](REFERENCE_EXPORT_IMPLEMENTATION_REVIEW.md).
Nessun endpoint job o collegamento worker introdotto. Integrazione della PR #7
e blocco NLTK rimangono aperti; questo completamento non è una release commerciale.

## Recupero filtri rating/recensioni — 10 ottobre 2026

Il proprietario ha confermato l'uso in **entrambe le modalità** e il design:
opzione disattivata inizialmente, rating superiore alla soglia e conteggio da 1
al massimo scelto, accesso `discovery.rating_filters` a scadenza. Se l'accesso
scade, la ricerca filtrata fallisce senza tornare silenziosamente a quella base.
Il confronto resta nell'adapter Google; metriche escluse da Excel, storage e AI.

La [specifica scritta](superpowers/specs/2026-10-10-filtri-rating-recensioni-design.md)
è stata preparata e autorevisionata sul branch `codex/licensed-rating-filters`,
basato su `6491f66` della [PR draft #9](https://github.com/Marcelluxx/lead-hunter-ai/pull/9).
Per la base sono passati tutti i gate GitHub, incluso Security dopo la rimozione
di NLTK inutilizzato. Le indicazioni di blocco precedenti restano storiche.

- [x] Recuperare regole e limiti precedenti.
- [x] Confermare entrambe le modalità.
- [x] Approvare il design conversazionale.
- [x] Scrivere e autorevisionare la specifica.
- [x] Approvare la specifica scritta (10 ottobre 2026).
- [x] Scrivere e autorevisionare il [piano operativo](superpowers/plans/2026-10-10-filtri-rating-recensioni-implementation-plan.md).
- [ ] Approvare il piano operativo; mantenere il metodo native già scelto.
- [ ] Implementare, verificare e pubblicare il modulo.

Il modulo rimane `planned`; non è stato modificato codice applicativo.
