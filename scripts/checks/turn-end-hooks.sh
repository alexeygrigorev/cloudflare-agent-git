#!/usr/bin/env bash
# Projects that follow the principal process (marker .follows-principal-process) should have the end-of-turn
# wake reminder hook installed. Claude is checked (fails when missing); other engines only warn.
# Install with scripts/ping/install-turn-end-hooks.sh <project-dir>. Projects without the marker are skipped.
set -u
root=$(cd "$(dirname "$0")/../.." && pwd)
cd "$root" || exit 2
[ -f .follows-principal-process ] || { echo "turn-end-hooks: no .follows-principal-process marker, skipped"; exit 0; }
for f in scripts/ping/turn-end-check.py scripts/ping/install-turn-end-hooks.sh; do
  [ -x "$f" ] || { echo "turn-end-hooks: missing or not executable: $f"; exit 1; }
done
# .claude/settings.json is local in some projects; CI and linked worktrees cannot see it, so there a missing
# file is skipped / warned (same rule as ask-guard.sh).
if [ ! -f .claude/settings.json ] && [ -n "${CI:-}" ]; then echo "turn-end-hooks: ok (CI: local settings not visible)"; exit 0; fi
if [ ! -f .claude/settings.json ] && [ "$(git rev-parse --git-dir 2>/dev/null)" != "$(git rev-parse --git-common-dir 2>/dev/null)" ]; then
  echo "turn-end-hooks: warn: no .claude/settings.json in this linked worktree; the primary checkout is checked"; exit 0
fi
out=$(scripts/ping/install-turn-end-hooks.sh . --check --engine all); fail=0
while read -r line; do
  eng=${line#engine=}; eng=${eng%% *}
  case "$line" in
    *status=missing*)
      if [ "$eng" = claude ]; then echo "turn-end-hooks: Stop hook for turn-end-check.py missing for claude (run scripts/ping/install-turn-end-hooks.sh . --engine claude)"; fail=1
      else echo "turn-end-hooks: warn: $eng hook missing (scripts/ping/install-turn-end-hooks.sh . --engine $eng)"; fi ;;
  esac
done <<< "$out"
[ "$fail" = 0 ] && echo "turn-end-hooks: ok"
exit "$fail"
