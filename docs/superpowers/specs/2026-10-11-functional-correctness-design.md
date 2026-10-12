# Correttezza funzionale — design

11 ottobre 2026. Parte della modernizzazione autonoma già autorizzata. Scopo:
rendere affidabili le funzioni esistenti senza perdere i moduli riservati con
accessi a scadenza. Metodo native, specifica/piano autorevisionati; il mandato
autonomo sostituisce le conferme procedurali sulle scelte ordinarie.

Il cambiamento riguarda più consumatori del contratto crawl/report, quindi
segue il percorso architetturale Superpowers. Gli input validi devono funzionare,
i filtri devono avere motivazioni osservabili e il report non deve inventare
tecnologie, città o necessità di JavaScript. Nessuna release pubblica implicita.

## Approccio

Correggere i filtri esistenti e introdurre un detector di tecnologie puro,
condiviso da report locale/server. Il crawler produce strategie distinte di
Markdown e metadati osservabili. Le boundary CLI/UI rifiutano input errati
prima di effetti. Alternative: togliere le opzioni (perderebbe funzioni richieste)
o riscrivere la pipeline (duplicherebbe i gate già verificati).

## Filtri

Età: WHOIS e testo visibile del sito sono fonti tri-state. Una fonte che prova
una data abbastanza vecchia permette; recente senza fonte vecchia contraria
esclude; nessun dato passa secondo la policy storica, dichiarato unknown.
WHOIS descrive la registrazione del dominio, non prova l'età aziendale.
Confronto annuale come il contratto esistente; min_years1–100, timeout WHOIS10s.
Date multiple: prima valida cronologicamente; date future o malformate ignorate.
Script/style/commenti non sono copywriting; riferimenti multipli sono valutati
insieme, evitando che il primo anno casuale domini quelli successivi.

Social: hostname normalizzato IDNA/lowercase/punto finale; solo host identico
o sottodominio. Parole nel path/query e suffissi omonimi non sono domini social.
extract_domain rimuove www, userinfo e porta dal solo hostname, gestisce host
senza schema e non restituisce query/path come dominio.

Franchise: match di marchi noti per token completi; termini brevi dentro altri
nomi non bastano. Ripetizioni di nomi nel dataset da sole non provano una catena,
quindi la vecchia inferenza substring viene rimossa. Entity resolution con sedi
e domini resta lavoro di qualità futuro; omonimi completi restano un limite noto.

E-commerce: filtro locale riattivato prima di comprare l'audit, dopo corpus
positivo/negativo. Richiede un'azione DOM carrello/checkout e un segnale commerciale
indipendente (Product/Offer, prezzo strutturato o asset commerce specifico).
Parole generiche, provider pagamenti, commenti, blog o semplice link social non
bastano. I job server schema1 non ricevono nuovi filtri impliciti; parametri
cliente configurabili appartengono alla successiva superficie clienti.

## Crawl e tecnologia

high_fidelity usa raw Markdown semantico; optimized usa fit con filtro pruning
threshold0.45/min_word_threshold15, fallback raw quando fit<100 caratteri.
Un helper seleziona contenuto per homepage e interne; entrambi mantengono
controlli min120/pagina e min200 totali, contatti ed evidenza. Opzione invalida
rifiutata prima del browser. Non si promette un risparmio token fisso senza misura.

CrawlResult: browser_used bool inizialeFalse, render_strategy not_started/browser,
js_required nullable e is_dynamic nullable per compatibilità. Senza confronto
statico/render non possiamo affermare JS necessario: entrambi restano unknown.
browser_used diventaTrue quando inizia arun, anche se fetch fallisce. Log mostra
il trasporto osservato, non un'affermazione dinamico/statico inventata.

Detector versione1 su generator meta e path asset/script strutturati:
WordPress, Drupal, Joomla, Shopify, Wix, Squarespace, Next.js, Nuxt.
TechnologyMatch(name, signals, confidence, rules_version): signals sono ID regola
pubblici, massimo32 segnali per sito, confidence0–1. Nessuna versione software
dedotta, richieste secondarie, raw HTML o URL query nei segnali. Generatore o asset
caratteristico sono evidenza osservata, non prova assoluta dell'intero backend.
Testo blog con nomi di tecnologie e commenti non basta.

framework nel lead verificato viene dal detector, mai dal campo libero LLM;
senza evidenza diventa Non rilevato. La risposta LLM continua a essere validata,
ma non prevale sui dati osservati. Il contratto puro WebsiteAuditResult non cambia.
Lead aggiunge technology_signals tuple di stringhe e technology_rules_version;
persistenza esistente per attributi/evidenze, allowlist API e workbook aggiornati.

L'hash DOM homepage viene raccolto separatamente dall'hash Markdown; provenance
di framework/segnali punta a URL ufficiale/timestamp/hash DOM. Audit e contatti
mantengono le evidenze del testo pulito. Si conservano solo fatti pubblici e hash,
nessun HTML privato. Report locale e server mostrano le stesse tecnologie.

## Normalizzazione e input

Categorie legacy tollerano null/tipi misti, trim/casefold/dedupe; massimo2 tag
come prima, fallback keyword sempre identificato come input utente. La helper
località tollera dati incompleti e conserva Unicode/nomi maiuscoli; assenza
indirizzo produce N/A, mai una città dedotta dalla keyword. Non recupera colonne
Google vietate negli export. Nuovi campi commerciali attendono fonti indipendenti.

CLI: coordinate0 valide; float finiti negli intervalli lat[-90,90], lng[-180,180],
keyword richieste. Max_pages1–20 e min_age1–100. Input invalido esce2 prima di
settings/orchestratore/file. URL --test-url verificato con validate_syntax prima
di settings/licenza/auditor/crawler/cleanup; GUI diagnostica prima di costruzioni
e cleanup. Rete sempre controllata separatamente da SafeUrlPolicy nel crawler.

Minor pipeline portato in questa fase: resume con budget insufficiente risponde
409/budget_exceeded come admission, mantenendo rollback e nessun messaggio coda.

## Vincoli globali

- Nessun contenuto Google in storage, prompt AI o Excel oltre riferimenti consentiti.
- Licenze/MFA/grants correnti ed isolamento workspace rimangono gate condivisi.
- Nessuna richiesta provider reale o credenziale operatore necessaria ai test.
- Nessun nuovo parametro implicito ai job schema1; filtro locale e-commerce attivo.
- Modalità high_fidelity/optimized; max_pages1–20; URL policy rete resta obbligatoria.

## Verifica

TDD sui casi reali, corpus filtri con veri DOM, generatore Crawl4AI e Chromium
effettivi su trasporto sintetico; provenance/persistenza/Excel riaperto e API.
Suite completa PostgreSQL app/worker, browser e distribuzione senza skip,
review fresca unica sul sottoprogetto e pass correzioni Critical/Important.
Commit/push a milestone, CI/Security esattoHEAD, integrazione develop quando verdi.

Self-review: confini dati/licenze preservati, source/hash separati, unknown esplicito;
qualità audit/gold set, robots/budget domini, UI/SSO/billing restano fasi successive.
