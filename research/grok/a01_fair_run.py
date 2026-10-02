#!/usr/bin/env python3
"""Launch one fair arm: two bound z.ai writers, then leave the trees for scoring."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path("/home/alexey/git/cloudflare-agent-git")
SCRATCH = Path("/tmp/grok-a01-fair-20261002")
FLOOR = 8 * 1024 ** 3


def free_bytes(path):
    st = os.statvfs(path)
    return st.f_bavail * st.f_frsize


def quota_ok():
    proc = subprocess.run(["quse", "zai", "--json"], capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(f"quse failed: {proc.stderr[:400]}")
    data = json.loads(proc.stdout)
    zai = data["zai"]
    details = zai["details"]
    summary = {
        "status": zai.get("status"),
        "limit_reached": details.get("limit_reached"),
        "five_hour_used_percent": details["windows"]["five_hour"]["used_percent"],
        "weekly_used_percent": details["windows"]["weekly"]["used_percent"],
        "percent_remaining_5h": zai["windows"]["5h"]["percent_remaining"],
        "percent_remaining_7d": zai["windows"]["7d"]["percent_remaining"],
    }
    print(json.dumps({"quse": summary}), flush=True)
    if zai.get("status") != "ok" or details.get("limit_reached") is not False:
        raise SystemExit("z.ai quota gate closed")
    if summary["percent_remaining_5h"] is None or summary["percent_remaining_7d"] is None:
        raise SystemExit("z.ai remaining unknown")
    if summary["percent_remaining_5h"] <= 0 or summary["percent_remaining_7d"] <= 0:
        raise SystemExit("z.ai remaining exhausted")
    return summary


def start_agent(arm, role, prompt):
    tag = f"grok-a01-fair-{arm}-{role.lower()}"
    repo = SCRATCH / arm / role
    proc = subprocess.run(
        [
            "aplexer", "start", "--json",
            "--workspace", str(ROOT),
            "--tag", tag,
            "--engine", "zcodex",
            "--cwd", str(repo),
            "--memory", "512M",
            "--pids", "64",
            "--no-skip-permissions",
            "--",
            "timeout", "20m",
            "zcodex", "exec",
            "--dangerously-bypass-approvals-and-sandbox",
            "--skip-git-repo-check",
            "-c", 'model="glm-5.3-flash"',
            "-c", 'model_provider="zcode"',
            "-o", "final.md",
            prompt,
        ],
        capture_output=True, text=True,
    )
    print(json.dumps({"start": tag, "exit": proc.returncode, "stdout": proc.stdout[-2000:], "stderr": proc.stderr[-2000:]}), flush=True)
    if proc.returncode != 0:
        raise SystemExit(f"start failed for {tag}")
    return tag


def session_states(tags):
    """Return matching rows, or None when the list command itself fails."""
    proc = subprocess.run(["aplexer", "list", "--json"], capture_output=True, text=True)
    if proc.returncode != 0:
        return None
    try:
        rows = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None
    found = {}
    for row in rows:
        if row.get("tag") in tags:
            found[row["tag"]] = {
                "id": row.get("id"),
                "state": row.get("state"),
                "reported_state": row.get("reported_state"),
            }
    return found


def main():
    arm = sys.argv[1]
    if arm not in ("completion", "live"):
        raise SystemExit("usage: a01_fair_run.py completion|live")
    for path in ("/", "/tmp"):
        free = free_bytes(path)
        print(json.dumps({"path": path, "free": free}), flush=True)
        if free < FLOOR:
            raise SystemExit(f"free space below 8 GiB on {path}")
    quota_ok()
    prompt_a = (SCRATCH / "prompt-A.md").read_text()
    prompt_b = (SCRATCH / "prompt-B.md").read_text()
    if prompt_a == prompt_b:
        raise SystemExit("role prompts unexpectedly identical")
    stop = SCRATCH / f"stop-{arm}"
    if stop.exists():
        stop.unlink()
    publisher = subprocess.Popen(
        [sys.executable, str(ROOT / "research/grok/a01_fair_publish.py"), arm],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    tags = []
    try:
        tags = [start_agent(arm, "A", prompt_a), start_agent(arm, "B", prompt_b)]
        deadline = time.time() + 22 * 60
        observed = {}
        ever_running = set()
        absent_streak = 0
        reason = "deadline"
        while time.time() < deadline:
            states = session_states(tags)
            if states is None:
                absent_streak = 0
                (SCRATCH / f"poll-{arm}.jsonl").open("a", encoding="utf-8").write(
                    json.dumps({"list": "unknown"}) + "\n"
                )
                time.sleep(20)
                continue
            for tag, row in states.items():
                observed[tag] = row
                if row.get("state") == "running":
                    ever_running.add(tag)
            running = [tag for tag, row in states.items() if row.get("state") == "running"]
            reaped = bool(tags) and all(tag in ever_running for tag in tags) and not states
            absent_streak = absent_streak + 1 if reaped else 0
            (SCRATCH / f"poll-{arm}.jsonl").open("a", encoding="utf-8").write(
                json.dumps({
                    "running": running,
                    "states": states,
                    "absent_streak": absent_streak,
                }) + "\n"
            )
            if states and not running:
                reason = "all-listed-not-running"
                break
            if absent_streak >= 2:
                reason = "absent-after-observed-running"
                break
            time.sleep(20)
        else:
            if not all(tag in ever_running for tag in tags):
                reason = "start-unobserved"
            print(json.dumps({"timeout": tags, "reason": reason}), flush=True)
        final = session_states(tags)
        disposition = {}
        for tag in tags:
            if tag not in ever_running:
                disposition[tag] = "start-unobserved"
            elif final and tag in final:
                disposition[tag] = "listed-" + str(final[tag].get("state"))
            else:
                disposition[tag] = "absent-after-observed-running"
        terminal = {
            "reason": reason,
            "tags": tags,
            "ever_running": sorted(ever_running),
            "last_observed": observed,
            "final_list": final if final is not None else {},
            "list_unknown": final is None,
            "disposition": disposition,
        }
        (SCRATCH / f"sessions-{arm}.json").write_text(json.dumps(terminal, indent=2) + "\n")
        print(json.dumps({"lifecycle": reason, "disposition": disposition}), flush=True)
    finally:
        stop.write_text("stop\n")
        publisher.wait(timeout=30)
    print(json.dumps({"arm_done": arm}), flush=True)


if __name__ == "__main__":
    main()
