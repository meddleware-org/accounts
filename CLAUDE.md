# CLAUDE.md — accounts

The Meddleware identity provider: a Keycloak image (build-time options baked in) and the realm as code. It is deployed in the `auth` namespace of the instance (Meddleware workspace,
`post-bootstrap/_prepared/auth-keycloak`, ADR-0016, stage 2). Services call it only through the identity contract (`identity-contract` repository); nothing in this repository is called by code.

## Layout

- `Dockerfile` — upstream Keycloak by digest, the theme copied in, `kc.sh build`, `CMD ["start", "--optimized"]`.
- `theme/meddleware/login/` — the login theme (extends `base`): `template.ftl` and one template per page, `resources/css/{tokens,login}.css`, `resources/js/{theme-init,webauthn}.js`. Rules: no inline script, style or event handler; no external host; no storage; `tokens.css` is a copy of `@meddleware/design-tokens` `src/tokens.css` (refresh it when the tokens change).
- `realm/apply.py` — idempotent realm as code over the admin REST API; `realm/clients/*.json` — one client each, `${ENV}` substituted.
- `tests/theme.sh` + `tests/theme-check.mjs` — the browser test of the theme (axe, CSP, storage, cookies); `tests/smoke.sh` — build + run read-only + apply twice + checks; `tests/clients/` — its fixtures.
- `.github/workflows/` — `ci.yml` (realm checks, smoke, Trivy) and `docker-publish.yml` (tags `v*`: publish to quay.io and Docker Hub, sign, SBOM, provenance, mirror to the private registry).

## Commands

```bash
python3 -m py_compile realm/apply.py && shellcheck -S warning tests/smoke.sh
bash tests/smoke.sh
```

The browser half (virtual security key: enrol, passkey sign-in, logout, break-glass) and the conformance suite run from the workspace: `k8s/base/auth/tests/keycloak-spike/run.sh`.

## Conventions and hard rules

- **The upstream image is pinned by digest** and moves by Dependabot pull requests; quay.io publishes no cosign signature for it, so the pin and the Trivy scan are the control. After a bump run the workspace spike harness.
- **Read-only root filesystem.** Anything that needs a write at start-up means a build-time option is missing from the `Dockerfile` (`kc.sh build`).
- **No secret in git.** Client files hold `${NAME}`; the values come from the environment (the instance's Secrets). `apply.py` prints the operator's one-time password once and stores it nowhere.
- **The passkey flow is the contract's assurance.** Do not add a password or email path to the applications' browser flow (`passkey-first`); the one-time-password page belongs to the `bootstrap` client only, is for enrolment and break-glass, and closes with `--finish`.
- **Sign-in has no username.** The realm's browser flow `passkey-first` is cookie + the key (usernameless: a resident credential identifies the user); `one-time-password` (username+password on ONE page, generic error, gate that refuses users without the `bootstrap` marker) is bound only to the client `bootstrap`. Never reintroduce a username-only step (it tells a visitor whether an account exists). `ensure_flow` rebuilds both flows each run.
- **Theme files are cache-busted** by `?v=<themeVersion>` (theme.properties; Keycloak's resource URLs do not change with the theme and are cached 30 days): bump `themeVersion` with every release (smoke.sh checks it equals the newest CHANGELOG version).
- **Key sign-in is automatic.** `webauthn.js` starts `navigator.credentials.get()` as soon as the key page loads and on the button; a cancelled or click-needing prompt (`NotAllowedError`/`AbortError`) is shown in the live region `#kc-webauthn-status`, never submitted to the server as an error. Registration always waits for its button (the key is named first).
- **The colour switch stores only on a choice** (`sessionStorage` `mw-color-mode`, this tab; System removes it): the test asserts nothing is stored before a choice, only that key after, nothing after System (storage ledger B15). Do not add another storage write.
- **The realm's Content-Security-Policy is strict** (`realm/apply.py`, `CSP`): a template that needs an inline script or style is a bug in the template. Keycloak's own account console cannot run under it and is disabled; keys are enrolled through the sign-in flow (`--operator`, `--add-key`). Keycloak itself appends one inline `history.replaceState` script to form-post responses, which the policy refuses harmlessly (accepted in the test).
- **No telemetry, no third-party call** from the image or the scripts.
- **Versions:** patch bumps until mainnet (workspace rule); the image tag follows the repository tag.

## Documentation rules (workspace documentation standard, D144)

Every file has a header; every function a doc comment; comments say why. `node scripts/check-docs.mjs --report accounts` in the workspace is the gate. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Gotchas

- Keycloak lists `plain` among its PKCE methods for the whole realm; a client with `pkce.code.challenge.method=S256` still refuses it (the contract asserts the behaviour).
- Keycloak emits no `amr`; the assurance is `acr` = `phr`.
- WebAuthn passwordless cannot enrol the first key: see the bootstrap path in the README. The key sign-in is usernameless, so the credential must be a resident (discoverable) one: the realm requires that at registration (`ResidentKey: required`); a key registered before that policy, or by another realm, would not sign in and is replaced through `--operator`.
- The realm uses `ResidentKey: required` (the older `RequireResidentKey` option logged a deprecation warning and is no longer set). The WebAuthn policy also has `AcceptableAaguids` (empty: any authenticator model) and `AuthenticatorAttachment` (`cross-platform`): see docs/auth/OPERATIONS.md in the Meddleware workspace, "More passkeys", before changing either.

## Related

ADR-0016, D148, FU-0182, FU-0194 and `docs/auth/IDP_MIGRATION.md` in the Meddleware workspace repository (private).
