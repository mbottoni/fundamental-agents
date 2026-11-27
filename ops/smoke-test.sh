#!/usr/bin/env bash
# Start the production stack from two images and check that it actually works.
#
#   ops/smoke-test.sh <image-tag> [expected-version]
#
# Run by CI before an image may be pushed, and by hand after `make prod-build`
# (tag: local). It uses the real docker-compose.prod.yml and Caddyfile, laid
# out the way the server holds them, so what passes here is what is deployed:
# a compose file that cannot start, a Caddy route that points nowhere or an
# image that needs something it does not contain all fail here, not in
# production.
#
# No provider is called: the keys are placeholders, and nothing in start-up
# or in /healthz makes a request to one.
set -euo pipefail

TAG="${1:?usage: smoke-test.sh <image-tag> [expected-version]}"
EXPECTED_VERSION="${2:-}"
PORT="${SMOKE_PORT:-18080}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK="$(mktemp -d)"
BASE="http://127.0.0.1:${PORT}"

cp "$ROOT/docker-compose.prod.yml" "$ROOT/Caddyfile" "$WORK/"
cat > "$WORK/.env.prod" <<EOF
SITE_ADDRESS=:80
FRONTEND_URL=https://smoke.example.com
SECRET_KEY=$(openssl rand -hex 40)
POSTGRES_PASSWORD=$(openssl rand -hex 16)
FINANCIAL_MODELING_PREP_API_KEY=smoke-test-placeholder
NEWS_API_KEY=smoke-test-placeholder
STRIPE_SECRET_KEY=sk_test_placeholder
STRIPE_WEBHOOK_SECRET=whsec_placeholder
PREMIUM_EMAILS=
EOF

compose() {
  IMAGE_TAG="$TAG" HTTP_PORT="$PORT" HTTPS_PORT="$((PORT + 363))" \
    docker compose --project-name fa-smoke --project-directory "$WORK" \
    -f "$WORK/docker-compose.prod.yml" --env-file "$WORK/.env.prod" "$@"
}

failed=0
fail() { echo "FAIL: $*"; failed=1; }
pass() { echo "ok:   $*"; }

finish() {
  status=$?
  if [ "$status" -ne 0 ] || [ "$failed" -ne 0 ]; then
    echo "----- container status -----"; compose ps -a || true
    for service in api worker web caddy; do
      echo "----- $service (last 40 lines) -----"
      compose logs --no-color --tail 40 "$service" 2>&1 | grep -v "alembic.runtime.plugins" || true
    done
  fi
  compose down --volumes --remove-orphans >/dev/null 2>&1 || true
  rm -rf "$WORK"
  [ "$status" -eq 0 ] && [ "$failed" -eq 0 ] || exit 1
}
trap finish EXIT

# --pull never: test the images just built, never whatever :latest is upstream.
compose up -d --pull never

# "ok" means the database answers, the migrations ran and the worker is alive.
body=""
for _ in $(seq 1 60); do
  body="$(curl -fsS -m 5 "$BASE/healthz" 2>/dev/null || true)"
  if echo "$body" | grep -q '"status":"ok"'; then break; fi
  sleep 3
done
if echo "$body" | grep -q '"status":"ok"'; then pass "/healthz through Caddy: $body"
else fail "/healthz never reported ok. Last answer: ${body:-<none>}"; exit 1; fi

if [ -n "$EXPECTED_VERSION" ]; then
  if echo "$body" | grep -q "\"version\":\"$EXPECTED_VERSION\""; then pass "the image reports version $EXPECTED_VERSION"
  else fail "expected version $EXPECTED_VERSION in $body"; fi
fi

status_of() { curl -s -o /dev/null -m 10 -w '%{http_code}' "$@"; }

code="$(status_of "$BASE/")"
[ "$code" = "200" ] && pass "the frontend answers on /" || fail "GET / returned $code"

# 401, not 404 or 502: the request reached the API and was refused for lack
# of a token, which proves the /api route.
code="$(status_of "$BASE/api/v1/auth/me")"
[ "$code" = "401" ] && pass "/api/* reaches the backend" || fail "GET /api/v1/auth/me returned $code, expected 401"

for path in /docs /openapi.json; do
  code="$(status_of "$BASE$path")"
  [ "$code" = "404" ] && pass "$path is not reachable from outside" || fail "GET $path returned $code, expected 404"
done

# A real request through the whole path: Caddy, the API, Postgres.
email="smoke-$(date +%s)@example.com"
code="$(status_of -X POST "$BASE/api/v1/auth/register" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$email\",\"password\":\"SmokeTest123\"}")"
[ "$code" = "201" ] && pass "an account can be registered" || fail "register returned $code, expected 201"
code="$(status_of -X POST "$BASE/api/v1/auth/login" -d "username=$email&password=SmokeTest123")"
[ "$code" = "200" ] && pass "and can sign in" || fail "login returned $code, expected 200"

type="$(curl -s -o /dev/null -m 20 -w '%{content_type}' -H 'Accept: image/webp,*/*' \
  "$BASE/_next/image?url=%2Fmountain.jpg&w=640&q=75")"
[ "$type" = "image/webp" ] && pass "next/image resizes (sharp is present)" || fail "image optimisation returned '$type', expected image/webp"

for service in api worker web; do
  uid="$(compose exec -T "$service" id -u)"
  [ "$uid" != "0" ] && pass "$service runs as uid $uid" || fail "$service runs as root"
done

# The API address is compiled into the bundle. A localhost address there means
# every browser would call the visitor's own machine.
if compose exec -T web sh -c 'grep -rlq "localhost:8000" .next server.js' 2>/dev/null; then
  fail "the frontend bundle contains localhost:8000"
else
  pass "the frontend bundle has no localhost address"
fi

[ "$failed" -eq 0 ] && echo "Smoke test passed." || echo "Smoke test FAILED."
