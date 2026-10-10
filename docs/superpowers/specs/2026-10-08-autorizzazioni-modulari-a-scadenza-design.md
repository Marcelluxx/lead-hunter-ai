# Lead Hunter — Autorizzazioni modulari a scadenza

Data: 8 ottobre 2026.

Stato: design conversazionale approvato dal proprietario; specifica scritta
approvata il 9 ottobre 2026. Piano e implementazione approvati il 9 ottobre 2026;
esecuzione native con Superpowers executing-plans e review indipendente finale.

## 1. Risultato richiesto

Mantenere un solo prodotto modulare, utilizzabile sul computer/server del cliente
oppure sul server del proprietario. Il proprietario può concedere accesso temporaneo
a singole funzioni riservate emettendo licenze firmate. L'accesso viene verificato
anche nell'esecuzione delle operazioni, oltre che nell'interfaccia.

Priorità confermate: export dei lead senza sito, filtri rating/recensioni e
diagnostica completa. Questo primo sottoprogetto costruisce il sistema comune di
autorizzazioni: il recupero delle tre funzioni segue in blocchi distinti. Una licenza
non modifica le regole di provenienza/esportazione dei dati e non realizza da sola
una funzione ancora assente.

Le funzioni base perpetue e la manutenzione separata seguono il design commerciale
del 1 agosto 2026. Gli accessi aggiuntivi descritti qui hanno tutti una scadenza,
compresi quelli dell'installazione personale del proprietario, che può rinnovarli.

## 2. Contesto e base di evidenza

Il repository locale è stato sincronizzato a `main @ 19c2730`. Il core contiene
autenticazione JWT, MFA, ruoli, workspace, RLS, budget, audit log e coda job.
Il worker commerciale termina ancora con `pipeline_not_configured`.

Ed25519, `cryptography` e PyJWT sono già utilizzati da
`src/infrastructure/crypto.py`. Il licensing usa componenti separati e chiavi
distinte dall'autenticazione. Le licenze non sono credenziali per autenticarsi.

`ExportPolicy` rifiuta i risultati transitori senza sito; il DTO pubblico dell'audit
esclude prompt e output diagnostici grezzi. Questi boundary restano attivi in questo
primo sottoprogetto. Nessun cambiamento alle credenziali dei provider è incluso.

## 3. Perimetro del primo sottoprogetto

Incluso:

- catalogo di funzioni riservate con identificatori stabili e disponibilità esplicita;
- formato di licenza firmata, verifica rigorosa e importazione atomica;
- strumento locale del proprietario per creare chiavi ed emettere licenze;
- identità persistente dell'installazione e storage locale o PostgreSQL;
- autorizzazioni per installazione locale o per utente/workspace sul server;
- stato leggibile dei permessi, della scadenza e della disponibilità dei moduli;
- gestione della scadenza, rinnovo, rimozione/revoca nell'installazione;
- interfaccia applicativa comune per CLI, GUI, API e futuri handler del worker;
- controlli di regressione dell'orologio con limiti espliciti;
- migrazione server con RLS, audit e verifiche appropriate.

Rinviato ai successivi blocchi della roadmap:

- ripristino effettivo dei tre moduli riservati;
- servizio centrale di attivazione/revoca online, billing e portale clienti;
- plugin caricabili da terzi e SDK, frontend prodotto dedicato;
- collegamento della pipeline commerciale al worker e resume dei job;
- firme delle release, updater, compilazione del core e rollback.

Il primo nucleo funziona senza un servizio licenze centrale. Le interfacce di
verifica e storage permettono di aggiungerlo senza cambiare i moduli applicativi.

## 4. Alternative considerate e scelta

| Approccio | Beneficio | Costo/limite |
|---|---|---|
| Nucleo unico, moduli e licenze firmate | Stesso prodotto in locale e sul server; accessi per funzione; supporto offline | Occorre un servizio comune di autorizzazione e distinguere i destinatari |
| Solo account su server centrale | Assegnazioni e revoche centralizzate | Non copre le installazioni indipendenti offline |
| Edizioni personale/commerciale separate | Distribuzioni facilmente distinguibili | Duplica manutenzione e favorisce divergenze |

È scelto il primo approccio, come confermato dal proprietario.

## 5. Componenti e responsabilità

| Componente | Responsabilità | Dipendenze |
|---|---|---|
| Catalogo funzioni | Identificatori, etichette, disponibilità e azioni richieste | Dominio; nessun accesso a rete/storage |
| Contratto licenza | Claim tipizzati, destinatario, validità e funzioni concesse | Dominio |
| Verificatore firme | Firma, emittente, audience e versione; restituisce claim autenticati | PyJWT/cryptography, sole chiavi pubbliche fidate |
| Servizio autorizzazioni | Combina licenza, contesto, ruolo, disponibilità e tempo | Verificatore, catalogo, repository, orologio |
| Repository locale | Identità installazione, licenza attiva, revoche e massimo tempo osservato | File locali con sostituzione atomica e lock |
| Repository server | Licenze per utente/workspace, revoche e stato del tempo | PostgreSQL, transazioni e RLS |
| Strumento emittente | Genera chiavi ed emette licenze a scadenza | Chiave privata del proprietario, formato pubblico |
| Adattatori UI/CLI/API | Importazione, consultazione stato e presentazione delle decisioni | Servizio applicativo comune |

Il dominio non importa Streamlit, FastAPI, SQLAlchemy, Redis o librerie provider.
La configurazione costruisce esplicitamente i componenti, seguendo
`ApplicationContainer` e `WebRuntime`. I moduli non leggono direttamente variabili
d'ambiente per decidere i privilegi.

Le aree previste sono `src/domain`, `src/application`, `src/infrastructure`,
`src/licensing` per la verifica pubblica e `tools/license_issuer` per gli strumenti
del proprietario. Lo strumento emittente viene escluso dall'immagine cliente.
Nomi e suddivisione dei singoli file saranno fissati dal piano operativo.

## 6. Catalogo iniziale

| Identificatore | Funzione prevista | Disponibilità alla fine del primo blocco |
|---|---|---|
| `export.no_website` | Export di record senza sito con provenienza ammessa | Pianificata, fino al recupero del modulo |
| `discovery.rating_filters` | Filtri rating/numero recensioni | Pianificata, fino al recupero del modulo |
| `diagnostics.full` | Diagnostica completa per utenti autorizzati | Pianificata, fino al recupero del modulo |

La disponibilità è dichiarata dal prodotto distribuito e non dal contenuto della
licenza. Lo stato espone separatamente `license_status` e `module_status`.
Una licenza valida per un modulo pianificato indica "autorizzato, modulo non ancora
disponibile"; l'esecuzione resta bloccata.

Gli identificatori sconosciuti sono rifiutati in questo formato. Si possono
concedere uno, due o tutti e tre gli identificatori. Non esistono wildcard o
privilegi impliciti derivanti dal nome del cliente, dal ruolo admin o da `localhost`.

## 7. Formato e firma della licenza

Formato v1: JWS compatto tramite PyJWT, algoritmo consentito esclusivamente
`EdDSA` con chiave Ed25519. Header richiesti: `typ = LH-FEATURE-LICENSE`, `alg` e
`kid`. `kid` seleziona una chiave da un insieme locale fidato: nessun URL nel token
viene utilizzato per scaricare chiavi. Header alternativi di recupero chiavi e
claim/header inattesi sono rifiutati. Dimensione massima del token: 16 KiB.

Claim obbligatori:

| Claim | Significato e vincolo |
|---|---|
| `version` | Intero `1` |
| `iss` | Emittente del proprietario configurato nel prodotto |
| `aud` | Stringa esatta `lead-hunter-feature-licenses` |
| `jti` | UUID univoco dell'autorizzazione |
| `iat`, `nbf`, `exp` | Secondi Unix UTC interi; booleani/float/stringhe rifiutati; `iat <= nbf < exp` |
| `installation_id` | UUID persistente della destinazione |
| `subject_kind` | `installation` oppure `workspace_user` |
| `sub` | UUID installazione per `installation`, UUID utente per `workspace_user` |
| `features` | Lista non vuota di identificatori noti e univoci |

Per `workspace_user` è obbligatorio anche `workspace_id` UUID. Per `installation`
`workspace_id` è assente e `sub` coincide con `installation_id`.

La firma autentica tutti i claim; il server confronta il destinatario con l'identità
autenticata e il workspace della richiesta. I claim dichiarati nella richiesta
non sostituiscono questi dati. Una licenza di tipo `installation` abilita soltanto
la modalità locale e non attribuisce funzioni a tutti gli account del server.

Oggetti JSON con chiavi duplicate, campi mancanti o tipi incompatibili sono
rifiutati. Firma e claim di fiducia vengono validati prima dell'utilizzo dei dati.
La licenza non contiene email, dati di lead, prompt, segreti provider o credenziali.

## 8. Emissione e gestione delle chiavi

Il proprietario ottiene l'identificativo della destinazione, seleziona funzioni,
inizio validità e scadenza, quindi genera un file di licenza. Nel caso server
specifica anche gli UUID di utente e workspace.

Lo strumento fornisce tre operazioni: generazione di una coppia Ed25519, emissione
di licenza e ispezione del riepilogo verificato. La chiave privata viene letta da
un file; la passphrase obbligatoria viene chiesta interattivamente e non
passata nei parametri di shell. La chiave privata deve essere salvata cifrata.
Le operazioni non stampano chiavi private o token completi nei log.

Il prodotto riceve un insieme di chiavi pubbliche fidate tramite configurazione
amministrativa del deployment. L'importazione di una licenza non modifica tale
insieme. Il proprietario può distribuire una nuova chiave pubblica prima di
emettere licenze con il nuovo `kid`, conservando le precedenti fino alla scadenza
o alla loro rimozione amministrativa. Le chiavi di login rimangono separate.

Le chiavi reali restano nei percorsi ignorati `.secrets/` o equivalenti esterni;
build, repository e test non contengono la chiave di produzione del proprietario.
I test generano chiavi effimere. Nessuna firma viene presentata come protezione
assoluta contro la modifica del programma da parte del proprietario della macchina.

## 9. Identità e importazione locale

L'identità di installazione viene generata una volta, salvata nel percorso di stato
configurato e mostrata con un'operazione di consultazione. Non deriva da hostname,
MAC address o altri fingerprint hardware. Un ripristino deve conservare lo stato
per mantenere l'identità; una nuova installazione richiede una nuova licenza.

La licenza importata deve essere firmata, valida nell'istante di importazione,
compatibile con il catalogo e destinata all'installazione corrente. Le licenze con
inizio futuro sono rifiutate all'importazione e possono essere importate quando
inizia la validità. Il file precedente rimane valido
se la nuova importazione fallisce.

Per la modalità locale è attiva una sola licenza. L'importazione sostituisce
completamente l'elenco di funzioni concesse; non viene fatta un'unione con la
licenza precedente. Importare di nuovo la medesima licenza attiva è idempotente.

CLI e console locale operano nell'account del sistema che conserva lo stato;
la console ascolta solo su loopback. L'esposizione a utenti remoti richiede la
modalità server con identità autenticate e grant per utente/workspace. La licenza
locale non distingue persone che condividono il medesimo account del sistema.

Stato e rinnovi usano scritture atomiche nello stesso filesystem e lock per
processi concorrenti. Lo storage non scrivibile o corrotto impedisce nuove
operazioni riservate, con un errore leggibile; l'avvio delle funzioni base continua.

## 10. Assegnazioni sul server

Il deployment ha un UUID stabile comune ad API e worker, fornito dalla
configurazione amministrativa. Gli account sono quelli già esistenti nella
piattaforma. La licenza per un utente/workspace deve includere quel deployment.

Una nuova tabella `feature_license_grants` conserva: workspace, destinatario,
token firmato, `jti`, date e funzioni indicizzabili, attivazione, revoca, autore
dell'importazione e timestamp. Il token autenticato rimane la fonte dei permessi:
modificare solo le colonne estratte non allarga una concessione.

Si mantiene una sola concessione attiva per coppia workspace/utente; il rinnovo
revoca la precedente e attiva la nuova nella stessa transazione. La medesima `jti`
non può essere riutilizzata per riattivare una concessione revocata. Le concessioni
precedenti vengono conservate come storico, senza generare un'unione di permessi.
Reimportare la medesima concessione già attiva restituisce lo stato corrente senza
creare un'altra riga o sostituire lo storico.

La tabella è soggetta a RLS per workspace. Il ruolo worker può leggere quanto serve
alla verifica e non può importare licenze. I vincoli di appartenenza sono verificati
dall'applicazione: un utente inattivo o non più membro del workspace perde accesso.

Operazioni API previste:

- consultare le funzioni disponibili e lo stato dei propri permessi;
- per un amministratore con MFA e `MANAGE_WORKSPACE`, importare una licenza firmata
  per un utente già membro del workspace;
- con gli stessi requisiti, consultare lo stato o revocare una concessione nel
  workspace amministrato.

Essere admin consente di gestire l'importazione, non di creare o estendere licenze.
I permessi del ruolo restano necessari: per esempio `EXPORT_RESULTS` per export;
`START_JOB` per i filtri di una ricerca; `VIEW_AUDIT_LOG` e MFA per consultare
diagnostica completa; `START_JOB` e MFA per richiederne la generazione. Queste
associazioni sono metadata del catalogo per i futuri moduli, non nuovi endpoint
diagnostici in questo blocco.

## 11. Decisione comune e flusso dati

Una richiesta passa per il seguente flusso:

1. L'adattatore costruisce il contesto da installazione e identità verificata.
2. Il servizio individua la concessione per il destinatario.
3. Verifica firma, versione, audience, emittente, destinatario, tempo e revoca.
4. Verifica che la funzione sia concessa, implementata e compatibile con i permessi
   del ruolo e la MFA richiesti nell'ambiente server.
5. Il modulo applica separatamente policy dati, budget e controlli specifici.

L'interfaccia mostra la stessa decisione ma non la sostituisce. Il controllo viene
eseguito nell'operazione applicativa, anche se chiamata direttamente da CLI/API.
Un flag di configurazione non crea una concessione riservata.

Per i futuri handler del worker, il contesto deriva da `created_by`, workspace e
installazione, non da un token o elenco di permessi salvati nei parametri del job.
La coda mantiene messaggi con solo UUID. In questo blocco il worker commerciale
resta fail-closed e il contratto di verifica viene testato senza fingere di avere
già completato il collegamento della pipeline.

## 12. Scadenza, rinnovo e operazioni in corso

Una licenza è temporalmente valida se `nbf <= now < exp`. Non c'è tolleranza oltre
`exp` per le funzioni aggiuntive. UTC è il formato interno; l'interfaccia mostra
data, ora e fuso locale, con Europe/Rome come riferimento di questa sessione.

Alla scadenza:

- nuove operazioni riservate sono rifiutate;
- ogni nuovo passaggio protetto di un job richiede un nuovo controllo;
- una chiamata esterna già autorizzata può concludersi, ma la consegna o lettura
  del risultato riservato richiede una licenza valida in quell'istante;
- stato, rinnovo, funzioni base e dati già memorizzati rimangono disponibili;
- il prodotto non cancella dati e non tenta di richiamare file già scaricati.

Per rinnovo si importa una nuova licenza valida. Se la verifica fallisce, la
concessione attiva precedente non viene modificata. Un rinnovo con meno funzioni
riduce i permessi al nuovo elenco.

Lo strumento emittente può indicare date esplicite; non è imposto un abbonamento
mensile/annuale né viene introdotto un pagamento automatico.

## 13. Revoca e funzionamento offline

Nel primo blocco, il proprietario/amministratore autorizzato può rimuovere o
revocare una concessione nell'installazione a cui accede. Il server applica questa
revoca alla richiesta successiva e ai nuovi passaggi protetti; non rimane una
cache che conceda accesso dopo una revoca persistita.

Una destinazione completamente offline può ricevere la revoca solo tramite
intervento locale o futura importazione di informazioni firmate. La revoca remota
immediata e il servizio centrale sono rinviati. L'assenza di rete non blocca una
licenza offline valida; il collegamento ai provider della pipeline resta una
dipendenza operativa distinta dal licensing.

## 14. Orologio e stato persistente

Il tempo viene fornito da un'interfaccia iniettata. In produzione legge il tempo
UTC del sistema; in test è controllabile. Client e parametri dei job non possono
fornire il tempo da usare per la verifica.

Il prodotto conserva il massimo istante osservato per installazione. Un salto
all'indietro superiore a cinque minuti produce `license_clock_regression`; entro
tale intervallo usa il massimo già osservato, impedendo di prolungare la validità
per piccoli rollback. Il massimo è aggiornato atomicamente prima di concedere
una nuova operazione riservata. Sul server è condiviso in PostgreSQL tra API e
worker; in locale è conservato nel repository di stato.

Lo stato server del tempo è una tabella separata per deployment: non contiene dati
tenant. Il piano fisserà permessi DB minimi per aggiornamenti monotoni e accesso
al solo deployment configurato. L'aggiornamento usa il massimo fra stato esistente
e istante corrente, evitando regressioni dovute a processi concorrenti.

Dopo un errore dell'orologio l'operatore corregge l'ora almeno al massimo registrato;
nessun reset automatico estende licenze scadute. La manipolazione di sistema,
programma o snapshot da parte dell'amministratore della macchina non può essere
esclusa dal solo controllo offline. Questo limite è documentato operativamente.

## 15. Errori, stato pubblico e audit

Gli errori sono tipizzati, con codici stabili: `license_missing`, `license_invalid`,
`license_expired`, `license_not_yet_valid`, `license_subject_mismatch`,
`license_revoked`, `license_clock_regression`, `feature_not_granted`,
`feature_unavailable`, `feature_role_denied` e `license_storage_unavailable`.

Le API usano 401 per autenticazione mancante/non valida, 403 per accesso negato,
422 per importazione non valida e 503 per storage necessario indisponibile.
Gli errori non espongono token, chiavi, eccezioni grezze o destinatari altrui.

Lo stato leggibile comprende identificativo della licenza, destinatario autorizzato,
funzioni, inizio/scadenza, stato della licenza e disponibilità dei moduli.
La consultazione del proprio stato è possibile anche dopo la scadenza. Le API
non restituiscono il token completo conservato.

Importazione, rinnovo e revoca sono registrati nell'audit esistente sul server.
Si conservano attore, workspace, `jti`, funzioni, scadenza ed esito, senza token.
La modalità locale registra gli stessi eventi amministrativi in forma redatta.
Le risposte standard del servizio di licenza non contengono prompt o diagnostica.

## 16. Verifica e criteri di accettazione

1. Firma alterata, algoritmo alternativo, chiave sconosciuta, audience/emittente
   errati, chiavi JSON duplicate, token oversize o claim non validi non concedono accesso.
2. Le soglie temporali sono testate prima di `nbf`, su `nbf`, prima di `exp` e su
   `exp`, senza dipendere dall'orologio reale o da attese.
3. Licenze per altra installazione, altro workspace o altro utente sono rifiutate.
4. La combinazione licenza/ruolo/MFA/membership è verificata su API e servizio comune;
   un admin senza licenza non ottiene automaticamente una funzione riservata.
5. Un modulo pianificato resta indisponibile anche con licenza valida.
6. Rinnovo valido sostituisce atomicamente la concessione; rinnovo invalido non la
   danneggia; reimport della concessione attiva è idempotente; una `jti` revocata
   non torna attiva e un rinnovo ridotto non conserva vecchi permessi.
7. Due processi concorrenti non corrompono lo stato locale né perdono revoche o
   aggiornamenti del tempo; le transazioni server rispettano i medesimi vincoli.
8. PostgreSQL verifica RLS dei grant, isolamento tra workspace, permessi worker,
   vincoli univoci e round trip delle migrazioni. Gli skip di integrazione non
   vengono presentati come verifiche superate.
9. CLI e GUI consultano il servizio comune; gli ingressi diretti non concedono
   accessi per il solo fatto che un pulsante sia nascosto o un flag sia impostato.
10. Scadenza durante un flusso simulato blocca il successivo passo protetto e la
    consegna di risultati riservati; la base resta operativa.
11. I contratti di verifica dei futuri job ricostruiscono il destinatario dai dati
    persistenti e non accettano permessi dichiarati dai parametri.
12. Licenza assente, clock regression e storage corrotto/non scrivibile negano
    funzioni riservate, senza disabilitare quelle base.
13. Build cliente e log non contengono chiavi private, strumenti emittenti o token
    completi; l'API non pubblica il materiale diagnostico.
14. Restano verdi le verifiche dei boundary esistenti di SSRF, evidenza, export,
    privacy, autenticazione e budget toccati dall'integrazione.

## 17. Collegamento alle milestone complessive

1. Questo blocco: licensing e autorizzazioni modulari a scadenza.
2. Recupero diagnostica completa con canale riservato e limiti di conservazione.
3. Recupero filtri rating/recensioni con un provider e un uso dei dati definiti.
4. Recupero export senza sito con record/provenienza adatti anche a fonti ammesse
   diverse dal sito ufficiale; non basta eliminare il rifiuto del DTO transitorio.
5. Collegamento pipeline al worker, riprendendo la roadmap corrente del README.

L'ordine dei tre recuperi è una proposta tecnica: tutte e tre le aree restano nel
perimetro richiesto dal proprietario. Link discovery AI, High-Fidelity e altri
campi report individuati nella ricognizione restano candidati da concordare.

## 18. Fonti e passaggio successivo

- [Nota di ripresa](../../RIPRESA_MODERNIZZAZIONE_2026-10-08.md).
- [Audit e roadmap](../../AUDIT_PRODOTTO_E_ROADMAP_STATO_DELL_ARTE.md).
- [Design commerciale precedente](2026-08-01-architettura-commercializzazione-e-p0-governance-design.md).
- [Roadmap operativa](../../../README.md#roadmap).
- [Documentazione PyJWT](https://pyjwt.readthedocs.io/en/stable/usage.html).
- [Documentazione Ed25519 di cryptography](https://cryptography.io/en/latest/hazmat/primitives/asymmetric/ed25519/).

Il proprietario ha approvato questa specifica il 9 ottobre 2026. È stato redatto il
[piano operativo](../plans/2026-10-09-autorizzazioni-modulari-a-scadenza-implementation-plan.md)
con Superpowers writing-plans; approvato il 9 ottobre 2026 e in esecuzione native.
