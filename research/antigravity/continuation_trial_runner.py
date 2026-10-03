#!/usr/bin/env python3
"""Automated, reproducible test harness for Scoped Reversible Continuation Preflight of aplexer-7efa493.

Executes the protocol specified in TRIAL-MANIFEST.md and authorized by Principals
under CONDITIONAL-PILOT-OK (Muse R21 / head-scope-correction.md):
1. Candidate binary: aplexer-7efa493 (sha256: 06b1a842...)
   Rollback CLI: /home/alexey/.local/bin/aplexer (sha256: 8d49a216...) - strictly preserved.
2. Isolated workspace (.local/continuation-trial/workspace) with standalone git repo.
3. Fresh quota, disk headroom, and memory floor captured at preflight.
4. Genuine turn-completion boot: receiver boots, settles to UI idle, executes initial
   'aplexer whoami --json' tool call (without workspace override), and debounces to idle,
   establishing authentic turn completion baseline.
5. Strict composer classification supporting OpenCode bordered composer UI and shell/codex prompts.
6. Twice-captured full composer/state captures before every delivery with durable evidence storage.
7. Negative 1: Active child tool execution negative (probe deliver occurs strictly while child
   process 'sleep 15' is actively running in /proc and DB).
8. Negative 2: Unfinished composer draft negative (probe deliver occurs while composer has draft).
9. Positive Turn 1: External-driver receiver continuation cycle 1 (turn1_<nonce>.txt + correlated receiver ACK).
10. Positive Turn 2: External-driver receiver continuation cycle 2 (turn2_<nonce>.txt + correlated receiver ACK).
11. PTY echo & raw diff preservation (verifying no probe echo in output history).
12. Full Markdown & JSON telemetry report with dynamic gate derivations (never hardcoded PASS).
13. Clean teardown and verification that installed binary remains untouched.
"""
import hashlib
import json
import os
import re
import shlex
import shutil
import sqlite3
import subprocess
import sys
import time
import traceback

PILOT_BIN = "/home/alexey/git/cloudflare-agent-git/.local/producer-review/bin/aplexer-7efa493"
ROLLBACK_BIN = "/home/alexey/.local/bin/aplexer"
EXPECTED_CANDIDATE_SHA = "06b1a84247c96cdbf8272786c8540fd8047443e9613c63e437de26efb7bf2d86"
EXPECTED_ROLLBACK_SHA = "8d49a216d43c70843bc07705f4c11eb13f3eb51646d5c6fc204ce0796ce618c4"

BASE_DIR = "/home/alexey/git/cloudflare-agent-git/.local/continuation-trial"
WORKSPACE = os.path.join(BASE_DIR, "workspace")
CONFIG_DIR = os.path.join(BASE_DIR, "config")
DATA_DIR = os.path.join(BASE_DIR, "data")
STATE_DIR = os.path.join(BASE_DIR, "state")
EVIDENCE_DIR = os.path.join(BASE_DIR, "evidence")
DB_PATH = os.path.join(DATA_DIR, "opencode", "opencode.db")
PRISTINE_DB_SOURCE = "/home/alexey/git/cloudflare-agent-git/.local/pilot-ca1/data/opencode/opencode.db"
OPENCODE_BIN = "/home/alexey/.nvm/versions/node/v24.13.1/bin/opencode"

# Named subsequent adoption target
REAL_HEAD_TARGET = "space-bunny-head (2d829c93-8363-477d-b2fd-10f0a3af006e) on task label-binding-residual-repair / stowaway manifest"

REPORT_MD = os.path.join(BASE_DIR, "TRIAL-REPORT.md")
REPORT_JSON = os.path.join(BASE_DIR, "trial_results.json")


def run_host_cmd(cmd, timeout=30):
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def parse_json_safely(output_str):
    if not output_str:
        return None
    try:
        return json.loads(output_str)
    except Exception:
        pass
    start_idx = output_str.find('{')
    if start_idx != -1:
        depth = 0
        in_string = False
        escape = False
        for i in range(start_idx, len(output_str)):
            c = output_str[i]
            if escape:
                escape = False
                continue
            if c == '\\':
                escape = True
                continue
            if c == '"':
                in_string = not in_string
                continue
            if not in_string:
                if c == '{':
                    depth += 1
                elif c == '}':
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(output_str[start_idx:i+1])
                        except Exception:
                            break
    for line in output_str.strip().splitlines():
        line = line.strip()
        if line.startswith('{') and line.endswith('}'):
            try:
                return json.loads(line)
            except Exception:
                pass
    return None


def composer_classifier(screen, tag="continuation-receiver"):
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


def get_status(session_uuid):
    res = run_host_cmd([PILOT_BIN, "status", session_uuid, "--workspace", WORKSPACE, "--json"])
    if res.returncode != 0:
        return None
    return parse_json_safely(res.stdout)


def capture_screen(session_uuid):
    res = run_host_cmd([PILOT_BIN, "capture", session_uuid, "--workspace", WORKSPACE, "--screen", "--plain"])
    return res.stdout


def exec_in_sender(sender_uuid, cmd_args, timeout=30):
    """Executes a command inside the native trial-sender session and captures exit code and output."""
    script_path = os.path.join(WORKSPACE, ".sender_script.sh")
    with open(script_path, "w") as f:
        f.write("#!/bin/bash\n")
        f.write(" ".join(shlex.quote(str(a)) for a in cmd_args) + "\n")
    os.chmod(script_path, 0o755)

    out_file = os.path.join(WORKSPACE, ".sender_cmd_out")
    done_file = os.path.join(WORKSPACE, ".sender_cmd_done")
    if os.path.exists(out_file):
        try: os.remove(out_file)
        except OSError: pass
    if os.path.exists(done_file):
        try: os.remove(done_file)
        except OSError: pass

    full_cmd = f"{script_path} > {out_file} 2>&1; echo $? > {done_file}"
    run_host_cmd([PILOT_BIN, "send", sender_uuid, full_cmd, "--workspace", WORKSPACE, "--enter"])

    t0 = time.time()
    while time.time() - t0 < timeout:
        if os.path.exists(done_file):
            try:
                with open(done_file) as f:
                    code_str = f.read().strip()
                if code_str:
                    exit_code = int(code_str)
                    output = ""
                    if os.path.exists(out_file):
                        with open(out_file) as f:
                            output = f.read()
                    return exit_code, output
            except (ValueError, IOError):
                pass
        time.sleep(0.2)
    raise TimeoutError(f"Command timed out in trial-sender: {cmd_args}")


def is_resting(session_uuid, allow_reported_none=False):
    s = get_status(session_uuid)
    screen = capture_screen(session_uuid)
    if s is None or not screen:
        return False, screen, "missing_session_or_screen"
    
    # 1. Full empty composer classification
    comp_state = composer_classifier(screen, "continuation-receiver")
    if comp_state != "empty":
        return False, screen, f"composer_{comp_state}"

    # 2. Authentic reported idle check: reported_state must be 'idle' (or None on initial UI boot before first turn)
    reported = s.get("reported_state")
    if allow_reported_none:
        if reported not in ("idle", None):
            return False, screen, f"reported_{reported}"
    else:
        if reported != "idle":
            return False, screen, f"reported_{reported}"

    # 3. Uncontradicted resting state: subsequent PTY activity must NOT exceed reported_state_at_ms + 250ms
    rep_at = s.get("reported_state_at_ms") or 0
    last_act = s.get("last_activity_ms") or 0
    if reported == "idle" and rep_at > 0:
        if last_act > rep_at + 250:
            return False, screen, f"activity_contradiction_delta_{last_act - rep_at}ms"

    return True, screen, "empty"


def verify_receiver_idle_twice(receiver_uuid, step_name, delta=2.0, max_wait=90, allow_reported_none=False):
    """Twice-captured full composer/state captures: ensures resting state at t and t+delta.
    Saves both captures into evidence directory for durable auditability.
    """
    print(f"[{step_name}] Verifying receiver idle state with twice full empty-composer captures (delta={delta}s, allow_reported_none={allow_reported_none})...")
    t0 = time.time()
    while time.time() - t0 < max_wait:
        ok1, screen1, reason1 = is_resting(receiver_uuid, allow_reported_none=allow_reported_none)
        if not ok1:
            s = get_status(receiver_uuid)
            print(f"[{time.time()-t0:.1f}s] Waiting for resting: reason={reason1}, reported={s.get('reported_state') if s else None}")
            time.sleep(1)
            continue
        
        # Save first capture
        ev1 = os.path.join(EVIDENCE_DIR, f"{step_name}_capture1_{int(time.time()*1000)}.txt")
        with open(ev1, "w") as f:
            f.write(screen1)

        time.sleep(delta)
        ok2, screen2, reason2 = is_resting(receiver_uuid, allow_reported_none=allow_reported_none)
        if ok2:
            # Save second capture
            ev2 = os.path.join(EVIDENCE_DIR, f"{step_name}_capture2_{int(time.time()*1000)}.txt")
            with open(ev2, "w") as f:
                f.write(screen2)
            print(f"[{step_name}] Receiver confirmed resting idle (composer empty) at twice captures (total {time.time()-t0:.1f}s)")
            return True, screen2, ev1, ev2
        print(f"[{time.time()-t0:.1f}s] Second capture failed resting check: {reason2}")
        time.sleep(1)
    
    last_screen = capture_screen(receiver_uuid)
    return False, last_screen, None, None


def get_receiver_opencode_session_id(workspace, since_ms=None, db_path=None):
    """
    Get the OpenCode session ID created in workspace at or after since_ms.
    Enforces exact 1:1 root session mapping and fails closed on ambiguity:
    1. Filters for root sessions (parent_id IS NULL OR parent_id = '') in the target workspace directory.
    2. Filters time_created >= since_ms if since_ms is specified.
    3. If exactly one matching root session exists, returns its ID.
    4. If zero matching root sessions exist, returns None.
    5. If multiple matching root sessions exist (ambiguity/collision), fails closed and returns None.
    Child sessions (parent_id NOT NULL) never collide with or override the receiver root session.
    """
    path = db_path if db_path is not None else DB_PATH
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=2.0)
        cur = con.cursor()
        query = """SELECT id FROM session
                   WHERE directory = ?
                     AND (parent_id IS NULL OR parent_id = '')"""
        params = [workspace]
        if since_ms is not None:
            query += " AND time_created >= ?"
            params.append(since_ms)
        query += " ORDER BY time_created ASC;"
        cur.execute(query, tuple(params))
        rows = cur.fetchall()
        con.close()
        if len(rows) == 1:
            return rows[0][0]
        # Ambiguous (len > 1) or not found (len == 0): fail closed
        return None
    except Exception as e:
        print("DB session query error:", e)
        return None


def query_db_part_command(cmd_substr, opencode_sid=None, since_ms=None, db_path=None):
    """Query opencode.db part table for a bash tool call containing cmd_substr, optionally filtered by session_id and since_ms."""
    path = db_path if db_path is not None else DB_PATH
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=2.0)
        cur = con.cursor()
        query = """SELECT id, time_created, time_updated,
                          json_extract(data, '$.state.status'),
                          json_extract(data, '$.state.time.start'),
                          json_extract(data, '$.state.time.end'),
                          json_extract(data, '$.state.input.command'),
                          json_extract(data, '$.state.output')
                   FROM part
                   WHERE json_extract(data, '$.tool') = 'bash'
                     AND json_extract(data, '$.state.input.command') LIKE ?"""
        params = [f"%{cmd_substr}%"]
        if opencode_sid is not None:
            query += " AND session_id = ?"
            params.append(opencode_sid)
        if since_ms is not None:
            query += " AND time_created >= ?"
            params.append(since_ms)
        query += " ORDER BY time_created DESC LIMIT 1;"
        cur.execute(query, tuple(params))
        row = cur.fetchone()
        con.close()
        return row
    except Exception as e:
        print("DB query error:", e)
        return None


def verify_whoami_identity(whoami_output, expected_uuid, expected_workspace):
    """
    Strict first-JSON-object identity and binding guard.
    Parses the first JSON object from whoami tool output and enforces:
    1. obj["id"] == expected_uuid (exact match, no substring pass)
    2. obj["workspace"] == expected_workspace (exact match)
    3. obj["binding_check"] must be present as a dict with obj["binding_check"]["ok"] is True.
       Missing, null, non-dict, or ok!=True fails closed.
    """
    if not (whoami_output is not None and len(whoami_output.strip()) > 0):
        return False, "whoami output is empty", {}
    
    stripped = whoami_output.strip()
    start_idx = stripped.find("{")
    if start_idx == -1:
        return False, "no JSON object start '{' found in output", {}
    
    try:
        obj, _ = json.JSONDecoder().raw_decode(stripped[start_idx:])
    except Exception as e:
        return False, f"first JSON object unparseable: {e}", {}
    
    if not isinstance(obj, dict):
        return False, f"first JSON object is not a dict: {type(obj)}", {}
    
    if obj.get("id") != expected_uuid:
        return False, f"first JSON id mismatch: expected {expected_uuid!r}, got {obj.get('id')!r}", obj
    
    if obj.get("workspace") != expected_workspace:
        return False, f"first JSON workspace mismatch: expected {expected_workspace!r}, got {obj.get('workspace')!r}", obj
    
    bc = obj.get("binding_check")
    if bc is None:
        return False, "binding_check is missing or null", obj
    if not isinstance(bc, dict):
        return False, f"binding_check is not a dict: {type(bc)}", obj
    if bc.get("ok") is not True:
        return False, f"binding_check.ok is not True: {bc}", obj
        
    return True, "verified", obj


def cleanup_trial_sessions():
    res = run_host_cmd([PILOT_BIN, "list", "--json"])
    if res.returncode == 0:
        data = parse_json_safely(res.stdout)
        if isinstance(data, list):
            for s in data:
                if s.get("workspace") == WORKSPACE:
                    sid = s.get("id")
                    if sid:
                        print(f"Cleaning up lingering session {sid} ({s.get('tag')})...")
                        run_host_cmd([PILOT_BIN, "kill", sid])


def main():
    print("=================================================================")
    print("STARTING SCOPED REVERSIBLE CONTINUATION PREFLIGHT (aplexer-7efa493)")
    print("=================================================================")

    # 1. Verification of binaries, environment, and resources
    bin_sha = sha256_file(PILOT_BIN)
    rollback_sha = sha256_file(ROLLBACK_BIN)
    print(f"Candidate Binary:       {PILOT_BIN}")
    print(f"Candidate SHA256:       {bin_sha}")
    print(f"Rollback Installed CLI: {ROLLBACK_BIN}")
    print(f"Rollback SHA256:        {rollback_sha}")
    assert bin_sha == EXPECTED_CANDIDATE_SHA, f"Candidate SHA mismatch! Got {bin_sha}, expected {EXPECTED_CANDIDATE_SHA}"
    assert rollback_sha == EXPECTED_ROLLBACK_SHA, f"Rollback SHA mismatch! Got {rollback_sha}, expected {EXPECTED_ROLLBACK_SHA}"

    df_out = run_host_cmd(["df", "-h", "/home/alexey/git/cloudflare-agent-git"]).stdout.strip()
    free_out = run_host_cmd(["free", "-m"]).stdout.strip()
    quota_res = run_host_cmd(["quse", "--json"])
    all_quotas = parse_json_safely(quota_res.stdout) or {}
    target_quota = all_quotas.get("go", {})
    codex_quota = all_quotas.get("codex", {})
    gemini_quota = all_quotas.get("gemini", {})
    zai_quota = all_quotas.get("zai", {})

    target_limit_reached = target_quota.get("details", {}).get("limit_reached", False)
    go_5h = target_quota.get("windows", {}).get("5h", {}).get("percent_remaining")
    go_7d = target_quota.get("windows", {}).get("7d", {}).get("percent_remaining")
    go_monthly = target_quota.get("windows", {}).get("monthly", {}).get("percent_remaining")

    assert not target_limit_reached, "Target OpenCode Go provider limit_reached is True!"
    assert go_5h is not None and go_5h >= 15.0, f"Target OpenCode Go 5h quota insufficient or missing: {go_5h}% (reserve 15%)"
    assert go_7d is not None and go_7d >= 15.0, f"Target OpenCode Go 7d quota insufficient or missing: {go_7d}% (reserve 15%)"
    if go_monthly is not None:
        assert go_monthly >= 15.0, f"Target OpenCode Go monthly quota insufficient: {go_monthly}%"

    quota_data = {
        "target_provider": "go (opencode-go / muse)",
        "go_windows": {"5h_remaining": go_5h, "7d_remaining": go_7d, "monthly_remaining": go_monthly},
        "target_allowed": True,
        "codex_windows": codex_quota.get("windows", {}),
        "gemini_windows": gemini_quota.get("windows", {}),
        "zai_windows": zai_quota.get("windows", {}),
    }
    print("--- Host Resource Headroom ---")
    print(df_out)
    print(free_out)
    print("--- Fresh Provider Quotas ---")
    print(json.dumps(quota_data, indent=2))

    os.makedirs(EVIDENCE_DIR, exist_ok=True)
    cleanup_trial_sessions()
    time.sleep(1)

    # Clean previous workspace trial files to avoid counting old artifacts as new
    print(f"Cleaning previous trial artifacts in workspace: {WORKSPACE}...")
    if os.path.exists(WORKSPACE):
        for fname in os.listdir(WORKSPACE):
            if fname.startswith("turn1_") or fname.startswith("turn2_") or fname.startswith(".sender_cmd"):
                fpath = os.path.join(WORKSPACE, fname)
                try:
                    os.remove(fpath)
                except OSError:
                    pass

    # Restore pristine opencode.db snapshot to ensure clean state (no interrupted tool calls from previous runs)
    print(f"Restoring pristine SQLite database from {PRISTINE_DB_SOURCE}...")
    assert os.path.exists(PRISTINE_DB_SOURCE), f"Pristine source DB missing at {PRISTINE_DB_SOURCE}!"
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    for ext in ["", "-wal", "-shm"]:
        target_f = DB_PATH + ext
        if os.path.exists(target_f):
            os.remove(target_f)
    shutil.copy2(PRISTINE_DB_SOURCE, DB_PATH)

    # Verify opencode.db is present before launch
    assert os.path.exists(DB_PATH), f"opencode.db missing at {DB_PATH}!"
    con_check = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    cur_check = con_check.cursor()
    cur_check.execute("SELECT count(*) FROM session;")
    sess_count = cur_check.fetchone()[0]
    con_check.close()
    print(f"Verified pristine DB restored with {sess_count} baseline session(s).")

    # 2. Launch fresh disposable sessions under cgroups
    print("\n--- Step 1: Launching disposable receiver and sender sessions ---")
    t_launch_ms = int(time.time() * 1000)
    init_cmd = f"{PILOT_BIN} whoami --json"
    start_recv_cmd = [
        PILOT_BIN, "start",
        "--workspace", WORKSPACE,
        "--tag", "continuation-receiver",
        "--engine", "opencode",
        "--env", f"XDG_DATA_HOME={DATA_DIR}",
        "--env", f"XDG_CONFIG_HOME={CONFIG_DIR}",
        "--env", f"XDG_STATE_HOME={STATE_DIR}",
        "--memory", "1500M",
        "--pids", "256",
        "--json",
        "--",
        OPENCODE_BIN,
        "--auto",
        "--prompt", f"Run this initial baseline tool command: {init_cmd}"
    ]
    res_recv = run_host_cmd(start_recv_cmd)
    assert res_recv.returncode == 0, f"Failed to start receiver: {res_recv.stderr}"
    receiver_data = parse_json_safely(res_recv.stdout)
    assert receiver_data is not None, f"Failed to parse receiver output: {res_recv.stdout}"
    receiver_uuid = receiver_data["id"]
    receiver_history_path = receiver_data["history_path"]
    print(f"Receiver Session ID: {receiver_uuid}")
    print(f"Receiver History Path: {receiver_history_path}")

    start_sender_cmd = [
        PILOT_BIN, "start",
        "--workspace", WORKSPACE,
        "--tag", "continuation-sender",
        "--engine", "shell",
        "--memory", "500M",
        "--pids", "64",
        "--json"
    ]
    res_sender = run_host_cmd(start_sender_cmd)
    assert res_sender.returncode == 0, f"Failed to start sender: {res_sender.stderr}"
    sender_data = parse_json_safely(res_sender.stdout)
    assert sender_data is not None, f"Failed to parse sender output: {res_sender.stdout}"
    sender_uuid = sender_data["id"]
    print(f"Sender Session ID: {sender_uuid}")

    # Results dictionary
    results = {
        "candidate_binary": PILOT_BIN,
        "candidate_sha256": bin_sha,
        "rollback_binary": ROLLBACK_BIN,
        "rollback_sha256": rollback_sha,
        "receiver_session_id": receiver_uuid,
        "sender_session_id": sender_uuid,
        "opencode_session_id": "auto_created",
        "workspace": WORKSPACE,
        "subsequent_real_head_target": REAL_HEAD_TARGET,
        "resource_headroom": {
            "df": df_out,
            "free": free_out,
            "quota": quota_data
        },
        "steps": {},
        "overall_status": "IN_PROGRESS"
    }

    try:
        # Step 2: Establish Baseline via Launch Initial Task Entrypoint
        print("\n--- Step 2: Waiting for Baseline Initial Task Turn to Execute and Settle into Authentic Resting Idle ---")
        ok_idle, screen_idle, ev1, ev2 = verify_receiver_idle_twice(receiver_uuid, "boot_turn_idle", delta=2.0, max_wait=120, allow_reported_none=False)
        assert ok_idle, f"Receiver failed to complete initial baseline turn or reach authentic resting idle! Screen:\n{screen_idle}"
        print("Receiver successfully completed initial baseline turn and settled into authentic resting idle.")

        # Verify actual whoami tool execution in DB part table (Codex 01a1012a / C-1258 / C-1259 directive)
        receiver_opencode_sid = get_receiver_opencode_session_id(WORKSPACE, since_ms=t_launch_ms)
        print(f"Receiver OpenCode Session ID: {receiver_opencode_sid}")
        assert receiver_opencode_sid is not None, f"Failed to identify OpenCode session ID in {WORKSPACE} after {t_launch_ms}!"
        results["opencode_session_id"] = receiver_opencode_sid
        
        whoami_part = query_db_part_command("whoami", opencode_sid=receiver_opencode_sid, since_ms=t_launch_ms)
        print(f"DB Part row for baseline whoami tool: {whoami_part}")
        assert whoami_part is not None, f"Baseline whoami tool call not found in DB part table for session {receiver_opencode_sid} after {t_launch_ms}!"
        whoami_part_id, _, _, whoami_status, whoami_start, whoami_end, whoami_cmd, whoami_output = whoami_part
        assert whoami_status == "completed", f"Baseline whoami tool status is '{whoami_status}', expected 'completed'!"
        print(f"Verified baseline whoami execution in DB: id={whoami_part_id}, status={whoami_status}")
        print(f"Baseline whoami tool output: {whoami_output}")
        assert whoami_output is not None and len(whoami_output) > 0, "Baseline whoami tool output is empty!"
        ok_id, id_err, whoami_json = verify_whoami_identity(whoami_output, receiver_uuid, WORKSPACE)
        assert ok_id, f"First-model whoami identity validation failed: {id_err}! Output: {whoami_output}"
        print(f"Verified first-model whoami identity: id={whoami_json.get('id')}, workspace={whoami_json.get('workspace')}, binding_check={whoami_json.get('binding_check')}")

        results["steps"]["boot_turn_baseline"] = {
            "passed": True,
            "launch_prompt": f"Run this initial baseline tool command: {init_cmd}",
            "evidence_capture_1": ev1,
            "evidence_capture_2": ev2,
            "whoami_part_id": whoami_part_id,
            "whoami_status": whoami_status,
            "whoami_output": whoami_output,
            "note": "Native executor launch with initial task entrypoint. Verified whoami tool completed and settled into authentic reported_state=='idle'."
        }

        # Step 3: Test Negative 1 - Active Child Tool Process Rejection
        print("\n--- Step 3: Test Negative 1 - Active Child Tool Process Rejection ---")
        sleep_nonce = str(int(time.time()))
        sleep_marker = f"child-sleep-marker-{sleep_nonce}"
        cmd_to_run = f"sleep 15 && echo {sleep_marker}"
        print(f"Prompting receiver to execute: {cmd_to_run}")

        send_rc, send_out = exec_in_sender(
            sender_uuid,
            [PILOT_BIN, "message", "send", "--to", "continuation-receiver", f"Run this command: {cmd_to_run}", "--workspace", WORKSPACE, "--json"]
        )
        assert send_rc == 0, f"Failed to send tool trigger message: {send_out}"
        trigger_msg = parse_json_safely(send_out)
        trigger_id = trigger_msg["id"]
        print(f"Trigger Message ID: {trigger_id}")

        deliv_rc, deliv_out = exec_in_sender(
            sender_uuid,
            [PILOT_BIN, "message", "deliver", trigger_id, "--workspace", WORKSPACE, "--json"]
        )
        assert deliv_rc == 0, f"Failed to deliver tool trigger: {deliv_out}"
        print(f"Tool trigger delivered. Monitoring /proc for active child sleep process...")

        child_pid = None
        t_start_wait = time.time()
        while time.time() - t_start_wait < 25:
            pgrep_res = run_host_cmd(["pgrep", "-f", f"sleep 15.*{sleep_marker}"])
            if pgrep_res.returncode == 0 and pgrep_res.stdout.strip():
                pids = pgrep_res.stdout.strip().split()
                child_pid = int(pids[0])
                break
            time.sleep(0.3)

        assert child_pid is not None, "Failed to observe active child sleep process in /proc!"
        print(f"Active Child Tool Process CONFIRMED running: PID {child_pid}")

        proc_stat = run_host_cmd(["cat", f"/proc/{child_pid}/stat"]).stdout
        proc_cmdline = run_host_cmd(["cat", f"/proc/{child_pid}/cmdline"]).stdout
        ev_proc = os.path.join(EVIDENCE_DIR, f"negative_active_tool_pid_{child_pid}.txt")
        with open(ev_proc, "w") as f:
            f.write(f"PID: {child_pid}\nSTAT: {proc_stat}\nCMDLINE: {proc_cmdline}\n")

        pre_probe_bytes = 0
        if os.path.exists(receiver_history_path):
            pre_probe_bytes = os.path.getsize(receiver_history_path)

        print("Preparing probe delivery while child sleep process is active...")
        probe_rc, probe_out = exec_in_sender(
            sender_uuid,
            [PILOT_BIN, "message", "send", "--to", "continuation-receiver", f"PROBE_ACTIVE_TOOL_{sleep_nonce}", "--workspace", WORKSPACE, "--json"]
        )
        assert probe_rc == 0, f"Failed to send probe message: {probe_out}"
        probe_msg = parse_json_safely(probe_out)
        probe_id = probe_msg["id"]

        t_probe_attempt = int(time.time() * 1000)
        deliver_probe_rc, deliver_probe_out = exec_in_sender(
            sender_uuid,
            [PILOT_BIN, "message", "deliver", probe_id, "--workspace", WORKSPACE]
        )
        t_probe_finish = int(time.time() * 1000)

        is_child_still_alive = (run_host_cmd(["kill", "-0", str(child_pid)]).returncode == 0)
        print(f"Probe deliver returncode: {deliver_probe_rc}")
        print(f"Probe deliver output:     {deliver_probe_out.strip()}")
        print(f"Child PID {child_pid} still live after probe deliver: {is_child_still_alive}")

        assert deliver_probe_rc == 1, f"Probe deliver did NOT return exit 1! Output: {deliver_probe_out}"
        assert is_child_still_alive, f"Child PID {child_pid} was not alive during probe attempt!"

        # Verify probe message remains in inbox (fail-closed preservation)
        log_res = run_host_cmd([PILOT_BIN, "message", "log", "--workspace", WORKSPACE, "--json"])
        assert log_res.returncode == 0, f"Failed to get message log: {log_res.stderr}"
        msg_list = parse_json_safely(log_res.stdout) or []
        probe_env = next((m for m in msg_list if m.get("id") == probe_id), None)
        assert probe_env is not None, f"Probe message {probe_id} not found in workspace message log!"
        assert probe_env.get("delivery") == "inbox", f"Probe message {probe_id} delivery was {probe_env.get('delivery')}, expected 'inbox'!"
        print(f"Probe message {probe_id} safely preserved in inbox (delivery='inbox').")

        print("Waiting for sleep tool to complete and receiver to return to resting idle...")
        time.sleep(10)
        ok_idle_post_tool, screen_post_tool, ev1_pt, ev2_pt = verify_receiver_idle_twice(receiver_uuid, "post_tool_idle", delta=2.0, max_wait=60)
        assert ok_idle_post_tool, "Receiver failed to return to resting idle after sleep tool!"

        part_row = query_db_part_command(sleep_marker, opencode_sid=receiver_opencode_sid, since_ms=t_probe_attempt - 15000)
        print("DB Part row for sleep tool:", part_row)
        assert part_row is not None, "Failed to find sleep tool in DB part table!"
        part_id, part_created, part_updated, part_status, part_start, part_end, part_cmd, part_output = part_row
        print(f"DB Tool Part: start={part_start}, probe={t_probe_attempt}, end={part_end}")
        assert part_start is not None and part_end is not None, "DB start/end timestamps missing!"
        assert part_start <= t_probe_attempt <= part_end, f"Probe timestamp {t_probe_attempt} was not within [{part_start}, {part_end}]!"

        # Raw PTY history slice and diff preservation
        post_probe_bytes = os.path.getsize(receiver_history_path)
        with open(receiver_history_path, "rb") as f:
            f.seek(pre_probe_bytes)
            appended_bytes = f.read()
        
        diff_file = os.path.join(EVIDENCE_DIR, f"pty_history_diff_tool_probe_{sleep_nonce}.bin")
        with open(diff_file, "wb") as f:
            f.write(appended_bytes)
        
        probe_str_bytes = f"PROBE_ACTIVE_TOOL_{sleep_nonce}".encode("utf-8")
        probe_echo_detected = probe_str_bytes in appended_bytes
        print(f"PTY output history: appended {len(appended_bytes)} bytes, probe echo detected: {probe_echo_detected}")
        assert not probe_echo_detected, "Probe string leaked/echoed into receiver output history!"

        results["steps"]["negative_active_tool"] = {
            "passed": True,
            "child_pid": child_pid,
            "probe_id": probe_id,
            "probe_attempt_timestamp_ms": t_probe_attempt,
            "deliver_probe_exit_code": deliver_probe_rc,
            "db_part_id": part_id,
            "db_part_start_ms": part_start,
            "db_part_end_ms": part_end,
            "no_observed_probe_echo_in_history": True,
            "appended_history_bytes": len(appended_bytes),
            "pty_diff_file": diff_file,
            "evidence_proc_file": ev_proc
        }

        # Step 4: Test Negative 2 - Unfinished Draft Composer Rejection
        print("\n--- Step 4: Test Negative 2 - Unfinished Draft Composer Rejection ---")
        draft_nonce = str(int(time.time()))
        draft_text = f"UNSUBMITTED_DRAFT_TEXT_{draft_nonce}"
        print(f"Injecting draft text into receiver composer: {draft_text}")

        run_host_cmd([PILOT_BIN, "send", receiver_uuid, draft_text, "--workspace", WORKSPACE])
        time.sleep(1)

        draft_screen = capture_screen(receiver_uuid)
        comp_class_draft = composer_classifier(draft_screen, "continuation-receiver")
        ev_draft_screen = os.path.join(EVIDENCE_DIR, f"negative_draft_screen_{draft_nonce}.txt")
        with open(ev_draft_screen, "w") as f:
            f.write(draft_screen)
        
        print(f"Composer classified during draft test: '{comp_class_draft}'")
        assert comp_class_draft == "draft" or draft_text in draft_screen, f"Draft text not visible or classified as draft! Comp={comp_class_draft}\n{draft_screen}"

        probe_draft_rc, probe_draft_out = exec_in_sender(
            sender_uuid,
            [PILOT_BIN, "message", "send", "--to", "continuation-receiver", f"PROBE_DRAFT_{draft_nonce}", "--workspace", WORKSPACE, "--json"]
        )
        assert probe_draft_rc == 0, f"Failed to send draft probe message: {probe_draft_out}"
        probe_draft_id = parse_json_safely(probe_draft_out)["id"]

        deliv_draft_rc, deliv_draft_out = exec_in_sender(
            sender_uuid,
            [PILOT_BIN, "message", "deliver", probe_draft_id, "--workspace", WORKSPACE]
        )
        print(f"Draft probe deliver returncode: {deliv_draft_rc}")
        print(f"Draft probe deliver output:     {deliv_draft_out.strip()}")
        assert deliv_draft_rc == 1, f"Deliver against draft composer did NOT reject with exit 1! Output: {deliv_draft_out}"

        # Verify draft probe message remains in inbox (fail-closed preservation)
        log_res2 = run_host_cmd([PILOT_BIN, "message", "log", "--workspace", WORKSPACE, "--json"])
        msg_list2 = parse_json_safely(log_res2.stdout) or []
        probe_draft_env = next((m for m in msg_list2 if m.get("id") == probe_draft_id), None)
        assert probe_draft_env is not None, f"Draft probe message {probe_draft_id} not found in message log!"
        assert probe_draft_env.get("delivery") == "inbox", f"Draft probe delivery was {probe_draft_env.get('delivery')}, expected 'inbox'!"
        print(f"Draft probe message {probe_draft_id} safely preserved in inbox (delivery='inbox').")

        # Clear draft from composer
        run_host_cmd([PILOT_BIN, "send", receiver_uuid, "\x03\x15", "--workspace", WORKSPACE])
        time.sleep(1)

        ok_idle_post_draft, screen_post_draft, ev1_pd, ev2_pd = verify_receiver_idle_twice(receiver_uuid, "post_draft_idle", delta=2.0, max_wait=30)
        assert ok_idle_post_draft, "Receiver failed to return to resting idle after draft cleared!"

        results["steps"]["negative_draft_composer"] = {
            "passed": True,
            "draft_text": draft_text,
            "composer_classification": comp_class_draft,
            "probe_draft_id": probe_draft_id,
            "deliver_draft_exit_code": deliv_draft_rc,
            "evidence_screen_file": ev_draft_screen
        }

        # Step 5: Test Positive Turn 1 - External-Driver Continuation Cycle 1
        print("\n--- Step 5: Test Positive Turn 1 - External-Driver Continuation Cycle 1 ---")
        turn1_nonce = str(int(time.time()))
        turn1_file = f"turn1_{turn1_nonce}.txt"
        turn1_path = os.path.join(WORKSPACE, turn1_file)
        turn1_content = f"CONTINUATION_TURN1_VERIFIED_{turn1_nonce}"

        ok_turn1_pre, _, ev1_t1, ev2_t1 = verify_receiver_idle_twice(receiver_uuid, "turn1_pre", delta=2.0, max_wait=30)
        assert ok_turn1_pre, "Receiver was not at resting idle before Turn 1!"

        turn1_prompt = (
            f"Please write exactly '{turn1_content}' to file {turn1_file} in your workspace. "
            f"After writing the file, reply to this message with 'ACK_TURN1_{turn1_nonce}'."
        )
        send_t1_rc, send_t1_out = exec_in_sender(
            sender_uuid,
            [PILOT_BIN, "message", "send", "--to", "continuation-receiver", turn1_prompt, "--workspace", WORKSPACE, "--json"]
        )
        assert send_t1_rc == 0, f"Failed to send Turn 1 message: {send_t1_out}"
        msg_t1_id = parse_json_safely(send_t1_out)["id"]
        print(f"Turn 1 Message ID: {msg_t1_id}")

        t_deliver_t1 = int(time.time() * 1000)
        deliv_t1_rc, deliv_t1_out = exec_in_sender(
            sender_uuid,
            [PILOT_BIN, "message", "deliver", msg_t1_id, "--workspace", WORKSPACE]
        )
        print(f"Turn 1 Deliver exit code: {deliv_t1_rc}")
        assert deliv_t1_rc == 0, f"Turn 1 deliver failed! Output: {deliv_t1_out}"

        print(f"Waiting for Turn 1 file {turn1_file}...")
        t_wait_t1 = time.time()
        while time.time() - t_wait_t1 < 45:
            if os.path.exists(turn1_path):
                break
            time.sleep(1)
        assert os.path.exists(turn1_path), f"Turn 1 file {turn1_file} was not created!"

        with open(turn1_path) as f:
            actual_t1_content = f.read().strip()
        assert turn1_content in actual_t1_content, f"Content mismatch! Expected {turn1_content}, got {actual_t1_content}"
        turn1_file_sha = sha256_file(turn1_path)
        print(f"Turn 1 File Created: {turn1_file} (SHA256: {turn1_file_sha})")

        ok_turn1_post, _, ev1_t1_post, ev2_t1_post = verify_receiver_idle_twice(receiver_uuid, "turn1_post", delta=2.0, max_wait=75)
        assert ok_turn1_post, "Receiver failed to return to resting idle after Turn 1!"

        mail_t1_rc, mail_t1_out = exec_in_sender(
            sender_uuid,
            [PILOT_BIN, "message", "log", "--workspace", WORKSPACE, "--json"]
        )
        ack_t1_found = f"ACK_TURN1_{turn1_nonce}" in mail_t1_out
        print(f"Turn 1 ACK received in mailbox: {ack_t1_found}")
        assert ack_t1_found, f"Turn 1 ACK not found in mailbox log!"

        results["steps"]["turn1"] = {
            "passed": True,
            "message_id": msg_t1_id,
            "target_file": turn1_file,
            "file_sha256": turn1_file_sha,
            "ack_verified": True
        }

        # Step 6: Test Positive Turn 2 - External-Driver Continuation Cycle 2
        print("\n--- Step 6: Test Positive Turn 2 - External-Driver Continuation Cycle 2 ---")
        turn2_nonce = str(int(time.time()))
        turn2_file = f"turn2_{turn2_nonce}.txt"
        turn2_path = os.path.join(WORKSPACE, turn2_file)
        turn2_content = f"CONTINUATION_TURN2_VERIFIED_{turn2_nonce}"

        ok_turn2_pre, _, ev1_t2, ev2_t2 = verify_receiver_idle_twice(receiver_uuid, "turn2_pre", delta=2.0, max_wait=30)
        assert ok_turn2_pre, "Receiver was not at resting idle before Turn 2!"

        turn2_prompt = (
            f"Please write exactly '{turn2_content}' to file {turn2_file} in your workspace. "
            f"After writing the file, reply to this message with 'ACK_TURN2_{turn2_nonce}'."
        )
        send_t2_rc, send_t2_out = exec_in_sender(
            sender_uuid,
            [PILOT_BIN, "message", "send", "--to", "continuation-receiver", turn2_prompt, "--workspace", WORKSPACE, "--json"]
        )
        assert send_t2_rc == 0, f"Failed to send Turn 2 message: {send_t2_out}"
        msg_t2_id = parse_json_safely(send_t2_out)["id"]
        print(f"Turn 2 Message ID: {msg_t2_id}")

        t_deliver_t2 = int(time.time() * 1000)
        deliv_t2_rc, deliv_t2_out = exec_in_sender(
            sender_uuid,
            [PILOT_BIN, "message", "deliver", msg_t2_id, "--workspace", WORKSPACE]
        )
        print(f"Turn 2 Deliver exit code: {deliv_t2_rc}")
        assert deliv_t2_rc == 0, f"Turn 2 deliver failed! Output: {deliv_t2_out}"

        print(f"Waiting for Turn 2 file {turn2_file}...")
        t_wait_t2 = time.time()
        while time.time() - t_wait_t2 < 45:
            if os.path.exists(turn2_path):
                break
            time.sleep(1)
        assert os.path.exists(turn2_path), f"Turn 2 file {turn2_file} was not created!"

        with open(turn2_path) as f:
            actual_t2_content = f.read().strip()
        assert turn2_content in actual_t2_content, f"Content mismatch! Expected {turn2_content}, got {actual_t2_content}"
        turn2_file_sha = sha256_file(turn2_path)
        print(f"Turn 2 File Created: {turn2_file} (SHA256: {turn2_file_sha})")

        ok_turn2_post, _, ev1_t2_post, ev2_t2_post = verify_receiver_idle_twice(receiver_uuid, "turn2_post", delta=2.0, max_wait=75)
        assert ok_turn2_post, "Receiver failed to return to resting idle after Turn 2!"

        mail_t2_rc, mail_t2_out = exec_in_sender(
            sender_uuid,
            [PILOT_BIN, "message", "log", "--workspace", WORKSPACE, "--json"]
        )
        ack_t2_found = f"ACK_TURN2_{turn2_nonce}" in mail_t2_out
        print(f"Turn 2 ACK received in mailbox: {ack_t2_found}")
        assert ack_t2_found, f"Turn 2 ACK not found in mailbox log!"

        results["steps"]["turn2"] = {
            "passed": True,
            "message_id": msg_t2_id,
            "target_file": turn2_file,
            "file_sha256": turn2_file_sha,
            "ack_verified": True
        }

        # Step 7: Final Rollback & Installed Binary Integrity Verification
        print("\n--- Step 7: Final Rollback & Installed Binary Integrity Verification ---")
        final_rollback_sha = sha256_file(ROLLBACK_BIN)
        print(f"Installed CLI SHA256 post-trial: {final_rollback_sha}")
        assert final_rollback_sha == EXPECTED_ROLLBACK_SHA, "Installed CLI /home/alexey/.local/bin/aplexer was modified!"
        results["rollback_verified_untouched"] = True
        results["overall_status"] = "PASS"

        print("\n=================================================================")
        print("ALL CONTINUATION PREFLIGHT STEPS PASSED SUCCESSFULLY!")
        print("=================================================================")

    except Exception as e:
        results["error"] = str(e)
        results["traceback"] = traceback.format_exc()
        results["overall_status"] = "FAIL"
        raise

    finally:
        print("\n--- Cleaning up trial sessions ---")
        cleanup_trial_sessions()

        final_rollback_sha = sha256_file(ROLLBACK_BIN)
        results["post_trial_rollback_sha256"] = final_rollback_sha
        rollback_intact = (final_rollback_sha == EXPECTED_ROLLBACK_SHA and rollback_sha == EXPECTED_ROLLBACK_SHA)
        results["rollback_verified_untouched"] = rollback_intact

        with open(REPORT_JSON, "w") as f:
            json.dump(results, f, indent=2)
        print(f"Results saved to {REPORT_JSON}")

        def get_gate_status(step_key):
            step_data = results["steps"].get(step_key)
            if step_data is None:
                return "**NOT-RUN**"
            return "**PASS**" if step_data.get("passed") else "**FAIL**"

        s_boot = get_gate_status("boot_turn_baseline")
        s_neg1 = get_gate_status("negative_active_tool")
        s_neg2 = get_gate_status("negative_draft_composer")
        s_t1 = get_gate_status("turn1")
        s_t2 = get_gate_status("turn2")
        s_roll = "**PASS**" if rollback_intact else "**FAIL**"
        overall = results.get("overall_status", "FAIL")

        with open(REPORT_MD, "w") as f:
            f.write("# Continuation Trial Preflight Report: External-Driver Repeated Receiver Cycles & Reversible Safety Verification\n\n")
            f.write(f"- **Execution Timestamp:** {time.strftime('%Y-%m-%d %H:%M:%SZ', time.gmtime())}\n")
            f.write(f"- **Candidate Binary:** `{PILOT_BIN}` (SHA256: `{bin_sha}`)\n")
            f.write(f"- **Rollback CLI:** `{ROLLBACK_BIN}` (SHA256: `{final_rollback_sha}`, verified untouched: {rollback_intact})\n")
            f.write(f"- **Receiver Session:** `{receiver_uuid}` (engine `opencode`, model `muse-spark-1.3-contributor`)\n")
            f.write(f"- **Sender Session:** `{sender_uuid}` (engine `shell`)\n")
            f.write(f"- **Workspace:** `{WORKSPACE}` (isolated git repo)\n")
            f.write(f"- **Subsequent Real-Head Target:** `{REAL_HEAD_TARGET}`\n")
            f.write(f"- **Overall Status:** **{overall}**\n\n")
            if "error" in results:
                f.write(f"> [!WARNING] **Trial Error Encountered:** `{results['error']}`\n\n")
            f.write("## Verified Gates & Results\n\n")
            f.write("| Test Step | Target Condition | Observed Outcome | Gate Status |\n")
            f.write("|---|---|---|---|\n")
            boot_step = results["steps"].get("boot_turn_baseline", {})
            boot_out = "Initial task executed via launch prompt; authentic reported idle confirmed with twice empty-composer"
            f.write(f"| Baseline Turn (Launch Initial Task) | Initial task execution -> debounced idle | {boot_out} | {s_boot} |\n")
            neg1 = results["steps"].get("negative_active_tool", {})
            neg1_out = f"Exit {neg1.get('deliver_probe_exit_code')} (not-ready), envelope preserved, no probe echo (appended {neg1.get('appended_history_bytes')} bytes)" if neg1 else "Not reached"
            f.write(f"| Negative 1 (Active Tool) | Deliver during child sleep ({neg1.get('child_pid', 'N/A')}) | {neg1_out} | {s_neg1} |\n")
            neg2 = results["steps"].get("negative_draft_composer", {})
            neg2_out = f"Exit {neg2.get('deliver_draft_exit_code')} (not-ready), envelope preserved, draft detected" if neg2 else "Not reached"
            f.write(f"| Negative 2 (Draft Composer) | Deliver during unsubmitted draft | {neg2_out} | {s_neg2} |\n")
            t1 = results["steps"].get("turn1", {})
            t1_out = f"Created `{t1.get('target_file')}`, ACK verified" if t1 else "Not reached"
            f.write(f"| Turn 1 (Continuation Cycle) | Delivery -> file write -> ACK | {t1_out} | {s_t1} |\n")
            t2 = results["steps"].get("turn2", {})
            t2_out = f"Created `{t2.get('target_file')}`, ACK verified" if t2 else "Not reached"
            f.write(f"| Turn 2 (Continuation Cycle) | Delivery -> file write -> ACK | {t2_out} | {s_t2} |\n")
            f.write(f"| Rollback CLI Integrity | Installed binary untouched | SHA256 verified identical post-trial | {s_roll} |\n\n")
            f.write("## Evidence Artifacts\n\n")
            f.write(f"- Detailed JSON: `{REPORT_JSON}`\n")
            f.write(f"- Evidence directory: `{EVIDENCE_DIR}`\n")
            for root_d, _, files in os.walk(EVIDENCE_DIR):
                for fn in sorted(files):
                    f.write(f"  - `{fn}`\n")
            f.write("\n")
        print(f"Markdown report generated at {REPORT_MD}")


if __name__ == "__main__":
    main()
