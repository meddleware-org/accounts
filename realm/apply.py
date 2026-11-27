#!/usr/bin/env python3
"""Apply the Meddleware realm to a running Keycloak through its admin REST API (realm as code; ADR-0016, FU-0194).

It is idempotent for the realm, the browser flow and the clients (a client that exists is updated, a missing one is created) and it never deletes
a realm. What it builds:

  * realm `meddleware`: phishing-resistant level `phr` = LoA 2; WebAuthn passwordless policy with a security key (cross-platform attachment), user
    verification required and a resident key; unmanaged user attributes enabled for the admin (the bootstrap marker needs them);
  * browser flow `passkey-first` (see ensure_flow): no username step; the security key identifies the user (a resident credential, user verification required, level 2 = `phr`), with a
    one-time-password page (one form with username and password, generic errors) for a first enrolment and for break-glass, which sends the user to register a key;
  * Keycloak's account console disabled (it cannot run under the strict policy; see disable_account_console);
  * the realm roles in ROLES (`--grant NAME ROLE` gives one to a user; `--set-email NAME EMAIL` sets an email);
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
# The Content-Security-Policy of every page the realm serves (the login pages and the account console): scripts and styles only from Keycloak's own origin, nothing inline, no plug-ins, no framing, no
# <base>. (No form-action: Chromium applies it to the redirect after a form post, which goes back to the application.) CSP_MODE=report-only sends it as a report-only header while it is being tried out.
CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; font-src 'self'; connect-src 'self'; frame-src 'none'; "
       "frame-ancestors 'none'; object-src 'none'; base-uri 'none'")
# The browser flows: the applications' one (cookie, then the key) and the one only the `bootstrap` client uses (the one-time-password page).
FLOW = "passkey-first"
KEY_FLOW = "Security key"
OTP_FLOW = "one-time-password"
# The public address people use (the `--operator` output prints the enrolment link under it); the tests set their own.
PUBLIC_URL = os.environ.get("KC_PUBLIC_URL", "https://accounts.meddleware.co.uk").rstrip("/")
# Realm roles the platform's clients map to application roles (a client's `roles` claim). `grafana-admin`: Grafana Admin (stage 5, ADR-0016).
ROLES = ("grafana-admin",)
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
    path = r(f"/authentication/flows/{urllib.parse.quote(flow)}/executions")
    for e in api("GET", path):
        if name in (e.get("displayName"), e.get("alias"), e.get("providerId")):
            if seen == index:
                e["requirement"] = requirement
                api("PUT", path, e)
                return
            seen += 1
    die(f"no execution {name} in {flow}")


def configure(flow, provider, alias, config):
    """Attach a configuration to the first execution of `flow` with the given provider id."""
    # The execution to configure: the first one in the flow with this provider id.
    e = [x for x in api("GET", r(f"/authentication/flows/{urllib.parse.quote(flow)}/executions")) if x.get("providerId") == provider][0]
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
        # The login theme of the accounts repository (theme/meddleware/login) and the name it shows.
        "loginTheme": "meddleware", "displayName": "Meddleware",
        "webAuthnPolicyPasswordlessResidentKey": "required", "webAuthnPolicyPasswordlessRpEntityName": "Meddleware",
        # The same physical key cannot be registered twice (a second key must be a different one), so "two keys" always means two.
        "webAuthnPolicyPasswordlessAvoidSameAuthenticatorRegister": True,
    }
    # A 404 means the realm does not exist yet: create it with the settings; otherwise update the existing realm in place.
    if api("GET", r(""), allow=(404,)) is None:
        api("POST", "/realms", settings)
    else:
        current = api("GET", r(""))
        current.update({k: v for k, v in settings.items() if k != "attributes"})
        current.setdefault("attributes", {}).update(settings["attributes"])
        api("PUT", r(""), current)
    # The security headers: the realm's existing set, with the Content-Security-Policy replaced (a partial map would reset the others).
    realm = api("GET", r(""))
    headers = dict(realm.get("browserSecurityHeaders") or {})
    report_only = os.environ.get("CSP_MODE") == "report-only"
    # With CSP_MODE=report-only the strict policy is only reported while it is being tried, and the old header stays in force.
    headers["contentSecurityPolicy"] = "frame-src 'self'; frame-ancestors 'self'; object-src 'none';" if report_only else CSP
    headers["contentSecurityPolicyReportOnly"] = CSP if report_only else ""
    realm["browserSecurityHeaders"] = headers
    api("PUT", r(""), realm)
    # Attributes the admin sets (the bootstrap marker) are kept only when unmanaged attributes are enabled for admins.
    # The user profile decides which attributes survive a save; unmanaged ones are dropped unless this policy allows them.
    profile = api("GET", r("/users/profile"))
    profile["unmanagedAttributePolicy"] = "ADMIN_EDIT"
    # The operators are a handful of known people: no first name, last name or email is required of them. Left required, Keycloak interposes an "update your profile" page
    # (the VERIFY_PROFILE required action) in the sign-in of a user created without them, in front of every application's login.
    for attribute in profile.get("attributes", []):
        if attribute.get("name") in ("firstName", "lastName", "email"):
            attribute.pop("required", None)
    api("PUT", r("/users/profile"), profile)


def ensure_roles():
    """Create each realm role of ROLES that does not exist yet."""
    for name in ROLES:
        if api("GET", r(f"/roles/{urllib.parse.quote(name)}"), allow=(404,)) is None:
            api("POST", r("/roles"), {"name": name, "description": "Platform role (see realm/apply.py ROLES)"})


def grant(name, role):
    """Give a user a realm role from ROLES (idempotent); refuses a role this script does not manage."""
    if role not in ROLES:
        die(f"unknown role {role}; the roles are {', '.join(ROLES)}")
    found = api("GET", r("/users?exact=true&username=" + urllib.parse.quote(name)))
    if not found:
        die(f"no user {name}")
    # The role representation Keycloak wants in the mapping request.
    rep = api("GET", r(f"/roles/{urllib.parse.quote(role)}"))
    api("POST", r(f"/users/{found[0]['id']}/role-mappings/realm"), [rep])
    print(f"user {name}: has role {role}")


def set_email(name, email):
    """Set a user's email (marked verified): applications that need one (Grafana) read it from the ID token."""
    found = api("GET", r("/users?exact=true&username=" + urllib.parse.quote(name)))
    if not found:
        die(f"no user {name}")
    user = api("GET", r(f"/users/{found[0]['id']}"))
    user["email"], user["emailVerified"] = email, True
    api("PUT", r(f"/users/{found[0]['id']}"), user)
    print(f"user {name}: email set")


def ensure_flow():
    """(Re)build the two browser flows and make the passkey-first one the realm's browser flow.

    `passkey-first` (every application's sign-in) has no username step, so there is no username to be told is wrong (OWASP: a valid and an invalid credential look alike): the cookie, then the
    security key with no user identified yet. The key (a resident credential) says who is signing in, user verification is required, and a level-of-authentication condition makes the result
    `acr` = `phr` (level 2). An unknown or unusable key gives one generic failure.

    `one-time-password` is bound only to the client `bootstrap` (its flow-binding override, see ensure_clients): ONE page with username and password, so a wrong username and a wrong password give
    the same message. It exists for a first enrolment or break-glass: a user without the `bootstrap` marker is refused after the password, and a signed-in bootstrap user is sent to register a key
    by their required action. Nobody meets it by signing in to an application.

    Both are rebuilt on every run (they are small), so a change here reaches the realm by running this script; the realm points at the built-in flow while the old ones are deleted."""
    flows = api("GET", r("/authentication/flows"))
    old = [f for f in flows if f["alias"] in (FLOW, OTP_FLOW, KEY_FLOW, "passkey-browser")]
    if old:
        realm = api("GET", r(""))
        realm["browserFlow"] = "browser"
        api("PUT", r(""), realm)
        # A client bound to a flow keeps the flow from being deleted: clear the override first (ensure_clients sets it again from the new flow's id).
        for c in api("GET", r("/clients")):
            if (c.get("authenticationFlowBindingOverrides") or {}).get("browser"):
                # An empty value for the key removes the override (an empty map would leave it in place).
                c["authenticationFlowBindingOverrides"] = {"browser": ""}
                api("PUT", r(f"/clients/{c['id']}"), c)
        for f in old:
            api("DELETE", r(f"/authentication/flows/{f['id']}"), allow=(404,))

    def sub(parent, alias):
        """Add a sub-flow called `alias` under `parent`."""
        api("POST", r(f"/authentication/flows/{urllib.parse.quote(parent)}/executions/flow"), {"alias": alias, "type": "basic-flow", "provider": "registration-page-form"})

    def add(flow, provider):
        """Add an execution of the authenticator `provider` to `flow`."""
        api("POST", r(f"/authentication/flows/{urllib.parse.quote(flow)}/executions/execution"), {"provider": provider})

    # The applications' flow: cookie, then the key (a conditional sub-flow: the level condition, then the key).
    api("POST", r("/authentication/flows"), {"alias": FLOW, "providerId": "basic-flow", "topLevel": True, "builtIn": False})
    add(FLOW, "auth-cookie")
    sub(FLOW, KEY_FLOW)
    sub(KEY_FLOW, "passkey-level")
    add("passkey-level", "conditional-level-of-authentication")
    add("passkey-level", "webauthn-authenticator-passwordless")
    execution(FLOW, "Cookie", "ALTERNATIVE")
    execution(FLOW, KEY_FLOW, "ALTERNATIVE")
    execution(KEY_FLOW, "passkey-level", "CONDITIONAL")
    execution("passkey-level", "conditional-level-of-authentication", "REQUIRED")
    execution("passkey-level", "webauthn-authenticator-passwordless", "REQUIRED")
    # Level 2 (`phr`) once the key succeeds.
    configure("passkey-level", "conditional-level-of-authentication", "loa-2", {"loa-condition-level": "2", "loa-max-age": "0"})

    # The bootstrap client's flow: the one-time-password page, then the gate that refuses anyone not marked `bootstrap`.
    api("POST", r("/authentication/flows"), {"alias": OTP_FLOW, "providerId": "basic-flow", "topLevel": True, "builtIn": False})
    add(OTP_FLOW, "auth-username-password-form")
    sub(OTP_FLOW, "bootstrap-gate")
    add("bootstrap-gate", "conditional-user-attribute")
    add("bootstrap-gate", "deny-access-authenticator")
    execution(OTP_FLOW, "auth-username-password-form", "REQUIRED")
    execution(OTP_FLOW, "bootstrap-gate", "CONDITIONAL")
    execution("bootstrap-gate", "conditional-user-attribute", "REQUIRED")
    execution("bootstrap-gate", "deny-access-authenticator", "REQUIRED")
    # The gate applies to a user who is NOT marked `bootstrap` (they are denied even with a correct password).
    configure("bootstrap-gate", "conditional-user-attribute", "not-bootstrap", {"attribute_name": "bootstrap", "attribute_expected_value": "true", "not": "true"})

    # Make the applications' flow the realm's browser flow (the realm representation is read, changed and written back whole).
    realm = api("GET", r(""))
    realm["browserFlow"] = FLOW
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
        # A flow-binding override names its flow by alias with a leading "@" (the id is only known after ensure_flow built it): resolve it.
        overrides = client.get("authenticationFlowBindingOverrides") or {}
        for binding, ref in list(overrides.items()):
            if str(ref).startswith("@"):
                flow = [f for f in api("GET", r("/authentication/flows")) if f["alias"] == ref[1:]]
                if not flow:
                    die(f"{path}: no flow {ref[1:]}")
                overrides[binding] = flow[0]["id"]
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


def disable_account_console():
    """Disable Keycloak's self-service account console (the clients `account` and `account-console`).

    The account console is a single-page app that needs inline scripts and styles, which the realm's strict Content-Security-Policy refuses (and the Ingress does not route it). Nothing in this platform
    needs it: keys are enrolled and added through the sign-in flow's own required action (`--operator`, `--add-key`), which the login theme serves under the policy."""
    # Both built-in clients: the old and the current account console.
    for client_id in ("account", "account-console"):
        found = api("GET", r("/clients?clientId=" + urllib.parse.quote(client_id)))
        if found and found[0].get("enabled", True):
            found[0]["enabled"] = False
            api("PUT", r(f"/clients/{found[0]['id']}"), found[0])


def add_key(name):
    """Ask a user (who already signs in with a key) to register another one at their next sign-in: sets the register-key required action; the user then signs in with the key they have, any application will do."""
    # The user must exist; their required actions are read first so an action already pending is kept.
    found = api("GET", r("/users?exact=true&username=" + urllib.parse.quote(name)))
    if not found:
        die(f"no user {name}")
    user = api("GET", r(f"/users/{found[0]['id']}"))
    actions = set(user.get("requiredActions") or [])
    actions.add("webauthn-register-passwordless")
    user["requiredActions"] = sorted(actions)
    api("PUT", r(f"/users/{found[0]['id']}"), user)
    print(f"user {name}: will be asked to register another key at the next sign-in with the key they have (sign in at any application, for example Grafana's \"Sign in with Meddleware\")")


def enrol_url():
    """The link that starts a first enrolment or a break-glass: the `bootstrap` client's sign-in (the one-time-password page, then the key registration), landing on the platform's own site afterwards."""
    q = urllib.parse.urlencode({"client_id": "bootstrap", "response_type": "code", "scope": "openid", "redirect_uri": "https://meddleware.co.uk/", "state": "enrol",
                                "code_challenge": "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM", "code_challenge_method": "S256"})
    return f"{PUBLIC_URL}/realms/meddleware/protocol/openid-connect/auth?{q}"


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
    print(f"operator {name}: enrol the key at this link (username, this password, then the key): {enrol_url()}")
    print(f"operator {name}: bootstrap password (shown once), then run with --finish {name}: {password}")


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


def status(name):
    """Print the sign-in state of a user without any secret: credential types and labels, the bootstrap marker, pending required actions."""
    found = api("GET", r("/users?exact=true&username=" + urllib.parse.quote(name)))
    if not found:
        die(f"no user {name}")
    uid = found[0]["id"]
    creds = api("GET", r(f"/users/{uid}/credentials"))
    print(f"user {name}: enabled={found[0].get('enabled')}")
    print("credentials: " + (", ".join(f"{c['type']} ({c.get('userLabel') or 'no label'})" for c in creds) or "none"))
    print(f"bootstrap marker: {'bootstrap' in (found[0].get('attributes') or {})}; required actions: {found[0].get('requiredActions') or 'none'}")


def main():
    """Parse the arguments and run the requested steps."""
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--operator", metavar="NAME", help="create or reset (break-glass) this user in the bootstrap state")
    ap.add_argument("--finish", metavar="NAME", help="close the bootstrap path of this user after they enrolled a key")
    ap.add_argument("--status", metavar="NAME", help="print this user's (or ALL users') credential types, bootstrap marker and required actions (no secrets)")
    ap.add_argument("--add-key", metavar="NAME", help="ask this user to register another security key at their next sign-in")
    ap.add_argument("--grant", nargs=2, metavar=("NAME", "ROLE"), help="give this user this realm role (one of ROLES)")
    ap.add_argument("--set-email", nargs=2, metavar=("NAME", "EMAIL"), help="set this user's email (marked verified)")
    ap.add_argument("--dry-run", action="store_true", help="read and print what would change for clients; realm and flow steps still run")
    args = ap.parse_args()
    # The admin credentials come from the environment, never from arguments (they would show in process listings).
    for var in ("KC_ADMIN", "KC_ADMIN_PW"):
        if var not in os.environ:
            die(f"{var} is not set")
    if args.status:
        # `--status ALL` lists every user instead of one.
        for u in (api("GET", r("/users?max=200")) if args.status == "ALL" else [{"username": args.status}]):
            status(u["username"])
        return
    if args.add_key:
        add_key(args.add_key)
        return
    if args.grant:
        ensure_roles()
        grant(*args.grant)
        return
    if args.set_email:
        set_email(*args.set_email)
        return
    if args.finish:
        finish_operator(args.finish)
        return
    ensure_realm()
    ensure_roles()
    ensure_flow()
    ensure_clients(args.dry_run)
    disable_account_console()
    if args.operator:
        ensure_operator(args.operator)


if __name__ == "__main__":
    main()
