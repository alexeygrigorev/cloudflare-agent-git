#!/usr/bin/env bash
# Projects that follow the principal process (marker file .follows-principal-process at the repo root)
# must have the ask-guard Stop hook in .claude/settings.json and the ledger tools present.
# Projects without the marker are skipped. Install with scripts/ping/install-ask-guard.sh <project-dir>.
set -u
root=$(cd "$(dirname "$0")/../.." && pwd)
cd "$root" || exit 2
[ -f .follows-principal-process ] || { echo "ask-guard: no .follows-principal-process marker, skipped"; exit 0; }
fail=0
for f in scripts/ping/ask-ledger.py scripts/ping/stop-guard.py; do
  [ -x "$f" ] || { echo "ask-guard: missing or not executable: $f"; fail=1; }
done
# .claude/settings.json is local (git-ignored or untracked) in some projects; CI cannot see it, so there
# the hook entry is checked only on machines that have the file (CI=true skips just that part).
# A linked git worktree does not carry local settings either: a missing file there only warns.
if [ ! -f .claude/settings.json ] && [ -n "${CI:-}" ]; then :
elif [ ! -f .claude/settings.json ] && [ "$(git rev-parse --git-dir 2>/dev/null)" != "$(git rev-parse --git-common-dir 2>/dev/null)" ]; then
  echo "ask-guard: warn: no .claude/settings.json in this linked worktree; the primary checkout is checked"
elif ! python3 - <<'PY'
import json, sys
try:
    d = json.load(open(".claude/settings.json"))
except Exception:
    sys.exit(1)
sys.exit(0 if any("stop-guard.py" in h.get("command", "") for e in d.get("hooks", {}).get("Stop", []) for h in e.get("hooks", [])) else 1)
PY
then echo "ask-guard: Stop hook entry for stop-guard.py missing in .claude/settings.json (run scripts/ping/install-ask-guard.sh .)"; fail=1; fi
[ "$fail" = 0 ] && echo "ask-guard: ok"
exit "$fail"
