# Correttezza funzionale — review e verifica

12 ottobre 2026. PR #13 verso develop, base `9941a22`, implementazione
`6dede7a`. Revisore indipendente gpt-6-astra/high, contesto pulito, intero diff,
specifica, piano e ruling; checkout read-only. Sedici test mirati PASS e
riproduzioni dei casi non coperti. Nessun provider reale o rilascio in produzione.

## Risultati e unico pass di correzione

Nessun Critical. Tre Important confermati e una segnalazione rivalutata Important:

1. URL malformati negli attributi DOM interrompevano il filtro e facevano perdere
   lead validi. Ignoriamo il singolo URL malformato e continuiamo gli altri segnali.
   Regressioni filtro e orchestratore locale RED→GREEN.
2. Il preflight accettava hostname con caratteri invalidi e trasformava porta0
   nella porta predefinita. Validazione label DNS dopo IDNA, IPv6 preservato,
   distinzione porta assente/zero. Regressioni policy, CLI e GUI con licenza reale
   RED→GREEN: nessun crawler, auditor, sessione di esecuzione o cleanup su URL
   invalido; la GUI conserva soltanto il probe di disponibilità iniziale.
3. Link canonical/alternate/preconnect/dns-prefetch e radici CDN potevano dichiarare
   un CMS. Ora solo link risorsa stylesheet/preload/modulepreload e percorsi CDN
   specifici. Negativi e positivi RED→GREEN, senza nuove richieste di rete.
4. Fit100–119 invalidava l'evidenza di pagina; fit120–199 poteva invalidare un audit
   homepage singola anche con raw sufficiente. Soglia fit120 per pagine interne,
   fit200 per homepage e fallback raw quando sufficiente. Se raw è insufficiente
   conserviamo fit disponibile; rimangono i gate di evidenza. Test con il wrapper
   Crawl4AI reale RED→GREEN. Specifica e manuale aggiornati.

Primo RED: 34 test, 25 failure e3 errori sui casi riprodotti (2 browser non abilitati);
RED delivery firmata: 2 test, 4 failure. Dopo correzioni: 43/43 PASS incluso Chromium.
Suite completa finale360/360 PASS senza skip,127.808s: PostgreSQL17 con ruoli
app/worker, Chromium e build distribuzione abilitati. Lock, compile e diff PASS.
Commit e gate GitHub sono verificati dopo il push sull'esatto HEAD.
Nessuna seconda review; correzioni verificate con regressioni e suite completa.

## Rulings I made — in ordine, con costo se errati

1. Specifica/piano preparati e controllati inline sotto delega autonoma già
   autorizzata. Costo: revisione ordinaria se la scelta di progetto va corretta.
2. Intestazioni native normalizzate a Task N per il parser. Costo: bookkeeping.
3. Ogni codice modificato ha la suite completa; task-done ripete i moduli del brief
   sullo stesso codice già verificato. Costo: niente seconda suite identica prima
   del ledger; la suite finale rimane obbligatoria.
4. Ipotesi temporanea raw_html per la selezione token SUPERATA: la vera causa era
   StringCompatibleMarkdown, sottoclasse str che eludeva la selezione raw/fit.
   Ripristinato cleaned DOM normale. Costo dell'ipotesi errata: boilerplate maggiore,
   evitato prima del commit; nessun override raw DOM distribuito.
5. Nuovi campi DTO aggiunti dopo quelli esistenti per compatibilità posizionale,
   verificata da regressione. Costo: future estensioni devono mantenere l'ordine.
6. Exporter locale esteso perché la specifica richiede parità con il server.
   Costo: consumatori che impongono il numero fisso di colonne devono adattarsi;
   posizioni delle colonne precedenti preservate.
7. show_examples stampa senza terminare internamente; main restituisce0 prima
   della configurazione. Costo: chi chiama direttamente il helper continua.
8. Probe licenza GUI prima dell'input conservato; preflight prima dell'esecuzione.
   Costo: setup dello stato licenza iniziale possibile senza URL, nessun audit.
9. Ledger task completato prima della review/merge secondo il flusso native.
   Costo: commit correttivo possibile; merge ancora subordinato a review e CI.
10. Revisore non giudica nuovamente gli interni predecessori di licenze, diagnostica,
    autenticazione e worker; restano review/gate già registrati e regressioni
    dell'integrazione corrente. Costo: eventuali difetti non raggiunti da queste
    integrazioni richiedono un intervento dedicato.
11. Omonimi esatti di marchi restano limite documentato del filtro a token, senza
    risoluzione entità semantica. Costo: un omonimo può essere escluso; futura
    risoluzione entità necessaria se il caso si presenta.
12. WHOIS indica età del dominio, non prova l'età dell'impresa; confidence CMS è
    forza euristica, non probabilità calibrata. Manteniamo comunicazione esplicita.
    Costo: eventuale interpretazione commerciale più forte richiede calibrazione.
13. Soglia fit100 scelta dal piano non protegge l'evidenza promessa: rivalutata
    Important e corretta al punto4. Costo: fallback raw può usare più token;
    quote/budget e gate di evidenza restano applicati.
14. Copertura indirizzi completa per paese, altri CMS, robots, billing e provider
    reale restano roadmap; non estendiamo la correzione oltre la milestone.
    Costo: queste capacità non sono ancora una promessa della versione corrente.
15. Interni contatti/provenienza non modificati restano contratti predecessori,
    verificando qui separazione hash DOM/Markdown e export delle nuove evidenze.
    Costo: una revisione completa aggiuntiva dei predecessori resta lavoro distinto.
16. Su richiesta di concludere rapidamente chiudiamo questa milestone prima di
    avviare qualità audit. Costo: la milestone successiva resta da implementare.

## Deferred minors

- Fallback indirizzi legacy non strutturati può scambiare regione/postcode per
  città in indirizzi internazionali. Nessun consumatore di produzione attuale
  del helper; percorsi strutturati preservano Unicode e maiuscole. Da affrontare
  quando quel fallback entra in un flusso utilizzato.

Restano i limiti documentati nel manuale e le milestone successive della roadmap.
