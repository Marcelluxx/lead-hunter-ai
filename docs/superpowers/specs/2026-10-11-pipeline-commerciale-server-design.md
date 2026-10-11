# Pipeline commerciale server — design

11 ottobre 2026. Sottoprogetto architetturale della roadmap autonoma del proprietario.
Intento: eseguire le ricerche commerciali e gli audit indipendenti nel worker,
mantenendo moduli riservati con licenze a scadenza, isolamento workspace e budget.
Metodo native; scelte ordinarie delegate, specifica/piano autorevisionati.

## Architettura scelta

Estendere orchestrazione e servizi esistenti invece di avviare una seconda pipeline
o richiamare la GUI. Handler registrati e parametri stretti separano ammissione,
esecuzione, persistenza e consegna. Actor Dramatiq riceve solo UUID; transazioni
brevi per claim/checkpoint e controlli prima di azioni esterne, mai una transazione
con lock job durante il lavoro rete. Runtime per workspace risolve le credenziali
cifrate; nessun token, ruolo, MFA o costo scelto dal client diventa autorità.

Alternative considerate: subprocess CLI (pochi adattamenti ma controllo/cancellazione
e contesti non affidabili), riscrittura completa (duplicazione dei gate). Il riuso
con guard comune e handler dedicati mantiene licenze, provenance e test già presenti.

## Contratti e limiti

Kind supportati: `discover.no_website`, `discover.with_website`, `audit.website`,
`diagnostic.website`. Parametri JSON normalizzati, extra vietati, versione 1.
Discovery: lat/lng finiti negli intervalli geografici (zero valido), 1–5 keyword
uniche da 1–100 caratteri, max_leads 1–100 (default 20), max_pages 1–20 (default 5),
max_leads * max_pages <= 200 per audit. Token mode high_fidelity/optimized.
Filtro rating opzionale nelle due modalità, soglia strettamente superata come nel
modulo esistente; grant discovery.rating_filters richiesto a esecuzione/consegna.
Audit.website: 1–20 URL pubblici sintatticamente validi e senza credenziali,
max_pages 1–20, numero URL * max_pages <= 200. Diagnostic.website: un solo URL,
max_pages 1–20, retention intera 1–168 ore (default 24), grant diagnostics.full
con MFA corrente e permessi EXECUTE/VIEW (il servizio comune sigilla sotto VIEW).
Sintassi verificata prima di prompt/cleanup; URL policy e rete
restano verifiche distinte su ogni richiesta/redirect.

Solo campi permessi entrano nei parametri; nessun payload Google, raw HTML,
credenziale, path output, costo, ruolo, booleano MFA o identità controllato dal client.
Risultati: riferimenti Place ID/Maps link consentiti e lead da sito indipendente con
provenance/evidenza, contatti sotto policy/privacy/suppression esistenti. Metriche
Google e materiali diagnostici non entrano nei DTO cliente o checkpoint.
Diagnostica in archivio privato UUID, redatto, con limite/scadenza del servizio comune;
API consegna soltanto dopo VIEW+MFA+licenza attuale e deadline originale.

## Esecuzione, cancellazione e ripresa

Persistenza server di sessione d'origine/versione, lease/tentativo, checkpoint
bounded e richiesta cancellazione con migrazione reversibile e RLS workspace.
Worker ricontrolla sessione, account, membership, workspace e grants per fase e
prima delle chiamate esterne. Logout/scadenza/session-version fermano esecuzione.
Claim esclusivo con lease; tentativi <= 3, heartbeat, coda morta esplicita tramite
stato failed/codice/registro tentativi consultabile. Ripresa esplicita solo per job
interrotti recuperabili e nuova sessione autorizzata; risultati già verificati non
vengono duplicati. Mai riavvio automatico di lavori cancellati o senza accesso.

Checkpoint solo identificatori/contatori/fase e riferimenti indipendenti già
verificati; discovery transitoria si ripete quando necessario, senza persistere
URL/nome da Google. Idempotenza della persistenza e dei claim, inclusa redelivery.

## Budget

Quote server da configurazione operatore versionata e limiti massimi di chiamate,
non estimated_cost del client. Prezzi mancanti bloccano lavoro a pagamento prima
che venga accodato. Retry SDK disabilitati nel percorso server; ogni tentativo
provider passa dal guard e dal budget durevole. Contabilità prudenziale delle
chiamate autorizzate con tetti configurati, distinta da fatturazione cliente e da
una dichiarazione di tariffa Google/OpenRouter corrente; documentare incertezza
quando il provider non restituisce un costo verificabile. Nessuna credenziale
reale o acquisto richiesti per test e implementazione.

Nel worker, pulizia delle pagine sequenziale per fermare anche richieste sorelle
dopo revoca/cancel; timeout SDK 20 secondi, massimo 2000 token output e richiesta
JSON fino a 200KB. Nessun fallback presentato come audit riuscito dopo errore AI.
Archivi diagnostici sotto cartella server/workspace, UUID nel checkpoint; expiry
e classificazione dal manifest bounded, nessun path client o payload privato nel DB.

## Verifica e stato

TDD con validazione strict, queue UUID, licenze Ed25519/DB reali, contesti correnti,
revoca/cancellazione nei callback HTTP, duplicati/lease/ripresa/costi, workspace
incrociati e privacy. PostgreSQL concorrente e RLS, roundtrip migrazioni, API fino
al risultato e ZIP/XLSX riaperti, Chromium e suite. Review fresca finale, CI/Security
esatto HEAD prima dell'integrazione develop. Nessun rilascio clienti implicito.

Spec autorevisionata: coerente con roadmap, riferimenti consentiti, MFA e retention.
Interfacce dettagliate nei task del piano; eventuali deviazioni registrate nel ledger.
