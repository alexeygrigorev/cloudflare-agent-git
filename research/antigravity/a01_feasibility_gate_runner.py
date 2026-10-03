#!/usr/bin/env python3
"""A01 Unscored Engineering Feasibility Gate Runner (3 Paired Trials / 6 Agent Sessions)

Executes the protocol specified in r12-a01-natural-hazard-preregistration.md (v2.2, commit 9412520,
prospective roster addendum f588508) authorized by Codex Principal (C-1281) and Claude Principal (01a10186, 01a10187):
1. Standardized model route: opencode-go/muse-spark-1.3-contributor across all 3 arms (6 sessions).
2. Arm 1a: Silent Isolation (Pair 1: Producer + Consumer)
3. Arm 1b: Cheap Incumbent / Intent Note (Pair 2: Producer + Consumer)
4. Arm 2: Live Collision Radar Warning (Pair 3: Producer + Consumer)
5. Execution containment: cgroups --memory 1500M --pids 256 per session.
6. Isolated worktrees under .local/a01-feasibility/<arm>/run-<timestamp>/{producer,consumer}.
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
    """Quota Gate: Check quse --json for go provider. Require percent_remaining > 10.0 and limit_reached == False."""
    res = run_cmd(["quse", "--json"])
    assert res.returncode == 0, f"quse command failed: {res.stderr}"
    data = json.loads(res.stdout) if res.stdout else {}
    go_q = data.get("go", {})
    lim = go_q.get("details", {}).get("limit_reached", False)
    assert not lim, "OpenCode Go quota limit reached (limit_reached == True)!"
    windows = go_q.get("windows", {})
    rem_5h = windows.get("5h", {}).get("percent_remaining")
    rem_7d = windows.get("7d", {}).get("percent_remaining")
    assert rem_5h is not None and rem_5h > 10.0, f"OpenCode Go 5h quota below 10% reserve: {rem_5h}%"
    assert rem_7d is not None and rem_7d > 10.0, f"OpenCode Go 7d quota below 10% reserve: {rem_7d}%"
    return {"5h_remaining": rem_5h, "7d_remaining": rem_7d, "limit_reached": lim}


def setup_workspace(dest_dir):
    """Set up an isolated workspace for an agent. Overwrite refused per immutability policy."""
    if os.path.exists(dest_dir):
        raise FileExistsError(f"Workspace directory {dest_dir} already exists; overwrite refused per immutability policy")
    os.makedirs(dest_dir, exist_ok=False)
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
    """Set up an isolated OpenCode configuration and data directory. Overwrite refused per immutability policy."""
    if os.path.exists(env_dir):
        raise FileExistsError(f"Environment directory {env_dir} already exists; overwrite refused per immutability policy")
    data_dir = os.path.join(env_dir, "data")
    config_dir = os.path.join(env_dir, "config")
    state_dir = os.path.join(env_dir, "state")
    db_path = os.path.join(data_dir, "opencode", "opencode.db")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    os.makedirs(config_dir, exist_ok=True)
    os.makedirs(state_dir, exist_ok=True)
    shutil.copy2(PRISTINE_DB_SOURCE, db_path)
    return {"data": data_dir, "config": config_dir, "state": state_dir, "db": db_path}


def verify_session_model_route(db_path, session_workspace, launch_t0_ms, timeout=20, sessions_to_kill=None):
    """Verify session initialized with the authorized assistant model route in opencode.db.

    Queries root assistant message where time_created >= launch_t0_ms - 2000.
    Asserts json_extract(data, '$.providerID') == 'opencode-go' and
            json_extract(data, '$.modelID') == 'muse-spark-1.3-contributor'.
    If mismatch or timeout, immediately kills sessions and raises RuntimeError('MODEL_MISMATCH_ABORT').
    """
    t0 = time.time()
    min_time = launch_t0_ms - 2000
    while time.time() - t0 < timeout:
        try:
            con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            cur = con.cursor()
            cur.execute("""
                SELECT m.id, json_extract(m.data, '$.providerID'), json_extract(m.data, '$.modelID')
                FROM message m
                JOIN session s ON m.session_id = s.id
                WHERE s.directory = ?
                  AND (s.parent_id IS NULL OR s.parent_id = '')
                  AND m.time_created >= ?
                  AND json_extract(m.data, '$.role') = 'assistant'
                ORDER BY m.time_created ASC LIMIT 1
            """, (session_workspace, min_time))
            row = cur.fetchone()
            con.close()
            if row:
                _, provider_id, model_id = row
                if provider_id == "opencode-go" and model_id == "muse-spark-1.3-contributor":
                    print(f"Verified assistant model route for {session_workspace}: {provider_id}/{model_id}")
                    return True
                else:
                    if sessions_to_kill:
                        for sid in sessions_to_kill:
                            run_cmd([PILOT_BIN, "kill", sid])
                    raise RuntimeError(f"MODEL_MISMATCH_ABORT: expected opencode-go/muse-spark-1.3-contributor, got {provider_id}/{model_id}")
        except sqlite3.OperationalError:
            pass
        time.sleep(1.0)

    if sessions_to_kill:
        for sid in sessions_to_kill:
            run_cmd([PILOT_BIN, "kill", sid])
    raise RuntimeError(f"MODEL_MISMATCH_ABORT: timed out after {timeout}s waiting for session root assistant message")


def extract_session_telemetry(db_path, session_workspace, launch_t0_ms):
    """Extract authoritative token usage, whoami, tool calls, and model reasoning from opencode.db.

    Uses a launch-time lower bound (launch_t0_ms - 2000) to find the current run's root session.
    """
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
        min_time = launch_t0_ms - 2000
        # Find root session created at or after launch_t0_ms - 2000
        cur.execute(
            "SELECT id FROM session WHERE directory = ? AND (parent_id IS NULL OR parent_id = '') AND time_created >= ? ORDER BY time_created ASC LIMIT 1",
            (session_workspace, min_time)
        )
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


def check_session_notice(db_path, session_workspace, launch_t0_ms, delivered_at_ms, target_msg_id):
    """Confirm model notice ONLY when verified by completed, successful tool call
    inspecting the exact target_msg_id with output confirming envelope exposure.
    Rejects:
    - Failed tool executions (status != completed/success, or output containing error/failed/failure/rc=[1-9])
    - Unrelated commands (e.g. echo <ID>, grep <ID>)
    - Bare command substring matches without read output exposure
    - Bare user prompt presence (transport presence is NOT model notice).
    """
    if not delivered_at_ms or not target_msg_id:
        return None
    target_msg_id = str(target_msg_id).strip()
    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        cur = con.cursor()
        min_time = launch_t0_ms - 2000
        cur.execute(
            "SELECT id FROM session WHERE directory = ? AND (parent_id IS NULL OR parent_id = '') AND time_created >= ? ORDER BY time_created ASC LIMIT 1",
            (session_workspace, min_time)
        )
        row = cur.fetchone()
        if not row:
            con.close()
            return None
        sid = row[0]

        # Inspect tool calls with command, status, and output
        cur.execute("""
            SELECT time_created,
                   json_extract(data, '$.state.input.command'),
                   json_extract(data, '$.state.status'),
                   json_extract(data, '$.state.output')
            FROM part
            WHERE session_id = ? AND json_extract(data, '$.type') = 'tool' AND time_created >= ?
            ORDER BY time_created ASC
        """, (sid, delivered_at_ms))

        for t_created, cmd, status, output in cur.fetchall():
            cmd_str = str(cmd or "")
            status_str = str(status or "").lower()
            output_str = str(output or "")

            # 1. Command must be a genuine message inspection command containing target_msg_id
            if target_msg_id not in cmd_str:
                continue
            if not re.search(r'\b(?:a|aplexer)?\s*message\s+(?:show|read)\b', cmd_str):
                continue

            # 2. Tool execution must be completed / successful
            if status_str and status_str not in ("completed", "success"):
                continue

            # 3. Output must NOT indicate failure
            out_lower = output_str.lower()
            if re.search(r'\b(?:error|failed|failure|rc=[1-9])\b', out_lower):
                continue

            # 4. Read output must expose the envelope (target_msg_id in output)
            if target_msg_id not in output_str:
                continue

            con.close()
            return t_created

        con.close()
    except Exception as e:
        print(f"Error checking session notice: {e}")
    return None


def parse_delivery_disposition(res):
    """Parse delivery outcome with strict uncertain/malformed handling."""
    if res.returncode != 0:
        return f"failed_rc_{res.returncode}"
    try:
        d_json = json.loads(res.stdout)
    except Exception:
        return "UNKNOWN"
    if not isinstance(d_json, dict) or "status" not in d_json:
        return "UNKNOWN"
    status = str(d_json["status"]).lower()
    if status == "uncertain" or not status:
        return "UNKNOWN"
    return d_json["status"]


def create_intervention_data(intervention_type):
    """Factory creating the standardized intervention_data dictionary."""
    return {
        "type": intervention_type,
        "delivered": False,
        "delivered_at_ms": None,
        "delivery_timestamp_ms": None,
        "message_ids": {},
        "producer_delivered_at_ms": None,
        "consumer_delivered_at_ms": None,
        "producer_delivery_disposition": None,
        "consumer_delivery_disposition": None,
        "producer_noticed_at_ms": None,
        "consumer_noticed_at_ms": None,
        "producer_notice_at_ms": None,  # backwards-compat alias
        "consumer_notice_at_ms": None,  # backwards-compat alias
        "producer_uptake_detected": False,
        "consumer_uptake_detected": False
    }


def composer_classifier(screen, tag=""):
    """Full empty composer classification for OpenCode bordered UI and shell/codex prompts."""
    if not screen:
        return "unknown"
    s_lower = screen.lower()

    # 1. Busy check: if model is actively generating or executing a tool with interrupt enabled
    if "working (" in s_lower or "esc to interrupt" in s_lower or "esc interrupt" in s_lower:
        return "busy"

    # 2. Check for menu / choice overlay
    if re.search(r"How is Claude doing|Choose|Select|feedback", screen, re.I):
        return "menu-or-draft"

    # 3. OpenCode Bordered Composer Detection
    lines = screen.splitlines()
    bottom_indices = [i for i, l in enumerate(lines) if "╹" in l or re.search(r"^\s*╹", l)]
    
    composer_lines = []
    if bottom_indices:
        b_idx = bottom_indices[-1]
        idx = b_idx - 1
        while idx >= 0:
            l = lines[idx]
            if re.match(r"^\s*┃", l):
                composer_lines.insert(0, l)
                idx -= 1
            elif not l.strip():
                idx -= 1
            elif "▣" in l:
                break
            else:
                break
    else:
        build_indices = [i for i, l in enumerate(lines) if "▣" in l and "build" in l.lower()]
        if build_indices:
            start_idx = build_indices[-1]
            composer_lines = [l for l in lines[start_idx:] if re.match(r"^\s*┃", l)]
        elif "ctrl+p" in s_lower:
            all_pipe = [l for l in lines if re.match(r"^\s*┃", l)]
            if all_pipe:
                composer_lines = all_pipe[-5:]

    if "ctrl+p" in s_lower and composer_lines:
        draft_content = []
        for l in composer_lines:
            cleaned = re.sub(r"^\s*┃\s*", "", l).strip()
            if not cleaned:
                continue
            if re.match(r"^Build (?:auto|prompt)(?:\s*·.*)?$", cleaned, re.I):
                continue
            draft_content.append(cleaned)
        
        if draft_content:
            return "draft"
        return "empty"

    # 4. Standard shell / codex › or ❯ prompt check
    starts = [(i, re.sub(r"^\s*[›❯]\s*", "", line).strip())
              for i, line in enumerate(lines) if re.match(r"^\s*[›❯]", line)]
    if starts:
        index, content = starts[-1]
        if any(line.strip() and not re.match(r"^\s*[─━]|.*(?:Context|for shortcuts|auto mode|manage|monitor|agents|tokens|GPT-|usage|workspace|warning)", line)
               for line in lines[index + 1:]):
            return "unknown"
        if content and not (tag == "codex-principal" and content == "Ask Codex to do anything"):
            return "draft"
        return "empty"

    return "unknown"


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


def check_resting_empty_composer(session_uuid, workspace, tag=""):
    """Check if session is resting idle with an empty composer."""
    resting, reason = is_session_resting(session_uuid, workspace)
    if not resting:
        return False, f"not_resting_{reason}"
    cap_res = run_cmd([PILOT_BIN, "capture", session_uuid, "--screen", "--plain", "--workspace", workspace])
    if cap_res.returncode != 0:
        return False, "capture_failed"
    screen = cap_res.stdout
    comp_state = composer_classifier(screen, tag=tag)
    if comp_state != "empty":
        return False, f"composer_{comp_state}"
    return True, "resting_empty"


def verify_twice_resting_empty_composer(session_uuid, workspace, tag="", min_delay_sec=1.5):
    """Require twice-fresh resting check separated by at least min_delay_sec with empty composer."""
    ok1, reason1 = check_resting_empty_composer(session_uuid, workspace, tag=tag)
    if not ok1:
        return False, f"first_check_failed_{reason1}"
    time.sleep(min_delay_sec)
    ok2, reason2 = check_resting_empty_composer(session_uuid, workspace, tag=tag)
    if not ok2:
        return False, f"second_check_failed_{reason2}"
    return True, "twice_resting_empty"


def wait_for_session_idle(session_uuid, workspace, timeout=180):
    t0 = time.time()
    while time.time() - t0 < timeout:
        resting, reason = is_session_resting(session_uuid, workspace)
        if resting:
            time.sleep(2.0)
            resting2, _ = is_session_resting(session_uuid, workspace)
            if resting2:
                return True
        time.sleep(1.0)
    return False


def is_file_modified(ws, rel_path):
    target = os.path.join(ws, rel_path)
    base = os.path.join(BASE_REPO, rel_path)
    if not os.path.exists(target):
        return False
    if sha256_file(target) != sha256_file(base):
        return True
    st = run_cmd(["git", "status", "--porcelain", rel_path], cwd=ws).stdout.strip()
    return len(st) > 0


def run_unit_tests(ws_dir):
    res = run_cmd(["python3", "-m", "unittest", "discover", "-s", "tests"], cwd=ws_dir)
    return {
        "exit_code": res.returncode,
        "stdout": res.stdout.strip(),
        "stderr": res.stderr.strip(),
        "passed": (res.returncode == 0)
    }


def run_external_producer_acceptance(prod_ws):
    """Task-specific external producer acceptance test.
    Asserts batch[0]['timestamp_us'] exists and is int.
    Strictly fails on unmodified BASE.
    """
    code = """
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / "src"))
from event_store.producer import EventProducer

producer = EventProducer()
producer.emit_event({"session_id": "test_sess", "t_sec": 1700000000.123456, "payload": "ping"})
batch = producer.flush_batch()
assert len(batch) > 0, "Producer flush_batch returned empty batch"
assert "timestamp_us" in batch[0], "batch[0] missing required 'timestamp_us' key"
assert isinstance(batch[0]["timestamp_us"], int), f"'timestamp_us' is not int: {type(batch[0]['timestamp_us'])}"
"""
    res = run_cmd(["python3", "-c", code], cwd=prod_ws)
    return {
        "passed": (res.returncode == 0),
        "exit_code": res.returncode,
        "stdout": res.stdout.strip(),
        "stderr": res.stderr.strip()
    }


def run_external_consumer_acceptance(cons_ws):
    """Task-specific external consumer acceptance test.
    Asserts SessionAggregator.process_stream aggregates events.
    Strictly fails on unmodified BASE.
    """
    code = """
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / "src"))
from event_store.consumer import SessionAggregator

agg = SessionAggregator()
events = [
    {"session_id": "s1", "timestamp": 10.0, "payload": "a"},
    {"session_id": "s1", "timestamp": 15.0, "payload": "b"},
    {"session_id": "s2", "timestamp": 20.0, "payload": "c"},
    {"session_id": "s2", "timestamp": 22.5, "payload": "d"},
]
out = agg.process_stream(events)
assert isinstance(out, list), f"process_stream output must be a list, got {type(out)}"
assert len(out) == 2, f"Expected 2 aggregated sessions, got {len(out)}"
by_id = {r.get("session_id"): r for r in out}
assert "s1" in by_id and "s2" in by_id, f"Missing session IDs in aggregated output: {list(by_id.keys())}"
assert abs(by_id["s1"].get("duration_seconds", 0.0) - 5.0) < 1e-3, f"Wrong s1 duration: {by_id['s1']}"
assert abs(by_id["s2"].get("duration_seconds", 0.0) - 2.5) < 1e-3, f"Wrong s2 duration: {by_id['s2']}"
"""
    res = run_cmd(["python3", "-c", code], cwd=cons_ws)
    return {
        "passed": (res.returncode == 0),
        "exit_code": res.returncode,
        "stdout": res.stdout.strip(),
        "stderr": res.stderr.strip()
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

    status = "ERROR" if res.returncode == 2 else ("PASS" if res.returncode == 0 else "FAIL")

    return {
        "exit_code": res.returncode,
        "stdout": res.stdout.strip(),
        "stderr": res.stderr.strip(),
        "passed": (res.returncode == 0),
        "status": status,
        "duration_sec": duration,
        "details": details
    }


def run_pair(arm_name, pair_num, intervention_type):
    print(f"\n=======================================================")
    print(f"STARTING {arm_name.upper()} (Pair {pair_num}, Intervention: {intervention_type})")
    print(f"=======================================================")

    quota_pre = check_quota()
    print(f"Preflight OpenCode Go Quota: {json.dumps(quota_pre)}")

    arm_dir = os.path.join(FEASIBILITY_ROOT, arm_name, f"run-{int(time.time())}")
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

    # Start Producer session with explicit model route
    print(f"Launching Producer session ({prod_tag}) under cgroups (1500M/256pids) with model {MODEL_ID}...")
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
        "--model", MODEL_ID,
        "--auto",
        "--prompt", PRODUCER_PROMPT
    ]
    t0_prod = int(time.time() * 1000)
    res_prod = run_cmd(cmd_prod)
    assert res_prod.returncode == 0, f"Failed to start producer: {res_prod.stderr}"
    prod_session_id = json.loads(res_prod.stdout)["id"]
    print(f"Producer Session ID: {prod_session_id}")

    # Start Consumer session with explicit model route
    print(f"Launching Consumer session ({cons_tag}) under cgroups (1500M/256pids) with model {MODEL_ID}...")
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
        "--model", MODEL_ID,
        "--auto",
        "--prompt", CONSUMER_PROMPT
    ]
    t0_cons = int(time.time() * 1000)
    res_cons = run_cmd(cmd_cons)
    assert res_cons.returncode == 0, f"Failed to start consumer: {res_cons.stderr}"
    cons_session_id = json.loads(res_cons.stdout)["id"]
    print(f"Consumer Session ID: {cons_session_id}")

    active_sessions = [prod_session_id, cons_session_id]

    # Post-Boot Model Route Verification Gate
    try:
        print("Verifying Producer session assistant model route in opencode.db...")
        verify_session_model_route(prod_env["db"], prod_ws, t0_prod, timeout=20, sessions_to_kill=active_sessions)
        print("Verifying Consumer session assistant model route in opencode.db...")
        verify_session_model_route(cons_env["db"], cons_ws, t0_cons, timeout=20, sessions_to_kill=active_sessions)
    except Exception as e:
        print(f"Model verification failed: {e}. Active sessions killed.")
        raise

    intervention_data = create_intervention_data(intervention_type)

    t0 = time.time()
    max_wait = 360
    settle_start_time = None
    SETTLE_REQUIRED_SEC = 20.0
    settle_completed = False
    print(f"Monitoring pair execution (max_wait={max_wait}s, settle_required={SETTLE_REQUIRED_SEC}s)...")

    while time.time() - t0 < max_wait:
        # Check if target files modified
        prod_modified = is_file_modified(prod_ws, "src/event_store/producer.py")
        cons_modified = is_file_modified(cons_ws, "src/event_store/consumer.py")

        # Check interventions
        if not intervention_data["delivered"]:
            if intervention_type == "intent_note":
                # Check for first tool execution in either session
                prod_tel = extract_session_telemetry(prod_env["db"], prod_ws, t0_prod)
                cons_tel = extract_session_telemetry(cons_env["db"], cons_ws, t0_cons)
                prod_tools = [t for t in prod_tel["tool_calls"] if "whoami" not in str(t.get("command", ""))]
                cons_tools = [t for t in cons_tel["tool_calls"] if "whoami" not in str(t.get("command", ""))]
                if len(prod_tools) > 0 or len(cons_tools) > 0:
                    print(f"[{arm_name}] First tool execution observed! Injecting Arm 1b Intent Note to both inboxes...")
                    t_deliv = int(time.time() * 1000)
                    s_p = run_cmd([PILOT_BIN, "message", "send", "--to", prod_tag, INTENT_NOTE_PAYLOAD, "--workspace", prod_ws, "--json"])
                    mid_p = json.loads(s_p.stdout)["id"] if s_p.returncode == 0 else None
                    s_c = run_cmd([PILOT_BIN, "message", "send", "--to", cons_tag, INTENT_NOTE_PAYLOAD, "--workspace", cons_ws, "--json"])
                    mid_c = json.loads(s_c.stdout)["id"] if s_c.returncode == 0 else None
                    if s_p.returncode == 0 or s_c.returncode == 0:
                        intervention_data["delivered"] = True
                        intervention_data["delivered_at_ms"] = t_deliv
                        intervention_data["delivery_timestamp_ms"] = t_deliv
                        if s_p.returncode == 0:
                            intervention_data["producer_delivered_at_ms"] = t_deliv
                        if s_c.returncode == 0:
                            intervention_data["consumer_delivered_at_ms"] = t_deliv
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
                    if s_p.returncode == 0 or s_c.returncode == 0:
                        intervention_data["delivered"] = True
                        intervention_data["delivered_at_ms"] = t_deliv
                        intervention_data["delivery_timestamp_ms"] = t_deliv
                        if s_p.returncode == 0:
                            intervention_data["producer_delivered_at_ms"] = t_deliv
                        if s_c.returncode == 0:
                            intervention_data["consumer_delivered_at_ms"] = t_deliv
                        intervention_data["message_ids"] = {"producer": mid_p, "consumer": mid_c}
                        print(f"[{arm_name}] Radar Warning queued in mailbox at {t_deliv} (mid_p={mid_p}, mid_c={mid_c})")

        # Check notice or attempt prompt delivery if resting (with retry-freeze)
        if intervention_data["delivered"]:
            mid_p = intervention_data["message_ids"].get("producer")
            mid_c = intervention_data["message_ids"].get("consumer")

            # Check if producer noticed via exact envelope inspection
            if intervention_data["producer_noticed_at_ms"] is None:
                p_notice_time = check_session_notice(
                    prod_env["db"], prod_ws, t0_prod, intervention_data["producer_delivered_at_ms"], mid_p
                )
                if p_notice_time:
                    intervention_data["producer_noticed_at_ms"] = p_notice_time
                    intervention_data["producer_notice_at_ms"] = p_notice_time
                    print(f"[{arm_name}] Producer notice confirmed at {p_notice_time}")
                elif mid_p and intervention_data.get("producer_delivery_disposition") is None:
                    # Retry-freeze: only attempt message deliver once!
                    p_rest_twice, _ = verify_twice_resting_empty_composer(
                        prod_session_id, prod_ws, tag=prod_tag, min_delay_sec=1.5
                    )
                    if p_rest_twice:
                        del_p = run_cmd([PILOT_BIN, "message", "deliver", mid_p, "--workspace", prod_ws, "--json"])
                        disposition = parse_delivery_disposition(del_p)
                        intervention_data["producer_delivery_disposition"] = disposition
                        print(f"[{arm_name}] Producer delivery attempted, disposition: {disposition}")

                        # Do NOT equate returncode 0 with model notice; verify via check_session_notice
                        if del_p.returncode == 0:
                            p_notice_post = check_session_notice(
                                prod_env["db"], prod_ws, t0_prod, intervention_data["producer_delivered_at_ms"], mid_p
                            )
                            if p_notice_post:
                                intervention_data["producer_noticed_at_ms"] = p_notice_post
                                intervention_data["producer_notice_at_ms"] = p_notice_post
                                print(f"[{arm_name}] Notice confirmed in Producer session at {p_notice_post}")

            # Check if consumer noticed via exact envelope inspection
            if intervention_data["consumer_noticed_at_ms"] is None:
                c_notice_time = check_session_notice(
                    cons_env["db"], cons_ws, t0_cons, intervention_data["consumer_delivered_at_ms"], mid_c
                )
                if c_notice_time:
                    intervention_data["consumer_noticed_at_ms"] = c_notice_time
                    intervention_data["consumer_notice_at_ms"] = c_notice_time
                    print(f"[{arm_name}] Consumer notice confirmed at {c_notice_time}")
                elif mid_c and intervention_data.get("consumer_delivery_disposition") is None:
                    # Retry-freeze: only attempt message deliver once!
                    c_rest_twice, _ = verify_twice_resting_empty_composer(
                        cons_session_id, cons_ws, tag=cons_tag, min_delay_sec=1.5
                    )
                    if c_rest_twice:
                        del_c = run_cmd([PILOT_BIN, "message", "deliver", mid_c, "--workspace", cons_ws, "--json"])
                        disposition = parse_delivery_disposition(del_c)
                        intervention_data["consumer_delivery_disposition"] = disposition
                        print(f"[{arm_name}] Consumer delivery attempted, disposition: {disposition}")

                        # Do NOT equate returncode 0 with model notice; verify via check_session_notice
                        if del_c.returncode == 0:
                            c_notice_post = check_session_notice(
                                cons_env["db"], cons_ws, t0_cons, intervention_data["consumer_delivered_at_ms"], mid_c
                            )
                            if c_notice_post:
                                intervention_data["consumer_noticed_at_ms"] = c_notice_post
                                intervention_data["consumer_notice_at_ms"] = c_notice_post
                                print(f"[{arm_name}] Notice confirmed in Consumer session at {c_notice_post}")

        # Check resting state
        p_rest, p_reason = is_session_resting(prod_session_id, prod_ws)
        c_rest, c_reason = is_session_resting(cons_session_id, cons_ws)

        # Both sessions modified their target files AND both are resting
        if prod_modified and cons_modified and p_rest and c_rest:
            if settle_start_time is None:
                settle_start_time = time.time()
                print(f"[{arm_name}] Both target files modified & both resting. Starting {SETTLE_REQUIRED_SEC}s settle period...")
            elif time.time() - settle_start_time >= SETTLE_REQUIRED_SEC:
                print(f"[{arm_name}] Both sessions sustained resting idle for {SETTLE_REQUIRED_SEC}s after modifications! Settling complete.")
                settle_completed = True
                break
        else:
            if settle_start_time is not None:
                print(f"[{arm_name}] Session activity resumed (p_rest={p_rest},{p_reason}; c_rest={c_rest},{c_reason}; p_mod={prod_modified}, c_mod={cons_modified}). Resetting settle timer.")
                settle_start_time = None

        time.sleep(2.0)

    timeout_occurred = not settle_completed

    # Final settlement grace if settled
    if settle_completed:
        print("Waiting for final buffer flush (3s)...")
        time.sleep(3.0)

    # Check git diffs and code uptake
    has_prod_change = is_file_modified(prod_ws, "src/event_store/producer.py")
    has_cons_change = is_file_modified(cons_ws, "src/event_store/consumer.py")

    prod_diff = run_cmd(["git", "diff", "HEAD"], cwd=prod_ws).stdout
    if not prod_diff.strip():
        init_commit = run_cmd(["git", "rev-list", "--max-parents=0", "HEAD"], cwd=prod_ws).stdout.strip()
        if init_commit:
            prod_diff = run_cmd(["git", "diff", init_commit], cwd=prod_ws).stdout
    cons_diff = run_cmd(["git", "diff", "HEAD"], cwd=cons_ws).stdout
    if not cons_diff.strip():
        init_commit = run_cmd(["git", "rev-list", "--max-parents=0", "HEAD"], cwd=cons_ws).stdout.strip()
        if init_commit:
            cons_diff = run_cmd(["git", "diff", init_commit], cwd=cons_ws).stdout

    # Code uptake check: did producer add property timestamp or did consumer handle timestamp_us?
    if "@property" in prod_diff and "def timestamp" in prod_diff:
        intervention_data["producer_uptake_detected"] = True
    if "timestamp_us" in cons_diff:
        intervention_data["consumer_uptake_detected"] = True

    # Final check on notice telemetry
    if intervention_data["delivered"]:
        mid_p = intervention_data["message_ids"].get("producer")
        mid_c = intervention_data["message_ids"].get("consumer")
        if intervention_data["producer_noticed_at_ms"] is None:
            p_n = check_session_notice(
                prod_env["db"], prod_ws, t0_prod, intervention_data["producer_delivered_at_ms"], mid_p
            )
            intervention_data["producer_noticed_at_ms"] = p_n
            intervention_data["producer_notice_at_ms"] = p_n
        if intervention_data["consumer_noticed_at_ms"] is None:
            c_n = check_session_notice(
                cons_env["db"], cons_ws, t0_cons, intervention_data["consumer_delivered_at_ms"], mid_c
            )
            intervention_data["consumer_noticed_at_ms"] = c_n
            intervention_data["consumer_notice_at_ms"] = c_n

    # Run external acceptance tests
    print("Running task-specific external acceptance tests...")
    prod_acc = run_external_producer_acceptance(prod_ws)
    cons_acc = run_external_consumer_acceptance(cons_ws)
    print(f"External Producer Acceptance: {'PASS' if prod_acc['passed'] else 'FAIL'}")
    print(f"External Consumer Acceptance: {'PASS' if cons_acc['passed'] else 'FAIL'}")

    # Run internal unit tests in each workspace
    print("Running internal unit tests in each workspace...")
    prod_units = run_unit_tests(prod_ws)
    cons_units = run_unit_tests(cons_ws)
    print(f"Producer unit tests: {'PASS' if prod_units['passed'] else 'FAIL'}")
    print(f"Consumer unit tests: {'PASS' if cons_units['passed'] else 'FAIL'}")

    # Validity Gate: requires non-empty target modifications, external acceptance pass, and no timeout
    validity_gate_passed = (
        not timeout_occurred
        and has_prod_change
        and has_cons_change
        and prod_acc["passed"]
        and cons_acc["passed"]
    )

    grade_res = None
    if validity_gate_passed:
        # Run frozen composite grader only if validity gate passed
        print("Validity gate PASSED: running composite integration acceptance grader...")
        grading_dir = os.path.join(arm_dir, "composite_eval")
        grade_res = grade_composite(prod_ws, cons_ws, grading_dir)
        print(f"Composite Grader Verdict: {grade_res['status']} (exit {grade_res['exit_code']} in {grade_res['duration_sec']:.2f}s)")
        if not grade_res["passed"]:
            print(f"Grader stdout: {grade_res['stdout']}\nStderr: {grade_res['stderr']}")
        overall_status = grade_res["status"]
    else:
        reasons = []
        if timeout_occurred:
            reasons.append("TIMEOUT_FAIL_CLOSED")
        if not has_prod_change:
            reasons.append("PRODUCER_TARGET_NOT_MODIFIED")
        if not has_cons_change:
            reasons.append("CONSUMER_TARGET_NOT_MODIFIED")
        if not prod_acc["passed"]:
            reasons.append("PRODUCER_EXTERNAL_ACCEPTANCE_FAILED")
        if not cons_acc["passed"]:
            reasons.append("CONSUMER_EXTERNAL_ACCEPTANCE_FAILED")
        invalid_reason = " | ".join(reasons)
        print(f"Validity gate FAILED ({invalid_reason}). Composite grader execution refused.")
        grade_res = {
            "exit_code": None,
            "stdout": "",
            "stderr": "",
            "passed": False,
            "status": "NOT_SCORED_VALIDITY_GATE_FAILED",
            "duration_sec": 0.0,
            "details": {"error": f"Composite grader not run: {invalid_reason}"}
        }
        overall_status = f"INVALID_OBSERVATION: {invalid_reason}"

    # Extract authoritative telemetry with launch-time bounds
    prod_telemetry = extract_session_telemetry(prod_env["db"], prod_ws, t0_prod)
    cons_telemetry = extract_session_telemetry(cons_env["db"], cons_ws, t0_cons)

    # Clean up sessions
    print("Cleaning up agent sessions...")
    run_cmd([PILOT_BIN, "kill", prod_session_id])
    run_cmd([PILOT_BIN, "kill", cons_session_id])

    pair_results = {
        "arm_name": arm_name,
        "pair_num": pair_num,
        "intervention_type": intervention_type,
        "run_dir": arm_dir,
        "validity_gate": {
            "passed": validity_gate_passed,
            "timeout_occurred": timeout_occurred,
            "has_prod_change": has_prod_change,
            "has_cons_change": has_cons_change,
            "producer_acceptance": prod_acc,
            "consumer_acceptance": cons_acc
        },
        "producer": {
            "session_id": prod_session_id,
            "tag": prod_tag,
            "unit_tests": prod_units,
            "external_acceptance": prod_acc,
            "diff_snippet": prod_diff[:500],
            "telemetry": prod_telemetry
        },
        "consumer": {
            "session_id": cons_session_id,
            "tag": cons_tag,
            "unit_tests": cons_units,
            "external_acceptance": cons_acc,
            "diff_snippet": cons_diff[:500],
            "telemetry": cons_telemetry
        },
        "intervention": intervention_data,
        "composite_grader": grade_res,
        "overall_status": overall_status
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

    ts = int(time.time())
    summary_file = os.path.join(FEASIBILITY_ROOT, "feasibility_summary.json")
    ts_summary = os.path.join(FEASIBILITY_ROOT, f"feasibility_summary_{ts}.json")
    with open(ts_summary, "w") as f:
        json.dump(all_results, f, indent=2)
    with open(summary_file, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nAll feasibility runs complete. Summary written to {summary_file} (and {ts_summary})")


if __name__ == "__main__":
    main()
