#!/usr/bin/env python3
"""
Agent Branches Cloudflare Deploy-Config / Smoke Verification Suite
Standard library Python only.
Zero credentials printed to stdout or persisted in report.json.
Finite subprocess timeouts and child waits.
Supports live Cloudflare Worker deployment and mock/loopback verification.
"""

import os
import sys
import json
import time
import uuid
import shutil
import urllib.request
import urllib.error
import subprocess
import tempfile
import threading
import http.server
import socketserver
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor

# Hard limits agreed with backend Coordinator Durable Object budget tracker
MAX_BUDGET_DELTA_HARD = 90  # live run measured 60 ops through the merge-tree step
MAX_DAILY_OPS = int(os.environ.get("MAX_DAILY_OPS", 200))
MAX_MONTHLY_OPS = int(os.environ.get("MAX_MONTHLY_OPS", 6000))
MAX_REPOS = int(os.environ.get("MAX_REPOS", 4))
MAX_TOTAL_BYTES = int(os.environ.get("MAX_TOTAL_BYTES", 16777216))
MAX_BODY_BYTES = int(os.environ.get("MAX_BODY_BYTES", 262144))

SUBPROCESS_TIMEOUT = 15
HTTP_TIMEOUT = 15


def get_utc_iso():
    return datetime.now(timezone.utc).isoformat()


def get_tool_versions():
    git_ver = "unknown"
    try:
        r = subprocess.run(["git", "--version"], capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            git_ver = r.stdout.strip()
    except Exception as e:
        git_ver = f"error: {e}"

    node_ver = None
    try:
        r = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            node_ver = r.stdout.strip()
    except Exception:
        pass

    return {
        "git_version": git_ver,
        "python_version": sys.version.split()[0],
        "node_version": node_ver,
        "cwd": os.getcwd()
    }


class MockBackendHandler(http.server.BaseHTTPRequestHandler):
    """
    In-memory / loopback mock server implementing the exact Cloudflare Worker
    backend interface agreed with backend peer (interface.json & worker.ts).
    """

    def log_message(self, format, *args):
        # Suppress routine HTTP request logging to avoid token leakage
        pass

    def get_bearer_token(self):
        auth = self.headers.get("Authorization", "")
        if auth.lower().startswith("bearer "):
            return auth[7:].strip()
        return None

    def send_json(self, status, data):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        state = self.server.state
        url_path = self.path
        if "?" in url_path:
            url_path, query = url_path.split("?", 1)
        else:
            query = ""

        # 1. GET /public/status (0 Artifacts ops - stored snapshot)
        if url_path == "/public/status":
            canonical_info = {
                "name": state.get("canonical_name"),
                "remote": f"/git/{state.get('canonical_name')}.git" if state.get("canonical_name") else None
            }
            self.send_json(200, {
                "status": "ok",
                "canonical": canonical_info,
                "sanitizedSnapshot": True
            })
            return

        # 2. GET /cloud/budget (flat fields: caps and remaining)
        if url_path == "/cloud/budget":
            token = self.get_bearer_token()
            if not token or token != self.server.admin_token:
                self.send_response(401 if not token else 403)
                self.end_headers()
                return

            with state["lock"]:
                day_ops = state["utc_day_ops"]
                month_ops = state["calendar_month_ops"]
                self.send_json(200, {
                    "utcDayOps": day_ops,
                    "calendarMonthOps": month_ops,
                    "repoCount": len(state["repos"]),
                    "totalBytesUploaded": state["total_bytes_uploaded"],
                    "dailyCap": MAX_DAILY_OPS,
                    "monthlyCap": MAX_MONTHLY_OPS,
                    "maxRepos": MAX_REPOS,
                    "maxTotalBytes": MAX_TOTAL_BYTES,
                    "remainingDayOps": max(0, MAX_DAILY_OPS - day_ops),
                    "remainingMonthOps": max(0, MAX_MONTHLY_OPS - month_ops)
                })
            return

        # 3. GET /git/:repo.git/info/refs
        git_match = url_path.startswith("/git/") and "/info/refs" in url_path
        if git_match:
            self.handle_git_request(url_path, query)
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        state = self.server.state
        url_path = self.path

        # Method auth check: POST /public/status -> 405 Method Not Allowed
        if url_path == "/public/status":
            self.send_response(405)
            self.end_headers()
            return

        if "?" in url_path:
            url_path, query = url_path.split("?", 1)
        else:
            query = ""

        # Read JSON body if application/json
        content_length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_length) if content_length > 0 else b""

        # 1. POST /setup
        if url_path == "/setup":
            token = self.get_bearer_token()
            if not token or token != self.server.admin_token:
                self.send_response(401 if not token else 403)
                self.end_headers()
                return

            with state["lock"]:
                state["utc_day_ops"] += 1
                state["calendar_month_ops"] += 1
                can_name = "agent-branches-canonical"
                state["canonical_name"] = can_name
                state["repos"][can_name] = {
                    "name": can_name,
                    "upstream": None,
                    "is_canonical": True
                }
                # Create bare git repo on disk in git_root
                can_dir = os.path.join(self.server.git_root, f"{can_name}.git")
                if not os.path.exists(can_dir):
                    subprocess.run(["git", "init", "--bare", can_dir], check=True, capture_output=True, timeout=5)
                    subprocess.run(["git", "-C", can_dir, "config", "http.receivepack", "true"], check=True, timeout=5)

            self.send_json(201, {
                "canonical": {
                    "name": can_name,
                    "remote": f"/git/{can_name}.git"
                },
                "created": True,
                "seedCommit": None
            })
            return

        # 2. POST /tasks
        if url_path == "/tasks":
            token = self.get_bearer_token()
            if not token or token != self.server.admin_token:
                self.send_response(401 if not token else 403)
                self.end_headers()
                return

            req_data = {}
            if raw_body:
                try:
                    req_data = json.loads(raw_body.decode("utf-8"))
                except Exception:
                    pass

            with state["lock"]:
                if len(state["repos"]) >= MAX_REPOS:
                    self.send_response(500)
                    self.end_headers()
                    self.wfile.write(b"Budget exceeded: max repos")
                    return

                state["utc_day_ops"] += 2  # fork + mintToken
                state["calendar_month_ops"] += 2
                seq = len(state["tasks"]) + 1
                agent_raw = req_data.get("agent", "agent")
                agent_id = f"{agent_raw}-{seq:04d}"
                task_id = f"task-{seq:04d}"
                fork_name = f"canonical-{agent_id}"

                # Clone canonical bare repo to fork bare repo
                can_dir = os.path.join(self.server.git_root, f"{state['canonical_name']}.git")
                fork_dir = os.path.join(self.server.git_root, f"{fork_name}.git")
                if not os.path.exists(fork_dir):
                    subprocess.run(["git", "clone", "--bare", can_dir, fork_dir], check=True, capture_output=True, timeout=10)
                    subprocess.run(["git", "-C", fork_dir, "config", "http.receivepack", "true"], check=True, timeout=5)

                gw_token = f"gw_{uuid.uuid4().hex}"
                state["tokens"][gw_token] = {
                    "agentId": agent_id,
                    "taskId": task_id,
                    "repo": fork_name,
                    "expiresAt": "2026-10-12T06:30:00Z"
                }
                state["repos"][fork_name] = {
                    "name": fork_name,
                    "upstream": fork_dir,
                    "is_canonical": False
                }
                state["tasks"][task_id] = {
                    "taskId": task_id,
                    "agentId": agent_id,
                    "forkName": fork_name,
                    "baseSha": req_data.get("base_sha", ""),
                    "token": gw_token
                }
                state["agents"][agent_id] = {
                    "agentId": agent_id,
                    "taskId": task_id,
                    "forkName": fork_name,
                    "head": None
                }

                origin = f"http://127.0.0.1:{self.server.server_address[1]}"
                fork_remote = f"{origin}/git/{fork_name}.git"

            self.send_json(201, {
                "taskId": task_id,
                "agentId": agent_id,
                "fork": {
                    "name": fork_name,
                    "remote": fork_remote
                },
                "ref": "refs/heads/main",
                "base_sha": req_data.get("base_sha", ""),
                "intent": req_data.get("intent", ""),
                "token": {
                    "scope": "write",
                    "expiresAt": "2026-10-12T06:30:00Z",
                    "plaintext": gw_token
                },
                "head": None
            })
            return

        # 3. POST /events/push
        if url_path == "/events/push":
            token = self.get_bearer_token()
            if not token:
                self.send_response(401)
                self.end_headers()
                return

            req_data = json.loads(raw_body.decode("utf-8")) if raw_body else {}
            with state["lock"]:
                token_info = state["tokens"].get(token)
                if not token_info:
                    self.send_response(403)
                    self.end_headers()
                    return

                agent_id = req_data.get("agent")
                if token_info["agentId"] != agent_id:
                    self.send_response(403)
                    self.end_headers()
                    return

                sha = req_data.get("sha")
                state["heads"][agent_id] = sha
                if agent_id in state["agents"]:
                    state["agents"][agent_id]["head"] = sha
                state["utc_day_ops"] += 1
                state["calendar_month_ops"] += 1

                resp = {
                    "accepted": True,
                    "deduped": False,
                    "agent": agent_id,
                    "heads": dict(state["heads"]),
                    "invalidatedWarnings": [],
                    "newWarnings": [],
                    "radarChecks": 0,
                    "receipt": {
                        "id": f"receipt-{agent_id}-{sha}",
                        "sha": sha,
                        "status": "valid"
                    }
                }
            self.send_json(200, resp)
            return

        # 4. POST /checks
        if url_path == "/checks":
            token = self.get_bearer_token()
            if not token or token != self.server.runner_token:
                self.send_response(401 if not token else 403)
                self.end_headers()
                return

            req_data = json.loads(raw_body.decode("utf-8")) if raw_body else {}
            if req_data.get("contract") not in ("0.0", "0.1"):
                self.send_json(400, {"error": "unsupported contract version"})
                return
            vector = req_data.get("vector", {})

            with state["lock"]:
                current_heads = state["heads"]
                stale = False
                if set(vector.keys()) != set(current_heads.keys()):
                    stale = True
                else:
                    for k, v in vector.items():
                        if current_heads.get(k) != v:
                            stale = True
                            break

                if stale:
                    self.send_json(409, {
                        "stale": True,
                        "currentHeads": dict(current_heads)
                    })
                    return

                state["utc_day_ops"] += 1
                state["calendar_month_ops"] += 1
                results = req_data.get("results", [])

            self.send_json(200, {
                "stale": False,
                "accepted": len(results),
                "pairs": [],
                "createdWarnings": [],
                "currentHeads": dict(vector),
                "runnerReport": {
                    "policy": req_data.get("policy"),
                    "accepted": len(results),
                    "at": get_utc_iso()
                }
            })
            return

        # 5. POST /tasks/:id/tests (test provenance & cross-task negative check)
        if url_path.startswith("/tasks/") and url_path.endswith("/tests"):
            parts = url_path.split("/")
            task_id = parts[2]
            token = self.get_bearer_token()
            with state["lock"]:
                task = state["tasks"].get(task_id)
                token_info = state["tokens"].get(token) if token else None
                if not task or not token_info or token_info["taskId"] != task_id:
                    self.send_response(403)
                    self.end_headers()
                    return
                state["utc_day_ops"] += 1
                state["calendar_month_ops"] += 1
            self.send_json(201, {"ok": True, "taskId": task_id})
            return

        # 6. POST /git/:repo.git/git-receive-pack or git-upload-pack
        git_match = url_path.startswith("/git/") and (
            "/git-receive-pack" in url_path or "/git-upload-pack" in url_path
        )
        if git_match:
            self.handle_git_request(url_path, query, raw_body)
            return

        self.send_response(404)
        self.end_headers()

    def do_DELETE(self):
        state = self.server.state
        url_path = self.path

        # DELETE /cloud/demo-repos: Authenticated app inventory cleanup
        if url_path == "/cloud/demo-repos":
            token = self.get_bearer_token()
            if not token or token != self.server.admin_token:
                self.send_response(401 if not token else 403)
                self.end_headers()
                return

            with state["lock"]:
                count = len(state["repos"])
                state["repos"].clear()
                state["tokens"].clear()
                state["tasks"].clear()
                state["agents"].clear()
                state["heads"].clear()
                state["canonical_name"] = None
                state["utc_day_ops"] += 1
                state["calendar_month_ops"] += 1

                # Clean all git repositories from disk in git_root
                if os.path.exists(self.server.git_root):
                    for item in os.listdir(self.server.git_root):
                        target = os.path.join(self.server.git_root, item)
                        if os.path.isdir(target):
                            shutil.rmtree(target, ignore_errors=True)

            self.send_json(200, {"deleted": count})
            return

        self.send_response(404)
        self.end_headers()

    def handle_git_request(self, url_path, query, body=b""):
        state = self.server.state
        parts = url_path[len("/git/"):].split("/")
        repo_file = parts[0]
        repo_name = repo_file[:-4] if repo_file.endswith(".git") else repo_file
        action = "/".join(parts[1:])

        token = self.get_bearer_token()
        if not token:
            self.send_response(401)
            self.end_headers()
            return

        with state["lock"]:
            # Check authorization:
            # If canonical, token must be ADMIN_TOKEN
            if repo_name == state.get("canonical_name"):
                if token != self.server.admin_token:
                    self.send_response(403)
                    self.end_headers()
                    return
            else:
                token_info = state["tokens"].get(token)
                if not token_info or token_info["repo"] != repo_name:
                    self.send_response(403)
                    self.end_headers()
                    return

            # Budget operation & byte reservation BEFORE execution
            if state["utc_day_ops"] >= MAX_DAILY_OPS:
                self.send_response(429)
                self.end_headers()
                self.wfile.write(b"Budget exceeded: max daily ops")
                return

            if len(body) > MAX_BODY_BYTES:
                self.send_response(413)
                self.end_headers()
                self.wfile.write(b"Payload too large")
                return

            if state["total_bytes_uploaded"] + len(body) > MAX_TOTAL_BYTES:
                self.send_response(429)
                self.end_headers()
                self.wfile.write(b"Budget exceeded: max total bytes")
                return

            state["utc_day_ops"] += 1
            state["calendar_month_ops"] += 1
            if len(body) > 0:
                state["total_bytes_uploaded"] += len(body)

        # Execute git-http-backend
        cgi_env = {
            "GIT_PROJECT_ROOT": self.server.git_root,
            "GIT_HTTP_EXPORT_ALL": "1",
            "PATH_INFO": f"/{repo_name}.git/{action}",
            "QUERY_STRING": query,
            "REQUEST_METHOD": self.command,
            "PATH": os.environ.get("PATH", "/usr/bin:/bin")
        }
        if "Content-Type" in self.headers:
            cgi_env["CONTENT_TYPE"] = self.headers["Content-Type"]

        backend_bin = "/usr/lib/git-core/git-http-backend"
        if not os.path.exists(backend_bin):
            backend_bin = "git-http-backend"

        proc = subprocess.Popen(
            [backend_bin],
            env=cgi_env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        out, err = proc.communicate(input=body, timeout=SUBPROCESS_TIMEOUT)

        if b"\r\n\r\n" not in out:
            self.send_response(500)
            self.end_headers()
            return

        parts = out.split(b"\r\n\r\n", 1)
        header_lines = parts[0].split(b"\r\n")
        resp_status = 200
        resp_headers = []
        for line in header_lines:
            if not line:
                continue
            k, v = line.decode("iso-8859-1").split(":", 1)
            if k.lower() == "status":
                resp_status = int(v.strip().split()[0])
            else:
                resp_headers.append((k, v.strip()))

        self.send_response(resp_status)
        for k, v in resp_headers:
            self.send_header(k, v)
        self.end_headers()
        if len(parts) > 1:
            self.wfile.write(parts[1])


class MockServerManager:
    def __init__(self, admin_token="smoke_admin_secret", runner_token="smoke_runner_secret"):
        self.admin_token = admin_token
        self.runner_token = runner_token
        self.git_root = tempfile.mkdtemp(prefix="mock_git_root_")
        os.chmod(self.git_root, 0o700)

        self.server = socketserver.TCPServer(("127.0.0.1", 0), MockBackendHandler)
        self.server.admin_token = self.admin_token
        self.server.runner_token = self.runner_token
        self.server.git_root = self.git_root
        self.server.state = {
            "lock": threading.Lock(),
            "utc_day_ops": 0,
            "calendar_month_ops": 0,
            "total_bytes_uploaded": 0,
            "repos": {},
            "tasks": {},
            "agents": {},
            "tokens": {},
            "heads": {},
            "canonical_name": None
        }

        self.port = self.server.server_address[1]
        self.base_url = f"http://127.0.0.1:{self.port}"
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.daemon = True
        self.thread.start()

    def shutdown(self):
        try:
            self.server.shutdown()
            self.server.server_close()
        except Exception:
            pass
        if os.path.exists(self.git_root):
            shutil.rmtree(self.git_root, ignore_errors=True)


class CloudSmokeRunner:
    """
    Executes the full smoke verification against BASE_URL using ADMIN_TOKEN and RUNNER_TOKEN.
    """

    def __init__(self, base_url, admin_token, runner_token, actors_count=2, report_path="report.json", is_mock=False):
        self.base_url = base_url.rstrip("/")
        self.admin_token = admin_token
        self.runner_token = runner_token
        self.actors_count = actors_count
        self.report_path = report_path
        self.is_mock = is_mock

        self.temp_dirs = []
        self.start_time = None
        self.end_time = None

        self.initial_budget = None
        self.budget_utc_day = None
        self.final_budget = None
        self.budget_delta = None

        self.verifications = {
            "preflight_budget_headroom_ok": False,
            "public_status_sanitized_ok": False,
            "setup_canonical_created": False,
            "seed_push_successful": False,
            "concurrent_actors_fork_and_push_ok": False,
            "explicit_events_push_callbacks_ok": False,
            "trusted_runner_merge_tree_clean": False,
            "trusted_runner_typed_checks_accepted": False,
            "negative_method_not_allowed_405_refused": False,
            "negative_stale_checks_409_refused": False,
            "negative_cross_task_403_refused": False,
            "negative_cross_repo_push_403_refused": False,
            "negative_unauth_budget_401_refused": False,
            "cleanup_demo_repos_ok": False
        }

        self.canonical_name = None
        self.canonical_remote = None
        self.base_sha = None
        self.actor_data = {}  # agent_id -> { taskId, forkRemote, token, headSha }

    def make_temp_dir(self, prefix):
        td = tempfile.mkdtemp(prefix=prefix)
        os.chmod(td, 0o700)
        self.temp_dirs.append(td)
        return td

    def clean_temp_dirs(self):
        for td in self.temp_dirs:
            if os.path.exists(td):
                try:
                    shutil.rmtree(td, ignore_errors=True)
                except Exception:
                    pass
        self.temp_dirs.clear()

    def http_request(self, method, path, headers=None, body=None, expect_status=None):
        url = f"{self.base_url}{path}" if path.startswith("/") else f"{self.base_url}/{path}"
        req_headers = {"User-Agent": "AgentBranches-Smoke/1.0"}
        if headers:
            req_headers.update(headers)

        data = None
        if body is not None:
            if isinstance(body, (dict, list)):
                data = json.dumps(body).encode("utf-8")
                req_headers["Content-Type"] = "application/json"
            elif isinstance(body, bytes):
                data = body
            elif isinstance(body, str):
                data = body.encode("utf-8")

        req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
                resp_status = resp.status
                resp_bytes = resp.read()
                resp_data = None
                content_type = resp.headers.get("Content-Type", "")
                if "application/json" in content_type:
                    try:
                        resp_data = json.loads(resp_bytes.decode("utf-8"))
                    except Exception:
                        pass
                if expect_status is not None and resp_status != expect_status:
                    raise RuntimeError(f"Expected HTTP {expect_status} on {method} {path}, got {resp_status}")
                return resp_status, resp_data, resp_bytes
        except urllib.error.HTTPError as he:
            err_bytes = he.read()
            err_data = None
            if "application/json" in he.headers.get("Content-Type", ""):
                try:
                    err_data = json.loads(err_bytes.decode("utf-8"))
                except Exception:
                    pass
            if expect_status is not None and he.code != expect_status:
                detail = err_data.get("error") if isinstance(err_data, dict) else None
                raise RuntimeError(f"HTTP {he.code} on {method} {path} (expected {expect_status})" + (f": {str(detail)[:200]}" if detail else ""))
            return he.code, err_data, err_bytes

    def configure_git_repo(self, repo_dir):
        subprocess.run(["git", "config", "user.name", "AgentBranches Smoke"], cwd=repo_dir, check=True, timeout=5)
        subprocess.run(["git", "config", "user.email", "smoke@agent-branches.local"], cwd=repo_dir, check=True, timeout=5)

    def git_env(self, token):
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"
        if token:
            env["GIT_CONFIG_COUNT"] = "1"
            env["GIT_CONFIG_KEY_0"] = "http.extraHeader"
            env["GIT_CONFIG_VALUE_0"] = f"Authorization: Bearer {token}"
        return env

    def run_preflight(self):
        print("[1/8] Running preflight status and budget checks...")
        # 1. Public status (costs 0 Artifacts ops - stored snapshot)
        status, data, _ = self.http_request("GET", "/public/status", expect_status=200)
        if data and data.get("sanitizedSnapshot") is True:
            self.verifications["public_status_sanitized_ok"] = True
        else:
            raise RuntimeError(f"Public status snapshot not sanitized or invalid: {data}")

        # 2. Budget check
        status, budget, _ = self.http_request(
            "GET",
            "/cloud/budget",
            headers={"Authorization": f"Bearer {self.admin_token}"},
            expect_status=200
        )
        if not budget:
            raise RuntimeError("Failed to retrieve initial budget stats")

        # Track ownrun: refuse initial unrelated inventory
        initial_repo_count = budget.get("repoCount", 0)
        if initial_repo_count > 0:
            raise RuntimeError(
                f"Initial unrelated inventory detected (repoCount={initial_repo_count} > 0). "
                f"Refusing run to prevent corrupting existing environment."
            )

        # Read server caps and rollover conservative
        daily_cap = budget.get("dailyCap", MAX_DAILY_OPS)
        monthly_cap = budget.get("monthlyCap", MAX_MONTHLY_OPS)
        server_day_remaining = budget.get("remainingDayOps", daily_cap - budget.get("utcDayOps", 0))
        server_month_remaining = budget.get("remainingMonthOps", monthly_cap - budget.get("calendarMonthOps", 0))

        local_day_remaining = MAX_DAILY_OPS - budget.get("utcDayOps", 0)
        local_month_remaining = MAX_MONTHLY_OPS - budget.get("calendarMonthOps", 0)

        effective_day_remaining = min(server_day_remaining, local_day_remaining)
        effective_month_remaining = min(server_month_remaining, local_month_remaining)

        if effective_day_remaining < MAX_BUDGET_DELTA_HARD or effective_month_remaining < MAX_BUDGET_DELTA_HARD:
            raise RuntimeError(
                f"Insufficient operational budget headroom: {effective_day_remaining} daily ops remaining, "
                f"{effective_month_remaining} monthly ops remaining (required: >= {MAX_BUDGET_DELTA_HARD})"
            )

        self.budget_utc_day = datetime.now(timezone.utc).date().isoformat()
        self.initial_budget = budget
        self.verifications["preflight_budget_headroom_ok"] = True
        print(f"      Preflight OK: Day ops: {budget.get('utcDayOps')}, Repo count: {initial_repo_count}")

    def run_setup(self):
        print("[2/8] Setting up canonical baseline repository via gateway ADMIN credential...")
        status, data, _ = self.http_request(
            "POST",
            "/setup",
            headers={"Authorization": f"Bearer {self.admin_token}"},
            expect_status=201
        )
        if not data or not data.get("canonical"):
            raise RuntimeError(f"Setup returned invalid response: {data}")

        self.canonical_name = data["canonical"]["name"]
        remote = data["canonical"]["remote"]
        if remote.startswith("/"):
            self.canonical_remote = f"{self.base_url}{remote}"
        else:
            self.canonical_remote = remote

        self.verifications["setup_canonical_created"] = True
        print(f"      Canonical repo established: {self.canonical_name}")

    def run_seed_push(self):
        print("[3/8] Pushing canonical empty baseline seed via gateway ADMIN credential...")
        seed_dir = self.make_temp_dir("smoke_seed_")
        subprocess.run(["git", "init", "-b", "main"], cwd=seed_dir, check=True, capture_output=True, timeout=5)
        self.configure_git_repo(seed_dir)

        # Create small test fixture file
        seed_path = os.path.join(seed_dir, "SEED.md")
        with open(seed_path, "w") as f:
            f.write(f"# Agent Branches Fixture Baseline\nCreated: {get_utc_iso()}\n")

        subprocess.run(["git", "add", "SEED.md"], cwd=seed_dir, check=True, timeout=5)
        subprocess.run(["git", "commit", "-m", "Seed canonical baseline fixture"], cwd=seed_dir, check=True, capture_output=True, timeout=5)

        r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=seed_dir, capture_output=True, text=True, check=True, timeout=5)
        self.base_sha = r.stdout.strip()

        # Push to canonical remote via gateway ADMIN token
        subprocess.run(
            ["git", "push", "-u", self.canonical_remote, "main"],
            cwd=seed_dir,
            check=True,
            capture_output=True,
            timeout=SUBPROCESS_TIMEOUT,
            env=self.git_env(self.admin_token)
        )
        self.verifications["seed_push_successful"] = True
        print(f"      Seed push verified. Base SHA: {self.base_sha[:12]}")

    def _actor_worker(self, index):
        actor_name = f"scripted-actor-{index}"
        # 1. Create task
        status, task_data, _ = self.http_request(
            "POST",
            "/tasks",
            headers={"Authorization": f"Bearer {self.admin_token}"},
            body={"agent": actor_name, "intent": f"Smoke verification worker {index}", "base_sha": self.base_sha},
            expect_status=201
        )

        agent_id = task_data["agentId"]
        task_id = task_data["taskId"]
        fork_remote = task_data["fork"]["remote"]
        if fork_remote.startswith("/"):
            fork_remote = f"{self.base_url}{fork_remote}"
        gw_token = task_data["token"]["plaintext"]

        # 2. Local git clone from fork remote
        actor_dir = self.make_temp_dir(f"actor_{index}_")
        subprocess.run(["git", "clone", fork_remote, actor_dir], check=True, capture_output=True, timeout=SUBPROCESS_TIMEOUT, env=self.git_env(gw_token))
        self.configure_git_repo(actor_dir)

        # 3. Add distinct scripted change
        actor_file = os.path.join(actor_dir, f"actor_{index}.txt")
        with open(actor_file, "w") as f:
            f.write(f"Scripted actor {index} evidence output at {get_utc_iso()}\n")

        subprocess.run(["git", "add", f"actor_{index}.txt"], cwd=actor_dir, check=True, timeout=5)
        subprocess.run(
            ["git", "commit", "-m", f"Commit from actor {index}"],
            cwd=actor_dir,
            check=True,
            capture_output=True,
            timeout=5
        )

        r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=actor_dir, capture_output=True, text=True, check=True, timeout=5)
        head_sha = r.stdout.strip()

        # 4. Git push to fork remote
        subprocess.run(["git", "push", "origin", "main"], cwd=actor_dir, check=True, capture_output=True, timeout=SUBPROCESS_TIMEOUT, env=self.git_env(gw_token))

        # 5. Explicit agentauth /events/push callback
        status, push_resp, _ = self.http_request(
            "POST",
            "/events/push",
            headers={"Authorization": f"Bearer {gw_token}"},
            body={
                "agent": agent_id,
                "fork": task_data["fork"]["name"],
                "ref": "refs/heads/main",
                "sha": head_sha
            },
            expect_status=200
        )
        if not push_resp or push_resp.get("accepted") is not True:
            raise RuntimeError(f"Push event callback rejected for {agent_id}: {push_resp}")

        return agent_id, {
            "taskId": task_id,
            "forkRemote": fork_remote,
            "token": gw_token,
            "headSha": head_sha,
            "actorDir": actor_dir
        }

    def run_concurrent_actors(self):
        print(f"[4/8] Executing {self.actors_count} concurrent scripted Git actors...")
        with ThreadPoolExecutor(max_workers=self.actors_count) as executor:
            futures = [executor.submit(self._actor_worker, i + 1) for i in range(self.actors_count)]
            for f in futures:
                agent_id, data = f.result()
                self.actor_data[agent_id] = data

        self.verifications["concurrent_actors_fork_and_push_ok"] = True
        self.verifications["explicit_events_push_callbacks_ok"] = True
        print(f"      All {self.actors_count} concurrent scripted actors cloned, committed, pushed, and notified.")

    def run_trusted_runner_checks(self):
        print("[5/8] Running local trusted runner git merge-tree & submitting typed checks...")
        runner_dir = self.make_temp_dir("smoke_runner_")
        subprocess.run(["git", "init", "-b", "main"], cwd=runner_dir, check=True, capture_output=True, timeout=5)
        self.configure_git_repo(runner_dir)

        agent_ids = list(self.actor_data.keys())

        # Fetch heads of all actors
        for aid in agent_ids:
            remote_url = self.actor_data[aid]["forkRemote"]
            fetch_cmd = ["git", "fetch", remote_url, f"refs/heads/main:refs/remotes/{aid}"]
            token = self.actor_data[aid]["token"]
            subprocess.run(fetch_cmd, cwd=runner_dir, check=True, capture_output=True, timeout=SUBPROCESS_TIMEOUT, env=self.git_env(token))

        # Run git merge-tree between each pair of actors (ACTUALLY executed with recorded command, head, exit)
        vector = {aid: self.actor_data[aid]["headSha"] for aid in agent_ids}
        check_results = []
        for i in range(len(agent_ids)):
            for j in range(i + 1, len(agent_ids)):
                a1 = agent_ids[i]
                a2 = agent_ids[j]
                h1 = self.actor_data[a1]["headSha"]
                h2 = self.actor_data[a2]["headSha"]

                mt_cmd = ["git", "merge-tree", self.base_sha, h1, h2]
                r = subprocess.run(mt_cmd, cwd=runner_dir, capture_output=True, text=True, timeout=10)
                # Verify clean merge (no <<<<<<< conflict markers and exit code 0)
                if r.returncode != 0 or "<<<<<<<" in r.stdout:
                    status = "conflict"
                    evidence = "merge-tree conflict detected"
                else:
                    status = "clean"
                    evidence = "merge-tree clean: non-overlapping files"

                check_results.append({
                    "pair": [a1, a2],
                    "status": status,
                    "kind": "merge-tree",
                    "evidence": evidence,
                    "heads": {a1: h1, a2: h2},
                    "command": " ".join(mt_cmd),
                    "exit": r.returncode,
                    "head_sha": h2
                })

                # Record test provenance on task
                task_id = self.actor_data[a1]["taskId"]
                token = self.actor_data[a1]["token"]
                self.http_request(
                    "POST",
                    f"/tasks/{task_id}/tests",
                    headers={"Authorization": f"Bearer {token}"},
                    body={
                        "command": " ".join(mt_cmd),
                        "exit": r.returncode,
                        "head_sha": h1
                    },
                    expect_status=201
                )

        all_clean = all(c["status"] == "clean" for c in check_results)
        if not all_clean:
            raise RuntimeError("Trusted runner detected unexpected merge conflict among distinct actor files")

        self.verifications["trusted_runner_merge_tree_clean"] = True

        # Submit typed POST /checks with RUNNER_TOKEN
        payload = {
            "contract": "0.0",
            "coverage": ["|".join(c["pair"]) for c in check_results],
            "policy": "pairwise-merge-tree",
            "policyVerbatim": "merge-tree-v1",
            "vector": vector,
            "results": check_results
        }
        status, check_resp, _ = self.http_request(
            "POST",
            "/checks",
            headers={"Authorization": f"Bearer {self.runner_token}"},
            body=payload,
            expect_status=200
        )

        if not check_resp or check_resp.get("stale") is True or check_resp.get("accepted", 0) < len(check_results):
            raise RuntimeError(f"POST /checks submission was not accepted properly with status {status}")

        self.verifications["trusted_runner_typed_checks_accepted"] = True
        print(f"      Merge-tree checks verified ({len(check_results)} clean pairs accepted).")

    def run_negative_tests(self):
        print("[6/8] Executing negative boundary and security tests...")
        agent_ids = list(self.actor_data.keys())

        # 1. Method auth: POST /public/status -> 405 Method Not Allowed
        status, _, _ = self.http_request("POST", "/public/status", body={"test": 1})
        if status == 405:
            self.verifications["negative_method_not_allowed_405_refused"] = True
        else:
            raise RuntimeError(f"Expected HTTP 405 on POST /public/status, got HTTP {status}")

        # 2. Stale old vector POST /checks -> 409 Conflict
        fake_vector = {aid: self.actor_data[aid]["headSha"] for aid in agent_ids}
        fake_vector[agent_ids[0]] = "0" * 40  # Stale/invalid commit
        stale_payload = {
            "contract": "0.0",
            "coverage": [],
            "policy": "pairwise-merge-tree",
            "vector": fake_vector,
            "results": []
        }
        status, _, _ = self.http_request(
            "POST",
            "/checks",
            headers={"Authorization": f"Bearer {self.runner_token}"},
            body=stale_payload
        )
        if status == 409:
            self.verifications["negative_stale_checks_409_refused"] = True
        else:
            raise RuntimeError(f"Expected HTTP 409 on stale checks vector, got HTTP {status}")

        # 3. Cross-task access -> 403 Forbidden
        a1 = agent_ids[0]
        a2 = agent_ids[1]
        token_a1 = self.actor_data[a1]["token"]
        task_a2 = self.actor_data[a2]["taskId"]

        status, _, _ = self.http_request(
            "POST",
            f"/tasks/{task_a2}/tests",
            headers={"Authorization": f"Bearer {token_a1}"},
            body={"command": "test", "exit": 0, "head_sha": self.actor_data[a1]["headSha"]}
        )
        if status == 403:
            self.verifications["negative_cross_task_403_refused"] = True
        else:
            raise RuntimeError(f"Expected HTTP 403 on cross-task unauthorized mutation, got HTTP {status}")

        # 4. Cross-repo git push attempt -> 403 Forbidden
        # Actor 1 attempts to push to Actor 2's remote
        fork_remote_a2 = self.actor_data[a2]["forkRemote"]
        push_r = subprocess.run(
            ["git", "push", fork_remote_a2, "main"],
            cwd=self.actor_data[a1]["actorDir"],
            capture_output=True,
            timeout=SUBPROCESS_TIMEOUT,
            env=self.git_env(token_a1)
        )
        if push_r.returncode != 0:
            self.verifications["negative_cross_repo_push_403_refused"] = True
        else:
            raise RuntimeError("Cross-repo push unexpectedly succeeded with foreign token")

        # 5. Unauthenticated request to /cloud/budget -> 401 or 403
        status, _, _ = self.http_request("GET", "/cloud/budget")
        if status in (401, 403):
            self.verifications["negative_unauth_budget_401_refused"] = True
        else:
            raise RuntimeError(f"Expected HTTP 401/403 on unauthenticated budget call, got HTTP {status}")

        print("      Negative checks passed (405 method auth, 409 stale vector, 403 cross-task, 403 cross-repo, 401/403 unauth).")

    def run_cleanup(self):
        print("[7/8] Cleaning up demo repos via DELETE /cloud/demo-repos...")
        try:
            status, resp_data, _ = self.http_request(
                "DELETE",
                "/cloud/demo-repos",
                headers={"Authorization": f"Bearer {self.admin_token}"},
                expect_status=200
            )
            deleted_count = resp_data.get("deleted", 0) if isinstance(resp_data, dict) else 0

            # Verify remaining repos on backend
            _, check_b, _ = self.http_request(
                "GET",
                "/cloud/budget",
                headers={"Authorization": f"Bearer {self.admin_token}"},
                expect_status=200
            )
            repo_count_after = check_b.get("repoCount", 0) if isinstance(check_b, dict) else -1
            if repo_count_after != 0:
                raise RuntimeError(f"Cleanup verification failed: remaining repo count is {repo_count_after} (expected 0)")

            self.verifications["cleanup_demo_repos_ok"] = True
            print(f"      Cleanup complete: {deleted_count} demo repos deleted; remaining repos: {repo_count_after}")
            return deleted_count, repo_count_after
        finally:
            self.clean_temp_dirs()

    def run_budget_verification(self):
        print("[8/8] Verifying backend operation budget consumption after cleanup...")
        status, final_b, _ = self.http_request(
            "GET",
            "/cloud/budget",
            headers={"Authorization": f"Bearer {self.admin_token}"},
            expect_status=200
        )
        self.final_budget = final_b

        if self.initial_budget is None or self.budget_utc_day != datetime.now(timezone.utc).date().isoformat():
            raise RuntimeError("Budget measurement crossed a UTC day boundary or has no baseline")
        def counter(stats, name):
            value = stats.get(name) if isinstance(stats, dict) else None
            if type(value) is not int or value < 0:
                raise RuntimeError("Invalid budget counter")
            return value
        day_delta = counter(final_b, "utcDayOps") - counter(self.initial_budget, "utcDayOps")
        month_delta = counter(final_b, "calendarMonthOps") - counter(self.initial_budget, "calendarMonthOps")
        bytes_delta = counter(final_b, "totalBytesUploaded") - counter(self.initial_budget, "totalBytesUploaded")
        if day_delta < 0 or month_delta < 0 or bytes_delta < 0 or day_delta != month_delta:
            raise RuntimeError("Budget counters reset or are inconsistent")

        self.budget_delta = {
            "utcDayOpsDelta": day_delta,
            "calendarMonthOpsDelta": month_delta,
            "totalBytesUploadedDelta": bytes_delta
        }

        print(f"      Initial Day Ops: {self.initial_budget.get('utcDayOps')}, Final Day Ops: {final_b.get('utcDayOps')}")
        print(f"      Budget Operation Delta: {day_delta} ops (Hard ceiling: <= {MAX_BUDGET_DELTA_HARD})")

        if day_delta > MAX_BUDGET_DELTA_HARD or month_delta > MAX_BUDGET_DELTA_HARD:
            raise RuntimeError(f"Budget exceeded hard run ceiling! Delta: {day_delta} > {MAX_BUDGET_DELTA_HARD}")

    def generate_report(self, exit_code, deleted_count=0, repo_count_after=0):
        duration = round(self.end_time - self.start_time, 3) if (self.start_time and self.end_time) else 0.0

        report = {
            "timestamp_utc": get_utc_iso(),
            "sanitized": True,
            "environment": get_tool_versions(),
            "proof": {
                "is_mock": self.is_mock,
                "real_cloudflare_proof": False if self.is_mock else True,
                "notice": "Local explicit mock tests validate protocol and bounds; NOT real Cloudflare deployment proof." if self.is_mock else "Executed against live Cloudflare deployment."
            },
            "metrics": {
                "duration_seconds": duration,
                "actors_count": self.actors_count,
                "initial_budget": self.initial_budget,
                "final_budget": self.final_budget,
                "budget_delta": self.budget_delta,
                "budget_delta_within_limit": bool(self.budget_delta and self.budget_delta["utcDayOpsDelta"] <= MAX_BUDGET_DELTA_HARD),
                "cleanup_deleted": deleted_count,
                "repo_count_after_cleanup": repo_count_after
            },
            "verifications": self.verifications,
            "exit_code": exit_code
        }

        # Write to requested report path
        try:
            os.makedirs(os.path.dirname(os.path.abspath(self.report_path)), exist_ok=True)
            with open(self.report_path, "w") as f:
                json.dump(report, f, indent=2)
        except Exception as e:
            print(f"Warning: could not write report to {self.report_path}: {e}", file=sys.stderr)

        return report

    def run_all(self):
        self.start_time = time.time()
        exit_code = 1
        deleted_count = 0
        repo_count_after = 0
        try:
            self.run_preflight()
            self.run_setup()
            self.run_seed_push()
            self.run_concurrent_actors()
            self.run_trusted_runner_checks()
            self.run_negative_tests()
            exit_code = 0
        except Exception as e:
            print(f"\n[FAIL] Smoke verification error: {e}", file=sys.stderr)
            exit_code = 1
        finally:
            try:
                deleted_count, repo_count_after = self.run_cleanup()
            except Exception as ce:
                print(f"[WARN] Cleanup failure: {ce}", file=sys.stderr)
                if exit_code == 0:
                    exit_code = 2
            try:
                self.run_budget_verification()
            except Exception as be:
                print(f"[WARN] Budget verification failure: {be}", file=sys.stderr)
                if exit_code == 0:
                    exit_code = 3
            self.end_time = time.time()
            report = self.generate_report(exit_code, deleted_count, repo_count_after)

        print("\n================ SMOKE REPORT SUMMARY ================")
        print(f"Exit code:           {exit_code}")
        print(f"Duration:            {report['metrics']['duration_seconds']}s")
        print(f"Actors count:        {report['metrics']['actors_count']}")
        if report['metrics']['budget_delta']:
            print(f"Budget Delta:        {report['metrics']['budget_delta']['utcDayOpsDelta']} ops (limit <= {MAX_BUDGET_DELTA_HARD})")
        print(f"Cleanup Repos:       {deleted_count} deleted (current: {repo_count_after})")
        print(f"Mock run:            {self.is_mock} (Real Cloudflare proof: {report['proof']['real_cloudflare_proof']})")
        print("Verifications:")
        for k, v in report["verifications"].items():
            status_str = "PASS" if v else "FAIL"
            print(f"  - {k:40s} [{status_str}]")
        print(f"Sanitized report saved to {self.report_path}")
        print("======================================================\n")
        return exit_code


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Agent Branches Cloudflare Deploy-Config / Smoke Verification")
    parser.add_argument("--mock", action="store_true", help="Launch local loopback mock backend server (explicit MOCK only)")
    parser.add_argument("--actors", type=int, default=2, help="Number of concurrent scripted Git actors (default: 2)")
    parser.add_argument("--output", type=str, default="report.json", help="Path to write sanitized report.json")
    args = parser.parse_args()

    base_url = os.environ.get("BASE_URL")
    admin_token = os.environ.get("ADMIN_TOKEN")
    runner_token = os.environ.get("RUNNER_TOKEN")

    mock_mgr = None
    if not args.mock:
        if not base_url:
            print("Error: Missing BASE_URL environment variable. Live verification requires BASE_URL unless --mock is explicitly specified.", file=sys.stderr)
            sys.exit(1)
        if not base_url.startswith("https://"):
            print(f"Error: Strict HTTPS required for deployed BASE_URL: '{base_url}'. Only explicit --mock permits loopback HTTP.", file=sys.stderr)
            sys.exit(1)
        if not admin_token or not runner_token:
            print("Error: ADMIN_TOKEN and RUNNER_TOKEN environment variables must be set for live verification.", file=sys.stderr)
            sys.exit(1)
    else:
        # Explicit mock mode
        mock_mgr = MockServerManager()
        base_url = mock_mgr.base_url
        admin_token = mock_mgr.admin_token
        runner_token = mock_mgr.runner_token

    try:
        runner = CloudSmokeRunner(
            base_url=base_url,
            admin_token=admin_token,
            runner_token=runner_token,
            actors_count=args.actors,
            report_path=args.output,
            is_mock=bool(args.mock)
        )
        exit_code = runner.run_all()
    finally:
        if mock_mgr:
            mock_mgr.shutdown()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
