# Graph Report - .  (2026-07-30)

## Corpus Check
- Corpus is ~21,422 words - fits in a single context window. You may not need a graph.

## Summary
- 353 nodes · 456 edges · 50 communities (20 shown, 30 thin omitted)
- Extraction: 81% EXTRACTED · 19% INFERRED · 0% AMBIGUOUS · INFERRED: 86 edges (avg confidence: 0.8)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Excel Export|Excel Export]]
- [[_COMMUNITY_Orchestration and Audit|Orchestration and Audit]]
- [[_COMMUNITY_Secure Crawler|Secure Crawler]]
- [[_COMMUNITY_Crawl Evidence Contract|Crawl Evidence Contract]]
- [[_COMMUNITY_URL Policy Security|URL Policy Security]]
- [[_COMMUNITY_Production SaaS Architecture|Production SaaS Architecture]]
- [[_COMMUNITY_Pipeline and UI Helpers|Pipeline and UI Helpers]]
- [[_COMMUNITY_Python CI Test Matrix|Python CI Test Matrix]]
- [[_COMMUNITY_LLM Trust Boundary|LLM Trust Boundary]]
- [[_COMMUNITY_Security Backlog|Security Backlog]]
- [[_COMMUNITY_Repository Analysis Context|Repository Analysis Context]]
- [[_COMMUNITY_Audit Output Contract|Audit Output Contract]]
- [[_COMMUNITY_Legacy V2 Scout|Legacy V2 Scout]]
- [[_COMMUNITY_Legacy V1 Engine|Legacy V1 Engine]]
- [[_COMMUNITY_Product Positioning|Product Positioning]]
- [[_COMMUNITY_Diagnostic Testing|Diagnostic Testing]]
- [[_COMMUNITY_Data Policy Compliance|Data Policy Compliance]]
- [[_COMMUNITY_CI Secret Scanning|CI Secret Scanning]]
- [[_COMMUNITY_Audit Contract Tests|Audit Contract Tests]]
- [[_COMMUNITY_Prompt and Data Exposure|Prompt and Data Exposure]]
- [[_COMMUNITY_Dependency Reproducibility|Dependency Reproducibility]]
- [[_COMMUNITY_Precommit Secret Scanning|Precommit Secret Scanning]]
- [[_COMMUNITY_Test Package|Test Package]]
- [[_COMMUNITY_Export Documentation|Export Documentation]]
- [[_COMMUNITY_Column Sizing|Column Sizing]]
- [[_COMMUNITY_Competitor Selection|Competitor Selection]]
- [[_COMMUNITY_Runtime Dependencies|Runtime Dependencies]]
- [[_COMMUNITY_OpenRouter Key Exposure|OpenRouter Key Exposure]]
- [[_COMMUNITY_Domain Age Bug|Domain Age Bug]]
- [[_COMMUNITY_No Website Audit Bug|No Website Audit Bug]]
- [[_COMMUNITY_Google Timeout Bug|Google Timeout Bug]]
- [[_COMMUNITY_LLM JSON Parsing Bug|LLM JSON Parsing Bug]]
- [[_COMMUNITY_Token Mode Bug|Token Mode Bug]]
- [[_COMMUNITY_Normalization Bugs|Normalization Bugs]]
- [[_COMMUNITY_Dependency Lifecycle|Dependency Lifecycle]]
- [[_COMMUNITY_Secret Injection Sources|Secret Injection Sources]]
- [[_COMMUNITY_Sensitive Files Policy|Sensitive Files Policy]]
- [[_COMMUNITY_Secret Hygiene|Secret Hygiene]]
- [[_COMMUNITY_OpenRouter Detector|OpenRouter Detector]]
- [[_COMMUNITY_Secret Rotation|Secret Rotation]]
- [[_COMMUNITY_Provider Usage Review|Provider Usage Review]]
- [[_COMMUNITY_Local Secret Cleanup|Local Secret Cleanup]]
- [[_COMMUNITY_Git History Remediation|Git History Remediation]]
- [[_COMMUNITY_Incident Documentation|Incident Documentation]]
- [[_COMMUNITY_Private Security Reporting|Private Security Reporting]]
- [[_COMMUNITY_Pull Request Security|Pull Request Security]]
- [[_COMMUNITY_Main Branch Security|Main Branch Security]]
- [[_COMMUNITY_Manual Security Scan|Manual Security Scan]]
- [[_COMMUNITY_Read-only CI Permissions|Read-only CI Permissions]]

## God Nodes (most connected - your core abstractions)
1. `HybridCrawler` - 20 edges
2. `SafeUrlPolicy` - 18 edges
3. `LeadAuditor` - 13 edges
4. `LeadHunterOrchestrator` - 11 edges
5. `sanitize_untrusted_text()` - 11 edges
6. `update_elapsed()` - 10 edges
7. `SafeUrlPolicyTests` - 9 edges
8. `Security Boundary Tests Job` - 9 edges
9. `LeadScraper` - 8 edges
10. `ensure_auditable_pages()` - 8 edges

## Surprising Connections (you probably didn't know these)
- `HybridCrawler` --references--> `Product Weaknesses and State-of-the-art Roadmap Query`  [EXTRACTED]
  src/crawler.py → graphify-out/memory/query_20260729_222724_quali_sono_i_punti_deboli_di_lead_hunter_v3_e_come.md
- `LeadHunterOrchestrator` --uses--> `DataExporter`  [INFERRED]
  main.py → src/exporter.py
- `LeadHunterOrchestrator` --uses--> `HybridCrawler`  [INFERRED]
  main.py → src/crawler.py
- `LeadHunterOrchestrator` --references--> `Product Weaknesses and State-of-the-art Roadmap Query`  [EXTRACTED]
  main.py → graphify-out/memory/query_20260729_222724_quali_sono_i_punti_deboli_di_lead_hunter_v3_e_come.md
- `LeadAuditor` --references--> `Product Weaknesses and State-of-the-art Roadmap Query`  [EXTRACTED]
  src/auditor.py → graphify-out/memory/query_20260729_222724_quali_sono_i_punti_deboli_di_lead_hunter_v3_e_come.md

## Communities (50 total, 30 thin omitted)

### Community 0 - "Excel Export"
Cohesion: 0.09
Nodes (30): _calculate_column_widths(), DataExporter, export_to_excel(), _format_no_website_rows(), _format_website_rows(), _get_no_website_columns(), _get_website_columns(), Lead Hunter V3 — Excel Exporter (openpyxl) Export duale:   - Modalità "no_webs (+22 more)

### Community 1 - "Orchestration and Audit"
Cohesion: 0.08
Nodes (15): LeadHunterOrchestrator, Lead Hunter V3 — Main Orchestrator & CLI Supporta due modalità operative:   -, Core Engine disaccoppiato dalla UI. Può essere invocato da CLI, GUI o API estern, Product Weaknesses and State-of-the-art Roadmap Query, LeadAuditor, Lead Hunter V3 — AI Auditor Module Due modalità:   1. "No Website" — analisi l, Pulisce e ricostruisce una pagina web utilizzando il modello economico/gratuito, Assegna un'etichetta leggibile a un URL (es. 'Homepage', 'Contatti'). (+7 more)

### Community 2 - "Secure Crawler"
Cohesion: 0.10
Nodes (12): HybridCrawler, _page_metadata(), Lead Hunter V3 — Crawl4AI Web Crawler Replaces custom HybridCrawler with Crawl4, Crawla la homepage e le pagine interne prioritarie utilizzando Crawl4AI., Pulisce gli spazi consecutivi e i ritorni a capo eccessivi per ottimizzare i tok, Estrae email dall'HTML, dal Markdown e dai tag mailto., Chiude la sessione attiva del browser Crawl4AI., Crawler basato su Crawl4AI per estrazione di Markdown semantico ottimizzato per (+4 more)

### Community 3 - "Crawl Evidence Contract"
Cohesion: 0.11
Nodes (17): audit_rejection_reason(), CrawlEvidenceError, CrawlResult, CrawlStatus, ensure_auditable_pages(), _failure_code(), from_content(), is_auditable() (+9 more)

### Community 4 - "URL Policy Security"
Cohesion: 0.13
Nodes (12): Policy fail-closed per gli URL visitati dal crawler.  La validazione viene appli, Esegue la risoluzione DNS fuori dall'event loop del browser., URL rifiutato dalla policy di rete., Risultato immutabile di una validazione URL., Valida URL e DNS, bloccando destinazioni non pubbliche.      Per ogni hostname v, Apre una nuova sessione logica di crawl., Valida schema, credenziali, porta, hostname e tutte le risposte DNS., SafeUrlPolicy (+4 more)

### Community 5 - "Production SaaS Architecture"
Cohesion: 0.12
Nodes (25): API Gateway, Authentication, and RBAC, Quota, Cost Ledger, and Billing, Deterministic Audit Workers, Evidence Store, Human Review and Approval, Job Queue and Workflow Engine, LLM Evidence Synthesizer, Logs, Metrics, Traces, and Alerts (+17 more)

### Community 6 - "Pipeline and UI Helpers"
Cohesion: 0.15
Nodes (20): Pipeline completa per lead con sito web (Streaming Parallelo).         on_phase, Dispatcher che smista alla pipeline corretta in base al mode., Pipeline originale per lead senza sito web., format_elapsed(), get_approximate_location(), on_audit_progress(), on_crawl_progress(), on_kw_end() (+12 more)

### Community 7 - "Python CI Test Matrix"
Cohesion: 0.09
Nodes (24): beautifulsoup4 >=4.12,<5, Cancel In-Progress Runs, Checkout Action Pinned to 11d5960a326750d5838078e36cf38b85af677262, CI Workflow, Compile Source Step, Compile Targets: src, tests, and main.py, CI Workflow and Ref Concurrency Control, Contents Read Permission (+16 more)

### Community 8 - "LLM Trust Boundary"
Cohesion: 0.13
Nodes (13): Controlli di sicurezza condivisi dall'applicazione., build_untrusted_pages_payload(), Sanitizzazione e incapsulamento dei dati non fidati destinati agli LLM., Normalizza testo esterno e rimuove segmenti con indicatori di injection., Serializza le evidenze web in JSON, senza delimitatori controllabili dal sito., sanitize_untrusted_text(), SanitizedContent, _strip_hidden_html() (+5 more)

### Community 9 - "Security Backlog"
Cohesion: 0.18
Nodes (12): OWASP SSRF Prevention Cheat Sheet, P0-01 SSRF and Arbitrary Navigation, P0-03 Streamlit GUI XSS, P0-08 Excel Formula Injection, P2-02 Test Suite and CI, P2-06 Browser Resource Governance and Isolation, P2-07 Policy-Aware Crawling and robots.txt, P2-08 Content and Resource Limits (+4 more)

### Community 10 - "Repository Analysis Context"
Cohesion: 0.18
Nodes (12): Git History Metrics Analysis, Portfolio Project Profile Schema, README-First Analysis Strategy, Repository Analysis Workflow, Technology Stack Detection, Shallow Repository Structure Scan, Fail-Fast Centralized API Configuration, Lead Hunter Modular Architecture (+4 more)

### Community 11 - "Audit Output Contract"
Cohesion: 0.24
Nodes (8): AuditValidationError, _bounded_string(), from_llm(), Contratti tipizzati per gli output dell'audit AI., L'output del modello non rispetta il contratto applicativo., Espone esclusivamente i campi di prodotto consentiti., WebsiteAuditResult, Modelli di dominio indipendenti da UI e provider esterni.

### Community 12 - "Legacy V2 Scout"
Cohesion: 0.27
Nodes (4): LeadHunterScouter, Cerca lead in un raggio specifico usando le coordinate GPS., Genera una matrice di coordinate attorno a un punto centrale., Esegue l'intera campagna di ricerca ed elimina i duplicati.

### Community 13 - "Legacy V1 Engine"
Cohesion: 0.29
Nodes (3): LeadHunterEngine, Cerca attività e filtra quelle che non hanno un sito web., Esporta i dati in un file Excel.

### Community 14 - "Product Positioning"
Cohesion: 0.33
Nodes (6): Agency SaaS, Lead Hunter V3 Technical and Product Audit, Managed Service, Marketplace and API, Vertical Opportunity Intelligence for Agencies, codex/p0-secure-crawl-evidence Branch

### Community 15 - "Diagnostic Testing"
Cohesion: 0.33
Nodes (5): extract_domain(), Estrae il dominio puro da un URL (es. 'www.example.com' -> 'example.com')., Lead Hunter V3 — CLI URL Testing Module Persegue il testing completo di un sing, Funzione principale che orchestra il test di un sito web e scrive i risultati, run_url_test()

### Community 16 - "Data Policy Compliance"
Cohesion: 0.50
Nodes (4): Google Places API Policies and Attributions, P0-04 Google Places Storage, Attribution, and Map Governance, P0-05 Italian Lead Generation and Marketing Compliance, Policy Engine for Google, GDPR, and Retention

### Community 17 - "CI Secret Scanning"
Cohesion: 0.50
Nodes (4): CI Gitleaks Scan of Reachable History, Full Repository History Checkout, GitHub Token for Gitleaks Action, Gitleaks Repository History Scan

### Community 19 - "Prompt and Data Exposure"
Cohesion: 0.67
Nodes (3): OWASP LLM Prompt Injection Prevention Cheat Sheet, P0-02 Indirect Prompt Injection and Prompt Leakage, P0-09 Sensitive Data and Full Prompt Exposure

## Knowledge Gaps
- **46 isolated node(s):** `PageEvidence`, `Dual Operational Modes`, `Python Runtime Dependency Set`, `Lead Hunter V3 Project Profile`, `codex/p0-secure-crawl-evidence Branch` (+41 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **30 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `HybridCrawler` connect `Secure Crawler` to `Orchestration and Audit`, `Pipeline and UI Helpers`, `Diagnostic Testing`?**
  _High betweenness centrality (0.144) - this node is a cross-community bridge._
- **Why does `LeadHunterOrchestrator` connect `Orchestration and Audit` to `Excel Export`, `Secure Crawler`, `Pipeline and UI Helpers`?**
  _High betweenness centrality (0.080) - this node is a cross-community bridge._
- **Why does `LeadAuditor` connect `Orchestration and Audit` to `LLM Trust Boundary`, `Diagnostic Testing`?**
  _High betweenness centrality (0.065) - this node is a cross-community bridge._
- **Are the 9 inferred relationships involving `HybridCrawler` (e.g. with `LeadHunterOrchestrator` and `.run_with_website()`) actually correct?**
  _`HybridCrawler` has 9 INFERRED edges - model-reasoned connections that need verification._
- **Are the 11 inferred relationships involving `SafeUrlPolicy` (e.g. with `.__init__()` and `SafeUrlPolicyTests`) actually correct?**
  _`SafeUrlPolicy` has 11 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `LeadAuditor` (e.g. with `LeadHunterOrchestrator` and `.__init__()`) actually correct?**
  _`LeadAuditor` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `LeadHunterOrchestrator` (e.g. with `LeadScraper` and `LeadAuditor`) actually correct?**
  _`LeadHunterOrchestrator` has 4 INFERRED edges - model-reasoned connections that need verification._