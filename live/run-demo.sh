#!/usr/bin/env bash
# live/run-demo.sh - Thin CLI wrapper for AB53 split runner runtime (task-0011)
set -euo pipefail

# Secure umask for sensitive files and logs
umask 077

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Ensure Node is on PATH for native git post-receive notify hook
if [[ -n "${NODE_BIN_DIR:-}" && -d "$NODE_BIN_DIR" ]]; then
    export PATH="$NODE_BIN_DIR:$PATH"
elif command -v node >/dev/null 2>&1; then
    NODE_DIR="$(dirname "$(command -v node)")"
    export PATH="$NODE_DIR:$PATH"
fi

if ! command -v node >/dev/null 2>&1; then
    echo "ERROR: node is required on PATH for native sidecar git hooks." >&2
    exit 1
fi

export PYTHONPATH="$ROOT:${PYTHONPATH:-}"

exec python3 "$ROOT/live/demo_runtime.py" "$@"
