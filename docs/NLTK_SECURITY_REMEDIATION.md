# Rimozione della dipendenza NLTK inutilizzata — 9 ottobre 2026

## Obiettivo e causa

Rimuovere il blocco Security senza perdere le funzioni dell'app e senza introdurre
eccezioni allo scanner. Baseline: `62b6580`, PR export #8. Intervento separato nel
branch `codex/remove-unused-nltk`, basato su quella PR.

La scansione runtime della baseline riproduce un solo risultato:
`nltk==3.10.3`, `PYSEC-2026-3740` / `CVE-2026-81726` /
`GHSA-8mgp-746c-j5xp`, senza versione corretta indicata dal servizio di audit.
L'[advisory del manutentore](https://github.com/nltk/nltk/security/advisories/GHSA-8mgp-746c-j5xp)
indica accesso a file fuori dalle directory consentite tramite API di modelli.
La [release PyPI](https://pypi.org/project/nltk/3.10.3/) resta 3.10.3.

NLTK non viene importato dal codice dell'app: è dichiarato obbligatorio da
Crawl4AI 0.9.2 e anche dai metadati della release 0.9.4. Nel codice installato
è usato da chunking NLP, utility dei modelli e strumenti legacy; il percorso
applicativo usa `PruningContentFilter`, `DefaultMarkdownGenerator`, browser e
link extraction, che non lo richiedono. Il filtro pruning usa BeautifulSoup;
gli altri filtri non sono selezionati dalla pipeline.

## Modifica

- Crawl4AI fissato a 0.9.2, la versione già presente nel lockfile.
- Esclusione NLTK attraverso `tool.uv.exclude-dependencies`, un
  [meccanismo documentato di risoluzione](https://docs.astral.sh/uv/concepts/resolution/#dependency-exclusions).
- Lock rigenerato senza NLTK e joblib, dipendenza rimasta esclusiva di NLTK.
- Nessun cambio a crawler, URL policy, licenze delle funzioni o report.
- Nessuna vulnerabilità ignorata; il gate Security e la policy delle licenze
  delle dipendenze rimangono invariati.

Il prodotto supporta il percorso Crawl4AI utilizzato dall'app. Le utility
NLTK di Crawl4AI (chunking NLP, download punkt, persistenza dei modelli, legacy
llmtxt) non fanno parte di questo percorso e non sono disponibili nel runtime.
Un futuro utilizzo richiede una dipendenza corretta e una nuova valutazione.
I metadati upstream continuano a dichiarare NLTK: un controllo generico delle
dipendenze pip segnala tale requisito mancante; la risoluzione ufficiale del
prodotto è quella uv, con esclusione esplicita e test di compatibilità.
Non installare Crawl4AI separatamente con pip, che reintrodurrebbe NLTK.

## Verifica

Il nuovo test di assenza della distribuzione ha fallito prima della modifica
e passa dopo la sincronizzazione dell'ambiente. La prova di compatibilità usa
il vero Crawl4AI per configurazione, pruning e generazione Markdown, verificando
testo e contatto della fixture.

La prova browser usa il vero `HybridCrawler`, Chromium e Crawl4AI. Solo il
trasporto è sostituito da risposte HTML controllate su URL con IP pubblico;
la route passa attraverso la URL policy reale prima di fornire la fixture.
Verifica homepage e pagina contatti, evidenze HTTP valide, testo utilizzabile
e contatto con provenienza. Non chiama Google o LLM e non visita siti esterni.
È abilitata nel job CI Python 3.11, dopo l'installazione Chromium.

La scansione runtime ripetuta dopo la modifica, con hash obbligatori e modalità
strict, termina con `No known vulnerabilities found`. Lo SBOM non contiene NLTK.
La policy licenze verifica 137 pacchetti senza errori; gli obblighi di revisione
MPL/LGPL già previsti rimangono, senza nuove eccezioni.

Suite locale completa con browser abilitato: **197 test, 186 superati, 11 saltati**
(10 integrazioni PostgreSQL senza URL locali e 1 prova Docker opt-in).
Passano lock check, compilazione e controllo whitespace. `uv pip check` segnala
il solo requisito upstream NLTK volutamente escluso, come descritto sopra.
I risultati GitHub della PR sul commit finale completano la verifica per Linux,
Python 3.10–3.13, PostgreSQL e container prima di integrare il branch.

La rimozione di questo blocco non completa le altre milestone commerciali:
worker, interfaccia clienti, firma/distribuzione e requisiti operativi restano aperti.
