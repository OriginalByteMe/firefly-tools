#!/usr/bin/env bash
#
# Run the full Firefly III MCP integration test suite.
#
# Usage:
#   ./integration/run.sh           # Full run: start services, test, tear down
#   ./integration/run.sh --keep    # Keep services running after tests
#   ./integration/run.sh --test    # Skip bootstrap, just run tests (services must be up)
#   ./integration/run.sh --down    # Tear down services only
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.yml"

KEEP=false
TEST_ONLY=false
DOWN_ONLY=false

for arg in "$@"; do
    case $arg in
        --keep) KEEP=true ;;
        --test) TEST_ONLY=true ;;
        --down) DOWN_ONLY=true ;;
    esac
done

teardown() {
    echo "==> Tearing down Docker services..."
    docker compose -f "$COMPOSE_FILE" down -v --remove-orphans 2>&1
    rm -f "$SCRIPT_DIR/.env.test"
    echo "    Done."
}

if [ "$DOWN_ONLY" = true ]; then
    teardown
    exit 0
fi

if [ "$TEST_ONLY" = false ]; then
    # Bootstrap: start services and configure
    echo "============================================"
    echo "  Phase 1: Bootstrap Firefly III"
    echo "============================================"
    "$SCRIPT_DIR/bootstrap.sh"
    echo ""
fi

# Run integration tests
echo "============================================"
echo "  Phase 2: Run Integration Tests"
echo "============================================"

cd "$REPO_ROOT"
uv run --extra dev pytest integration/test_mcp_tools.py -v --tb=short 2>&1
TEST_EXIT=$?

if [ "$KEEP" = false ] && [ "$TEST_ONLY" = false ]; then
    echo ""
    echo "============================================"
    echo "  Phase 3: Teardown"
    echo "============================================"
    teardown
fi

echo ""
if [ $TEST_EXIT -eq 0 ]; then
    echo "ALL INTEGRATION TESTS PASSED"
else
    echo "SOME INTEGRATION TESTS FAILED (exit code: $TEST_EXIT)"
fi

exit $TEST_EXIT
