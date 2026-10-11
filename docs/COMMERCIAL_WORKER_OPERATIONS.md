# Pipeline commerciale server

La coda contiene soltanto UUID. Sessione, workspace, permessi, licenza e credenziali
vengono letti dal server; questo lavoro non attiva pagamenti o una release pubblica.

## Configurazione

Applicare le migrazioni con il ruolo owner, poi avviare API, worker, Redis,
`job-recovery` e retention di `compose.yml`. App e worker usano ruoli PostgreSQL
distinti senza bypass RLS. Il recupero pubblica al massimo500 UUID ogni30 secondi:
jobs è la fonte durevole quando Redis non riceve un messaggio; lease esclusiva
e checkpoint gestiscono invii ripetuti e processi interrotti.

Nel workspace salvare credenziali cifrate per `google_places` e `openrouter`
tramite secrets (admin e MFA). Nessun fallback alle chiavi globali locali.
Trust licensing solo pubblico e UUID installazione stabile condiviso.

Audit e diagnostica richiedono il bundle prompt privato conforme a `src.prompting`.
In Compose montare `secrets/private-prompts/private_audit_prompts.py` in sola lettura;
`LEADHUNTER_PROMPT_MODULE` sceglie il modulo importabile. Il bundle non viene copiato
nell'immagine né nel repository. Un bundle mancante produce `job_prompts_missing`
prima di chiamare l'AI. La ricerca senza sito non richiede questo bundle.

| Variabile | Significato |
|---|---|
| `LEADHUNTER_JOB_PRICE_VERSION` | Versione delle ipotesi di costo |
| `LEADHUNTER_JOB_GOOGLE_CALL_CEILING` | Tetto per tentativo HTTP Google |
| `LEADHUNTER_JOB_LLM_CALL_CEILING` | Tetto per tentativo HTTP AI |
| `LEADHUNTER_JOB_COST_CURRENCY` | Valuta uguale al budget workspace |

Tetti finiti, positivi, sei decimali; prezzi richiesti mancanti bloccano il lavoro.
`estimated_cost` client accettato per compatibilità, ignorato. Prenotazione massima:
18 richieste Google/keyword e 3 richieste AI/pagina più3 per audit finale, per sito.
Una configurazione cambiata richiede nuovo job/quote.

Il ledger registra **stime conservative delle chiamate autorizzate**, anche quando
un processo muore prima della risposta. Non certifica il costo effettivo provider
né la fattura cliente. L'operatore deve configurare tetti adeguati ai propri modelli;
riconciliazione e fatturazione appartengono al sottoprogetto billing.

## API

Base `/workspaces/{workspace_id}/jobs`, autenticazione richiesta. POST richiede
`Idempotency-Key`; stessa chiave con parametri/proprietario diversi: conflitto.

| Kind | Parametri | Risultato |
|---|---|---|
| `discover.no_website` | lat/lng, keywords, max_leads | Place ID/link Maps |
| `discover.with_website` | lat/lng, keywords, max_leads, max_pages, token_mode | Lead, audit ed evidenze indipendenti |
| `audit.website` | urls, max_pages, token_mode | Audit dei siti indicati |
| `diagnostic.website` | url, max_pages, token_mode, retention_hours | ZIP diagnostico privato redatto |

Schema1. Coordinate finite (zero valido), keyword uniche1–5 da1–100 caratteri,
max_leads1–100/default20, max_pages1–20/default5. Audit diretto1–20 URL; massimo
200 pagine complessive anche nella ricerca con sito. URL senza credenziali, sintassi
validata prima di effetti; policy rete verifica indirizzi/redirect nel crawling.
Extra, segreti, payload Google, path, ruoli e flag MFA client respinti.

`rating_filters: {min_rating, max_reviews}` opzionale nelle due ricerche richiede
`discovery.rating_filters`; metriche solo nell'adapter Google. Export riferimenti:
`export.no_website`. Diagnostica: `diagnostics.full`, MFA, permessi EXECUTE/VIEW;
il ruolo admin li possiede.

| Azione | Endpoint relativo |
|---|---|
| Stato/codice errore sicuro/tentativi | `GET /{job_id}` |
| Risultati con provenance/contatti consentiti | `GET /{job_id}/results` |
| Excel o ZIP diagnostico | `GET /{job_id}/export` |
| Cancellazione | `POST /{job_id}/cancel` |
| Ripresa del proprio job recuperabile | `POST /{job_id}/resume` |

Controlli correnti prima delle azioni esterne e della consegna. Una richiesta già
inviata non può essere ritirata; cancel/revoca impediscono la successiva. Retry SDK
nascosti disabilitati; AI timeout20s, output massimo2000 token, richiesta fino200KB.
Pulizia sequenziale per impedire richieste sorelle dopo revoca. Massimo3 tentativi;
checkpoint e risultato nella stessa transazione senza rete sotto lock. Ripresa con
nuova sessione autorizzata e budget residuo, spesa/risultati preservati. Codici non
recuperabili o limite tentativi negano la ripresa.

## Dati e retention

DB: riferimenti consentiti e dati indipendenti dal sito con provenienza/hash.
Nomi, URL e metriche Google non diventano attributi lead o prompt AI. Contatti sotto
classificazione, retention, policy e suppression anche alla consegna. Un export
diventato superato durante rendering viene rifiutato con `job_result_changed`.

Archivi in `/var/lib/leadhunter/server-diagnostics`, cartelle workspace/UUID nel
volume privato condiviso API/worker/recupero. Retention1–168h/default24, mai oltre
licenza d'origine. Pulizia periodica solo di archivi riconosciuti scaduti, anche per
workspace inattivi. Proteggere volume e backup: i contenuti redatti possono includere
prompt proprietari; non inserirli nell'immagine cliente o negli export ordinari.

Grant e deadline ricontrollati fra blocchi64KB. Accesso perso dopo l'inizio del
download interrompe i byte ancora da consegnare; quelli ricevuti e le copie esportate
restano sotto il controllo del destinatario.

## Verifiche

API/DB e SDK reale con HTTP controllato; licenze Ed25519; PostgreSQL17 con ruoli
app/worker, concorrenza e HTTP→worker→Excel riaperto; roundtrip migrazioni; Chromium
host e immagine non root. Review fresca e gate GitHub exact HEAD prima di integrare.
