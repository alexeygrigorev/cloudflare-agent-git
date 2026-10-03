#!/usr/bin/env bash
# agents/launch.sh - Real-Agent Harness Launcher for Agent Branches (L6)
#
# Launches concurrent real coding agents across demo tasks with:
# - L1 task registration via L2 client
# - Isolated fork/workspace setup
# - Concurrent aplexer agent sessions (zcodex, Space Bunny, Grok) or reference dry-run
# - L3 radar evaluation on push events posting CONTRACT v0.1 checks
# - Full chronological timeline JSON recording
#
# Usage:
#   ./agents/launch.sh --dry-run                           # Test harness using reference patches
#   ./agents/launch.sh --engine-mode zcodex                # Run real zcodex agents
#   ./agents/launch.sh --engine-mode multi-model           # Compete zcodex vs Space Bunny vs Grok
#   ./agents/launch.sh --server http://127.0.0.1:8787      # Target running L1 stack

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Ensure harness root is on PYTHONPATH
export PYTHONPATH="${WORKSPACE_ROOT}:${PYTHONPATH:-}"

# Defaults from environment
SERVER_URL="${AGENT_BRANCHES_SERVER_URL:-${SERVER_URL:-http://127.0.0.1:8787}}"
ADMIN_TOKEN="${ADMIN_TOKEN:-demo-admin-token}"
RUNNER_TOKEN="${RUNNER_TOKEN:-demo-runner-token}"

# Parse leading flags or forward directly to driver.py
ARGS=()
HAS_SERVER=false
HAS_ADMIN=false
HAS_RUNNER=false

for arg in "$@"; do
    case "$arg" in
        --server=*)
            HAS_SERVER=true
            ;;
        --server)
            HAS_SERVER=true
            ;;
        --admin-token=*)
            HAS_ADMIN=true
            ;;
        --admin-token)
            HAS_ADMIN=true
            ;;
        --runner-token=*)
            HAS_RUNNER=true
            ;;
        --runner-token)
            HAS_RUNNER=true
            ;;
    esac
    ARGS+=("$arg")
done

# If server or tokens were not explicitly passed in args, inject environment defaults
INJECTED_ARGS=()
if [ "$HAS_SERVER" = false ]; then
    INJECTED_ARGS+=(--server "${SERVER_URL}")
fi
if [ "$HAS_ADMIN" = false ]; then
    INJECTED_ARGS+=(--admin-token "${ADMIN_TOKEN}")
fi
if [ "$HAS_RUNNER" = false ]; then
    INJECTED_ARGS+=(--runner-token "${RUNNER_TOKEN}")
fi

exec python3 "${WORKSPACE_ROOT}/agents/driver.py" "${INJECTED_ARGS[@]}" "${ARGS[@]}"
