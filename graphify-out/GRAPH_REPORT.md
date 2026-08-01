# Graph Report - .  (2026-08-01)

## Corpus Check
- Corpus is ~23,265 words - fits in a single context window. You may not need a graph.

## Summary
- 393 nodes · 545 edges · 28 communities (17 shown, 11 thin omitted)
- Extraction: 84% EXTRACTED · 16% INFERRED · 0% AMBIGUOUS · INFERRED: 89 edges (avg confidence: 0.76)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Audit Evidence Architecture|Audit Evidence Architecture]]
- [[_COMMUNITY_GUI Audit Orchestration|GUI Audit Orchestration]]
- [[_COMMUNITY_Security Product Roadmap|Security Product Roadmap]]
- [[_COMMUNITY_Crawl Evidence Contracts|Crawl Evidence Contracts]]
- [[_COMMUNITY_Privacy Geolocation Controls|Privacy Geolocation Controls]]
- [[_COMMUNITY_Browser Crawl Runtime|Browser Crawl Runtime]]
- [[_COMMUNITY_SSRF URL Policy|SSRF URL Policy]]
- [[_COMMUNITY_Lead Filtering Rules|Lead Filtering Rules]]
- [[_COMMUNITY_LLM Content Safety|LLM Content Safety]]
- [[_COMMUNITY_Safe Excel Export|Safe Excel Export]]
- [[_COMMUNITY_Safe GUI Rendering|Safe GUI Rendering]]
- [[_COMMUNITY_Google Places Scraping|Google Places Scraping]]
- [[_COMMUNITY_Project Analysis Knowledge|Project Analysis Knowledge]]
- [[_COMMUNITY_Legacy Scouter Pipeline|Legacy Scouter Pipeline]]
- [[_COMMUNITY_Legacy Lead Engine|Legacy Lead Engine]]
- [[_COMMUNITY_Market Product Positioning|Market Product Positioning]]
- [[_COMMUNITY_Audit Contract Tests|Audit Contract Tests]]
- [[_COMMUNITY_Test Package Metadata|Test Package Metadata]]
- [[_COMMUNITY_Competitor Selection Logic|Competitor Selection Logic]]
- [[_COMMUNITY_Runtime Dependencies|Runtime Dependencies]]
- [[_COMMUNITY_Product Audit Query|Product Audit Query]]
- [[_COMMUNITY_Exporter Documentation|Exporter Documentation]]
- [[_COMMUNITY_Column Sizing Logic|Column Sizing Logic]]
- [[_COMMUNITY_Orchestrator Alias|Orchestrator Alias]]
- [[_COMMUNITY_Auditor Alias|Auditor Alias]]
- [[_COMMUNITY_Crawler Alias|Crawler Alias]]
- [[_COMMUNITY_Exporter Alias|Exporter Alias]]

## God Nodes (most connected - your core abstractions)
1. `SafeUrlPolicy` - 21 edges
2. `HybridCrawler` - 19 edges
3. `LeadAuditor` - 12 edges
4. `sanitize_untrusted_text()` - 11 edges
5. `Website Audit` - 11 edges
6. `update_elapsed()` - 10 edges
7. `GeolocationError` - 10 edges
8. `UrlPolicyError` - 10 edges
9. `LeadHunterOrchestrator` - 9 edges
10. `SafeUrlPolicyTests` - 9 edges

## Surprising Connections (you probably didn't know these)
- `Lead Hunter Automated Test Package` --conceptually_related_to--> `Python Security Boundary Test Matrix`  [INFERRED]
  tests/__init__.py → github/workflows/ci.yml
- `P0 Application Security Hardening` --references--> `Sensitive Text Redaction`  [EXTRACTED]
  docs/AUDIT_PRODOTTO_E_ROADMAP_STATO_DELL_ARTE.md → tests/test_privacy_controls.py
- `Policy-Aware Deterministic Evidence with AI Synthesis and Human Approval` --conceptually_related_to--> `UNTRUSTED_WEB_DATA Boundary`  [INFERRED]
  docs/AUDIT_PRODOTTO_E_ROADMAP_STATO_DELL_ARTE.md → tests/test_untrusted_content.py
- `Python Security Boundary Test Matrix` --references--> `Safe URL Policy Tests`  [EXTRACTED]
  github/workflows/ci.yml → tests/test_url_policy.py
- `Policy-Aware Deterministic Evidence with AI Synthesis and Human Approval` --conceptually_related_to--> `Safe URL Policy Validation`  [INFERRED]
  docs/AUDIT_PRODOTTO_E_ROADMAP_STATO_DELL_ARTE.md → tests/test_url_policy.py

## Hyperedges (group relationships)
- **Website Lead Qualification Pipeline** — main_run_with_website, crawler_crawl, crawl_is_auditable, auditor_audit_website, exporter_export_to_excel [EXTRACTED 1.00]
- **LLM Untrusted Data Boundary** — untrusted_sanitize_untrusted_text, untrusted_build_untrusted_pages_payload, untrusted_system_rules, audit_from_llm, auditor_audit_website [INFERRED 0.95]
- **Network Destination Safety** — url_policy_safe_url_policy, url_policy_validate, crawler_secure_route, crawler_crawl, geolocation_lookup_approximate_location [EXTRACTED 1.00]
- **Privacy Controls Defense Bundle** — test_privacy_controls_redact_sensitive_text, test_privacy_controls_lookup_approximate_location, test_privacy_controls_purge_expired_diagnostic_files [EXTRACTED 1.00]
- **P0 Security Boundary Suite** — test_url_policy_ssrf_guard, test_untrusted_content_untrusted_web_data, test_spreadsheet_security_sanitize_spreadsheet_value, test_privacy_controls_redact_sensitive_text [EXTRACTED 1.00]
- **Evidence-Driven Agency Product Operating Model** — audit_target_architecture, audit_policy_aware_evidence_product, audit_vertical_opportunity_intelligence, audit_managed_service_first [INFERRED 0.95]

## Communities (28 total, 11 thin omitted)

### Community 0 - "Audit Evidence Architecture"
Cohesion: 0.06
Nodes (46): LLM Audit Contract Validation, Public Audit Projection, Website Audit Result, No-Website Lead Audit, No-Website Batch Audit, Website Audit, Website Batch Audit, LLM Page Cleaning (+38 more)

### Community 1 - "GUI Audit Orchestration"
Cohesion: 0.08
Nodes (27): LeadHunterOrchestrator, Lead Hunter V3 — Main Orchestrator & CLI Supporta due modalità operative:   -, Pipeline completa per lead con sito web (Streaming Parallelo).         on_phase, Dispatcher che smista alla pipeline corretta in base al mode., Core Engine disaccoppiato dalla UI. Può essere invocato da CLI, GUI o API estern, Pipeline originale per lead senza sito web., LeadAuditor, Lead Hunter V3 — AI Auditor Module Due modalità:   1. "No Website" — analisi l (+19 more)

### Community 2 - "Security Product Roadmap"
Cohesion: 0.06
Nodes (38): Crawl4AI Browser-Based Crawler, Garante Privacy Promotional Activity and Anti-Spam Guidelines, Google Places Storage, Attribution and Map Governance, Google Places API Policies and Attributions, Lead Hunter V3 Technical and Product Audit, OWASP LLM Prompt Injection Prevention Cheat Sheet, OWASP SSRF Prevention Cheat Sheet, P0 Application Security Hardening (+30 more)

### Community 3 - "Crawl Evidence Contracts"
Cohesion: 0.08
Nodes (25): AuditValidationError, _bounded_string(), from_llm(), Contratti tipizzati per gli output dell'audit AI., L'output del modello non rispetta il contratto applicativo., Espone esclusivamente i campi di prodotto consentiti., WebsiteAuditResult, audit_rejection_reason() (+17 more)

### Community 4 - "Privacy Geolocation Controls"
Cohesion: 0.09
Nodes (21): RuntimeError, ApproximateLocation, configured_geolocation_endpoint(), GeolocationError, lookup_approximate_location(), Explicit, HTTPS-only approximate IP geolocation., A safe, user-displayable geolocation failure., Return the operator-configured provider without exposing credentials. (+13 more)

### Community 5 - "Browser Crawl Runtime"
Cohesion: 0.10
Nodes (12): HybridCrawler, _page_metadata(), Lead Hunter V3 — Crawl4AI Web Crawler Replaces custom HybridCrawler with Crawl4, Crawla la homepage e le pagine interne prioritarie utilizzando Crawl4AI., Pulisce gli spazi consecutivi e i ritorni a capo eccessivi per ottimizzare i tok, Estrae email dall'HTML, dal Markdown e dai tag mailto., Chiude la sessione attiva del browser Crawl4AI., Crawler basato su Crawl4AI per estrazione di Markdown semantico ottimizzato per (+4 more)

### Community 6 - "SSRF URL Policy"
Cohesion: 0.13
Nodes (12): Policy fail-closed per gli URL visitati dal crawler.  La validazione viene app, Esegue la risoluzione DNS fuori dall'event loop del browser., URL rifiutato dalla policy di rete., Risultato immutabile di una validazione URL., Valida URL e DNS, bloccando destinazioni non pubbliche.      Per ogni hostname, Apre una nuova sessione logica di crawl., Valida schema, credenziali, porta, hostname e tutte le risposte DNS., SafeUrlPolicy (+4 more)

### Community 7 - "Lead Filtering Rules"
Cohesion: 0.09
Nodes (23): _check_copywriting_age(), _check_whois_age(), clean_and_translate_categories(), extract_address_details(), extract_domain(), filter_by_business_age(), filter_by_reviews(), filter_ecommerce() (+15 more)

### Community 8 - "LLM Content Safety"
Cohesion: 0.13
Nodes (13): Controlli di sicurezza condivisi dall'applicazione., build_untrusted_pages_payload(), Sanitizzazione e incapsulamento dei dati non fidati destinati agli LLM., Normalizza testo esterno e rimuove segmenti con indicatori di injection., Serializza le evidenze web in JSON, senza delimitatori controllabili dal sito., sanitize_untrusted_text(), SanitizedContent, _strip_hidden_html() (+5 more)

### Community 9 - "Safe Excel Export"
Cohesion: 0.14
Nodes (15): is_text_cell(), Spreadsheet output guards for untrusted lead and LLM values., Neutralize formula-like text while preserving intentional numeric cells.      Ex, Return whether an exported value must be forced to Excel string type., sanitize_spreadsheet_value(), _calculate_column_widths(), DataExporter, export_to_excel() (+7 more)

### Community 10 - "Safe GUI Rendering"
Cohesion: 0.17
Nodes (10): build_keyword_card_html(), build_phase_card_html(), escape_dynamic_html(), normalize_log_message(), Safe presentation helpers for values rendered by the Streamlit GUI., Escape a dynamic value before interpolating it into trusted static HTML., Build the keyword card while treating every caller value as untrusted., Build the phase card with escaped icon, text and elapsed time. (+2 more)

### Community 11 - "Google Places Scraping"
Cohesion: 0.18
Nodes (5): LeadScraper, Esegue il Reverse Geocoding per ottenere il nome della città.         Restituisc, [Metodo Privato] Genera la matrice di coordinate in base al GRID_SIZE configurat, [Metodo Privato] Esegue una singola chiamata API per un punto specifico., [Metodo Pubblico Principale] Orchestra la generazione della griglia.         on_

### Community 12 - "Project Analysis Knowledge"
Cohesion: 0.18
Nodes (12): Git History Metrics Analysis, Portfolio Project Profile Schema, README-First Analysis Strategy, Repository Analysis Workflow, Technology Stack Detection, Shallow Repository Structure Scan, Fail-Fast Centralized API Configuration, Lead Hunter Modular Architecture (+4 more)

### Community 13 - "Legacy Scouter Pipeline"
Cohesion: 0.27
Nodes (4): LeadHunterScouter, Cerca lead in un raggio specifico usando le coordinate GPS., Genera una matrice di coordinate attorno a un punto centrale., Esegue l'intera campagna di ricerca ed elimina i duplicati.

### Community 14 - "Legacy Lead Engine"
Cohesion: 0.29
Nodes (3): LeadHunterEngine, Cerca attività e filtra quelle che non hanno un sito web., Esporta i dati in un file Excel.

### Community 15 - "Market Product Positioning"
Cohesion: 0.50
Nodes (4): Apify Platform Documentation, Claygent AI Agents for GTM, Managed Service Before SaaS, Vertical Opportunity Intelligence for Agencies

## Knowledge Gaps
- **40 isolated node(s):** `Dual Operational Modes`, `Python Runtime Dependency Set`, `Lead Hunter V3 Project Profile`, `Product Weaknesses and State-of-the-art Roadmap Query`, `PageEvidence` (+35 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **11 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `HybridCrawler` connect `Browser Crawl Runtime` to `GUI Audit Orchestration`, `Privacy Geolocation Controls`?**
  _High betweenness centrality (0.087) - this node is a cross-community bridge._
- **Why does `SafeUrlPolicy` connect `SSRF URL Policy` to `Privacy Geolocation Controls`, `Browser Crawl Runtime`?**
  _High betweenness centrality (0.068) - this node is a cross-community bridge._
- **Why does `LeadHunterOrchestrator` connect `GUI Audit Orchestration` to `Safe Excel Export`, `Browser Crawl Runtime`?**
  _High betweenness centrality (0.044) - this node is a cross-community bridge._
- **Are the 13 inferred relationships involving `SafeUrlPolicy` (e.g. with `.__init__()` and `GeolocationError`) actually correct?**
  _`SafeUrlPolicy` has 13 INFERRED edges - model-reasoned connections that need verification._
- **Are the 9 inferred relationships involving `HybridCrawler` (e.g. with `LeadHunterOrchestrator` and `.run_with_website()`) actually correct?**
  _`HybridCrawler` has 9 INFERRED edges - model-reasoned connections that need verification._
- **Are the 11 inferred relationships involving `str` (e.g. with `_page_metadata()` and `.crawl()`) actually correct?**
  _`str` has 11 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `LeadAuditor` (e.g. with `LeadHunterOrchestrator` and `.__init__()`) actually correct?**
  _`LeadAuditor` has 3 INFERRED edges - model-reasoned connections that need verification._