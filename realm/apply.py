#!/usr/bin/env python3
"""Apply the Meddleware realm to a running Keycloak through its admin REST API (realm as code; ADR-0016, FU-0194).

It is idempotent for the realm, the browser flow and the clients (a client that exists is updated, a missing one is created) and it never deletes
a realm. What it builds:

  * realm `meddleware`: phishing-resistant level `phr` = LoA 2; WebAuthn passwordless policy with a security key (cross-platform attachment), user
    verification required and a resident key; unmanaged user attributes enabled for the admin (the bootstrap marker needs them);
  * browser flow `passkey-browser`: a username, then EITHER the bootstrap path (users with the attribute `bootstrap=true`: a one-time password and
    the register-key required action, used for the first enrolment and for break-glass) OR the passkey path (everyone else: WebAuthn passwordless
    with user verification, reaching level 2);
  * one client per file in `realm/clients/*.json` (a Keycloak ClientRepresentation). `${NAME}` in a file is replaced by the environment variable
    NAME, so secrets and public keys never sit in git; a missing variable stops the run.

The operator user is created by `--operator <username>` (with the bootstrap attribute, a random one-time password printed once to stdout, and the
register-key required action). Re-running it for an existing user resets them to that bootstrap state, which is the break-glass: the lost credential
is deleted first.

    KC_URL=https://accounts.example KC_ADMIN=admin KC_ADMIN_PW=... python3 realm/apply.py [--operator NAME] [--dry-run]

Environment: KC_URL (base URL, default http://localhost:8080), KC_ADMIN and KC_ADMIN_PW (an admin of the master realm), REALM (default meddleware),
CLIENTS_DIR (default realm/clients), plus whatever the client files reference. Exit status: 0 on success, 1 on any failed call or missing variable. No telemetry, no third-party call.
"""
import argparse
import glob
import json
import os
import re
import secrets
import sys
import urllib.error
import urllib.parse
import urllib.request

KC = os.environ.get("KC_URL", "http://localhost:8080").rstrip("/")
REALM = os.environ.get("REALM", "meddleware")
HERE = os.path.dirname(os.path.abspath(__file__))
# Where the client files are read from (CLIENTS_DIR overrides it, for the smoke test's fixtures).
CLIENTS = os.environ.get("CLIENTS_DIR", os.path.join(HERE, "clients"))
# The admin token, fetched on first use.
_TOKEN = None


def die(message):
    """Print an error to standard error and stop with status 1."""
    sys.exit(f"apply.py: {message}")


def admin_token():
    """Return an admin access token for the master realm, using the bootstrap or a named admin."""
    body = urllib.parse.urlencode({"grant_type": "password", "client_id": "admin-cli", "username": os.environ["KC_ADMIN"], "password": os.environ["KC_ADMIN_PW"]}).encode()
    with urllib.request.urlopen(urllib.request.Request(KC + "/realms/master/protocol/openid-connect/token", body), timeout=30) as r:
        return json.load(r)["access_token"]


def api(method, path, body=None, allow=()):
    """One admin REST call; return the decoded JSON (or None). HTTP statuses in `allow` return None instead of stopping the run."""
    # The token is fetched once and reused for every call of the run (a run is short, well inside the token's lifetime).
    global _TOKEN
    _TOKEN = _TOKEN or admin_token()
    # A body is sent as JSON; a call with none (GET, DELETE) sends no data.
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(KC + "/admin" + path, method=method, data=data, headers={"Authorization": "Bearer " + _TOKEN, "Content-Type": "application/json"})
    try:
        # A timeout on every call: a hung Keycloak must stop the run, not hang it.
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        # The caller named the statuses it expects (a 404 while probing for the realm); anything else is a failure.
        if e.code in allow:
            return None
        die(f"{method} {path}: HTTP {e.code}")


def r(path):
    """The realm-relative admin path."""
    return f"/realms/{REALM}{path}"


def execution(flow, name, requirement, index=0):
    """Set the requirement of the index-th execution of `flow` whose display name, alias or provider id is `name`."""
    # An authenticator can appear more than once in a flow, so `index` picks which one; `seen` counts the matches so far.
    seen = 0
    for e in api("GET", r(f"/authentication/flows/{flow}/executions")):
        if name in (e.get("displayName"), e.get("alias"), e.get("providerId")):
            if seen == index:
                e["requirement"] = requirement
                api("PUT", r(f"/authentication/flows/{flow}/executions"), e)
                return
            seen += 1
    die(f"no execution {name} in {flow}")


def configure(flow, provider, alias, config):
    """Attach a configuration to the first execution of `flow` with the given provider id."""
    # The execution to configure: the first one in the flow with this provider id.
    e = [x for x in api("GET", r(f"/authentication/flows/{flow}/executions")) if x.get("providerId") == provider][0]
    api("POST", r(f"/authentication/executions/{e['id']}/config"), {"alias": alias, "config": config})


def ensure_realm():
    """Create the realm when it does not exist, then set the settings that make it the Meddleware realm."""
    # The settings this script owns; everything else in the realm is left as it is.
    settings = {
        "realm": REALM, "enabled": True, "sslRequired": "external",
        # `phr` is the platform's phishing-resistant level: LoA 2, reached only through the passkey path of the flow below.
        "attributes": {"acr.loa.map": json.dumps({"phr": "2"})},
        # A security key (roaming authenticator) with user verification and a resident credential (ADR-0016 Q3).
        "webAuthnPolicyPasswordlessAuthenticatorAttachment": "cross-platform", "webAuthnPolicyPasswordlessUserVerificationRequirement": "required",
        "webAuthnPolicyPasswordlessRequireResidentKey": "Yes", "webAuthnPolicyPasswordlessRpEntityName": "Meddleware",
    }
    # A 404 means the realm does not exist yet: create it with the settings; otherwise update the existing realm in place.
    if api("GET", r(""), allow=(404,)) is None:
        api("POST", "/realms", settings)
    else:
        current = api("GET", r(""))
        current.update({k: v for k, v in settings.items() if k != "attributes"})
        current.setdefault("attributes", {}).update(settings["attributes"])
        api("PUT", r(""), current)
    # Attributes the admin sets (the bootstrap marker) are kept only when unmanaged attributes are enabled for admins.
    # The user profile decides which attributes survive a save; unmanaged ones are dropped unless this policy allows them.
    profile = api("GET", r("/users/profile"))
    profile["unmanagedAttributePolicy"] = "ADMIN_EDIT"
    api("PUT", r("/users/profile"), profile)


def ensure_flow():
    """Build the passkey-only browser flow once and make it the realm's browser flow."""
    # Build the flow only once: a second run must not create a duplicate (and must not reorder one an admin has changed).
    flows = api("GET", r("/authentication/flows"))
    if not any(f["alias"] == "passkey-browser" for f in flows):
        api("POST", r("/authentication/flows"), {"alias": "passkey-browser", "providerId": "basic-flow", "topLevel": True, "builtIn": False})

        def sub(parent, alias):
            """Add a sub-flow called `alias` under `parent`."""
            api("POST", r(f"/authentication/flows/{parent}/executions/flow"), {"alias": alias, "type": "basic-flow", "provider": "registration-page-form"})

        def add(flow, provider):
            """Add an execution of the authenticator `provider` to `flow`."""
            api("POST", r(f"/authentication/flows/{flow}/executions/execution"), {"provider": provider})

        # The tree: an existing session (cookie) is enough; otherwise the forms sub-flow runs a username, then one of two paths.
        add("passkey-browser", "auth-cookie")
        sub("passkey-browser", "passkey-forms")
        add("passkey-forms", "auth-username-form")
        sub("passkey-forms", "bootstrap-path")
        add("bootstrap-path", "conditional-user-attribute")
        add("bootstrap-path", "auth-password-form")
        sub("passkey-forms", "passkey-path")
        add("passkey-path", "conditional-user-attribute")
        add("passkey-path", "conditional-level-of-authentication")
        add("passkey-path", "webauthn-authenticator-passwordless")
        # Requirements: cookie and forms are alternatives; the username is required; each path runs only when its condition holds.
        execution("passkey-browser", "Cookie", "ALTERNATIVE")
        execution("passkey-browser", "passkey-forms", "ALTERNATIVE")
        execution("passkey-forms", "Username Form", "REQUIRED")
        execution("passkey-forms", "bootstrap-path", "CONDITIONAL")
        execution("passkey-forms", "passkey-path", "CONDITIONAL")
        for f in ("bootstrap-path", "passkey-path"):
            execution(f, "conditional-user-attribute", "REQUIRED")
        execution("bootstrap-path", "auth-password-form", "REQUIRED")
        execution("passkey-path", "conditional-level-of-authentication", "REQUIRED")
        execution("passkey-path", "webauthn-authenticator-passwordless", "REQUIRED")
        # Conditions: the bootstrap path for users marked `bootstrap=true`, the passkey path for everyone else, and level 2 (`phr`) once the passkey succeeds.
        configure("bootstrap-path", "conditional-user-attribute", "is-bootstrap", {"attribute_name": "bootstrap", "attribute_expected_value": "true", "not": "false"})
        configure("passkey-path", "conditional-user-attribute", "not-bootstrap", {"attribute_name": "bootstrap", "attribute_expected_value": "true", "not": "true"})
        configure("passkey-path", "conditional-level-of-authentication", "loa-2", {"loa-condition-level": "2", "loa-max-age": "0"})
    # Make it the realm's browser flow (the realm representation is read, changed and written back whole).
    realm = api("GET", r(""))
    realm["browserFlow"] = "passkey-browser"
    api("PUT", r(""), realm)


def substitute(text, path):
    """Replace every ${NAME} in a client file by the environment variable NAME; a missing variable stops the run (a client with a hole in it must not exist)."""
    def one(m):
        """Return the value for one ${NAME} match, JSON-escaped for its place inside a string."""
        if m.group(1) not in os.environ:
            die(f"{path} needs the environment variable {m.group(1)}")
        return json.dumps(os.environ[m.group(1)])[1:-1]
    return re.sub(r"\$\{([A-Z0-9_]+)\}", one, text)


def ensure_clients(dry):
    """Create or update one client per realm/clients/*.json file."""
    # Sorted, so a run is deterministic and its output comparable.
    for path in sorted(glob.glob(os.path.join(CLIENTS, "*.json"))):
        client = json.loads(substitute(open(path).read(), path))
        # Clients are looked up by their public client id; Keycloak's internal id is what the update needs.
        found = api("GET", r("/clients?clientId=" + urllib.parse.quote(client["clientId"])))
        print(f"client {client['clientId']}: {'update' if found else 'create'}")
        # A dry run reports and changes nothing for clients.
        if dry:
            continue
        if found:
            api("PUT", r(f"/clients/{found[0]['id']}"), client)
        else:
            api("POST", r("/clients"), client)


def ensure_operator(name):
    """Create the operator (or reset them for break-glass) in the bootstrap state and print the one-time password once."""
    # 18 random bytes (144 bits) from the operating system: used once to enrol the key, then deleted by --finish.
    password = secrets.token_urlsafe(18)
    # The user may already exist (break-glass) or not (first enrolment).
    found = api("GET", r("/users?exact=true&username=" + urllib.parse.quote(name)))
    # The bootstrap state: the marker that selects the bootstrap path, and the required action that registers the key.
    body = {"username": name, "enabled": True, "attributes": {"bootstrap": ["true"]}, "requiredActions": ["webauthn-register-passwordless"]}
    if found:
        uid = found[0]["id"]
        # Break-glass: the lost credentials (every key and any old password) go first.
        for c in api("GET", r(f"/users/{uid}/credentials")):
            api("DELETE", r(f"/users/{uid}/credentials/{c['id']}"))
        api("PUT", r(f"/users/{uid}"), {**found[0], **body})
    else:
        # A new user: create, then read back the id Keycloak assigned.
        api("POST", r("/users"), body)
        uid = api("GET", r("/users?exact=true&username=" + urllib.parse.quote(name)))[0]["id"]
    # The one-time password is permanent until --finish removes it (not marked temporary: Keycloak would then ask for a change first).
    api("PUT", r(f"/users/{uid}/reset-password"), {"type": "password", "value": password, "temporary": False})
    print(f"operator {name}: bootstrap password (shown once, use it to enrol the key, then run with --finish {name}): {password}")


def finish_operator(name):
    """After enrolment: delete the password and clear the bootstrap marker, leaving the passkey as the only credential."""
    found = api("GET", r("/users?exact=true&username=" + urllib.parse.quote(name)))
    if not found:
        die(f"no user {name}")
    uid = found[0]["id"]
    creds = api("GET", r(f"/users/{uid}/credentials"))
    # Never close the bootstrap path before a key exists: that would lock the operator out.
    if not any(c["type"] == "webauthn-passwordless" for c in creds):
        die(f"{name} has no passkey yet: enrol first")
    for c in creds:
        if c["type"] == "password":
            api("DELETE", r(f"/users/{uid}/credentials/{c['id']}"))
    # Remove the marker last, after the password: the order never leaves a user with a password path and no marker.
    user = api("GET", r(f"/users/{uid}"))
    user.get("attributes", {}).pop("bootstrap", None)
    api("PUT", r(f"/users/{uid}"), user)
    print(f"operator {name}: bootstrap path closed; the passkey is the only credential")


def main():
    """Parse the arguments and run the requested steps."""
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--operator", metavar="NAME", help="create or reset (break-glass) this user in the bootstrap state")
    ap.add_argument("--finish", metavar="NAME", help="close the bootstrap path of this user after they enrolled a key")
    ap.add_argument("--dry-run", action="store_true", help="read and print what would change for clients; realm and flow steps still run")
    args = ap.parse_args()
    # The admin credentials come from the environment, never from arguments (they would show in process listings).
    for var in ("KC_ADMIN", "KC_ADMIN_PW"):
        if var not in os.environ:
            die(f"{var} is not set")
    if args.finish:
        finish_operator(args.finish)
        return
    ensure_realm()
    ensure_flow()
    ensure_clients(args.dry_run)
    if args.operator:
        ensure_operator(args.operator)


if __name__ == "__main__":
    main()
