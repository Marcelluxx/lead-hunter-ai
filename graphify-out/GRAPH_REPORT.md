# Graph Report - E:\PROGETTI\PROGRAMMAZIONE\AGENTE LEAD  (2026-07-30)

## Corpus Check
- Corpus is ~28,758 words - fits in a single context window. You may not need a graph.

## Summary
- 304 nodes · 473 edges · 19 communities (14 shown, 5 thin omitted)
- Extraction: 94% EXTRACTED · 5% INFERRED · 1% AMBIGUOUS · INFERRED: 26 edges (avg confidence: 0.8)
- Token cost: 36,400 input · 17,700 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Module Imports & Dependencies|Module Imports & Dependencies]]
- [[_COMMUNITY_AI Audit Orchestration|AI Audit Orchestration]]
- [[_COMMUNITY_Lead Filters & Excel Export|Lead Filters & Excel Export]]
- [[_COMMUNITY_Diagnostic Evidence Artifacts|Diagnostic Evidence Artifacts]]
- [[_COMMUNITY_UI & Campaign Pipeline|UI & Campaign Pipeline]]
- [[_COMMUNITY_GitHub Delta & Critical Risks|GitHub Delta & Critical Risks]]
- [[_COMMUNITY_Crawl4AI Web Extraction|Crawl4AI Web Extraction]]
- [[_COMMUNITY_Architecture & Repository Context|Architecture & Repository Context]]
- [[_COMMUNITY_403 Audit Case Study|403 Audit Case Study]]
- [[_COMMUNITY_Legacy V2 Lead Scouter|Legacy V2 Lead Scouter]]
- [[_COMMUNITY_Commercialization Roadmap|Commercialization Roadmap]]
- [[_COMMUNITY_Legacy V1 Lead Engine|Legacy V1 Lead Engine]]
- [[_COMMUNITY_Audit JSON Schema|Audit JSON Schema]]
- [[_COMMUNITY_Audit & Package Overview|Audit & Package Overview]]
- [[_COMMUNITY_Excel Export Documentation|Excel Export Documentation]]
- [[_COMMUNITY_Column Width Utilities|Column Width Utilities]]
- [[_COMMUNITY_Proprietary Prompt Module|Proprietary Prompt Module]]
- [[_COMMUNITY_Test Audit Artifact|Test Audit Artifact]]

## God Nodes (most connected - your core abstractions)
1. `src/tester.py` - 14 edges
2. `LeadAuditor` - 13 edges
3. `src/gui.py` - 13 edges
4. `LeadHunterOrchestrator` - 12 edges
5. `HybridCrawler` - 12 edges
6. `End-to-end audit test report` - 12 edges
7. `src/auditor.py` - 11 edges
8. `update_elapsed()` - 10 edges
9. `AI website diagnosis` - 10 edges
10. `LLM-cleaned homepage findings` - 10 edges

## Surprising Connections (you probably didn't know these)
- `Product Weaknesses and State-of-the-art Roadmap Query` --references--> `HybridCrawler`  [EXTRACTED]
  graphify-out/memory/query_20260729_222724_quali_sono_i_punti_deboli_di_lead_hunter_v3_e_come.md → src/crawler.py
- `Lead Hunter v3 Package` --conceptually_related_to--> `Audit tecnico, vendibilità e roadmap stato dell'arte`  [INFERRED]
  src/__init__.py → docs/AUDIT_PRODOTTO_E_ROADMAP_STATO_DELL_ARTE.md
- `LeadHunterOrchestrator` --uses--> `DataExporter`  [INFERRED]
  main.py → src/exporter.py
- `LeadHunterOrchestrator` --uses--> `HybridCrawler`  [INFERRED]
  main.py → src/crawler.py
- `LeadHunterOrchestrator` --uses--> `CrawlResult`  [INFERRED]
  main.py → src/crawler.py

## Hyperedges (group relationships)
- **Crawler-to-LLM Audit Artifact Flow** — page_1_homepage_403_forbidden, page_1_homepage_processed_content, page_1_homepage_cleaned_summary, ai_prompt_sent_website_audit_prompt, ai_raw_response_website_audit_result, test_report_two_phase_audit_test [EXTRACTED 1.00]
- **Website Qualification and Audit Flow** — src_scraper_leadscraper_scrape_entire_grid, agente_lead_main_leadhunterorchestrator_run_with_website, src_crawler_hybridcrawler_crawl, src_auditor_leadauditor_audit_website, src_exporter_export_to_excel [EXTRACTED 1.00]
- **Lead Hunter Implementation Evolution** — legacy_lead_hunter_leadhunterengine_fetch_leads, legacy_lead_hunter_v2_leadhunterscouter_run_campaign, agente_lead_main_leadhunterorchestrator_run_no_website [INFERRED 0.85]

## Communities (19 total, 5 thin omitted)

### Community 0 - "Module Imports & Dependencies"
Cohesion: 0.08
Nodes (52): main, src.auditor, src.config, src.crawler, src.exporter, src.filters, src.prompts, src.scraper (+44 more)

### Community 1 - "AI Audit Orchestration"
Cohesion: 0.06
Nodes (26): LeadHunterOrchestrator, Lead Hunter V3 — Main Orchestrator & CLI Supporta due modalità operative:   -, Core Engine disaccoppiato dalla UI. Può essere invocato da CLI, GUI o API estern, Product Weaknesses and State-of-the-art Roadmap Query, LeadAuditor, Lead Hunter V3 — AI Auditor Module Due modalità:   1. "No Website" — analisi l, Pulisce e ricostruisce una pagina web utilizzando il modello economico/gratuito, Audit completo del sito web tramite LLM.         Output: website_score, diagnos (+18 more)

### Community 2 - "Lead Filters & Excel Export"
Cohesion: 0.09
Nodes (30): _calculate_column_widths(), DataExporter, export_to_excel(), _format_no_website_rows(), _format_website_rows(), _get_no_website_columns(), _get_website_columns(), Lead Hunter V3 — Excel Exporter (openpyxl) Export duale:   - Modalità "no_webs (+22 more)

### Community 3 - "Diagnostic Evidence Artifacts"
Cohesion: 0.13
Nodes (30): Saved AI audit JSON, AI-generated cold outreach message, AI website diagnosis, Prompt sent to the LLM, Raw AI audit response, AI-generated lead site brief, Design, UX, and copywriting not evaluable, Google rating 4.5 out of 5 (+22 more)

### Community 4 - "UI & Campaign Pipeline"
Cohesion: 0.13
Nodes (23): Pipeline completa per lead con sito web (Streaming Parallelo).         on_phase, Dispatcher che smista alla pipeline corretta in base al mode., Pipeline originale per lead senza sito web., format_elapsed(), get_approximate_location(), on_audit_progress(), on_crawl_progress(), on_kw_end() (+15 more)

### Community 5 - "GitHub Delta & Critical Risks"
Cohesion: 0.09
Nodes (27): AsyncWebCrawler riutilizzato, Audit prodotto senza evidenza valida, Riuso della sessione browser, Incoerenze nella normalizzazione di categorie e località, Commit 62e5d9a: framework/CMS nell'output, Commit 78ffe58: indirizzi, categorie e WHOIS, Commit e7afdbd: migrazione a Crawl4AI, Crawl4AI adapter (+19 more)

### Community 6 - "Crawl4AI Web Extraction"
Cohesion: 0.10
Nodes (17): Crawl4AI Semantic Crawling, Python Runtime Dependency Set, CrawlResult, HybridCrawler, Lead Hunter V3 — Crawl4AI Web Crawler Replaces custom HybridCrawler with Crawl4, Pulisce gli spazi consecutivi e i ritorni a capo eccessivi per ottimizzare i tok, Estrae email dall'HTML, dal Markdown e dai tag mailto., Chiude la sessione attiva del browser Crawl4AI. (+9 more)

### Community 7 - "Architecture & Repository Context"
Cohesion: 0.15
Nodes (15): Git History Metrics Analysis, Portfolio Project Profile Schema, README-First Analysis Strategy, Repository Analysis Workflow, Technology Stack Detection, Shallow Repository Structure Scan, External Service and Pipeline Configuration, Fail-Fast Centralized API Configuration (+7 more)

### Community 8 - "403 Audit Case Study"
Cohesion: 0.42
Nodes (10): Italian Website Compliance Audit Criteria, Testing and Diagnostics Sector, Santamartapizzeria Website Audit Prompt, Santamartapizzeria AI Website Audit Result, Santamartapizzeria 403 Forbidden Homepage, LLM-Cleaned Homepage Summary, Noindex Error Page Directive, Processed Homepage Content (+2 more)

### Community 9 - "Legacy V2 Lead Scouter"
Cohesion: 0.27
Nodes (4): LeadHunterScouter, Cerca lead in un raggio specifico usando le coordinate GPS., Genera una matrice di coordinate attorno a un punto centrale., Esegue l'intera campagna di ricerca ed elimina i duplicati.

### Community 10 - "Commercialization Roadmap"
Cohesion: 0.36
Nodes (8): Policy-aware, evidenze deterministiche, sintesi AI e human approval, Managed service con design partner e revisione umana, Non pronto per SaaS pubblico, Fase 1: motore affidabile, Fasi 2-3: prodotto differenziato e SaaS vendibile, Streamlit come console interna, API, job queue, PostgreSQL multi-tenant ed evidence store, Buon prototipo tecnico

### Community 11 - "Legacy V1 Lead Engine"
Cohesion: 0.29
Nodes (3): LeadHunterEngine, Cerca attività e filtra quelle che non hanno un sito web., Esporta i dati in un file Excel.

### Community 12 - "Audit JSON Schema"
Cohesion: 0.40
Nodes (4): cold_message, diagnosis, site_brief, website_score

## Ambiguous Edges - Review These
- `Testing and Diagnostics Sector` → `Santamartapizzeria`  [AMBIGUOUS]
  test_output/ai_prompt_sent.txt · relation: conceptually_related_to
- `python-whois` → `src/filters.py`  [AMBIGUOUS]
  src/filters.py · relation: imports
- `whois` → `src/filters.py`  [AMBIGUOUS]
  src/filters.py · relation: imports

## Knowledge Gaps
- **28 isolated node(s):** `website_score`, `diagnosis`, `site_brief`, `cold_message`, `Lead Hunter V3 Project Profile` (+23 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **5 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `Testing and Diagnostics Sector` and `Santamartapizzeria`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **What is the exact relationship between `python-whois` and `src/filters.py`?**
  _Edge tagged AMBIGUOUS (relation: imports) - confidence is low._
- **What is the exact relationship between `whois` and `src/filters.py`?**
  _Edge tagged AMBIGUOUS (relation: imports) - confidence is low._
- **Why does `LeadHunterOrchestrator` connect `AI Audit Orchestration` to `Lead Filters & Excel Export`, `UI & Campaign Pipeline`, `Crawl4AI Web Extraction`?**
  _High betweenness centrality (0.073) - this node is a cross-community bridge._
- **Why does `LeadAuditor` connect `AI Audit Orchestration` to `Crawl4AI Web Extraction`?**
  _High betweenness centrality (0.048) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `LeadAuditor` (e.g. with `LeadHunterOrchestrator` and `run_url_test()`) actually correct?**
  _`LeadAuditor` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 5 inferred relationships involving `LeadHunterOrchestrator` (e.g. with `LeadScraper` and `LeadAuditor`) actually correct?**
  _`LeadHunterOrchestrator` has 5 INFERRED edges - model-reasoned connections that need verification._