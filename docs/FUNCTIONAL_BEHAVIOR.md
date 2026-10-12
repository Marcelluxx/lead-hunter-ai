# Comportamento delle funzioni verificate

12 ottobre 2026. Fase correttezza funzionale della roadmap autonoma.

## Qualificazione locale

Anzianità minima: confronto annuale tra data di registrazione dominio e riferimenti
visibili del sito. Un riferimento sufficientemente vecchio permette l'attività;
recente senza una fonte vecchia contraria esclude; nessuna data è unknown e passa.
La data del dominio non certifica la fondazione dell'azienda. Date future/invalide
ignorate, prima data WHOIS valida cronologicamente, timeout10s.

Social: hostname esatto o sottodominio normalizzato, mai parole nel path o substring
di siti omonimi. Franchise: marchio noto completo per token; la ripetizione di nomi
comuni non è prova di una catena. Omonimi completi richiedono futura entity resolution.

E-commerce locale: serve azione DOM carrello/checkout più un segnale commerciale
indipendente, come schema Product/Offer o asset commerce. Blog, parole generiche e
provider di pagamento da soli non bastano. Esclusione prima dell'audit a pagamento.
I job server schema1 mantengono i filtri dichiarati, senza nuove esclusioni implicite.

## Scansione e tecnologie

high_fidelity conserva Markdown completo semantico; optimized usa contenuto pruning
threshold0.45/min15 parole, con fallback completo se il fit è più corto di100 caratteri.
Homepage e pagine interne usano la stessa scelta. Non è promesso risparmio fisso.
Browser usato è un fatto osservato; necessità di JavaScript resta unknown senza
confronto statico/render. Input bloccato prima della navigazione non dichiara browser usato.

CMS/framework: segnali meta generator e asset strutturati per WordPress, Drupal,
Joomla, Shopify, Wix, Squarespace, Next.js e Nuxt. Nessuna versione software inferita
e nessuna tecnologia dal solo suggerimento AI. Non rilevato è esplicito.
Segnali pubblici e versione regole1 negli Excel/API; hash DOM e provenienza separati
dalle evidenze Markdown di audit/contatti. Nessun HTML o prompt nei segnali.
Confidence indica forza euristica della regola, non probabilità calibrata o prova
del backend; calibrazione/gold set appartengono alla successiva fase qualità audit.

## Input e normalizzazione

CLI accetta coordinate0, richiede float finiti nei range geografici, keyword non
vuote, max_pages1–20 e min_age1–100. Errori input escono2 prima di configurazione,
prompt, crawler o file. --examples esce0 senza caricare configurazioni.
URL test CLI e diagnostica GUI vengono normalizzati sintatticamente prima dell'avvio;
DNS, indirizzi e redirect restano sotto controlli separati durante la scansione.

Helper legacy categorie: null/tipi misti ignorati, trim/casefold/dedupe, massimo2 tag.
Località strutturata conserva maiuscole/Unicode; dati mancanti restano N/A e non
diventano la keyword. La helper non riapre l'export di colonne Google vietate.

Budget insufficiente per admission/ripresa:409/budget_exceeded, stato e prenotazioni
restano sotto rollback, nessun nuovo messaggio alla coda. La privacy dei contatti
rimane limitata ai lead del job, con403 sicuro e stop dello streaming dopo revoca.
