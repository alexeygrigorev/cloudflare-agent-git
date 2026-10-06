#!/bin/bash
set -euo pipefail

# Ensure no inherited aplexer session identity or caller cgroup context
unset APLEXER_SESSION_ID APLEXER_TAG APLEXER_WORKSPACE

export PATH="/home/alexey/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$PATH"

REPO_ROOT="/home/alexey/git/cloudflare-agent-git"
STOP_FILE="$REPO_ROOT/.local/supervision/stop"
LOCK_FILE="$REPO_ROOT/.local/supervision/service.lock"

# Check existing experiment-supervision status
STATUS=$(python3 -c "
import subprocess, json
try:
    out = subprocess.check_output(['aplexer', 'status', 'experiment-supervision', '--json'], stderr=subprocess.DEVNULL)
    d = json.loads(out)
    state = d.get('state') or ''
    worker_alive = d.get('worker_alive', False)
    parent = d.get('parent_session') or ''
    cgroup = d.get('workload_cgroup') or ''
    if state == 'broken' or not worker_alive:
        print('BROKEN:False')
    else:
        # Tethered if parent is set or if cgroup contains ant head session
        tethered = ('5e1abcdb' in cgroup) or (parent != '')
        print(f'EXISTS:{tethered}')
except Exception:
    print('ABSENT:False')
")

if [[ "$STATUS" == "EXISTS:True" || "$STATUS" == "BROKEN:False" ]]; then
    echo "Found tethered, broken, or dead experiment-supervision session. Purging..."
    touch "$STOP_FILE"
    for i in {1..10}; do
        if ! aplexer status experiment-supervision >/dev/null 2>&1; then
            break
        fi
        sleep 1
    done
    aplexer kill experiment-supervision >/dev/null 2>&1 || true
elif [[ "$STATUS" == "EXISTS:False" ]]; then
    echo "experiment-supervision is already running independently and healthy in aplexer"
    exit 0
fi

# Ensure stop file is removed before starting new service
rm -f "$STOP_FILE"

# Ensure status.json has an updated timestamp so watcher grace period begins
touch "$REPO_ROOT/.local/supervision/status.json" 2>/dev/null || true

# Wait for lock release if still held
for i in {1..15}; do
    if ! fuser "$LOCK_FILE" >/dev/null 2>&1; then
        break
    fi
    sleep 1
done

echo "Starting independent experiment-supervision in aplexer from systemd..."
aplexer start --workspace "$REPO_ROOT" --tag experiment-supervision --engine shell -- python3 scripts/supervision/service.py
