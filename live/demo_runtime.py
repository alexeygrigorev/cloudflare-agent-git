#!/usr/bin/env python3
"""
live/demo_runtime.py - Independent Phase Runtime Implementer (task-0011).

Implements the AB53 split runner runtime module according to:
phase-interface.md (AB53 private working contract)

Public contract interface:
  runtime.start_runtime(options) -> session_path
  runtime.stop_runtime(session_path) -> receipt
  runtime.check_preflight(options) -> dict

Session Schema (mode 0600):
  schema_version=1, run_id, source_root, run_root, workspace_root,
  coordinator_url, sidecar_url,
  secrets={admin_token, runner_token, sidecar_token},
  canonical={name, remote, base_sha},
  tasks=[{task_id, agent_id, fork_remote, token, workspace}],
  processes=[{pid, start_ticks, cwd, argv}],
  source_pins, physical_two_host_pending=true.
"""

import argparse
import io
import json
import os
import pathlib
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

_RUNNING_POPENS: Dict[int, subprocess.Popen] = {}


def _secure_umask():
    os.umask(0o077)


def get_start_ticks(pid: int) -> Optional[int]:
    """Read Linux /proc/{pid}/stat start_ticks (field 22, 0-indexed 21)."""
    try:
        stat_path = pathlib.Path(f"/proc/{pid}/stat")
        if not stat_path.exists():
            return None
        content = stat_path.read_text()
        # comm can contain spaces and parentheses: e.g. (node main.js)
        close_paren = content.rfind(")")
        if close_paren == -1:
            fields = content.split()
            return int(fields[21]) if len(fields) > 21 else None
        remainder = content[close_paren + 1 :].split()
        # field 22 is index 19 of remainder
        return int(remainder[19]) if len(remainder) > 19 else None
    except Exception:
        return None


def get_process_cmdline(pid: int) -> Optional[List[str]]:
    """Read Linux /proc/{pid}/cmdline as a list of strings."""
    try:
        cmd_path = pathlib.Path(f"/proc/{pid}/cmdline")
        if not cmd_path.exists():
            return None
        raw = cmd_path.read_bytes()
        parts = raw.split(b"\x00")
        return [p.decode("utf-8", errors="replace") for p in parts if p]
    except Exception:
        return None


def get_process_cwd(pid: int) -> Optional[str]:
    """Read Linux /proc/{pid}/cwd target path."""
    try:
        cwd_link = pathlib.Path(f"/proc/{pid}/cwd")
        if not cwd_link.exists():
            return None
        return os.path.realpath(str(cwd_link))
    except Exception:
        return None


def is_port_occupied(port: int, host: str = "127.0.0.1") -> bool:
    """Check if a TCP port is currently listening / occupied."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        res = s.connect_ex((host, port))
        return res == 0


def find_free_port(host: str = "127.0.0.1") -> int:
    """Bind to port 0 to allocate an unused ephemeral port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((host, 0))
        return int(s.getsockname()[1])


def git_auth_env(url: str, token: str) -> Dict[str, str]:
    """Generate Git authentication environment variables without exposing token in argv."""
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_CONFIG_COUNT"] = "1"
    env["GIT_CONFIG_KEY_0"] = f"http.{url}.extraHeader"
    env["GIT_CONFIG_VALUE_0"] = f"Authorization: Bearer {token}"
    return env


def api_request(url: str, token: Optional[str], path: str, body: Optional[Dict[str, Any]] = None, timeout: float = 15.0) -> Any:
    """Perform a secure HTTP API request using urllib.request with finite deadline."""
    req_url = url.rstrip("/") + "/" + path.lstrip("/")
    data = None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(req_url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        content = resp.read()
        if not content:
            return None
        return json.loads(content.decode("utf-8"))


def find_node_executable() -> str:
    """Find Node on PATH or fallback to explicit environment variable."""
    node_on_path = shutil.which("node")
    if node_on_path:
        return node_on_path
    node_env = os.environ.get("NODE_BIN") or os.environ.get("NODE_EXECUTABLE")
    if node_env and os.path.exists(node_env) and os.access(node_env, os.X_OK):
        return node_env
    raise RuntimeError("Node executable not found on PATH or via NODE_BIN/NODE_EXECUTABLE.")


def find_cached_tsc(source_root: Optional[pathlib.Path] = None) -> Optional[str]:
    """Find cached tsc compiler in source_root / node_modules, sibling repos, or PATH."""
    tsc_env = os.environ.get("TSC_BIN") or os.environ.get("TSC_PATH")
    if tsc_env and os.path.exists(tsc_env) and os.access(tsc_env, os.X_OK):
        return tsc_env
    if source_root:
        local_tsc = source_root / "prototype" / "node_modules" / ".bin" / "tsc"
        if local_tsc.exists() and os.access(str(local_tsc), os.X_OK):
            return str(local_tsc)
        sibling_tsc = source_root.parent / "agent-branches" / "prototype" / "node_modules" / ".bin" / "tsc"
        if sibling_tsc.exists() and os.access(str(sibling_tsc), os.X_OK):
            return str(sibling_tsc)
    repo_root = pathlib.Path(__file__).resolve().parent.parent
    sibling_tsc = repo_root.parent / "agent-branches" / "prototype" / "node_modules" / ".bin" / "tsc"
    if sibling_tsc.exists() and os.access(str(sibling_tsc), os.X_OK):
        return str(sibling_tsc)
    path_tsc = shutil.which("tsc")
    if path_tsc:
        return path_tsc
    return None


def find_cached_main_js(source_root: pathlib.Path, explicit_path: Optional[str] = None) -> Optional[pathlib.Path]:
    """Find prebuilt coordinator main.js via explicit option, env, or built location."""
    if explicit_path:
        p = pathlib.Path(explicit_path).resolve()
        if p.exists() and p.is_file():
            return p
    env_path = os.environ.get("CACHED_MAIN_JS") or os.environ.get("CACHED_COORDINATOR_JS")
    if env_path:
        p = pathlib.Path(env_path).resolve()
        if p.exists() and p.is_file():
            return p
    built_main = source_root / "prototype" / ".build" / "node" / "src" / "local" / "main.js"
    if built_main.exists() and built_main.is_file():
        return built_main
    sibling_cached = source_root.parent / "cloudflare-agent-git" / ".local" / "agent-branches-contest-head" / "source" / "prototype" / ".build" / "node" / "src" / "local" / "main.js"
    if sibling_cached.exists() and sibling_cached.is_file():
        return sibling_cached
    return None


def verify_owned_process(proc_info: Dict[str, Any]) -> bool:
    """Verify that a PID exactly matches recorded PID, start_ticks, cwd, and argv."""
    pid = proc_info.get("pid")
    if not pid:
        return False
    expected_ticks = proc_info.get("start_ticks")
    expected_cwd = proc_info.get("cwd")
    expected_argv = proc_info.get("argv")

    actual_ticks = get_start_ticks(pid)
    if actual_ticks is None or actual_ticks != expected_ticks:
        return False

    actual_cwd = get_process_cwd(pid)
    if actual_cwd is not None and expected_cwd is not None:
        if os.path.realpath(actual_cwd) != os.path.realpath(expected_cwd):
            return False

    actual_argv = get_process_cmdline(pid)
    if actual_argv is not None and expected_argv is not None:
        if actual_argv != expected_argv:
            return False

    return True


def check_preflight(options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Validate environment, required commands, source, compiler, and ports without model launch.
    Fail closed if critical requirements are missing.
    Leaves occupied listener intact and records explicit port status.
    """
    opts = options or {}
    results = {
        "status": "ok",
        "commands": {},
        "source": {},
        "cache": {},
        "ports": {},
        "errors": []
    }

    # 1. Commands
    try:
        node_bin = find_node_executable()
        node_ver = subprocess.check_output([node_bin, "-v"], text=True).strip()
        results["commands"]["node"] = {"path": node_bin, "version": node_ver}
    except Exception as e:
        results["errors"].append(f"node missing or failed: {e}")
        results["commands"]["node"] = {"error": str(e)}

    git_bin = shutil.which("git")
    if git_bin:
        try:
            git_ver = subprocess.check_output([git_bin, "--version"], text=True).strip()
            results["commands"]["git"] = {"path": git_bin, "version": git_ver}
        except Exception as e:
            results["errors"].append(f"git version check failed: {e}")
    else:
        results["errors"].append("git command missing on PATH")

    # 2. Source root and prototype
    source_root = pathlib.Path(opts.get("source_root", os.getcwd())).resolve()
    sidecar_mjs = source_root / "prototype" / "local-artifacts" / "sidecar.mjs"
    if sidecar_mjs.exists():
        results["source"]["sidecar_mjs"] = str(sidecar_mjs)
    else:
        results["errors"].append(f"sidecar.mjs not found at {sidecar_mjs}")

    # 3. Compiler & prebuilt main
    main_js_path = find_cached_main_js(source_root, opts.get("cached_main"))
    tsc_bin = find_cached_tsc(source_root)

    if main_js_path and main_js_path.exists():
        results["cache"]["main_js"] = str(main_js_path)
    elif tsc_bin:
        results["cache"]["tsc"] = tsc_bin
    else:
        results["errors"].append("Neither compiled main.js nor cached tsc compiler available (provide --cached-main or set CACHED_MAIN_JS)")

    # 4. Port checks (leave occupied listeners intact)
    ports_to_check = opts.get("check_ports", [18890, 18891, 8788])
    for p in ports_to_check:
        occupied = is_port_occupied(p)
        results["ports"][str(p)] = "occupied" if occupied else "free"

    if results["errors"]:
        results["status"] = "failed"

    return results


def start_runtime(options: Optional[Dict[str, Any]] = None) -> str:
    """
    Launch uniquely owned loopback Node coordinator and Git sidecar runtime.
    Seeds actual prototype source via Git archive, creates three real task forks,
    and writes private session JSON (mode 0600).
    Returns session_path.
    """
    _secure_umask()
    opts = options or {}
    source_root = pathlib.Path(opts.get("source_root", os.getcwd())).resolve()

    # Preflight validation first
    preflight = check_preflight({"source_root": str(source_root)})
    if preflight["status"] != "ok":
        raise RuntimeError(f"Preflight validation failed: {preflight['errors']}")

    node_bin = find_node_executable()
    node_dir = str(pathlib.Path(node_bin).parent)

    # Resolve run_root and sibling workspaces
    run_id = f"run-{int(time.time())}-{secrets.token_hex(4)}"
    if "run_root" in opts and opts["run_root"]:
        run_root = pathlib.Path(opts["run_root"]).resolve()
    elif os.environ.get("RUN_ROOT"):
        run_root = pathlib.Path(os.environ["RUN_ROOT"]).resolve()
    else:
        default_sibling = source_root.parent / "sibling_workspaces"
        run_root = default_sibling / run_id

    run_root.mkdir(parents=True, exist_ok=False, mode=0o700)
    workspace_root = run_root / "workspaces"
    workspace_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    store_root = run_root / "store"
    store_root.mkdir(parents=True, exist_ok=True, mode=0o700)

    # Determine ports: if user specified ports, verify they are NOT occupied
    sidecar_port = opts.get("sidecar_port")
    if sidecar_port:
        if is_port_occupied(sidecar_port):
            raise RuntimeError(f"Requested sidecar_port {sidecar_port} is already occupied. Preserving listener intact.")
    else:
        sidecar_port = find_free_port()

    coordinator_port = opts.get("coordinator_port")
    if coordinator_port:
        if is_port_occupied(coordinator_port):
            raise RuntimeError(f"Requested coordinator_port {coordinator_port} is already occupied. Preserving listener intact.")
    else:
        coordinator_port = find_free_port()
        while coordinator_port == sidecar_port:
            coordinator_port = find_free_port()

    coordinator_url = f"http://127.0.0.1:{coordinator_port}"
    sidecar_url = f"http://127.0.0.1:{sidecar_port}"

    # Generate secrets
    admin_token = secrets.token_urlsafe(32)
    runner_token = secrets.token_urlsafe(32)
    sidecar_token = secrets.token_urlsafe(32)

    # Locate sidecar entry and coordinator entry
    sidecar_entry = source_root / "prototype" / "local-artifacts" / "sidecar.mjs"
    if not sidecar_entry.exists():
        raise RuntimeError(f"sidecar.mjs not found at {sidecar_entry}")

    coordinator_entry = find_cached_main_js(source_root, opts.get("cached_main"))
    if not coordinator_entry or not coordinator_entry.exists():
        tsc_bin = find_cached_tsc(source_root)
        if not tsc_bin:
            raise RuntimeError("No compiled main.js and no tsc found to compile prototype (provide --cached-main or set CACHED_MAIN_JS).")
        tsconfig = source_root / "prototype" / "tsconfig.node.json"
        subprocess.run([tsc_bin, "-p", str(tsconfig)], check=True)
        coordinator_entry = source_root / "prototype" / ".build" / "node" / "src" / "local" / "main.js"
        if not coordinator_entry.exists():
            raise RuntimeError(f"tsc build did not produce expected {coordinator_entry}")

    processes_record: List[Dict[str, Any]] = []

    # 1. Start sidecar process
    sidecar_log_path = run_root / "sidecar.log"
    sidecar_log = open(sidecar_log_path, "a")
    sidecar_env = os.environ.copy()
    sidecar_env.update({
        "SIDECAR_ROOT": str(store_root),
        "SIDECAR_PORT": str(sidecar_port),
        "SIDECAR_HOST": "127.0.0.1",
        "SIDECAR_TOKEN": sidecar_token,
        "SIDECAR_NOTIFY_URL": f"{coordinator_url}/events/push",
        "PATH": f"{node_dir}:{sidecar_env.get('PATH', '')}"
    })
    sidecar_argv = [node_bin, str(sidecar_entry)]
    sidecar_proc = subprocess.Popen(
        sidecar_argv,
        cwd=str(source_root),
        env=sidecar_env,
        stdout=sidecar_log,
        stderr=sidecar_log
    )
    sidecar_log.close()
    _RUNNING_POPENS[sidecar_proc.pid] = sidecar_proc
    time.sleep(0.3)
    sidecar_ticks = get_start_ticks(sidecar_proc.pid)
    processes_record.append({
        "name": "sidecar",
        "pid": sidecar_proc.pid,
        "start_ticks": sidecar_ticks,
        "cwd": str(source_root),
        "argv": sidecar_argv
    })

    # 2. Start coordinator process
    coord_log_path = run_root / "coordinator.log"
    coord_log = open(coord_log_path, "a")
    coord_env = os.environ.copy()
    coord_env.update({
        "LOCAL_ARTIFACTS_URL": sidecar_url,
        "LOCAL_ARTIFACTS_TOKEN": sidecar_token,
        "ADMIN_TOKEN": admin_token,
        "RUNNER_TOKEN": runner_token,
        "PORT": str(coordinator_port),
        "HOST": "127.0.0.1",
        "COORDINATOR_STATE_FILE": str(run_root / "coordinator.json"),
        "PATH": f"{node_dir}:{coord_env.get('PATH', '')}"
    })
    coord_argv = [node_bin, str(coordinator_entry)]
    coord_proc = subprocess.Popen(
        coord_argv,
        cwd=str(source_root),
        env=coord_env,
        stdout=coord_log,
        stderr=coord_log
    )
    coord_log.close()
    _RUNNING_POPENS[coord_proc.pid] = coord_proc
    time.sleep(0.3)
    coord_ticks = get_start_ticks(coord_proc.pid)
    processes_record.append({
        "name": "coordinator",
        "pid": coord_proc.pid,
        "start_ticks": coord_ticks,
        "cwd": str(source_root),
        "argv": coord_argv
    })

    # Poll for coordinator readiness up to 10 seconds
    ready = False
    for _ in range(40):
        try:
            status = api_request(coordinator_url, runner_token, "/status", timeout=1.0)
            if status is not None:
                ready = True
                break
        except Exception:
            time.sleep(0.25)

    if not ready:
        stop_runtime_processes(processes_record)
        raise RuntimeError("Coordinator failed to become ready within deadline.")

    # 3. Setup canonical repo on coordinator
    setup_resp = api_request(coordinator_url, admin_token, "/setup", {})
    canonical_info = setup_resp["canonical"]
    canon_name = canonical_info["name"]
    canon_remote = canonical_info["remote"]

    # Mint token for canonical repo from sidecar
    canon_tok_resp = api_request(
        sidecar_url,
        sidecar_token,
        f"/api/repos/{canon_name}/tokens",
        {"scope": "write", "ttlSeconds": 7200}
    )
    canon_plaintext_token = canon_tok_resp["plaintext"]

    # Seed canonical repo using git archive of prototype
    seed_dir = run_root / "seed"
    git_bin = shutil.which("git") or "git"

    # Clone canonical repo
    clone_env = git_auth_env(canon_remote, canon_plaintext_token)
    subprocess.run([git_bin, "clone", "-q", canon_remote, str(seed_dir)], env=clone_env, check=True)

    # Archive prototype from source_root and extract to seed_dir
    archive_bytes = subprocess.check_output([git_bin, "archive", "HEAD", "prototype"], cwd=str(source_root))
    with tarfile.open(fileobj=io.BytesIO(archive_bytes)) as t:
        t.extractall(seed_dir, filter="data")

    subprocess.run([git_bin, "add", "prototype"], cwd=str(seed_dir), check=True)
    subprocess.run(
        [
            git_bin,
            "-c", "user.name=Agent Branches Demo",
            "-c", "user.email=demo@example.invalid",
            "commit",
            "-m", "Seed pinned contest prototype source"
        ],
        cwd=str(seed_dir),
        check=True
    )
    subprocess.run([git_bin, "push", "-q", "origin", "main"], cwd=str(seed_dir), env=clone_env, check=True)
    base_sha = subprocess.check_output([git_bin, "rev-parse", "HEAD"], cwd=str(seed_dir), text=True).strip()

    # 4. Create three real task forks
    task_specs = [
        {"agent": "ab-live-a-0005", "intent": "Task A concurrency branch"},
        {"agent": "ab-live-b-0006", "intent": "Task B concurrency branch"},
        {"agent": "ab-live-c-0007", "intent": "Task C concurrency branch"},
    ]
    tasks_record: List[Dict[str, Any]] = []

    for spec in task_specs:
        task_data = api_request(
            coordinator_url,
            admin_token,
            "/tasks",
            {"agent": spec["agent"], "intent": spec["intent"], "base_sha": base_sha, "ttlSeconds": 7200}
        )
        task_id = task_data["taskId"]
        agent_id = task_data["agentId"]
        fork_remote = task_data["fork"]["remote"]
        fork_token = task_data["token"]["plaintext"]

        # Clone task fork into workspace_root / task_id
        task_workspace = workspace_root / task_id
        task_env = git_auth_env(fork_remote, fork_token)
        subprocess.run([git_bin, "clone", "-q", fork_remote, str(task_workspace)], env=task_env, check=True)

        tasks_record.append({
            "task_id": task_id,
            "agent_id": agent_id,
            "fork_remote": fork_remote,
            "token": fork_token,
            "workspace": str(task_workspace)
        })

    # Source commit pin
    source_commit = subprocess.check_output([git_bin, "rev-parse", "HEAD"], cwd=str(source_root), text=True).strip()

    # 5. Build session dictionary matching phase-interface.md contract
    session_data = {
        "schema_version": 1,
        "run_id": run_id,
        "source_root": str(source_root),
        "run_root": str(run_root),
        "workspace_root": str(workspace_root),
        "coordinator_url": coordinator_url,
        "sidecar_url": sidecar_url,
        "secrets": {
            "admin_token": admin_token,
            "runner_token": runner_token,
            "sidecar_token": sidecar_token
        },
        "canonical": {
            "name": canon_name,
            "remote": canon_remote,
            "base_sha": base_sha
        },
        "tasks": tasks_record,
        "processes": processes_record,
        "source_pins": {
            "source_commit": source_commit,
            "canonical_base": base_sha
        },
        "physical_two_host_pending": True,
        "parent_session": opts.get("parent_session", "67560da5-4a2a-44ea-bfd8-29d988d0bea9")
    }

    session_path = run_root / "session.json"
    session_path.write_text(json.dumps(session_data, indent=2))
    session_path.chmod(0o600)

    return str(session_path)


def stop_runtime_processes(processes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Verify and stop only exact owned processes. Never kill unrelated listeners."""
    receipts = []
    for proc in processes:
        pid = proc.get("pid")
        if not pid:
            continue
        is_owned = verify_owned_process(proc)
        if not is_owned:
            receipts.append({
                "pid": pid,
                "action": "skipped",
                "reason": "Process does not match recorded PID, start_ticks, cwd, or argv."
            })
            continue

        try:
            os.kill(pid, signal.SIGTERM)
            # Wait up to 5 seconds for termination
            terminated = False
            for _ in range(50):
                time.sleep(0.1)
                try:
                    os.kill(pid, 0)
                except OSError:
                    terminated = True
                    break
            if not terminated:
                os.kill(pid, signal.SIGKILL)
                terminated = True
            if pid in _RUNNING_POPENS:
                try:
                    _RUNNING_POPENS[pid].wait(timeout=1.0)
                except Exception:
                    pass
                _RUNNING_POPENS.pop(pid, None)
            receipts.append({
                "pid": pid,
                "action": "terminated",
                "status": "success"
            })
        except ProcessLookupError:
            receipts.append({
                "pid": pid,
                "action": "already_stopped",
                "status": "success"
            })
        except Exception as e:
            receipts.append({
                "pid": pid,
                "action": "error",
                "error": str(e)
            })
    return receipts


def stop_runtime(session_path: str) -> Dict[str, Any]:
    """
    Public API: stop runtime servers recorded in session JSON.
    Verifies exact owned PID/start/cwd/argv before cleanup.
    Returns sanitized receipt.
    """
    path = pathlib.Path(session_path)
    if not path.exists():
        raise FileNotFoundError(f"Session file not found: {session_path}")
    session_data = json.loads(path.read_text())
    processes = session_data.get("processes", [])
    process_receipts = stop_runtime_processes(processes)
    all_ok = all(pr.get("status") == "success" for pr in process_receipts)
    receipt = {
        "status": "stopped" if all_ok else "cleanup_failed",
        "run_id": session_data.get("run_id"),
        "processes": process_receipts
    }
    return receipt


def is_models_receipt_successful(rec: Any) -> bool:
    """Validate whether models phase completed successfully."""
    if not isinstance(rec, dict):
        return False
    if rec.get("launched") is False:
        return False
    status = rec.get("status")
    return status in ("completed", "completed-awaiting-review", "accepted")


def is_checks_receipt_successful(rec: Any) -> bool:
    """Validate whether checks phase completed and posted successfully."""
    if not isinstance(rec, dict):
        return False
    if rec.get("error"):
        return False
    if rec.get("checks_posted") is False:
        return False
    status = rec.get("status")
    if status in ("rejected", "failed", "unknown", "error", "pending"):
        return False
    if status is not None:
        return status in ("ok", "completed", "clean", "conflict")
    return rec.get("stage") == "checks" and "pair_results" in rec


def run_cli():
    """CLI handler for --help, --preflight, --live, --session, --stage."""
    parser = argparse.ArgumentParser(
        description="Agent Branches Phase Runtime CLI (task-0011).",
        add_help=True
    )
    parser.add_argument("--preflight", action="store_true", help="Run preflight environment checks without live side effects.")
    parser.add_argument("--live", action="store_true", help="Execute live setup, actor execution, and verification checks.")
    parser.add_argument("--session", type=str, default=None, help="Path to existing private session JSON file.")
    parser.add_argument("--stage", choices=["models", "checks", "owner", "cleanup"], default=None, help="Execute specific phase stage.")
    parser.add_argument("--source-root", type=str, default=os.environ.get("SOURCE_ROOT"), help="Path to repository source root.")
    parser.add_argument("--run-root", type=str, default=os.environ.get("RUN_ROOT"), help="Path to runtime run root directory.")
    parser.add_argument("--launcher-root", type=str, default=os.environ.get("LAUNCHER_ROOT"), help="Path to agent-quota-launcher root.")
    parser.add_argument("--launcher-config", type=str, default=os.environ.get("LAUNCHER_CONFIG"), help="Path to launcher-config directory.")
    parser.add_argument("--cached-main", type=str, default=os.environ.get("CACHED_MAIN_JS") or os.environ.get("CACHED_COORDINATOR_JS"), help="Path to cached coordinator main.js.")

    args = parser.parse_args()

    repo_root = pathlib.Path(__file__).resolve().parent.parent
    source_root = pathlib.Path(args.source_root).resolve() if args.source_root else repo_root

    # Resolve launcher_root
    launcher_root: Optional[pathlib.Path] = None
    if args.launcher_root:
        launcher_root = pathlib.Path(args.launcher_root).resolve()
    elif os.environ.get("LAUNCHER_ROOT"):
        launcher_root = pathlib.Path(os.environ["LAUNCHER_ROOT"]).resolve()
    else:
        sibling_launcher = source_root.parent / "agent-quota-launcher"
        if sibling_launcher.exists() and (sibling_launcher / "launcher").is_dir():
            launcher_root = sibling_launcher.resolve()

    # Resolve launcher_config
    launcher_config: Optional[pathlib.Path] = None
    if args.launcher_config:
        launcher_config = pathlib.Path(args.launcher_config).resolve()
    elif os.environ.get("LAUNCHER_CONFIG"):
        launcher_config = pathlib.Path(os.environ["LAUNCHER_CONFIG"]).resolve()
    else:
        if launcher_root and (launcher_root / ".local" / "launcher-config").is_dir():
            launcher_config = (launcher_root / ".local" / "launcher-config").resolve()
        elif (source_root / ".local" / "launcher-config").is_dir():
            launcher_config = (source_root / ".local" / "launcher-config").resolve()

    def validate_launcher_and_config() -> Tuple[bool, str]:
        if not launcher_root or not launcher_root.is_dir():
            return False, f"Missing or invalid launcher root: {launcher_root}"
        if not (launcher_root / "launcher").is_dir():
            return False, f"Launcher package not found in launcher root: {launcher_root / 'launcher'}"
        if not launcher_config or not launcher_config.is_dir():
            return False, f"Missing or invalid launcher config directory: {launcher_config}"
        return True, ""

    if args.preflight:
        print("[preflight] Validating environment, commands, cache, and ports...")
        opts = {"source_root": str(source_root)}
        if args.cached_main:
            opts["cached_main"] = str(pathlib.Path(args.cached_main).resolve())
        res = check_preflight(opts)
        print(json.dumps(res, indent=2))
        if res.get("status") != "ok":
            sys.exit(1)
        sys.exit(0)

    if args.stage == "cleanup":
        if not args.session:
            print("ERROR: --stage cleanup requires --session PATH", file=sys.stderr)
            sys.exit(1)
        if not os.path.exists(args.session):
            print(f"ERROR: Session file not found: {args.session}", file=sys.stderr)
            sys.exit(1)
        receipt = stop_runtime(args.session)
        print("[cleanup] Receipt:")
        print(json.dumps(receipt, indent=2))
        if receipt.get("status") != "stopped":
            sys.exit(1)
        sys.exit(0)

    if args.stage in ["models", "checks", "owner"]:
        if not args.session:
            print(f"ERROR: --stage {args.stage} requires --session PATH", file=sys.stderr)
            sys.exit(1)
        if not os.path.exists(args.session):
            print(f"ERROR: Session file not found: {args.session}", file=sys.stderr)
            sys.exit(1)
        session_path = args.session

        if args.stage in ("models", "owner"):
            ok, err_msg = validate_launcher_and_config()
            if not ok:
                print(f"ERROR: {err_msg}", file=sys.stderr)
                sys.exit(1)

        if args.stage == "models":
            try:
                import live.demo_actors as demo_actors
            except ImportError as e:
                print(f"STAGE models: PENDING (live/demo_actors.py missing: {e})", file=sys.stderr)
                sys.exit(2)
            rec = demo_actors.run_parallel(session_path, str(launcher_root), str(launcher_config))
            print(f"[models] Receipt: {json.dumps(rec, indent=2)}")
            if not is_models_receipt_successful(rec):
                sys.exit(1)
            sys.exit(0)

        elif args.stage == "checks":
            try:
                import live.demo_checks as demo_checks
            except ImportError as e:
                print(f"STAGE checks: PENDING (live/demo_checks.py missing: {e})", file=sys.stderr)
                sys.exit(2)
            rec = demo_checks.run_checks(session_path)
            print(f"[checks] Receipt: {json.dumps(rec, indent=2)}")
            if not is_checks_receipt_successful(rec):
                sys.exit(1)
            sys.exit(0)

        elif args.stage == "owner":
            try:
                import live.demo_checks as demo_checks
            except ImportError as e:
                print(f"STAGE owner: PENDING (live/demo_checks.py missing: {e})", file=sys.stderr)
                sys.exit(2)
            rec = demo_checks.run_owner_followup(session_path, str(launcher_root), str(launcher_config))
            print(f"[owner] Receipt: {json.dumps(rec, indent=2)}")
            st = rec.get("status") if isinstance(rec, dict) else None
            if st in ("failed", "rejected", "error") or (isinstance(rec, dict) and rec.get("error")):
                sys.exit(1)
            sys.exit(0)

    if args.live:
        # Validate launcher and config before side effects
        ok, err_msg = validate_launcher_and_config()
        if not ok:
            print(f"ERROR: {err_msg}", file=sys.stderr)
            sys.exit(1)

        # Validate modules import before side effects
        try:
            import live.demo_actors as demo_actors
        except ImportError as e:
            print(f"ERROR: Missing live.demo_actors module: {e}", file=sys.stderr)
            sys.exit(2)
        try:
            import live.demo_checks as demo_checks
        except ImportError as e:
            print(f"ERROR: Missing live.demo_checks module: {e}", file=sys.stderr)
            sys.exit(2)

        opts = {
            "source_root": str(source_root),
        }
        if args.run_root:
            opts["run_root"] = str(pathlib.Path(args.run_root).resolve())
        if args.cached_main:
            opts["cached_main"] = str(pathlib.Path(args.cached_main).resolve())

        print("[live] Starting isolated runtime and seeding canonical repository...")
        session_path = None
        exit_code = 0
        try:
            session_path = start_runtime(opts)
            print(f"[live] Session initialized at: {session_path}")

            print("[live] Executing actor models phase...")
            models_receipt = demo_actors.run_parallel(session_path, str(launcher_root), str(launcher_config))
            print(f"[live] Models phase completed: {models_receipt}")

            if not is_models_receipt_successful(models_receipt):
                print(f"[live] Models phase rejected or failed: {models_receipt}", file=sys.stderr)
                exit_code = 1

            print("[live] Executing checks phase...")
            checks_receipt = demo_checks.run_checks(session_path)
            print(f"[live] Checks phase completed: {checks_receipt}")

            if not is_checks_receipt_successful(checks_receipt):
                print(f"[live] Checks phase rejected or failed: {checks_receipt}", file=sys.stderr)
                exit_code = 1

        except Exception as e:
            print(f"[live] Execution error: {e}", file=sys.stderr)
            exit_code = 1
        finally:
            if session_path:
                print("[live] Cleaning up owned processes...")
                try:
                    cleanup_receipt = stop_runtime(session_path)
                    print(f"[live] Cleanup complete: {json.dumps(cleanup_receipt)}")
                    if cleanup_receipt.get("status") != "stopped":
                        exit_code = exit_code or 1
                    for p_rec in cleanup_receipt.get("processes", []):
                        if p_rec.get("action") in ("error", "skipped"):
                            exit_code = exit_code or 1
                except Exception as ce:
                    print(f"[live] Cleanup error: {ce}", file=sys.stderr)
                    exit_code = exit_code or 1

        sys.exit(exit_code)

    # No arguments provided
    parser.print_help()
    sys.exit(0)


if __name__ == "__main__":
    run_cli()
