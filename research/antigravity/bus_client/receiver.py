#!/usr/bin/env python3
"""Agent Bus Real Receiver Client (Task bus-real-receiver-client-adoption-01).

An isolated, production-grade outbound-only receiver client that connects to the
Agent Bus REST adapter (or loopback adapter), polls for messages, and executes
the complete 5-stage coordination lifecycle:
  1. Poll inbox (GET /v1/inbox)
  2. Read-ACK (POST /v1/ack) -> records message delivery (acked_at)
  3. Semantic Acceptance (POST /v1/accept) -> records task commitment (accepted_at)
  4. Execution / Delegation -> executes task handler
  5. Completion (POST /v1/complete) -> records artifact digest and status (completed_at)
  6. Correlated Reply (POST /v1/reply) -> links back to sender with reply_to

Invariants:
- Uses strictly Python standard library (urllib.request, json, hashlib, etc.).
- Never binds listening sockets (strictly outbound HTTP client).
- Manages credentials in private files (mode 0600, umask 077).
- Preserves Bus source lease (zero edits in /home/alexey/git/agent-bus).
- Clean error taxonomy (401, 403, 404, 409).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("bus_client.receiver")


class BusClientError(Exception):
    """Base exception for bus client errors."""
    def __init__(self, message: str, status_code: int = 500, error_code: str = "internal_error"):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code


class AuthenticationError(BusClientError):
    """Raised when authentication fails (HTTP 401)."""
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, status_code=401, error_code="auth_failed")


class AuthorizationError(BusClientError):
    """Raised when access is denied or recipient mismatch (HTTP 403)."""
    def __init__(self, message: str = "Access forbidden", error_code: str = "not_recipient"):
        super().__init__(message, status_code=403, error_code=error_code)


class NotFoundError(BusClientError):
    """Raised when a message or resource is not found (HTTP 404)."""
    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, status_code=404, error_code="not_found")


class IdempotencyConflictError(BusClientError):
    """Raised when an idempotency conflict occurs (HTTP 409)."""
    def __init__(self, message: str = "Idempotency key conflict"):
        super().__init__(message, status_code=409, error_code="idempotency_conflict")


@dataclass
class ReceiverCredentials:
    identity_id: str
    agent_name: str
    device_id: str
    project_id: str
    token: str
    registered_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReceiverCredentials":
        return cls(
            identity_id=data.get("identity_id") or data.get("id", ""),
            agent_name=data.get("agent_name", ""),
            device_id=data.get("device_id", ""),
            project_id=data.get("project_id", ""),
            token=data.get("token", ""),
            registered_at=data.get("registered_at", ""),
        )


def compute_payload_digest(data: Any) -> str:
    """Compute deterministic SHA-256 digest of arbitrary payload."""
    if isinstance(data, bytes):
        raw = data
    elif isinstance(data, str):
        raw = data.encode("utf-8")
    else:
        raw = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class BusReceiverClient:
    """Outbound-only receiver client interacting with the Agent Bus REST adapter."""

    def __init__(
        self,
        adapter_url: str = "http://127.0.0.1:8788/v1",
        agent_name: str = "ant-receiver-client",
        device_id: str = "device-ant-01",
        project_id: str = "agent-bus",
        credentials_path: Optional[Path | str] = None,
        timeout_sec: float = 10.0,
        handler: Optional[Callable[[Dict[str, Any]], Tuple[str, str, Any]]] = None,
    ):
        self.adapter_url = adapter_url.rstrip("/")
        self.agent_name = agent_name
        self.device_id = device_id
        self.project_id = project_id
        self.credentials_path = Path(credentials_path) if credentials_path else None
        self.timeout_sec = timeout_sec
        self.handler = handler or self._default_handler

        self.credentials: Optional[ReceiverCredentials] = None
        self.identity_id: Optional[str] = None
        self.token: Optional[str] = None

    def _default_handler(self, envelope: Dict[str, Any]) -> Tuple[str, str, Any]:
        """Default handler: echoes payload and computes SHA-256 digest."""
        body = envelope.get("body", {})
        digest = compute_payload_digest(body)
        result = {
            "echo": body,
            "processed_at": time.time(),
            "status": "success",
            "sha256": digest,
        }
        return "success", digest, result

    def _request(
        self,
        method: str,
        path: str,
        payload: Optional[Dict[str, Any]] = None,
        query: Optional[Dict[str, Any]] = None,
        token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute an HTTP request against the adapter with comprehensive error mapping."""
        url = f"{self.adapter_url}{path}"
        if query:
            clean_query = {k: v for k, v in query.items() if v is not None}
            if clean_query:
                url = f"{url}?{urllib.parse.urlencode(clean_query)}"

        headers = {
            "Accept": "application/json",
            "User-Agent": f"BusReceiverClient/{self.agent_name}",
        }
        data: Optional[bytes] = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        active_token = token or self.token
        if active_token:
            headers["Authorization"] = f"Bearer {active_token}"

        req = urllib.request.Request(url, data=data, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
                raw_body = resp.read()
                if not raw_body:
                    return {}
                return json.loads(raw_body.decode("utf-8"))
        except urllib.error.HTTPError as exc:
            err_data: Dict[str, Any] = {}
            try:
                raw_err = exc.read().decode("utf-8")
                err_data = json.loads(raw_err)
            except Exception:
                err_data = {"error": exc.reason}

            msg = err_data.get("message") or err_data.get("error") or exc.reason
            code = err_data.get("code") or ""

            if exc.code == 401:
                raise AuthenticationError(msg) from exc
            elif exc.code == 403:
                raise AuthorizationError(msg, error_code=code or "forbidden") from exc
            elif exc.code == 404:
                raise NotFoundError(msg) from exc
            elif exc.code == 409:
                raise IdempotencyConflictError(msg) from exc
            else:
                raise BusClientError(f"HTTP {exc.code}: {msg}", status_code=exc.code, error_code=code) from exc
        except urllib.error.URLError as exc:
            raise BusClientError(f"Network error connecting to adapter at {url}: {exc.reason}") from exc

    def get_status(self) -> Dict[str, Any]:
        """Query adapter health and transport status."""
        return self._request("GET", "/status")

    def register(self) -> ReceiverCredentials:
        """Register agent identity with the adapter and obtain credentials."""
        payload = {
            "agent_name": self.agent_name,
            "device_id": self.device_id,
            "project_id": self.project_id,
        }
        resp = self._request("POST", "/register", payload=payload)
        ident_info = resp.get("identity", {})
        identity_id = (
            resp.get("identity_id")
            or resp.get("id")
            or ident_info.get("identity_id")
            or ident_info.get("id")
        )
        token = resp.get("token")
        if not identity_id or not token:
            raise BusClientError(f"Registration response missing identity_id or token: {resp}")

        creds = ReceiverCredentials(
            identity_id=identity_id,
            agent_name=self.agent_name,
            device_id=self.device_id,
            project_id=self.project_id,
            token=token,
            registered_at=resp.get("registered_at", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())),
        )
        self.credentials = creds
        self.identity_id = identity_id
        self.token = token

        if self.credentials_path:
            self.save_credentials()

        return creds

    def save_credentials(self) -> None:
        """Save credentials to disk with mode 0600."""
        if not self.credentials_path or not self.credentials:
            return
        self.credentials_path.parent.mkdir(parents=True, exist_ok=True)
        old_umask = os.umask(0o077)
        try:
            tmp_path = self.credentials_path.with_suffix(".tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self.credentials.to_dict(), f, indent=2)
            os.chmod(tmp_path, 0o600)
            os.replace(tmp_path, self.credentials_path)
        finally:
            os.umask(old_umask)

    def load_credentials(self) -> bool:
        """Load credentials from disk if present."""
        if not self.credentials_path or not self.credentials_path.exists():
            return False
        try:
            with open(self.credentials_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            creds = ReceiverCredentials.from_dict(data)
            self.credentials = creds
            self.identity_id = creds.identity_id
            self.token = creds.token
            return True
        except Exception as exc:
            logger.warning("Failed to load credentials from %s: %s", self.credentials_path, exc)
            return False

    def ensure_registered(self) -> ReceiverCredentials:
        """Ensure client is registered, loading from disk or calling register."""
        if self.token and self.identity_id:
            if not self.credentials:
                self.credentials = ReceiverCredentials(
                    identity_id=self.identity_id,
                    agent_name=self.agent_name,
                    device_id=self.device_id,
                    project_id=self.project_id,
                    token=self.token,
                    registered_at="",
                )
            return self.credentials
        if self.load_credentials():
            return self.credentials  # type: ignore[return-value]
        return self.register()

    def send_message(
        self,
        recipient_id: str,
        body: Any,
        idempotency_key: Optional[str] = None,
        reply_to: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Send an envelope to another identity via the adapter."""
        self.ensure_registered()
        payload: Dict[str, Any] = {
            "sender_id": self.identity_id,
            "token": self.token,
            "recipient_id": recipient_id,
            "body": body,
        }
        if idempotency_key:
            payload["idempotency_key"] = idempotency_key
        if reply_to:
            payload["reply_to"] = reply_to
        if metadata:
            payload["metadata"] = metadata

        resp = self._request("POST", "/send", payload=payload)
        msg_info = resp.get("message", {})
        if msg_info:
            mid = msg_info.get("id") or msg_info.get("message_id")
            if mid:
                resp["id"] = mid
                resp["message_id"] = mid
        return resp

    def poll_inbox(self, unread_only: bool = True) -> List[Dict[str, Any]]:
        """Poll inbox for available messages."""
        self.ensure_registered()
        query = {
            "identity_id": self.identity_id,
            "token": self.token,
            "unread_only": "true" if unread_only else "false",
        }
        resp = self._request("GET", "/inbox", query=query)
        messages = resp.get("messages", [])
        return messages

    def ack_message(self, message_id: str) -> Dict[str, Any]:
        """Record read-ACK transition on message."""
        self.ensure_registered()
        payload = {
            "identity_id": self.identity_id,
            "token": self.token,
            "message_id": message_id,
        }
        resp = self._request("POST", "/ack", payload=payload)
        msg_info = resp.get("message", {})
        if msg_info:
            resp["acked_at"] = msg_info.get("acked_at")
            resp["id"] = msg_info.get("id") or msg_info.get("message_id")
        return resp

    def accept_message(self, message_id: str) -> Dict[str, Any]:
        """Record semantic acceptance transition on message."""
        self.ensure_registered()
        payload = {
            "identity_id": self.identity_id,
            "token": self.token,
            "message_id": message_id,
        }
        resp = self._request("POST", "/accept", payload=payload)
        msg_info = resp.get("message", {})
        if msg_info:
            resp["accepted_at"] = msg_info.get("accepted_at")
            resp["id"] = msg_info.get("id") or msg_info.get("message_id")
        return resp

    def complete_message(
        self,
        message_id: str,
        status: str = "success",
        digest: str = "",
        artifact: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Record task outcome completion with artifact digest."""
        self.ensure_registered()
        payload = {
            "identity_id": self.identity_id,
            "token": self.token,
            "message_id": message_id,
            "status": status,
            "digest": digest,
            "artifact": artifact or {},
        }
        resp = self._request("POST", "/complete", payload=payload)
        msg_info = resp.get("message", {})
        if msg_info:
            resp["outcome_at"] = msg_info.get("outcome_at")
            resp["completed_at"] = msg_info.get("outcome_at")
            resp["id"] = msg_info.get("id") or msg_info.get("message_id")
        return resp

    def reply_message(
        self,
        message_id: str,
        body: Any,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send correlated reply envelope to sender of message_id."""
        self.ensure_registered()
        payload = {
            "sender_id": self.identity_id,
            "token": self.token,
            "message_id": message_id,
            "body": body,
            "idempotency_key": idempotency_key or f"reply-{message_id}-{uuid_hex(8)}",
        }
        resp = self._request("POST", "/reply", payload=payload)
        msg_info = resp.get("message", {})
        if msg_info:
            resp["id"] = msg_info.get("id") or msg_info.get("message_id")
            resp["reply_to"] = msg_info.get("reply_to")
        return resp

    def process_envelope(self, envelope: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the complete 5-stage coordination lifecycle for an envelope.

        Lifecycle:
        1. Read-ACK: records read receipt
        2. Semantic Acceptance: commits to processing the task
        3. Execution: delegates to handler
        4. Completion: records status and artifact digest
        5. Correlated Reply: sends result back to original sender
        """
        msg_id = envelope.get("id") or envelope.get("message_id")
        if not msg_id:
            raise BusClientError("Envelope missing message ID")

        sender_id = envelope.get("sender_id") or envelope.get("from", "unknown")
        start_time = time.time()
        record: Dict[str, Any] = {
            "message_id": msg_id,
            "sender_id": sender_id,
            "started_at": start_time,
            "stages": {},
        }

        # Stage 1: Read-ACK
        try:
            ack_resp = self.ack_message(msg_id)
            record["stages"]["ack"] = {"status": "ok", "response": ack_resp}
        except Exception as exc:
            record["stages"]["ack"] = {"status": "failed", "error": str(exc)}
            logger.error("Stage 1 (ACK) failed for message %s: %s", msg_id, exc)
            raise

        # Stage 2: Semantic Acceptance
        try:
            accept_resp = self.accept_message(msg_id)
            record["stages"]["accept"] = {"status": "ok", "response": accept_resp}
        except Exception as exc:
            record["stages"]["accept"] = {"status": "failed", "error": str(exc)}
            logger.error("Stage 2 (Accept) failed for message %s: %s", msg_id, exc)
            raise

        # Stage 3: Execution via handler
        outcome_status = "success"
        artifact_digest = ""
        result_artifact: Any = None
        try:
            outcome_status, artifact_digest, result_artifact = self.handler(envelope)
            record["stages"]["execution"] = {
                "status": outcome_status,
                "digest": artifact_digest,
                "artifact": result_artifact,
            }
        except Exception as exc:
            outcome_status = "failed"
            artifact_digest = hashlib.sha256(str(exc).encode("utf-8")).hexdigest()
            result_artifact = {"error": str(exc), "type": type(exc).__name__}
            record["stages"]["execution"] = {
                "status": "failed",
                "error": str(exc),
                "digest": artifact_digest,
            }
            logger.warning("Stage 3 (Execution) failed for message %s: %s", msg_id, exc)

        # Stage 4: Completion
        try:
            complete_resp = self.complete_message(
                msg_id,
                status=outcome_status,
                digest=artifact_digest,
                artifact=result_artifact,
            )
            record["stages"]["complete"] = {"status": "ok", "response": complete_resp}
        except Exception as exc:
            record["stages"]["complete"] = {"status": "failed", "error": str(exc)}
            logger.error("Stage 4 (Complete) failed for message %s: %s", msg_id, exc)

        # Stage 5: Correlated Reply
        try:
            reply_body = {
                "task_outcome": outcome_status,
                "artifact_sha256": artifact_digest,
                "result": result_artifact,
                "duration_sec": round(time.time() - start_time, 4),
            }
            reply_resp = self.reply_message(msg_id, body=reply_body)
            record["stages"]["reply"] = {"status": "ok", "response": reply_resp}
        except Exception as exc:
            record["stages"]["reply"] = {"status": "failed", "error": str(exc)}
            logger.error("Stage 5 (Reply) failed for message %s: %s", msg_id, exc)

        record["completed_at"] = time.time()
        record["duration_sec"] = round(record["completed_at"] - start_time, 4)
        record["final_status"] = outcome_status
        return record

    def poll_and_process_once(self) -> List[Dict[str, Any]]:
        """Poll for unread messages and process each through the full lifecycle."""
        messages = self.poll_inbox(unread_only=True)
        results = []
        for msg in messages:
            try:
                res = self.process_envelope(msg)
                results.append(res)
            except Exception as exc:
                logger.error("Failed to process message %s: %s", msg.get("id"), exc)
                results.append({
                    "message_id": msg.get("id"),
                    "final_status": "error",
                    "error": str(exc),
                })
        return results

    def run_loop(
        self,
        poll_interval_sec: float = 1.0,
        max_iterations: Optional[int] = None,
        stop_event: Optional[Any] = None,
    ) -> int:
        """Run continuous polling loop until stopped or max_iterations reached."""
        self.ensure_registered()
        iterations = 0
        processed_total = 0

        while True:
            if stop_event and stop_event.is_set():
                break
            if max_iterations is not None and iterations >= max_iterations:
                break

            iterations += 1
            try:
                results = self.poll_and_process_once()
                processed_total += len(results)
            except Exception as exc:
                logger.warning("Error during polling iteration %d: %s", iterations, exc)

            if max_iterations is not None and iterations >= max_iterations:
                break

            time.sleep(poll_interval_sec)

        return processed_total


def uuid_hex(length: int = 8) -> str:
    """Helper to generate random hex string."""
    return os.urandom(length // 2).hex()


def cli_main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point for the receiver client."""
    parser = argparse.ArgumentParser(description="Agent Bus Real Receiver Client")
    parser.add_argument("--adapter-url", default="http://127.0.0.1:8788/v1", help="Adapter REST API base URL")
    parser.add_argument("--agent-name", default="ant-receiver-client", help="Agent identity name")
    parser.add_argument("--device-id", default="device-ant-01", help="Device identifier")
    parser.add_argument("--project-id", default="agent-bus", help="Project identifier")
    parser.add_argument("--credentials-file", help="Path to 0600 credentials file")
    parser.add_argument("--poll-interval", type=float, default=2.0, help="Poll interval in seconds")
    parser.add_argument("--once", action="store_true", help="Poll and process exactly once, then exit")
    parser.add_argument("--max-iterations", type=int, help="Maximum polling loop iterations")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")

    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    client = BusReceiverClient(
        adapter_url=args.adapter_url,
        agent_name=args.agent_name,
        device_id=args.device_id,
        project_id=args.project_id,
        credentials_path=args.credentials_file,
    )

    try:
        client.ensure_registered()
        if args.once:
            results = client.poll_and_process_once()
            if args.json:
                print(json.dumps({"status": "ok", "processed": len(results), "results": results}, indent=2))
            else:
                print(f"Processed {len(results)} message(s).")
            return 0
        else:
            total = client.run_loop(
                poll_interval_sec=args.poll_interval,
                max_iterations=args.max_iterations,
            )
            if args.json:
                print(json.dumps({"status": "ok", "total_processed": total}))
            else:
                print(f"Receiver stopped. Total processed: {total}")
            return 0
    except Exception as exc:
        if args.json:
            print(json.dumps({"status": "error", "error": str(exc)}), file=sys.stderr)
        else:
            print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(cli_main())
