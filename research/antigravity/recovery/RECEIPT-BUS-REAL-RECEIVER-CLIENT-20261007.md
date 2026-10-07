# Implementation Receipt: Agent Bus Real Receiver Client (Task `bus-real-receiver-client-adoption-01`)

- **Author**: `ant-head-readiness-custody-20261007` (Session `3b522ddb-8dc8-41b4-a382-f76baab33b0a`)
- **Date**: 2026-10-07T00:36:00Z (2026-10-07 02:36:00 Berlin)
- **Task ID**: `bus-real-receiver-client-adoption-01`
- **Directive**: Directive C3108 / Scale-50 Follow-Through & Real Model Adoption
- **Target Repository**: `/home/alexey/git/cloudflare-agent-git`
- **Target Deliverables**:
  - `research/antigravity/bus_client/__init__.py`
  - `research/antigravity/bus_client/receiver.py`
  - `research/antigravity/bus_client/test_receiver.py`
- **Bus Sibling Repository Under Read-Only Audit**: `/home/alexey/git/agent-bus` (pin `bf351f423441d17d981e95f0a202e79dc4466003`)
- **Status**: Implemented & Verified (8/8 Unit & Negative Tests Passing)

---

## 1. Overview & Context

Following the landing of the Windows 35 loopback spike (Commit `2016f679`, Directive C3087) and guidance from `codex-principal` in Directive C3108, this task implements an isolated, production-grade real receiver client (`research/antigravity/bus_client/receiver.py`). 

The client connects to the Agent Bus REST adapter (or loopback adapter), registers an agent/device identity, polls for incoming envelopes, and executes the complete 5-stage coordination lifecycle:
1. **Inbox Polling**: Queries unread message envelopes via `GET /v1/inbox`.
2. **Read-ACK (`POST /v1/ack`)**: Immediately records receipt delivery (`acked_at`).
3. **Semantic Acceptance (`POST /v1/accept`)**: Commits to task processing (`accepted_at`).
4. **Execution / Delegation**: Dispatches to a task handler (custom callback or default execution).
5. **Completion (`POST /v1/complete`)**: Records outcome status (`success` / `failed`), execution duration, and cryptographic SHA-256 artifact digest (`outcome_at`).
6. **Correlated Reply (`POST /v1/reply`)**: Dispatches a correlated response envelope linking back to the origin message (`reply_to`).

---

## 2. Deliverables & Cryptographic Integrity

| File Path | SHA-256 Checksum | Description |
|---|---|---|
| `research/antigravity/bus_client/__init__.py` | `2e51d5a6d67975a498e2802fc9770931cccd06bd4e4432ddb995cc3f65a26437` | Bus client package initialization. |
| `research/antigravity/bus_client/receiver.py` | `d20b28c794dd138b7d979b5e37a0b798d7a0fa5101ba09ed2d76ad4f812bd3e6` | Outbound-only real receiver client implementing 5-stage coordination lifecycle. |
| `research/antigravity/bus_client/test_receiver.py` | `9f7e666c012e077b395db6649d7a63669e761a604b0bca2fd7c00af3022e7a7e` | Comprehensive unit and negative test suite (8 test cases). |

---

## 3. Architecture & Security Invariants

1. **Standard Library Only**:
   Implemented strictly in Python 3.12 standard library (`urllib.request`, `json`, `hashlib`, `dataclasses`). Requires zero external packages or dependencies.
2. **Strictly Outbound-Only Client**:
   The receiver never binds listening ports or opens inbound network sockets. It communicates strictly via outbound HTTP requests, enabling operation behind NATs, firewalls, and Windows environments without inbound SSH or listener requirements.
3. **Private Credential Security**:
   Bearer tokens and registration credentials are saved with `umask 077` and explicit `chmod 0600` permissions. Temporary file creation with atomic replacement (`os.replace`) prevents incomplete writes.
4. **Error Taxonomy & Fail-Closed Semantics**:
   - `401 Unauthorized` -> `AuthenticationError`
   - `403 Forbidden` -> `AuthorizationError` (`not_recipient`, `project_scope`)
   - `404 Not Found` -> `NotFoundError`
   - `409 Conflict` -> `IdempotencyConflictError`
   - Handler exceptions fail closed: record `status="failed"`, generate error digest, complete message, and reply with failure diagnostics without crashing the receiver loop.
5. **Bus Source Lease Protection**:
   Sibling repository `/home/alexey/git/agent-bus` is accessed strictly in read-only mode at pin `bf351f423441d17d981e95f0a202e79dc4466003`. Zero files in `agent-bus` were modified or created.

---

## 4. Empirical Test Suite Execution Results

Executed: `python3 -m unittest -v research/antigravity/bus_client/test_receiver.py`

```text
test_authentication_and_authorization_failures (research.antigravity.bus_client.test_receiver.TestBusReceiverClient.test_authentication_and_authorization_failures)
Verifies AuthenticationError (401) and AuthorizationError (403). ... ok
test_cli_execution (research.antigravity.bus_client.test_receiver.TestBusReceiverClient.test_cli_execution)
Verifies CLI entrypoint via subprocess with --once and --json. ... ok
test_custom_handler_error_fails_closed (research.antigravity.bus_client.test_receiver.TestBusReceiverClient.test_custom_handler_error_fails_closed)
Verifies that an unhandled handler exception records failed completion and reply. ... ok
test_full_5_stage_coordination_lifecycle (research.antigravity.bus_client.test_receiver.TestBusReceiverClient.test_full_5_stage_coordination_lifecycle)
Tests complete 5-stage coordination lifecycle with custom handler and correlated reply. ... ok
test_idempotency_conflict_rejection (research.antigravity.bus_client.test_receiver.TestBusReceiverClient.test_idempotency_conflict_rejection)
Verifies IdempotencyConflictError (409) when key is reused with conflicting body. ... ok
test_registration_and_credential_persistence (research.antigravity.bus_client.test_receiver.TestBusReceiverClient.test_registration_and_credential_persistence)
Verifies registration, token issuance, 0600 file saving and reloading. ... ok
test_run_loop_bounded_iterations (research.antigravity.bus_client.test_receiver.TestBusReceiverClient.test_run_loop_bounded_iterations)
Verifies that run_loop terminates cleanly after max_iterations. ... ok
test_status_endpoint (research.antigravity.bus_client.test_receiver.TestBusReceiverClient.test_status_endpoint)
Verifies status endpoint reporting adapter status and store info. ... ok

----------------------------------------------------------------------
Ran 8 tests in 4.225s

OK
```

---

## 5. Operational Invariants & Resource Proofs

1. **Zero Lingering Daemons**:
   All test fixtures cleanly shut down the ephemeral loopback HTTPServer in `tearDown()` via `server.shutdown()` and `server.server_close()`.
2. **Zero Builds**:
   Zero `cargo build`, `cargo test`, or `npm` commands executed.
3. **Physical Bounds**:
   Executed well within host limits (`MemoryMax=1500M`, `TasksMax=100`, running in 4.2s).

---

## 6. Next Steps

1. Launch a distinct, independent reviewer subagent to conduct rigorous code QA and author `research/antigravity/reviews/REV-BUS-REAL-RECEIVER-CLIENT-20261007.md`.
2. Sync deliverables using Agent Branches isolated sync onto `origin/recovery/bus-real-receiver-client-01` and promote to `origin/main`.
3. Provide interface details to D3 (`zcode-quota-recovery-head-20261006`) for genuine bus envelope task consumption.
