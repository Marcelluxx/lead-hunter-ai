# Feature-license operations

The licensing core is implemented for local installations and managed servers.
Additional accesses expire; base functions remain usable. Export without a
website, rating/review filters, and full diagnostics are still planned modules.
A license authorizes a feature but cannot make an unavailable module execute.
Provider-data, export, privacy, budget, and SSRF policies still apply.

## Owner: create separate encrypted signing keys

Run in the owner's source checkout; the customer image excludes this tool.
Create the ignored directory first. Keep an external encrypted backup of the
private key and its passphrase. Commands never overwrite existing key files.

```powershell
New-Item -ItemType Directory -Force .secrets
uv run --frozen python -m tools.license_issuer keygen --private-out .secrets/license-private.pem --public-out .secrets/license-public.pem
```

The passphrase is requested twice interactively. Do not place it in arguments or
environment variables. Do not reuse the login JWT key pair.

## Configure public trust

Distribute only a trust JSON file and public key material, using an administrative
channel independent of the license import. File schema:

```json
{
  "version": 1,
  "issuer": "lead-hunter-owner",
  "keys": {
    "owner-2026": "<complete public Ed25519 PEM, with JSON-escaped newlines>"
  }
}
```

Generate the file from the public PEM (PowerShell):

```powershell
@{version=1; issuer='lead-hunter-owner'; keys=@{'owner-2026'=(Get-Content -Raw .secrets/license-public.pem)}} | ConvertTo-Json -Depth 3 | Set-Content -Encoding utf8 .secrets/license-trust.json
$env:LEADHUNTER_LICENSE_TRUST_FILE=(Resolve-Path .secrets/license-trust.json).Path
$env:LEADHUNTER_LICENSE_STATE_DIR='.leadhunter-state'
```

Use UTF-8 without a BOM when generating JSON with Windows PowerShell 5.
Supported trust files reject duplicates, unknown fields and private-key PEMs.
For rotation, distribute a new public `kid` before issuing with it. Retain the
previous public key until its grants expire or intentionally disable it.
An import cannot add trusted keys.

## Local activation and lifecycle

```powershell
uv run --frozen python -m src.cli.feature_licenses installation-id
uv run --frozen python -m src.cli.feature_licenses status
uv run --frozen python -m src.cli.feature_licenses import .secrets/customer.lh
uv run --frozen python -m src.cli.feature_licenses revoke 00000000-0000-0000-0000-000000000005
```

The local identity is generated once in the configured state directory. Back up
the complete directory, including identity, revocations and time high-watermark.
Restore it to preserve the identity. A fresh directory creates a new installation
requiring a new grant. Do not put state in output/test-output folders. Protect the
directory using the operating-system account permissions.

The console's **Licenze e funzioni riservate** panel displays identity, grant
status, expiry (Europe/Rome) and module availability, and imports license files.
Both `python main.py --gui` and direct Streamlit launches bind to loopback.
Local access is shared by people using the same OS account; use the authenticated
server for access by distinct remote users.

## Owner: issue and inspect

Obtain the actual destination UUID first. These UUIDs are fictitious examples;
replace them and select dates in the future with an explicit UTC offset.
The start must be at or after issuance, and expiry must be after the start.
Future-start grants can be imported once their start is reached.

```powershell
uv run --frozen python -m tools.license_issuer issue --private-key .secrets/license-private.pem --kid owner-2026 --issuer lead-hunter-owner --installation-id 00000000-0000-0000-0000-000000000001 --subject-kind installation --subject-id 00000000-0000-0000-0000-000000000001 --feature diagnostics.full --feature discovery.rating_filters --feature export.no_website --not-before 2026-11-01T00:00:00+01:00 --expires-at 2026-12-01T00:00:00+01:00 --out .secrets/customer.lh
uv run --frozen python -m tools.license_issuer inspect --license-file .secrets/customer.lh --public-key .secrets/license-public.pem --kid owner-2026 --issuer lead-hunter-owner --installation-id 00000000-0000-0000-0000-000000000001 --subject-kind installation --subject-id 00000000-0000-0000-0000-000000000001
```

For a managed-server grant use `--subject-kind workspace_user`,
`--subject-id USER_UUID`, `--workspace-id WORKSPACE_UUID` and the stable deployment
UUID. Inspection verifies signature and recipient, reports expired grants safely,
and never prints the token. Output files are created exclusively.

## Managed server

Apply Alembic migration `0004_feature_licenses`. Configure one stable
`LEADHUNTER_INSTALLATION_ID` UUID shared by API and worker, and set
`LEADHUNTER_LICENSE_TRUST_FILE=/run/secrets/license-trust.json` for Compose
(place the public trust JSON in the mounted `secrets/` directory).
`LEADHUNTER_LICENSE_ISSUER` defaults to `lead-hunter-owner`.
Never mount the licensing private key. The runtime's separate JWT key files
remain necessary for login.

With the existing Bearer authentication:

| Method/path | Requirement |
|---|---|
| GET /workspaces/{workspace}/features | Active member, own status |
| PUT /workspaces/{workspace}/feature-licenses/{user} body {"token":"..."} | Admin with MANAGE_WORKSPACE and MFA; existing active member target |
| GET /workspaces/{workspace}/feature-licenses/{user} | Own status, or admin with MFA for another user |
| DELETE /workspaces/{workspace}/feature-licenses/{user}/{license} | Admin with MFA; idempotent revocation |

Grant responses contain verified metadata and ISO UTC dates, never the token.
The app DB role manages grants in the current workspace; worker has SELECT only.
Both roles advance the persisted clock only through a restricted monotonic
function. A local installation grant cannot unlock all server accounts.
Admin privileges permit management of signed grants, not their creation.
Without server trust configured, feature status remains missing and the
single-grant management endpoints return 503; health/login/base work normally.

## Expiry, renewal, clock and offline limits

Validity is `not_before <= now < expires_at`, with no grace after expiry.
Each protected step and sensitive delivery requires a fresh verification.
An already-started provider call may finish; delivering reserved material still
requires current authorization. Stored data and files already downloaded are
not deleted or recalled.

Renew by importing a newly signed, currently valid grant. It replaces all
previous features atomically; grants are never unioned. Invalid renewal preserves
the current grant. Replacement revokes the old grant permanently, and the same
active grant can be reimported idempotently. Revoked IDs cannot be reactivated.

A rollback of the system clock by more than 300 seconds from the persisted
maximum denies protected access (`license_clock_regression`). Smaller rollbacks
use that maximum. Correct the UTC system time to at least the stored maximum;
do not reset state to extend a grant. API/worker share the PostgreSQL high-watermark,
committed independently of the request transaction.

Offline installations can verify valid signed grants without a central service,
but cannot receive immediate remote revocation. Local/admin intervention applies
revocation; online revocation service and billing remain later milestones.
An OS administrator can modify the program or restore snapshots: offline
signatures and clock checks do not promise absolute tamper resistance.

Storage corruption/unwritable state fails closed for additional functions with
`license_storage_unavailable`. Repair from a trusted complete backup and preserve
the identity and revocations. Do not silently regenerate identity during recovery.
