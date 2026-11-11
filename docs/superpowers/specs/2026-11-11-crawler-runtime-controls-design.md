# Controlli operativi del crawler

Obiettivo: rendere prevedibili scansioni locali e job esistenti. Conferma del
proprietario: se robots.txt manca (404 o 410), il crawl continua. Se il server
non permette di leggere il file, tentare una volta in più solo per errore
transitorio; se persiste, non avviare la scansione. La scelta dei limiti è
dell'implementatore sotto la delega ordinaria già ricevuta.

Approcci: attivare l'opzione Crawl4AI sarebbe più breve ma il suo trasporto
non usa la policy URL del prodotto. Riscrivere il trasporto di Chromium
richiederebbe un nuovo confine di rete. Adottiamo un fetch robots dedicato e
controlli attorno al crawler attuale, mantenendo rendering, prove e output.

- Robots per origine, TTL 15 minuti per regole/assenza, 30 secondi per errore,
  massimo 512 origini; richiesta senza cookie, proxy d'ambiente o redirect
  automatici; ogni salto autorizzato, connessione sull'IP verificato, Host
  e verifica TLS per il nome originale, limite 512 KiB e 4 secondi per hop.
  Limite complessivo per lookup 10 secondi. Gruppi LeadHunter e wildcard,
  match più specifico, Allow a parità, caratteri percent-encoded, * e $.
- Per istanza: 24 tentativi di navigazione per hostname in finestra di 60s,
  massimo 512 stati; browser 160 richieste intercettate per tentativo, media
  esclusi, 25s per tentativo, 90s per crawl. Limiti regolabili nel costruttore
  Python; nessun nuovo input pubblico. Budget incluso nei retry. Blocco
  temporaneo dopo due errori transitori consecutivi; 429 apre il circuito e
  non viene ritentato. Cooldown base 60s. Un solo retry su errore transitorio;
  nessun retry browser diagnostico (evita duplicare artefatti).
- Controlli di esecuzione esistenti prima/dopo richieste, nessuna promozione
  a evidenza di risultati negati. Un errore di pagina interna conserva le
  evidenze già valide; se mancanti, non avvia l'audit. Niente rete reale nei
  test; fixture HTTP e Chromium. Nessun nuovo pacchetto nel lock.
- Robots viene verificato prima delle navigazioni richieste dal tool e al
  confine del risultato prima di usare una pagina finale. I callback browser
  sono un controllo applicativo, non un firewall: non viene garantita
  intercettazione di tutti i redirect, worker o connessioni del browser.
  Isolamento egress, quote distribuite, proxy, deploy e UI fuori da questo PR.
