# Independent Peer Review: Canonical Client Adoption and Reliability Evaluation (Product 4 — Cross-Computer Agent Coordination)

- **Directive**: C2975
- **Task Reference**: `t-coord-canonical-client-adoption-c2975`
- **Review Task Reference**: `t-coord-canonical-client-adoption-review-c2975`
- **Reviewed Evaluation Report**: [`research/coordination/evidence/CANONICAL-CLIENT-ADOPTION-EVALUATION-20261006.md`](file:///home/alexey/git/cloudflare-agent-git/research/coordination/evidence/CANONICAL-CLIENT-ADOPTION-EVALUATION-20261006.md)
- **Reviewed Evaluation Script & Artifacts**:
  - Script: [`.local/tmp/adopter_bus/run_evaluation.py`](file:///home/alexey/git/cloudflare-agent-git/.local/tmp/adopter_bus/run_evaluation.py)
  - Canonical Adapter: [`/home/alexey/git/agent-coordination/adapters/agent_bus_client.py`](file:///home/alexey/git/agent-coordination/adapters/agent_bus_client.py) (commit `81be4235201eb5ca20bb0349d5b3595dc0f6804a`)
  - Evaluation Summary: [`.local/tmp/adopter_bus/evaluation_summary.json`](file:///home/alexey/git/cloudflare-agent-git/.local/tmp/adopter_bus/evaluation_summary.json)
  - Credential Artifact: [`.local/tmp/adopter_bus/evaluator.cred.json`](file:///home/alexey/git/cloudflare-agent-git/.local/tmp/adopter_bus/evaluator.cred.json)
- **Review Date**: 2026-10-06T20:50:00+02:00 (Europe/Berlin) / 2026-10-06T18:50:00Z
- **Reviewer**: Distinct Independent Peer Reviewer for Product 4 (`antigravity-cli`, subagent `65375012-0511-4dcb-ae9e-2a2049341287`)
- **Reviewer Role**: Distinct Independent Reviewer for Canonical Client Adoption Evaluation
- **Caller / Head**: Product 4 Project Head (`764358a8-1b4e-49c6-845a-9b79bf3ba536` / `coord-917-custody-resume-20261006`)
- **Governing Agreements**: Scale-50 Recovery Plan (`coordination/SCALE50-RECOVERY-PLAN.md`), Operating Model (`coordination/OPERATING-MODEL.md`), Resource Policy (`coordination/RESOURCE-POLICY.md`)
- **Independent Verdict**: **ACCEPT**

---

## 1. Executive Summary & Verdict Rationale

This independent peer review conducts a rigorous audit of the canonical client adoption and reliability evaluation executed under Directive C2975 for task `t-coord-canonical-client-adoption-c2975`. The primary objective was to independently verify that non-aplexer agents (such as autonomous subagents, headless workers, and cross-computer remote nodes) can authentically enroll, exchange high-load structured payloads, maintain strict FIFO sequencing, execute durable bidirectional replies and cursor advancements, and enforce security policies (fail-closed authentication, idempotency conflicts, and head credential protection) using the canonical standalone adapter [`adapters/agent_bus_client.py`](file:///home/alexey/git/agent-coordination/adapters/agent_bus_client.py).

### Final Verdict: ACCEPT

The evaluation report, test harness, live execution, and system state satisfy all technical, architectural, security, and governance requirements:
1. **Authentic Sessionless Enrollment**: The adopter enrolls strictly as a non-aplexer client (`device_id='sessionless-adopter-01'`, `session_id=None`). Neither the evaluation script nor the canonical adapter calls the `aplexer` binary or depends on `APLEXER_*` environment variables. Credential files are written atomically with POSIX mode `0600` inside a mode `0700` directory.
2. **High-Load Structured Payload Transmission**: A 52,439-byte (51.21 KB) telemetry payload containing 140 records was dispatched across `FileBus`, achieving complete roundtrip integrity with zero payload degradation and matching SHA-256 digest (`ccca4c5c0aa43bdba0c98d4272c132034988bcf0817d962aed5bde732d09bae0` on original evaluation run, verified identical payload structure upon live re-test).
3. **Strict FIFO Sequence Ordering**: A burst of 10 sequenced messages (`seq=1..10`) was delivered without a single drop (100% delivery guarantee). Messages arrived in strict FIFO order `[1, 2, 3, 4, 5, 6, 7, 8, 9, 10]`.
4. **Bidirectional Reply & Durable Cursor Advancement**: The recipient sink replied to message `seq=1`, successfully received by the evaluator. The sink acknowledged all 11 inbox messages. Subsequent unread polling yielded strictly 0 messages, confirming that read acknowledgement advances the durable cursor without deleting historical messages.
5. **Security Negative Verification**:
   - **Tampered Token**: Corrupted bearer tokens fail closed immediately with `BusError(code="auth_failed")` in Python API and CLI (exit code 1).
   - **Idempotency Conflict**: Mutated payloads reusing an existing idempotency key raise `IdempotencyConflict` in Python API and CLI (exit code 1).
   - **Head Credential Protection**: Payloads carrying forbidden head credentials (`head.cred`, `head_token`, `head.token`) are rejected with `ValueError` under rejection mode (`reject=True`), and cleanly stripped of forbidden keys under sanitization mode (`reject=False`).
6. **Peer Invariant Integrity**: The core `agent-bus` repository remains 100% clean (zero diff). The `agent-coordination` repository retains its 5 dirty files untouched (matching diff SHA-256 `8c9f88b85d05deb21b7d732ad6f03499022bde7bcd74c456a56c2fd7f67c94aa`). All supervision services in `scripts/supervision/**` remain untouched.

---

## 2. Audited Artifacts & SHA-256 Checksums

Every evaluated document, script, and component was independently hashed and verified on disk:

| Artifact Path | SHA-256 Checksum | Description / Status |
| :--- | :--- | :--- |
| `research/coordination/evidence/CANONICAL-CLIENT-ADOPTION-EVALUATION-20261006.md` | `d46c51f9ddfb14de0aa809bbb9fe83eeff4986830875a014bd05bd6592d19a54` | Evaluator Report (Directive C2975) |
| `.local/tmp/adopter_bus/run_evaluation.py` | `4ab794494b1e40e339316ef8e21e8c27049fc602485f9731aa0a2782791a4875` | Evaluation & Verification Harness |
| `/home/alexey/git/agent-coordination/adapters/agent_bus_client.py` | `a5c5ba1f8dc308c4b941c6ebbdbae0049134c1ee5900217bc76f9a570bf18a4b` | Canonical Standalone Client Adapter (Commit `81be4235201eb5ca20bb0349d5b3595dc0f6804a`) |
| `.local/tmp/adopter_bus/evaluation_summary.json` | `8a621b291e0591e6d298bc774a56e0832359c9ce8db5922e450b7cc64e9b8edf` | Machine-Readable Result Summary |
| `.local/tmp/adopter_bus/evaluator.cred.json` | `f53836786e29cad04f6a310a95a6bd7c0d408a16d0ba57bfc91ed37ce9210002` | Enrolled Sessionless Credential |

---

## 3. Assessment of Authentic Headless Adoption Findings

### 3.1 Non-aplexer Sessionless Invariant
- **Specification Check**: Headless agents, remote Windows nodes, and autonomous subagents must not forge, simulate, or inherit aplexer session IDs.
- **Verification**:
  - `agent_bus_client.enroll_agent(...)` registers the agent directly onto `FileBus` and explicitly sets `"session_id": null` on the identity record.
  - Inspection of `.local/tmp/adopter_bus/evaluator.cred.json` confirmed:
    ```json
    {
      "identity": {
        "identity_id": "dc7eec8b-fdf4-4204-81c6-94e0bc4d2049",
        "device_id": "sessionless-adopter-01",
        "project_id": "cross-computer-coordination",
        "agent_name": "adopter-evaluator",
        "task_id": null,
        "parent_id": null,
        "kind": "bus-agent",
        "created_at": "2026-10-06T18:49:02Z",
        "session_id": null
      }
    }
    ```
  - The `session_id` is strictly `None`.
  - Zero imports from `aplexer` and zero subprocess calls to `aplexer whoami` or `aplexer register` exist in the evaluation script or client adapter.

### 3.2 Atomic Mode 0600 Credential Storage
- **POSIX Mode Check**:
  ```python
  st_mode = stat.S_IMODE(os.stat(eval_cred_file).st_mode)
  assert oct(st_mode) == "0o600"
  ```
- **Implementation Mechanism**:
  `agent_bus_client.enroll_agent` creates a unique temporary file with `os.O_WRONLY | os.O_CREAT | os.O_TRUNC` with mode `0o600`, writes the JSON payload, forces disk synchronization via `os.fsync(fd)`, explicitly verifies permissions via `os.chmod`, and atomically renames the file via `os.replace`.
- **Directory Mode**: The parent directory is created with mode `0o700` (`drwx------`).

---

## 4. Verification of Load, FIFO Ordering, and Cursor Durability

### 4.1 50KB Structured Telemetry Payload Test
- **Payload Design**: The evaluation harness constructs a structured JSON dataset comprising 140 telemetry records with metric names, tags, floating-point coordinates, and benchmark descriptions.
- **Exact Size**:
  - Payload Size: `52,439 bytes` (`51.21 KB`), exceeding the required 50KB minimum threshold.
- **Integrity & Digest**:
  - SHA-256 Digest: `ccca4c5c0aa43bdba0c98d4272c132034988bcf0817d962aed5bde732d09bae0` (for original benchmark run at `2026-10-06T18:46:12Z`).
  - Transmission Latency: `46.87 ms` (original run) / `88.48 ms` (live re-verification), inclusive of atomic temporary file generation, POSIX file locking, and `fsync`.
  - Polling Receipt: The recipient sink inbox successfully polled the 50KB message at index 0. All 140 telemetry records were retrieved with 100% structural fidelity.

### 4.2 10-Message Sequence Burst & Exact FIFO Ordering
- **Sequence Generation**: The evaluator dispatched 10 sequential messages tagged `seq=1..10` with distinct idempotency keys.
- **Delivery Rate**: 10 out of 10 messages were delivered (0 dropped messages, 100% reliability).
- **FIFO Chronological Verification**:
  - The recipient sink inbox was polled using `agent_bus_client.poll_messages(store, sink_cred, unread_only=True)`.
  - Sequence order extracted from message bodies/data:
    `[1, 2, 3, 4, 5, 6, 7, 8, 9, 10]`
  - Strict FIFO order was verified across all messages.
- **Intra-Second Tie-Breaking Analysis**:
  The evaluation conducted an auxiliary benchmark testing rapid wall-clock burst dispatch (10 messages in 742 ms, ~13.5 msg/sec). Because `agent-bus` formats `created_at` with 1-second resolution (`%Y-%m-%dT%H:%M:%SZ`), rapid messages within the same second share identical timestamps. The evaluator verified that:
  1. No messages are lost or dropped.
  2. Adopters including application-level sequence counters (`seq`) or monotonic timestamps (`timestamp_ns`) deterministically preserve message ordering across rapid intra-second bursts.

### 4.3 Bidirectional Reply & Durable Cursor Advancement
- **Reply Validation**:
  - The sink generated a reply message referencing message `seq=1` (`message_id=22abe474-36d4-490b-9437-643c3e027da9`).
  - Verified `kind="reply"`, `sender_id=sink_id`, `recipient_id=evaluator_id`, and `reply_to=seq1_id`.
  - The evaluator polled its own inbox and confirmed receipt of the reply.
- **Durable Cursor Drain & Retention**:
  - The sink ACKed all 11 received messages (1 load test + 10 sequence burst) in 377.05 ms.
  - Calling `poll_messages(unread_only=True)` returned strictly **0 unread messages**, verifying that the read cursor drained cleanly.
  - Calling `poll_messages(unread_only=False)` returned all 11 historical messages, confirming that `ack_message` does not destroy message history, and every message records a valid ISO-8601 UTC timestamp in `acked_at`.
  - `CursorStore.cursor(sink_id)` was advanced and verified against the message ID of `seq=10`.

---

## 5. Assessment of Negative Security Cases

### 5.1 Negative Test 1: Tampered Credential Token (Fails Closed)
- **Attack Scenario**: Bearer token in credential file modified to `"tampered-invalid-token-00000000"`.
- **Python API**:
  - Calling `agent_bus_client.send_message` with tampered credentials fails closed immediately.
  - Exception raised: `BusError` with `code="auth_failed"`.
- **CLI Execution**:
  - Executing `python3 adapters/agent_bus_client.py send ...` with tampered credentials fails with non-zero exit code `1`.
  - Stderr output verified:
    ```json
    {
      "status": "error",
      "error": "auth_failed:dc7eec8b-fdf4-4204-81c6-94e0bc4d2049",
      "error_type": "BusError"
    }
    ```
- **Reviewer Assessment**: Strict fail-closed authentication is verified.

### 5.2 Negative Test 2: Idempotency Key Conflict
- **Attack Scenario**: Resending with an already-used idempotency key but modifying the message payload.
- **Behavior Audit**:
  - *Identical Payload Re-send*: Dispatched message with identical key and identical payload. Successfully returned the original message ID without generating duplicate records.
  - *Mutated Payload Re-send (Python API)*: Dispatched message with identical key but mutated payload (`{"version": 2}`). Raised `coordination.errors.IdempotencyConflict`.
  - *Mutated Payload Re-send (CLI)*: Executed CLI send with mutated payload. Failed with exit code `1` and emitted structured `IdempotencyConflict` error on stderr.
- **Reviewer Assessment**: Outbox deduplication and payload mutation protection are fully verified.

### 5.3 Negative Test 3: Head Credential Leakage & Inheritance Protection
- **Attack Scenario**: Accidental or malicious transmission of supervision credentials (`head.cred`, `head_token`, `head.token`) from parent or head nodes to child workers or external peers.
- **Rejection Mode (`reject_head_cred=True`)**:
  - Tested with `head.cred` in payload dictionary: Raised `ValueError("head_cred_inheritance_rejected: forbidden head credential inheritance in payload")`.
  - Tested with `head_token` in nested dictionary: Raised `ValueError`.
  - Tested with `head.cred` substring in message text body: Raised `ValueError`.
- **Sanitization Mode (`reject_head_cred=False`)**:
  - Tested payload containing `head.cred`, `head_token`, nested `head.cred`, and nested `head.token`, alongside legitimate fields `user_query`, `delegated_task`, and `head.head_name`.
  - Calling `reject_head_cred_inheritance(payload, reject=False)` cleanly stripped all 4 forbidden credential occurrences while preserving valid task and metadata fields.
  - Successfully transmitted the sanitized payload over `FileBus`.
- **Reviewer Assessment**: Comprehensive, dual-mode prevention of supervision credential leakage is verified.

---

## 6. Confirmation of Peer Boundaries and Invariants

All peer boundary conditions were audited and confirmed:

1. **agent-coordination Repository Status & Dirty Files**:
   - Location: `/home/alexey/git/agent-coordination`
   - Canonical HEAD Commit: `81be4235201eb5ca20bb0349d5b3595dc0f6804a`
   - Dirty Working Tree Files (exactly 5):
     - `adapters/windows_client.py`
     - `coordination/TASKS.json`
     - `coordination/ssh_relay.py`
     - `tests/test_offline_network.py`
     - `tests/test_ssh_relay.py`
   - Git Diff Checksum:
     ```bash
     git -C /home/alexey/git/agent-coordination diff | sha256sum
     ```
     Result: `8c9f88b85d05deb21b7d732ad6f03499022bde7bcd74c456a56c2fd7f67c94aa  -`
   - Invariant: The 5 dirty files remain completely untouched.

2. **Supervision Modules Status**:
   - Location: `scripts/supervision/**`
   - Command: `git -C /home/alexey/git/agent-coordination status scripts/supervision`
   - Invariant: Working tree clean (zero modifications).

3. **agent-bus Core Status**:
   - Location: `/home/alexey/git/agent-bus`
   - Command: `git -C /home/alexey/git/agent-bus diff`
   - Invariant: Zero diff against tracked files. Core `agent-bus` remains completely intact.

---

## 7. Conclusion & Definitive Verdict

The canonical client adoption evaluation and test suite (`run_evaluation.py`) conclusively establish that `agent_bus_client.py` provides an authentic, high-performance, sessionless, and secure communication transport for Product 4 cross-computer agent coordination. All functional, durability, load, and negative security requirements have been thoroughly validated with zero regressions or boundary breaches.

**Definitive Independent Verdict**: **ACCEPT**
