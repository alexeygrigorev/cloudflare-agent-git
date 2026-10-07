#!/usr/bin/env bash
# Every scripts/ path that the docs name as installed must exist, and a script
# must be executable. Executable contract (platform-independent):
#   - data files (.service .timer .md .json .yml .yaml .txt .toml) are exempt;
#   - a tracked script is executable when its git index mode is 100755
#     (`git ls-files -s`), because the filesystem bit is unreliable on MSYS/NTFS;
#   - an untracked script falls back to the filesystem bit;
#   - a shebang is not required.
# Gaps that are known and tracked go in KNOWN_GAPS with an issue number; they are
# reported on every run, never skipped silently. A gap that has been fixed must be
# removed from the list (the check fails on stale entries).
set -u
root=$(cd "$(dirname "$0")/../.." && pwd)
cd "$root" || exit 2

# path|issue
KNOWN_GAPS=(
  "scripts/recover-agent|102"
  "scripts/supervision/service.py|104"
)

fail=0
docs=$(grep -rhoE 'scripts/[A-Za-z0-9_.-]+(/[A-Za-z0-9_.-]+)*' _docs AGENTS.md 2>/dev/null \
  | sed -E 's/[.,;:)]+$//' | sort -u)

gap_issue() {
  local g
  for g in "${KNOWN_GAPS[@]}"; do
    [ "${g%%|*}" = "$1" ] && { echo "${g##*|}"; return 0; }
  done
  return 1
}

is_data() {
  case "$1" in
    *.service|*.timer|*.md|*.json|*.yml|*.yaml|*.txt|*.toml) return 0;;
  esac
  return 1
}

is_exec() {
  local mode
  mode=$(git ls-files -s -- "$1" 2>/dev/null | awk 'NR==1{print $1}')
  if [ -n "$mode" ]; then [ "$mode" = "100755" ]; else [ -x "$1" ]; fi
}

for p in $docs; do
  [ -d "$p" ] && continue          # directory references are not scripts
  case "$(basename "$p")" in test_*) continue;; esac  # tests are run, not installed
  if issue=$(gap_issue "$p"); then
    if [ -e "$p" ] && is_exec "$p"; then
      echo "STALE ALLOWLIST: $p now exists and is executable; remove it from KNOWN_GAPS (issue $issue)"; fail=1
    else
      echo "KNOWN GAP: $p is advertised but missing or not executable (issue $issue)"
    fi
    continue
  fi
  if [ ! -e "$p" ]; then echo "MISSING: $p is named in the docs but does not exist"; fail=1
  elif is_data "$p"; then :
  elif ! is_exec "$p"; then echo "NOT EXECUTABLE: $p"; fail=1
  fi
done

for g in "${KNOWN_GAPS[@]}"; do
  grep -qx "${g%%|*}" <<<"$docs" || { echo "STALE ALLOWLIST: ${g%%|*} is no longer named in the docs"; fail=1; }
done
exit $fail
