# Independent Peer Review: Autonomous Sink Dispatcher Service & Multi-Host Admission Integration

- **Document Reference**: `REV-SINK-DISPATCHER-C3012`
- **Directive**: Directive C3012
- **Task Reference**: Task `t-coord-sink-dispatcher-review-c3012`
- **Reviewed Task**: Task `t-coord-sink-dispatcher-c3012`
- **Product**: Product 4 (Cross-computer Agent Coordination)
- **Review Date**: 2026-10-06T21:52:00+02:00 (Europe/Berlin) / 2026-10-06T19:52:00Z
- **Reviewer Identity**: Distinct Independent Peer Reviewer for Product 4 (`antigravity-cli`, conversation `f68ea2b3-79d6-423f-9e0a-5d9bfad4bd97`)
- **Reviewer Role**: Distinct Independent Reviewer for Autonomous Sink Dispatcher Service & Multi-Host Admission Integration
- **Caller / Head**: Product 4 Project Head (`764358a8-1b4e-49c6-845a-9b79bf3ba536` / `coord-917-custody-resume-20261006`)
- **Evaluated Target Commit**: `045e2ca4d084649a92ea9a9243c902f9a76114b9` (`045e2ca`, pushed to `origin/codex/role-failover-20261006`)
- **Target Repository**: `/home/alexey/git/agent-coordination`
- **Governing Policies**: Scale-50 Recovery Plan (`coordination/SCALE50-RECOVERY-PLAN.md`), Operating Model (`coordination/OPERATING-MODEL.md`), Resource Policy (`coordination/RESOURCE-POLICY.md`)
- **Definitive Independent Verdict**: **ACCEPT** (Unconditional Pass across architecture audit, fail-closed security assertions, poison-pill containment, compatibility suites, full 94-test regression pass, and strict peer invariant preservation)

---

## 1. Executive Summary & Verdict Rationale

This independent peer review evaluates the Autonomous Sink Dispatcher Service and Multi-Host Admission Integration implemented under **Directive C3012** for Product 4 (Cross-computer Agent Coordination). The reviewed service (`coordination/sink_dispatcher.py`) provides the autonomous, decoupled ingestion daemon for `coord-primary-sink` running on the primary coordinator host (`hetzner-rmthz`). It continuously polls inbound `FileBus` envelopes, validates multi-host task admission against `MultiHostAdmission` (`coordination/host_interface.py`), enforces strict fail-closed security boundaries (rejecting head credential inheritance and unregistered devices), records auditable structured JSON events to `host_events.jsonl`, dispatches correlated reply receipts to senders, and deterministically advances the durable `FileBus` read cursor.

### Definitive Independent Verdict: ACCEPT

The implementation and test suite in commit `045e2ca` meet all architectural, operational, and security criteria:
1. **Robust SinkDispatcher Architecture**:
   - Clean, decoupled object model accepting explicit `store_path`, `cred` (as `dict`, JSON string, or file `Path`), optional pre-configured `admission` instance, and `events_dir`.
   - Complete extraction of message metadata (`message_id`, `sender_id`, `body`, and structured payload `data`).
   - Strict FIFO ordering in `poll_and_dispatch` sorted deterministically by `(created_at, seq)`.
   - Full-featured CLI interface supporting `--store`, `--cred`, `--registry`, `--events-dir`, `--once` / subcommand `once`, `--max-messages`, `--interval`, and `--json`.
2. **MultiHostAdmission Integration & Fail-Closed Guards**:
   - Delegates admission verification directly to `MultiHostAdmission._admit_host_task_impl(device_id, task_id, data, reject_on_cred=True)`.
   - Enforces anti-spoofing and sessionless invariants (`session_id=None` across envelopes, admissions, and replies), preventing synthetic aplexer session leakage.
   - Enforces fail-closed rejection of `head.cred` in both payload dictionaries and raw string bodies via `reject_head_cred_inheritance(..., reject=True)`.
3. **Resilient Poison-Pill Containment**:
   - Catches `UnknownDevice`, `GuardRejected`, and `ValueError` without terminating the process or crashing the polling loop.
   - Emits structured `admission_rejected` or `guard_rejected` diagnostic events into `host_events.jsonl`.
   - Explicitly acknowledges (`ack_message`) poison-pill messages in the `FileBus` store, advancing the read cursor and preventing infinite replay stall loops.
4. **Correlated Bidirectional Replies & Cursor Progression**:
   - For handshakes, commands, or explicit `reply_requested=True`, constructs and delivers correlated reply envelopes with `reply_to=message_id`, `execution_target="hetzner-rmthz"`, and idempotency keys `reply:{message_id}`.
   - Calls `ack_message` on successful admission, draining unread inboxes cleanly to 0.
5. **Clean Verification & Invariant Preservation**:
   - All 5 tests in `tests/test_sink_dispatcher.py` pass cleanly.
   - All 17 tests in compatibility suites (`test_host_interface.py`, `test_agent_bus_client.py`) pass cleanly.
   - Full repository test suite (94 tests across 19 modules) passes 100% cleanly in 20.83s.
   - Preserved dirty peer files in `/home/alexey/git/agent-coordination` strictly match the required invariant diff SHA-256 (`8c9f88b85d05deb21b7d732ad6f03499022bde7bcd74c456a56c2fd7f67c94aa`).
   - Core `agent-bus` and `scripts/supervision/**` remain 100% untouched.

---

## 2. Target Commit & Code Delta Inspection

### 2.1 Commit Information
- **Repository**: `/home/alexey/git/agent-coordination`
- **Commit Pin**: `045e2ca4d084649a92ea9a9243c902f9a76114b9` (`045e2ca`)
- **Author**: Alexey Grigorev <alexey.s.grigoriev@gmail.com>
- **Date**: Tue Oct 6 21:47:59 2026 +02:00
- **Commit Message**: `coord: implement autonomous sink dispatcher service and multi-host admission integration (C3012)`

### 2.2 Modified Files
| File Path | Additions | Deletions | Description |
| :--- | :--- | :--- | :--- |
| `coordination/sink_dispatcher.py` | +369 | 0 | Autonomous Sink Dispatcher Service implementation and CLI |
| `tests/test_sink_dispatcher.py` | +399 | 0 | Comprehensive pytest suite covering admission, rejections, FIFO progression, and CLI |

---

## 3. Detailed Architectural & Security Assessment

### 3.1 SinkDispatcher Architecture & Initialization
The `SinkDispatcher` class (`coordination/sink_dispatcher.py`) provides a clean separation of concerns:
```python
class SinkDispatcher:
    def __init__(
        self,
        store_path: Path | str | None,
        cred: dict[str, Any] | str | Path,
        admission: MultiHostAdmission | None = None,
        events_dir: Path | str | None = None,
    ) -> None:
```
- **Credential Flexibility**: Ingests `cred` as an in-memory dictionary, inline JSON string, or filesystem path, enforcing fail-closed `FileNotFoundError` or `TypeError` on malformed inputs.
- **Store Path Resolution**: Gracefully resolves `store_path` from explicit constructor argument or extracts it from the credential's `store` field.
- **Admission & Event Directory Alignment**: Seamlessly binds to an existing `MultiHostAdmission` instance or instantiates one with the specified `events_dir`.

### 3.2 Dispatch Pipeline & Message Intake
The core dispatch method `dispatch_message(msg)` handles heterogeneous payloads safely:
1. **Defensive Ingestion**: Extracts `message_id`, `sender_id`, and `body`. Payload `data` can be `None`, a pre-parsed dictionary, or a JSON-encoded string; strings are safely parsed via `json.loads` with a fallback `{"raw": ...}` wrapper to prevent unhandled deserialization crashes.
2. **Device & Task Resolution**: Derives `device_id` from `data.get("device_id")` or `data.get("origin_device")`, defaulting to `"unknown"`. Derives `task_id` from `data.get("task_id")`, defaulting to `f"msg:{message_id}"`.
3. **Fail-Closed Credential Leak Guard**:
   ```python
   if data:
       try:
           reject_head_cred_inheritance(data, reject=True)
       except ValueError as exc:
           raise GuardRejected(str(exc)) from exc
   if body:
       try:
           reject_head_cred_inheritance({"body": body}, reject=True)
       except ValueError as exc:
           raise GuardRejected(str(exc)) from exc
   ```
   Both the structured payload and message body are scrutinized against `reject_head_cred_inheritance` with `reject=True`. Any attempt to pass `head.cred` or `head_cred` raises `GuardRejected`.
4. **Admission Enforcement**: Calls `self.admission._admit_host_task_impl(device_id, task_id, data, reject_on_cred=True)`.

### 3.3 Poison-Pill Containment & Fail-Safe Cursor Progression
In message queue architectures, malformed or unauthorized messages can become "poison pills" that crash consumers on every attempt, stalling the entire pipeline. `SinkDispatcher` handles this cleanly:
- On `(UnknownDevice, GuardRejected, ValueError)`:
  - Classifies the event type: `guard_rejected` for guard/value failures, `admission_rejected` for unknown devices.
  - Emits structured event to `host_events.jsonl` containing reason, error type, `message_id`, and `sender_id`.
  - **Crucial containment step**: Calls `ack_message(self.store_path, self.cred, message_id=message_id)`.
  - Result: The offending message is committed on the sink's cursor and will not be re-polled, allowing subsequent valid messages to proceed without operator intervention.
  - Returns `{"status": "rejected", "reason": ..., "message_id": ..., "device_id": ...}`.

### 3.4 Correlated Replying & Successful Admission
On successful admission:
- Emits `task_admitted` event to `host_events.jsonl` containing `delivery`, `execution_target`, `session_id`, `message_id`, and `sender_id`.
- Checks if a reply is warranted (`data.get("reply_requested")` or `msg.get("kind") in ("command", "handshake")`):
  - Formulates reply payload:
    ```python
    reply_data = {
        "handshake": data.get("handshake"),
        "status": "admitted",
        "sink_id": sink_id,
        "reply_to_message_id": message_id,
        "session_id": None,
        "execution_target": "hetzner-rmthz",
    }
    ```
  - Emits reply via `reply_message` with `reply_to=message_id`, body `f"{body}-ACK"`, and deterministic idempotency key `reply:{message_id}`.
- Acknowledges message (`ack_message`) in `FileBus`.
- Returns structured outcome `{"status": "admitted", "message_id": ..., "device_id": ..., "reply_sent": ..., "event_id": ...}`.

### 3.5 FIFO Ordering & Polling Mechanics
In `poll_and_dispatch(max_messages=20, unread_only=True)`:
- Inbound messages are sorted by `(created_at, seq)`:
  ```python
  sorted_messages = sorted(
      messages,
      key=lambda m: (m.get("created_at") or "", m.get("seq", 0)),
  )
  ```
- Strictly processes batches up to `max_messages`, returning structured per-message outcomes.

### 3.6 CLI Interface & Operational Usability
The CLI parser (`build_cli_parser`) and entrypoint (`main`) support headless production execution:
- Flags: `--store`, `--cred` (required), `--registry`, `--events-dir`, `--once` / positional `once`, `--max-messages`, `--interval`, and `--json`.
- In `once` mode, outputs structured summary:
  ```json
  {
    "status": "ok",
    "count": <int>,
    "dispatched_count": <int>,
    "outcomes": [...]
  }
  ```
- In loop mode, sleeps for `--interval` seconds and streams dispatched batches formatted as JSON.

---

## 4. Negative Security & Boundary Verification

The test suite in `tests/test_sink_dispatcher.py` comprehensively exercises negative security cases:

| Scenario / Negative Case | Input Trigger | Observed Behavior | Verification Outcome |
| :--- | :--- | :--- | :--- |
| **Valid Cross-Host Handshake** | Windows desktop (`windows-desktop`) sends typed `handshake` ping `AC-WIN-HETZ-001` | Admitted, `task_admitted` emitted, correlated ACK reply sent to Windows sender, sink cursor drained | **PASSED** (`test_sink_dispatcher_admit_valid_handshake`) |
| **Unknown Device Rejection** | Client sends message claiming `device_id="rogue-unregistered-device-999"` | Rejected with `UnknownDevice`, `admission_rejected` emitted to `host_events.jsonl`, poison pill ACKed, zero replies sent | **PASSED** (`test_sink_dispatcher_rejects_unknown_device`) |
| **Head Credential Leak Rejection** | Message payload or body contains forbidden `"head.cred": "stolen-token"` | Rejected with `GuardRejected("head_cred_inheritance_rejected")`, `guard_rejected` emitted, message ACKed, zero replies sent | **PASSED** (`test_sink_dispatcher_rejects_head_cred_leak`) |
| **FIFO Cursor Drainage** | 4 messages sent sequentially, dispatched in batches of 2 | Dispatched in strict order `task-seq-1..4`, remaining cursor drops from 4 -> 2 -> 0 | **PASSED** (`test_sink_dispatcher_fifo_cursor_progression`) |
| **CLI Execution Modes** | CLI invoked with `--once` flag and `once` positional command | Dispatches message, outputs structured JSON to stdout, drains inbox | **PASSED** (`test_sink_dispatcher_cli_once`) |

---

## 5. Test Execution Results & Command Output

### 5.1 Dedicated Sink Dispatcher Suite
```bash
$ pytest -v tests/test_sink_dispatcher.py
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.1.1, pluggy-1.6.0
rootdir: /home/alexey/git/agent-coordination
configfile: pyproject.toml
plugins: anyio-4.12.1, opik-2.2.54
collecting ... collected 5 items

tests/test_sink_dispatcher.py::test_sink_dispatcher_admit_valid_handshake PASSED [ 20%]
tests/test_sink_dispatcher.py::test_sink_dispatcher_rejects_unknown_device PASSED [ 40%]
tests/test_sink_dispatcher.py::test_sink_dispatcher_rejects_head_cred_leak PASSED [ 60%]
tests/test_sink_dispatcher.py::test_sink_dispatcher_fifo_cursor_progression PASSED [ 80%]
tests/test_sink_dispatcher.py::test_sink_dispatcher_cli_once PASSED      [100%]

============================== 5 passed in 0.67s ===============================
```

### 5.2 MultiHostAdmission & AgentBusClient Compatibility Suites
```bash
$ pytest -v tests/test_host_interface.py tests/test_agent_bus_client.py
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.1.1, pluggy-1.6.0
rootdir: /home/alexey/git/agent-coordination
configfile: pyproject.toml
plugins: anyio-4.12.1, opik-2.2.54
collecting ... collected 17 items

tests/test_host_interface.py::test_device_registry_loading PASSED         [  5%]
tests/test_host_interface.py::test_memory_limit_parsing PASSED            [ 11%]
tests/test_host_interface.py::test_admit_host_task_windows PASSED         [ 17%]
tests/test_host_interface.py::test_admit_host_task_hetzner PASSED         [ 23%]
tests/test_host_interface.py::test_host_event_emission_and_query PASSED  [ 29%]
tests/test_agent_bus_client.py::test_enroll_agent PASSED                  [ 35%]
tests/test_agent_bus_client.py::test_send_and_poll_messages PASSED        [ 41%]
tests/test_agent_bus_client.py::test_reply_message PASSED                 [ 47%]
tests/test_agent_bus_client.py::test_ack_message PASSED                   [ 52%]
tests/test_agent_bus_client.py::test_reject_head_cred_inheritance PASSED  [ 58%]
tests/test_agent_bus_client.py::test_offline_spool_enqueue_and_flush PASSED [ 64%]
tests/test_agent_bus_client.py::test_offline_spool_idempotency_conflict PASSED [ 70%]
tests/test_agent_bus_client.py::test_offline_spool_prune_and_stats PASSED [ 76%]
tests/test_agent_bus_client.py::test_cli_enroll PASSED                    [ 82%]
tests/test_agent_bus_client.py::test_cli_send_and_poll PASSED             [ 88%]
tests/test_agent_bus_client.py::test_cli_spool_and_flush PASSED           [ 94%]
tests/test_agent_bus_client.py::test_cli_reject_head_cred PASSED          [100%]

============================== 17 passed in 2.76s ==============================
```

### 5.3 Full Repository Regression Suite
```bash
$ pytest -v
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.1.1, pluggy-1.6.0
rootdir: /home/alexey/git/agent-coordination
configfile: pyproject.toml
testpaths: tests
plugins: anyio-4.12.1, opik-2.2.54
collecting ... collected 94 items

tests/test_adapter_cli.py .                                              [  1%]
tests/test_agent_bus_client.py ............                              [ 13%]
tests/test_bus.py .....                                                  [ 19%]
tests/test_bus_cli_host_addressing.py ......                             [ 25%]
tests/test_bus_dogfood.py .                                              [ 26%]
tests/test_cursors.py ...                                                [ 29%]
tests/test_device_registry.py .....                                      [ 35%]
tests/test_envelope.py ..                                                [ 37%]
tests/test_failover_bridge.py ......                                     [ 43%]
tests/test_guards.py ...                                                 [ 46%]
tests/test_host_interface.py .....                                       [ 52%]
tests/test_offline_network.py .                                          [ 53%]
tests/test_ql_consumer_fencing.py ......                                 [ 59%]
tests/test_quorum_authority.py .....                                     [ 64%]
tests/test_role_failover.py ..............                               [ 79%]
tests/test_sessionless_worker_bus.py .......                             [ 87%]
tests/test_sink_dispatcher.py .....                                      [ 92%]
tests/test_ssh_relay.py ......                                           [ 98%]
tests/test_worker_bus_cli.py .                                           [100%]

============================= 94 passed in 20.83s ==============================
```

---

## 6. Peer Invariants & Workspace Boundary Verification

### 6.1 Preserved Dirty Peer Files Invariant Hash
In accordance with governance rules, the 5 existing working tree modifications in `/home/alexey/git/agent-coordination` were audited before and after testing:
```bash
$ git diff HEAD -- adapters/windows_client.py coordination/TASKS.json coordination/ssh_relay.py tests/test_offline_network.py tests/test_ssh_relay.py | sha256sum
8c9f88b85d05deb21b7d732ad6f03499022bde7bcd74c456a56c2fd7f67c94aa  -
```
The resulting checksum **strictly matches** `8c9f88b85d05deb21b7d732ad6f03499022bde7bcd74c456a56c2fd7f67c94aa`. Zero dirty peer lines were touched or disturbed.

### 6.2 Protection of Core Modules
- `agent-bus` core transport: **Untouched (100% clean)**.
- `scripts/supervision/**`: **Untouched (100% clean)**.
- Working tree status in `/home/alexey/git/agent-coordination`: Contains only the 5 preserved peer files.

---

## 7. Review Summary & Sign-off

| Evaluation Criterion | Requirement | Observed Status | Assessment |
| :--- | :--- | :--- | :--- |
| **Architecture** | SinkDispatcher accepts store, cred, admission, events_dir | Fully implemented with strict type handling | **SATISFIED** |
| **Admission Integration** | Calls `_admit_host_task_impl` with `reject_on_cred=True` | Fully integrated and verified | **SATISFIED** |
| **Poison-Pill Protection** | Emits rejection events and ACKs malformed messages | Fully implemented with try-except ack protection | **SATISFIED** |
| **Correlated Replies** | Emits correlated reply for handshakes/commands | Fully implemented with idempotency keys | **SATISFIED** |
| **FIFO Cursor Draining** | Inbound sorted by `(created_at, seq)`, drains inbox | Fully verified in pytest batches | **SATISFIED** |
| **CLI Usability** | Supports `--once`, `--store`, `--cred`, `--json` | Verified in pytest subprocess calls | **SATISFIED** |
| **Security Guards** | Anti-spoofing (`session_id=None`), `head.cred` rejection | Strict fail-closed verification | **SATISFIED** |
| **Test Quality** | Comprehensive unit & regression tests pass | 5/5 sink tests, 17/17 compatibility, 94/94 total pass | **SATISFIED** |
| **Peer Invariants** | Diff hash preserved at `8c9f88b8...` | Verified match: zero peer disruption | **SATISFIED** |

### Independent Reviewer Sign-off:
- **Verdict**: **ACCEPT**
- **Reviewer**: Distinct Independent Peer Reviewer for Product 4 (`antigravity-cli`, `f68ea2b3-79d6-423f-9e0a-5d9bfad4bd97`)
- **Signature Date**: 2026-10-06T21:52:00+02:00
