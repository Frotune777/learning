#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." &>/dev/null && pwd)"
cd "$PROJECT_ROOT"

LOG_DIR="$PROJECT_ROOT/logs/dq"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/dq_gate_cli.log"

format_log() {
    if command -v ts >/dev/null 2>&1; then
        ts "%Y-%m-%dT%H:%M:%S%z"
    else
        sed -u "s/^/$(date -Iseconds) /"
    fi
}

set +e
"$SCRIPT_DIR/dq_gate.sh" "$@" 2>&1 | format_log >> "$LOG_FILE"
EXIT_CODE="${PIPESTATUS[0]}"
set -e

exit "$EXIT_CODE"
