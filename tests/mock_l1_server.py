"""Offline Mock L1 Coordinator Server for Agent Branches testing.

Implements the exact HTTP routes:
- POST /tasks
- POST /events/push
- GET /status
- GET /tasks/<id>
- POST /warnings/<id>/ack
"""

import argparse
import datetime
import http.server
import json
import re
import socketserver
import sys
import threading
import time
import urllib.parse
from typing import Any, Dict, List, Optional, Set, Tuple


class MockCoordinatorState:
    """Thread-safe in-memory state for mock L1 coordinator."""

    def __init__(self, expected_admin_token: Optional[str] = None):
        self.lock = threading.Lock()
        self.seq = 0
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self.agents: Dict[str, Dict[str, Any]] = {}
        self.warnings: Dict[str, Dict[str, Any]] = {}
        self.seen_pushes: Set[Tuple[str, str]] = set()
        self.radar_log: List[Dict[str, Any]] = []
        self.canonical_name = "agent-branches-canonical"
        self.canonical_remote = "https://git.cloudflare.local/canonical.git"
        self.expected_admin_token = expected_admin_token

    def create_task(self, data: Dict[str, Any]) -> Dict[str, Any]:
        with self.lock:
            self.seq += 1
            seq_str = f"{self.seq:04d}"
            agent_raw = data.get("agent") or "alpha"
            slug = re.sub(r"[^a-z0-9._-]+", "-", agent_raw.lower()).strip("-") or "alpha"
            agent_id = f"{slug}-{seq_str}"
            task_id = f"task-{seq_str}"
            repo = data.get("repo", "https://github.com/agent-branches/repo.git")
            base_sha = data.get("base_sha") or "0000000000000000000000000000000000000000"
            branch = data.get("branch") or "main"
            intent = data.get("intent", "")
            fork_url = f"https://git.cloudflare.local/forks/{agent_id}.git"
            ref = f"refs/heads/{branch}"
            now = datetime.datetime.now(datetime.timezone.utc).isoformat()

            record = {
                "id": task_id,
                "taskId": task_id,
                "task_id": task_id,
                "agentId": agent_id,
                "agent_id": agent_id,
                "repo": repo,
                "base_sha": base_sha,
                "branch": branch,
                "ref": ref,
                "intent": intent,
                "forkUrl": fork_url,
                "fork_url": fork_url,
                "fork": {
                    "name": f"{self.canonical_name}-{agent_id}",
                    "remote": fork_url,
                },
                "token": f"mock-token-{seq_str}",
                "head": base_sha,
                "head_sha": base_sha,
                "pushes": 0,
                "status": "active",
                "files_changed": [],
                "test_provenance": None,
                "createdAt": now,
                "created_at": now,
                "last_push_at": None,
            }

            self.tasks[task_id] = record
            self.agents[agent_id] = record
            return record

    def record_push(self, data: Dict[str, Any]) -> Dict[str, Any]:
        with self.lock:
            agent_id = data.get("agentId") or data.get("agent")
            head_sha = data.get("head_sha") or data.get("sha")

            if not agent_id or not head_sha:
                raise ValueError("agentId (or agent) and head_sha (or sha) are required")

            # Enforce distinct agentId vs taskId: reject if client sends taskId directly
            if agent_id in self.tasks and agent_id not in self.agents:
                raise KeyError(
                    f"unknown agent: {agent_id} (received taskId instead of agentId)"
                )

            task = self.agents.get(agent_id)
            if not task:
                raise KeyError(f"unknown agent: {agent_id}")

            canonical_task_id = task["task_id"]
            dedup_key = (agent_id, head_sha)

            if dedup_key in self.seen_pushes or task.get("head_sha") == head_sha:
                return {
                    "accepted": True,
                    "deduped": True,
                    "agentId": agent_id,
                    "agent_id": agent_id,
                    "task_id": canonical_task_id,
                    "head_sha": head_sha,
                    "heads": {t["task_id"]: t["head_sha"] for t in self.tasks.values()},
                    "new_warnings": [],
                    "invalidated_warnings": [],
                    "radar_checks": 0,
                }

            now = datetime.datetime.now(datetime.timezone.utc).isoformat()
            self.seen_pushes.add(dedup_key)
            task["head"] = head_sha
            task["head_sha"] = head_sha
            task["pushes"] += 1
            task["last_push_at"] = now

            if "base_sha" in data and data["base_sha"]:
                task["base_sha"] = data["base_sha"]
            if "intent" in data and data["intent"]:
                task["intent"] = data["intent"]
            elif "intent_update" in data and data["intent_update"]:
                task["intent"] = data["intent_update"]
            if "test_provenance" in data and data["test_provenance"]:
                task["test_provenance"] = data["test_provenance"]

            raw_files = data.get("files_changed")
            files_changed: List[str] = []
            if isinstance(raw_files, list):
                files_changed = [str(f) for f in raw_files]
            elif isinstance(raw_files, str):
                files_changed = [f.strip() for f in raw_files.split(",") if f.strip()]
            if files_changed:
                task["files_changed"] = files_changed

            # Invalidate older active warnings for this task
            invalidated: List[str] = []
            for w in self.warnings.values():
                if w.get("status") == "active" and canonical_task_id in w.get("pair", []):
                    w["status"] = "invalidated"
                    w["invalidated_at"] = now
                    invalidated.append(w["warning_id"])

            # Simulate pairwise radar merge-tree check
            new_warnings: List[Dict[str, Any]] = []
            other_tasks = [t for t in self.tasks.values() if t["task_id"] != canonical_task_id]
            radar_checks = len(other_tasks)

            for other in other_tasks:
                other_id = other["task_id"]
                other_files = set(other.get("files_changed", []))
                cur_files = set(files_changed)
                overlap = list(cur_files & other_files)

                # Trigger conflict if common files are modified or explicit test marker
                has_conflict = bool(overlap) or "conflict" in str(task.get("intent", "")).lower()

                if has_conflict:
                    warn_idx = len(self.warnings) + 1
                    warn_id = f"warn-{warn_idx:03d}"
                    conflicting = overlap if overlap else ["src/auth.ts"]
                    kind = "test" if "fail" in str(task.get("test_provenance", "")).lower() else "textual"
                    warn_record = {
                        "warning_id": warn_id,
                        "id": warn_id,
                        "pair": [canonical_task_id, other_id],
                        "heads": {
                            canonical_task_id: head_sha,
                            other_id: other.get("head_sha", "unknown"),
                        },
                        "kind": kind,
                        "evidence": {
                            "conflicting_files": conflicting,
                            "conflict_type": "content_conflict",
                            "details": f"Trial merge detected conflict between {canonical_task_id} and {other_id}",
                        },
                        "status": "active",
                        "created_at_ms": int(time.time() * 1000),
                        "created_at": now,
                        "invalidated_at": None,
                    }
                    self.warnings[warn_id] = warn_record
                    new_warnings.append(warn_record)
                    self.radar_log.append({
                        "at": now,
                        "pair": [canonical_task_id, other_id],
                        "reason": f"conflict in {conflicting}",
                    })

            return {
                "accepted": True,
                "deduped": False,
                "agentId": agent_id,
                "agent_id": agent_id,
                "task_id": canonical_task_id,
                "head_sha": head_sha,
                "heads": {t["task_id"]: t["head_sha"] for t in self.tasks.values()},
                "new_warnings": new_warnings,
                "invalidated_warnings": invalidated,
                "radar_checks": radar_checks,
            }

    def get_status(self) -> Dict[str, Any]:
        with self.lock:
            active_warnings = [w for w in self.warnings.values() if w.get("status") == "active"]
            return {
                "canonical": {
                    "name": self.canonical_name,
                    "remote": self.canonical_remote,
                },
                "tasks": list(self.tasks.values()),
                "heads": {t["task_id"]: t["head_sha"] for t in self.tasks.values() if t.get("head_sha")},
                "warnings": active_warnings,
                "radar_log": self.radar_log[-20:],
            }

    def get_task(self, task_id: str) -> Dict[str, Any]:
        with self.lock:
            task = self.tasks.get(task_id) or self.agents.get(task_id)
            if not task:
                raise KeyError(f"unknown task: {task_id}")
            res = dict(task)
            canonical_id = task["task_id"]
            res["warnings"] = [
                w for w in self.warnings.values()
                if canonical_id in w.get("pair", []) and w.get("status") == "active"
            ]
            return res

    def ack_warning(self, warning_id: str, task_id: Optional[str], action: str) -> Dict[str, Any]:
        with self.lock:
            warning = self.warnings.get(warning_id)
            if not warning:
                raise KeyError(f"unknown warning: {warning_id}")

            now = datetime.datetime.now(datetime.timezone.utc).isoformat()
            warning["status"] = "acknowledged"
            warning["acknowledged"] = True
            warning["acknowledged_at"] = now
            warning["action"] = action
            warning["ack_task_id"] = task_id

            return {
                "acknowledged": True,
                "warning_id": warning_id,
                "task_id": task_id,
                "action": action,
                "status": "acknowledged",
                "acknowledged_at": now,
            }


class MockL1Handler(http.server.BaseHTTPRequestHandler):
    """HTTP Request Handler implementing L1 Coordinator routes."""

    # Silence default console logging
    def log_message(self, format: str, *args: Any) -> None:
        pass

    @property
    def state(self) -> MockCoordinatorState:
        return self.server.state  # type: ignore

    def _send_json(self, status: int, payload: Any) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> Dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length <= 0:
            return {}
        raw = self.rfile.read(content_length)
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            raise ValueError("request body must be valid JSON")

    def do_POST(self) -> None:
        path = urllib.parse.urlparse(self.path).path

        # POST /tasks
        if path == "/tasks":
            # Admin token auth check if configured
            if self.state.expected_admin_token is not None:
                auth_header = self.headers.get("Authorization", "")
                expected = f"Bearer {self.state.expected_admin_token}"
                if auth_header != expected:
                    self._send_json(401, {"error": "unauthorized: missing or invalid bearer token"})
                    return

            try:
                body = self._read_json()
            except ValueError as exc:
                self._send_json(400, {"error": str(exc)})
                return
            created = self.state.create_task(body)
            self._send_json(201, created)
            return

        # POST /events/push
        if path == "/events/push":
            try:
                body = self._read_json()
            except ValueError as exc:
                self._send_json(400, {"error": str(exc)})
                return
            try:
                res = self.state.record_push(body)
                self._send_json(200, res)
            except KeyError as exc:
                self._send_json(404, {"error": str(exc).strip("'")})
            except ValueError as exc:
                self._send_json(400, {"error": str(exc)})
            return

        # POST /warnings/<id>/ack
        ack_match = re.match(r"^/warnings/([^/]+)/ack$", path)
        if ack_match:
            warning_id = urllib.parse.unquote(ack_match.group(1))
            try:
                body = self._read_json()
            except ValueError as exc:
                self._send_json(400, {"error": str(exc)})
                return
            task_id = body.get("task_id")
            action = body.get("action", "acknowledged")
            try:
                res = self.state.ack_warning(warning_id=warning_id, task_id=task_id, action=action)
                self._send_json(200, res)
            except KeyError as exc:
                self._send_json(404, {"error": str(exc).strip("'")})
            return

        self._send_json(404, {"error": f"no route for POST {path}"})

    def do_GET(self) -> None:
        path = urllib.parse.urlparse(self.path).path

        # GET /status
        if path == "/status":
            self._send_json(200, self.state.get_status())
            return

        # GET /tasks/<id>
        task_match = re.match(r"^/tasks/([^/]+)$", path)
        if task_match:
            task_id = urllib.parse.unquote(task_match.group(1))
            try:
                res = self.state.get_task(task_id)
                self._send_json(200, res)
            except KeyError as exc:
                self._send_json(404, {"error": str(exc).strip("'")})
            return

        self._send_json(404, {"error": f"no route for GET {path}"})


class MockL1Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    """Threaded HTTP server holding coordinator state."""

    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, server_address: Tuple[str, int], state: Optional[MockCoordinatorState] = None):
        super().__init__(server_address, MockL1Handler)
        self.state = state or MockCoordinatorState()


def start_mock_l1_server(
    host: str = "127.0.0.1",
    port: int = 0,
    expected_admin_token: Optional[str] = None,
) -> Tuple[MockL1Server, threading.Thread, str, MockCoordinatorState]:
    """Start mock L1 coordinator on host and ephemeral or specified port.

    Returns:
        (server, thread, server_url, state)
    """
    state = MockCoordinatorState(expected_admin_token=expected_admin_token)
    server = MockL1Server((host, port), state=state)
    actual_port = server.server_address[1]
    server_url = f"http://{host}:{actual_port}"

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, server_url, state


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Mock L1 Coordinator Server")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8787, help="Bind port (default: 8787)")
    parser.add_argument("--admin-token", help="Require admin bearer token for task creation")
    args = parser.parse_args()

    server, thread, url, _ = start_mock_l1_server(
        host=args.host, port=args.port, expected_admin_token=args.admin_token
    )
    print(f"Mock L1 Coordinator Server listening at {url}")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down server...")
        server.shutdown()
        server.server_close()
        sys.exit(0)


if __name__ == "__main__":
    main()
