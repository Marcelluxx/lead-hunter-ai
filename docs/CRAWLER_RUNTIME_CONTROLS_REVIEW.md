# Controlli operativi del crawler — review

11 novembre 2026. [PR #18](https://github.com/Marcelluxx/lead-hunter-ai/pull/18),
base develop `b2100c7`. Il proprietario ha confermato che l'assenza di
robots.txt non deve fermare il crawl. Il resto dei limiti è una scelta
operativa del primo blocco, senza cambi a UI, hosting o condizioni commerciali.

## Verifica

- RED iniziale: nove test, dieci fallimenti per contratti non ancora disponibili.
- Prima suite completa: due sottocasi Chromium di una fixture DOM non avevano
  un trasporto robots fittizio; aggiunta la stessa fixture 404 usata dagli altri
  browser test. Suite successiva: 469/469, zero skip, 131.653s, PostgreSQL 17,
  Chromium e build Docker. Nessuna nuova versione nel lock.
- Review indipendente read-only di `b2100c7..29e2e5d`: 15/15 test mirati;
  nessun Critical, due Important. Un solo passaggio correttivo.
- Il circuito attribuiva 429 e transitori al primo host e non a chi
  rispondeva. L'evidenza di una navigazione tardiva poteva riusare stato
  HTTP e MIME del documento precedente. Due regressioni fallivano prima
  del fix. Ora si attribuisce al dominio rispondente, si verifica il legame
  URL/risposta e si rifiuta una nuova risposta di navigazione dopo quella
  legata al caricamento. Un test aggiuntivo copre il reload sullo stesso URL
  con 429, e quello cross-host verifica anche Retry-After e scadenza.
- Dopo il fix: suite mirata crawler/Chromium/DOM 35/35; 15/15 operativi dopo
  il test aggiuntivo. Le verifiche finali sono riportate nella PR.
- La scansione supply chain [42984866376](https://github.com/Marcelluxx/lead-hunter-ai/actions/runs/42984866376)
  ha rilevato 69 vulnerabilità in sei pacchetti: aiohttp, brotli, certifi,
  filelock, gitpython e pillow. Le sei versioni sono identiche a develop.
  La PR non allenta il gate e resta in bozza. Non sono state incluse
  migrazioni delle versioni maggiori delle dipendenze.

## Decisioni e limiti

| Decisione | Conseguenza |
|---|---|
| Design ordinario delegato; 404/410 consentiti, errore transitorio ritentato una volta | Un sito che resta irraggiungibile non genera evidenza |
| Controlli applicativi, nessuna quota distribuita o firewall browser | Un solo processo non impone limiti globali; alcuni redirect/connessioni richiedono isolamento |
| Contratto job non auditabile invariato | Il worker conserva la gestione esistente, senza una nuova semantica di skip/checkpoint |
| HTTPX già nel lock dichiarato come dipendenza diretta | Nessun aggiornamento implicito di pacchetti |
| TLS e nome originale verificati nella configurazione e con trasporto fittizio | Nessuna garanzia aggiuntiva di compatibilità con provider remoti non provati |
| Budget di richieste/attese asincrone | Nessun tetto rigido di CPU, memoria, byte o durata di arresto del processo |
| Suite PostgreSQL/Docker/Chromium eseguita dall'autore | La review indipendente non ha ripetuto tutta la matrice |
| Matching REP verificato per gruppi, wildcard, specificità e codifica | Nessun claim di conformità RFC esaustiva |
| Documento tardivo senza binding affidabile scartato | Alcuni siti con navigazione client possono risultare non auditabili |
| Aggiornamento supply chain separato dal primo blocco funzionale | Il merge resta bloccato dal gate attuale |

I sei ambiti lasciati fuori giudizio dal reviewer sono coperti nella tabella:
egress/quote, TLS remoto, limiti di processo, suite completa, RFC esaustiva
e semantica dei job. Minore rinviato: test di scadenza/eviction della cache,
capacità dello stato per dominio e scadenza globale dopo homepage valida.
