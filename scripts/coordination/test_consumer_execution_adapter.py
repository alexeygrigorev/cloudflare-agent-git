#!/usr/bin/env python3
"""Pytest suite for ConsumerExecutionAdapter (Directive C3032).

Tests:
- test_admission_reservation_state_is_never_fake_active
- test_spawn_worker_unit_executes_and_produces_artifact
- test_head_cred_leak_fails_closed_without_execution
- test_correlated_reply_and_cursor_advancement
- test_unrelated_cursor_isolation_during_execution
- test_unknown_device_admission_rejection
- test_cli_execution_once_json
- test_default_runner_is_launcher_backed_not_synthesized
- test_launcher_runner_maps_failed_state_to_unit_failure
- test_launcher_runner_poll_expiry_is_honest_failure
- test_launcher_runner_fail_closed_missing_params
- test_launcher_request_nonzero_exit_fails_unit
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Setup sys.path for agent-coordination and agent-bus
COORD_ROOT = Path("/home/alexey/git/agent-coordination")
BUS_ROOT = Path("/home/alexey/git/agent-bus")
if str(BUS_ROOT) not in sys.path:
    sys.path.insert(0, str(BUS_ROOT))
if str(COORD_ROOT) not in sys.path:
    sys.path.insert(0, str(COORD_ROOT))

try:
    import coordination
    coord_pkg = str(COORD_ROOT / "coordination")
    if coord_pkg not in coordination.__path__:
        coordination.__path__.insert(0, coord_pkg)
    bus_pkg = str(BUS_ROOT / "coordination")
    if bus_pkg not in coordination.__path__:
        coordination.__path__.append(bus_pkg)
except Exception:
    pass

from adapters.agent_bus_client import (
    ack_message,
    enroll_agent,
    poll_messages,
    send_message,
)
from coordination.bus import FileBus
from coordination.host_interface import (
    GuardRejected,
    UnknownDevice,
    query_host_events,
)
from scripts.coordination.consumer_execution_adapter import (
    ConsumerExecutionAdapter,
    ExecutionUnit,
    LauncherRequestRunner,
    main,
)
import scripts.coordination.consumer_execution_adapter as adapter_module


def _stub_runner(task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "completed",
        "launcher_task_id": f"t-stub-{task_id}",
        "controller_unit": f"ql-ctl-t-stub-{task_id}.service",
        "profile": "model-task",
        "source_receipt": {"resolved_commit": "f" * 40, "repo_path": "/tmp/stub"},
    }


def _fake_completed_process(returncode: int = 0, stdout: str = "", stderr: str = ""):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


def test_admission_reservation_state_is_never_fake_active(tmp_path: Path) -> None:
    """Verifies admitted task stays state='admitted', never 'active' or 'running'."""
    bus_store = tmp_path / "bus_store"
    bus_store.mkdir(parents=True, mode=0o700)
    events_dir = tmp_path / "events"
    events_dir.mkdir(parents=True, mode=0o700)
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir(parents=True, mode=0o700)

    consumer_cred, _ = enroll_agent(bus_store, "consumer-agent", device_id="hetzner-rmthz")
    client_cred, _ = enroll_agent(bus_store, "windows-client", device_id="windows-desktop")

    adapter = ConsumerExecutionAdapter(
        store_path=bus_store,
        cred=consumer_cred,
        events_dir=events_dir,
        artifacts_dir=artifacts_dir,
    )

    # Client sends task admission request
    send_message(
        bus_store,
        client_cred,
        recipient_id=consumer_cred["identity"]["identity_id"],
        body="Execute computation task",
        data={"task_id": "task-reserve-001", "device_id": "windows-desktop"},
        kind="command",
    )

    unread = poll_messages(bus_store, consumer_cred, unread_only=True)
    assert len(unread) == 1

    unit = adapter.admit_task(unread[0])

    # Strict state verification: state is 'admitted', NEVER 'active' or 'running'
    assert unit.state == "admitted"
    assert unit.state != "active"
    assert unit.state != "running"
    assert unit.pid is None
    assert unit.started_at is None
    assert unit.completed_at is None
    assert unit.artifact_path is None
    assert unit.artifact_sha256 is None
    assert unit.unit_id in adapter.units

    # Verify event recorded in host_events.jsonl reflects admitted reservation
    events = query_host_events(events_dir=events_dir, event_type="task_admitted")
    assert len(events) == 1
    evt = events[0]
    assert evt["device_id"] == "windows-desktop"
    assert evt["task_id"] == "task-reserve-001"
    assert evt["details"]["state"] == "admitted"
    assert evt["details"]["state"] not in ("active", "running")


def test_spawn_worker_unit_executes_and_produces_artifact(tmp_path: Path) -> None:
    """Verifies worker spawn transitions state running -> completed, produces artifact with verifiable sha256."""
    bus_store = tmp_path / "bus_store"
    bus_store.mkdir(parents=True, mode=0o700)
    events_dir = tmp_path / "events"
    events_dir.mkdir(parents=True, mode=0o700)
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir(parents=True, mode=0o700)

    consumer_cred, _ = enroll_agent(bus_store, "consumer-agent", device_id="hetzner-rmthz")
    adapter = ConsumerExecutionAdapter(
        store_path=bus_store,
        cred=consumer_cred,
        events_dir=events_dir,
        artifacts_dir=artifacts_dir,
    )

    unit = ExecutionUnit(
        task_id="task-artifact-002",
        device_id="hetzner-rmthz",
        state="admitted",
    )
    adapter.units[unit.unit_id] = unit

    payload = {"benchmark": "scale-50", "iterations": 100}
    executed_unit = adapter.spawn_worker_unit(
        unit=unit,
        action="benchmark_run",
        payload=payload,
        runner_fn=_stub_runner,
    )

    # State transitions to completed; pid is no longer the adapter process pid
    assert executed_unit.state == "completed"
    assert executed_unit.pid is None
    assert executed_unit.launcher_task_id == "t-stub-task-artifact-002"
    assert executed_unit.controller_unit == "ql-ctl-t-stub-task-artifact-002.service"
    assert executed_unit.source_receipt["resolved_commit"] == "f" * 40
    assert executed_unit.started_at is not None
    assert executed_unit.completed_at is not None
    assert executed_unit.artifact_path is not None
    assert Path(executed_unit.artifact_path).is_file()

    # Provenance verification: verify SHA256 matches actual file on disk
    with open(executed_unit.artifact_path, "rb") as f:
        file_bytes = f.read()
    computed_sha = hashlib.sha256(file_bytes).hexdigest()
    assert executed_unit.artifact_sha256 == computed_sha

    # Verify task_spawned and task_completed events
    spawn_events = query_host_events(events_dir=events_dir, event_type="task_spawned")
    assert len(spawn_events) == 1
    assert spawn_events[0]["task_id"] == "task-artifact-002"
    assert spawn_events[0]["details"]["state"] == "running"
    assert spawn_events[0]["details"]["pid"] is None

    completed_events = query_host_events(events_dir=events_dir, event_type="task_completed")
    assert len(completed_events) == 1
    assert completed_events[0]["task_id"] == "task-artifact-002"
    assert completed_events[0]["details"]["artifact_sha256"] == computed_sha
    assert completed_events[0]["details"]["state"] == "completed"

    # Also test custom runner_fn execution
    def custom_worker(task_id: str, p: dict[str, Any]) -> dict[str, Any]:
        return {"custom_task": task_id, "result_val": p["x"] * 2}

    unit_custom = ExecutionUnit(
        task_id="task-custom-fn-003",
        device_id="hetzner-rmthz",
        state="admitted",
    )
    adapter.units[unit_custom.unit_id] = unit_custom
    res_custom = adapter.spawn_worker_unit(
        unit=unit_custom,
        action="multiply",
        payload={"x": 21},
        runner_fn=custom_worker,
    )
    assert res_custom.state == "completed"
    with open(res_custom.artifact_path, "r", encoding="utf-8") as f:
        artifact_json = json.load(f)
    assert artifact_json["result_val"] == 42


def test_head_cred_leak_fails_closed_without_execution(tmp_path: Path) -> None:
    """Verifies head.cred in payload raises GuardRejected, emits guard_rejected event, ACKs poison pill, and unit is never created or executed."""
    bus_store = tmp_path / "bus_store"
    bus_store.mkdir(parents=True, mode=0o700)
    events_dir = tmp_path / "events"
    events_dir.mkdir(parents=True, mode=0o700)
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir(parents=True, mode=0o700)

    consumer_cred, _ = enroll_agent(bus_store, "consumer-agent", device_id="hetzner-rmthz")
    client_cred, _ = enroll_agent(bus_store, "windows-client", device_id="windows-desktop")
    consumer_id = consumer_cred["identity"]["identity_id"]

    adapter = ConsumerExecutionAdapter(
        store_path=bus_store,
        cred=consumer_cred,
        events_dir=events_dir,
        artifacts_dir=artifacts_dir,
    )

    # Inject poison pill containing forbidden head credential
    bus = FileBus(bus_store)
    poison_msg = bus.send(
        sender_id=client_cred["identity"]["identity_id"],
        token=client_cred["token"],
        recipient_id=consumer_id,
        body="Command with leaked credentials",
        data={
            "task_id": "task-poison-leak-003",
            "device_id": "windows-desktop",
            "head.cred": "stolen-super-secret-token",
        },
        kind="command",
    )
    poison_msg_id = poison_msg.message_id

    unread = poll_messages(bus_store, consumer_cred, unread_only=True)
    assert len(unread) == 1

    # Fail-closed guard rejection
    with pytest.raises(GuardRejected):
        adapter.admit_task(unread[0])

    # Invariant: unit is never created or executed
    assert len(adapter.units) == 0
    assert len(list(artifacts_dir.glob("*.json"))) == 0

    # Invariant: guard_rejected event recorded in host_events.jsonl
    events = query_host_events(events_dir=events_dir, event_type="guard_rejected")
    assert len(events) == 1
    assert events[0]["device_id"] == "windows-desktop"
    assert events[0]["task_id"] == "task-poison-leak-003"
    assert events[0]["details"]["message_id"] == poison_msg_id
    assert events[0]["details"]["error_type"] == "GuardRejected"

    # Invariant: poison pill message was ACKed so consumer does not stall or loop
    sink_unread = poll_messages(bus_store, consumer_cred, unread_only=True)
    assert len(sink_unread) == 0


def test_correlated_reply_and_cursor_advancement(tmp_path: Path) -> None:
    """Verifies completion reply is delivered to caller over FileBus with unit_id, artifact path, and sha256; cursor advances and inboxes drain."""
    bus_store = tmp_path / "bus_store"
    bus_store.mkdir(parents=True, mode=0o700)
    events_dir = tmp_path / "events"
    events_dir.mkdir(parents=True, mode=0o700)
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir(parents=True, mode=0o700)

    consumer_cred, _ = enroll_agent(bus_store, "consumer-agent", device_id="hetzner-rmthz")
    client_cred, _ = enroll_agent(bus_store, "windows-client", device_id="windows-desktop")
    consumer_id = consumer_cred["identity"]["identity_id"]

    adapter = ConsumerExecutionAdapter(
        store_path=bus_store,
        cred=consumer_cred,
        events_dir=events_dir,
        artifacts_dir=artifacts_dir,
    )

    # Client sends request
    sent = send_message(
        bus_store,
        client_cred,
        recipient_id=consumer_id,
        body="Compute task alpha",
        data={"task_id": "task-compute-004", "device_id": "windows-desktop", "action": "compute"},
        kind="command",
    )
    sent_id = sent["message_id"]

    unread = poll_messages(bus_store, consumer_cred, unread_only=True)
    assert len(unread) == 1
    msg = unread[0]

    unit = adapter.admit_task(msg)
    adapter.spawn_worker_unit(unit, action="compute", payload=msg["data"], runner_fn=_stub_runner)

    # Send completion reply and advance cursor
    reply_outcome = adapter.send_completion_reply(
        message_id=msg["message_id"],
        sender_id=msg["sender_id"],
        unit=unit,
    )
    assert reply_outcome is not None

    # Consumer inbox cursor advanced; unread drains to 0
    consumer_unread = poll_messages(bus_store, consumer_cred, unread_only=True)
    assert len(consumer_unread) == 0

    # Client receives correlated reply
    client_unread = poll_messages(bus_store, client_cred, unread_only=True)
    assert len(client_unread) == 1
    reply_msg = client_unread[0]

    assert reply_msg["body"] == f"TASK-COMPLETED:{unit.task_id}"
    rep_data = reply_msg["data"]
    assert rep_data["status"] == "completed"
    assert rep_data["unit_id"] == unit.unit_id
    assert rep_data["task_id"] == unit.task_id
    assert rep_data["artifact_path"] == unit.artifact_path
    assert rep_data["artifact_sha256"] == unit.artifact_sha256
    assert rep_data["session_id"] is None
    assert rep_data["execution_target"] == "hetzner-rmthz"

    # Client ACK drains client inbox
    ack_message(bus_store, client_cred, reply_msg["message_id"])
    assert len(poll_messages(bus_store, client_cred, unread_only=True)) == 0


def test_unrelated_cursor_isolation_during_execution(tmp_path: Path) -> None:
    """Verifies sentinel worker inbox remains untouched at 1 unread message throughout consumer execution."""
    bus_store = tmp_path / "bus_store"
    bus_store.mkdir(parents=True, mode=0o700)
    events_dir = tmp_path / "events"
    events_dir.mkdir(parents=True, mode=0o700)
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir(parents=True, mode=0o700)

    consumer_cred, _ = enroll_agent(bus_store, "consumer-agent", device_id="hetzner-rmthz")
    client_cred, _ = enroll_agent(bus_store, "windows-client", device_id="windows-desktop")
    sentinel_cred, _ = enroll_agent(bus_store, "sentinel-worker", device_id="hetzner-rmthz")

    consumer_id = consumer_cred["identity"]["identity_id"]
    sentinel_id = sentinel_cred["identity"]["identity_id"]

    # 1. Send sentinel message to unrelated agent
    send_message(
        bus_store,
        client_cred,
        recipient_id=sentinel_id,
        body="Sentinel message - isolation check",
        data={"task_id": "task-sentinel-001"},
    )

    sentinel_unread_before = poll_messages(bus_store, sentinel_cred, unread_only=True)
    assert len(sentinel_unread_before) == 1
    sentinel_msg_id = sentinel_unread_before[0]["message_id"]

    # 2. Setup consumer adapter with stubbed launcher runner
    adapter = ConsumerExecutionAdapter(
        store_path=bus_store,
        cred=consumer_cred,
        events_dir=events_dir,
        artifacts_dir=artifacts_dir,
        launcher_runner=_stub_runner,
    )

    # 3. Client sends 3 separate messages to consumer
    for i in range(3):
        send_message(
            bus_store,
            client_cred,
            recipient_id=consumer_id,
            body=f"Task {i}",
            data={"task_id": f"task-consumer-{i}", "device_id": "windows-desktop"},
            kind="command",
        )

    assert len(poll_messages(bus_store, consumer_cred, unread_only=True)) == 3

    # 4. Consumer polls and executes all messages
    outcomes = adapter.poll_and_execute()
    assert len(outcomes) == 3
    for oc in outcomes:
        assert oc["status"] == "completed"

    # Consumer inbox is completely drained
    assert len(poll_messages(bus_store, consumer_cred, unread_only=True)) == 0

    # 5. Sentinel worker inbox must remain untouched at 1 unread message
    sentinel_unread_after = poll_messages(bus_store, sentinel_cred, unread_only=True)
    assert len(sentinel_unread_after) == 1
    assert sentinel_unread_after[0]["message_id"] == sentinel_msg_id


def test_unknown_device_admission_rejection(tmp_path: Path) -> None:
    """Verifies tasks from unregistered devices raise UnknownDevice and record rejection event."""
    bus_store = tmp_path / "bus_store"
    bus_store.mkdir(parents=True, mode=0o700)
    events_dir = tmp_path / "events"
    events_dir.mkdir(parents=True, mode=0o700)
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir(parents=True, mode=0o700)

    consumer_cred, _ = enroll_agent(bus_store, "consumer-agent", device_id="hetzner-rmthz")
    adapter = ConsumerExecutionAdapter(
        store_path=bus_store,
        cred=consumer_cred,
        events_dir=events_dir,
        artifacts_dir=artifacts_dir,
    )

    msg = {
        "message_id": "msg-rogue-001",
        "sender_id": "rogue-agent",
        "body": "Run payload on unregistered device",
        "data": {
            "task_id": "task-rogue-001",
            "device_id": "unregistered-rogue-host",
        },
    }

    with pytest.raises(UnknownDevice):
        adapter.admit_task(msg)

    events = query_host_events(events_dir=events_dir, event_type="admission_rejected")
    assert len(events) == 1
    assert events[0]["device_id"] == "unregistered-rogue-host"
    assert events[0]["task_id"] == "task-rogue-001"
    assert events[0]["details"]["error_type"] == "UnknownDevice"


def test_cli_execution_once_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies CLI execution with --once --json flags."""
    bus_store = tmp_path / "bus_store"
    bus_store.mkdir(parents=True, mode=0o700)
    events_dir = tmp_path / "events"
    events_dir.mkdir(parents=True, mode=0o700)
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir(parents=True, mode=0o700)

    consumer_cred, cred_path = enroll_agent(bus_store, "consumer-agent", device_id="hetzner-rmthz")
    client_cred, _ = enroll_agent(bus_store, "windows-client", device_id="windows-desktop")

    send_message(
        bus_store,
        client_cred,
        recipient_id=consumer_cred["identity"]["identity_id"],
        body="CLI test task",
        data={"task_id": "task-cli-001", "device_id": "windows-desktop"},
        kind="command",
    )

    class StubRunner:
        def __call__(self, task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
            return {"status": "completed", "launcher_task_id": f"t-cli-{task_id}"}

    monkeypatch.setattr(adapter_module, "LauncherRequestRunner", StubRunner)
    ret = main([
        "--store", str(bus_store),
        "--cred", str(cred_path),
        "--events-dir", str(events_dir),
        "--artifacts-dir", str(artifacts_dir),
        "--once",
        "--json",
    ])
    assert ret == 0

    # Verify task was executed and consumer inbox drained
    unread = poll_messages(bus_store, consumer_cred, unread_only=True)
    assert len(unread) == 0

    # Verify deliverable artifact was written
    artifact_file = artifacts_dir / "task-cli-001.json"
    assert artifact_file.is_file()


def test_default_runner_is_launcher_backed_not_synthesized(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies the default execution path uses launcher request/status; no synthesized success."""
    bus_store = tmp_path / "bus_store"
    bus_store.mkdir(parents=True, mode=0o700)
    events_dir = tmp_path / "events"
    events_dir.mkdir(parents=True, mode=0o700)
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir(parents=True, mode=0o700)

    request_json = json.dumps({
        "task_id": "t-launcher-1",
        "controller_unit": "ql-ctl-t-launcher-1.service",
        "status": "queued-or-starting",
        "profile": "model-task",
        "timeout": 600.0,
        "source_receipt": {"resolved_commit": "a" * 40, "repo_path": "/tmp/wt"},
    })
    status_json = json.dumps({"id": "t-launcher-1", "state": "accepted", "reviewer": "rev-1"})
    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(list(cmd))
        if "request" in cmd:
            return _fake_completed_process(stdout=request_json)
        if "status" in cmd:
            return _fake_completed_process(stdout=status_json)
        raise AssertionError(f"unexpected cmd {cmd}")

    monkeypatch.setattr(adapter_module.subprocess, "run", fake_run)

    consumer_cred, _ = enroll_agent(bus_store, "consumer-agent", device_id="hetzner-rmthz")
    adapter = ConsumerExecutionAdapter(
        store_path=bus_store,
        cred=consumer_cred,
        events_dir=events_dir,
        artifacts_dir=artifacts_dir,
    )
    assert isinstance(adapter.launcher_runner, LauncherRequestRunner)

    unit = ExecutionUnit(task_id="task-launcher-001", device_id="hetzner-rmthz", state="admitted")
    adapter.units[unit.unit_id] = unit
    executed = adapter.spawn_worker_unit(
        unit=unit,
        action="compute",
        payload={"goal": "compute payload", "cwd": str(tmp_path / "wt"), "profile": "model-task"},
    )

    assert executed.state == "completed"
    assert executed.pid is None
    assert executed.launcher_task_id == "t-launcher-1"
    assert executed.controller_unit == "ql-ctl-t-launcher-1.service"
    assert executed.source_receipt["resolved_commit"] == "a" * 40

    assert "request" in calls[0]
    gi = calls[0].index("--goal")
    assert calls[0][gi + 1] == "compute payload"
    ci = calls[0].index("--cwd")
    assert calls[0][ci + 1].endswith("wt")
    pi = calls[0].index("--profile")
    assert calls[0][pi + 1] == "model-task"
    assert "status" in calls[1] and "--id" in calls[1] and "t-launcher-1" in calls[1]

    with open(executed.artifact_path, "r", encoding="utf-8") as f:
        art = json.load(f)
    assert art["launcher_status"]["state"] == "accepted"
    assert art["consumer_task_id"] == "task-launcher-001"

    launched_events = query_host_events(events_dir=events_dir, event_type="task_launched")
    assert len(launched_events) == 1
    assert launched_events[0]["details"]["launcher_task_id"] == "t-launcher-1"
    assert launched_events[0]["details"]["controller_unit"] == "ql-ctl-t-launcher-1.service"


def test_launcher_runner_maps_failed_state_to_unit_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies launcher failed state maps to unit failure with a truthful error."""
    bus_store = tmp_path / "bus_store"
    bus_store.mkdir(parents=True, mode=0o700)
    events_dir = tmp_path / "events"
    events_dir.mkdir(parents=True, mode=0o700)
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir(parents=True, mode=0o700)

    request_json = json.dumps({"task_id": "t-launcher-2", "controller_unit": "ql-ctl-2.service", "status": "queued-or-starting"})
    status_json = json.dumps({"id": "t-launcher-2", "state": "failed", "reason": "admission rejected: no route"})

    def fake_run(cmd, **kwargs):
        if "request" in cmd:
            return _fake_completed_process(stdout=request_json)
        if "status" in cmd:
            return _fake_completed_process(stdout=status_json)
        raise AssertionError(f"unexpected cmd {cmd}")

    monkeypatch.setattr(adapter_module.subprocess, "run", fake_run)

    consumer_cred, _ = enroll_agent(bus_store, "consumer-agent", device_id="hetzner-rmthz")
    adapter = ConsumerExecutionAdapter(
        store_path=bus_store, cred=consumer_cred,
        events_dir=events_dir, artifacts_dir=artifacts_dir,
    )
    unit = ExecutionUnit(task_id="task-launcher-002", device_id="hetzner-rmthz", state="admitted")
    adapter.units[unit.unit_id] = unit

    with pytest.raises(RuntimeError, match="failed"):
        adapter.spawn_worker_unit(
            unit=unit, action="compute",
            payload={"goal": "g", "cwd": str(tmp_path)},
        )

    assert unit.state == "failed"
    assert unit.artifact_path is None
    failed_events = query_host_events(events_dir=events_dir, event_type="task_failed")
    assert len(failed_events) == 1
    assert "no route" in failed_events[0]["details"]["error"]


def test_launcher_runner_poll_expiry_is_honest_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies a non-terminal launcher task at poll-window expiry fails the unit with the last real state."""
    bus_store = tmp_path / "bus_store"
    bus_store.mkdir(parents=True, mode=0o700)
    events_dir = tmp_path / "events"
    events_dir.mkdir(parents=True, mode=0o700)
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir(parents=True, mode=0o700)

    request_json = json.dumps({"task_id": "t-launcher-3", "controller_unit": "ql-ctl-3.service", "status": "queued-or-starting"})
    status_json = json.dumps({"id": "t-launcher-3", "state": "completed-awaiting-review"})

    def fake_run(cmd, **kwargs):
        if "request" in cmd:
            return _fake_completed_process(stdout=request_json)
        if "status" in cmd:
            return _fake_completed_process(stdout=status_json)
        raise AssertionError(f"unexpected cmd {cmd}")

    monkeypatch.setattr(adapter_module.subprocess, "run", fake_run)

    consumer_cred, _ = enroll_agent(bus_store, "consumer-agent", device_id="hetzner-rmthz")
    adapter = ConsumerExecutionAdapter(
        store_path=bus_store, cred=consumer_cred,
        events_dir=events_dir, artifacts_dir=artifacts_dir,
        launcher_runner=LauncherRequestRunner(
            launcher_root=tmp_path, poll_interval_s=0.01, poll_window_s=0.3,
        ),
    )
    unit = ExecutionUnit(task_id="task-launcher-003", device_id="hetzner-rmthz", state="admitted")
    adapter.units[unit.unit_id] = unit

    with pytest.raises(RuntimeError, match="still in state 'completed-awaiting-review'"):
        adapter.spawn_worker_unit(
            unit=unit, action="compute",
            payload={"goal": "g", "cwd": str(tmp_path)},
        )
    assert unit.state == "failed"


def test_launcher_runner_fail_closed_missing_params(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies missing goal or cwd fails closed before any launcher subprocess is spawned."""
    def no_spawn(cmd, **kwargs):
        raise AssertionError("subprocess must not be called for invalid payloads")

    monkeypatch.setattr(adapter_module.subprocess, "run", no_spawn)

    runner = LauncherRequestRunner(launcher_root=tmp_path)
    with pytest.raises(ValueError, match="goal"):
        runner("task-x", {})
    with pytest.raises(ValueError, match="cwd"):
        runner("task-x", {"goal": "some goal"})


def test_launcher_request_nonzero_exit_fails_unit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies a non-zero launcher request exit fails the unit with the captured stderr."""
    bus_store = tmp_path / "bus_store"
    bus_store.mkdir(parents=True, mode=0o700)
    events_dir = tmp_path / "events"
    events_dir.mkdir(parents=True, mode=0o700)
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir(parents=True, mode=0o700)

    def fake_run(cmd, **kwargs):
        return _fake_completed_process(returncode=1, stdout="", stderr="admission: unknown profile boom")

    monkeypatch.setattr(adapter_module.subprocess, "run", fake_run)

    consumer_cred, _ = enroll_agent(bus_store, "consumer-agent", device_id="hetzner-rmthz")
    adapter = ConsumerExecutionAdapter(
        store_path=bus_store, cred=consumer_cred,
        events_dir=events_dir, artifacts_dir=artifacts_dir,
    )
    unit = ExecutionUnit(task_id="task-launcher-004", device_id="hetzner-rmthz", state="admitted")
    adapter.units[unit.unit_id] = unit

    with pytest.raises(RuntimeError, match="exited rc=1"):
        adapter.spawn_worker_unit(
            unit=unit, action="compute",
            payload={"goal": "g", "cwd": str(tmp_path)},
        )
    assert unit.state == "failed"
    assert "unknown profile boom" in (unit.error or "")
