# CLAUDE.md — accounts

The Meddleware identity provider: a Keycloak image (build-time options baked in) and the realm as code. It is deployed in the `auth` namespace of the instance (Meddleware workspace,
`post-bootstrap/_prepared/auth-keycloak`, ADR-0016, stage 2). Services call it only through the identity contract (`identity-contract` repository); nothing in this repository is called by code.

## Layout

- `Dockerfile` — upstream Keycloak by digest, `kc.sh build`, `CMD ["start", "--optimized"]`. No theme yet (FU-0182).
- `realm/apply.py` — idempotent realm as code over the admin REST API; `realm/clients/*.json` — one client each, `${ENV}` substituted.
- `tests/smoke.sh` — build + run read-only + apply twice + checks; `tests/clients/` — its fixtures.
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
- **The passkey flow is the contract's assurance.** Do not add a password or email path to the browser flow; the bootstrap path is for enrolment and break-glass only and closes with `--finish`.
- **No telemetry, no third-party call** from the image or the scripts.
- **Versions:** patch bumps until mainnet (workspace rule); the image tag follows the repository tag.

## Documentation rules (workspace documentation standard, D144)

Every file has a header; every function a doc comment; comments say why. `node scripts/check-docs.mjs --report accounts` in the workspace is the gate. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Gotchas

- Keycloak lists `plain` among its PKCE methods for the whole realm; a client with `pkce.code.challenge.method=S256` still refuses it (the contract asserts the behaviour).
- Keycloak emits no `amr`; the assurance is `acr` = `phr`.
- WebAuthn passwordless cannot enrol the first key: see the bootstrap path in the README.
- The realm uses `ResidentKey: required` (the older `RequireResidentKey` option logged a deprecation warning and is no longer set). The WebAuthn policy also has `AcceptableAaguids` (empty: any authenticator model) and `AuthenticatorAttachment` (`cross-platform`): see docs/auth/OPERATIONS.md in the Meddleware workspace, "More passkeys", before changing either.

## Related

ADR-0016, D148, FU-0182, FU-0194 and `docs/auth/IDP_MIGRATION.md` in the Meddleware workspace repository (private).
