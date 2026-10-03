"""Offline Mock L1 Coordinator Server implementing CONTRACT v0.1 specification.

Endpoints:
- POST /tasks -> registers task, assigns agentId, returns fork info + token.
- POST /events/push -> records agent push, updates coordinator head vector {agentId: sha}.
- POST /checks -> CONTRACT v0.1 check evaluation route with stale vector check.
- GET /status -> returns global coordinator status with heads, pairs, warnings.
- GET /tasks/<id> -> returns task details and active warnings.
- POST /warnings/<id>/ack -> marks warning acknowledged.
"""

from __future__ import annotations

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
    """Thread-safe in-memory state for mock L1 coordinator implementing CONTRACT v0.1."""

    def __init__(
        self,
        expected_admin_token: Optional[str] = None,
        expected_runner_token: Optional[str] = None,
    ):
        self.lock = threading.Lock()
        self.seq = 0
        self.warn_seq = 0
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self.agents: Dict[str, Dict[str, Any]] = {}
        self.heads: Dict[str, str] = {}  # agentId -> head_sha
        self.pair_checks: Dict[str, Dict[str, Any]] = {}  # pair_key -> check record
        self.warnings: Dict[str, Dict[str, Any]] = {}  # id -> warning record
        self.seen_pushes: Set[Tuple[str, str]] = set()
        self.radar_log: List[Dict[str, Any]] = []
        self.canonical_name = "agent-branches-canonical"
        self.canonical_remote = "https://git.cloudflare.local/canonical.git"
        self.expected_admin_token = expected_admin_token
        self.expected_runner_token = expected_runner_token

    def reset(self) -> None:
        """Clear all in-memory state for fresh test isolation."""
        with self.lock:
            self.seq = 0
            self.warn_seq = 0
            self.tasks.clear()
            self.agents.clear()
            self.heads.clear()
            self.pair_checks.clear()
            self.warnings.clear()
            self.seen_pushes.clear()
            self.radar_log.clear()

    def _pair_key(self, pair: List[str]) -> str:
        s = sorted(str(p) for p in pair)
        return f"{s[0]}:{s[1]}"

    def create_task(self, data: Dict[str, Any]) -> Dict[str, Any]:
        with self.lock:
            self.seq += 1
            seq_str = f"{self.seq:04d}"
            agent_raw = data.get("agent") or f"agent-{seq_str}"
            slug = re.sub(r"[^a-z0-9._-]+", "-", agent_raw.lower()).strip("-") or "agent"
            agent_id = f"{slug}-{seq_str}" if not slug.endswith(seq_str) else slug
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
                "createdAt": now,
                "created_at": now,
                "last_push_at": None,
                "files_changed": [],
                "test_provenance": None,
            }

            self.tasks[task_id] = record
            self.agents[agent_id] = record
            self.heads[agent_id] = base_sha
            return record

    def record_push(self, data: Dict[str, Any]) -> Dict[str, Any]:
        with self.lock:
            agent_id = data.get("agentId") or data.get("agent")
            head_sha = data.get("head_sha") or data.get("sha")

            if not agent_id or not head_sha:
                raise ValueError("agentId and head_sha are required")

            task = self.agents.get(agent_id)
            if not task:
                task = self.tasks.get(agent_id)
                if task:
                    agent_id = task["agentId"]
                else:
                    raise KeyError(f"unknown agent: {agent_id}")

            canonical_task_id = task["task_id"]
            now = datetime.datetime.now(datetime.timezone.utc).isoformat()
            self.seen_pushes.add((agent_id, head_sha))
            task["head"] = head_sha
            task["head_sha"] = head_sha
            task["pushes"] += 1
            task["last_push_at"] = now
            self.heads[agent_id] = head_sha

            if "base_sha" in data and data["base_sha"]:
                task["base_sha"] = data["base_sha"]
            if "intent" in data and data["intent"]:
                task["intent"] = data["intent"]
            elif "intent_update" in data and data["intent_update"]:
                task["intent"] = data["intent_update"]
            if "test_provenance" in data and data["test_provenance"]:
                task["test_provenance"] = data["test_provenance"]

            raw_files = data.get("files_changed")
            if isinstance(raw_files, list):
                task["files_changed"] = [str(f) for f in raw_files]
            elif isinstance(raw_files, str):
                task["files_changed"] = [f.strip() for f in raw_files.split(",") if f.strip()]

            return {
                "accepted": True,
                "deduped": False,
                "agentId": agent_id,
                "agent_id": agent_id,
                "task_id": canonical_task_id,
                "head_sha": head_sha,
                "heads": dict(self.heads),
            }

    def process_checks(self, payload: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
        with self.lock:
            # 1. Schema validation
            if not isinstance(payload, dict):
                return 400, {"error": "payload must be a JSON object"}
            contract = str(payload.get("contract", ""))
            if not contract.startswith("0.1"):
                return 400, {"error": f"unsupported contract version: '{contract}'; requires '0.1'"}
            vector = payload.get("vector")
            if not isinstance(vector, dict) or not vector:
                return 400, {"error": "vector must be a non-empty dictionary mapping agentId -> sha"}
            results = payload.get("results")
            if not isinstance(results, list):
                return 400, {"error": "results must be a list"}

            # 2. Stale Vector Check:
            # If payload vector does not match coordinator heads, reject with HTTP 409
            stale = False
            for agent_id, expected_sha in vector.items():
                if self.heads.get(agent_id) != expected_sha:
                    stale = True
                    break

            if stale:
                return 409, {
                    "error": "stale_vector",
                    "message": "Head vector has advanced",
                    "expected": dict(self.heads),
                    "received": vector,
                }

            # 3. Process check results
            now = datetime.datetime.now(datetime.timezone.utc).isoformat()
            created_warnings: List[Dict[str, Any]] = []

            for item in results:
                raw_pair = item.get("pair")
                if not isinstance(raw_pair, (list, tuple)) or len(raw_pair) != 2:
                    return 400, {"error": "each result requires pair: [agentA, agentB]"}
                pair = [str(raw_pair[0]), str(raw_pair[1])]
                pair_key = self._pair_key(pair)
                status = str(item.get("status", "")).lower()
                kind = item.get("kind")
                evidence = item.get("evidence") or {}

                rec_vector = {
                    pair[0]: self.heads.get(pair[0], ""),
                    pair[1]: self.heads.get(pair[1], ""),
                }

                check_rec = {
                    "key": pair_key,
                    "pair": pair,
                    "status": status,
                    "kind": kind,
                    "evidence": evidence,
                    "vector": rec_vector,
                    "at": now,
                }
                self.pair_checks[pair_key] = check_rec
                self.radar_log.append({
                    "at": now,
                    "pair": pair,
                    "heads": rec_vector,
                    "status": status,
                    "kind": kind,
                    "evidence": evidence,
                })

                if status == "conflict":
                    existing = any(
                        w.get("status") == "active"
                        and set(w.get("pair", [])) == set(pair)
                        and w.get("heads") == rec_vector
                        for w in self.warnings.values()
                    )
                    if not existing:
                        self.warn_seq += 1
                        warn_id = f"warn-{self.warn_seq:03d}"
                        warn_rec = {
                            "id": warn_id,
                            "warning_id": warn_id,
                            "pair": pair,
                            "heads": rec_vector,
                            "reason": kind or "conflict",
                            "kind": kind,
                            "status": "active",
                            "evidence": evidence,
                            "created_at": now,
                            "invalidated_at": None,
                            "acks": [],
                        }
                        self.warnings[warn_id] = warn_rec
                        created_warnings.append(warn_rec)
                elif status == "clean":
                    # Invalidate active warnings for this pair
                    for w in self.warnings.values():
                        if w.get("status") == "active" and set(w.get("pair", [])) == set(pair):
                            w["status"] = "invalidated"
                            w["invalidated_at"] = now
                            w["resolved_by"] = "clean check"
                elif status == "unknown":
                    # Status is preserved strictly as unknown; never safe, never creates warnings
                    pass

            return 200, {
                "accepted": len(results),
                "pairs": self.get_pair_views(),
                "createdWarnings": created_warnings,
            }

    def get_pair_views(self) -> List[Dict[str, Any]]:
        agents = sorted(self.heads.keys())
        views: List[Dict[str, Any]] = []
        for i in range(len(agents)):
            for j in range(i + 1, len(agents)):
                a, b = agents[i], agents[j]
                pair = [a, b]
                pair_key = self._pair_key(pair)
                cur_heads = {a: self.heads[a], b: self.heads[b]}
                stored = self.pair_checks.get(pair_key)
                fresh = (
                    stored is not None
                    and stored["vector"].get(a) == cur_heads[a]
                    and stored["vector"].get(b) == cur_heads[b]
                )
                active_warn_ids = [
                    w["id"]
                    for w in self.warnings.values()
                    if w.get("status") == "active" and set(w.get("pair", [])) == {a, b}
                ]
                views.append({
                    "pair": pair,
                    "heads": cur_heads,
                    "status": stored["status"] if fresh else "not_checked",
                    "kind": stored.get("kind") if fresh else None,
                    "evidence": stored.get("evidence") if fresh else None,
                    "checkedAt": stored.get("at") if stored else None,
                    "stale": (stored is not None and not fresh),
                    "activeWarningIds": active_warn_ids,
                })
        return views

    def get_status(self) -> Dict[str, Any]:
        with self.lock:
            active_warnings = [w for w in self.warnings.values() if w.get("status") == "active"]
            return {
                "canonical": {
                    "name": self.canonical_name,
                    "remote": self.canonical_remote,
                },
                "agents": list(self.agents.values()),
                "tasks": list(self.tasks.values()),
                "heads": dict(self.heads),
                "pairs": self.get_pair_views(),
                "pair_checks": dict(self.pair_checks),
                "warnings": active_warnings,
                "all_warnings": list(self.warnings.values()),
                "radar_log": self.radar_log[-20:],
            }

    def get_task(self, task_id: str) -> Dict[str, Any]:
        with self.lock:
            task = self.tasks.get(task_id) or self.agents.get(task_id)
            if not task:
                raise KeyError(f"unknown task: {task_id}")
            res = dict(task)
            agent_id = task["agentId"]
            res["warnings"] = [
                w for w in self.warnings.values()
                if agent_id in w.get("pair", []) and w.get("status") == "active"
            ]
            return res

    def ack_warning(
        self,
        warning_id: str,
        task_id: Optional[str] = None,
        agent: Optional[str] = None,
        action: str = "acknowledged",
    ) -> Dict[str, Any]:
        with self.lock:
            warning = self.warnings.get(warning_id)
            if not warning:
                raise KeyError(f"unknown warning: {warning_id}")

            now = datetime.datetime.now(datetime.timezone.utc).isoformat()
            warning["status"] = "acknowledged"
            warning["acknowledged"] = True
            warning["acknowledged_at"] = now
            warning["action"] = action
            warning["acks"].append({
                "agent": agent or task_id or "unknown",
                "action": action,
                "at": now,
            })

            return {
                "acknowledged": True,
                "warning_id": warning_id,
                "status": "acknowledged",
                "action": action,
                "warning": warning,
            }


class MockL1Handler(http.server.BaseHTTPRequestHandler):
    """HTTP request handler implementing CONTRACT v0.1 coordinator routes."""

    def log_message(self, format: str, *args: Any) -> None:
        pass  # Suppress default console logs

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
            if self.state.expected_admin_token is not None:
                auth = self.headers.get("Authorization", "")
                if auth != f"Bearer {self.state.expected_admin_token}":
                    self._send_json(401, {"error": "unauthorized: invalid admin token"})
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

        # POST /checks (CONTRACT v0.1)
        if path == "/checks":
            if self.state.expected_runner_token is not None:
                auth = self.headers.get("Authorization", "")
                if auth != f"Bearer {self.state.expected_runner_token}":
                    self._send_json(401, {"error": "unauthorized: invalid runner token"})
                    return
            try:
                body = self._read_json()
            except ValueError as exc:
                self._send_json(400, {"error": str(exc)})
                return
            status_code, resp_body = self.state.process_checks(body)
            self._send_json(status_code, resp_body)
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
            agent = body.get("agent")
            action = body.get("action", "acknowledged")
            try:
                res = self.state.ack_warning(
                    warning_id=warning_id,
                    task_id=task_id,
                    agent=agent,
                    action=action,
                )
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
    """Threaded HTTP server holding mock L1 coordinator state."""

    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self,
        server_address: Tuple[str, int],
        state: Optional[MockCoordinatorState] = None,
    ):
        super().__init__(server_address, MockL1Handler)
        self.state = state or MockCoordinatorState()


def start_mock_l1_server(
    host: str = "127.0.0.1",
    port: int = 0,
    expected_admin_token: Optional[str] = None,
    expected_runner_token: Optional[str] = None,
) -> Tuple[MockL1Server, threading.Thread, str, MockCoordinatorState]:
    """Start mock L1 coordinator on ephemeral or specified port.

    Returns:
        (server, thread, server_url, state)
    """
    state = MockCoordinatorState(
        expected_admin_token=expected_admin_token,
        expected_runner_token=expected_runner_token,
    )
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
    args = parser.parse_args()

    server, _, url, _ = start_mock_l1_server(host=args.host, port=args.port)
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
