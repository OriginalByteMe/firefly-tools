#!/usr/bin/env bash
#
# Bootstrap script for Firefly III integration test environment.
#
# 1. Starts Docker Compose services (Firefly III + MariaDB + Data Importer)
# 2. Waits for Firefly III to be healthy
# 3. Creates a test user via artisan (APP_ENV=testing required)
# 4. Generates a Personal Access Token via artisan tinker
# 5. Writes a .env file for the MCP server
# 6. Restarts the importer with the real token
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$SCRIPT_DIR/.env.test"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.yml"

APP_CONTAINER="firefly_iii_test"
TEST_EMAIL="test@firefly.local"
IMPORTER_SECRET="integration-test-secret-32chars!!"

# Generate a random 32-char APP_KEY
APP_KEY="$(head /dev/urandom | LC_ALL=C tr -dc 'A-Za-z0-9' | head -c 32)"
export APP_KEY

echo "==> Starting Docker Compose services..."
docker compose -f "$COMPOSE_FILE" up -d --pull=always --wait 2>&1

echo "==> Waiting for Firefly III to be healthy..."
for i in $(seq 1 60); do
    if docker inspect --format='{{.State.Health.Status}}' "$APP_CONTAINER" 2>/dev/null | grep -q "healthy"; then
        echo "    Firefly III is healthy."
        break
    fi
    if [ "$i" -eq 60 ]; then
        echo "ERROR: Firefly III did not become healthy in time."
        docker compose -f "$COMPOSE_FILE" logs app
        exit 1
    fi
    sleep 2
done

echo "==> Running database migrations..."
docker exec "$APP_CONTAINER" php artisan migrate --force --seed 2>&1 || true

echo "==> Creating test user ($TEST_EMAIL)..."
USER_OUTPUT=$(docker exec "$APP_CONTAINER" php artisan firefly-iii:create-first-user "$TEST_EMAIL" 2>&1) || true
echo "    $USER_OUTPUT"

# Extract password from output (format: "Created new admin user with email ... and password ...")
USER_PASSWORD=$(echo "$USER_OUTPUT" | grep -oP 'password \K\S+' || echo "")
if [ -z "$USER_PASSWORD" ]; then
    echo "    (User may already exist, proceeding with token generation)"
fi

echo "==> Ensuring Passport personal access client exists..."
docker exec "$APP_CONTAINER" php artisan passport:client --personal --name="Integration Test" --no-interaction 2>&1 || true

echo "==> Generating Personal Access Token..."
TOKEN=$(docker exec "$APP_CONTAINER" php artisan tinker --execute="
    \$user = \FireflyIII\User::where('email', '$TEST_EMAIL')->first();
    if (!\$user) { echo 'ERROR: User not found'; exit(1); }
    \$token = \$user->createToken('integration-test')->accessToken;
    echo \$token;
" 2>&1)

# Clean up the token — tinker may output extra info
TOKEN=$(echo "$TOKEN" | tail -1 | tr -d '[:space:]')

if [ -z "$TOKEN" ] || echo "$TOKEN" | grep -qi "error"; then
    echo "ERROR: Failed to generate token. Output: $TOKEN"
    echo "==> Attempting alternative token creation..."
    # Fallback: try via the registration endpoint if available
    TOKEN=$(docker exec "$APP_CONTAINER" php artisan tinker --execute="
        \$user = \FireflyIII\User::first();
        if (!\$user) { echo 'NO_USER'; exit(1); }
        \$token = \$user->createToken('fallback-test')->accessToken;
        echo \$token;
    " 2>&1 | tail -1 | tr -d '[:space:]')
fi

echo "    Token: ${TOKEN:0:20}..."

echo "==> Verifying token with Firefly III API..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Accept: application/json" \
    "http://localhost:8080/api/v1/about")

if [ "$HTTP_CODE" = "200" ]; then
    echo "    API verification successful (HTTP $HTTP_CODE)"
else
    echo "    WARNING: API returned HTTP $HTTP_CODE — token may not work"
    echo "    Trying /api/v1/about response:"
    curl -s -H "Authorization: Bearer $TOKEN" -H "Accept: application/json" \
        "http://localhost:8080/api/v1/about" | head -5
fi

echo "==> Writing .env.test file..."
cat > "$ENV_FILE" <<ENVEOF
FIREFLY_URL=http://localhost:8080
FIREFLY_TOKEN=$TOKEN
FIREFLY_IMPORTER_URL=http://localhost:8081
FIREFLY_IMPORTER_SECRET=$IMPORTER_SECRET
ENVEOF

echo "    Written to $ENV_FILE"

echo "==> Restarting importer with real token..."
export FIREFLY_TOKEN="$TOKEN"
docker compose -f "$COMPOSE_FILE" up -d importer 2>&1

echo ""
echo "============================================"
echo "  Integration environment ready!"
echo "  Firefly III:    http://localhost:8080"
echo "  Data Importer:  http://localhost:8081"
echo "  .env file:      $ENV_FILE"
echo "============================================"
