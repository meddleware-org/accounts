# Changelog

All notable changes to `accounts` are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); until the platform's mainnet launch every release is a
patch bump, breaking changes included.

## [Unreleased]

## [0.0.4] - 2026-11-27

### Changed
- Signing in is one press: the key page opens the browser's key prompt by itself as soon as it is shown (the person has just pressed Sign in), and a cancelled prompt, or a browser that needs a click first, is explained in a live region on the page with the button to try again, not sent to the server as an error. The username button reads "Sign in".

### Added
- A colour-scheme switch (System, Light, Dark) in the login pages' footer: native radio buttons; a choice lasts for the tab only (`sessionStorage`, written only when Light or Dark is picked), so a person who never uses it has nothing stored.

## [0.0.3] - 2026-11-27

### Added
- The login theme `meddleware` (`theme/meddleware/login`): every page of the passkey-only sign-in on the platform's design tokens, light and dark by the system setting, with no inline script, style or handler, no font, no image, no storage. The realm sends a strict Content-Security-Policy and uses the theme. `tests/theme.sh` checks every page with axe, for policy violations, storage and cookies.
- `realm/apply.py --add-key NAME`: ask an operator who has a key to register another at their next sign-in.

### Changed
- Keycloak's account console is disabled (it cannot run under the policy); keys are enrolled through the sign-in flow. The key registration page has a real, labelled name field instead of a browser prompt.

### Changed
- The user profile no longer requires first name, last name or email (a user without them was sent to an "update your profile" page at sign-in). `realm/apply.py --grant`, `--set-email` and the `grafana-admin` role; `realm/clients/grafana.json` (stage 5).
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
