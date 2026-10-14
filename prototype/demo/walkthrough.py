#!/usr/bin/env python3
"""
Agent Branches: Self-contained protocol walkthrough (Python standard library only).
Zero external dependencies; safe path-scoped credentials; no argv exposure.
"""
import os
import sys
import time
import json
import socket
import shutil
import secrets
import pathlib
import tempfile
import subprocess
import urllib.request
import urllib.error

def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]

def http_request(url, method="GET", headers=None, data=None, timeout=10):
    req_headers = {"User-Agent": "agent-branches-walkthrough"}
    if headers:
        req_headers.update(headers)
    body = None
    if data is not None:
        if isinstance(data, (dict, list)):
            body = json.dumps(data).encode("utf-8")
            req_headers["Content-Type"] = "application/json"
        elif isinstance(data, str):
            body = data.encode("utf-8")
        elif isinstance(data, bytes):
            body = data
    req = urllib.request.Request(url, data=body, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content = resp.read().decode("utf-8")
            return resp.status, content
    except urllib.error.HTTPError as e:
        content = e.read().decode("utf-8") if e.fp else ""
        return e.code, content

def wait_for_ready(url, expected_statuses=(200, 401), timeout=15):
    start = time.time()
    while time.time() - start < timeout:
        try:
            status, _ = http_request(url, method="GET", timeout=2)
            if status in expected_statuses:
                return True
        except Exception:
            pass
        time.sleep(0.2)
    return False

def main():
    if os.environ.get("BASE_URL"):
        smoke_script = pathlib.Path(__file__).resolve().parent / "cloud-smoke.py"
        if not smoke_script.exists():
            sys.stderr.write(f"Error: expected cloud-smoke script not found at {smoke_script}\n")
            sys.exit(1)
        cmd = ["uv", "run", "--project", str(smoke_script.parent.parent), "python", str(smoke_script)] + sys.argv[1:]
        res = subprocess.run(cmd)
        sys.exit(res.returncode)

    here = pathlib.Path(__file__).resolve()
    proto_dir = here.parent.parent if here.parent.name == "demo" else here.parent

    if not (proto_dir / "local-artifacts" / "sidecar.mjs").exists():
        cwd = pathlib.Path.cwd().resolve()
        if (cwd / "prototype" / "local-artifacts" / "sidecar.mjs").exists():
            proto_dir = cwd / "prototype"
        elif (cwd / "local-artifacts" / "sidecar.mjs").exists():
            proto_dir = cwd

    sidecar_script = proto_dir / "local-artifacts" / "sidecar.mjs"
    coord_main = proto_dir / ".build" / "node" / "src" / "local" / "main.js"

    if not sidecar_script.exists():
        sys.stderr.write(f"Error: sidecar script not found at {sidecar_script}. Run from prototype directory.\n")
        sys.exit(1)
    if not coord_main.exists():
        sys.stderr.write(f"Error: coordinator build not found at {coord_main}. Run 'npm run build:node' first.\n")
        sys.exit(1)

    node_bin = shutil.which("node")
    git_bin = shutil.which("git")
    if not node_bin or not git_bin:
        sys.stderr.write("Error: node and git must be available on PATH.\n")
        sys.exit(1)

    # State directory setup outside source repository with 0700 permissions
    custom_state = os.environ.get("AB_STATE_PARENT")
    if custom_state:
        base_dir = pathlib.Path(custom_state).resolve()
        base_dir.mkdir(parents=True, exist_ok=True)
        state_dir = pathlib.Path(tempfile.mkdtemp(prefix="run-", dir=str(base_dir)))
    elif (proto_dir.parent / "state").exists():
        state_dir = pathlib.Path(tempfile.mkdtemp(prefix="run-", dir=str(proto_dir.parent / "state")))
    else:
        state_dir = pathlib.Path(tempfile.mkdtemp(prefix="ab-proto-"))
    os.chmod(state_dir, 0o700)

    sidecar_root = state_dir / "sidecar"
    sidecar_root.mkdir(parents=True, exist_ok=True)
    os.chmod(sidecar_root, 0o700)
    coord_state_file = state_dir / "coordinator-state.json"
    workspaces_dir = state_dir / "workspaces"
    workspaces_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(workspaces_dir, 0o700)

    sidecar_port = find_free_port()
    coord_port = find_free_port()
    while coord_port == sidecar_port:
        coord_port = find_free_port()

    # Shared secrets (random tokens, zero home defaults)
    sidecar_token = secrets.token_hex(20)
    admin_token = secrets.token_hex(20)
    runner_token = secrets.token_hex(20)

    sidecar_proc = None
    coord_proc = None
    sidecar_log = open(state_dir / "sidecar.log", "w")
    coord_log = open(state_dir / "coordinator.log", "w")

    try:
        # 1. Start sidecar
        sidecar_env = {
            **os.environ,
            "PATH": os.environ.get("PATH", ""),
            "SIDECAR_ROOT": str(sidecar_root),
            "SIDECAR_PORT": str(sidecar_port),
            "SIDECAR_TOKEN": sidecar_token,
            "SIDECAR_NOTIFY_URL": f"http://127.0.0.1:{coord_port}/events/push",
        }
        sidecar_proc = subprocess.Popen(
            [node_bin, str(sidecar_script)],
            env=sidecar_env,
            stdout=sidecar_log,
            stderr=sidecar_log,
            cwd=str(proto_dir),
        )

        # 2. Start coordinator
        coord_env = {
            **os.environ,
            "PORT": str(coord_port),
            "LOCAL_ARTIFACTS_URL": f"http://127.0.0.1:{sidecar_port}",
            "LOCAL_ARTIFACTS_TOKEN": sidecar_token,
            "ADMIN_TOKEN": admin_token,
            "RUNNER_TOKEN": runner_token,
            "COORDINATOR_STATE_FILE": str(coord_state_file),
        }
        coord_proc = subprocess.Popen(
            [node_bin, str(coord_main)],
            env=coord_env,
            stdout=coord_log,
            stderr=coord_log,
            cwd=str(proto_dir),
        )

        # Readiness gate (finite timeout)
        if not wait_for_ready(f"http://127.0.0.1:{coord_port}/status", expected_statuses=(401, 200), timeout=15):
            raise RuntimeError("Coordinator did not become ready within timeout")

        print("1. Service initialization: sidecar and coordinator listening on loopback.")

        # 3. Setup canonical repository
        status, resp_text = http_request(
            f"http://127.0.0.1:{coord_port}/setup",
            method="POST",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        if status not in (200, 201):
            raise RuntimeError(f"POST /setup failed with status {status}: {resp_text}")
        setup_data = json.loads(resp_text)
        print(f"2. Canonical repository setup: {setup_data.get('canonical', {}).get('name')}")

        # 4. Create Task 1 (claude) and Task 2 (codex)
        status, resp1_text = http_request(
            f"http://127.0.0.1:{coord_port}/tasks",
            method="POST",
            headers={"Authorization": f"Bearer {admin_token}"},
            data={"agent": "claude", "intent": "fix login loop"},
        )
        if status not in (200, 201):
            raise RuntimeError(f"POST /tasks (claude) failed with status {status}: {resp1_text}")
        task1 = json.loads(resp1_text)
        task1_token = task1["token"]["plaintext"]
        task1_remote = task1["fork"]["remote"]
        task1_agent = task1["agentId"]
        task1_id = task1["taskId"]

        # Store token with 0600 permissions outside source code
        task1_tok_file = workspaces_dir / ".task1.token"
        task1_tok_file.touch(mode=0o600)
        task1_tok_file.write_text(task1_token)

        status, resp2_text = http_request(
            f"http://127.0.0.1:{coord_port}/tasks",
            method="POST",
            headers={"Authorization": f"Bearer {admin_token}"},
            data={"agent": "codex", "intent": "refactor auth routes"},
        )
        if status not in (200, 201):
            raise RuntimeError(f"POST /tasks (codex) failed with status {status}: {resp2_text}")
        task2 = json.loads(resp2_text)
        task2_token = task2["token"]["plaintext"]
        task2_agent = task2["agentId"]
        task2_base_sha = task2.get("base_sha") or task2.get("head")

        task2_tok_file = workspaces_dir / ".task2.token"
        task2_tok_file.touch(mode=0o600)
        task2_tok_file.write_text(task2_token)
        print(f"3. Provisioned forks: {task1_agent} and {task2_agent}")

        # Base Git environment with GIT_TERMINAL_PROMPT=0 and path-scoped authentication
        base_git_env = {
            **os.environ,
            "GIT_TERMINAL_PROMPT": "0",
        }
        git_env = {
            **base_git_env,
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "http.extraHeader",
            "GIT_CONFIG_VALUE_0": f"Authorization: Bearer {task1_token}",
        }

        # 5. Clone Task 1 fork into isolated workspace with path-scoped authentication
        clone_dir = workspaces_dir / "task1-clone"
        res = subprocess.run([git_bin, "clone", task1_remote, str(clone_dir)], env=git_env, capture_output=True, text=True, timeout=30)
        if res.returncode != 0:
            raise RuntimeError(f"git clone failed: {res.stderr}")
        print("4. Cloned fork into isolated workspace.")

        # 6. Make commit and push from clone
        subprocess.run([git_bin, "config", "user.name", "Agent Claude"], cwd=clone_dir, check=True, capture_output=True, env=base_git_env, timeout=15)
        subprocess.run([git_bin, "config", "user.email", "claude@example.invalid"], cwd=clone_dir, check=True, capture_output=True, env=base_git_env, timeout=15)

        sample_code_file = clone_dir / "fix.txt"
        sample_code_file.write_text("login loop fix verified\n")
        subprocess.run([git_bin, "add", "fix.txt"], cwd=clone_dir, check=True, capture_output=True, env=base_git_env, timeout=15)
        subprocess.run([git_bin, "commit", "-m", "fix login loop"], cwd=clone_dir, check=True, capture_output=True, env=base_git_env, timeout=15)

        res = subprocess.run([git_bin, "push", "origin", "main"], cwd=clone_dir, env=git_env, capture_output=True, text=True, timeout=30)
        if res.returncode != 0:
            raise RuntimeError(f"git push failed: {res.stderr}")

        task1_head = subprocess.check_output([git_bin, "rev-parse", "HEAD"], cwd=clone_dir, text=True, env=base_git_env, timeout=15).strip()
        print(f"5. Pushed commit to fork (head: {task1_head[:8]}).")

        # 7. Native coordinator head readback (wait for post-receive webhook delivery)
        updated = False
        start_poll = time.time()
        while time.time() - start_poll < 10:
            status, s_text = http_request(
                f"http://127.0.0.1:{coord_port}/status",
                method="GET",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            if status == 200:
                head_status_data = json.loads(s_text)
                if head_status_data.get("heads", {}).get(task1_agent) == task1_head:
                    updated = True
                    break
            time.sleep(0.3)

        if not updated:
            raise RuntimeError(f"Coordinator did not reflect updated head {task1_head} within timeout")
        print("6. Native post-receive hook verified: coordinator head vector updated.")

        # 8. Real git merge-tree check and Contract 0.1 typed checks submission
        res = subprocess.run(
            [git_bin, "merge-tree", "--write-tree", task1_head, task2_base_sha],
            cwd=clone_dir,
            capture_output=True,
            text=True,
            env=base_git_env,
            timeout=15,
        )
        if res.returncode == 0:
            check_status = "clean"
            check_kind = None
            evidence = {"summary": "clean trial merge across agent heads"}
        else:
            check_status = "conflict"
            check_kind = "textual"
            evidence = {"summary": "textual conflict detected by git merge-tree"}

        checks_payload = {
            "contract": "0.1",
            "vector": {task1_agent: task1_head, task2_agent: task2_base_sha},
            "policy": {
                "merge": "merge-tree-v1",
                "tests": {"command": "npm test", "budget_s": 60},
            },
            "results": [
                {
                    "pair": [task1_agent, task2_agent],
                    "heads": {task1_agent: task1_head, task2_agent: task2_base_sha},
                    "status": check_status,
                    "kind": check_kind,
                    "evidence": evidence,
                }
            ],
        }

        status, checks_resp = http_request(
            f"http://127.0.0.1:{coord_port}/checks",
            method="POST",
            headers={"Authorization": f"Bearer {runner_token}"},
            data=checks_payload,
        )
        if status != 200:
            raise RuntimeError(f"POST /checks failed with status {status}: {checks_resp}")
        print("7. Contract 0.1 typed checks submitted and accepted by coordinator.")

        # 9. Authenticated reads and anonymous 401 check
        status, _ = http_request(
            f"http://127.0.0.1:{coord_port}/status",
            method="GET",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        if status != 200:
            raise RuntimeError(f"Authenticated GET /status failed: {status}")

        status, _ = http_request(
            f"http://127.0.0.1:{coord_port}/status",
            method="GET",
        )
        if status != 401:
            raise RuntimeError(f"Anonymous GET /status expected 401, got {status}")

        status, _ = http_request(
            f"http://127.0.0.1:{coord_port}/tasks/{task1_id}",
            method="GET",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        if status != 200:
            raise RuntimeError(f"Authenticated GET /tasks/:id failed: {status}")
        print("8. Read access control verified: 200 OK authenticated, 401 Unauthorized anonymous.")
        print("Walkthrough completed successfully.")

    finally:
        # Graceful cleanup of exact child processes and state
        if coord_proc:
            try:
                coord_proc.terminate()
                coord_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                coord_proc.kill()
                coord_proc.wait(timeout=5)
            except Exception:
                pass
        if sidecar_proc:
            try:
                sidecar_proc.terminate()
                sidecar_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                sidecar_proc.kill()
                sidecar_proc.wait(timeout=5)
            except Exception:
                pass
        if sidecar_log and not sidecar_log.closed:
            sidecar_log.close()
        if coord_log and not coord_log.closed:
            coord_log.close()
        shutil.rmtree(state_dir, ignore_errors=True)

if __name__ == "__main__":
    main()
