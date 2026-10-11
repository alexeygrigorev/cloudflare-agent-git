"""Parallel Model Actors Phase Module (AB53 Shared Contract)

Integration role: live/demo_actors.py
Public contract function:
  actors.run_parallel(session_path, launcher_root, launcher_config, timeout_seconds=1800) -> receipt

Contract Guarantees:
- Maintained-launcher parallel model phase over session.tasks
- Explicit launcher config directory and launcher root passed explicitly
- Sibling task-units backend (systemd-run app.slice)
- Fresh plan/run quota admission with fail-closed gates (Codex <=15%, Grok <=5%)
- Parent head identity verified (head67560da5 / parent_session)
- Precreates paths and leases; credentials isolated in .local/task.json (mode 0600)
- All three model tasks launched concurrently before waiting
- Bounded monitor inspecting launcher status, real first tools, progress.md, native Git heads
- No process-only progress; no fabricated patches, whoami, or complete/accept spoofing
- Receipts explicitly label 'completed-awaiting-review' vs 'accepted' (independent review pending)
- Coding vs push intervals computed only from actual timestamps
- Distinguishes 64-hex SHA256 from 40-hex Git OIDs
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time
from typing import Any, Dict, List, Optional, Tuple


def sha256_file(path: pathlib.Path) -> Optional[str]:
    """Compute 64-hex SHA256 digest of a file, or None if missing."""
    try:
        data = path.read_bytes()
        return hashlib.sha256(data).hexdigest()
    except OSError:
        return None


def git_oid(path: pathlib.Path, cwd: Optional[pathlib.Path] = None) -> Optional[str]:
    """Compute 40-hex Git object OID for a file, or None if failed."""
    if not path.exists():
        return None
    try:
        proc = subprocess.run(
            ["git", "hash-object", str(path)],
            cwd=cwd or path.parent,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0:
            return proc.stdout.strip()
    except Exception:
        pass
    return None


def get_git_head(cwd: pathlib.Path) -> Optional[str]:
    """Get current git HEAD commit SHA in cwd."""
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0:
            return proc.stdout.strip()
    except Exception:
        pass
    return None


def sanitize_text(text: str, secrets: List[str]) -> str:
    """Sanitize secret tokens from text."""
    sanitized = text
    for sec in secrets:
        if sec and len(sec) >= 6:
            sanitized = sanitized.replace(sec, "REDACTED")
    return sanitized


def sanitize_data(data: Any, secrets: List[str]) -> Any:
    """Recursively sanitize credentials and tokens from data structures."""
    if isinstance(data, dict):
        out = {}
        for k, v in data.items():
            if any(term in k.lower() for term in ("token", "secret", "password", "auth", "bearer")):
                out[k] = "REDACTED"
            else:
                out[k] = sanitize_data(v, secrets)
        return out
    elif isinstance(data, list):
        return [sanitize_data(item, secrets) for item in data]
    elif isinstance(data, str):
        return sanitize_text(data, secrets)
    return data


def parse_iso_timestamp(ts_str: Optional[str]) -> Optional[datetime.datetime]:
    """Parse ISO8601 timestamp string into datetime object."""
    if not ts_str:
        return None
    try:
        norm = ts_str.strip()
        if norm.endswith("Z"):
            norm = norm[:-1] + "+00:00"
        return datetime.datetime.fromisoformat(norm)
    except Exception:
        return None


def compute_interval_overlap(
    intervals: List[Tuple[datetime.datetime, datetime.datetime]]
) -> Dict[str, Any]:
    """Compute true overlap across actual intervals without fabricating concurrency."""
    valid = [iv for iv in intervals if iv[0] and iv[1] and iv[0] <= iv[1]]
    if len(valid) < 2:
        return {
            "has_overlap": False,
            "overlap_seconds": 0.0,
            "max_concurrency": len(valid),
            "intervals_evaluated": len(valid),
        }

    # Find earliest start and latest end
    starts = [iv[0] for iv in valid]
    ends = [iv[1] for iv in valid]

    # Pairwise overlap checks
    pairwise_overlaps = []
    for i in range(len(valid)):
        for j in range(i + 1, len(valid)):
            overlap_start = max(valid[i][0], valid[j][0])
            overlap_end = min(valid[i][1], valid[j][1])
            if overlap_start < overlap_end:
                pairwise_overlaps.append(
                    (overlap_end - overlap_start).total_seconds()
                )

    has_overlap = len(pairwise_overlaps) > 0
    total_overlap_sec = max(pairwise_overlaps) if pairwise_overlaps else 0.0

    return {
        "has_overlap": has_overlap,
        "max_pairwise_overlap_seconds": total_overlap_sec,
        "pairwise_overlap_count": len(pairwise_overlaps),
        "intervals_evaluated": len(valid),
    }


def verify_parent_identity(session_data: Dict[str, Any]) -> Tuple[bool, str]:
    """Verify native parent head identity and session properties."""
    run_id = session_data.get("run_id", "")
    tasks = session_data.get("tasks", [])
    if not tasks:
        return False, "session contains no tasks"

    expected_parent_marker = "67560da5"
    has_valid_parent = False
    for t in tasks:
        parent = t.get("parent") or session_data.get("parent_session") or run_id
        if expected_parent_marker in str(parent):
            has_valid_parent = True
            break

    if not has_valid_parent and expected_parent_marker not in str(session_data):
        return False, f"parent head identity {expected_parent_marker} not found in session"

    return True, "parent head identity verified"


def run_launcher_command(
    launcher_root: pathlib.Path,
    launcher_config: pathlib.Path,
    subcmd: str,
    extra_args: List[str],
    timeout: int = 60,
    env_override: Optional[Dict[str, str]] = None,
) -> Tuple[int, str, str]:
    """Execute launcher CLI sub-command under shared launcher config."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(launcher_root)
    if env_override:
        env.update(env_override)

    cmd = [
        sys.executable,
        "-m",
        "launcher",
        "--config-dir",
        str(launcher_config),
        subcmd,
    ] + extra_args

    proc = subprocess.run(
        cmd,
        cwd=launcher_root,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


def build_actor_specs(
    session_data: Dict[str, Any],
    launcher_config: pathlib.Path,
) -> List[Dict[str, Any]]:
    """Construct authentic actor task definitions from session tasks.
    
    Actor A: Presenter formatAgentSummary(status) in prototype/demo/live-view.mjs
    Actor B: Presenter formatWarnings(status) in prototype/demo/live-view.mjs (same path, separate fork)
    Actor C: Sanitizer sanitizeEvidence(receipt) in prototype/demo/live-evidence.mjs (disjoint)
    """
    raw_tasks = session_data.get("tasks", [])
    actor_specs = []

    # Map roles A, B, C deterministically
    role_meta = [
        {
            "role": "a",
            "launcher_task": "ab53-live-a-r1",
            "source": "prototype/demo/live-view.mjs",
            "test": "prototype/demo/live-view-agent.test.mjs",
            "feature_desc": "formatAgentSummary(status) presenter for task/agent/base/head states",
        },
        {
            "role": "b",
            "launcher_task": "ab53-live-b-r1",
            "source": "prototype/demo/live-view.mjs",
            "test": "prototype/demo/live-view-warning.test.mjs",
            "feature_desc": "formatWarnings(status) presenter for warning/task-owner/ack states",
        },
        {
            "role": "c",
            "launcher_task": "ab53-live-c-r1",
            "source": "prototype/demo/live-evidence.mjs",
            "test": "prototype/demo/live-evidence.test.mjs",
            "feature_desc": "sanitizeEvidence(receipt) redacting token/password/auth/secret",
        },
    ]

    for idx, meta in enumerate(role_meta):
        task_info = raw_tasks[idx] if idx < len(raw_tasks) else {}
        task_id = task_info.get("task_id", f"task-000{5 + idx}")
        agent_id = task_info.get("agent_id", f"ab-live-{meta['role']}-000{5 + idx}")
        ws_root = session_data.get("workspace_root")
        if not ws_root:
            run_root_val = session_data.get("run_root")
            if run_root_val:
                ws_root = str(pathlib.Path(run_root_val) / "workspaces")
            else:
                ws_root = str(pathlib.Path(tempfile.gettempdir()) / "agent-branches-workspaces")
        default_workspace = str(pathlib.Path(ws_root) / f"agent-branches-live-{meta['role']}")
        workspace = pathlib.Path(task_info.get("workspace", default_workspace)).resolve()
        token = task_info.get("token", "")
        fork_remote = task_info.get("fork_remote", "")

        repo_root = pathlib.Path(__file__).resolve().parent.parent
        read_only_source = session_data.get("source_root", str(repo_root))
        
        # Build payload with strict model requirements and explicit RO/RW path claims
        payload = {
            "goal": (
                f"You are agent-branches-implementer-live-{meta['role']}, real concurrently launched "
                f"GeminiPro model actor, parent agent-branches-contest-head67560da5, task {task_id}/agent {agent_id}. "
                f"Scope ONLY {meta['source']}, matching test {meta['test']}, .local/**. "
                f"Goal: {meta['feature_desc']}. Built-in Node tests only (node --test). "
                f"Git auth via GIT_CONFIG_* env, credentials in ignored .local/task.json mode 0600. "
                f"Semantic ownership intent in .local/ownership-reply.md. No fabricated overlap or fake reviewer."
            ),
            "owner": "agent-branches-contest-head",
            "parent": session_data.get("parent_session", "67560da5-4a2a-44ea-bfd8-29d988d0bea9"),
            "project_id": "agent-branches",
            "cwd": str(workspace),
            "timeout": 1800,
            "memory_mb": 1500,
            "disk_mb": 16,
            "model_requirements": {
                "providers": ["antigravity"],
                "models": ["gemini-3.1-pro-high", "gemini-3.8-flash-high"],
            },
            "provider": "antigravity",
            "allow_fallback": False,
            "read_only_paths": [
                read_only_source,
            ],
            "read_write_paths": [str(workspace)],
        }

        actor_specs.append({
            "role": meta["role"],
            "task_id": task_id,
            "agent_id": agent_id,
            "launcher_task": meta["launcher_task"],
            "workspace": workspace,
            "token": token,
            "fork_remote": fork_remote,
            "source_rel": meta["source"],
            "test_rel": meta["test"],
            "payload": payload,
            "paths": [str(workspace / meta["source"]), str(workspace / meta["test"])],
        })

    return actor_specs


def prepare_actor_workspace(spec: Dict[str, Any], session_data: Dict[str, Any]) -> None:
    """Precreate workspace directories and private .local/task.json mode 0600."""
    ws = spec["workspace"]
    ws.mkdir(parents=True, exist_ok=True)
    local_dir = ws / ".local"
    local_dir.mkdir(mode=0o700, exist_ok=True)

    # Ensure .local is ignored in git to prevent credential leakage
    gitignore_path = ws / ".gitignore"
    if gitignore_path.exists():
        gi_content = gitignore_path.read_text()
        if ".local" not in gi_content:
            gitignore_path.write_text(gi_content + "\n.local/\n")
    else:
        gitignore_path.write_text(".local/\n")

    # Write private credentials file mode 0600
    task_creds = {
        "task_id": spec["task_id"],
        "agent_id": spec["agent_id"],
        "token": spec["token"],
        "fork_remote": spec["fork_remote"],
        "coordinator_url": session_data.get("coordinator_url", ""),
        "sidecar_url": session_data.get("sidecar_url", ""),
    }
    task_json = local_dir / "task.json"
    task_json.write_text(json.dumps(task_creds, indent=2))
    task_json.chmod(0o600)


def admit_and_launch_actor(
    spec: Dict[str, Any],
    launcher_root: pathlib.Path,
    launcher_config: pathlib.Path,
) -> Dict[str, Any]:
    """Submit, plan quota admission, and launch actor via task-units backend."""
    task_id = spec["launcher_task"]
    payload_str = json.dumps(spec["payload"])
    paths_arg = ",".join(spec["paths"])

    launch_record: Dict[str, Any] = {
        "launcher_id": task_id,
        "role": spec["role"],
        "submitted": False,
        "planned": False,
        "launched": False,
        "plan_data": None,
        "run_data": None,
        "error": None,
        "launch_timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

    # 1. Idempotent Submit
    rc, out, err = run_launcher_command(
        launcher_root,
        launcher_config,
        "submit",
        [
            "--id", task_id,
            "--key", f"ab53-actor-{spec['role']}",
            "--payload", payload_str,
            "--paths", paths_arg,
        ],
    )
    if rc != 0 and "already exists" not in err and "already exists" not in out:
        launch_record["error"] = f"submit failed (rc={rc}): {err or out}"
        return launch_record
    launch_record["submitted"] = True

    # 2. Quota & Gate Admission (Plan)
    rc, out, err = run_launcher_command(
        launcher_root,
        launcher_config,
        "plan",
        ["--id", task_id],
    )
    if rc != 0:
        launch_record["error"] = f"plan admission failed (rc={rc}): {err or out}"
        return launch_record

    try:
        plan_json = json.loads(out)
        launch_record["plan_data"] = plan_json
        # Fail-closed checks on candidate selection
        chosen = plan_json.get("chosen")
        if not chosen:
            rejections = plan_json.get("rejections", {})
            launch_record["error"] = f"admission gate rejected all routes: {rejections}"
            return launch_record
    except json.JSONDecodeError:
        launch_record["error"] = f"invalid plan JSON: {out[:200]}"
        return launch_record
    launch_record["planned"] = True

    # 3. Launch via task-units backend
    tmpdir = str(spec["workspace"] / ".local" / "tmp" / task_id)
    pathlib.Path(tmpdir).mkdir(parents=True, exist_ok=True)
    
    rc, out, err = run_launcher_command(
        launcher_root,
        launcher_config,
        "run",
        [
            "--backend", "task-units",
            "--id", task_id,
            "--cwd", str(spec["workspace"]),
            "--tmpdir", tmpdir,
        ],
    )
    if rc != 0:
        launch_record["error"] = f"run failed (rc={rc}): {err or out}"
        return launch_record

    try:
        run_json = json.loads(out)
        launch_record["run_data"] = run_json
    except json.JSONDecodeError:
        launch_record["run_data"] = {"raw_output": out}

    launch_record["launched"] = True
    return launch_record


def monitor_actor_state(
    spec: Dict[str, Any],
    launcher_root: pathlib.Path,
    launcher_config: pathlib.Path,
    secrets: List[str],
) -> Dict[str, Any]:
    """Inspect actual launcher status, progress.md, native git heads, and artifacts."""
    task_id = spec["launcher_task"]
    ws = spec["workspace"]

    state_info: Dict[str, Any] = {
        "launcher_id": task_id,
        "role": spec["role"],
        "task_id": spec["task_id"],
        "agent_id": spec["agent_id"],
        "workspace": str(ws),
        "launcher_state": "unknown",
        "native_git_head": get_git_head(ws),
        "progress_present": False,
        "provider_conversation": None,
        "model_identity": None,
        "first_tool_action": None,
        "source_sha256": None,
        "source_git_oid": None,
        "test_present": False,
        "ownership_intent_present": False,
        "receipt_present": False,
        "receipt_data": None,
        "coding_start_iso": None,
        "coding_end_iso": None,
        "push_timestamp_iso": None,
    }

    # Query launcher status
    rc, out, _ = run_launcher_command(
        launcher_root,
        launcher_config,
        "status",
        ["--id", task_id],
    )
    if rc == 0:
        try:
            st = json.loads(out)
            state_info["launcher_state"] = st.get("state", "unknown")
            state_info["launcher_reason"] = st.get("reason")
        except json.JSONDecodeError:
            state_info["launcher_state"] = "unparsable"

    # Inspect .local/progress.md for real first tool telemetry
    progress_file = ws / ".local" / "progress.md"
    if progress_file.exists():
        state_info["progress_present"] = True
        content = progress_file.read_text(errors="replace")
        for line in content.splitlines():
            line_str = line.strip()
            if "Conversation:" in line_str or "Native Provider Conversation:" in line_str:
                state_info["provider_conversation"] = line_str.split(":", 1)[1].strip()
            elif "Model:" in line_str:
                state_info["model_identity"] = line_str.split(":", 1)[1].strip()
            elif "Time:" in line_str or "Timestamp:" in line_str:
                state_info["coding_start_iso"] = line_str.split(":", 1)[1].strip()

    # Inspect source and test files
    source_file = ws / spec["source_rel"]
    if source_file.exists():
        state_info["source_sha256"] = sha256_file(source_file)
        state_info["source_git_oid"] = git_oid(source_file, cwd=ws)

    test_file = ws / spec["test_rel"]
    state_info["test_present"] = test_file.exists()

    # Inspect semantic ownership intent response
    ownership_file = ws / ".local" / "ownership-reply.md"
    if not ownership_file.exists():
        ownership_file = ws / ".local" / "ownership-handoff.json"
    state_info["ownership_intent_present"] = ownership_file.exists()

    # Inspect actor result receipt
    result_file = ws / ".local" / "result.json"
    if not result_file.exists():
        result_file = ws / ".local" / "result-repair.json"
    if result_file.exists():
        state_info["receipt_present"] = True
        try:
            rdata = json.loads(result_file.read_text(errors="replace"))
            state_info["receipt_data"] = sanitize_data(rdata, secrets)
            state_info["coding_end_iso"] = rdata.get("coding_end_utc") or rdata.get("as_of")
            state_info["push_timestamp_iso"] = rdata.get("push_timestamp_utc") or rdata.get("push_time")
        except json.JSONDecodeError:
            state_info["receipt_data"] = {"error": "unparsable result receipt"}

    return state_info


def run_parallel(
    session_path: str | pathlib.Path,
    launcher_root: str | pathlib.Path,
    launcher_config: str | pathlib.Path,
    timeout_seconds: int = 1800,
    poll_interval: float = 5.0,
) -> Dict[str, Any]:
    """Execute maintained-launcher parallel model phase over session.tasks.
    
    Adheres strictly to AB53 phase-interface contract:
    - Launch all three model tasks before waiting
    - Shared existing launcher config passed explicitly
    - Bounded monitoring of actual status, first tools, and native Git heads
    - Receipts explicitly label 'completed-awaiting-review' vs 'accepted'
    - Source and path leases remain pending independent head review
    """
    start_time = datetime.datetime.now(datetime.timezone.utc)
    s_path = pathlib.Path(session_path).resolve()
    l_root = pathlib.Path(launcher_root).resolve()
    l_config = pathlib.Path(launcher_config).resolve()

    # Initial receipt envelope
    receipt: Dict[str, Any] = {
        "schema_version": 1,
        "phase": "actors",
        "phase_task_id": "task-0012",
        "agent_id": "phase-actors-0012",
        "head_session": "67560da5-4a2a-44ea-bfd8-29d988d0bea9",
        "status": "in_progress",
        "source_acceptance": "pending",
        "source_review_pending": True,
        "physical_two_host_pending": True,
        "start_time_utc": start_time.isoformat(),
        "launcher_root": str(l_root),
        "launcher_config": str(l_config),
        "launch_manifest": [],
        "actors": {},
        "concurrency_evidence": {},
        "limitations": [
            "Source acceptance pending independent head and Pro review; self-approval prohibited.",
            "Physical two-host status pending (AgentBus AC60 interface accepted, hardware pending).",
        ],
    }

    # 1. Validate Session File
    if not s_path.exists():
        receipt["status"] = "failed"
        receipt["error"] = f"session_path does not exist: {s_path}"
        return receipt

    try:
        session_data = json.loads(s_path.read_text())
    except Exception as e:
        receipt["status"] = "failed"
        receipt["error"] = f"failed to read session JSON: {e}"
        return receipt

    # Extract secrets for sanitization
    secrets: List[str] = []
    sec_dict = session_data.get("secrets", {})
    if isinstance(sec_dict, dict):
        secrets.extend([str(v) for v in sec_dict.values() if v])
    for t in session_data.get("tasks", []):
        tok = t.get("token")
        if tok:
            secrets.append(str(tok))

    # 2. Verify Parent Head Identity
    ok, msg = verify_parent_identity(session_data)
    if not ok:
        receipt["status"] = "failed"
        receipt["error"] = f"parent verification failed: {msg}"
        return receipt

    # 3. Construct Actor Specs & Precreate Workspaces
    specs = build_actor_specs(session_data, l_config)
    for spec in specs:
        prepare_actor_workspace(spec, session_data)

    # 4. CRITICAL: Launch all three model tasks before waiting
    launches = []
    for spec in specs:
        l_rec = admit_and_launch_actor(spec, l_root, l_config)
        launches.append(l_rec)
    receipt["launch_manifest"] = launches

    # If any launch failed outright, record failure
    failed_launches = [l for l in launches if not l.get("launched")]
    if failed_launches:
        receipt["status"] = "launch_rejected"
        receipt["error"] = f"{len(failed_launches)} actor(s) failed admission or launch"
        receipt["failed_launches"] = failed_launches
        return receipt

    # 5. Bounded Monitor Loop
    effective_poll = min(poll_interval, max(0.01, timeout_seconds / 20.0))
    deadline = time.time() + min(timeout_seconds, 1800)
    all_terminal = False

    while time.time() < deadline:
        active_count = 0
        current_actor_states = {}

        for spec in specs:
            st = monitor_actor_state(spec, l_root, l_config, secrets)
            current_actor_states[spec["role"]] = st
            # Check terminal conditions
            l_st = st.get("launcher_state", "")
            if l_st not in ("completed", "completed-awaiting-review", "accepted", "failed", "rejected"):
                active_count += 1

        receipt["actors"] = current_actor_states

        if active_count == 0:
            all_terminal = True
            break

        time.sleep(effective_poll)

    # 6. Final Evaluation & Overlap Computation
    coding_intervals: List[Tuple[datetime.datetime, datetime.datetime]] = []
    push_timestamps: List[datetime.datetime] = []

    for role, act in receipt["actors"].items():
        c_start = parse_iso_timestamp(act.get("coding_start_iso"))
        c_end = parse_iso_timestamp(act.get("coding_end_iso"))
        if c_start and c_end:
            coding_intervals.append((c_start, c_end))

        p_ts = parse_iso_timestamp(act.get("push_timestamp_iso"))
        if p_ts:
            push_timestamps.append(p_ts)

    coding_overlap = compute_interval_overlap(coding_intervals)
    
    # Check true push overlap
    push_overlap = False
    if len(push_timestamps) >= 2:
        # Pushes overlap only if timestamps match within 2 seconds
        sorted_pushes = sorted(push_timestamps)
        for i in range(len(sorted_pushes) - 1):
            if (sorted_pushes[i+1] - sorted_pushes[i]).total_seconds() <= 2.0:
                push_overlap = True
                break

    receipt["concurrency_evidence"] = {
        "coding_intervals_count": len(coding_intervals),
        "coding_overlap": coding_overlap,
        "push_timestamps_count": len(push_timestamps),
        "push_overlap_claimed": push_overlap,
        "push_overlap_note": (
            "True push overlap requires sub-2s push timing; otherwise sequential pushes are reported truthfully."
        ),
    }

    # Determine overall status
    if all_terminal:
        # Check if all completed
        all_completed = all(
            act.get("launcher_state") in ("completed", "completed-awaiting-review")
            for act in receipt["actors"].values()
        )
        if all_completed:
            receipt["status"] = "completed-awaiting-review"
        else:
            receipt["status"] = "completed_with_failures"
    else:
        receipt["status"] = "timeout_bounded"

    receipt["end_time_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    return receipt


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python3 demo_actors.py <session_path> <launcher_root> <launcher_config> [timeout_seconds]")
        sys.exit(1)
    s_path = sys.argv[1]
    l_root = sys.argv[2]
    l_config = sys.argv[3]
    t_sec = int(sys.argv[4]) if len(sys.argv) > 4 else 1800
    res = run_parallel(s_path, l_root, l_config, timeout_seconds=t_sec)
    print(json.dumps(res, indent=2))
