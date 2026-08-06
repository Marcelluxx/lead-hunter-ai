# Lead Hunter V3 — Design approvato per commercializzazione, piattaforma server e P0 di governance

> Stato: design approvato il 1 agosto 2026.
>
> Questo documento e stato richiesto come file locale non versionato. Non deve essere aggiunto a Git, committato o pubblicato senza una nuova autorizzazione esplicita.

## 1. Scopo

Questo documento raccoglie le decisioni approvate per trasformare Lead Hunter V3 da prototipo tecnico in un prodotto server vendibile, aggiornabile e sostenibile, mantenendo il crawler come elemento distintivo.

Il design copre:

- modello commerciale e tutela della proprieta intellettuale;
- distribuzione server e protezione del core;
- licenze online e offline;
- aggiornamenti firmati;
- architettura applicativa e deployment;
- autenticazione, ruoli, workspace e controllo dei costi;
- plugin;
- provider di discovery e uso prudente di Google Places;
- privacy, provenienza, retention e suppression;
- affidabilita, osservabilita e test;
- ordine di implementazione della terza macrocategoria P0.

Il documento e una specifica tecnica e di prodotto. I profili contrattuali, fiscali, privacy e di proprieta intellettuale dovranno essere verificati da professionisti qualificati prima della commercializzazione.

## 2. Posizionamento commerciale approvato

Il prodotto non nasce inizialmente come SaaS pubblico multi-tenant. Verranno offerte tre modalita commerciali.

### 2.1 Servizio report

Il fornitore gestisce l'intera piattaforma e vende al cliente il risultato del lavoro:

- ricerche;
- lead verificati;
- evidenze;
- audit;
- report ed esportazioni concordate.

Il cliente non riceve software, repository, accesso al server o codice sorgente.

### 2.2 Private Managed

L'applicazione gira in un ambiente dedicato al cliente, ma installazione, manutenzione e aggiornamenti sono gestiti dal fornitore.

Il cliente accede dal browser. I suoi dati rimangono isolati e il servizio puo prevedere un canone ricorrente per gestione, aggiornamenti, backup e assistenza.

### 2.3 Self-Hosted Enterprise

Il cliente gestisce il prodotto sul proprio server tramite Docker Compose. Riceve:

- container ufficiali firmati;
- documentazione operativa;
- procedure di backup, aggiornamento e ripristino;
- SDK e contratti per i plugin;
- licenza online oppure offline;
- nel contratto piu costoso, il sorgente applicativo per audit e continuita operativa.

Il diritto d'uso e perpetuo per la versione acquistata. Manutenzione, nuove versioni, supporto e aggiornamenti successivi al periodo incluso sono servizi separati e rinnovabili.

## 3. Tutela della proprieta intellettuale

### 3.1 Titolarita e licenza

La proprieta intellettuale del prodotto rimane al fornitore. Il cliente acquista un diritto d'uso:

- non esclusivo;
- limitato alla propria entita legale;
- non cedibile e non sublicenziabile, salvo accordo scritto;
- limitato alle installazioni e agli ambienti contrattualizzati;
- privo del diritto di rivendere, pubblicare o trasformare il prodotto in un'offerta concorrente.

Il contratto dovra disciplinare almeno:

- divieto di pubblicazione o distribuzione del repository;
- accesso al sorgente soltanto da parte di personale e fornitori autorizzati;
- obblighi equivalenti di riservatezza per tutti i soggetti ammessi;
- separazione fra licenza perpetua, manutenzione, assistenza e aggiornamenti;
- conseguenze di modifiche non autorizzate al core;
- foro, legge applicabile, risoluzione e rimedi;
- trattamento dei componenti open source e di terzi;
- proprieta e supporto delle personalizzazioni.

Il contratto definitivo dovra essere redatto o revisionato da un legale italiano specializzato in software, proprieta intellettuale e contratti IT.

### 3.2 Evidenze di titolarita

Verranno mantenuti:

- cronologia Git pulita;
- tag e release firmati;
- hash degli artefatti;
- provenienza delle build;
- inventario delle dipendenze e delle relative licenze;
- cessioni o attribuzioni scritte da parte di eventuali collaboratori;
- SBOM per ogni release;
- eventuale registrazione del software presso il Pubblico Registro Software SIAE, da valutare professionalmente.

Algoritmi, configurazioni, procedure, dataset proprietari e know-how non pubblici dovranno essere trattati con misure concrete di riservatezza e controllo degli accessi per beneficiare della protezione dei segreti commerciali.

### 3.3 Limiti della protezione tecnica

Nessun eseguibile, container o sistema di offuscamento rende impossibile il reverse engineering. La protezione effettiva deriva dalla combinazione di:

- contratto;
- prove di titolarita;
- accesso controllato;
- build firmate;
- core compilato;
- separazione delle chiavi private;
- supporto limitato agli artefatti ufficiali.

Se al cliente viene consegnato il sorgente leggibile, il core rimane tecnicamente modificabile. Tali modifiche sono pero fuori dal canale supportato; le personalizzazioni previste dal prodotto passano esclusivamente dai plugin.

## 4. Formato di distribuzione e core compilato

### 4.1 Applicazione server

La modalita privata principale sara una piattaforma centralizzata installata su un server e accessibile tramite browser. Non verra progettata inizialmente come programma Windows installato su ogni postazione.

Il deployment ufficiale iniziale sara Docker Compose. Kubernetes non fara parte della prima release, ma l'architettura non dovra impedirne il supporto futuro per clienti con requisiti di alta disponibilita.

### 4.2 Compilazione

Il codice Python rimane la base di sviluppo. Il core distribuito potra essere compilato con uno strumento come Nuitka per produrre codice nativo e rendere piu difficile l'analisi dell'artefatto.

La compilazione non equivale a una riscrittura completa in C++. Il crawler e principalmente limitato da rete, browser e provider esterni. Eventuali componenti in Rust o C++ verranno introdotti soltanto dopo benchmark che dimostrino un collo di bottiglia reale.

Le chiavi API, le password, le credenziali e le chiavi private di firma non saranno mai incorporate nell'eseguibile o nel container.

### 4.3 Container firmato

Il container contiene applicazione, runtime e dipendenze necessari all'esecuzione sul server. Database, configurazioni, plugin e file persistenti rimangono esterni, consentendo di sostituire una versione senza perdere dati.

La firma crittografica non cifra il container. Dimostra:

- chi ha prodotto l'artefatto;
- che non e stato alterato;
- quale versione esatta viene installata.

La firma delle immagini usera un meccanismo moderno come Sigstore/Cosign, con chiavi e processo di firma mantenuti nell'infrastruttura privata del fornitore.

## 5. Architettura applicativa approvata

E stato scelto un monolite modulare server. I microservizi non verranno introdotti prematuramente; i confini interni permetteranno in futuro di estrarre soltanto i moduli che ne avranno necessita.

### 5.1 Struttura logica obiettivo

```text
src/
├── domain/          entita, valori e regole pure
├── application/     casi d'uso e orchestrazione
├── providers/       discovery, Google, LLM, storage e adapter esterni
├── infrastructure/  database, queue, cifratura e audit log
├── web/             API, autenticazione e interfaccia
├── workers/         crawler, audit, report e retention
├── plugins/         SDK, permessi e protocollo dei plugin
└── licensing/       client licenza e verifica aggiornamenti
```

La migrazione sara incrementale. Crawler, filtri, controlli di sicurezza e contratti di dominio gia esistenti verranno conservati e spostati dietro interfacce applicative; non e prevista una riscrittura indiscriminata.

### 5.2 Servizi Docker Compose

L'installazione conterra:

- gateway HTTPS per certificati, limiti e ingresso alla piattaforma;
- web/API per utenti, workspace, configurazioni e consultazione;
- worker per discovery, crawling, audit e report;
- PostgreSQL come sistema di record;
- coda per lavori asincroni, concorrenza e retry;
- plugin runner isolato;
- storage persistente per report ed evidenze.

Streamlit potra inizialmente diventare un client del backend. In seguito potra essere sostituito senza modificare dominio, crawler, dati e autenticazione.

### 5.3 Separazione fra prodotto e control plane privato

Nel prodotto consegnato saranno presenti:

- verifica delle licenze online e offline;
- verifica dei manifest;
- verifica delle firme;
- compatibilita e installazione controllata degli aggiornamenti.

L'infrastruttura privata del fornitore gestira invece:

- emissione e revoca delle licenze;
- chiavi private di firma;
- costruzione e attestazione delle release;
- registry privato;
- pubblicazione degli aggiornamenti;
- registro commerciale dei clienti.

Il control plane privato, le chiavi di firma, le credenziali di build e i sistemi commerciali non fanno parte del sorgente applicativo consegnato al cliente.

## 6. Licensing

Saranno disponibili due modalita.

### 6.1 Licenza online

L'installazione utilizza un identificativo pseudonimo e comunica con il servizio licenze per attivazione, stato della manutenzione e autorizzazione al download degli aggiornamenti.

Un'indisponibilita temporanea del servizio non deve fermare il prodotto. E previsto un periodo di tolleranza e non verra introdotto un kill switch sui dati o sulle funzioni perpetuamente licenziate.

### 6.2 Licenza offline

Per ambienti isolati verra generato un file di licenza firmato verificabile mediante una chiave pubblica incorporata nel prodotto.

Gli aggiornamenti potranno essere trasferiti tramite bundle offline firmati. La chiave privata rimarra esclusivamente al fornitore.

### 6.3 Scadenza della manutenzione

Alla scadenza della manutenzione:

- la versione perpetua acquistata continua a funzionare;
- i dati rimangono accessibili;
- non vengono distribuite nuove release non comprese;
- assistenza e aggiornamenti richiedono rinnovo.

## 7. Aggiornamenti e supply chain

### 7.1 Manifest

L'applicazione controllera un manifest firmato pubblicato sul server del fornitore. Il manifest includera almeno:

- versione disponibile;
- versione minima compatibile;
- canale, inizialmente stabile;
- note di rilascio;
- URL autenticato o temporaneo;
- digest/hash;
- firma;
- requisiti e spazio necessario;
- compatibilita dei plugin;
- migrazioni previste.

### 7.2 Pipeline di release

```text
test
  -> dipendenze bloccate
  -> build riproducibile
  -> compilazione core
  -> SBOM
  -> scansione vulnerabilita
  -> container
  -> firma e attestazione
  -> pubblicazione nel registry privato
```

### 7.3 Installazione

Gli aggiornamenti non saranno applicati silenziosamente. Un amministratore visualizzera versione, modifiche e compatibilita e autorizzera l'operazione.

Il flusso sara:

1. verifica della licenza e della manutenzione;
2. download;
3. verifica di firma e hash;
4. controllo dello spazio e dei plugin;
5. backup;
6. migrazione del database;
7. avvio della nuova versione;
8. health check;
9. rollback automatico in caso di errore.

## 8. Plugin e protezione del core

Il core supportato non verra personalizzato direttamente. Tutte le estensioni passeranno dalla Plugin API.

Ogni plugin dichiarera:

- autore;
- versione;
- firma;
- versioni del core compatibili;
- permessi richiesti;
- funzioni o provider esposti;
- dipendenze;
- eventuali dati e migrazioni proprie.

Il plugin runner sara separato dal core. Un plugin non avra accesso diretto a:

- database;
- chiavi API;
- file interni;
- segreti;
- rete arbitraria.

Le funzioni del core saranno raggiunte attraverso un gateway con permessi, quote, timeout e validazione.

Per default verranno eseguiti soltanto plugin firmati dal fornitore. Un cliente Enterprise potra registrare una propria autorita di firma e assumersi la responsabilita dei plugin interni.

I plugin avranno limiti di CPU, memoria, durata e richieste. Un plugin incompatibile o instabile potra essere disabilitato o messo in quarantena senza fermare il prodotto. Gli aggiornamenti del core non cancelleranno i plugin.

## 9. Identita, ruoli e workspace

### 9.1 Autenticazione

Sono approvati:

- account locali sicuri;
- MFA obbligatoria almeno per gli amministratori;
- OIDC Enterprise per Microsoft Entra ID, Google Workspace, Okta e provider compatibili;
- account amministrativo locale di emergenza;
- sessioni con scadenza, rinnovo controllato e revoca;
- futura integrazione SAML soltanto se richiesta commercialmente.

### 9.2 Ruoli iniziali

I ruoli iniziali sono:

- `admin`: utenti, workspace, provider, licenze, budget e configurazioni;
- `operator`: avvio e gestione dei lavori consentiti;
- `viewer/auditor`: consultazione di risultati e audit senza modifiche operative.

Non vengono introdotti nella prima versione ruoli commerciali con assegnazione del singolo lead.

### 9.3 Workspace isolati

Anche il servizio gestito utilizzera workspace separati per cliente. Ogni workspace avra:

- membri e ruoli;
- configurazioni;
- credenziali/provider;
- budget;
- ricerche e job;
- lead ed evidenze;
- report;
- log e retention applicabili.

Il `workspace_id` sara obbligatorio sulle entita di business. L'isolamento sara applicato nel livello applicativo e, dove praticabile, tramite policy PostgreSQL come difesa aggiuntiva.

## 10. Segreti e credenziali dei provider

Le credenziali non saranno piu variabili globali lette durante l'importazione dei moduli.

Saranno:

- associate all'installazione o al workspace;
- cifrate nel database;
- protette da una chiave principale esterna al database;
- disponibili soltanto al servizio autorizzato durante l'operazione;
- escluse da log, errori, report, plugin e backup in chiaro.

Nel servizio gestito si useranno le credenziali del fornitore con contabilizzazione per workspace. Nel self-hosted il cliente usera e paghera direttamente le proprie chiavi Google, LLM e degli altri provider.

## 11. Controllo dei costi

Ogni job effettuera una prenotazione di budget prima di iniziare:

1. stima del costo massimo;
2. verifica della disponibilita;
3. prenotazione atomica;
4. contabilizzazione del consumo reale;
5. rilascio del residuo non utilizzato.

Sono approvati:

- avviso all'80%;
- blocco rigido al 100%;
- limite per singolo job;
- limite di concorrenza;
- timeout e numero massimo di tentativi;
- circuit breaker per provider in errore;
- override esclusivamente amministrativo, motivato e registrato.

La contabilizzazione atomica deve impedire che job concorrenti superino il limite prima dell'aggiornamento del saldo.

## 12. Provider di discovery sostituibili

Google non sara una dipendenza strutturale del dominio. Il core usera un contratto `DiscoveryProvider` e ogni fonte verra implementata come adapter.

Il provider restituira candidati transitori. La pipeline decidera quali attributi possono entrare nel database, con quale provenienza e con quale scadenza.

Questo consente di:

- aggiungere fonti alternative;
- disabilitare Google senza bloccare crawler e report;
- applicare policy diverse per provider;
- evitare che modelli Google contaminino il dominio applicativo;
- testare gli adapter tramite contract test comuni.

## 13. Google Places e contenuti transitori

Per dati grezzi Google si intendono i campi restituiti direttamente dalla Places API, inclusi, a titolo esemplificativo:

- nome e categoria;
- indirizzo e coordinate;
- telefono e sito web;
- rating e numero di recensioni;
- orari;
- foto e recensioni;
- `place_id`;
- risposta JSON completa.

La provenienza del singolo campo e determinante. Un dato trovato autonomamente sul sito ufficiale non deve essere confuso con lo stesso valore ricevuto da Google.

Il profilo prudente approvato prevede:

- payload completo Google usato in memoria e non persistito;
- `place_id` conservabile e soggetto a controllo periodico;
- coordinate Google conservate al massimo per il periodo consentito e comunque non oltre 30 giorni nel profilo iniziale;
- niente archivio permanente di nomi, indirizzi, foto o recensioni provenienti da Google;
- niente esportazione massiva del payload;
- attribuzione nelle visualizzazioni pertinenti;
- esclusione dagli export dei campi non autorizzati;
- disattivazione configurabile del provider.

Il caso d'uso di lead discovery nell'EEA dovra essere validato legalmente e contrattualmente prima della vendita. L'attribuzione da sola non rende automaticamente consentita la memorizzazione o esportazione.

## 14. Provenienza campo per campo

Il modello permanente non sara un dizionario indistinto. Ogni attributo significativo conterra almeno:

```text
LeadAttribute
├── tipo
├── valore
├── fonte: google | sito aziendale | operatore | derivato
├── URL o evidenza
├── data di acquisizione
├── livello di confidenza
├── eventuale scadenza
└── classificazione personale/non personale
```

Il report dovra poter dimostrare se un dato proviene:

- dal sito ufficiale;
- da un provider;
- da inserimento umano;
- da un'analisi proprietaria;
- da un modello AI.

Un valore Google non puo essere rinominato come dato del crawler senza una verifica indipendente e documentata.

## 15. Mercato, privacy e contatti

La prima versione e progettata per Italia e Unione Europea.

Il prodotto trova, verifica e inserisce contatti nei report, ma non invia automaticamente campagne email o messaggi. Le eventuali attivita di outreach vengono effettuate dal cliente con strumenti esterni e sotto la sua responsabilita.

Sono supportati:

- contatti aziendali generici;
- email nominative professionali in modalita controllata.

Prima di abilitare la raccolta di email nominative, il workspace dovra dichiarare:

- finalita;
- base giuridica scelta dal titolare;
- referente privacy;
- mercato autorizzato;
- retention.

Il software non decide automaticamente che un contatto sia legalmente utilizzabile. Fornisce provenienza, data, contesto, confidence e strumenti per documentare la valutazione.

Prima di ogni export verranno controllati:

- permessi dell'utente;
- scadenza;
- suppression;
- provenienza;
- policy del workspace;
- policy del provider.

## 16. Retention approvata

Le durate iniziali sono:

| Categoria | Retention predefinita |
|---|---:|
| Payload Google completo | Non persistito |
| Coordinate Google | Massimo 30 giorni |
| HTML completo scaricato | 7 giorni |
| Screenshot intermedi | 30 giorni |
| Evidenze selezionate nel report | 12 mesi |
| Contatti nominativi professionali | 90 giorni |
| Contatti aziendali generici | 12 mesi |
| Report e analisi | 12 mesi |
| Log operativi dettagliati | 30 giorni |
| Audit log minimale di sicurezza | 12 mesi |
| Suppression | Finche necessaria a impedire la nuova acquisizione |

Ogni record soggetto a scadenza conterra origine, `collected_at` ed `expires_at`.

La cancellazione coinvolgera database, cache e storage. I dati scompariranno dai backup con la loro rotazione documentata. Le durate potranno essere ridotte; eventuali estensioni richiederanno policy esplicita e autorizzazione amministrativa.

## 17. Suppression e diritti degli interessati

Nel servizio gestito sono previsti due livelli:

- suppression del singolo workspace;
- suppression globale dell'installazione.

Il controllo verra eseguito prima di salvare, arricchire o esportare. Una richiesta globale impedira che il crawler riacquisisca lo stesso contatto in un altro workspace.

La suppression conservera soltanto gli identificatori minimi necessari, protetti e non utilizzabili come nuovo archivio commerciale.

Saranno previste procedure per:

- accesso;
- rettifica;
- cancellazione;
- esportazione;
- opposizione o blocco di ulteriori acquisizioni;
- audit della richiesta senza ricreare il dato cancellato.

Nel self-hosted gli strumenti sono locali e sotto il controllo del cliente.

## 18. Residenza dei dati e modelli AI

Per il servizio gestito, database, storage, backup, log e osservabilita saranno ospitati nell'Unione Europea, con fornitori dotati di DPA e controllo dei sub-responsabili.

Le chiamate a provider esterni restano soggette alle loro regioni e condizioni e dovranno essere configurate e documentate separatamente.

Il core utilizzera un contratto `ModelProvider` per supportare:

- provider cloud approvati;
- modelli locali/on-premise come opzione Enterprise futura.

L'astrazione viene progettata subito; l'integrazione locale puo essere implementata in una fase successiva senza modificare il dominio.

## 19. Telemetria

Le installazioni private non invieranno al fornitore:

- lead;
- query;
- URL visitati;
- contenuti delle pagine;
- report;
- risultati di audit.

Il traffico obbligatorio per licenza e aggiornamenti conterra soltanto:

- identificativo pseudonimo dell'istanza;
- versione;
- tipo e stato della licenza;
- richiesta e risultato dell'aggiornamento.

Qualsiasi telemetria tecnica aggiuntiva sara disattivata per default e attivabile esplicitamente dal cliente.

## 20. Modello dei dati essenziale

Il sistema di record includera almeno:

- installazione/organizzazione;
- utente;
- workspace;
- membership e ruolo;
- credenziale/provider cifrato;
- policy del workspace;
- job ed esecuzione;
- candidato transitorio;
- lead;
- attributo con provenienza;
- evidenza;
- audit;
- report;
- voce di consumo e prenotazione budget;
- suppression entry;
- audit event;
- plugin e autorizzazioni;
- licenza e stato aggiornamenti.

I contratti e gli schemi saranno versionati. Gli output dei modelli AI continueranno a essere validati e trasformati in DTO pubblici tramite allowlist.

## 21. Flusso operativo

Ogni lavoro sara persistente e avra stati espliciti:

```text
queued -> validating -> running -> completed
                          ├── partial
                          ├── cancelled
                          └── failed
```

Il flusso completo e:

1. autenticazione e selezione del workspace;
2. validazione di configurazione, provider, finalita e permessi;
3. stima e prenotazione del budget;
4. acquisizione transitoria dei candidati;
5. controllo suppression e duplicati;
6. crawling con guardie di rete;
7. estrazione degli attributi con provenienza;
8. audit AI con output strutturato;
9. applicazione di confidence, retention e policy;
10. persistenza del risultato;
11. generazione del report;
12. contabilizzazione finale e audit log.

## 22. Affidabilita ed error handling

I job saranno idempotenti: un retry non deve duplicare lead, costi o report.

Sono previsti:

- retry soltanto per errori temporanei;
- backoff;
- circuit breaker;
- timeout per fase;
- limite dei tentativi;
- cancellazione controllata;
- checkpoint per lavori lunghi;
- recupero dopo il riavvio;
- risultati parziali chiaramente marcati;
- codici di errore stabili;
- nessuna eccezione grezza mostrata all'utente;
- quarantena dei plugin instabili.

Le evidenze insufficienti devono continuare a produrre un audit non valido o parziale, mai un risultato apparentemente completo e non supportato.

## 23. Audit log e osservabilita

L'audit log append-only registrera almeno:

- accessi e tentativi falliti;
- creazione e modifica dei workspace;
- variazioni di ruoli e budget;
- utilizzo e rotazione delle credenziali;
- esportazioni;
- cancellazioni e suppression;
- plugin installati o disabilitati;
- aggiornamenti e rollback;
- override amministrativi.

I log conterranno identificativi e metadati minimi, non payload completi o dati personali non necessari.

Ogni richiesta e job avra un correlation ID condiviso fra API, worker e provider. Verranno misurati:

- stato e durata delle fasi;
- successo e profondita del crawler;
- errori per provider;
- consumo e costo;
- dimensione della coda;
- retry;
- aggiornamenti e rollback;
- plugin disabilitati;
- esecuzione delle retention.

Health check e readiness check impediranno di assegnare nuovi lavori a componenti non pronti.

## 24. Backup

Nel servizio gestito, backup e restore resteranno nell'UE, cifrati e sottoposti a test periodici.

Nel self-hosted verranno fornite procedure automatizzate per:

- backup consistente del database;
- backup dello storage persistente;
- verifica dell'integrita;
- ripristino su ambiente pulito;
- test prima degli aggiornamenti.

Il cliente rimane responsabile della destinazione, frequenza e conservazione effettiva dei backup nella propria infrastruttura.

## 25. Strategia di test e criteri di release

La verifica comprendera:

- unit test di dominio, retention, ruoli, budget e suppression;
- integration test con PostgreSQL e coda;
- contract test per discovery e model provider;
- test di isolamento fra workspace;
- test di concorrenza sui budget;
- test delle migrazioni;
- backup e ripristino;
- installazione, aggiornamento e rollback;
- licenze online e offline;
- plugin validi, incompatibili, alterati e malevoli;
- end-to-end dell'intero Docker Compose;
- regressioni di sicurezza esistenti;
- scansione di dipendenze, segreti, immagini e SBOM.

Una release e pubblicabile soltanto se supera build, test, migrazione, aggiornamento e rollback sia su un ambiente pulito sia su una copia della versione precedente.

## 26. Mappatura sulla terza macrocategoria P0

La prossima implementazione seguira l'ordine strutturale seguente.

### 26.1 Fondazioni strutturali

- eliminazione della configurazione globale rigida;
- modelli persistenti;
- confini applicativi;
- workspace;
- job persistenti;
- preparazione dell'esecuzione asincrona.

### 26.2 P0-07 — Accesso, isolamento e costi

- autenticazione locale;
- ruoli iniziali;
- OIDC predisposto/Enterprise;
- isolamento dei workspace;
- cifratura delle credenziali;
- prenotazione e limite rigido del budget;
- audit amministrativo.

### 26.3 P0-04 — Google Places e provider

- contratto `DiscoveryProvider`;
- adapter Google;
- candidati transitori;
- provenienza;
- retention per provider;
- attribuzione;
- controllo degli export;
- possibilita di sostituzione/disattivazione.

### 26.4 P0-05 — Privacy e contatti

- classificazione dei contatti;
- policy del workspace;
- retention;
- suppression workspace e globale;
- richieste degli interessati;
- autorizzazione e audit degli export;
- esclusione dell'invio automatico.

### 26.5 Hardening conclusivo

- end-to-end;
- concorrenza e failure injection;
- backup e restore;
- revisione dell'audit di prodotto;
- documentazione operativa.

## 27. Strategia Git approvata per la futura implementazione

La terza macrocategoria verra realizzata in un branch dedicato derivato da `develop`.

Ogni P0 potra costituire un commit piccolo e tematico, preceduto dalle fondazioni strettamente necessarie. Il branch verra verificato prima del merge in `develop`.

Prima di iniziare le modifiche, l'assistente dovra sempre:

1. descrivere brevemente cosa intende cambiare;
2. indicare impatto e verifiche previste;
3. chiedere autorizzazione esplicita;
4. iniziare soltanto dopo la conferma.

Questo documento non autorizza da solo l'implementazione.

## 28. Riferimenti normativi e contrattuali consultati

- Direttiva 2009/24/CE sulla tutela giuridica dei programmi per elaboratore: <https://eur-lex.europa.eu/legal-content/it/ALL/?uri=CELEX%3A32009L0024>
- Pubblico Registro Software SIAE: <https://www.siae.it/it/cosa-facciamo/altri-servizi/pubblico-registro-software/>
- Commissione europea, protezione dei segreti commerciali: <https://single-market-economy.ec.europa.eu/industry/strategy/intellectual-property/trade-secrets_en>
- Google Maps Platform EEA Terms: <https://cloud.google.com/terms/maps-platform/eea>
- Places API permitted uses per clienti EEA: <https://cloud.google.com/terms/maps-platform/eea-places-api-permitted-uses>
- Policy Places API: <https://developers.google.com/maps/documentation/places/web-service/policies>
- Gestione dei Place ID: <https://developers.google.com/maps/documentation/places/web-service/place-id>
- Nuitka User Manual: <https://nuitka.net/doc/user-manual>
- Docker, code signing e Cosign: <https://docs.docker.com/dhi/core-concepts/signatures/>

## 29. Decisioni esplicitamente rinviate

Non fanno parte della prima implementazione:

- SaaS pubblico multi-tenant self-service;
- Kubernetes;
- applicazione desktop Windows;
- riscrittura generalizzata in C++;
- marketplace pubblico dei plugin;
- invio automatico di campagne;
- ruolo commerciale con lead assegnati;
- SAML, salvo specifica richiesta cliente;
- runtime locale LLM completo, pur predisponendo l'interfaccia;
- telemetria tecnica obbligatoria oltre il minimo di licenza/aggiornamento.

## 30. Criterio di successo

Il design sara realizzato correttamente quando Lead Hunter V3 potra essere eseguito come piattaforma server isolata e aggiornabile, con:

- utenti e ruoli;
- workspace senza commistione dei dati;
- costi bloccati entro budget;
- provider sostituibili;
- provenienza verificabile;
- privacy e retention applicate automaticamente;
- plugin controllati;
- container e aggiornamenti firmati;
- licenze online e offline;
- backup e rollback verificati;
- nessuna dipendenza strutturale da un singolo provider;
- un modello commerciale coerente per report, Private Managed e Self-Hosted Enterprise.
