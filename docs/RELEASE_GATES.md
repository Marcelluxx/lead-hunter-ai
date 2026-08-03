# Release gates

A Lead Hunter release candidate is acceptable only when every required GitHub
check succeeds on the exact commit being released.

## Required pull-request checks

- Python 3.10, 3.11, 3.12 and 3.13 tests from the committed `uv.lock`;
- mandatory PostgreSQL 17 concurrency, RLS, retention and suppression tests;
- container build from digest-pinned base images;
- clean-database bootstrap of the least-privilege application and worker roles;
- PostgreSQL migration round trip (`upgrade`, `downgrade`, `upgrade`);
- API startup and `/health/live` smoke check;
- full-history Gitleaks scan;
- dependency vulnerability and license policy checks;
- CycloneDX SBOM generation.

## Release invariants

- `pyproject.toml` and `uv.lock` change together;
- a release is built from a clean, tagged commit;
- secrets and customer data are never embedded in the image or artifacts;
- the image digest and SBOM are retained with the release record;
- migrations are tested against a clean database before publishing;
- rollback is rehearsed against the previous supported release before the first
  commercial distribution.

Image signing, provenance attestation, update manifests and automated rollback
remain later commercial-release gates. Until those controls exist, CI produces
verified development images rather than customer release artifacts.
