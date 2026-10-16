#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." &>/dev/null && pwd)"
cd "$PROJECT_ROOT"

if ! command -v uv >/dev/null 2>&1; then
    echo "ERROR: uv is not installed or not in PATH" >&2
    exit 2
fi

echo "=== DQ Gate: $(date -Iseconds) ==="

set +e
uv run python main.py dq-check "$@"
EXIT_CODE=$?
set -e

echo "=== DQ Gate: exit=$EXIT_CODE ==="
exit "$EXIT_CODE"
