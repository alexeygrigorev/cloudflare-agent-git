# Independent Review: Consumer Execution Adapter & Strict State Separation (Directive C3032)

**Reviewer Identity**: Independent Peer Reviewer for Product 4 (Cross-computer Agent Coordination)  
**Agent Subagent ID**: `a5d6e886-ea4c-4a94-be4d-3b01d93686b8` (Parent Caller: `764358a8-1b4e-49c6-845a-9b79bf3ba536`)  
**Task ID**: `t-coord-consumer-exec-adapter-review-c3032`  
**Directives**: Directive C3032 (enforcing C3031, C3033, C3024, C3026)  
**Date**: 2026-10-06T22:35:25+02:00 (Europe/Berlin) / 2026-10-06T20:35:25Z  
**Definitive Verdict**: **ACCEPT**

---

## 1. Evaluated Artifacts & Exact SHA-256 Hashes

| Artifact | Repository & Path | Commit / Reference | SHA-256 Checksum |
|:---|:---|:---|:---|
| **Evidence Document** | `cloudflare-agent-git`:<br>[`research/coordination/evidence/CONSUMER-EXECUTION-ADAPTER-EVIDENCE-20261006.md`](file:///home/alexey/git/cloudflare-agent-git/research/coordination/evidence/CONSUMER-EXECUTION-ADAPTER-EVIDENCE-20261006.md) | `0529c68ba05716ca7018bcf90259cdaf5b28d8a6` | `276cbe224b127cc674dbd24f7792f92d2eca202a388f25ded92feb3ba791bad1` |
| **Adapter Implementation** | `cloudflare-agent-git`:<br>[`scripts/coordination/consumer_execution_adapter.py`](file:///home/alexey/git/cloudflare-agent-git/scripts/coordination/consumer_execution_adapter.py) | `a7b01afcd74ef4dcd54c95e743b0916b51613246` | `dc3e31f4438b2824f4b19db7ea388bd7a6eae4f356bccdd12c7e0a363c544df9` |
| **Adapter Test Suite** | `cloudflare-agent-git`:<br>[`scripts/coordination/test_consumer_execution_adapter.py`](file:///home/alexey/git/cloudflare-agent-git/scripts/coordination/test_consumer_execution_adapter.py) | `a7b01afcd74ef4dcd54c95e743b0916b51613246` | `d336e4a66fb33d7f75578d5c69cb858cd5328a110710a01208968a9dc98c1c9a` |
| **Peer Commit** | `agent-coordination`:<br>`origin/codex/role-failover-20261006` | `045e2ca4d084649a92ea9a9243c902f9a76114b9` | N/A (Git Commit Object) |

All local file checksums and commit identifiers were independently computed and verified against disk and git history.

---

## 2. Detailed Assessment of Consumer Execution Adapter Architecture

The `ConsumerExecutionAdapter` provides the execution plane integration for Product 4 (Cross-computer Agent Coordination), receiving admitted task envelopes from FileBus and managing their execution lifecycle with strict isolation.

### Key Architectural Components

1. **`ExecutionUnit` Dataclass**:
   - Represents the state of an individual unit of work.
   - Initialized strictly with `state="admitted"`, generating a unique `unit_id` (`unit-<12hex>`).
   - Maintains execution bounds: `pid`, `started_at`, `completed_at`, `artifact_path`, `artifact_sha256`, and `error`.

2. **`admit_task(msg)`**:
   - Performs fail-closed security filtering: runs `reject_head_cred_inheritance` over both envelope `data` and raw `body`.
   - Delegates admission validation to `MultiHostAdmission._admit_host_task_impl` with `reject_on_cred=True`.
   - Emits structured events to `host_events.jsonl`: `task_admitted` on admission; `guard_rejected` or `admission_rejected` on security failure.
   - Implements poison-pill containment: if an envelope fails security guards, it ACKs the message before raising `GuardRejected` or `UnknownDevice`, ensuring consumer sinks never enter infinite retry crash-loops.

3. **`spawn_worker_unit(unit, action, payload, runner_fn=None)`**:
   - Explicitly transitions state from `"admitted"` to `"running"`.
   - Binds host runtime metadata (`os.getpid()`, UTC ISO timestamp).
   - Emits `task_spawned` event.
   - Executes callable logic (or default execution handler) and writes the outcome to an immutable deliverable artifact at `<artifacts_dir>/<task_id>.json`.
   - Computes the deliverable's SHA-256 digest on disk, sets `unit.state = "completed"`, and emits `task_completed` with provenance checksums.

4. **`send_completion_reply(message_id, sender_id, unit)`**:
   - Formulates a correlated completion message via `reply_message` on FileBus containing `status="completed"`, `unit_id`, `task_id`, `artifact_path`, `artifact_sha256`, `session_id=None`, and `execution_target="hetzner-rmthz"`.
   - Explicitly advances the consumer's durable read cursor via `ack_message`.

5. **`poll_and_execute(limit=None)` & CLI**:
   - End-to-end polling and batch dispatch loop with full headless CLI support (`--once`, `--json`, `--store`, `--cred`, `--registry`, `--events-dir`, `--artifacts-dir`).

---

## 3. Verification of Strict State Separation & Anti-Overclaiming (C3031 / C3032 / C3033)

A core requirement from Directives C3031 and C3033 is the total elimination of "fake active" or premature running states. Under review:

- **Admission as Reservation**: When `admit_task` evaluates an inbound message, the returned `ExecutionUnit` is strictly assigned `state="admitted"`. The fields `pid`, `started_at`, `completed_at`, and `artifact_path` remain `None`. The logged host event in `host_events.jsonl` records `state: "admitted"`. Under no circumstances is the unit flagged `active` or `running` during admission.
- **Spawn-Time Activation**: The transition to `state="running"` occurs only within `spawn_worker_unit`, at the precise instant execution begins. It captures the operating system PID and exact UTC start timestamp.
- **Deliverable Completion**: The transition to `state="completed"` is conditioned on the physical writing of the artifact file to disk and the computation of its cryptographic hash.

Independent inspection confirms that `consumer_execution_adapter.py` strictly upholds this lifecycle invariant.

---

## 4. Verification of Deliverable Artifact Provenance & SHA-256 Invariance

The review confirmed artifact generation and integrity:
1. Every completed unit writes its deliverable to `<artifacts_dir>/<task_id>.json`.
2. The SHA-256 digest is calculated directly from the written artifact bytes (`hashlib.sha256(artifact_content).hexdigest()`).
3. The computed digest is bound to `unit.artifact_sha256` and included in the FileBus completion reply envelope and `task_completed` event log.
4. Independent verification in test `test_spawn_worker_unit_executes_and_produces_artifact` demonstrates byte-for-byte SHA-256 parity between the recorded metadata and disk contents.

---

## 5. Verification of Negative Security Cases & Poison-Pill Containment

The implementation was evaluated against four critical negative and security conditions:

1. **Credential Leak Prevention (`reject_head_cred_inheritance`)**:
   - Inbound envelopes carrying leaked head credentials (e.g. `head.cred`) fail closed immediately.
   - Raises `GuardRejected` and prevents unit instantiation or execution.
2. **Unregistered Device Defense (`UnknownDevice`)**:
   - Inbound requests specifying unverified devices (e.g. `unregistered-rogue-host`) raise `UnknownDevice` and emit `admission_rejected` events.
3. **Poison-Pill Loop Containment**:
   - Rejection handlers call `ack_message(...)` on the poison envelope before re-raising the exception. This ensures that corrupt or hostile payloads do not cause persistent queue blockage or sink spinning.
4. **Cross-Agent Inbox Isolation**:
   - Durable cursors operate per-agent without leaking state across unrelated accounts.
   - Verified that a sentinel agent (`unrelated-worker-gamma` / `sentinel-worker`) inbox remained strictly untouched at exactly 1 unread message while the consumer processed multiple tasks.

---

## 6. Test Suite Execution & Verification Results

### Test Suite 1: Consumer Execution Adapter (`test_consumer_execution_adapter.py`)
Command:
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

============================== 7 passed in 1.09s ===============================
```

### Test Suite 2: Combined Regression Suite (`test_agent_bus_transport.py` + `test_consumer_execution_adapter.py`)
Command:
```bash
python3 -m pytest -v scripts/coordination/test_agent_bus_transport.py scripts/coordination/test_consumer_execution_adapter.py
```
Output:
```
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.1.1, pluggy-1.6.0 -- /usr/bin/python3
cachedir: .pytest_cache
rootdir: /home/alexey/git/cloudflare-agent-git
plugins: anyio-4.12.1, opik-2.2.54
collecting ... collected 14 items

scripts/coordination/test_agent_bus_transport.py::test_enroll_creates_sessionless_identity_and_mode_0600_cred PASSED [  7%]
scripts/coordination/test_agent_bus_transport.py::test_send_and_poll_lifecycle PASSED [ 14%]
scripts/coordination/test_agent_bus_transport.py::test_reply_and_ack_durable_cursor PASSED [ 21%]
scripts/coordination/test_agent_bus_transport.py::test_reject_head_cred_inheritance PASSED [ 28%]
scripts/coordination/test_agent_bus_transport.py::test_duplicate_idempotency_key PASSED [ 35%]
scripts/coordination/test_agent_bus_transport.py::test_rpc_dispatch_interface PASSED [ 42%]
scripts/coordination/test_agent_bus_transport.py::test_cli_subcommands_headless_execution PASSED [ 50%]
scripts/coordination/test_consumer_execution_adapter.py::test_admission_reservation_state_is_never_fake_active PASSED [ 57%]
scripts/coordination/test_consumer_execution_adapter.py::test_spawn_worker_unit_executes_and_produces_artifact PASSED [ 64%]
scripts/coordination/test_consumer_execution_adapter.py::test_head_cred_leak_fails_closed_without_execution PASSED [ 71%]
scripts/coordination/test_consumer_execution_adapter.py::test_correlated_reply_and_cursor_advancement PASSED [ 78%]
scripts/coordination/test_consumer_execution_adapter.py::test_unrelated_cursor_isolation_during_execution PASSED [ 85%]
scripts/coordination/test_consumer_execution_adapter.py::test_unknown_device_admission_rejection PASSED [ 92%]
scripts/coordination/test_consumer_execution_adapter.py::test_cli_execution_once_json PASSED [100%]

============================== 14 passed in 6.49s ==============================
```

All 14 unit and integration tests passed cleanly with zero failures or warnings.

---

## 7. Verification of Peer Invariants & Repository Scoping

1. **Peer Working Tree Invariance**:
   In `/home/alexey/git/agent-coordination`:
   ```bash
   git diff HEAD -- adapters/windows_client.py coordination/TASKS.json coordination/ssh_relay.py tests/test_offline_network.py tests/test_ssh_relay.py | sha256sum
   ```
   Output:
   ```
   8c9f88b85d05deb21b7d732ad6f03499022bde7bcd74c456a56c2fd7f67c94aa  -
   ```
   The diff hash exactly matches the required invariant `8c9f88b85d05deb21b7d732ad6f03499022bde7bcd74c456a56c2fd7f67c94aa`.

2. **Standalone Repositories Untouched**:
   - `/home/alexey/git/agent-bus`: Clean tracked state; zero modifications to bus core.
   - `scripts/coordination/agent_bus.py`: Clean and unmodified in `cloudflare-agent-git`.

3. **Ownership Boundary Adherence**:
   - No cross-repository bleed or unauthorized directory changes occurred during implementation or testing.

---

## 8. Definitive Independent Verdict

**VERDICT: ACCEPT**

The Consumer Execution Adapter (`scripts/coordination/consumer_execution_adapter.py`) and its accompanying verification test suite (`scripts/coordination/test_consumer_execution_adapter.py`) fulfill all requirements under Directive **C3032**:
1. Strict separation of admission reservation (`state='admitted'`) from active execution (`state='running'`).
2. High-integrity execution units capturing PID, runtime, and SHA-256 deliverable artifact provenance.
3. Fail-closed security validation with poison-pill loop prevention and event logging.
4. Total test pass (14/14 tests) and absolute preservation of peer working tree invariants.
