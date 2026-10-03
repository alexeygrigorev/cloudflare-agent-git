#!/usr/bin/env python3
"""A01 Unscored Engineering Feasibility Gate Runner (3 Paired Trials / 6 Agent Sessions)

Executes the protocol specified in r12-a01-natural-hazard-preregistration.md (v2.2, commit 9412520,
prospective roster addendum f588508) authorized by Codex Principal (C-1281) and Claude Principal (01a10186, 01a10187):
1. Standardized model route: opencode-go/muse-spark-1.3-contributor across all 3 arms (6 sessions).
2. Arm 1a: Silent Isolation (Pair 1: Producer + Consumer)
3. Arm 1b: Cheap Incumbent / Intent Note (Pair 2: Producer + Consumer)
4. Arm 2: Live Collision Radar Warning (Pair 3: Producer + Consumer)
5. Execution containment: cgroups --memory 1500M --pids 256 per session.
6. Isolated worktrees under .local/a01-feasibility/<arm>/{producer,consumer}.
7. Procedural separation: Grader (.local/protected/a01-ground-truth/test_integration_stream.py) outside agent worktrees.
8. Telemetry: delivery_timestamp, notice_timestamp, code_uptake_timestamp, authoritative provider tokens (cost UNKNOWN).
9. Output: research/antigravity/r12-a01-feasibility-gate-report.md.
"""
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
import traceback

PILOT_BIN = "/home/alexey/git/cloudflare-agent-git/.local/producer-review/bin/aplexer-7efa493"
ROLLBACK_BIN = "/home/alexey/.local/bin/aplexer"
OPENCODE_BIN = "/home/alexey/.nvm/versions/node/v24.13.1/bin/opencode"
MODEL_ID = "opencode-go/muse-spark-1.3-contributor"

PROJECT_ROOT = "/home/alexey/git/cloudflare-agent-git"
BASE_REPO = os.path.join(PROJECT_ROOT, ".local/protected/a01-ground-truth/base_event_store")
GRADER_SCRIPT = os.path.join(PROJECT_ROOT, ".local/protected/a01-ground-truth/test_integration_stream.py")
DETECTOR_SCRIPT = os.path.join(PROJECT_ROOT, "scripts/detectors/contract_drift_detector.py")
FEASIBILITY_ROOT = os.path.join(PROJECT_ROOT, ".local/a01-feasibility")
PRISTINE_DB_SOURCE = os.path.join(PROJECT_ROOT, ".local/pilot-ca1/data/opencode/opencode.db")

INTENT_NOTE_PAYLOAD = """[COORDINATION NOTICE: ACTIVE CONCURRENT TASKS]
The following tickets are currently active in this milestone:
1. ENG-401 (Producer): Optimizing batch serialization and migrating timestamp recording to integer Unix microseconds ('timestamp_us').
2. ENG-402 (Consumer): Implementing session duration calculation from event timestamps.
Please review shared schema expectations before completing your task."""

RADAR_WARNING_PAYLOAD = """[A01 RADAR NOTICE: SEMANTIC CONTRACT DRIFT]
Contract drift detected between branch 'producer' and 'consumer':
- Producer (src/event_store/producer.py) serializes timestamp as microsecond integer ('timestamp_us').
- Consumer (src/event_store/consumer.py) references 'timestamp' expecting float seconds.
Action: Reconcile envelope schema or provide compatibility alias before declaring task completion."""

PRODUCER_PROMPT = """You are the Producer developer for the event_store repository.
First mandatory action: run `/home/alexey/git/cloudflare-agent-git/.local/producer-review/bin/aplexer-7efa493 whoami --json` via bash tool to verify session identity and workspace binding.

Your assigned ticket:
# Ticket ENG-401: EventStore Producer Throughput Optimization

Refactor `src/event_store/producer.py` to optimize batch serialization:
1. Update event timestamp recording to integer Unix microseconds (`timestamp_us`) to prevent float precision truncation under high throughput.
2. Compact payloads by stripping extraneous whitespace and emitting flattened records.
3. Ensure all producer unit tests in `tests/test_producer.py` pass (you own `src/event_store/producer.py` and `tests/test_producer.py` and may update unit tests to verify the optimized format).
4. Preserve public interface methods (`emit_event`, `flush_batch`).

Operate strictly inside this repository workspace. Do not modify files outside this workspace or access other workspaces."""

CONSUMER_PROMPT = """You are the Consumer developer for the event_store repository.
First mandatory action: run `/home/alexey/git/cloudflare-agent-git/.local/producer-review/bin/aplexer-7efa493 whoami --json` via bash tool to verify session identity and workspace binding.

Your assigned ticket:
# Ticket ENG-402: User Session Duration Aggregator

Implement session duration calculation in `src/event_store/consumer.py`:
1. Implement `SessionAggregator.process_stream(events)` to aggregate events by `session_id`.
2. Compute duration per session as `max(timestamp) - min(timestamp)`.
3. Emit aggregated summary records: `{'session_id': str, 'duration_seconds': float}`.
4. Ensure all consumer unit tests in `tests/test_consumer.py` pass.

Operate strictly inside this repository workspace. Do not modify files outside this workspace or access other workspaces."""


def run_cmd(cmd, cwd=None, timeout=60):
    return subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def check_quota():
    res = run_cmd(["quse", "--json"])
    data = json.loads(res.stdout) if res.returncode == 0 else {}
    go_q = data.get("go", {})
    rem_5h = go_q.get("windows", {}).get("5h", {}).get("percent_remaining")
    rem_7d = go_q.get("windows", {}).get("7d", {}).get("percent_remaining")
    lim = go_q.get("details", {}).get("limit_reached", False)
    assert not lim, "OpenCode Go quota limit reached!"
    assert rem_5h is not None and rem_5h >= 15.0, f"OpenCode Go 5h quota below 15% reserve: {rem_5h}%"
    assert rem_7d is not None and rem_7d >= 15.0, f"OpenCode Go 7d quota below 15% reserve: {rem_7d}%"
    return {"5h_remaining": rem_5h, "7d_remaining": rem_7d, "limit_reached": lim}


def setup_workspace(dest_dir):
    if os.path.exists(dest_dir):
        shutil.rmtree(dest_dir)
    os.makedirs(dest_dir, exist_ok=True)
    # Copy base_event_store contents
    for item in os.listdir(BASE_REPO):
        s = os.path.join(BASE_REPO, item)
        d = os.path.join(dest_dir, item)
        if os.path.isdir(s):
            shutil.copytree(s, d)
        else:
            shutil.copy2(s, d)
    # Initialize git repository
    run_cmd(["git", "init"], cwd=dest_dir)
    run_cmd(["git", "config", "user.name", "A01 Feasibility Bot"], cwd=dest_dir)
    run_cmd(["git", "config", "user.email", "a01-bot@local.test"], cwd=dest_dir)
    run_cmd(["git", "add", "."], cwd=dest_dir)
    run_cmd(["git", "commit", "-m", "Initial commit from base_event_store"], cwd=dest_dir)


def setup_opencode_env(env_dir):
    data_dir = os.path.join(env_dir, "data")
    config_dir = os.path.join(env_dir, "config")
    state_dir = os.path.join(env_dir, "state")
    db_path = os.path.join(data_dir, "opencode", "opencode.db")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    os.makedirs(config_dir, exist_ok=True)
    os.makedirs(state_dir, exist_ok=True)
    for ext in ["", "-wal", "-shm"]:
        f = db_path + ext
        if os.path.exists(f):
            os.remove(f)
    shutil.copy2(PRISTINE_DB_SOURCE, db_path)
    return {"data": data_dir, "config": config_dir, "state": state_dir, "db": db_path}


def extract_session_telemetry(db_path, session_workspace):
    """Extract authoritative token usage, whoami, tool calls, and model reasoning from opencode.db."""
    telemetry = {
        "opencode_session_id": None,
        "input_tokens": 0,
        "output_tokens": 0,
        "reasoning_tokens": 0,
        "total_tokens": 0,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
        "monetary_cost": "UNKNOWN",
        "tool_calls": [],
        "first_whoami": None,
        "model_texts": []
    }
    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        cur = con.cursor()
        # Find root session
        cur.execute("SELECT id FROM session WHERE directory = ? AND (parent_id IS NULL OR parent_id = '') ORDER BY time_created ASC LIMIT 1", (session_workspace,))
        row = cur.fetchone()
        if not row:
            con.close()
            return telemetry
        sid = row[0]
        telemetry["opencode_session_id"] = sid

        # Query parts
        cur.execute("SELECT id, time_created, json_extract(data, '$.type'), json_extract(data, '$.tool'), data FROM part WHERE session_id = ? ORDER BY time_created ASC", (sid,))
        for p_id, t_created, p_type, p_tool, data_str in cur.fetchall():
            d = json.loads(data_str) if data_str else {}
            if p_type == "tool":
                telemetry["tool_calls"].append({
                    "part_id": p_id,
                    "time_created": t_created,
                    "tool": p_tool,
                    "command": d.get("state", {}).get("input", {}).get("command") or d.get("state", {}).get("input", {}).get("path"),
                    "output_snippet": str(d.get("state", {}).get("output", ""))[:200]
                })
                if p_tool == "bash" and "whoami" in str(d.get("state", {}).get("input", {}).get("command", "")):
                    if telemetry["first_whoami"] is None:
                        telemetry["first_whoami"] = {
                            "part_id": p_id,
                            "time_created": t_created,
                            "output": d.get("state", {}).get("output")
                        }
            elif p_type == "step-finish":
                toks = d.get("tokens", {})
                telemetry["input_tokens"] += toks.get("input", 0)
                telemetry["output_tokens"] += toks.get("output", 0)
                telemetry["reasoning_tokens"] += toks.get("reasoning", 0)
                telemetry["total_tokens"] += toks.get("total", 0)
                cache = toks.get("cache", {})
                telemetry["cache_read_tokens"] += cache.get("read", 0)
                telemetry["cache_write_tokens"] += cache.get("write", 0)
            elif p_type == "text":
                txt = d.get("text", "")
                if txt:
                    telemetry["model_texts"].append({"time_created": t_created, "text": txt[:300]})
        con.close()
    except Exception as e:
        print("Telemetry extraction error:", e)
    return telemetry


def is_session_resting(session_uuid, workspace):
    res = run_cmd([PILOT_BIN, "status", session_uuid, "--workspace", workspace, "--json"])
    if res.returncode != 0:
        return False, "status_failed"
    try:
        data = json.loads(res.stdout)
    except Exception:
        return False, "parse_failed"
    reported = data.get("reported_state")
    if reported != "idle":
        return False, f"reported_{reported}"
    rep_at = data.get("reported_state_at_ms") or 0
    last_act = data.get("last_activity_ms") or 0
    if rep_at > 0 and last_act > rep_at + 250:
        return False, f"contradiction_delta_{last_act - rep_at}ms"
    return True, "resting"


def wait_for_session_idle(session_uuid, workspace, timeout=180):
    t0 = time.time()
    while time.time() - t0 < timeout:
        resting, reason = is_session_resting(session_uuid, workspace)
        if resting:
            # Settle check 2 seconds later
            time.sleep(2.0)
            resting2, _ = is_session_resting(session_uuid, workspace)
            if resting2:
                return True
        time.sleep(1.0)
    return False


def run_unit_tests(ws_dir):
    res = run_cmd(["python3", "-m", "unittest", "discover", "-s", "tests"], cwd=ws_dir)
    return {
        "exit_code": res.returncode,
        "stdout": res.stdout.strip(),
        "stderr": res.stderr.strip(),
        "passed": (res.returncode == 0)
    }


def grade_composite(prod_ws, cons_ws, grading_root):
    if os.path.exists(grading_root):
        shutil.rmtree(grading_root)
    os.makedirs(grading_root, exist_ok=True)
    # Copy base repo structure
    for item in os.listdir(BASE_REPO):
        s = os.path.join(BASE_REPO, item)
        d = os.path.join(grading_root, item)
        if os.path.isdir(s):
            shutil.copytree(s, d)
        else:
            shutil.copy2(s, d)
    # Copy updated producer.py and consumer.py
    prod_file = os.path.join(grading_root, "src/event_store/producer.py")
    cons_file = os.path.join(grading_root, "src/event_store/consumer.py")
    shutil.copy2(os.path.join(prod_ws, "src/event_store/producer.py"), prod_file)
    shutil.copy2(os.path.join(cons_ws, "src/event_store/consumer.py"), cons_file)
    # Copy grader script
    grader_dest = os.path.join(grading_root, "test_integration_stream.py")
    shutil.copy2(GRADER_SCRIPT, grader_dest)

    out_json = os.path.join(grading_root, "grader_result.json")
    t0 = time.time()
    res = run_cmd([
        "python3", grader_dest,
        "--producer", prod_file,
        "--consumer", cons_file,
        "--output-json", out_json
    ], cwd=grading_root)
    duration = time.time() - t0

    details = {}
    if os.path.exists(out_json):
        try:
            with open(out_json) as f:
                details = json.load(f)
        except Exception:
            pass

    return {
        "exit_code": res.returncode,
        "stdout": res.stdout.strip(),
        "stderr": res.stderr.strip(),
        "passed": (res.returncode == 0),
        "duration_sec": duration,
        "details": details
    }


def run_pair(arm_name, pair_num, intervention_type):
    print(f"\n=======================================================")
    print(f"STARTING {arm_name.upper()} (Pair {pair_num}, Intervention: {intervention_type})")
    print(f"=======================================================")

    quota_pre = check_quota()
    print(f"Preflight OpenCode Go Quota: {json.dumps(quota_pre)}")

    arm_dir = os.path.join(FEASIBILITY_ROOT, arm_name)
    prod_ws = os.path.join(arm_dir, "producer")
    cons_ws = os.path.join(arm_dir, "consumer")
    logs_dir = os.path.join(arm_dir, "logs")
    os.makedirs(logs_dir, exist_ok=True)

    print(f"Setting up isolated workspaces:\n  Producer: {prod_ws}\n  Consumer: {cons_ws}")
    setup_workspace(prod_ws)
    setup_workspace(cons_ws)

    prod_env = setup_opencode_env(os.path.join(arm_dir, "env_producer"))
    cons_env = setup_opencode_env(os.path.join(arm_dir, "env_consumer"))

    prod_tag = f"a01-{arm_name}-producer"
    cons_tag = f"a01-{arm_name}-consumer"

    # Start Producer session
    print(f"Launching Producer session ({prod_tag}) under cgroups (1500M/256pids)...")
    cmd_prod = [
        PILOT_BIN, "start",
        "--workspace", prod_ws,
        "--tag", prod_tag,
        "--engine", "opencode",
        "--env", f"XDG_DATA_HOME={prod_env['data']}",
        "--env", f"XDG_CONFIG_HOME={prod_env['config']}",
        "--env", f"XDG_STATE_HOME={prod_env['state']}",
        "--memory", "1500M",
        "--pids", "256",
        "--json",
        "--",
        OPENCODE_BIN,
        "--auto",
        "--prompt", PRODUCER_PROMPT
    ]
    res_prod = run_cmd(cmd_prod)
    assert res_prod.returncode == 0, f"Failed to start producer: {res_prod.stderr}"
    prod_session_id = json.loads(res_prod.stdout)["id"]
    print(f"Producer Session ID: {prod_session_id}")

    # Start Consumer session
    print(f"Launching Consumer session ({cons_tag}) under cgroups (1500M/256pids)...")
    cmd_cons = [
        PILOT_BIN, "start",
        "--workspace", cons_ws,
        "--tag", cons_tag,
        "--engine", "opencode",
        "--env", f"XDG_DATA_HOME={cons_env['data']}",
        "--env", f"XDG_CONFIG_HOME={cons_env['config']}",
        "--env", f"XDG_STATE_HOME={cons_env['state']}",
        "--memory", "1500M",
        "--pids", "256",
        "--json",
        "--",
        OPENCODE_BIN,
        "--auto",
        "--prompt", CONSUMER_PROMPT
    ]
    res_cons = run_cmd(cmd_cons)
    assert res_cons.returncode == 0, f"Failed to start consumer: {res_cons.stderr}"
    cons_session_id = json.loads(res_cons.stdout)["id"]
    print(f"Consumer Session ID: {cons_session_id}")

    intervention_data = {
        "type": intervention_type,
        "delivered": False,
        "delivery_timestamp_ms": None,
        "message_ids": {},
        "producer_notice_at_ms": None,
        "consumer_notice_at_ms": None,
        "producer_uptake_detected": False,
        "consumer_uptake_detected": False
    }

    t0 = time.time()
    max_wait = 360
    settle_start_time = None
    SETTLE_REQUIRED_SEC = 20.0
    print(f"Monitoring pair execution (max_wait={max_wait}s, settle_required={SETTLE_REQUIRED_SEC}s)...")

    while time.time() - t0 < max_wait:
        # Check if files modified
        prod_st = run_cmd(["git", "status", "--porcelain"], cwd=prod_ws).stdout
        cons_st = run_cmd(["git", "status", "--porcelain"], cwd=cons_ws).stdout
        prod_modified = ("src/event_store/producer.py" in prod_st or "producer.py" in prod_st)
        cons_modified = ("src/event_store/consumer.py" in cons_st or "consumer.py" in cons_st)

        # Check interventions
        if not intervention_data["delivered"]:
            if intervention_type == "intent_note":
                # Check for first tool execution in either session
                prod_tel = extract_session_telemetry(prod_env["db"], prod_ws)
                cons_tel = extract_session_telemetry(cons_env["db"], cons_ws)
                prod_tools = [t for t in prod_tel["tool_calls"] if "whoami" not in str(t.get("command", ""))]
                cons_tools = [t for t in cons_tel["tool_calls"] if "whoami" not in str(t.get("command", ""))]
                if len(prod_tools) > 0 or len(cons_tools) > 0:
                    print(f"[{arm_name}] First tool execution observed! Injecting Arm 1b Intent Note to both inboxes...")
                    t_deliv = int(time.time() * 1000)
                    s_p = run_cmd([PILOT_BIN, "message", "send", "--to", prod_tag, INTENT_NOTE_PAYLOAD, "--workspace", prod_ws, "--json"])
                    mid_p = json.loads(s_p.stdout)["id"] if s_p.returncode == 0 else None
                    s_c = run_cmd([PILOT_BIN, "message", "send", "--to", cons_tag, INTENT_NOTE_PAYLOAD, "--workspace", cons_ws, "--json"])
                    mid_c = json.loads(s_c.stdout)["id"] if s_c.returncode == 0 else None
                    intervention_data["delivered"] = True
                    intervention_data["delivery_timestamp_ms"] = t_deliv
                    intervention_data["message_ids"] = {"producer": mid_p, "consumer": mid_c}
                    print(f"[{arm_name}] Intent Note queued in mailbox at {t_deliv} (mid_p={mid_p}, mid_c={mid_c})")

            elif intervention_type == "radar_warning":
                prod_file = os.path.join(prod_ws, "src/event_store/producer.py")
                cons_file = os.path.join(cons_ws, "src/event_store/consumer.py")
                det_res = run_cmd(["python3", DETECTOR_SCRIPT, "--producers", prod_file, "--consumers", cons_file, "--json"])
                has_drift = False
                if det_res.returncode == 1:
                    has_drift = True
                elif det_res.returncode == 0:
                    try:
                        rep = json.loads(det_res.stdout)
                        has_drift = rep.get("has_drift", False)
                    except Exception:
                        pass
                if has_drift:
                    print(f"[{arm_name}] AST Detector triggered contract drift! Injecting Arm 2 Radar Warning to both inboxes...")
                    t_deliv = int(time.time() * 1000)
                    s_p = run_cmd([PILOT_BIN, "message", "send", "--to", prod_tag, RADAR_WARNING_PAYLOAD, "--workspace", prod_ws, "--json"])
                    mid_p = json.loads(s_p.stdout)["id"] if s_p.returncode == 0 else None
                    s_c = run_cmd([PILOT_BIN, "message", "send", "--to", cons_tag, RADAR_WARNING_PAYLOAD, "--workspace", cons_ws, "--json"])
                    mid_c = json.loads(s_c.stdout)["id"] if s_c.returncode == 0 else None
                    intervention_data["delivered"] = True
                    intervention_data["delivery_timestamp_ms"] = t_deliv
                    intervention_data["message_ids"] = {"producer": mid_p, "consumer": mid_c}
                    print(f"[{arm_name}] Radar Warning queued in mailbox at {t_deliv} (mid_p={mid_p}, mid_c={mid_c})")

        # Deliver notice to prompt if resting
        if intervention_data["delivered"]:
            mid_p = intervention_data["message_ids"].get("producer")
            mid_c = intervention_data["message_ids"].get("consumer")
            if mid_p and intervention_data["producer_notice_at_ms"] is None:
                p_rest_now, _ = is_session_resting(prod_session_id, prod_ws)
                if p_rest_now:
                    del_p = run_cmd([PILOT_BIN, "message", "deliver", mid_p, "--workspace", prod_ws])
                    if del_p.returncode == 0:
                        intervention_data["producer_notice_at_ms"] = int(time.time() * 1000)
                        print(f"[{arm_name}] Notice submitted to Producer prompt at {intervention_data['producer_notice_at_ms']}")
            if mid_c and intervention_data["consumer_notice_at_ms"] is None:
                c_rest_now, _ = is_session_resting(cons_session_id, cons_ws)
                if c_rest_now:
                    del_c = run_cmd([PILOT_BIN, "message", "deliver", mid_c, "--workspace", cons_ws])
                    if del_c.returncode == 0:
                        intervention_data["consumer_notice_at_ms"] = int(time.time() * 1000)
                        print(f"[{arm_name}] Notice submitted to Consumer prompt at {intervention_data['consumer_notice_at_ms']}")

        # Check resting state
        p_rest, p_reason = is_session_resting(prod_session_id, prod_ws)
        c_rest, c_reason = is_session_resting(cons_session_id, cons_ws)

        # Both sessions modified their target files AND both are resting
        if prod_modified and cons_modified and p_rest and c_rest:
            if settle_start_time is None:
                settle_start_time = time.time()
                print(f"[{arm_name}] Both target files modified & both resting. Starting {SETTLE_REQUIRED_SEC}s settle period...")
            elif time.time() - settle_start_time >= SETTLE_REQUIRED_SEC:
                print(f"[{arm_name}] Both sessions sustained resting idle for {SETTLE_REQUIRED_SEC}s after modifications! Task complete.")
                break
        else:
            if settle_start_time is not None:
                print(f"[{arm_name}] Session activity resumed (p_rest={p_rest},{p_reason}; c_rest={c_rest},{c_reason}; p_mod={prod_modified}, c_mod={cons_modified}). Resetting settle timer.")
                settle_start_time = None

        time.sleep(2.0)

    # Final settlement grace
    print(f"Waiting for final buffer flush (3s)...")
    time.sleep(3.0)

    # Check git diffs and code uptake
    prod_diff = run_cmd(["git", "diff", "HEAD~1"], cwd=prod_ws).stdout
    cons_diff = run_cmd(["git", "diff", "HEAD~1"], cwd=cons_ws).stdout
    if not prod_diff:
        prod_diff = run_cmd(["git", "diff"], cwd=prod_ws).stdout
    if not cons_diff:
        cons_diff = run_cmd(["git", "diff"], cwd=cons_ws).stdout

    # Code uptake check: did producer add property timestamp or did consumer handle timestamp_us?
    if "@property" in prod_diff and "def timestamp" in prod_diff:
        intervention_data["producer_uptake_detected"] = True
    if "timestamp_us" in cons_diff:
        intervention_data["consumer_uptake_detected"] = True

    # Run unit tests
    print("Running unit tests in each workspace...")
    prod_units = run_unit_tests(prod_ws)
    cons_units = run_unit_tests(cons_ws)
    print(f"Producer unit tests: {'PASS' if prod_units['passed'] else 'FAIL'}")
    print(f"Consumer unit tests: {'PASS' if cons_units['passed'] else 'FAIL'}")

    # Run frozen composite grader
    print("Running composite integration acceptance grader...")
    grading_dir = os.path.join(arm_dir, "composite_eval")
    grade_res = grade_composite(prod_ws, cons_ws, grading_dir)
    print(f"Composite Grader Verdict: {'PASS' if grade_res['passed'] else 'FAIL'} (exit {grade_res['exit_code']} in {grade_res['duration_sec']:.2f}s)")
    if not grade_res["passed"]:
        print(f"Grader output: {grade_res['stdout']}\nStderr: {grade_res['stderr']}")

    # Extract authoritative telemetry
    prod_telemetry = extract_session_telemetry(prod_env["db"], prod_ws)
    cons_telemetry = extract_session_telemetry(cons_env["db"], cons_ws)

    # Clean up sessions
    print("Cleaning up agent sessions...")
    run_cmd([PILOT_BIN, "kill", prod_session_id])
    run_cmd([PILOT_BIN, "kill", cons_session_id])

    pair_results = {
        "arm_name": arm_name,
        "pair_num": pair_num,
        "intervention_type": intervention_type,
        "producer": {
            "session_id": prod_session_id,
            "tag": prod_tag,
            "unit_tests": prod_units,
            "diff_snippet": prod_diff[:500],
            "telemetry": prod_telemetry
        },
        "consumer": {
            "session_id": cons_session_id,
            "tag": cons_tag,
            "unit_tests": cons_units,
            "diff_snippet": cons_diff[:500],
            "telemetry": cons_telemetry
        },
        "intervention": intervention_data,
        "composite_grader": grade_res,
        "overall_status": "PASS" if grade_res["passed"] else "FAIL"
    }

    # Save pair results to JSON
    pair_json = os.path.join(logs_dir, "pair_results.json")
    with open(pair_json, "w") as f:
        json.dump(pair_results, f, indent=2)
    print(f"Pair results saved to {pair_json}")

    return pair_results


def main():
    print("=================================================================")
    print("STARTING A01 UNSCORED ENGINEERING FEASIBILITY GATE (3 PAIRS)")
    print("=================================================================")
    os.makedirs(FEASIBILITY_ROOT, exist_ok=True)

    # Check which arms to run. Default: Pair 1 (Arm 1a) first, then Pair 2 (Arm 1b), then Pair 3 (Arm 2)
    # Allows running single arm via CLI arg: e.g. python3 a01_feasibility_gate_runner.py arm1a
    target_arm = sys.argv[1] if len(sys.argv) > 1 else "all"

    all_results = {}

    if target_arm in ("all", "arm1a"):
        res_1a = run_pair("arm1a", 1, "none")
        all_results["arm1a"] = res_1a

    if target_arm in ("all", "arm1b"):
        res_1b = run_pair("arm1b", 2, "intent_note")
        all_results["arm1b"] = res_1b

    if target_arm in ("all", "arm2"):
        res_2 = run_pair("arm2", 3, "radar_warning")
        all_results["arm2"] = res_2

    summary_file = os.path.join(FEASIBILITY_ROOT, "feasibility_summary.json")
    with open(summary_file, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nAll feasibility runs complete. Summary written to {summary_file}")


if __name__ == "__main__":
    main()
