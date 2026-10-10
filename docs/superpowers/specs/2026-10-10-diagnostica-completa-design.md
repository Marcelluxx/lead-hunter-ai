# Diagnostica completa riservata

## Mandato e scelte

Il proprietario vuole recuperare le funzioni diagnostiche personali anche nel
prodotto vendibile, per sé e destinatari autorizzati con accesso a scadenza,
locale e server. Il 10 ottobre ha delegato esplicitamente l'esecuzione autonoma
dell'intera roadmap, comprese le scelte ordinarie e l'integrazione dei recuperi.
Metodo native mantenuto. Questa specifica è autorevisionata sotto tale delega;
non si richiede un nuovo ciclo di approvazioni per ogni documento.

Scegliamo una sessione diagnostica comune e un ZIP per esecuzione: si riusa dal
tester GUI/CLI e dai futuri handler server. Rispetto ai vecchi file condivisi
evita mescolanza fra esecuzioni e consegna involontaria; un backend di telemetria
esterno introdurrebbe infrastruttura non necessaria al recupero.

## Contratto

- `diagnostics.full` diventa available solo dopo flussi reali verificati.
- EXECUTE richiede START_JOB, VIEW richiede VIEW_AUDIT_LOG; MFA server obbligatoria
  per entrambi, senza cambiare il formato firmato o il modello locale.
- Il tester base conserva il DTO pubblico; la diagnostica completa è opt-in.
- CLI `--full-diagnostics` richiede `--test-url`; `--diagnostic-output` ha senso
  soltanto insieme al flag. Senza licenza: exit 2 prima di crawler/prompt/API/file.
- GUI: pannello dedicato URL/max pagine/retention, disabilitato senza accesso;
  download ZIP inline dopo verifica corrente, senza bytes in sessione/media.
- Nessun campo diagnostico aggiunto a lead, prompt cliente, database o coda.
  Sessioni operative non serializzabili e separate dal DTO pubblico dell'audit.

## Contenuto, limiti e autorizzazione

Si catturano soltanto materiali del sito indipendente e del relativo audit:
HTML delle pagine già caricate, CSS accessibile dal browser già caricato (inline
e regole stylesheet accessibili, senza nuovi fetch diagnostici), testo elaborato,
evidenza/stato, richieste LLM (prompt completi), risposte LLM e DTO finale.
Le limitazioni CSS cross-origin sono esplicite nel record e non aggirate.
Mai risposte Google Places, rating/recensioni, cookie/header di autenticazione,
chiavi, licenze, contesti di autorizzazione o tracebacks. Il collector rifiuta
strutture provider; URL/prompt/HTML/output vengono oscurati per credenziali
note e pattern segreti/PII. I file sono JSON/text nel ZIP, mai HTML eseguito in UI.

Limiti: 1 MiB per record, 8 MiB totali UTF-8, 256 record; rifiuto esplicito al
superamento, nessun archivio parziale spacciato per completo. Lock per capture
concorrenti dell'auditor. Retention intera 1–168 ore, default 24; il manifest
riporta created/expires, con scadenza non oltre la licenza. Sessione chiusa dopo
il risultato, niente contaminazione di run successivi.

Verifiche fresche all'avvio, a ogni capture, prima di tentativi LLM e richieste
browser, ritorno, serializzazione, sostituzione atomica e consegna inline.
Revoca/scadenza propagano senza fallback diagnostico o archivi parziali. Errore
ordinario produce un codice sicuro. La base resta accessibile con un nuovo avvio.

Salvataggio CLI atomico; nome generato UUID quando non specificato, directory
privata dedicata, file temporaneo pulito e destinazione preesistente preservata
al rifiuto. File nuovi con permessi owner-only dove supportati. Pulizia automatica
solo dentro la directory diagnostica dedicata, senza seguire symlink o eliminare
altri file dell'utente. File già consegnati non si possono ritirare retroattivamente.

## Verifica

Licenze vere: assente/non concessa/alterata/scaduta/revocata; server con MFA/ruolo
e identità corrente. Redazione di segreti anche nei prompt e nell'HTML, rifiuto
provider payload, limiti e concorrenza; revoca durante ZIP/fsync/HTML impedisce
consegna e conserva vecchio file. Base invariata e nessun extra campo pubblico.
CLI e GUI con crawler/LLM fixture, archivio reale riaperto, crawler Chromium
reale opt-in. Suite, lock, Gitleaks, review indipendente e CI/Security.

## Stato

Design autorevisionato per scope, interfacce, limiti, base compatibile e minacce.
Esecuzione autorizzata dalla delega autonoma del proprietario del 10 ottobre 2026.
Pipeline server e qualità audit sono sottoprogetti successivi; questo recupero
non richiede nuove risorse esterne o un nuovo formato di licenza.
