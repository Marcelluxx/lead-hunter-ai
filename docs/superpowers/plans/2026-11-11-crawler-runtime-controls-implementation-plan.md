# Crawler Runtime Controls Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Integrare policy robots e limiti operativi nelle scansioni reali.
**Architecture:** Policy robots indipendente, stato runtime per istanza e integrazione nel crawler esistente.
**Tech Stack:** Python 3.10–3.13, HTTPX già nel lock, Crawl4AI e Chromium.
**Spec:** docs/superpowers/specs/2026-11-11-crawler-runtime-controls-design.md

## Global Constraints

Nessun nuovo pacchetto o servizio. 404/410 consentono il crawl. Stessi contratti
di audit e autorizzazione. Nessun provider reale nei test.

## Review Focus

- Negazione robots non avvia il browser né consegna evidenza.
- Assenza robots non altera il normale audit e il record del dominio resta circoscritto.
- 429 o fallimenti ripetuti fermano il dominio, gli altri continuano.
- Fallimenti e retry consumano budget; la cancellazione non viene assorbita.
- Timeout o blocchi interni mantengono il risultato parziale solo se auditabile.

### Task 1: Policy robots e limiti runtime

- [x] RED tests/test_crawler_operations.py: policy, budget, retry e integrazione non disponibili.
- [x] Implementare RobotsPolicy.require(decision, guard) in src/robots_policy.py e
  CrawlLimits/CrawlRuntime in src/crawl_runtime.py; collegarli a HybridCrawler.
- [x] GREEN con fixture in memoria; controllare lock, regressioni, Chromium reale.
- [x] Aggiornare roadmap/manuale, completare review del branch e verificare prima del push.
