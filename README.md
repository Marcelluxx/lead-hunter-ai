<h1 align="center">Lead Hunter V3</h1>

<p align="center">
  <strong>Evidence-first B2B lead discovery and website audit platform</strong>
</p>

<p align="center">
  Discover local businesses, verify official websites, collect traceable crawl evidence,
  run guarded AI audits, and produce professional lead reports.
</p>

<p align="center">
  <a href="https://github.com/Marcelluxx/lead-hunter-ai/actions/workflows/ci.yml"><img src="https://github.com/Marcelluxx/lead-hunter-ai/actions/workflows/ci.yml/badge.svg?branch=develop" alt="CI status"></a>
  <a href="https://github.com/Marcelluxx/lead-hunter-ai/actions/workflows/security.yml"><img src="https://github.com/Marcelluxx/lead-hunter-ai/actions/workflows/security.yml/badge.svg?branch=develop" alt="Security status"></a>
  <img src="https://img.shields.io/badge/Python-3.10--3.13-3776AB?logo=python&logoColor=white" alt="Python 3.10 through 3.13">
  <img src="https://img.shields.io/badge/PostgreSQL-17-4169E1?logo=postgresql&logoColor=white" alt="PostgreSQL 17">
  <img src="https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white" alt="Docker Compose">
  <img src="https://img.shields.io/badge/License-Proprietary-critical" alt="Proprietary license">
</p>

> [!IMPORTANT]
> This repository is a **verified development baseline**, not a finished public SaaS.
> The direct CLI pipeline and internal Streamlit console are usable; the server core
> provides authentication, workspaces, privacy controls, budgets, persistence, and
> queues, but commercial crawl/audit jobs are not yet connected to the worker runtime.

## Table of contents

- [Product overview](#product-overview)
- [Current maturity](#current-maturity)
- [Architecture](#architecture)
- [Security and privacy](#security-and-privacy)
- [Prerequisites](#prerequisites)
- [Quick start with Docker](#quick-start-with-docker)
- [Local CLI and GUI setup](#local-cli-and-gui-setup)
- [Configuration reference](#configuration-reference)
- [Operations manual](#operations-manual)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)
- [Project structure](#project-structure)
- [Roadmap](#roadmap)
- [Development workflow](#development-workflow)
- [Security reporting](#security-reporting)
- [License](#license)

## Product overview

Lead Hunter V3 combines local-business discovery, guarded web crawling, evidence
capture, AI-assisted analysis, and controlled reporting. It is designed for agencies,
consultancies, and internal sales teams that need to identify businesses with concrete,
demonstrable digital opportunities.

The product supports two direct operating modes:

| Mode | Purpose | Current output |
|---|---|---|
| `no_website` | Discover businesses without an official website | Transient, attributed Google Places results displayed only for the active session; export is intentionally disabled |
| `with_website` | Verify official sites, crawl selected pages, run an AI audit, and qualify opportunities | Verified leads exported to a protected XLSX report |

Core capabilities include:

- Google Places V1 discovery with a bounded geographic grid and provider attribution;
- official-site verification and provenance-aware domain models;
- Crawl4AI/Playwright crawling with SSRF, redirect, and private-network guards;
- evidence records containing status, content type, hash, timestamp, and source URL;
- untrusted-content boundaries before data reaches an LLM;
- professional-email classification, consent policy, retention, and suppression;
- spreadsheet formula-injection protection;
- FastAPI server core with JWT authentication, MFA, RBAC, workspaces, budgets, and audit logs;
- PostgreSQL row-level security and separate application/worker roles;
- Redis/Dramatiq job and retention infrastructure;
- reproducible dependencies, SBOM generation, vulnerability checks, license policy, and full-history secret scanning.

## Current maturity

| Area | Status | Notes |
|---|---|---|
| Direct CLI pipeline | Available | `with_website` requires provider keys and the private prompt bundle |
| Streamlit console | Internal/demo | Useful for controlled operation; it is not the final customer frontend |
| Website crawler | Available | Evidence-first and guarded, but broader crawler resource governance remains on the roadmap |
| XLSX reports | Available | Formula-neutralized and generated only from verified leads |
| FastAPI platform core | Available | Authentication, MFA, RBAC, workspaces, budgets, privacy APIs, and audit logging |
| PostgreSQL and RLS | Available | Tested on PostgreSQL 17 with fail-closed workspace isolation |
| Retention worker | Available | Bounded, restartable contact deletion with Redis scheduling |
| Commercial job worker | Scaffold only | Unsupported jobs deliberately fail with `pipeline_not_configured` and release their budget reservation |
| Public SaaS | Not ready | Product frontend, billing, SSO, observability, operational controls, and legal gates remain |
| Customer release artifacts | Not ready | Image signing, provenance attestation, signed update manifests, and automated rollback remain |

For the detailed technical and commercial assessment, read
[`docs/AUDIT_PRODOTTO_E_ROADMAP_STATO_DELL_ARTE.md`](docs/AUDIT_PRODOTTO_E_ROADMAP_STATO_DELL_ARTE.md).

## Architecture

```mermaid
flowchart LR
    subgraph Direct["Direct lead pipeline"]
        Places["Google Places V1"] --> Discovery["Transient discovery"]
        Discovery --> Crawler["Guarded Crawl4AI crawler"]
        Crawler --> Evidence["Verified crawl evidence"]
        Evidence --> Boundary["Untrusted-content boundary"]
        Boundary --> Audit["Private prompt provider + OpenRouter"]
        Audit --> Lead["Verified lead"]
        Lead --> XLSX["Protected XLSX report"]
    end

    subgraph Platform["Server platform core"]
        API["FastAPI"] --> Auth["JWT, MFA, RBAC"]
        API --> DB["PostgreSQL 17 + RLS"]
        API --> Redis["Redis rate limits and queue"]
        Redis --> Worker["Dramatiq worker"]
        Worker --> DB
        Scheduler["Retention scheduler"] --> Redis
    end

    Worker -. commercial pipeline adapter pending .-> Crawler
```

The domain, application, and infrastructure layers are intentionally separated.
Provider response documents remain transient, queue messages contain only UUIDs, and
workspace context is applied at the database boundary.

The generated architecture knowledge graph is available as:

- [`graphify-out/GRAPH_REPORT.md`](graphify-out/GRAPH_REPORT.md) — human-readable report;
- [`graphify-out/graph.html`](graphify-out/graph.html) — interactive visualization;
- [`graphify-out/graph.json`](graphify-out/graph.json) — machine-readable graph.

## Security and privacy

The repository implements defense in depth rather than treating the crawler or LLM as
trusted components.

- URL validation blocks non-HTTP(S), credential-bearing, loopback, private, link-local,
  reserved, and unsafe redirect destinations.
- Browser requests are checked again at the Playwright routing boundary.
- Crawled text is sanitized and wrapped as untrusted data before LLM processing.
- Provider payloads cannot cross the persistence or queue boundary.
- Named professional contacts require an explicit workspace privacy policy.
- Suppression is HMAC-backed and checked before persistence and export.
- Default contact retention is bounded; deletion workers run in finite batches.
- Diagnostic artifacts are opt-in and time-limited.
- API credentials are encrypted at rest with a workspace-independent master key.
- Runtime database roles cannot bypass PostgreSQL RLS.
- Gitleaks scans the complete Git history in CI.

This code does not replace legal analysis. Commercial operation in Italy or the EU still
requires a documented lawful basis, privacy notices, processor agreements, a subprocessor
inventory, Google Maps Platform contractual review, and an outreach-compliance assessment.

## Prerequisites

Recommended:

- Git;
- Docker Desktop with Docker Compose v2;
- `uv` 0.11.15;
- Python 3.10, 3.11, 3.12, or 3.13;
- OpenSSL for local JWT key generation;
- a Google Cloud project with Places API V1 enabled;
- an OpenRouter key for the website-audit mode;
- the private prompt provider for LLM-backed operations.

Install `uv` by following the official instructions at <https://docs.astral.sh/uv/>.

## Quick start with Docker

### 1. Clone the repository

```bash
git clone https://github.com/Marcelluxx/lead-hunter-ai.git
cd lead-hunter-ai
```

### 2. Create local configuration

Linux/macOS:

```bash
cp .env.example .env
mkdir -p secrets
```

PowerShell:

```powershell
Copy-Item .env.example .env
New-Item -ItemType Directory -Force secrets | Out-Null
```

Edit `.env` and replace every placeholder password or key. Generate two independent
32-byte URL-safe keys with:

```bash
python -c "import base64,secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
```

Use one output for `LEADHUNTER_MASTER_KEY_BASE64`, run the command again, and use the
second output for `LEADHUNTER_SUPPRESSION_HMAC_KEY_BASE64`.

Generate the JWT signing pair:

```bash
openssl genpkey -algorithm ED25519 -out secrets/jwt_private.pem
openssl pkey -in secrets/jwt_private.pem -pubout -out secrets/jwt_public.pem
```

On Linux, the containers run as UID/GID `10001:10001`. Preserve least privilege while
making the bind-mounted keys readable:

```bash
chmod 0400 secrets/jwt_private.pem
chmod 0444 secrets/jwt_public.pem
sudo chown 10001:10001 secrets/jwt_private.pem secrets/jwt_public.pem
```

> [!WARNING]
> Never commit `.env`, PEM files, provider credentials, customer data, or the private
> prompt implementation. They are excluded by `.gitignore`, but operators remain
> responsible for secret handling and rotation.

### 3. Validate and start the stack

```bash
docker compose config --quiet
docker compose build api
docker compose up -d --wait
docker compose ps
```

Check the API:

```bash
curl http://127.0.0.1:8000/health/live
```

PowerShell equivalent:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health/live
```

Expected response:

```json
{"status":"ok"}
```

Interactive API documentation is available at <http://127.0.0.1:8000/docs>.

### 4. Bootstrap the first administrator and workspace

Set all `LEADHUNTER_BOOTSTRAP_*` values in `.env`, then run the one-time bootstrap.
Replace `YOUR_ADMIN_PASSWORD` with the URL-encoded value of `POSTGRES_ADMIN_PASSWORD`:

```bash
docker compose run --rm --env-from-file .env \
  -e DATABASE_MIGRATION_URL="postgresql+psycopg://postgres:YOUR_ADMIN_PASSWORD@postgres:5432/leadhunter" \
  api python -m src.cli.bootstrap
```

Remove bootstrap credentials from the operational environment after the command succeeds.
Running the command again with the same identity is rejected rather than silently creating
an inconsistent platform state.

### 5. Operate and stop the stack

```bash
docker compose logs -f api worker retention-scheduler
docker compose stop
```

To remove containers and local database/Redis volumes:

```bash
docker compose down --volumes --remove-orphans
```

> [!CAUTION]
> `--volumes` permanently deletes the local PostgreSQL and Redis data volumes. Do not use
> it against an environment containing data you need to retain.

## Local CLI and GUI setup

### Install the locked environment

```bash
uv lock --check
uv sync --frozen --group test --no-install-project
uv run playwright install chromium
```

Create `.env` as described above. The direct pipeline reads:

- `GOOGLE_API_KEY` for both operating modes;
- `OPENROUTER_API_KEY` for `with_website` and URL diagnostics;
- model and endpoint overrides when explicitly configured.

### Install the private prompt provider

LLM-backed operations load `src.prompts` at runtime. The file is intentionally absent
from public version control and must provide this contract:

```python
SYSTEM_NO_WEBSITE: str
SYSTEM_WEBSITE_AUDIT: str
SYSTEM_PAGE_CLEAN: str

def build_no_website_prompt(business_name, category, competitor, review_text): ...
def build_website_audit_prompt(business_name, category, rating, review_count, pages_content): ...
def build_page_clean_prompt(page_url, label, content): ...
```

Keep the implementation in the protected core distribution or mount it into the runtime.
Do not commit proprietary prompt content to this repository.

## Configuration reference

### Direct pipeline

| Variable | Required | Purpose |
|---|---:|---|
| `GOOGLE_API_KEY` | Yes | Google Places V1 and geocoding access |
| `OPENROUTER_API_KEY` | Website mode | LLM page cleaning and final audit |
| `LLM_MODEL` | No | Final audit model |
| `LLM_MODEL_FREE` | No | Lower-cost page preprocessing model |
| `TOKEN_MODE` | No | `high_fidelity` or `optimized` |
| `GOOGLE_PLACES_V1_URL` | No | HTTPS-only provider endpoint override |
| `GOOGLE_GEOCODING_URL` | No | HTTPS-only geocoding endpoint override |
| `OPENROUTER_BASE_URL` | No | HTTPS-only OpenRouter-compatible endpoint |
| `IP_GEOLOCATION_URL` | No | Opt-in GUI geolocation provider; HTTPS only |

### Server runtime

| Variable | Required | Purpose |
|---|---:|---|
| `LEADHUNTER_DATABASE_URL` | Yes | PostgreSQL URL using the application or worker role |
| `LEADHUNTER_REDIS_URL` | Yes | Redis broker and rate-limit backend |
| `LEADHUNTER_MASTER_KEY_BASE64` | Yes | 32-byte key for credential encryption |
| `LEADHUNTER_SUPPRESSION_HMAC_KEY_BASE64` | Yes | Independent 32-byte suppression key |
| `LEADHUNTER_JWT_PRIVATE_KEY_FILE` | Yes | Ed25519 private signing key path |
| `LEADHUNTER_JWT_PUBLIC_KEY_FILE` | Yes | Ed25519 public verification key path |
| `POSTGRES_ADMIN_PASSWORD` | Docker | Database owner/bootstrap password |
| `LEADHUNTER_APP_DB_PASSWORD` | Docker | Least-privilege API role password |
| `LEADHUNTER_WORKER_DB_PASSWORD` | Docker | Least-privilege worker role password |
| `LEADHUNTER_RETENTION_SCHEDULE_SECONDS` | No | Retention scan interval; default `3600` |

Use a managed secret store in production. `.env` is suitable only for controlled local
development.

## Operations manual

### Show all CLI options

```bash
uv run python main.py --help
uv run python main.py --examples
```

### Discover businesses without websites

```bash
uv run python main.py \
  --mode no_website \
  --lat 45.4642 \
  --lng 9.1900 \
  --keywords restaurant dentist
```

This mode intentionally prints transient, attributed results and does not export Google
Places data.

### Crawl and audit businesses with websites

```bash
uv run python main.py \
  --mode with_website \
  --lat 45.4642 \
  --lng 9.1900 \
  --keywords restaurant dentist \
  --min-age 3 \
  --max-pages 4 \
  --token-mode high_fidelity \
  --out outputs/milan-leads.xlsx
```

Only auditable, evidence-backed leads reach the XLSX exporter.

### Start the internal Streamlit console

```bash
uv run python main.py --gui
```

### Diagnose a single URL

```bash
uv run python main.py --test-url https://example.com --max-pages 3
```

Sensitive HTML/text artifacts are not saved by default. Enable them only for a controlled
debugging session:

```bash
uv run python main.py \
  --test-url https://example.com \
  --save-diagnostic-artifacts \
  --diagnostic-retention-hours 4
```

### API operations

The server exposes routes for:

- login, refresh, logout, and MFA enrollment/confirmation;
- workspace-scoped job creation and status;
- usage-budget reads and overrides;
- encrypted provider-secret management;
- workspace privacy policies and suppression;
- data-subject access, rectification, erasure, and objection workflows.

Use the OpenAPI interface at `/docs` for the current request/response schemas. Protected
routes require a bearer access token; workspace permissions and MFA requirements are
enforced server-side.

## Testing

The commands below are the supported ways to test the project. The GitHub workflows in
`.github/workflows/` remain the authoritative release gates.

### Fast developer test loop

```bash
uv lock --check
uv sync --frozen --group test --no-install-project
uv run --frozen --group test python -m compileall -q src tests main.py
uv run --frozen --group test python -m unittest discover -s tests -v
```

PostgreSQL-only tests are skipped unless their three database URLs are configured. CI sets
`REQUIRE_POSTGRES_TESTS=1`, which turns a missing database into a hard failure.

### Run a focused test module

```bash
uv run --frozen --group test python -m unittest tests.test_url_policy -v
uv run --frozen --group test python -m unittest tests.test_crawler_network_guard -v
uv run --frozen --group test python -m unittest tests.test_untrusted_content -v
uv run --frozen --group test python -m unittest tests.test_spreadsheet_security -v
uv run --frozen --group test python -m unittest tests.test_authentication -v
```

### PostgreSQL 17 integration tests

Start the database and apply migrations:

```bash
docker compose build api
docker compose up -d --wait postgres redis
docker compose run --rm migrate alembic upgrade head
```

Run the integration suite inside the application image. Replace the three password
placeholders with the corresponding values from `.env`:

```bash
docker compose run --rm --no-deps \
  -v ./tests:/app/tests:ro \
  -e REQUIRE_POSTGRES_TESTS=1 \
  -e TEST_DATABASE_OWNER_URL="postgresql+psycopg://postgres:ADMIN_PASSWORD@postgres:5432/leadhunter" \
  -e TEST_DATABASE_APP_URL="postgresql+psycopg://leadhunter_app:APP_PASSWORD@postgres:5432/leadhunter" \
  -e TEST_DATABASE_WORKER_URL="postgresql+psycopg://leadhunter_worker:WORKER_PASSWORD@postgres:5432/leadhunter" \
  migrate python -m unittest discover -s tests/integration -t . -v
```

This suite verifies budget concurrency, fail-closed RLS, workspace isolation, retention,
and runtime-role restrictions.

### Reproduce the container release gate

The following sequence mirrors the important CI container checks:

```bash
docker compose config --quiet
docker compose build api
docker compose up -d --wait postgres redis

docker compose exec -T postgres psql \
  -U postgres -d leadhunter -v ON_ERROR_STOP=1 \
  -tAc "SELECT string_agg(rolname, ',' ORDER BY rolname) FROM pg_roles WHERE rolname IN ('leadhunter_app','leadhunter_worker');"

docker compose run --rm migrate alembic upgrade head
docker compose run --rm migrate alembic downgrade base
docker compose run --rm migrate alembic upgrade head
docker compose up -d --wait api
curl http://127.0.0.1:8000/health/live
```

Always clean up the disposable test stack when finished:

```bash
docker compose down --volumes --remove-orphans
```

### Secret scanning

```bash
uvx pre-commit install
uvx pre-commit run --all-files
```

CI additionally runs Gitleaks against the complete reachable Git history.

### SBOM, vulnerability, and license checks

Install the locked audit tools:

```bash
uv sync --frozen --no-default-groups --group audit --no-install-project
```

Linux/macOS:

```bash
mkdir -p test_output/supply-chain
```

PowerShell:

```powershell
New-Item -ItemType Directory -Force test_output/supply-chain | Out-Null
```

Generate and validate the evidence:

```bash
uv export --frozen --no-default-groups --no-emit-project \
  --format requirements.txt \
  --output-file test_output/supply-chain/runtime-requirements.txt

uv export --frozen --no-default-groups --no-emit-project \
  --format cyclonedx1.5 \
  --output-file test_output/supply-chain/sbom.cdx.json

uv run --frozen --no-default-groups --group audit pip-audit \
  --requirement test_output/supply-chain/runtime-requirements.txt \
  --require-hashes --disable-pip --strict --progress-spinner off \
  --format json \
  --output test_output/supply-chain/vulnerabilities.json

uv run --frozen --no-default-groups --group audit pip-licenses \
  --format json \
  --output-file test_output/supply-chain/environment-licenses.json

uv run --frozen --no-default-groups --group audit python scripts/check_licenses.py \
  --inventory test_output/supply-chain/environment-licenses.json \
  --sbom test_output/supply-chain/sbom.cdx.json \
  --policy .github/license-policy.json \
  --report test_output/supply-chain/license-policy-report.json
```

## Troubleshooting

### Docker engine is unavailable

Start Docker Desktop and verify:

```bash
docker version
docker compose version
```

### API exits with `PermissionError` for `/run/secrets/jwt_private.pem`

On Linux, make the key readable by the non-root runtime UID without making the private key
world-readable:

```bash
sudo chown 10001:10001 secrets/jwt_private.pem secrets/jwt_public.pem
chmod 0400 secrets/jwt_private.pem
chmod 0444 secrets/jwt_public.pem
docker compose up -d --force-recreate api worker retention-scheduler
```

### `PromptProviderUnavailable`

Install or mount the private `src.prompts` implementation and verify every constant and
function in the prompt contract above. Unit tests do not require the private prompt bundle;
live LLM operations do.

### PostgreSQL integration tests are skipped

Configure `TEST_DATABASE_OWNER_URL`, `TEST_DATABASE_APP_URL`, and
`TEST_DATABASE_WORKER_URL`. Set `REQUIRE_POSTGRES_TESTS=1` when a skip must fail the run.

### Containers are unhealthy

```bash
docker compose ps
docker compose logs --no-color postgres redis migrate api worker retention-scheduler
```

### PostgreSQL roles are missing

Use a new disposable volume or run `docker/postgres/init.sh` as the database owner. The
initialization script only runs automatically when PostgreSQL creates a fresh data volume.

### Browser installation is incomplete

```bash
uv run playwright install chromium
```

On Linux CI images, Playwright may additionally require system dependencies supported by
the selected base image.

## Project structure

```text
lead-hunter-ai/
├── .github/workflows/       # CI and security release gates
├── docker/postgres/         # Least-privilege PostgreSQL role bootstrap
├── docs/                    # Product audit and release policy
├── graphify-out/            # Portable architecture knowledge graph
├── migrations/              # Alembic schema and RLS migrations
├── scripts/                 # License-policy validation
├── src/
│   ├── application/         # Use cases and policy orchestration
│   ├── cli/                 # One-time platform bootstrap
│   ├── domain/              # Entities, value objects, and invariants
│   ├── infrastructure/      # PostgreSQL, Redis, crypto, persistence models
│   ├── providers/           # External discovery adapters
│   ├── security/            # URL, privacy, content, and presentation guards
│   ├── web/                 # FastAPI routes, schemas, and dependencies
│   ├── workers/             # Dramatiq jobs and retention scheduler
│   ├── crawler.py           # Guarded Crawl4AI integration
│   ├── auditor.py           # LLM audit orchestration
│   ├── exporter.py          # Protected XLSX output
│   ├── gui.py               # Internal Streamlit console
│   ├── prompting.py         # Public contract for private prompts
│   └── server.py            # Production API composition root
├── tests/                   # Unit, contract, security, and integration tests
├── compose.yml              # PostgreSQL, Redis, API, workers, and migrations
├── Dockerfile               # Non-root, lockfile-based runtime image
├── main.py                  # Direct CLI and GUI entry point
├── pyproject.toml           # Project and dependency policy
└── uv.lock                  # Reproducible dependency lock
```

## Roadmap

The P0 structural security and governance work is substantially complete. The next work is
ordered by commercial risk and architectural leverage:

1. **Connect the commercial pipeline to the server worker.** Add supported job handlers,
   phase checkpoints, cooperative cancellation, resume, and an explicit dead-letter queue.
2. **Fix remaining functional correctness issues.** Complete domain-age behavior,
   e-commerce and franchise filtering, token-mode behavior, framework/CMS detection,
   category/location normalization, and edge-case CLI validation.
3. **Make audit quality measurable.** Add cited findings, report/evidence versioning, a
   real-site gold set, score calibration, browser end-to-end tests, coverage reporting, and
   regression benchmarks.
4. **Harden crawler operations.** Add robots/policy governance, per-domain budgets,
   browser resource limits, proxy/egress controls, and stronger retry/circuit-breaker policy.
5. **Build the customer product surface.** Replace Streamlit as the customer UI, then add
   report review/editing, white-label output, SSO, billing, and customer administration.
6. **Add production operations.** Structured observability, SLOs, alerting, backup/restore,
   disaster recovery, capacity planning, and incident runbooks.
7. **Complete the trusted release chain.** Sign images, generate provenance attestations,
   publish signed update manifests, rehearse rollback, and retain release evidence.
8. **Close commercial and legal gates.** Review Google Maps Platform terms, GDPR and
   outreach obligations, LGPL/MPL distribution duties, DPAs, subprocessors, and data
   residency before customer deployment.

The intentionally deferred local credential rotation described in the audit remains an
operator decision; no credential is embedded in the repository history examined by CI.

## Development workflow

The repository uses `develop` as the integration branch.

1. Create a focused branch from an up-to-date `develop`.
2. Keep commits small, thematic, and independently reviewable.
3. Update tests and documentation with behavior changes.
4. Open a pull request targeting `develop`.
5. Merge only after every required CI and Security check is green.
6. Delete the completed remote branch.

Before opening a pull request:

```bash
uv lock --check
uv run --frozen --group test python -m unittest discover -s tests -v
uvx pre-commit run --all-files
docker compose config --quiet
```

Dependency changes must update `pyproject.toml` and `uv.lock` together.

## Security reporting

Do not open a public issue containing credentials, personal data, or exploitable details.
Follow [`SECURITY.md`](SECURITY.md) and use GitHub private security advisories for sensitive
reports.

## License

`pyproject.toml` declares `LicenseRef-Proprietary`. This repository does **not** grant an
MIT or other open-source license. All rights are reserved unless a separate written license
agreement says otherwise. Contact the repository owner for evaluation, source-code, server,
or report-service commercial terms.

---

<p align="center">
  Built and maintained by <a href="https://github.com/Marcelluxx">Marcelluxx</a>.
</p>
