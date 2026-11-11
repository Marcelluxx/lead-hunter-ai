# Controlli operativi del crawler

I controlli si applicano automaticamente a CLI, diagnostica e worker. Non è
necessaria una nuova opzione per usarli. La qualità dell'evidenza resta il
criterio che determina se avviare l'audit.

| Caso | Comportamento |
|---|---|
| robots.txt 404 o 410 | Scansione consentita, come richiesto. |
| robots.txt con regole | Si usano le regole di LeadHunter, o quelle generali se manca il gruppo dedicato. Vince la regola più specifica, Allow a parità. |
| Errore transitorio durante robots.txt | Un solo nuovo tentativo entro la scadenza del controllo; poi il sito viene fermato senza avviare l'audit. |
| 401, 403 o 429 per robots.txt | Nessuna scansione. Per 429 si conserva la sospensione, considerando Retry-After se valido. |
| Una pagina interna è vietata o fallisce | La pagina non conta come evidenza. L'audit può usare le altre pagine se sono sufficienti. |
| 429 durante una navigazione | Nessun nuovo tentativo. Il dominio viene sospeso per almeno 60 secondi, fino a 24 ore con un Retry-After valido. |
| Errori transitori ripetuti | Un solo retry browser di norma; il secondo errore consecutivo sospende il dominio. La diagnostica non ripete la navigazione, per evitare artefatti duplicati. |

Valori predefiniti: 24 tentativi per hostname in 60 secondi per istanza del
crawler, 160 richieste browser intercettate per tentativo, 25 secondi per
tentativo e 90 secondi di attesa asincrona per scansione. Il budget conta
anche i tentativi falliti. Il browser non scarica audio/video intercettati;
il rendering e l'estrazione di contenuti restano attivi. Le verifiche di
licenza, annullamento e budget del job restano applicate.

La policy robots si conserva in memoria per origine (15 minuti per assenza
o regole, intervalli brevi per errori). Le richieste robots usano un IP
validato, TLS con il nome originale, nessun proxy d'ambiente e controllo
esplicito delle destinazioni dei redirect. Non inviano cookie browser.

Lo stato operativo non è condiviso tra worker o istanze. Il worker mantiene
la semantica esistente di job non auditabile; i codici specifici sono
disponibili nel risultato di crawl. Il limite richieste riguarda quelle
visibili ai callback del browser e non è un tetto di memoria o byte di
Chromium. I callback non equivalgono a un firewall: alcuni redirect e
connessioni del browser richiedono un isolamento egress separato. L'esito
finale viene comunque verificato prima di usare le evidenze.

Riferimenti: [RFC 9309](https://www.rfc-editor.org/rfc/rfc9309.html) e
[limiti di intercettazione Playwright](https://playwright.dev/python/docs/api/class-page#page-route).
