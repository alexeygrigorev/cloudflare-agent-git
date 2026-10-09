#!/usr/bin/env bash
# Install or check the end-of-turn "is the wake armed" hook (scripts/ping/turn-end-check.py) in ONE project.
#   install-turn-end-hooks.sh <project-dir> [--engine claude|codex|zcodex|gemini|opencode|all] [--check] [--join] [--with-inbox]
# --with-inbox additionally registers (or, with --check, checks) the incoming-message hook scripts/ping/inbox-guard.py:
# claude gets UserPromptSubmit + Stop entries, codex/zcodex a Stop entry; gemini and opencode have no verified hook
# format for it and report status=unsupported (ask-wake-runner.py --inbox covers every engine).
# Project scope only: every write stays under <project-dir>; user-global engine configs are never touched.
# Opt-in: the project must carry .follows-principal-process. Without it, install refuses (exit 4) unless --join
# is given, which creates the marker first. --check on a markerless project reports "not in scope" and exits 0.
# --check prints one line per engine (engine=<e> status=installed|missing) and exits 3 if any is missing.
exec python3 - "$0" "$@" <<'PY'
import json, os, sys

self_path, *argv = sys.argv[1:]
check_script = os.path.join(os.path.dirname(os.path.abspath(self_path)), "turn-end-check.py")
ENGINES = ["claude", "codex", "zcodex", "gemini", "opencode"]
proj = None; engine = "all"; check = False; join = False; with_inbox = False
inbox_script = os.path.join(os.path.dirname(os.path.abspath(self_path)), "inbox-guard.py")
it = iter(argv)
for a in it:
    if a == "--engine": engine = next(it, "")
    elif a == "--check": check = True
    elif a == "--with-inbox": with_inbox = True
    elif a == "--join": join = True
    elif a.startswith("-"): sys.exit(f"unknown option {a}")
    elif proj is None: proj = a
    else: sys.exit("usage: install-turn-end-hooks.sh <project-dir> [--engine E|all] [--check] [--join]")
if proj is None or not os.path.isdir(proj):
    sys.exit("usage: install-turn-end-hooks.sh <project-dir> [--engine E|all] [--check] [--join]")
if engine != "all" and engine not in ENGINES:
    sys.exit(f"unknown engine {engine}")
proj = os.path.realpath(proj)
engines = ENGINES if engine == "all" else [engine]
marker = os.path.join(proj, ".follows-principal-process")

def inside(p):
    return os.path.realpath(p).startswith(proj + os.sep)

def cmd(fmt):
    return f"[ -f {check_script} ] && python3 {check_script} --format {fmt} || exit 0"  # a missing script never blocks

def has_entry(d, event, script="turn-end-check.py"):
    return any(script in h.get("command", "") for e in d.get("hooks", {}).get(event, []) for h in e.get("hooks", []))

# engine -> [(event, inbox-guard --format)]; engines not listed have no verified hook format for inbox-guard
INBOX_EVENTS = {"claude": [("UserPromptSubmit", "claude-prompt"), ("Stop", "claude-stop")],
                "codex": [("Stop", "claude-stop")], "zcodex": [("Stop", "claude-stop")]}

def inbox_cmd(fmt):
    return f"[ -f {inbox_script} ] && python3 {inbox_script} --format {fmt} || exit 0"

def inbox_installed(e):
    d = load(os.path.join(proj, paths(e)))
    return bool(d) and all(has_entry(d, ev, "inbox-guard.py") for ev, _ in INBOX_EVENTS[e])

def load(p):
    try:
        return json.load(open(p)) if os.path.getsize(p) else {}
    except OSError:
        return {}
    except ValueError:
        return None

def paths(e):
    return {"claude": ".claude/settings.json", "codex": ".codex/hooks.json", "zcodex": ".codex/hooks.json",
            "gemini": ".gemini/settings.json", "opencode": ".opencode/plugin/turn-end-check.js"}[e]

def installed(e):
    p = os.path.join(proj, paths(e))
    if e == "opencode":
        try: return "turn-end-check.py" in open(p).read()
        except OSError: return False
    d = load(p)
    return bool(d) and has_entry(d, "AfterAgent" if e == "gemini" else "Stop")

PLUGIN = """// Project-scope OpenCode plugin (scripts/ping/install-turn-end-hooks.sh): when the session goes idle, run
// turn-end-check.py, which reminds this session over the bus if it waits without an armed wake.
import child_process from "node:child_process";
export const TurnEndCheck = async () => ({
  event: async ({ event }) => {
    if (event?.type !== "session.idle") return;
    try {
      child_process.spawnSync("python3", ["%s", "--format", "plain", "--also-bus"],
        { stdio: "ignore", timeout: 15000, cwd: process.cwd() });
    } catch (_) {}
  },
});
"""

def write_json(p, d):
    assert inside(p), p
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w") as f:
        json.dump(d, f, indent=2); f.write("\n")
    os.replace(tmp, p)

def install(e):
    p = os.path.join(proj, paths(e))
    if not inside(p):
        print(f"engine={e} status=refused (path escapes project)"); return
    if e == "opencode":
        if not installed(e):
            os.makedirs(os.path.dirname(p), exist_ok=True)
            open(p, "w").write(PLUGIN % check_script)
        print(f"engine={e} status=installed ({paths(e)})"); return
    d = load(p)
    if d is None:
        print(f"engine={e} status=refused ({paths(e)} is not valid JSON; left untouched)"); return
    event, fmt = ("AfterAgent", "plain") if e == "gemini" else ("Stop", "claude-stop")
    if not has_entry(d, event):
        d.setdefault("hooks", {}).setdefault(event, []).append({"hooks": [{"type": "command", "command": cmd(fmt)}]})
        write_json(p, d)
    print(f"engine={e} status=installed ({paths(e)})")

if not os.path.isfile(marker):
    if check:
        print("turn-end-hooks: no .follows-principal-process marker, not in scope"); sys.exit(0)
    if not join:
        print(f"turn-end-hooks: refusing: {proj} has no .follows-principal-process (not part of the org). "
              "Pass --join to opt this project in (creates the marker).", file=sys.stderr); sys.exit(4)
    open(marker, "a").close()
    print(f"turn-end-hooks: --join: created {marker}; this project now follows the principal process")

def install_inbox(e):
    p = os.path.join(proj, paths(e))
    if e not in INBOX_EVENTS:
        print(f"engine={e} inbox=unsupported (no verified hook format; use ask-wake-runner.py --inbox)"); return
    if not inside(p):
        print(f"engine={e} inbox=refused (path escapes project)"); return
    d = load(p)
    if d is None:
        print(f"engine={e} inbox=refused ({paths(e)} is not valid JSON; left untouched)"); return
    changed = False
    for ev, fmt in INBOX_EVENTS[e]:
        if not has_entry(d, ev, "inbox-guard.py"):
            d.setdefault("hooks", {}).setdefault(ev, []).append({"hooks": [{"type": "command", "command": inbox_cmd(fmt)}]})
            changed = True
    if changed:
        write_json(p, d)
    print(f"engine={e} inbox=installed ({paths(e)})")

missing = 0
for e in engines:
    if check:
        ok = installed(e)
        print(f"engine={e} status={'installed' if ok else 'missing'} ({paths(e)})")
        missing += not ok
    else:
        install(e)
    if with_inbox:
        if e not in INBOX_EVENTS:
            print(f"engine={e} inbox=unsupported (no verified hook format; use ask-wake-runner.py --inbox)")
        elif check:
            ok = inbox_installed(e)
            print(f"engine={e} inbox={'installed' if ok else 'missing'} ({paths(e)})")
            missing += not ok
        else:
            install_inbox(e)
if check and missing:
    sys.exit(3)
if not check:
    print("note: codex/zcodex ask you to trust a new project hook on first run; gemini likewise for project hooks.")
PY
