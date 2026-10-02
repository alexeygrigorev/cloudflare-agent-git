#!/usr/bin/env bash
set -euo pipefail
repo=/home/alexey/git/cloudflare-agent-git
python3 "$repo/scripts/quota-gate.py"
exec /home/alexey/.nvm/versions/node/v24.13.1/bin/codex "$@"
