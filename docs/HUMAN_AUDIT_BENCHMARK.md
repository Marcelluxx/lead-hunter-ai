# Raccolta e confronto delle valutazioni umane

Questo strumento offline prepara campioni e schede di revisione, quindi misura
la relazione tra giudizi umani, voto AI e indice markup. Non raccoglie siti,
non interroga provider/DB e non modifica la rubrica dom-markup-1. I dati sono
giudizi provvisori: non un gold set adjudicato né una calibrazione completata.

## Protocollo di revisione human-site-1

Definire prima il campione: categorie di attività, lingua, tipo/dimensione sito,
modalità di raccolta e criteri di inclusione. Evitare di selezionare soltanto
siti già riusciti nell'audit. Registrare gli esclusi/mancanti, congelare versione
codice/modello/configurazione e non usare i risultati per cambiare retroattivamente
le valutazioni. Un campione 200–500 siti è un obiettivo progressivo, non un minimo
statistico garantito. Un eventuale fit di pesi richiederà un set di validazione
separato: questa versione non esegue fitting né split automatici.

Ogni revisore riceve soltanto la propria scheda e questa rubrica, senza dataset,
voti automatici o discussioni dei voti altrui. Almeno due revisori indipendenti
sono consigliati per misurare disaccordo; il formato accetta anche uno solo ma
in quel caso l'accordo non è misurabile. Gli ID revisore sono pseudonimi, non
account autenticati: l'operatore è responsabile della provenienza reale.

Compilare **due giudizi indipendenti**:

| Dimensione | Scala e ancore |
|---|---|
| quality_score | 1–2 gravemente insufficiente; 3–4 debole; 5–6 adeguato con limiti; 7–8 buono; 9–10 molto buono |
| intervention_priority | 0 nessun intervento evidente; 1 miglioramento non urgente; 2 intervento utile e prioritario; 3 problema che blocca un compito importante |

Per qualità considerare chiarezza, facilità dei compiti, fruibilità visiva/mobile
e fiducia. Non è un audit certificato di accessibilità/sicurezza. La priorità
non misura budget, intenzione d'acquisto o ricavi dell'impresa e non va calcolata
automaticamente dalla qualità. Usare lo stesso protocollo di visita per tutti.

Un sito live può cambiare rispetto al crawl: se il confronto non è ragionevole,
marcare unassessable/changed_site e preparare un nuovo campione. Il tool non
conserva screenshot o originali HTML e non garantisce equivalenza temporale.

## Preparare i dati

Usare una cartella `.benchmark-data/` locale esclusa da Git e Docker. I file
possono contenere URL ed evidenze: proteggerli e applicare la retention/policy
della fonte. Nessuna licenza o policy viene aggirata: usare soltanto copie già
legittimamente ottenute. Questa CLI non legge credenziali e non esegue job.

Il formato snapshot contiene esattamente schema_version e samples:

```json
{
  "schema_version": 1,
  "samples": [
    {
      "source_url": "https://example.com/",
      "captured_at": "2026-10-15T12:00:00+00:00",
      "website_score": 7,
      "dom_report": {},
      "score_report": {}
    }
  ]
}
```

Le parentesi vuote dei due report sono **segnaposto illustrativi, non input
valido**: sostituirli con i report reali validati dell'app. captured_at è
l'istante UTC dell'esportazione, non precedente ai timestamp DOM. website_score
ammette null per dato assente e interi1–10. Sono ammessi i report empty storici
reali: nessuna rubrica viene applicata retroattivamente.

```powershell
uv run --frozen python -m src.cli.benchmark prepare --input .benchmark-data/snapshots.json --prediction-version release-f477815-model-config-A --out .benchmark-data/dataset.json
```

In alternativa salvare una risposta JSON autorizzata e completed del server
`GET /workspaces/{workspace_id}/jobs/{job_id}/results`, poi:

```powershell
uv run --frozen python -m src.cli.benchmark prepare --from-job --input .benchmark-data/job-results.json --captured-at 2026-10-15T12:00:00+00:00 --prediction-version release-f477815-model-config-A --out .benchmark-data/dataset.json
```

L'adapter conserva URL pubblico, data dichiarata e due predizioni con i report
DOM/score. Nome, contatti, messaggi commerciali, provenance e dati Google non
vengono copiati nel dataset o nel suo hash. L'originale job-results rimane sotto
il controllo dell'operatore e può contenere dati soggetti a policy più restrittive.
prediction_version deve identificare davvero codice/modello/configurazione usati;
è una dichiarazione operatore, non una verifica automatica del modello.

Sono supportati1–500 campioni. Duplicati dello stesso URL pubblico e istante sono
rifiutati. Il dataset è ordinato e legato tramite SHA256 al contenuto completo.
Un digest dimostra coerenza interna, non autenticità contro un operatore malevolo.

## Preparare e compilare le schede

```powershell
uv run --frozen python -m src.cli.benchmark review-packet --dataset .benchmark-data/dataset.json --reviewer revisore_a --out .benchmark-data/revisore_a.json
uv run --frozen python -m src.cli.benchmark review-packet --dataset .benchmark-data/dataset.json --reviewer revisore_b --out .benchmark-data/revisore_b.json
```

La scheda non contiene voto AI, indice DOM o diagnosi. Le righe partono pending
con campi decisionali null. Il revisore modifica soltanto:

- status=reviewed, reviewed_at UTC, quality_score1–10, intervention_priority0–3,
  reason=null per un giudizio completo;
- status=unassessable, reviewed_at UTC, punteggi null e reason uno di unavailable,
  changed_site, insufficient_context, other quando non valutabile;
- pending e tutti i campi decisionali null se non ancora revisionata.

Esempio **sintetico** di soli campi da compilare, non un giudizio umano reale:

```json
{"status":"reviewed","reviewed_at":"2026-10-15T13:00:00+00:00","quality_score":6,"intervention_priority":2,"reason":null}
```

Conservare dataset_sha256, versione, ID campione, URL, data e ordine delle righe.
Ogni packet contiene tutte le righe una volta. Nessun campo libero per note,
contatti o nomi è ammesso. Nuove revisioni del dataset richiedono nuove schede.

## Valutare

```powershell
uv run --frozen python -m src.cli.benchmark evaluate --dataset .benchmark-data/dataset.json --reviews .benchmark-data/revisore_a.json .benchmark-data/revisore_b.json --out .benchmark-data/comparison.json
```

Sono accettati fino a500 revisori distinti, entro32MiB complessivi di schede
serializzate e32MiB totali letti dai file (spazi inclusi); ripetere lo stesso ID, anche con un
file diverso, è errore. I giudizi sono mediati per sito e dimensione: ogni sito
pesa una volta, non di più se ha più revisori. Pending/unassessable restano nei
conteggi e non diventano zero. Il report valutativo non contiene URL o ID revisore.

- AI vs qualità: n, MAE, RMSE, bias (AI meno umano) nelle unità1–10, Spearman.
- DOM vs qualità e AI/DOM vs priorità: soltanto n e Spearman; nessuna MAE tra
  scale diverse, nessun verso della relazione imposto.
- Spearman usa ranghi medi per i pari. Meno di due coppie o rango costante
  produce null, non zero. Le metriche sono arrotondate a6 decimali.
- Accordo umano: numero coppie nello stesso sito e distanza assoluta media,
  separata per qualità/priorità. Non è una reliability calibrata.
- Conteggi dei mancanti e risultati separati per DOM complete/partial/unavailable.
  Complete descrive le pagine eleggibili raccolte, non l'intero sito.

Una buona correlazione in pochi campioni non certifica capacità predittiva.
calibration_status rimane uncalibrated, reference_status provisional_human_ratings.
Non si producono intervalli, significatività o modifiche automatiche ai pesi.

## Errori e protezione dei file

Ogni JSON è UTF8 senza BOM, massimo32MiB; chiavi duplicate, NaN, campi extra e
versioni ignote sono rifiutati. Output su file nuovo esclusivo, senza --force:
un file esistente o input=output non viene sovrascritto. I nuovi file hanno
permessi0600 dove supportati; su Windows applicare anche gli ACL della cartella.
Errore exit2 con codice sicuro, senza payload/path; successo exit0. Non ci sono
chiamate provider, caricamento dei prompt o configurazione delle chiavi.

## Cosa manca per la milestone completa

Raccolta reale, protocollo rappresentativo, verifica dei revisori, analisi del
disaccordo/adjudication, dataset congelato e validazione separata. Solo dopo
queste attività si potrà proporre una nuova rubrica calibrata. I test sintetici
di questo modulo verificano calcoli e contratti, non la qualità del prodotto.
