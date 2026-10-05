#!/bin/bash
set -euo pipefail

export PATH="/home/alexey/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$PATH"

if aplexer status experiment-supervision >/dev/null 2>&1; then
    echo "experiment-supervision is already running in aplexer"
else
    echo "Starting experiment-supervision in aplexer..."
    aplexer start --workspace /home/alexey/git/cloudflare-agent-git --tag experiment-supervision --engine shell -- python3 scripts/supervision/service.py
fi
