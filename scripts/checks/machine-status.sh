#!/usr/bin/env bash
# Fail when current docs state a machine's present on/off/offline status.
# Availability belongs in coordination/MACHINES.json; reachability is probed at
# run time. Journal, incidents, research archives and experiment notes are out
# of scope (history may record past events).
set -u
here=$(cd "$(dirname "$0")" && pwd)
cd "$here/../.." || exit 2
. scripts/checks/lib.sh
. scripts/checks/lib/principal-override.sh
check_parse_args "$@"

# Paths that may describe past events or research, not current operating status.
SKIP_PREFIXES=(
  "_docs/founder-journal/"
  "_docs/incidents/"
  "_docs/research/"
  "research/"
  "experiment/"
  "website/"
  "docs-submission/"
)

skip_path() {
  local p=$1 d
  for d in "${SKIP_PREFIXES[@]}"; do
    [[ $p == "$d"* ]] && return 0
  done
  return 1
}

# Phrases that assert a machine's current power/reachability state.
# Avoid bare "offline" so capability phrases like "offline recovery" stay allowed.
PATTERN='temporarily offline|currently offline|currently online|is offline since|offline since about|when it is back|when it'\''s back|heads and cross-computer work resume on it|heads resume on it'

bad=0
while IFS= read -r path; do
  [ -n "$path" ] || continue
  skip_path "$path" && continue
  case "$path" in
    *.md|AGENTS.md) ;;
    *) continue ;;
  esac
  [ -f "$path" ] || continue
  # Whole-file scan for current docs: status wording is wrong even if pre-existing.
  if grep -nEi "$PATTERN" -- "$path" >/tmp/machine-status-hits.$$ 2>/dev/null; then
    while IFS= read -r hit; do
      echo "machine-status: $path:$hit"
      bad=1
    done < /tmp/machine-status-hits.$$
  fi
done < <(
  if [ "${CHECK_MODE:-staged}" = all ] || [ "${CHECK_MODE:-}" = range ]; then
    # Operating docs that must not carry current on/off status.
    printf '%s\n' AGENTS.md
    find _docs recovery coordination -type f -name '*.md' 2>/dev/null | sort
  else
    # Staged mode: still scan the living operating docs (status is about content now).
    printf '%s\n' AGENTS.md
    find _docs recovery coordination -type f -name '*.md' 2>/dev/null | sort
  fi
)
rm -f /tmp/machine-status-hits.$$

if [ $bad -eq 1 ] && principal_override machine-status "${PRINCIPAL_OVERRIDE:+Principal-Override: $PRINCIPAL_OVERRIDE}"; then
  exit 0
fi
exit $bad
