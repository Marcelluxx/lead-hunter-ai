# Filtri rating/recensioni — evidenze di implementazione

10 ottobre 2026. Branch `codex/licensed-rating-filters`, base funzionale
`6491f66da0f7fd956b88626a02dfca609ca7437e`. Specifica e piano operativo approvati
dal proprietario; metodo native, una review indipendente finale. Nessun merge/release.

## Risultato

Filtri opt-in in entrambe le modalità, criteri 3.9/100 applicati solo se attivi,
confronto rating stretto e conteggio da 1 al massimo incluso. Dati di selezione
effimeri nell'adapter; nessuna estensione dei DTO o persistenza delle metriche.
Verifica a ogni tentativo, retry, ritorno e consegna; origine operativa conservata
anche per riferimenti e report derivati dal sito. Export protetto atomico CLI e
download inline GUI. Il modulo viene abilitato nel catalogo dopo i flussi verificati.

## Prove locali

- Task 1: RED nuove interfacce assenti; GREEN 5 test criteri/guard con licenze reali.
- Task 2: RED servizio assente; GREEN 10 test provider/contratti, incluse concorrenza,
  mask base invariato, duplica qualificata, scadenza/revoca e contesto server corrente.
- Task 3: RED origine/export mancanti; GREEN 33 test pipeline, policy/export, injection.
- Task 4: RED flag/preflight mancanti; GREEN 21 test CLI, references e injection.
- Task 5: RED toggle/origine mancanti; GREEN 28 test GUI/licenze/consegna, inclusa
  regressione console Windows. Nessuna decisione di licensing mockata.
- Browser Chromium reale: entrambe le modalità; download effettivo di riferimenti
  (2 colonne, Place ID `NoSiteQualified`) e report sito (9 colonne, nome ricostruito
  `Official Clinic`), salvati e riaperti con openpyxl; scadenza simulata e nuova
  ricerca base esplicita. Trasporti Google/LLM e sito simulati, chiavi effimere;
  nessuna chiamata Places/LLM a pagamento. Server temporaneo arrestato.
- Task 6 RED: catalogo produttivo ancora planned rifiuta i flussi CLI/GUI con licenza
  firmata valida. GREEN suite completa dopo attivazione: 234 test, 222 passati,
  12 saltati (10 PostgreSQL, un container, un crawler browser opt-in).

Lock `uv 0.11.15 --check`, compilazione e `git diff --check`: PASS. Crawler Chromium
opt-in eseguito separatamente: 3/3 PASS, incluso crawler reale senza NLTK.
PostgreSQL/container richiedono prove CI quando non disponibili localmente.
Il verde di una base precedente non certifica questo HEAD. Gitleaks viene
eseguito sullo staging di ogni commit; gate remoti ancora da ottenere.

## Decisioni dell'implementer

1. Una selezione filtrata scaduta rimane selezionata e disabilitata; il pulsante
   esplicito «Usa la ricerca base» consente un nuovo avvio base senza fallback
   automatico. Costo se la scelta fosse errata: un controllo UI aggiuntivo.
2. La prova browser Windows ha riprodotto una `UnicodeEncodeError` nei messaggi
   console legacy senza sito, prima della consegna. Applicato il normalizzatore
   console già usato con sito, con test RED→GREEN su output cp1252. Costo: alcuni
   simboli console vengono sostituiti quando la codifica non li supporta.
3. Commit locale dell'attivazione prima della review, per fornire al revisore uno
   snapshot esatto dell'intero ramo. Push/PR restano successivi alla review.
   Costo: un commit aggiuntivo per documentare i gate conclusivi.

## Review indipendente e gate remoti

In attesa della review finale e della PR draft. L'integrazione delle PR licensing,
reference export e rimozione NLTK rimane separata. Worker commerciale e diagnostica
completa restano nelle milestone successive; questo documento non è una release.
