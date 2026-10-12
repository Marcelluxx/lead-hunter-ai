# Correttezza funzionale Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** correggere i filtri e rendere affidabili modalità crawl, CMS e input locali.
**Architecture:** correggere adapter esistenti; detector puro condiviso, dati crawl
e provenance separati dai materiali privati. Nessuna riscrittura di worker/licensing.
**Tech Stack:** Python3.12, unittest, BeautifulSoup, Crawl4AI/Playwright già bloccati,
SQLAlchemy/PostgreSQL, OpenPyXL. Nessuna dipendenza nuova.
**Spec:** docs/superpowers/specs/2026-10-11-functional-correctness-design.md

Metodo native conservato dal mandato autonomo. Baseline develop9941a22, PR #12
merged dopo review/fix e CI38125603382/Security38125603395 PASS su c7f86da.
Comandi test: uv0.11.15 run --frozen --group test python -m unittest MODULE -v;
runtime già installato e isolato. Ogni Task verifica la suite intera sul codice
modificato; task-done ripete il comando mirato del brief sullo stesso codice.
La suite finale usa flags PostgreSQL/Chromium/Docker nella workspace propria.

## Global Constraints

- Nessun contenuto Google in storage, prompt AI o Excel oltre riferimenti consentiti.
- Licenze/MFA/grants correnti ed isolamento workspace rimangono gate condivisi.
- Nessuna richiesta provider reale o credenziale operatore necessaria ai test.
- Nessun nuovo parametro implicito ai job schema1; filtro locale e-commerce attivo.
- Modalità high_fidelity/optimized; max_pages1–20; URL policy rete resta obbligatoria.

## Review Focus

1. Siti omonimi e hostname con parole social nel path: nessuna esclusione errata.
2. DOM parla di pagamenti/tecnologie senza vendere: nessun falso e-commerce/CMS.
3. Markdown ottimizzato corto: fallback preserva evidenza e contatti utili.
4. Città internazionali e input null/provider incompleto: niente crash o città inventata.
5. URL invalido con licenza valida: niente auditor/cleanup/file prima dell'errore input.

### Task 1: qualificazione locale

**Files:** src/filters.py, main.py; tests/test_functional_filters.py,
tests/test_compliant_pipeline.py.
**Interfaces:** preservare filter_by_business_age(domain, html_text='', min_years=5),
filter_social_media(domain,social_domains), filter_franchise(name,names,known),
filter_ecommerce(html_text,indicators), extract_domain(url).

- [ ] **Scrivere test RED** in FunctionalFilterTests con le seguenti assertion:

```python
# WHOIS fixture returns datetime current year; no external lookup.
self.assertFalse(filter_by_business_age('studio.test', '', 5))
self.assertTrue(filter_by_business_age('studio.test', '<p>Dal 1999</p>', 5))
self.assertFalse(filter_social_media('examplex.com', ['x.com']))
self.assertTrue(filter_social_media('m.x.com.', ['x.com']))
self.assertFalse(filter_franchise('Pampa Studio', [], ['pam']))
self.assertFalse(filter_franchise('Studio', ['Studio Uno', 'Studio Due', 'Studio Tre'], []))
self.assertFalse(filter_ecommerce('<p>Blog su Stripe e cart</p>', ECOMMERCE_INDICATORS))
self.assertTrue(filter_ecommerce(SHOP_DOM_WITH_CART_AND_PRODUCT, ECOMMERCE_INDICATORS))
```

- [ ] Test age: WHOISrecente+nessuntesto False; unknown True; sitoold+WHOISrecente
  True; date multiple/malformate/future robuste, testo nonvisibile non conta.
- [ ] Test social: x.com e m.x.com True; examplex.com, instagram.com.example.org,
  sito.test/path/facebook.com False; hostname uppercase/punto finale normalizzati.
- [ ] Test franchise: PAM/Pam Milano True, Pampa Studio False; nomi comuni ripetuti
  non provano franchise. Marchio completo per token, non substring.
- [ ] Corpus ecommerce: azione carrello+Product/Offer/price/domcommerce True;
  Stripe+cart nel blog, parole nascoste/commenti, shopify articolo False.
- [ ] Eseguire prima test; Expected: FAIL sui bug esistenti, non import/config.
- [ ] Implementare tri-state, normalizzazione host/token e segnali DOM indipendenti.
  WHOIStimeout10; date minvalida; unknown esplicito nei log senza payload sensibile.
- [ ] Riattivare ecommerce in run_with_website prima dell'auditor; integrare un sito
  positivo e uno negativo nel test pipeline mantenendo provenance/filtri licenziati.
- [ ] Run tests.test_functional_filters tests.test_compliant_pipeline e rating delivery;
  Expected: PASS. Commit/push milestone.

### Task 2: modalità contenuto e rendering

**Files:** src/crawler.py, src/domain/crawl.py, main.py;
tests/test_crawler_modes.py, tests/test_crawler_runtime.py.
**Interfaces:** HybridCrawler._select_markdown(provider_markdown)->str;
CrawlResult.browser_used bool, render_strategy str, js_required Optional[bool].
is_dynamic rimane compatibilità nullable: senza confronto HTTP statico è unknown.

- [ ] **Scrivere test RED** CrawlerModeTests e Chromium fixture subclass:

```python
md = SimpleNamespace(raw_markdown='R' * 500, fit_markdown='F' * 120)
self.assertEqual(HybridCrawler(token_mode='high_fidelity')._select_markdown(md), 'R' * 500)
self.assertEqual(HybridCrawler(token_mode='optimized')._select_markdown(md), 'F' * 120)
md.fit_markdown = 'short'
self.assertEqual(HybridCrawler(token_mode='optimized')._select_markdown(md), 'R' * 500)
self.assertTrue(result.browser_used)  # actual Chromium arun via fixture transport
self.assertEqual(result.render_strategy, 'browser')
self.assertIsNone(result.js_required)
self.assertIsNone(result.is_dynamic)
```

- [ ] Test generator Crawl4AI reale: fixture contiene corpo+boilerplate; raw
  high_fidelity conserva testo, optimized fit riduce; optimized corto ricade raw.
  Entrambe homepage/interne usano helper. token_mode invalido rifiutato.
- [ ] Browser fixture reale: browser_used True dopo arun, js_required unknown;
  URL bloccato prima di arun browser_used False. Nessuna log JS-required inventata.
- [ ] Run focused; Expected: FAIL strategia identica/metadati mancanti.
- [ ] Implementare helper, config coerente, metadati; log usa browser_used.
- [ ] Run browser opt-in e network guard; Expected: PASS. Commit/push milestone.

### Task 3: CMS osservato e provenance DOM

**Files:** create src/domain/technology.py; modify src/domain/crawl.py,
src/crawler.py, src/domain/provenance.py, src/application/provenance.py,
src/application/job_results.py; tests/test_technology_detection.py,
tests/test_technology_reports.py.
**Interfaces:** detect_technologies(html)->tuple[TechnologyMatch,...],
TechnologyMatch(name,signals,confidence,rules_version='1'); nessuna versione
software inferita. CrawlResult raw_html_home_sha256; VerifiedLead technology_signals
tuple bounded e technology_rules_version. framework deriva dal detector.

- [ ] **Scrivere test RED** TechnologyDetectionTests/TechnologyReportTests:

```python
matches = detect_technologies('<meta name="generator" content="WordPress 6">')
self.assertEqual(matches[0].name, 'WordPress')
self.assertEqual(matches[0].rules_version, '1')
self.assertTrue(matches[0].signals)
self.assertEqual(detect_technologies('<p>Parliamo di WordPress</p>'), ())
lead = build_verified_lead(crawl, search_keyword='Studio', audit={'framework': 'Inventato'})
self.assertEqual(lead.framework, 'WordPress')
self.assertEqual(lead.provenance['framework'].evidence_sha256, sha256(crawl.raw_html_home.encode()).hexdigest())
self.assertNotIn('Inventato', repr(lead.to_export_record()))
```

- [ ] Fixtures generator meta e asset specifici WordPress/Drupal/Joomla/Shopify/Wix/
  Squarespace/Next.js/Nuxt; testo blog con nomi, commenti o query non basta.
  unknown non prende framework inventato dal LLM.
- [ ] Report locale/server identici: framework+segnali, hashDOM corretto distinto
  hashclean audit; source_url ufficiale. Nessun HTML/prompt/provider nel report.
- [ ] Run focused; Expected: FAIL detector assente/falso framework LLM.
- [ ] Implementare regole pure bounded su attributi strutturati; pattern sui path
  asset, non contenuto arbitrario. Integrare provenance usando hash HTML raccolto
  ed existing evidence persistence; tecnologia pubblica allowlist API/Excel.
- [ ] Run detector/provenance/worker/API/output XLSX riaperto; Expected: PASS.
  Commit/push milestone.

### Task 4: normalizzazione e preflight

**Files:** src/filters.py, main.py, src/ui/diagnostic_panel.py, src/web/routes/jobs.py;
tests/test_functional_inputs.py, tests/test_diagnostic_delivery.py, tests/test_commercial_job_api.py.
**Interfaces:** categorie/indirizzo preservano firme legacy; località unknown=N/A;
SafeUrlPolicy.validate_syntax riusata prima di effetti, validate rete nel crawler.

- [ ] **Scrivere test RED** FunctionalInputTests e CommercialJobApiTests:

```python
self.assertEqual(main(['--lat','0','--lng','0','--keywords','studio','--out','fixture.xlsx']), 0)
self.assertEqual(main(['--lat','nan','--lng','9','--keywords','studio']), 2)
self.assertEqual(main(['--test-url','not-a-url','--full-diagnostics']), 2)
settings.assert_not_called(); auditor.assert_not_called(); crawler.assert_not_called()
self.assertEqual(clean_and_translate_categories([None, ' dentist ', 'dentist', 42]), 'Dentista')
self.assertEqual(extract_address_details({'search_keyword': 'Dentista'}), ('N/A','N/A'))
self.assertEqual(response.status_code, 409)  # resume after reducing budget
self.assertEqual(response.json(), {'detail':'budget_exceeded'})
self.assertEqual(job.state, 'cancelled'); self.assertEqual(publisher.messages, initial_messages)
```

- [ ] Test CLI lat0/lng0 avvia con fake transport; nan/inf/range/missing non avvia
  settings/orchestrator/file, codice2. Test URLnot-a-url/urlconcredenziali malformed
  precedono auditor/crawler/cleanup/settings, con e senza licenza; GUI equivalente.
- [ ] Test categorie null/miste/duplicati/trim max2; località strutturate con nome
  maiuscolo e Unicode conservato; no indirizzo non diventa keyword-città.
- [ ] Run focused; Expected: FAIL zero/URL/normalizzazione bug attuali.
- [ ] Implementare confini input e normalizzazione tollerante; aggiornare copy
  etàdominio/unknown/strategie/CMS nella documentazione prodotto.
  Admission e resume usano stesso409/budget_exceeded; reactivation rollback rimane
  invariato. Questa fase risolve il Minor rinviato dalla review pipeline.
- [ ] Run full suite con PostgreSQL+Chromium+Docker flags e lock/compile/diff/secrets;
  Expected: PASS senza skip. Commit/push milestone.
- [ ] Review fresca unica intero branch; one fix pass TDD Critical/Important;
  persist report/rulings/minors, CI/Security esattoHEAD e merge develop.
