# Reference export implementation and review

Date: 9 October 2026. Branch: `codex/no-website-reference-export`.
Draft PR: [#8](https://github.com/Marcelluxx/lead-hunter-ai/pull/8), stacked on
the licensing [PR #7](https://github.com/Marcelluxx/lead-hunter-ai/pull/7).

## Delivered behavior

Local CLI opts in with `--export-references --mode no_website`; GUI prepares and
delivers inline XLSX bytes from the last successful no-website search. Only Place ID
and Google Maps link enter the workbook, deduplicated with strict typed validation.
EXECUTE/VIEW checks use fresh contexts; expiry, revocation and current scope/role
are enforced. Atomic saves preserve old files on pre-delivery failure. Base search
remains available when export cannot accept its identifiers or batch size.

## Independent review and correction

A fresh reviewer on GPT-6-astra reviewed `876c839..969fb95`, read the approved
specification and plan, and independently ran 35 targeted tests successfully.
It found one Important regression, no Critical or Minor findings: export projection
could abort GUI base-result display before any export request.

The implementer reproduced both unsupported ID `A/B` and 10,001 candidates with
`test_export_validation_does_not_hide_base_results`: RED, zero dataframes.
The fix catches the export-specific error locally, keeps IDs empty, displays its
redacted code and continues showing attributed transient results. GREEN verifies
both cases, the complete displayed row count, no generic error and no export payload.
No second reviewer was dispatched; the native workflow verifies fixes by RED→GREEN
and the full suite. After the fix, 194 tests ran: 183 passed and the 11 existing
environment-dependent tests were skipped locally. Lock, compilation, diff and
secret checks passed again. The PR checks provide the final-head database/container
and Python matrix results; the Security vulnerability gate remains blocking.

## Evidence and release limits

Before the review fix: local suite 193 tests, OK with 11 existing skips (10 require
PostgreSQL and one is an opt-in Docker distribution build). Lock, compile, diff and
Gitleaks checks passed. [CI at 969fb95](https://github.com/Marcelluxx/lead-hunter-ai/actions/runs/37951968977)
passed Python 3.10–3.13, all 10 mandatory PostgreSQL tests, container build, customer
image inspection, migration round trip and API smoke. Final fix/head checks are
recorded in the PR checks; completion requires those same code gates to pass.

Real in-app browser evidence: 5,587 XLSX bytes received through iframe srcdoc,
decoded and reopened with three reference rows and the exact two columns, no
static media URL; after expiry a new preparation was denied and no iframe remained.
The in-app browser's automatic download/file-save events timed out. Successful
OS saving from that browser is not claimed; byte delivery and CLI disk saving are
verified separately.

Fresh local vulnerability audit reports NLTK 3.10.3, `PYSEC-2026-3740`, with no fixed
version. [Security at 969fb95](https://github.com/Marcelluxx/lead-hunter-ai/actions/runs/37951968986)
passes Gitleaks and fails the supply-chain audit. No vulnerability exception or
dependency change was introduced. Commercial release/merge remains blocked by
this existing gate and the licensing integration prerequisite.

## Rulings made by the implementer

- The plan listed review before the final implementation commit; native review
  needs a committed branch. Commit verified implementation, review the whole diff,
  then commit verified fixes and rerun gates. Cost if wrong: checks must be repeated
  on the changed head; no merge occurs before review/gates.
- Worker and public job-export endpoints remain deferred as specified. Cost if
  wrong: the commercial server pipeline is still unavailable.
- Live Place ID resolution and contractual eligibility were not reassessed in
  code review; the approved reference-only boundary remains binding. Cost if wrong:
  IDs may no longer resolve, and external provider/legal validation remains a release task.
- Projection over excluded candidates has no separate iteration cap because current
  discovery supplies materialized lists; qualifying references are bounded at 10,000.
  Cost if wrong: a future unbounded excluded-candidate source needs its own input bound.
- The existing NLTK vulnerability is outside this subproject; keep its release gate
  blocking without an exception. Cost if wrong: commercialization waits for remediation.

Deferred minors: none. Worktree and draft PR remain available for integration.
