#!/usr/bin/env bash
# Claim-before-edit check on staged files. Skips cleanly without aplexer (e.g. CI).
set -u
here="$(cd "$(dirname "$0")" && pwd)"
if [ -n "${CI:-}" ] || ! command -v aplexer >/dev/null 2>&1 || ! aplexer context --json >/dev/null 2>&1; then
  echo "claims: skipped (aplexer unavailable)"; exit 0
fi
exec python3 "$here/../guards/claims_check.py" "$@"
