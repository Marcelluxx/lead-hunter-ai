# Security policy

## Segreti e configurazione

- Le credenziali devono arrivare esclusivamente da variabili d'ambiente o da un secret manager.
- File `.env*`, configurazioni locali degli agenti e chiavi private non devono essere versionati.
- Non inserire valori reali in prompt, log, screenshot, issue o pull request.
- Prima di ogni commit installare gli hook con:

  ```powershell
  python -m pip install pre-commit
  pre-commit install
  pre-commit run --all-files
  ```

La CI esegue Gitleaks sull'intera cronologia raggiungibile. Le regole predefinite
sono estese con un detector dedicato alle chiavi OpenRouter.

## Gestione di una possibile esposizione

1. Revocare la credenziale dal provider e generarne una nuova.
2. Verificare utilizzo, costi e log di accesso anomali.
3. Rimuovere il valore da file locali, backup e configurazioni di tooling.
4. Se il segreto è entrato in Git, considerarlo compromesso anche dopo la rimozione
   e pianificare la riscrittura della cronologia con i proprietari del repository.
5. Documentare incidente, impatto, finestra temporale e misure correttive senza
   copiare il segreto nel report.

## Segnalazioni

Non aprire issue pubbliche contenenti dettagli sfruttabili o credenziali. Usare
la funzione privata di security advisory del repository GitHub.
