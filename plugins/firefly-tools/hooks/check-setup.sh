#!/usr/bin/env bash
# Checks if .env is configured. Outputs a hint if not.
# Used by SessionStart hook to remind users to run /firefly-tools:setup

PLUGIN_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$PLUGIN_ROOT/.env"

if [ ! -f "$ENV_FILE" ]; then
    echo "Firefly III is not configured yet. Run /firefly-tools:setup to get started."
    exit 0
fi

if grep -q "REPLACE_WITH" "$ENV_FILE"; then
    echo "Firefly III setup is incomplete — some credentials are still placeholders. Run /firefly-tools:setup to finish."
    exit 0
fi

# All good — no output needed
