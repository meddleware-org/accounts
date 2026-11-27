# Changelog

All notable changes to `accounts` are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); until the platform's mainnet launch every release is a
patch bump, breaking changes included.

## [Unreleased]

## [0.0.1] - 2026-11-27

### Added
- The image: Keycloak 26.8.2 (pinned by digest) with `kc.sh build --db=postgres --health-enabled --metrics-enabled`, started with `--optimized` on a read-only root filesystem.
- `realm/apply.py`: the realm as code (passkey-only browser flow with the bootstrap path, `acr` `phr`), clients from `realm/clients/*.json`, `--operator` and `--finish`.
- `tests/smoke.sh`, the CI workflow (realm checks, smoke, Trivy) and the release workflow (quay.io and Docker Hub, cosign, SBOM, provenance, private registry mirror).
