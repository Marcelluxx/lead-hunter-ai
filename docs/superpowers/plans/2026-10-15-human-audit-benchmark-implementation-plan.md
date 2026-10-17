# Human Audit Benchmark Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Raccolta locale di giudizi umani separati e confronto ripetibile con AI/DOM.
**Architecture:** Package offline con contratti rigorosi, metriche pure e CLI.
Dataset e schede separati per revisione cieca; nessun accesso runtime/DB/provider.
**Tech Stack:** Python 3.10–3.13, standard library, validatori DOM/score esistenti.
**Spec:** docs/superpowers/specs/2026-10-15-human-audit-benchmark-design.md

## Global Constraints

- Schema1; massimo500 campioni/revisori, JSON32MiB UTF8, nessuna nuova dipendenza.
- human-site-1: qualità1–10, priorità0–3 separate, pending/mancanti non zero.
- dom-markup-1 invariata, calibration_status uncalibrated, nessun umano inventato.
- Niente provider/DB o chiavi, dati locali in .benchmark-data esclusa Git/Docker.
- Output nuovo esclusivo; nessun overwrite; errori safe exit2.
- Delega autonoma spec/piano, esecuzione native, una review indipendente finale.

## Review Focus

- Dati storici con DOM valido ma indice assente: unavailable, non scoring retroattivo (Task1).
- Scheda riusata dopo modifica a una predizione/metadato: binding rifiutato, non confronto plausibile su altro campione (Task1).
- Ripetizione di uno stesso revisore e numero diverso di revisori per sito: nessuna duplicazione e peso per sito (Task2).
- Ranghi pari, segnali costanti, zero e gruppi vuoti: n esplicito e null dove non definito (Task2).
- Risposta server reale con contatti/segreti, errore JSON e file esistente: proiezione minima, errore senza leak e nessuna sovrascrittura (Task3).

### Task 1: Dataset e revisione cieca

**Files:** Create src/benchmark/__init__.py, contracts.py, dataset.py, reviews.py;
tests/benchmark_helpers.py, tests/test_benchmark_contracts.py.
**Interfaces:** `BenchmarkError(code)`, `canonical(value)->str`,
`build_dataset(records:list,prediction_version:str)->dict`, `validate_dataset(dict)->dict`,
`build_review_packet(dataset:dict,reviewer_id:str)->dict`,
`validate_review_packet(packet:dict,dataset:dict)->dict`.

- [x] Scrivere test per canonicalizzazione ordine/digest, private projection, score
  zero e storico, bool/NaN/corruzione DOM/score, 501 campioni, duplicati URL+tempo.
- [x] RED: unittest tests.test_benchmark_contracts -v, contratto assente.
- [x] Implementare contratti con errori benchmark_invalid/dataset_invalid/review_invalid;
  riusare public_evidence_url e validate_score_report. Packet senza predizioni;
  pending/assessable/unassessable, date e schema rigorosi come specifica.
- [x] GREEN: stessi test, anche modifica metadata/hash, timestamp e reviewer invalidi.
- [x] Suite progetto, lock/compile/diff/Gitleaks e commit: feat: add bound human benchmark datasets and blind reviews.

### Task 2: Metriche di confronto

**Files:** Create src/benchmark/evaluation.py; tests/test_benchmark_evaluation.py.
**Interfaces:** Consumes Task1 validate_dataset/validate_review_packet;
produces `evaluate(dataset:dict,packets:list[dict])->dict`.

- [x] Test per tre campioni, qualità AI vs umano con differenze 1,-1,0:
  MAE0.666667, RMSE0.816497, bias0; priorità distinta; missing esclusi.
- [x] RED: unittest tests.test_benchmark_evaluation -v, evaluate assente.
- [x] Implementare ranks/ties/Spearman, medie per sito, accordo pairwise,
  n metriche/null, gruppi DOM e output senza URL/reviewer ID, max500 packet.
- [x] GREEN: stessi test, inclusi ranghi inversi/pari/costanti, duplicati revisori,
  ordine input e numero revisori diverso, nessuna calibrazione o scale confuse.
- [x] Suite progetto e controlli; commit feat: compare human judgments with uncalibrated audit signals.

### Task 3: CLI e adapter server offline

**Files:** Create src/cli/benchmark.py; src/benchmark/io.py;
tests/test_benchmark_cli.py; docs/HUMAN_AUDIT_BENCHMARK.md.
Modify .gitignore/.dockerignore; docs/MODERNIZZAZIONE_AUTONOMA.md.
**Interfaces:** Consumes Task1/2; `dataset_from_job(result:dict,*,prediction_version:str,captured_at:str)->dict`;
`load_json(path)->dict`, `write_json_new(path,value)->None`, CLI main(argv=None)->int.

- [x] Test subprocess prepare/review-packet/evaluate su tmp, senza env/credenziali;
  artifact riaperti con metriche attese; adapter server con dati privati non copiati.
- [x] RED: unittest tests.test_benchmark_cli -v, CLI assente.
- [x] Implementare input bounded/no duplicate keys/NaN, esclusione overwrite,
  output0600/fsync/cleanup file proprio fallito, messaggi sicuri. Adapter legge
  output results completed e proietta solo i campi necessari, nessun contatto.
- [x] GREEN: end-to-end, JSON annidato/oversize/duplicate/errori safe, input=output,
  storico, from-job con data obbligatoria, file precedente preservato.
- [x] Manuale con rubriche, protocollo cieco, limiti e comandi; dati sintetici solo
  nei test. Roadmap aggiorna merge16 e distingue strumenti pronti da benchmark reale.
- [x] Suite completa PostgreSQL/Chromium/distribuzione, lock/compile/diff/Gitleaks;
  commit feat: add offline benchmark collection and evaluation CLI.

## Chiusura

Una review fresca whole-branch con focus e ruling; Critical/Important un fix pass
RED/GREEN, Minor registrati. Rapporto review tracciato, push e PR draft→ready
su develop solo dopo gate esatto HEAD. Merge su richiesta separata. Nessuna
pulizia scratch/worktree condiviso dopo il precedente rifiuto automatico.
