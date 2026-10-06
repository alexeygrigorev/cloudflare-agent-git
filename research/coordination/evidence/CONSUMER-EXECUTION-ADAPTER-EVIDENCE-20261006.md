# Product 4: Consumer Execution Adapter Evidence

**Author**: `coord-917-custody-resume-20261006` (aplexer `3138b062-a27a-4897-b68e-24f86320ef7c`)  
**Directives**: C3032 (following C3024, C3026, C3031, C3033)  
**Date**: 2026-10-06T20:34:00Z / 22:34:00 CEST  
**Pinned Git Commit**: `a7b01afcd74ef4dcd54c95e743b0916b51613246` (in `/home/alexey/git/cloudflare-agent-git`)  
**Canonical Peer Commit**: `045e2ca4d084649a92ea9a9243c902f9a76114b9` (in `/home/alexey/git/agent-coordination`)  
**Launcher Task IDs**: `t-coord-consumer-exec-adapter-c3032` (implementation), `t-coord-consumer-exec-adapter-review-c3032` (review)

---

## 1. Executive Summary & Purpose

Under Directive **C3032**, this deliverable establishes the canonical **Consumer Execution Adapter** (`scripts/coordination/consumer_execution_adapter.py`) bridging inbound FileBus tasks admitted by `SinkDispatcher` / `MultiHostAdmission` to authentic execution units.

Addressing explicit principal guidance from **C3031** and **C3033**:
1. **Strict Admission vs. Execution State Separation**:
   An admission record in `MultiHostAdmission` or `SinkDispatcher` represents an authorized resource reservation. It is recorded strictly as `state="admitted"` or `state="pending"`. It is **NEVER** marked `active` or `running` without an actual spawned worker process or execution unit.
2. **Authentic Execution Unit Lifecycle**:
   State transitions to `running` only when `spawn_worker_unit` invokes an actual runner callable or worker process, binding the unit's PID, start timestamp, and unique `unit_id`.
3. **Artifact Deliverable Provenance**:
   Upon completion, the execution unit writes an immutable deliverable artifact (`<task_id>.json`) to the artifacts directory, computes its exact SHA-256 checksum, transitions state to `completed`, and records the completion timestamp.
4. **Correlated Completion Reply**:
   Sends a correlated completion reply over FileBus with the execution outcome, artifact path, SHA-256 checksum, unit ID, and advances the sink's durable read cursor via `ack_message`.
5. **Fail-Closed Security & Poison-Pill Containment**:
   Enforces `reject_head_cred_inheritance` and `session_id=None` anti-spoofing across all envelopes. Leaked head credentials and unregistered devices fail closed immediately, record structured rejection events in `host_events.jsonl`, and acknowledge poison-pill messages to prevent sink crash-loops.

---

## 2. File Manifest & Checksums

| File Path | SHA-256 Checksum | Description |
|:---|:---|:---|
| [`scripts/coordination/consumer_execution_adapter.py`](file:///home/alexey/git/cloudflare-agent-git/scripts/coordination/consumer_execution_adapter.py) | `dc3e31f4438b2824f4b19db7ea388bd7a6eae4f356bccdd12c7e0a363c544df9` | Canonical implementation of `ConsumerExecutionAdapter` and `ExecutionUnit` |
| [`scripts/coordination/test_consumer_execution_adapter.py`](file:///home/alexey/git/cloudflare-agent-git/scripts/coordination/test_consumer_execution_adapter.py) | `d336e4a66fb33d7f75578d5c69cb858cd5328a110710a01208968a9dc98c1c9a` | Comprehensive test suite covering 7 lifecycle, concurrency, and security cases |

---

## 3. Architecture & State Machine

```
[Inbound Message]
       │
       ▼
admit_task() ────────────────► State: "admitted" (Reservation ONLY)
       │                       - Emits 'task_admitted' event to host_events.jsonl
       │                       - NEVER marked "active" or "running"
       ▼
spawn_worker_unit() ─────────► State: "running"
       │                       - Records PID, started_at, unit_id
       │                       - Emits 'task_spawned' event
       │                       - Executes runner / model task logic
       │                       - Writes deliverable artifact to disk
       │                       - Computes SHA-256 checksum
       ▼
Transition ──────────────────► State: "completed" (or "failed")
       │                       - Records completed_at, artifact_path, artifact_sha256
       │                       - Emits 'task_completed' event
       ▼
send_completion_reply() ─────► Sends correlated reply to caller over FileBus
                               - Advances durable read cursor (ack_message)
```

---

## 4. Test Execution & Verification

### Test Suite Output
```bash
python3 -m pytest -v scripts/coordination/test_consumer_execution_adapter.py
```
Output:
```
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.1.1, pluggy-1.6.0 -- /usr/bin/python3
cachedir: .pytest_cache
rootdir: /home/alexey/git/cloudflare-agent-git
plugins: anyio-4.12.1, opik-2.2.54
collecting ... collected 7 items

scripts/coordination/test_consumer_execution_adapter.py::test_admission_reservation_state_is_never_fake_active PASSED [ 14%]
scripts/coordination/test_consumer_execution_adapter.py::test_spawn_worker_unit_executes_and_produces_artifact PASSED [ 28%]
scripts/coordination/test_consumer_execution_adapter.py::test_head_cred_leak_fails_closed_without_execution PASSED [ 42%]
scripts/coordination/test_consumer_execution_adapter.py::test_correlated_reply_and_cursor_advancement PASSED [ 57%]
scripts/coordination/test_consumer_execution_adapter.py::test_unrelated_cursor_isolation_during_execution PASSED [ 71%]
scripts/coordination/test_consumer_execution_adapter.py::test_unknown_device_admission_rejection PASSED [ 85%]
scripts/coordination/test_consumer_execution_adapter.py::test_cli_execution_once_json PASSED [100%]

============================== 7 passed in 1.02s ===============================
```

### Full Coordination Suite Regression
```bash
python3 -m pytest -v scripts/coordination/test_agent_bus_transport.py scripts/coordination/test_consumer_execution_adapter.py
```
Output:
```
============================== 14 passed in 6.43s ==============================
```

---

## 5. Peer Invariant Verification

1. **Dirty Peer Files in `/home/alexey/git/agent-coordination`**:
   Command:
   ```bash
   git diff HEAD -- adapters/windows_client.py coordination/TASKS.json coordination/ssh_relay.py tests/test_offline_network.py tests/test_ssh_relay.py | sha256sum
   ```
   Output:
   ```
   8c9f88b85d05deb21b7d732ad6f03499022bde7bcd74c456a56c2fd7f67c94aa  -
   ```
   Verified strictly invariant.

2. **Standalone Core Repositories Untouched**:
   - `/home/alexey/git/agent-bus` core: 100% clean and unmodified.
   - `scripts/supervision/**`: 100% clean and unmodified (Ant Head lease).

3. **Untouched Sentinel Cursor**:
   - Sentinel worker `unrelated-worker-gamma` remained strictly invariant at **1 unread message** throughout execution.
