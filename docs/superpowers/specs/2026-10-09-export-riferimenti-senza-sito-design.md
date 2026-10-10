# Export dei riferimenti Google per attività senza sito

Data: 9 ottobre 2026, Europe/Rome.

Stato: specifica scritta approvata dal proprietario il 9 ottobre 2026.
Piano operativo approvato il 9 ottobre 2026; implementazione pubblicata nella PR draft #8.
Metodo di esecuzione scelto: native.

Base: `876c839`, core delle licenze nella PR draft #7.
Branch dedicato: `codex/no-website-reference-export`, derivato da
`codex/expiring-feature-licenses`. La PR #7 resta il prerequisito di integrazione.

## 1. Risultato approvato

Recuperare un export Excel utile per ritrovare su Google Maps le attività
individuate dalla ricerca senza sito. Il proprietario ha scelto i risultati delle
ricerche Google Places esistenti, usa una normale chiave API e ha approvato la
variante limitata ai riferimenti, anziché il precedente report completo.

Il file contiene esattamente due colonne: **Place ID** e **Link Google Maps**.
Ogni identificativo compare una volta, nell'ordine della prima occorrenza.
Il confronto degli identificativi è esatto e distingue maiuscole e minuscole.
Il link apre Google Maps con l'identificativo del luogo come destinazione.
Il report è una raccolta di riferimenti della ricerca: non certifica che
un'attività sia tuttora senza sito o che un identificativo sia ancora valido.

La funzione `export.no_website` diventa disponibile dopo il completamento del
modulo. Generazione e consegna richiedono una licenza valida per questa funzione.
Le ricerche base, i report con sito e le altre funzioni mantengono il loro percorso.

## 2. Fonti e motivazione del confine

La documentazione Google consente di conservare i Place ID e descrive i link Maps
con `query_place_id`. Le condizioni standard limitano invece l'esportazione dei
contenuti Places, inclusi nomi e indirizzi delle attività.

- [Policy Places e eccezione per Place ID](https://developers.google.com/maps/documentation/places/web-service/policies).
- [Identificativi dei luoghi](https://developers.google.com/maps/documentation/places/web-service/place-id).
- [Sintassi dei link Maps](https://developers.google.com/maps/documentation/urls/get-started).
- [Condizioni EEA, §3.3.2](https://cloud.google.com/terms/maps-platform/eea).

L'Excel e il relativo contenitore ZIP non includono nomi, indirizzi, coordinate
Google, telefoni, rating, recensioni, keyword di ricerca, risposte provider,
prompt, credenziali o token di licenza: né nelle celle né in commenti, fogli
nascosti, proprietà o collegamenti aggiuntivi. La licenza dell'app non amplia i
diritti sulla fonte. `ExportPolicy` continua a rifiutare l'export del contenuto
di `TransientCandidate` e il vecchio report completo `no_website`.

## 3. Architettura e contratto dei riferimenti

Un contratto immutabile dedicato contiene soltanto `place_id`. Una proiezione
esplicita estrae questo identificativo dai candidati Google della ricerca senza
sito, verificando `provider == google_places` e `website_url is None`.
Non converte il candidato transitorio in un `VerifiedLead`.

Il servizio comune riceve solo riferimenti tipizzati, un verificatore di accesso
e una funzione che ricostruisce il contesto corrente. Non accetta dizionari di
risposta Places, contenuti del provider o booleani client come autorizzazione.
Un chiamante server deve acquisire i riferimenti nel workspace autenticato e
ricostruire utente/membership/ruolo a ogni controllo. La sola stringa di un Place ID
non prova l'appartenenza a un workspace.

Il serializer XLSX riceve i soli riferimenti validati e produce byte in memoria.
La funzione applicativa protegge generazione e consegna; GUI e CLI la riutilizzano.
Le funzioni di formattazione non diventano un percorso pubblico alternativo che
consenta il nuovo export senza controllo di licenza.

Il servizio è utilizzabile anche dal backend e viene testato con un contesto
server corrente. Endpoint pubblici per l'export dei job e collegamento al worker
commerciale restano nella milestone del worker: questo sottoprogetto non dichiara
già eseguibile la pipeline server né modifica `pipeline_not_configured`.

## 4. Validazione e formato XLSX

Gli identificativi devono essere stringhe ASCII di 1–500 caratteri con grammatica
applicativa `[A-Za-z0-9][A-Za-z0-9_-]{0,499}`. Il limite riflette il contratto
applicativo/database attuale; non afferma un limite universale dei Place ID Google.
Nuovi formati non riconosciuti richiedono un aggiornamento esplicito del contratto.
Valori vuoti, formule, spazi/control character e record non tipizzati sono rifiutati.
Un errore invalida l'intero batch prima che un file venga consegnato.

Massimo 10.000 elementi in ingresso, prima della deduplicazione; il limite viene
applicato anche agli iteratori senza materializzazione illimitata. Un batch vuoto
non produce un file. Le due colonne contengono testo, senza formule Excel.
Il foglio `Riferimenti` ha header, filtro e prima riga bloccata; nessun foglio nascosto.

I link sono costruiti con una libreria di encoding URL, host e schema fissi:

`https://www.google.com/maps/search/?api=1&query=attivit%C3%A0&query_place_id=PLACE_ID`

`query` è un testo generico costante, richiesto dalla sintassi Maps; non contiene
nomi o indirizzi Google. `query_place_id` contiene l'identificativo codificato.
Il target dell'hyperlink Excel coincide con il valore della cella ed è sempre
HTTPS sul dominio `www.google.com`. Se l'ID non è più riconosciuto, Maps può usare
la ricerca generica: il software non inventa dati o garantisce la risoluzione.
La creazione dell'Excel non effettua richieste di dettaglio o refresh a Google.

## 5. Licenza, scadenza e consegna

Il servizio usa `FeatureAccessService` e la concessione `export.no_website`.
Prima della generazione richiede `EXECUTE`; prima della consegna richiede `VIEW`
con un contesto ricostruito. Sul server entrambi richiedono `EXPORT_RESULTS`;
il ruolo da solo non sostituisce la licenza. Restano applicabili firma, soggetto,
workspace, revoca, regressione dell'orologio e regola `nbf <= now < exp`.

La licenza non viene memorizzata come permesso booleano in sessione. Se scade,
viene revocata o perde la funzione mentre l'Excel è in preparazione, i byte non
sono consegnati e il salvataggio definitivo non avviene. Stato, rinnovo e ricerca
base rimangono disponibili. I dati già ricevuti dal browser o salvati sul computer
non vengono richiamati o cancellati alla scadenza.

In GUI non è sufficiente autorizzare un callback che genera una URL statica:
Streamlit 1.60 registra il file generato nel media manager, da cui la successiva
lettura non ripete il controllo applicativo. Il nuovo export deve quindi consegnare
i byte al browser tramite contenuto inline autorizzato, senza pubblicarli nel
media manager/static directory o in una URL server riutilizzabile senza verifica.
L'eventuale link `data:` XLSX appartiene al materiale già ricevuto dal browser.
Il suo HTML è generato da MIME, nome file costante e base64, senza markup provider.

Questo requisito è verificato sul flusso effettivo di consegna, non dedotto dal
solo stato del pulsante. La componente comune non dipende da Streamlit.

## 6. Interfacce locali

### GUI

La ricerca continua a mostrare i risultati transitori con l'attribuzione esistente.
Una sezione dedicata permette di preparare e ricevere l'Excel dei riferimenti
dell'ultima ricerca senza sito. La UI comunica che il file contiene soltanto ID
e link; il nome della funzione nel catalogo lo rende esplicito.

Per i rerun della GUI si conservano soltanto gli identificativi normalizzati
dell'ultima ricerca, senza il payload Places o gli altri attributi del candidato.
All'avvio di una nuova ricerca si azzerano quei riferimenti; una ricerca vuota o
fallita non riattiva il report di una ricerca precedente. Il controllo della
licenza si ripete quando si prepara e quando si consegna il contenuto.
L'assenza di licenza o trust impedisce l'export, continuando a consentire la ricerca.

### CLI

`--export-references` attiva esplicitamente l'export con `--mode no_website`;
`--out` indica la destinazione secondo la gestione dei path già esistente.
La combinazione con `--mode with_website` viene rifiutata dal parser.
Se la funzione è richiesta, si verifica la licenza prima delle chiamate Google.
Senza il flag, la ricerca senza sito mantiene il comportamento base.

Il file definitivo viene scritto con temporaneo nello stesso filesystem e
sostituzione atomica, dopo un ulteriore controllo di consegna. Gli errori prima
della sostituzione preservano un eventuale file precedente e ripuliscono il
temporaneo. Un file aperto o una destinazione non scrivibile causano un errore
esplicito; non viene stampato un successo dopo un salvataggio fallito.

## 7. Errori e disponibilità

I dinieghi usano gli errori redatti del licensing. Gli errori del modulo distinguono
input non valido, nessun riferimento, limite del batch e scrittura fallita.
Log ed eccezioni pubbliche non includono il batch, contenuti provider o token.
Non viene introdotto un nuovo journal di audit dei riferimenti né una migrazione.

Solo `export.no_website` passa da `planned` ad `available` quando l'intero flusso
approvato è implementato e verificato. I filtri rating/recensioni e la diagnostica
completa restano pianificati. Manuale e milestone descrivono il recupero limitato
ai riferimenti, evitando di dichiarare ripristinate le vecchie colonne complete.

## 8. Accettazione e verifiche

- Una ricerca senza sito produce riferimenti Google tipizzati; candidati con sito
  o provider diverso non diventano riferimenti di questo export.
- Workbook reale riaperto con openpyxl: due colonne esatte, ID deduplicati,
  link e target corretti, nessuna formula. Ispezione ZIP/proprietà: nessun contenuto
  provider aggiuntivo, foglio nascosto, credenziale o token.
- Batch vuoti, input misti, ID ostili/malformati, limite di 10.000 e iteratori
  eccedenti non producono un file o byte consegnabili.
- Licenza assente, alterata, scaduta, revocata, di altro soggetto o senza questa
  funzione impedisce l'export, anche chiamando direttamente il servizio.
- Clock controllato che supera `exp` durante il serializer, revoca/rinnovo durante
  la preparazione e contesto server che perde ruolo/membership negano la consegna.
- Chiamanti server: workspace corrente, ruolo autorizzato e contesto ricostruito;
  i controlli non derivano da parametri, token o flag del client.
- CLI: flag, percorso e salvataggio reale, errore su scrittura/sostituzione,
  preservazione del file precedente, cleanup del temporaneo e zero chiamate Google
  quando la licenza richiesta viene negata all'ingresso.
- GUI: rerun con riferimenti dell'ultima ricerca, azzeramento su nuova ricerca,
  preparazione e ricezione reali, controlli di scadenza/revoca e assenza di URL
  statiche server che permettano una nuova consegna dopo il diniego.
- Regressioni del report con sito, export policy, formula injection, discovery,
  UI/licensing, packaging e suite completa. Controlli CI supportati Python 3.10–3.13.

Le prove dipendenti dal server completo restano proporzionate allo scope: questa
fase testa il servizio comune con il contesto server, senza inventare un worker
commerciale funzionante. Il blocco NLTK della PR #7 rimane un gate di release
distinto; la specifica non propone eccezioni all'audit o aggiornamenti dipendenze.

## 9. Passo successivo

Il modulo è implementato e la review indipendente è stata recepita con test
RED→GREEN. Verificare i gate della PR draft #8 sull'HEAD finale; l'integrazione
dipende dalla PR #7 e il gate NLTK resta bloccante per la release commerciale.
I recuperi successivi sono filtri rating/recensioni e diagnostica completa,
seguiti dal collegamento della pipeline commerciale al worker.
