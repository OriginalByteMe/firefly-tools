#!/usr/bin/env bash
#
# Bootstrap script for Firefly III integration test environment.
#
# 1. Starts Docker Compose services (Firefly III + MariaDB + Data Importer)
# 2. Waits for Firefly III to be healthy
# 3. Runs database migrations and upgrades
# 4. Creates a test user and Personal Access Token via inline PHP
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

echo "==> Running Firefly III database upgrade & corrections..."
docker exec "$APP_CONTAINER" php artisan firefly-iii:upgrade-database 2>&1 || true
docker exec "$APP_CONTAINER" php artisan firefly-iii:correct-database 2>&1 || true

echo "==> Setting up Passport encryption keys..."
docker exec "$APP_CONTAINER" php artisan firefly-iii:laravel-passport-keys 2>&1 \
    || docker exec "$APP_CONTAINER" php artisan passport:keys --force --no-interaction 2>&1 \
    || true
docker exec "$APP_CONTAINER" php artisan passport:client --personal --name="Integration Test" --no-interaction 2>&1 || true

echo "==> Creating test user and generating Personal Access Token..."
# Use inline PHP to create the user and token in one step. This avoids
# depending on artisan commands that change names across Firefly III versions
# (firefly-iii:create-first-user vs system:create-first-user) and on artisan
# tinker which was removed entirely in v6.x.
TOKEN=$(docker exec "$APP_CONTAINER" php -r '
    require "/var/www/html/vendor/autoload.php";
    $app = require_once "/var/www/html/bootstrap/app.php";
    $app->make("Illuminate\Contracts\Console\Kernel")->bootstrap();

    use FireflyIII\User;
    use Illuminate\Support\Facades\Hash;

    $email = "'"$TEST_EMAIL"'";

    // Find or create the test user
    $user = User::where("email", $email)->first();
    if (!$user) {
        $user = User::create([
            "email" => $email,
            "password" => Hash::make("test-password-integration"),
        ]);
        // Assign admin role if the method exists
        if (method_exists($user, "assignRole")) {
            try { $user->assignRole("owner"); } catch (\Throwable $e) {}
        }
        fwrite(STDERR, "Created user: $email (ID #{$user->id})\n");
    } else {
        fwrite(STDERR, "User already exists: $email (ID #{$user->id})\n");
    }

    // Generate a Personal Access Token via Passport
    $token = $user->createToken("integration-test")->accessToken;
    echo $token;
' 2>/tmp/user_creation.log) || true

# Show user creation log
if [ -f /tmp/user_creation.log ]; then
    cat /tmp/user_creation.log
fi

# Clean up — strip whitespace to be safe
TOKEN=$(echo "$TOKEN" | tail -1 | tr -d '[:space:]')

if [ -z "$TOKEN" ] || echo "$TOKEN" | grep -qi "error"; then
    echo "ERROR: Could not generate a Personal Access Token."
    echo "       Token output: $TOKEN"
    # Dump any PHP errors
    docker exec "$APP_CONTAINER" cat /var/www/html/storage/logs/laravel.log 2>/dev/null | tail -30 || true
    exit 1
fi

echo "    Token: ${TOKEN:0:20}..."

echo "==> Verifying token with Firefly III API..."
# Use /api/v1/accounts (authenticated) to verify the token actually works
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Accept: application/json" \
    "http://localhost:8080/api/v1/accounts")

if [ "$HTTP_CODE" = "200" ]; then
    echo "    API verification successful (HTTP $HTTP_CODE)"
else
    echo "    WARNING: API returned HTTP $HTTP_CODE — token may not work"
    echo "    Response from /api/v1/accounts:"
    curl -s -H "Authorization: Bearer $TOKEN" -H "Accept: application/json" \
        "http://localhost:8080/api/v1/accounts" | head -10
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
