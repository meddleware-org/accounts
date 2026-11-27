# Changelog

All notable changes to `accounts` are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); until the platform's mainnet launch every release is a
patch bump, breaking changes included.

## [Unreleased]

### Added
- Clients `content-hub-console` and `link-in-bio-console` for the two operator consoles' sign-in (ADR-0016 stage 6): confidential, authorization code with PKCE `S256`, `default.acr.values` `phr`, an exact redirect URI on the console's own host, and a back-channel logout URL inside the cluster. Their secrets come from `${CONTENT_HUB_CONSOLE_SECRET}` and `${LINK_IN_BIO_CONSOLE_SECRET}`.

## [0.0.5] - 2026-11-27

### Changed
- **No username on the sign-in page (OWASP: a valid and an invalid credential look alike).** The realm's browser flow is now `passkey-first`: the key page opens the browser's key prompt by itself and the key (a resident credential) says who is signing in, so there is no username to be told is wrong. A first enrolment or break-glass uses the one-time-password page, reached only through the new client `bootstrap` (its own flow, `one-time-password`): one page with username and password, so a wrong username and a wrong password give the same message. `realm/apply.py --operator` prints the link; `realm/apply.py` rebuilds both flows on every run and resolves a client's `authenticationFlowBindingOverrides` written as `@<flow alias>`.
- The theme's stylesheet and script URLs carry `?v=<themeVersion>`: Keycloak's resource paths do not change when a theme changes and its static files are cached for 30 days, so a browser kept the previous release's CSS and JS beside the new templates (the colour switch appeared unstyled and inert). `themeVersion` must equal the newest released version (`tests/smoke.sh` checks).
- The colour-scheme switch is restyled as three pill-shaped choices.

### Removed
- The username page and the separate password page (replaced by the key page and the one-time-password page).

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
