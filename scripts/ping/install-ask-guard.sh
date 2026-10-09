#!/usr/bin/env bash
# Idempotently add the ask-guard Stop hook to <project-dir>/.claude/settings.json (project scope only,
# never ~/.claude), keeping every other key. Usage: install-ask-guard.sh <project-dir> [guard-script]
# The guard script defaults to this repo's scripts/ping/stop-guard.py (absolute path).
set -eu
proj=${1:?usage: install-ask-guard.sh <project-dir> [guard-script]}
guard=${2:-$(cd "$(dirname "$0")" && pwd)/stop-guard.py}
mkdir -p "$proj/.claude"
python3 - "$proj/.claude/settings.json" "$guard" <<'PY'
import json, os, sys
p, guard = sys.argv[1:3]
cmd = f"[ -f {guard} ] && python3 {guard} || exit 0"  # a missing guard must never block stopping
d = json.load(open(p)) if os.path.exists(p) and os.path.getsize(p) else {}
stop = d.setdefault("hooks", {}).setdefault("Stop", [])
if not any(h.get("command") == cmd for e in stop for h in e.get("hooks", [])):
    stop.append({"hooks": [{"type": "command", "command": cmd}]})
    tmp = p + ".tmp"
    json.dump(d, open(tmp, "w"), indent=2); open(tmp, "a").write("\n")
    os.replace(tmp, p)
    print("installed ask-guard in", p)
else:
    print("ask-guard already installed in", p)
PY
