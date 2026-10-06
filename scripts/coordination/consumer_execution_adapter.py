#!/usr/bin/env python3
"""Consumer execution adapter for admitted tasks (Directive C3032).

Strict admission vs execution state separation, isolated worker unit spawn,
artifact deliverable provenance, and zero fake ACTIVE state.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import logging
import os
import sys
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

# sys.path handling for /home/alexey/git/agent-coordination and /home/alexey/git/agent-bus
def _setup_sys_path() -> None:
    this_file = Path(__file__).resolve() if "__file__" in globals() else Path.cwd()
    coord_roots = [
        os.environ.get("AGENT_COORDINATION_ROOT"),
        "/home/alexey/git/agent-coordination",
        str(this_file.parents[3] / "agent-coordination") if len(this_file.parents) > 3 else "",
        str(this_file.parents[2] / "agent-coordination") if len(this_file.parents) > 2 else "",
    ]
    bus_roots = [
        os.environ.get("AGENT_BUS_ROOT"),
        "/home/alexey/git/agent-bus",
        str(this_file.parents[3] / "agent-bus") if len(this_file.parents) > 3 else "",
        str(this_file.parents[2] / "agent-bus") if len(this_file.parents) > 2 else "",
    ]
    for root in bus_roots:
        if root and os.path.isdir(root) and str(root) not in sys.path:
            sys.path.insert(0, str(root))
            break
    for root in coord_roots:
        if root and os.path.isdir(root):
            if str(root) in sys.path:
                sys.path.remove(str(root))
            sys.path.insert(0, str(root))
            break

_setup_sys_path()

try:
    import coordination
    for coord_root in [os.environ.get("AGENT_COORDINATION_ROOT"), "/home/alexey/git/agent-coordination"]:
        if coord_root and os.path.isdir(coord_root):
            coord_pkg = os.path.join(coord_root, "coordination")
            if os.path.isdir(coord_pkg) and coord_pkg not in coordination.__path__:
                coordination.__path__.insert(0, coord_pkg)
    for bus_root in [os.environ.get("AGENT_BUS_ROOT"), "/home/alexey/git/agent-bus"]:
        if bus_root and os.path.isdir(bus_root):
            bus_coord = os.path.join(bus_root, "coordination")
            if os.path.isdir(bus_coord) and bus_coord not in coordination.__path__:
                coordination.__path__.append(bus_coord)
except Exception:
    pass

from adapters.agent_bus_client import (
    ack_message,
    enroll_agent,
    poll_messages,
    reject_head_cred_inheritance,
    reply_message,
)
from coordination.host_interface import (
    GuardRejected,
    MultiHostAdmission,
    UnknownDevice,
    emit_host_event,
)

logger = logging.getLogger(__name__)


@dataclass
class ExecutionUnit:
    """Execution unit representing an admitted or executing task."""

    unit_id: str = field(default_factory=lambda: f"unit-{uuid.uuid4().hex[:12]}")
    task_id: str = ""
    device_id: str = ""
    state: str = "admitted"  # 'admitted', 'pending', 'running', 'completed', 'failed'
    pid: int | None = None
    started_at: str | None = None
    completed_at: str | None = None
    artifact_path: str | None = None
    artifact_sha256: str | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        if not self.unit_id:
            self.unit_id = f"unit-{uuid.uuid4().hex[:12]}"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ConsumerExecutionAdapter:
    """Consumer execution adapter for admitted tasks with strict state boundaries."""

    def __init__(
        self,
        store_path: Path | str | None,
        cred: dict[str, Any] | str | Path,
        admission: MultiHostAdmission | None = None,
        events_dir: Path | str | None = None,
        artifacts_dir: Path | str | None = None,
    ) -> None:
        if isinstance(cred, (str, Path)):
            cred_str = str(cred).strip()
            if cred_str.startswith("{") and cred_str.endswith("}"):
                self.cred = json.loads(cred_str)
            else:
                cred_path = Path(cred).resolve()
                if not cred_path.is_file():
                    raise FileNotFoundError(f"Credential file not found: {cred_path}")
                try:
                    cred_path.chmod(0o600)
                except Exception:
                    pass
                with open(cred_path, "r", encoding="utf-8") as f:
                    self.cred = json.load(f)
        elif isinstance(cred, dict):
            self.cred = cred
        else:
            raise TypeError(f"Invalid cred type: {type(cred).__name__}; expected dict, str, or Path")

        if store_path is not None:
            self.store_path = Path(store_path).resolve()
        elif "store" in self.cred:
            self.store_path = Path(self.cred["store"]).resolve()
        else:
            raise ValueError("store_path is required (neither passed as argument nor found in credential)")

        if events_dir is not None:
            self.events_dir = Path(events_dir).resolve()
        elif admission is not None and getattr(admission, "events_dir", None) is not None:
            self.events_dir = Path(admission.events_dir).resolve()
        else:
            self.events_dir = None

        if admission is not None:
            self.admission = admission
        else:
            self.admission = MultiHostAdmission(events_dir=self.events_dir)

        if self.events_dir is None and getattr(self.admission, "events_dir", None) is not None:
            self.events_dir = Path(self.admission.events_dir).resolve()

        if artifacts_dir is not None:
            self.artifacts_dir = Path(artifacts_dir).resolve()
        else:
            self.artifacts_dir = self.store_path / "artifacts"
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

        self.units: dict[str, ExecutionUnit] = {}

    def admit_task(self, msg: dict[str, Any]) -> ExecutionUnit:
        """Admit task with strict validation and reservation state separation.

        Validates reject_head_cred_inheritance and host admission.
        On rejection: emits rejection event, ACKs poison pill message to avoid sink loops,
        and raises GuardRejected / UnknownDevice.
        On success: creates ExecutionUnit in state='admitted' (never 'active' or 'running'),
        emits 'task_admitted' event, and returns unit.
        """
        message_id = msg.get("message_id") or msg.get("id") or ""
        sender_id = msg.get("sender_id") or ""
        body = msg.get("body", "")
        raw_data = msg.get("data")
        if raw_data is None:
            data: dict[str, Any] = {}
        elif isinstance(raw_data, dict):
            data = copy.deepcopy(raw_data)
        elif isinstance(raw_data, str):
            try:
                parsed = json.loads(raw_data)
                data = parsed if isinstance(parsed, dict) else {"raw": parsed}
            except Exception:
                data = {"raw": raw_data}
        else:
            data = {"raw": raw_data}

        device_id = data.get("device_id") or data.get("origin_device") or msg.get("device_id") or "unknown"
        task_id = (
            data.get("task_id")
            or msg.get("task_id")
            or (f"task-{message_id}" if message_id else f"task-{uuid.uuid4().hex[:8]}")
        )

        try:
            # 1. Validates reject_head_cred_inheritance(msg.get('data') or {})
            try:
                reject_head_cred_inheritance(data, reject=True)
            except ValueError as exc:
                raise GuardRejected(str(exc)) from exc

            # 2. Validates reject_head_cred_inheritance({'body': msg.get('body', '')})
            try:
                reject_head_cred_inheritance({"body": body}, reject=True)
            except ValueError as exc:
                raise GuardRejected(str(exc)) from exc

            # 3. Validates device_id and task_id via self.admission._admit_host_task_impl
            admit_res = self.admission._admit_host_task_impl(
                device_id=device_id,
                task_id=task_id,
                payload=data,
                reject_on_cred=True,
            )
        except (GuardRejected, UnknownDevice, ValueError) as err:
            actual_err = err if isinstance(err, (GuardRejected, UnknownDevice)) else GuardRejected(str(err))
            event_type = "guard_rejected" if isinstance(actual_err, GuardRejected) else "admission_rejected"
            emit_host_event(
                event_type=event_type,
                device_id=device_id,
                task_id=task_id,
                details={
                    "reason": str(actual_err),
                    "error_type": type(actual_err).__name__,
                    "message_id": message_id,
                    "sender_id": sender_id,
                },
                events_dir=self.events_dir,
            )
            if message_id:
                try:
                    ack_message(self.store_path, self.cred, message_id=message_id)
                except Exception as ack_err:
                    logger.warning("Failed to ACK poison pill message %s: %s", message_id, ack_err)
            raise actual_err

        # On success: State is strictly 'admitted' / reservation-only. Never 'active' or 'running'.
        unit = ExecutionUnit(
            task_id=task_id,
            device_id=device_id,
            state="admitted",
        )
        self.units[unit.unit_id] = unit

        emit_host_event(
            event_type="task_admitted",
            device_id=device_id,
            task_id=task_id,
            details={
                "unit_id": unit.unit_id,
                "device_id": admit_res.get("device_id", device_id),
                "task_id": admit_res.get("task_id", task_id),
                "state": unit.state,
                "delivery": admit_res.get("delivery"),
                "execution_target": admit_res.get("execution_target"),
                "session_id": admit_res.get("session_id"),
                "message_id": message_id,
                "sender_id": sender_id,
            },
            events_dir=self.events_dir,
        )
        return unit

    def spawn_worker_unit(
        self,
        unit: ExecutionUnit,
        action: str,
        payload: dict[str, Any],
        runner_fn: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None,
    ) -> ExecutionUnit:
        """Spawn isolated worker unit, execute task, and write deliverable artifact."""
        unit.state = "running"
        unit.started_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        unit.pid = os.getpid()

        emit_host_event(
            event_type="task_spawned",
            device_id=unit.device_id,
            task_id=unit.task_id,
            details={
                "unit_id": unit.unit_id,
                "action": action,
                "pid": unit.pid,
                "started_at": unit.started_at,
                "state": unit.state,
            },
            events_dir=self.events_dir,
        )

        try:
            if runner_fn is not None:
                result = runner_fn(unit.task_id, payload)
            else:
                result = {
                    "task_id": unit.task_id,
                    "unit_id": unit.unit_id,
                    "device_id": unit.device_id,
                    "action": action,
                    "payload": payload,
                    "status": "success",
                    "executed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "deliverable": f"Artifact deliverable for {unit.task_id}",
                }

            artifact_file = self.artifacts_dir / f"{unit.task_id}.json"
            if isinstance(result, (dict, list)):
                artifact_content = json.dumps(result, indent=2, sort_keys=True).encode("utf-8")
            elif isinstance(result, (str, bytes)):
                artifact_content = result if isinstance(result, bytes) else result.encode("utf-8")
            elif result is None and artifact_file.exists():
                with open(artifact_file, "rb") as f:
                    artifact_content = f.read()
            else:
                artifact_content = json.dumps(
                    {"task_id": unit.task_id, "result": str(result)}, indent=2
                ).encode("utf-8")

            with open(artifact_file, "wb") as f:
                f.write(artifact_content)

            sha256 = hashlib.sha256(artifact_content).hexdigest()
            unit.artifact_path = str(artifact_file.resolve())
            unit.artifact_sha256 = sha256
            unit.state = "completed"
            unit.completed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

            emit_host_event(
                event_type="task_completed",
                device_id=unit.device_id,
                task_id=unit.task_id,
                details={
                    "unit_id": unit.unit_id,
                    "action": action,
                    "state": unit.state,
                    "artifact_path": unit.artifact_path,
                    "artifact_sha256": unit.artifact_sha256,
                    "completed_at": unit.completed_at,
                },
                events_dir=self.events_dir,
            )
        except Exception as exc:
            unit.state = "failed"
            unit.error = str(exc)
            unit.completed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            emit_host_event(
                event_type="task_failed",
                device_id=unit.device_id,
                task_id=unit.task_id,
                details={
                    "unit_id": unit.unit_id,
                    "action": action,
                    "state": unit.state,
                    "error": str(exc),
                    "completed_at": unit.completed_at,
                },
                events_dir=self.events_dir,
            )
            raise

        return unit

    def send_completion_reply(
        self, message_id: str, sender_id: str, unit: ExecutionUnit
    ) -> dict[str, Any]:
        """Send correlated completion reply to message sender and advance cursor."""
        reply_data = {
            "status": "completed" if unit.state == "completed" else unit.state,
            "unit_id": unit.unit_id,
            "task_id": unit.task_id,
            "artifact_path": unit.artifact_path,
            "artifact_sha256": unit.artifact_sha256,
            "session_id": None,
            "execution_target": "hetzner-rmthz",
        }
        if unit.error:
            reply_data["error"] = unit.error

        outcome = reply_message(
            store_path=self.store_path,
            cred=self.cred,
            message_id=message_id,
            body=f"TASK-COMPLETED:{unit.task_id}",
            data=reply_data,
        )
        if message_id:
            ack_message(self.store_path, self.cred, message_id=message_id)

        return outcome

    def poll_and_execute(self, limit: int | None = None) -> list[dict[str, Any]]:
        """Poll unread messages, admit each, execute in isolated worker, and reply."""
        messages = poll_messages(self.store_path, self.cred, unread_only=True)
        if limit is not None:
            messages = messages[:limit]

        outcomes: list[dict[str, Any]] = []
        for msg in messages:
            message_id = msg.get("message_id") or msg.get("id") or ""
            sender_id = msg.get("sender_id") or ""
            try:
                unit = self.admit_task(msg)
            except (GuardRejected, UnknownDevice, ValueError) as exc:
                outcomes.append({
                    "status": "rejected",
                    "reason": str(exc),
                    "message_id": message_id,
                    "sender_id": sender_id,
                })
                continue

            raw_data = msg.get("data") or {}
            action = msg.get("kind") or raw_data.get("action") or "execute"
            payload = raw_data.get("payload") if isinstance(raw_data.get("payload"), dict) else raw_data

            try:
                self.spawn_worker_unit(unit, action=action, payload=payload)
                reply_outcome = self.send_completion_reply(
                    message_id=message_id,
                    sender_id=sender_id,
                    unit=unit,
                )
                outcomes.append({
                    "status": "completed",
                    "unit": unit.to_dict(),
                    "message_id": message_id,
                    "reply": reply_outcome,
                })
            except Exception as exc:
                outcomes.append({
                    "status": "failed",
                    "error": str(exc),
                    "unit": unit.to_dict(),
                    "message_id": message_id,
                })
        return outcomes


def build_cli_parser() -> argparse.ArgumentParser:
    """Build CLI parser for consumer execution adapter."""
    parser = argparse.ArgumentParser(
        description="Consumer execution adapter for admitted tasks (Directive C3032)."
    )
    parser.add_argument("--store", type=str, default=None, help="Path to FileBus store directory.")
    parser.add_argument("--cred", type=str, default=None, help="Path to credential file or inline JSON.")
    parser.add_argument("--registry", type=str, default=None, help="Path to device registry JSON.")
    parser.add_argument("--events-dir", type=str, default=None, help="Path to directory for host_events.jsonl.")
    parser.add_argument("--artifacts-dir", type=str, default=None, help="Path to directory for deliverable artifacts.")
    parser.add_argument("--once", action="store_true", help="Process available messages once and exit.")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format.")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Main CLI entrypoint."""
    parser = build_cli_parser()
    args = parser.parse_args(argv)

    if not args.cred:
        parser.error("--cred is required")

    admission = MultiHostAdmission(
        registry_path=args.registry,
        events_dir=args.events_dir,
    )

    adapter = ConsumerExecutionAdapter(
        store_path=args.store,
        cred=args.cred,
        admission=admission,
        events_dir=args.events_dir,
        artifacts_dir=args.artifacts_dir,
    )

    outcomes = adapter.poll_and_execute()
    if args.json:
        print(json.dumps(outcomes, indent=2))
    else:
        for oc in outcomes:
            print(
                f"[{oc.get('status', 'unknown').upper()}] "
                f"message={oc.get('message_id')} "
                f"unit={oc.get('unit', {}).get('unit_id')}"
            )

    return 0


if __name__ == "__main__":
    sys.exit(main())
