---
type: "query"
date: "2026-07-29T22:27:24.741870+00:00"
question: "Quali sono i punti deboli di Lead Hunter V3 e come renderlo vendibile e stato dell arte?"
contributor: "graphify"
source_nodes: ["HybridCrawler", "LeadHunterOrchestrator", "LeadAuditor", "Python Dependency Manifest"]
---

# Q: Quali sono i punti deboli di Lead Hunter V3 e come renderlo vendibile e stato dell arte?

## Answer

Audit completato il 2026-07-30. Verdetto: prodotto potenzialmente vendibile come evidence-backed opportunity intelligence per agenzie, ma non pronto come SaaS pubblico. Blocker principali: SSRF, prompt injection indiretta, XSS Streamlit, Google Places e privacy/marketing, audit di pagine 403, assenza di autenticazione e tenant isolation, Excel formula injection, leakage di prompt e dati. Bug funzionali: filtro eta sempre permissivo, audit no-website non collegato, filtro ecommerce disattivato, filtro social a substring. Roadmap completa in docs/AUDIT_PRODOTTO_E_ROADMAP_STATO_DELL_ARTE.md.

## Source Nodes

- HybridCrawler
- LeadHunterOrchestrator
- LeadAuditor
- Python Dependency Manifest