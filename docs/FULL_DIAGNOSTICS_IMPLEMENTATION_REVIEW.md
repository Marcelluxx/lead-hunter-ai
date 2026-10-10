# Diagnostica completa — implementazione e verifica

10 ottobre 2026, branch `codex/licensed-full-diagnostics`, base `c231e8c`.

## Risultato

`diagnostics.full` recupera il tester riservato su sito indipendente in CLI e GUI.
La sessione comune raccoglie HTML/CSS caricati, testo/evidenza, prompt e risposte
AI in uno ZIP privato, separato dai report clienti. Il catalogo abilita il modulo;
licenze firmate, scadenza/revoca e autorizzazione server corrente restano obbligatorie.

## Verifiche

- Test CLI/GUI con catalogo reale, licenze Ed25519 reali e ZIP riaperti.
- Revoca dentro serializzazione ZIP, fsync e HTML: consegna negata, file precedente preservato.
- Ruoli server e MFA correnti, retention, limiti individuali/aggregati e capture concorrenti.
- Chromium/Crawl4AI reale: HTML e CSS catturati, email e credenziali oscurate nell'archivio.
- Prova browser RED→GREEN: la libreria scriveva URL sensibili in crawler.log;
  logger privato disabilita anche gli errori che forzano la verbosità, senza alterare il percorso base.
- Suite completa in corso; review fresca e CI/Security esatto HEAD da registrare.

## Decisioni delegate

1. Specifica/piano autorevisionati sotto la delega autonoma esplicita; eventuali
   preferenze diverse del proprietario richiederanno revisioni delle scelte ordinarie.
2. Limite diagnostico CLI allineato alla GUI a 1–20 pagine per contenere lavoro browser;
   un uso oltre 20 pagine richiederà un limite configurabile successivo.

## Limiti dichiarati

CSS cross-origin non leggibile non viene aggirato. File già consegnati non possono
essere ritirati: retention nel manifest e pulizia dei soli UUID riconosciuti nella
directory dedicata al successivo avvio autorizzato con output standard. Output
personalizzato e download GUI richiedono cancellazione da parte di chi li riceve.
Nessuna nuova dipendenza o migrazione. Il worker commerciale è il sottoprogetto successivo.
