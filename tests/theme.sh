#!/usr/bin/env bash
# Browser test of the login theme (ADR-0016, FU-0182): builds the image (with the theme), starts it against a throw-away PostgreSQL with the realm applied (which sets the strict Content-Security-Policy and the theme), and
# walks every page of the passkey-only sign-in in a real browser with a virtual security key: axe in light and dark, no CSP violation, nothing stored, only Keycloak's cookies. Screenshots go to $OUT/shots.
#
#   tests/theme.sh
#
# Environment: CONTAINER_TOOL (podman or docker), PLAYWRIGHT_FROM (a package.json beside a node_modules with playwright-core and @axe-core/playwright; default the Meddleware workspace's repos/ui), OUT (default a
# temporary directory, printed). Hostnames are kc.localhost (a secure context, which WebAuthn requires) mapped by the browser to the published port. Exit status 0 only if every check passed.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$HERE")"
TOOL="${CONTAINER_TOOL:-podman}"
export PLAYWRIGHT_FROM="${PLAYWRIGHT_FROM:-$ROOT/../ui/package.json}"
ID="accounts-theme-$$"
# free_port: a TCP port nobody is listening on.
free_port() { python3 -c 'import socket; s = socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()'; }
KP="$(free_port)"; MP="$(free_port)"
OUT="${OUT:-$(mktemp -d)}"; mkdir -p "$OUT"
PASS=0; FAIL=0
# ok <message>: count and print a passing check.
ok() { PASS=$((PASS + 1)); printf '  PASS  %s\n' "$*"; }
# bad <message>: count and print a failing check.
bad() { FAIL=$((FAIL + 1)); printf '  FAIL  %s\n' "$*" >&2; }
# cleanup: remove the containers, the network and the image.
cleanup() { "$TOOL" rm -f "$ID-kc" "$ID-pg" > /dev/null 2>&1; "$TOOL" network rm "$ID" > /dev/null 2>&1; "$TOOL" rmi -f "localhost/$ID" > /dev/null 2>&1; }
trap cleanup EXIT
# rand: a random alphanumeric string.
rand() { openssl rand -base64 48 | tr -dc 'A-Za-z0-9' | head -c 24; }
PGPW="$(rand)"; ADMINPW="$(rand)"
"$TOOL" build -q -t "localhost/$ID" "$ROOT" > /dev/null && ok "image builds with the theme" || { bad "image build failed"; exit 1; }
"$TOOL" network create "$ID" > /dev/null
"$TOOL" run -d --name "$ID-pg" --network "$ID" -e POSTGRES_PASSWORD="$PGPW" -e POSTGRES_DB=keycloak docker.io/library/postgres:18 > /dev/null
for _ in $(seq 1 60); do "$TOOL" exec "$ID-pg" pg_isready -U postgres -d keycloak > /dev/null 2>&1 && break; sleep 1; done
"$TOOL" run -d --name "$ID-kc" --network "$ID" --read-only --cap-drop ALL --security-opt no-new-privileges --memory 1g --tmpfs /tmp --tmpfs /opt/keycloak/data:rw,mode=1777 \
  -p "127.0.0.1:$KP:8080" -p "127.0.0.1:$MP:9000" -e KC_DB=postgres -e "KC_DB_URL=jdbc:postgresql://$ID-pg:5432/keycloak" -e KC_DB_USERNAME=postgres -e "KC_DB_PASSWORD=$PGPW" \
  -e KC_HTTP_ENABLED=true -e KC_HOSTNAME=http://kc.localhost:8080 -e KC_PROXY_HEADERS=xforwarded -e KC_BOOTSTRAP_ADMIN_USERNAME=admin -e "KC_BOOTSTRAP_ADMIN_PASSWORD=$ADMINPW" "localhost/$ID" start --optimized > /dev/null
for _ in $(seq 1 180); do curl -sf -m 2 "http://127.0.0.1:$MP/health/ready" > /dev/null 2>&1 && break; sleep 1; done
curl -sf -m 2 "http://127.0.0.1:$MP/health/ready" > /dev/null && ok "Keycloak ready" || { bad "Keycloak did not start"; exit 1; }
mkdir -p "$OUT/clients"
cp "$HERE/clients/enrol.json" "$OUT/clients/"
# The production bootstrap client (flow-binding override to the one-time-password flow) with the test redirect.
sed 's#https://meddleware.co.uk/#http://kc.localhost:8080/enrolled#g' "$ROOT/realm/clients/bootstrap.json" > "$OUT/clients/bootstrap.json"
export KC_URL="http://127.0.0.1:$KP" KC_ADMIN=admin KC_ADMIN_PW="$ADMINPW" CLIENTS_DIR="$OUT/clients"
python3 "$ROOT/realm/apply.py" > "$OUT/apply.log" 2>&1 && ok "realm applied (theme, strict CSP)" || { cat "$OUT/apply.log" >&2; bad "apply.py failed"; exit 1; }
PW="$(KC_PUBLIC_URL=http://kc.localhost:8080 python3 "$ROOT/realm/apply.py" --operator theme-user 2>&1 | grep "bootstrap password" | sed -n 's/.*: \([A-Za-z0-9_-]*\)$/\1/p')"
THEME_VERSION="$(sed -n 's/^themeVersion=//p' "$ROOT/theme/meddleware/login/theme.properties")" KC_API="http://127.0.0.1:$KP" APPLY="$ROOT/realm/apply.py" KC="http://kc.localhost:8080" USER=theme-user PASSWORD="$PW" OUT="$OUT" HOST_RULES="MAP kc.localhost 127.0.0.1:$KP" node "$HERE/theme-check.mjs" 2>&1 | tee "$OUT/theme-check.log"
if grep -q 'ALL PASSED' "$OUT/theme-check.log"; then ok "theme check (every page: axe, CSP, storage)"; else bad "theme check"; "$TOOL" logs "$ID-kc" 2>&1 | grep -iE "Caused by|freemarker|FTL|template|Failed" | tail -14 | cut -c1-300 >&2; fi
echo "[test] screenshots: $OUT/shots"
echo ""
if (( FAIL == 0 )); then printf '[theme] ALL PASSED (%d checks)\n' "$PASS"; else printf '[theme] %d FAILED, %d passed\n' "$FAIL" "$PASS" >&2; exit 1; fi
