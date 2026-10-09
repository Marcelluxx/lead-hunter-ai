# Licenze modulari a scadenza: implementazione e revisione

Piano approvato ed eseguito il 9 ottobre 2026 sul branch
`codex/expiring-feature-licenses`, [PR draft #7 verso develop](https://github.com/Marcelluxx/lead-hunter-ai/pull/7).
Tutti i nove task del piano sono implementati e pubblicati con commit separati.
Il core supporta installazioni locali e concessioni per utente/workspace sul server.
I tre moduli `export.no_website`, `discovery.rating_filters` e `diagnostics.full`
restano pianificati: il loro recupero è il prossimo sottoprogetto.
Il worker commerciale conserva `pipeline_not_configured`.

## Risultato e prove

- Contratti, catalogo, verifica rigorosa Ed25519 e scadenza senza periodo di grazia.
- Identità locale stabile, rinnovi atomici, revoche persistenti e orologio monotono.
- PostgreSQL: migrazione 0004, RLS, concorrenza dei rinnovi, worker in sola lettura.
- Controlli comuni di licenza, ruolo, MFA e disponibilità; API, CLI e pannello locale.
- Emittente separato con chiave privata cifrata; materiale privato escluso dal cliente.
- Suite finale Windows/Python 3.12: **158 test passati, zero skip**, con PostgreSQL 17
  reale e verifica Docker della distribuzione attivati. Migrazioni reali
  upgrade/downgrade/upgrade già verificate durante il task 4.
- `compileall`, `uv lock --check`, `git diff --check` e pre-commit/Gitleaks passati.
- Gitleaks sull'intera storia: 61 commit e circa 7,73 MB esaminati, nessuna fuga
  di segreti rilevata prima del commit finale di sola documentazione.
- Immagine aggiornata: esclusioni del materiale privato verificate, API avviata
  con utente non privilegiato (UID 10001), `/health/live` restituisce `ok`.
- CI GitHub sul commit applicativo `e8532d9`: Python 3.10/3.11/3.12/3.13,
  PostgreSQL 17, container/migrazioni/API e Gitleaks **passati**.
  Il gate supply-chain fallisce su **una vulnerabilità in un pacchetto**, NLTK,
  confermato dai log del run Security `37906858879`.
- Audit commerciale delle licenze di 140 dipendenze runtime conforme alla policy
  esistente; restano gli obblighi di revisione legale già previsti dalla roadmap.

## Revisione indipendente e correzioni

Un revisore indipendente gpt-6-astra ha esaminato il range `19c2730..e092ca7`,
specifica, piano e decisioni. Nessun problema Critical. Un solo passaggio di
correzione, verificato con test prima falliti e poi superati, senza seconda review:

| Problema | Correzione e regressione |
|---|---|
| Stato locale salvato prima di un audit fallito | Journal atomico in state.json; audit.jsonl è una proiezione ritentabile. Test `test_audit_projection_failure_keeps_grant_and_authoritative_event_together`, anche con proiezione corrotta. |
| Clock indipendente ma dipendente dal pool occupato dalle richieste | Pool dedicato di due connessioni senza overflow, transazioni brevi e chiusura nel ciclo di vita API. Test `test_clock_commits_with_request_pool_saturated`. |
| PEM pubblico concatenato a materiale privato accettato | Singolo blocco PEM pubblico ammesso. Test `test_signature_and_trust_are_strict`. |
| JSON profondamente annidato causa RecursionError | Errore normalizzato a `license_invalid`, senza token esposto. Test `test_deeply_nested_payload_is_a_redacted_invalid_license`. |

Gli ultimi due rilievi erano etichettati Minor dal revisore: sono stati rivalutati
Important perché compromettono rispettivamente il confine di distribuzione delle
chiavi e la gestione degli import non validi. **Minor rinviati: nessuno.**
Le correzioni e gli aggiornamenti dipendenze sono nei commit `bded302` e `e8532d9`.

## Blocco della release

Il primo audit CI ha segnalato 71 voci di vulnerabilità in cinque pacchetti.
Aggiornati GitPython, multidict, NLTK, PyJWT e urllib3 entro i vincoli compatibili,
con nuova suite completa e nuova immagine. Rimane **CVE-2026-81726 /
GHSA-8mgp-746c-j5xp** in NLTK 3.10.3, senza versione corretta pubblicata:
[advisory ufficiale NLTK](https://github.com/nltk/nltk/security/advisories/GHSA-8mgp-746c-j5xp).
NLTK è transitivo tramite Crawl4AI; il codice applicativo non richiama le API di
salvataggio/caricamento dei modelli descritte nell'advisory. Non è stata introdotta
alcuna eccezione all'audit. Il gate Security resta bloccante; questa PR non dichiara
il prodotto pronto alla vendita e rimane draft.

## Decisioni assunte, in ordine

1. Aggiornare il test esaustivo dello schema, omesso dal piano, per le due nuove
   tabelle intenzionali. Costo se errato: correzione dell'aspettativa di schema.
2. Sostituire le asserzioni sul testo delle esclusioni con build/export Docker
   isolati reali. Costo se errato: perdita di un segnale preliminare testuale;
   rimangono i gate effettivi di distribuzione.
3. Consentire nell'immagine solo i due PEM pubblici delle dipendenze fissate,
   certifi/cacert.pem e litellm/proxy/auth/public_key.pem, rifiutando contenuto
   privato anche lì. Costo se errato: falsa accettazione in quei due percorsi.
4. Aggiornare cinque dipendenze vulnerabili fuori dal piano funzionale, in risposta
   al CI. Costo se errato: regressioni di compatibilità; suite e immagine riverificate.
5. Rimandare i tre recuperi e il dispatcher produttivo secondo lo scope approvato.
   Costo se errato: quelle azioni restano inutilizzabili fino alla prossima milestone.
6. Richiedere contesti server ricostruiti prima di ogni futura azione/consegna.
   Costo se errato: un'integrazione futura può mantenere ruolo/membership obsoleti.
7. Lasciare la manomissione da amministratore OS/DB fuori dal confine offline,
   esplicitandone il limite. Costo se errato: bypass o ripristino di snapshot.
8. Limitare la garanzia filesystem a fsync del file e sostituzione atomica, con
   backup completo. Costo se errato: perdita dell'ultima modifica dopo un blackout.
9. Interpretare `granted` come diritto firmato, con ruolo/MFA e disponibilità
   controllati separatamente. Costo se errato: funzione autorizzata ma ancora
   indisponibile o negata dal ruolo, da comunicare chiaramente nell'interfaccia.
10. Validare gli aggiornamenti dipendenze separatamente dal range del revisore,
    mantenendo bloccante NLTK. Costo se errato: release ferma e necessità di nuove
    verifiche di compatibilità/sicurezza quando sarà disponibile una correzione.

Il manuale operativo è [FEATURE_LICENSES.md](FEATURE_LICENSES.md).
Worktree e branch sono conservati per il seguito della PR; i soli artefatti
temporanei di questo piano vengono rimossi dopo la verifica finale.
