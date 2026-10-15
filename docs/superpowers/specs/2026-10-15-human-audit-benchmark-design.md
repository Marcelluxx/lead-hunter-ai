# Benchmark umano degli audit — design

15 ottobre 2026. Sottoprogetto architetturale della milestone qualità audit.
Il proprietario ha chiesto di iniziare e ha scelto esplicitamente due giudizi
distinti: qualità del sito e priorità di intervento. Specifica e piano sono
autorevisionati sotto la delega autonoma già vigente; esecuzione native.

## Scopo e alternative

Preparare un percorso locale ripetibile per campioni, revisioni umane cieche ai
punteggi automatici e confronto. Non produrre un gold set inventato o cambiare
la rubrica dom-markup-1. Il successo è un flusso CLI offline verificato che
prepara dati minimali, raccoglie valutazioni e calcola metriche controllabili.

Alternative considerate: aggiungere subito UI/database/ruoli di annotazione
(più dipendenze prima di conoscere il protocollo); un foglio libero (rapido ma
senza binding o controllo dei tipi); JSON locali rigorosi e CLI (scelta: minore
superficie, testabile, riutilizzabile in una futura UI). Nessun nuovo provider,
dipendenza, migrazione o accesso diretto al DB. Solo file già lecitamente
ottenuti dall'operatore; il tool non scarica dati né aggira licenze/privacy.

## Campioni versionati

Package `src/benchmark`, separato dal runtime produttivo. Un dataset contiene
esattamente schema_version=1, prediction_version, samples, dataset_sha256.
prediction_version è un identificatore operatore ASCII [A-Za-z0-9_.-], 1–100
caratteri: identifica codice/modello/configurazione, non certifica il modello.
Da 1 a 500 campioni; intero JSON massimo 32 MiB UTF-8.

Input record: esattamente source_url, captured_at, website_score, dom_report,
score_report. source_url usa la proiezione pubblica condivisa: query/fragment e
path sensibili riconoscibili rimossi; userinfo rifiutata. Solo sintassi, nessun
DNS/fetch. captured_at ha timezone esplicita, normalizzato ISO UTC. website_score
è null o intero 1–10 (stringhe legacy ammesse solo nell'adapter API, mai bool).
DOM e score sono validati con i contratti esistenti. L'empty score storico è
ammesso anche con DOM presente, senza applicare retroattivamente la rubrica.
Ogni timestamp di pagina DOM deve essere <= captured_at, che rappresenta
l'istante dell'esportazione del campione, non necessariamente del singolo fetch.

Ogni campione aggiunge sample_id=s_<SHA256> della sua proiezione canonica,
incluse predizioni/copertura/tempi. Dataset ordinato per sample_id; hash radice
su schema/prediction_version/samples, senza il campo digest. Duplicati di URL
pubblico+captured_at rifiutati, così lo stesso snapshot non pesa due volte.
La validazione ricostruisce l'intero documento e confronta JSON canonico.
Digest rileva incoerenze, non autentica un operatore che modifica tutto.

## Revisione umana e rubrica human-site-1

Un review packet contiene schema_version=1, rubric_version=human-site-1,
dataset_sha256, reviewer_id (pseudonimo ASCII 1–64 [A-Za-z0-9_-]) e reviews.
Ogni riga: sample_id, source_url, captured_at, status, reviewed_at,
quality_score, intervention_priority, reason. Nessun voto AI, indice DOM,
diagnosi, messaggio commerciale o altra indicazione del modello.

La scheda nuova è pending, reviewed_at/scores null e reason null. Il revisore
compila tutte le righe, oppure può lasciarne alcune pending. Per reviewed:
reviewed_at UTC esplicito >= captured_at, quality_score intero 1–10,
intervention_priority intero 0–3, reason null. Per unassessable: data valida,
entrambi i punteggi null e reason uno di unavailable/changed_site/
insufficient_context/other. Pending richiede tutti i campi decisionali null.
Non si raccolgono testo libero, contatti, nomi o segreti nel formato v1.

Qualità: 1–2 gravemente insufficiente; 3–4 debole; 5–6 adeguata con limiti;
7–8 buona; 9–10 molto buona. Considerare chiarezza dei contenuti, facilità
dei compiti, fruibilità visiva/mobile e fiducia; è un giudizio operativo umano,
non una certificazione di accessibilità o sicurezza. Priorità: 0 nessun
intervento evidente; 1 miglioramento non urgente; 2 intervento utile e
prioritario; 3 problema che blocca un compito importante. Non inferire budget,
intenzione d'acquisto o potenziale economico. Non derivare una scala dall'altra.

Packet legato a dataset esatto, con tutte le righe una volta, ordine canonico,
URL/tempo uguali al dataset. Variazioni a versione/hash/prove invalidano il
legame. Più revisori sono ammessi; un reviewer_id può comparire una sola volta
nella valutazione. Nessuna fusione silenziosa di giudizi sovrascritti. I
pseudonimi non sono identità autenticate: l'operatore attesta chi ha revisionato.
Il sito osservato live può cambiare: usare changed_site e ripetere il campione
se serve. Non si sostiene un confronto temporale controllato da questi file.

## Metriche e incertezza

Ogni campione con almeno un reviewed usa la media dei giudizi per dimensione;
un campione pesa una volta, indipendentemente dal numero di revisori. È un
riferimento umano provvisorio, non un gold set adjudicato. Pending e
unassessable non diventano voti zero. Metriche null se non calcolabili.

Report schema1, metric_version=human-audit-comparison-1, dataset/hash/rubrica,
calibration_status=uncalibrated. Conteggi di campioni, revisori, reviewed,
pending, unassessable, copertura DOM complete/partial/unavailable. Per-campione:
ID, n giudizi, media qualità/priorità, AI/markup null o numerico e stato DOM;
nessun URL o reviewer_id nel report valutativo.

AI vs qualità umana: n, MAE, RMSE, bias (AI meno umano), Spearman. Indice DOM
vs qualità, AI vs priorità e indice DOM vs priorità: n e Spearman soltanto,
senza comparare scale diverse con MAE o assumere un verso della relazione.
Spearman = Pearson dei ranghi medi dei pari; n<2 o rango costante produce null.
Metriche arrotondate a 6 decimali; nessun test di significatività, intervallo
di confidenza o calibrazione automatica. Risultati anche separati per stato
DOM per rendere visibile il campione parziale.

Accordo umano: per ciascuna dimensione numero di coppie intra-campione e
distanza assoluta media delle coppie (unità originali). Campioni con un solo
revisore non contribuiscono. Non chiamarlo inter-rater reliability calibrata.

## CLI e file

`python -m src.cli.benchmark prepare --input snapshots.json --prediction-version
VERSION --out dataset.json` accetta {schema_version:1,samples:[input record]}.
`--from-job` proietta invece una risposta /jobs/{id}/results completed del
server. Solo lead id, attributi website/website_score, provenienza e report DOM/
score sono consumati; contatti/nome/Google/prompt non sono copiati né hashati.
captured_at è richiesto tramite --captured-at per questo adapter, perché il
risultato job non dichiara l'istante di esportazione. Score assente resta null,
report assenti diventano gli empty storici. Entrambi i report sono richiesti
se il punteggio derivato non è storico; input incompleto/corrotto rifiutato.

`review-packet --dataset FILE --reviewer ID --out FILE` crea la scheda cieca.
`evaluate --dataset FILE --reviews FILE [FILE ...] --out FILE` confronta.
Il file valutazioni non deve contenere più di 500 packet, unici per revisore.
Tutti i file letti bounded 32 MiB; anche l'insieme dei packet di una valutazione
è limitato a 32 MiB serializzati e 32 MiB complessivi letti dai file, prima
di caricarli tutti in memoria. JSON con chiavi duplicate/NaN vietati,
profondità e valori invalidi producono codice sicuro senza contenuti/path.
Output UTF-8 JSON, scrittura su file nuovo esclusivo con permessi 0600 dove
supportati; niente overwrite, anche input=output; fsync, chiusura e rimozione
del solo nuovo file se scrittura fallisce. Nessun --force nel v1.
Exit0 successo, exit2 errore; stdout contiene solo esito sintetico sicuro.
Cartella consigliata .benchmark-data, ignorata da Git e Docker. Nessun dataset
umano reale committato; fixture sintetiche soltanto nei test, dichiarate tali.

## Verifica e fuori scope

TDD su snapshot/digest/mancanti/zero/tipi/duplicati/versioni, review cieca,
binding/tempi, due scale separate, ranking ties/segno/degenerati, aritmetica
indipendente, duplicazione revisori e mancanti. Flusso subprocess CLI senza
configurazione/credenziali, errori bounded senza leak, file precedente intatto,
adapter della risposta server corrente e privacy della proiezione. Suite
esistente, PostgreSQL/Chromium/distribuzione e gate GitHub esatto HEAD.

Fuori scope: raccolta automatica live, UI clienti, nuovo licensing, import
Google, certificazioni, selezione rappresentativa automatica, train/test split
per fit di pesi, adjudication, calibrazione/pesi nuovi, credenziali produttive.
Prima di calibrate servono campione reale, protocollo di campionamento,
revisioni e validazione separata. Target orientativo 200–500 siti successivo.
