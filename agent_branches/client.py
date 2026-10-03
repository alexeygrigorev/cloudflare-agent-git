"""Agent Branches L2 Client implementation using standard library urllib."""

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Union


class AgentBranchesError(Exception):
    """Base exception for all agent-branches client errors."""
    pass


class AgentBranchesConnectionError(AgentBranchesError):
    """Raised when the client cannot connect to the L1 coordinator server."""
    pass


class AgentBranchesAPIError(AgentBranchesError):
    """Raised when the L1 coordinator returns an HTTP error response."""

    def __init__(self, status_code: int, message: str, payload: Optional[Any] = None):
        super().__init__(f"HTTP {status_code}: {message}")
        self.status_code = status_code
        self.message = message
        self.payload = payload


class AgentBranchesClient:
    """Robust, lightweight client for Cloudflare Agent Branches L1 Coordinator."""

    DEFAULT_SERVER = "http://127.0.0.1:8787"

    def __init__(self, server_url: Optional[str] = None, timeout: float = 10.0):
        url = server_url or os.environ.get("AGENT_BRANCHES_SERVER") or os.environ.get("COORDINATOR_URL") or self.DEFAULT_SERVER
        self.server_url = url.rstrip("/")
        self.timeout = timeout

    def _request(
        self,
        method: str,
        path: str,
        body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Perform an HTTP request and parse JSON response."""
        full_url = f"{self.server_url}{path}"
        data = None
        headers = {
            "Accept": "application/json",
            "User-Agent": "agent-branches-l2-client/1.0",
        }

        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json; charset=utf-8"

        req = urllib.request.Request(full_url, data=data, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                resp_bytes = response.read()
                if not resp_bytes:
                    return {}
                return json.loads(resp_bytes.decode("utf-8"))
        except urllib.error.HTTPError as exc:
            err_body = exc.read()
            err_msg = exc.reason
            payload = None
            if err_body:
                try:
                    payload = json.loads(err_body.decode("utf-8"))
                    if isinstance(payload, dict) and "error" in payload:
                        err_msg = payload["error"]
                except Exception:
                    err_msg = err_body.decode("utf-8", errors="replace")
            raise AgentBranchesAPIError(exc.code, str(err_msg), payload) from exc
        except (urllib.error.URLError, ConnectionError, OSError) as exc:
            reason = getattr(exc, "reason", str(exc))
            raise AgentBranchesConnectionError(
                f"Failed to connect to coordinator at {self.server_url}: {reason}"
            ) from exc

    def create_task(
        self,
        repo: str,
        base_sha: str,
        intent: str,
        branch: str,
        agent: Optional[str] = None,
        ttl_seconds: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Register a new task (POST /tasks).

        Returns:
            Dictionary containing task ID, fork URL, branch, token, etc.
        """
        payload: Dict[str, Any] = {
            "repo": repo,
            "base_sha": base_sha,
            "intent": intent,
            "branch": branch,
        }
        if agent:
            payload["agent"] = agent
        if ttl_seconds is not None:
            payload["ttlSeconds"] = ttl_seconds

        return self._request("POST", "/tasks", payload)

    def push(
        self,
        task_id: str,
        head_sha: str,
        base_sha: Optional[str] = None,
        files_changed: Optional[Union[List[str], str]] = None,
        intent: Optional[str] = None,
        test_provenance: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Register a WIP commit push (POST /events/push).

        Sends:
            task_id, head_sha, base_sha, files_changed, intent, test_provenance.
        """
        # Normalize files_changed to list of non-empty strings
        normalized_files: Optional[List[str]] = None
        if files_changed is not None:
            if isinstance(files_changed, str):
                normalized_files = [f.strip() for f in files_changed.split(",") if f.strip()]
            else:
                normalized_files = list(files_changed)

        payload: Dict[str, Any] = {
            "task_id": task_id,
            "agent": task_id,
            "head_sha": head_sha,
            "sha": head_sha,
        }
        if base_sha:
            payload["base_sha"] = base_sha
        if normalized_files is not None:
            payload["files_changed"] = normalized_files
        if intent:
            payload["intent"] = intent
            payload["intent_update"] = intent
        if test_provenance:
            payload["test_provenance"] = test_provenance

        return self._request("POST", "/events/push", payload)

    def get_status(self) -> Dict[str, Any]:
        """Fetch current global coordinator and radar status (GET /status)."""
        return self._request("GET", "/status")

    def get_task(self, task_id: str) -> Dict[str, Any]:
        """Fetch task status and active warnings for a specific task (GET /tasks/:id)."""
        encoded_id = urllib.parse.quote(task_id, safe="")
        return self._request("GET", f"/tasks/{encoded_id}")

    def ack_warning(
        self,
        warning_id: str,
        task_id: Optional[str] = None,
        action: str = "acknowledged",
    ) -> Dict[str, Any]:
        """Acknowledge a radar warning (POST /warnings/:id/ack)."""
        encoded_id = urllib.parse.quote(warning_id, safe="")
        payload: Dict[str, Any] = {"action": action}
        if task_id:
            payload["task_id"] = task_id

        return self._request("POST", f"/warnings/{encoded_id}/ack", payload)

    # MCP-compatible aliases (CONTRACT-L2-L3 Section 2.2)
    def branches_create_task(
        self, repo: str, base_sha: str, intent: str, branch: str
    ) -> Dict[str, Any]:
        return self.create_task(repo=repo, base_sha=base_sha, intent=intent, branch=branch)

    def branches_push_wip(
        self,
        task_id: str,
        head_sha: str,
        intent_update: Optional[str] = None,
        test_provenance: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self.push(
            task_id=task_id,
            head_sha=head_sha,
            intent=intent_update,
            test_provenance=test_provenance,
        )

    def branches_get_status(self, task_id: Optional[str] = None) -> Dict[str, Any]:
        if task_id:
            return self.get_task(task_id)
        return self.get_status()

    def branches_ack_warning(
        self, task_id: str, warning_id: str, action: str = "rebased_locally"
    ) -> Dict[str, Any]:
        return self.ack_warning(warning_id=warning_id, task_id=task_id, action=action)
