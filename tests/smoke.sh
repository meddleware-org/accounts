#!/usr/bin/env bash
# Smoke test of the image and the realm script: build the image, start it against a throw-away PostgreSQL, apply the realm, check the result.
#
#   tests/smoke.sh
#
# What it proves: `kc.sh build` works and the optimised image starts READ-ONLY with all capabilities dropped; realm/apply.py runs twice (idempotent); the
# discovery document names the issuer and offers S256; the passkey browser flow is the realm's browser flow; a client from a file (with a secret
# substituted from the environment) exists with PKCE S256 required; the operator is created in the bootstrap state and --finish refuses until a key exists.
# The browser half (enrolment with a virtual security key, passkey sign-in, logout, break-glass) and the identity-contract conformance suite run in the
# Meddleware workspace (k8s/base/auth/tests/keycloak-spike), which builds this same Dockerfile.
#
# Environment: CONTAINER_TOOL (podman or docker). Needs python3 and curl. No registry login, no cluster. Exit status 0 when every check passed.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$HERE")"
TOOL="${CONTAINER_TOOL:-podman}"
ID="accounts-smoke-$$"
PORT=$(( 20000 + RANDOM % 15000 )); MPORT=$(( PORT + 1000 ))
PASS=0; FAIL=0
# ok <message>: count and print a passing check.
ok() { PASS=$((PASS + 1)); printf '  PASS  %s\n' "$*"; }
# bad <message>: count and print a failing check.
bad() { FAIL=$((FAIL + 1)); printf '  FAIL  %s\n' "$*" >&2; }
# cleanup: remove the containers, the network and the image.
cleanup() { "$TOOL" rm -f "$ID-kc" "$ID-pg" > /dev/null 2>&1; "$TOOL" network rm "$ID" > /dev/null 2>&1; "$TOOL" rmi -f "localhost/$ID" > /dev/null 2>&1; }
trap cleanup EXIT
# rand: a random alphanumeric string of 24 characters.
rand() { openssl rand -base64 48 | tr -dc 'A-Za-z0-9' | head -c 24; }

PGPW="$(rand)"; ADMINPW="$(rand)"; CONSOLE_SECRET="$(rand)"; export CONSOLE_SECRET
"$TOOL" build -q -t "localhost/$ID" "$ROOT" > /dev/null && ok "image builds (kc.sh build)" || { bad "image build failed"; exit 1; }
"$TOOL" network create "$ID" > /dev/null
"$TOOL" run -d --name "$ID-pg" --network "$ID" -e POSTGRES_PASSWORD="$PGPW" -e POSTGRES_DB=keycloak docker.io/library/postgres:18 > /dev/null
for _ in $(seq 1 60); do "$TOOL" exec "$ID-pg" pg_isready -U postgres -d keycloak > /dev/null 2>&1 && break; sleep 1; done
"$TOOL" run -d --name "$ID-kc" --network "$ID" --read-only --cap-drop ALL --security-opt no-new-privileges --memory 1g --tmpfs /tmp --tmpfs /opt/keycloak/data:rw,mode=1777 \
  -p "127.0.0.1:$PORT:8080" -p "127.0.0.1:$MPORT:9000" -e KC_DB=postgres -e "KC_DB_URL=jdbc:postgresql://$ID-pg:5432/keycloak" -e KC_DB_USERNAME=postgres -e "KC_DB_PASSWORD=$PGPW" \
  -e KC_HTTP_ENABLED=true -e "KC_HOSTNAME=http://localhost:$PORT" -e KC_BOOTSTRAP_ADMIN_USERNAME=admin -e "KC_BOOTSTRAP_ADMIN_PASSWORD=$ADMINPW" "localhost/$ID" > /dev/null
ready=no; for _ in $(seq 1 180); do curl -sf -m 2 "http://127.0.0.1:$MPORT/health/ready" > /dev/null 2>&1 && { ready=yes; break; }; sleep 1; done
[[ "$ready" == yes ]] && ok "starts read-only (--optimized), ready" || { "$TOOL" logs "$ID-kc" 2>&1 | tail -15 >&2; bad "did not become ready"; exit 1; }

export KC_URL="http://localhost:$PORT" KC_ADMIN=admin KC_ADMIN_PW="$ADMINPW" CLIENTS_DIR="$HERE/clients"
python3 "$ROOT/realm/apply.py" > /dev/null 2>&1 || bad "first apply.py run failed"
OUT="$(python3 "$ROOT/realm/apply.py" --operator operator 2>&1)" && ok "apply.py runs twice (idempotent)" || { printf '%s\n' "$OUT" >&2; bad "apply.py failed"; }
grep -q 'bootstrap password' <<< "$OUT" && ok "operator created in the bootstrap state, password shown once" || bad "no bootstrap password printed"
DISC="$(curl -s "http://127.0.0.1:$PORT/realms/meddleware/.well-known/openid-configuration")"
python3 -c 'import json,sys; d=json.loads(sys.argv[1]); assert d["issuer"].endswith("/realms/meddleware") and "S256" in d["code_challenge_methods_supported"] and d["authorization_response_iss_parameter_supported"]' "$DISC" \
  && ok "discovery: issuer, S256, iss parameter" || bad "discovery document"
TOKEN="$(curl -s -d grant_type=password -d client_id=admin-cli -d username=admin --data-urlencode "password=$ADMINPW" "http://127.0.0.1:$PORT/realms/master/protocol/openid-connect/token" | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')"
REALM="$(curl -s -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:$PORT/admin/realms/meddleware")"
python3 -c 'import json,sys; d=json.loads(sys.argv[1]); assert d["browserFlow"]=="passkey-browser" and d["webAuthnPolicyPasswordlessUserVerificationRequirement"]=="required"' "$REALM" \
  && ok "browser flow is passkey-browser; user verification required" || bad "realm settings"
CLIENT="$(curl -s -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:$PORT/admin/realms/meddleware/clients?clientId=console")"
python3 -c 'import json,sys; c=json.loads(sys.argv[1])[0]; assert c["attributes"]["pkce.code.challenge.method"]=="S256"' "$CLIENT" && ok "client from file: PKCE S256 required" || bad "client"
OUT="$(python3 "$ROOT/realm/apply.py" --finish operator 2>&1)"; grep -q 'no passkey yet' <<< "$OUT" && ok "--finish refuses before a key is enrolled" || bad "--finish did not refuse"
echo ""; if (( FAIL == 0 )); then printf '[smoke] ALL PASSED (%d checks)\n' "$PASS"; else printf '[smoke] %d FAILED, %d passed\n' "$FAIL" "$PASS" >&2; exit 1; fi
