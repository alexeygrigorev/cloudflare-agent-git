#!/usr/bin/env bash
# Principal metrics entrypoint. Run on every ping cycle and at least every 30 minutes.
# Usage: scripts/principal-metrics.sh [--json] [--repos a,b] [--no-write]
# Exit 0 on target, 1 off target, 2 critical data unknown. Logic: scripts/principal_metrics.py
exec python3 "$(dirname "$0")/principal_metrics.py" "$@"
