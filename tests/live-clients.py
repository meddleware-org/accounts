#!/usr/bin/env python3
"""Create or remove the throw-away conformance clients on a LIVE Keycloak (used by the workspace's k8s/scripts/keycloak-live.sh conformance).

    live-clients.py create <jwks-file> <console-secret-file>
    live-clients.py remove

`create` makes the client scope `relay:upload`, the confidential client `conf-console` (PKCE S256 required) and the machine client `conf-worker`
(private_key_jwt with the given public JWK set, DPoP-bound RFC 9068 tokens, audience mapper for the relay origin) that the identity-contract
conformance suite signs in as. `remove` deletes all three. Nothing here is part of the realm: the clients exist only for the length of one run.
It reuses the admin helpers of realm/apply.py, so it needs the same environment (KC_URL, KC_ADMIN, KC_ADMIN_PW, REALM) and must run with realm/ importable
(set REALM_DIR, default ~/accounts-realm).
"""
import os
import sys

sys.path.insert(0, os.path.expanduser(os.environ.get("REALM_DIR", "~/accounts-realm")))
import apply as a  # noqa: E402  (the path is set just above)

# The audience the machine client's access token is minted for: the relay origin the access-gate Worker will call.
AUD = "https://walrus-storage-relay-origin.meddleware.dev"


def create(jwks_file, secret_file):
    """Create the scope and the two clients from the public key set and the console secret held in the given files."""
    jwks = open(jwks_file).read()
    secret = open(secret_file).read().strip()
    # The scope the machine client asks for; created once, removed by `remove`.
    if not [s for s in a.api("GET", a.r("/client-scopes")) if s["name"] == "relay:upload"]:
        a.api("POST", a.r("/client-scopes"), {"name": "relay:upload", "protocol": "openid-connect", "attributes": {"include.in.token.scope": "true", "display.on.consent.screen": "false"}})
    scope = [s for s in a.api("GET", a.r("/client-scopes")) if s["name"] == "relay:upload"][0]
    # The console client: authorization code with PKCE S256 only; the redirect URI is never visited.
    a.api("POST", a.r("/clients"), {"clientId": "conf-console", "protocol": "openid-connect", "publicClient": False, "secret": secret, "standardFlowEnabled": True,
                                    "directAccessGrantsEnabled": False, "redirectUris": ["https://console.example.test/callback"], "attributes": {"pkce.code.challenge.method": "S256"}})
    # The machine client: signs its token request with the private key whose public half is in the key set.
    a.api("POST", a.r("/clients"), {"clientId": "conf-worker", "protocol": "openid-connect", "publicClient": False, "clientAuthenticatorType": "client-jwt", "standardFlowEnabled": False,
                                    "serviceAccountsEnabled": True, "directAccessGrantsEnabled": False,
                                    "attributes": {"token.endpoint.auth.signing.alg": "ES256", "use.jwks.string": "true", "jwks.string": jwks, "dpop.bound.access.tokens": "true",
                                                   "access.token.header.type.rfc9068": "true", "access.token.lifespan": "300"}})
    worker = a.api("GET", a.r("/clients?clientId=conf-worker"))[0]
    a.api("PUT", a.r(f"/clients/{worker['id']}/default-client-scopes/{scope['id']}"))
    a.api("POST", a.r(f"/clients/{worker['id']}/protocol-mappers/models"), {"name": "relay-audience", "protocol": "openid-connect", "protocolMapper": "oidc-audience-mapper",
                                                                           "config": {"included.custom.audience": AUD, "access.token.claim": "true", "id.token.claim": "false",
                                                                                      "introspection.token.claim": "false"}})
    print("created")


def remove():
    """Delete both clients and the scope (a missing one is fine)."""
    for cid in ("conf-console", "conf-worker"):
        for c in a.api("GET", a.r("/clients?clientId=" + cid)):
            a.api("DELETE", a.r("/clients/" + c["id"]))
    for s in a.api("GET", a.r("/client-scopes")):
        if s["name"] == "relay:upload":
            a.api("DELETE", a.r("/client-scopes/" + s["id"]))
    print("removed")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "create":
        create(sys.argv[2], sys.argv[3])
    elif len(sys.argv) == 2 and sys.argv[1] == "remove":
        remove()
    else:
        sys.exit(__doc__)
