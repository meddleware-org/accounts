# accounts

The Meddleware identity provider, as an image and a realm as code: upstream [Keycloak](https://www.keycloak.org) with its build-time options baked in, and the script that gives
it the platform's realm. It is the provider behind [Meddleware](https://meddleware.co.uk)'s sign-in for operators (the content hub, the Link in Bio console, Grafana, the container
registry) and for machines (the access-gate Worker). Services do not talk to Keycloak in a Keycloak-specific way: they follow the platform's
[identity contract](https://github.com/meddleware-org/identity-contract), so another provider that passes its conformance suite can replace this one.

## What is here

| Path | What it is |
| --- | --- |
| `Dockerfile` | Upstream Keycloak pinned by digest, then `kc.sh build --db=postgres --health-enabled --metrics-enabled`. The result starts with `start --optimized` on a **read-only root filesystem**. |
| `realm/apply.py` | Realm as code through Keycloak's admin REST API (idempotent): the realm, the passkey-only browser flow, the clients in `realm/clients/*.json`, and the operator (`--operator`, `--finish`). |
| `realm/clients/` | One Keycloak client representation per file (`"@<flow alias>"` in `authenticationFlowBindingOverrides` is resolved to the flow's id); `${NAME}` is replaced from the environment so secrets and public keys never sit in git. Today: the three registry identities (`registry-ci-push`, `registry-node-pull`, `registry-browser`: service accounts with a client secret, because `docker login` can only send a user name and a password; their tokens live 60 s and are never used, the token service only checks that the grant succeeds). `grafana` (stage 5) and the two operator consoles `content-hub-console` and `link-in-bio-console` (stage 6: confidential, code flow with PKCE, `acr` `phr`, back-channel logout to the console inside the cluster) are there too; the Worker adds its own in stage 7. |
| `theme/meddleware/login/` | The login theme: page templates (username, password, key sign-in, key registration, errors, sign-out), `css/login.css` on `css/tokens.css` (vendored from `@meddleware/design-tokens`), `js/webauthn.js`, `js/theme-init.js`. |
| `tests/theme.sh` | Builds the image, applies the realm, and walks every sign-in page in a browser (virtual key): axe, Content-Security-Policy, storage, cookies; screenshots to `$OUT/shots`. |
| `tests/smoke.sh` | Builds the image, starts it against a throw-away PostgreSQL, applies the realm twice, checks discovery, the flow, a client and the operator state. |

## How sign-in works

- **Passkey only.** Operators sign in with a security key that verifies the user (WebAuthn passwordless, user verification required, a resident credential). There is no password and no email step.
  A successful sign-in has `acr` = `phr` (LoA 2), which is what the consoles require.
- **Enrolment and break-glass are one path, through its own client.** WebAuthn cannot enrol the first key, so a user with the attribute `bootstrap=true` signs in with a one-time password and then registers a key. That page is reached only
  through the client `bootstrap` (a flow-binding override to the flow `one-time-password`): `realm/apply.py --operator NAME` prints the link and the password (once), and a wrong username and a wrong password give the same message. After
  enrolment, `realm/apply.py --finish NAME` deletes the password and the marker; a user without the marker is refused on that page even with a password. If the key is lost, `--operator NAME` deletes the lost credentials and arms the path again.
  An extra key for someone who already has one: `realm/apply.py --add-key NAME`, then they sign in at any application with the key they have. Keycloak's own account console is **disabled** (it cannot run under the strict policy below).
- **No username, and nothing to click.** The sign-in page is the key page: it opens the browser's key prompt by itself and the key (a resident credential) says who is signing in. So there is no username to be told is wrong (OWASP: a valid and an invalid credential look alike). If the browser needs a click first (Safari) or the prompt is cancelled, the page says so in a live region and the button tries again (no error page).
- **A colour-scheme switch** (System, Light, Dark; native radio buttons in the footer). System, the default, follows the device. A choice lasts for the tab (`sessionStorage`, key `mw-color-mode`, written only when Light or Dark is picked) so it survives the pages of one sign-in; nothing is stored for a person who never uses it (storage ledger B15).
- **A strict Content-Security-Policy and a login theme.** `theme/meddleware/login` (templates, one stylesheet on the platform's design tokens, two small scripts, no font, no image, no inline script or style) is the realm's login theme;
  the realm sends `default-src 'none'; script-src 'self'; style-src 'self'; ...`. `tests/theme.sh` walks every page with a virtual key: axe (light and dark), no policy violation, nothing stored.
- **Machines** use a client with `private_key_jwt` (ES256) and DPoP-bound RFC 9068 access tokens; see the contract.

The full results of the spike that settled these choices are in the Meddleware workspace repository (ADR-0016, "Spike results").

## Run it

```bash
docker build -t accounts .
docker run --read-only --cap-drop ALL --tmpfs /tmp --tmpfs /opt/keycloak/data:rw,mode=1777 \
  -e KC_DB=postgres -e KC_DB_URL=jdbc:postgresql://HOST:5432/keycloak -e KC_DB_USERNAME=... -e KC_DB_PASSWORD=... \
  -e KC_HTTP_ENABLED=true -e KC_HOSTNAME=https://accounts.example.org -e KC_PROXY_HEADERS=xforwarded \
  -e KC_BOOTSTRAP_ADMIN_USERNAME=admin -e KC_BOOTSTRAP_ADMIN_PASSWORD=... accounts
KC_URL=https://accounts.example.org KC_ADMIN=admin KC_ADMIN_PW=... python3 realm/apply.py --operator me
```

Use `sslmode=verify-full` (and `sslrootcert`) in the database URL for any database that is not on the same host. Port 9000 is the management port (`/health/ready`, `/metrics`): keep it off the
public Ingress.

## Configuration

| Variable | Used by | Meaning |
| --- | --- | --- |
| `KC_*` | the image | Keycloak's runtime options (database, hostname, proxy headers, bootstrap admin). Build-time options are fixed in the `Dockerfile`. |
| `KC_URL`, `KC_ADMIN`, `KC_ADMIN_PW`, `REALM`, `CLIENTS_DIR` | `realm/apply.py` | The server, an admin of the master realm, the realm name (default `meddleware`) and where client files are read. |

## Troubleshooting

- **`Read-only file system` at start:** the image was not built with `kc.sh build` (use this `Dockerfile`), or `/tmp` and `/opt/keycloak/data` are not writable volumes.
- **`apply.py: ... needs the environment variable X`:** a client file references `${X}`; export it (a missing variable stops the run on purpose).
- **The operator cannot sign in with the key:** the sign-in is usernameless, so the key must hold a resident (discoverable) credential for this realm (the realm requires that when a key is registered). If the key page says the key was not used, try again; if it keeps failing, the credential may be missing or not discoverable: run `--operator NAME` (it deletes the old credentials) and enrol again through the printed link.

## Licence

[0BSD](LICENSE). Keycloak itself is Apache-2.0 and is not modified.
