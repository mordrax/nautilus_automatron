#!/usr/bin/env bash
# Sets up local (private) dependencies if available.
# Safe to run multiple times. Skips gracefully if private repos don't exist.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
NAUTILUS_STRATEGIES_PATH="${NAUTILUS_STRATEGIES_PATH:-/Users/mordrax/code/nautilus_strategies}"
RUNNER_DIR="$PROJECT_ROOT/packages/runner"
SERVER_DIR="$PROJECT_ROOT/packages/server"

# Install nautilus_strategies if the repo exists
if [ -d "$NAUTILUS_STRATEGIES_PATH" ]; then
    echo "Installing nautilus_strategies from $NAUTILUS_STRATEGIES_PATH..."

    if [ -d "$RUNNER_DIR/.venv" ]; then
        cd "$RUNNER_DIR" && uv pip install -e "$NAUTILUS_STRATEGIES_PATH"
    fi

    if [ -d "$SERVER_DIR/.venv" ]; then
        cd "$SERVER_DIR" && uv pip install -e "$NAUTILUS_STRATEGIES_PATH"
    fi

    echo "  nautilus_strategies installed"
else
    echo "nautilus_strategies not found at $NAUTILUS_STRATEGIES_PATH — skipping"
    echo "  Set NAUTILUS_STRATEGIES_PATH env var to override"
fi

# Copy strategies_local.py from example if it doesn't exist
LOCAL_FILE="$RUNNER_DIR/runner/strategies_local.py"
EXAMPLE_FILE="$RUNNER_DIR/runner/strategies_local.py.example"

if [ ! -f "$LOCAL_FILE" ] && [ -f "$EXAMPLE_FILE" ]; then
    if [ -d "$NAUTILUS_STRATEGIES_PATH" ]; then
        echo "Creating strategies_local.py (uncommented — nautilus_strategies found)..."
        sed 's/^# //' "$EXAMPLE_FILE" | sed 's/^#$//' > "$LOCAL_FILE"
    else
        echo "Creating strategies_local.py (commented — nautilus_strategies not found)..."
        cp "$EXAMPLE_FILE" "$LOCAL_FILE"
    fi
elif [ -f "$LOCAL_FILE" ]; then
    echo "strategies_local.py already exists — skipping"
fi

echo "Local setup complete."
