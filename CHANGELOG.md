# Changelog

All notable changes to `accounts` are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); until the platform's mainnet launch every release is a
patch bump, breaking changes included.

## [Unreleased]

### Changed
- The realm sets `ResidentKey: required` instead of the deprecated `RequireResidentKey`, and `AvoidSameAuthenticatorRegister` (the same physical key cannot be enrolled twice).

## [Unreleased]

### Added
- `realm/clients/registry-{ci-push,node-pull,browser}.json`: the registry's three identities as Keycloak clients (ADR-0016 stage 4). `realm/apply.py --status` prints a user's credential types and bootstrap state.

## [0.0.2] - 2026-11-27

### Added
- `.trivyignore`: one reviewed, expiring exception (Guava CVE-2026-102554 in upstream Keycloak: not reachable, it needs Java deserialization of untrusted bytes), wired into the CI and release scans. `v0.0.1` was never published because that scan failed.

## [0.0.1] - 2026-11-27

### Added
- The image: Keycloak 26.8.2 (pinned by digest) with `kc.sh build --db=postgres --health-enabled --metrics-enabled`, started with `--optimized` on a read-only root filesystem.
- `realm/apply.py`: the realm as code (passkey-only browser flow with the bootstrap path, `acr` `phr`), clients from `realm/clients/*.json`, `--operator` and `--finish`.
- `tests/smoke.sh`, the CI workflow (realm checks, smoke, Trivy) and the release workflow (quay.io and Docker Hub, cosign, SBOM, provenance, private registry mirror).
