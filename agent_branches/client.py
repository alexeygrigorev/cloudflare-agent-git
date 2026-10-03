"""Agent Branches L2 Client implementation using standard library urllib."""

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Union

CONTRACT_VERSION = "0.1.2"


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


class StaleVectorError(AgentBranchesAPIError):
    """Raised when the L1 coordinator returns HTTP 409 Conflict due to a stale head vector."""
    pass


class AgentBranchesClient:
    """Robust, lightweight client for Cloudflare Agent Branches L1 Coordinator."""

    DEFAULT_SERVER = "http://127.0.0.1:8787"

    def __init__(
        self,
        server_url: Optional[str] = None,
        timeout: float = 10.0,
        admin_token: Optional[str] = None,
    ):
        url = (
            server_url
            or os.environ.get("AGENT_BRANCHES_SERVER")
            or os.environ.get("COORDINATOR_URL")
            or self.DEFAULT_SERVER
        )
        self.server_url = url.rstrip("/")
        self.timeout = timeout
        self.admin_token = admin_token or os.environ.get("ADMIN_TOKEN")
        self.task_to_agent: Dict[str, str] = {}
        self.known_tasks: Dict[str, Dict[str, Any]] = {}

    def _request(
        self,
        method: str,
        path: str,
        body: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Perform an HTTP request and parse JSON response."""
        full_url = f"{self.server_url}{path}"
        data = None
        req_headers = {
            "Accept": "application/json",
            "User-Agent": "agent-branches-l2-client/1.0",
        }
        if headers:
            req_headers.update(headers)

        if body is not None:
            data = json.dumps(body).encode("utf-8")
            req_headers["Content-Type"] = "application/json; charset=utf-8"

        req = urllib.request.Request(full_url, data=data, headers=req_headers, method=method)

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
                    if isinstance(payload, dict):
                        err_msg = payload.get("message") or payload.get("error") or err_msg
                except Exception:
                    err_msg = err_body.decode("utf-8", errors="replace")
            if exc.code == 409:
                raise StaleVectorError(exc.code, str(err_msg), payload) from exc
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
        admin_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Register a new task (POST /tasks).

        Supports --admin-token (or $ADMIN_TOKEN) via Authorization: Bearer <token>.
        Returns dictionary containing distinct task ID, agent ID, fork URL, branch, token, etc.
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

        req_headers: Dict[str, str] = {}
        token = admin_token or self.admin_token or os.environ.get("ADMIN_TOKEN")
        if token:
            req_headers["Authorization"] = f"Bearer {token}"

        res = self._request("POST", "/tasks", payload, headers=req_headers)

        task_id = res.get("taskId") or res.get("id") or res.get("task_id")
        agent_id = res.get("agentId") or res.get("agent_id") or res.get("agent")

        # Normalize keys in returned dict
        if task_id:
            res["taskId"] = task_id
            res["task_id"] = task_id
        if agent_id:
            res["agentId"] = agent_id
            res["agent_id"] = agent_id

        if task_id and agent_id:
            self.task_to_agent[task_id] = agent_id
            self.known_tasks[task_id] = res

        return res

    def get_task(self, task_id: str) -> Dict[str, Any]:
        """Fetch task status and active warnings for a specific task (GET /tasks/:id).

        Returns the full task record including distinct agentId and taskId.
        """
        encoded_id = urllib.parse.quote(task_id, safe="")
        res = self._request("GET", f"/tasks/{encoded_id}")

        t_id = res.get("taskId") or res.get("id") or res.get("task_id") or task_id
        a_id = res.get("agentId") or res.get("agent_id") or res.get("agent")
        if t_id:
            res["taskId"] = t_id
            res["task_id"] = t_id
        if a_id:
            res["agentId"] = a_id
            res["agent_id"] = a_id
            self.task_to_agent[t_id] = a_id

        self.known_tasks[t_id] = res
        return res

    def push(
        self,
        task_id: Optional[str] = None,
        head_sha: str = "",
        base_sha: Optional[str] = None,
        files_changed: Optional[Union[List[str], str]] = None,
        intent: Optional[str] = None,
        test_provenance: Optional[str] = None,
        agent_id: Optional[str] = None,
        token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Register a WIP commit push (POST /events/push).

        Sends agentId (required by L1 coordinator), head_sha, base_sha, files_changed, intent, test_provenance.
        If agent_id is not passed, resolves it via task_id mapping or get_task(task_id).
        """
        # Resolve agent_id if not explicitly provided
        effective_agent_id = agent_id
        if not effective_agent_id and task_id:
            if task_id in self.task_to_agent:
                effective_agent_id = self.task_to_agent[task_id]
            else:
                try:
                    task_rec = self.get_task(task_id)
                    effective_agent_id = (
                        task_rec.get("agentId")
                        or task_rec.get("agent_id")
                        or task_rec.get("agent")
                    )
                except Exception as exc:
                    raise ValueError(
                        f"Cannot resolve agentId for task '{task_id}'. "
                        f"Task lookup failed: {exc}. "
                        "Specify agent_id explicitly."
                    ) from exc

        if not effective_agent_id:
            raise ValueError(
                f"Cannot resolve agentId for task '{task_id}'. "
                "Task lookup failed or task record is missing agentId. "
                "Specify agent_id explicitly."
            )

        # Normalize files_changed to list of non-empty strings
        normalized_files: Optional[List[str]] = None
        if files_changed is not None:
            if isinstance(files_changed, str):
                normalized_files = [f.strip() for f in files_changed.split(",") if f.strip()]
            else:
                normalized_files = list(files_changed)

        # L1 coordinator requires agent / agentId
        payload: Dict[str, Any] = {
            "agentId": effective_agent_id,
            "agent": effective_agent_id,
            "head_sha": head_sha,
            "sha": head_sha,
        }
        if task_id:
            payload["task_id"] = task_id
            payload["taskId"] = task_id
        if base_sha:
            payload["base_sha"] = base_sha
        if normalized_files is not None:
            payload["files_changed"] = normalized_files
        if intent:
            payload["intent"] = intent
            payload["intent_update"] = intent
        if test_provenance:
            payload["test_provenance"] = test_provenance

        headers: Dict[str, str] = {}
        effective_token = token or self.admin_token or os.environ.get("ADMIN_TOKEN")
        if effective_token:
            headers["Authorization"] = f"Bearer {effective_token}"

        return self._request("POST", "/events/push", payload, headers=headers)

    def get_status(self) -> Dict[str, Any]:
        """Fetch current global coordinator and radar status (GET /status)."""
        return self._request("GET", "/status")

    def ack_warning(
        self,
        warning_id: str,
        task_id: Optional[str] = None,
        action: str = "acknowledged",
        agent: Optional[str] = None,
        token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Acknowledge a radar warning (POST /warnings/:id/ack)."""
        encoded_id = urllib.parse.quote(warning_id, safe="")
        payload: Dict[str, Any] = {"action": action}
        if task_id:
            payload["task_id"] = task_id
            payload["taskId"] = task_id
            if not agent and task_id in self.task_to_agent:
                agent = self.task_to_agent[task_id]
        if not agent and task_id:
            try:
                task_info = self.get_task(task_id)
                agent = task_info.get("agent") or task_info.get("agent_id") or task_info.get("agentId")
            except Exception:
                pass
        if agent:
            payload["agent"] = agent
            payload["agentId"] = agent

        headers: Dict[str, str] = {}
        effective_token = token or self.admin_token or os.environ.get("ADMIN_TOKEN")
        if effective_token:
            headers["Authorization"] = f"Bearer {effective_token}"

        return self._request("POST", f"/warnings/{encoded_id}/ack", payload, headers=headers)

    def record_test_provenance(
        self,
        task_id: str,
        command: str,
        exit_code: int,
        head_sha: str,
        token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Attach test provenance to a task (POST /tasks/:id/tests)."""
        encoded_id = urllib.parse.quote(task_id, safe="")
        payload = {
            "command": command,
            "exit": exit_code,
            "head_sha": head_sha,
        }
        headers: Dict[str, str] = {}
        effective_token = token or self.admin_token or os.environ.get("ADMIN_TOKEN")
        if effective_token:
            headers["Authorization"] = f"Bearer {effective_token}"
        return self._request("POST", f"/tasks/{encoded_id}/tests", payload, headers=headers)

    def send_checks(
        self,
        payload: Dict[str, Any],
        runner_token: Optional[str] = None,
        return_error_dict: bool = False,
    ) -> Dict[str, Any]:
        """Submit radar evaluation check results to L1 coordinator (POST /checks).

        Validates CONTRACT v0.1 schema:
            payload must contain 'contract', 'vector', 'results'.

        Args:
            payload: CONTRACT v0.1 check payload dictionary.
            runner_token: Optional runner bearer token (defaults to $RUNNER_TOKEN).
            return_error_dict: If True, returns structured dict on 409 StaleVectorError
                               instead of raising exception.

        Returns:
            Coordinator response dict (e.g. {accepted, pairs, createdWarnings}).

        Raises:
            ValueError: If payload fails validation.
            StaleVectorError: On HTTP 409 Conflict (stale vector) if return_error_dict is False.
            AgentBranchesAPIError: On other API errors.
        """
        if not isinstance(payload, dict):
            raise ValueError("checks payload must be a JSON dictionary")
        if "contract" not in payload:
            raise ValueError("checks payload missing required 'contract' field")
        if "vector" not in payload:
            raise ValueError("checks payload missing required 'vector' field")
        if "results" not in payload or not isinstance(payload["results"], list):
            raise ValueError("checks payload missing required 'results' list")

        req_headers: Dict[str, str] = {}
        token = runner_token or os.environ.get("RUNNER_TOKEN")
        if token:
            req_headers["Authorization"] = f"Bearer {token}"

        try:
            return self._request("POST", "/checks", payload, headers=req_headers)
        except StaleVectorError as exc:
            if return_error_dict:
                return {
                    "error": "stale_vector",
                    "status_code": 409,
                    "message": exc.message,
                    "details": exc.payload,
                }
            raise


    # MCP-compatible aliases (CONTRACT-L2-L3 Section 2.2)
    def branches_create_task(
        self,
        repo: str,
        base_sha: str,
        intent: str,
        branch: str,
        admin_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self.create_task(
            repo=repo,
            base_sha=base_sha,
            intent=intent,
            branch=branch,
            admin_token=admin_token,
        )

    def branches_push_wip(
        self,
        task_id: str,
        head_sha: str,
        intent_update: Optional[str] = None,
        test_provenance: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self.push(
            task_id=task_id,
            head_sha=head_sha,
            intent=intent_update,
            test_provenance=test_provenance,
            agent_id=agent_id,
        )

    def branches_get_status(self, task_id: Optional[str] = None) -> Dict[str, Any]:
        if task_id:
            return self.get_task(task_id)
        return self.get_status()

    def branches_ack_warning(
        self, task_id: str, warning_id: str, action: str = "rebased_locally"
    ) -> Dict[str, Any]:
        return self.ack_warning(warning_id=warning_id, task_id=task_id, action=action)
