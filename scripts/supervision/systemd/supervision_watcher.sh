#!/bin/bash
set -euo pipefail
export PATH="/home/alexey/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$PATH"

REPO_ROOT="/home/alexey/git/cloudflare-agent-git"
cd "$REPO_ROOT"

function restart_supervision() {
    if [ -n "${PYTEST_CURRENT_TEST:-}" ] || [ "${SUPERVISION_TEST_MODE:-0}" = "1" ] || [ "${SUPERVISION_WATCHER_DRY_RUN:-0}" = "1" ]; then
        echo "Diagnostic: test/dry-run mode active. Skipping systemctl execution."
        exit 0
    fi
    systemctl --user restart supervision.service
}

# Check if experiment-supervision is alive
if ! python3 -c "
import subprocess, json
out = subprocess.check_output(['aplexer', 'status', 'experiment-supervision', '--json'], stderr=subprocess.DEVNULL)
d = json.loads(out)
if not d.get('worker_alive') or d.get('state') == 'broken':
    exit(1)
" >/dev/null 2>&1; then
    echo "Supervisor is down or missing. Restarting..."
    restart_supervision
else
    # Check if status.json is fresh (updated in last 600s, accommodating task runs)
    STATUS_AGE=$(stat -c %Y "$REPO_ROOT/.local/supervision/status.json" 2>/dev/null || echo 0)
    NOW=$(date +%s)
    if [ $((NOW - STATUS_AGE)) -gt 600 ]; then
        echo "Supervisor is alive but status.json is stale (>600s). Restarting..."
        restart_supervision
    else
        echo "Supervisor is healthy."
    fi
fi

# Automated metrics rolling retention under 192 MiB pressure
if [ -f "$REPO_ROOT/scripts/metrics/adapters.py" ]; then
    python3 "$REPO_ROOT/scripts/metrics/adapters.py" --json >/dev/null 2>&1 || true
fi
