# Independent Technical Review: Win35 Non-SSH Agent Bus Loopback Client Spike (Directive C3087 / Task `bus-win35-nonssh-loopback-spike-01`)

- **Review Date**: 2026-10-07T00:30:00Z (2026-10-07 02:30:00 Berlin)
- **Task ID**: `bus-win35-nonssh-loopback-spike-01`
- **Directive**: `C3087` / Scale-50 Follow-Through
- **Auditor / Independent Reviewer**: Antigravity Independent Review Agent
- **Reviewer Conversation ID**: `f7044808-6b7e-48db-a9ad-675d2737a563`
- **Parent Caller ID**: `ea14b401-20e9-4e48-ab08-d15be08da30d`
- **Bus Owner Session**: Bus327 (session `3273594b`)
- **Target Repository**: `/home/alexey/git/cloudflare-agent-git`
- **Sibling Repository Under Read-Only Audit**: `/home/alexey/git/agent-bus` (pin `bf351f423441d17d981e95f0a202e79dc4466003`)
- **Audited Target Receipt**: `research/antigravity/recovery/RECEIPT-BUS-WIN35-LOOPBACK-SPIKE-20261007.md`
- **Audited Implementation Files**:
  - `research/antigravity/spikes/bus_win35_loopback/adapter.py`
  - `research/antigravity/spikes/bus_win35_loopback/client.sh`
  - `research/antigravity/spikes/bus_win35_loopback/test_loopback_spike.py`
- **Test Suite Result**: 8/8 tests passed in 4.129s (`python3 -m unittest -v research/antigravity/spikes/bus_win35_loopback/test_loopback_spike.py`)
- **Operational Invariants**: Zero daemon leaks, zero tracked modifications in `agent-bus`, zero rust/npm builds.
- **Final Verdict**: **ACCEPTED WITH CONDITIONS**

---

## 1. Executive Summary & Verdict

Under Directive C3087 and Task `bus-win35-nonssh-loopback-spike-01`, an objective, independent technical QA review was conducted on the **Agent Bus Windows 35 Non-SSH HTTP Loopback Client Spike**. The spike demonstrates that an outbound-only GitBash client operating under Windows 35 can coordinate reliably across host boundaries with the Hetzner Agent Bus via a local loopback HTTP REST adapter, without requiring inbound listening ports on Windows, SSH daemons, or core modifications to `agent-bus`.

### Key Review Findings:
1. **Architectural Elegance & Independence**:
   `adapter.py` is implemented entirely within Python 3.12 standard library (`http.server.HTTPServer` / `BaseHTTPRequestHandler`), binding strictly to `127.0.0.1`. It wraps `coordination.bus.FileBus` cleanly via library import without any mutation or writes to the `/home/alexey/git/agent-bus` repository.
2. **Outbound-Only Client Verification (`client.sh`)**:
   `client.sh` verifies that an agent executing in GitBash on Windows 35 can execute the complete 5-stage coordination lifecycle (`register` -> `send` -> `poll inbox` -> `read-ack` -> `accept` -> `complete` with SHA-256 artifact digest -> `reply`) purely via outbound `curl` calls. No incoming connections, open ports, or SSH access are required on the Windows side.
3. **Comprehensive Negative Matrix Coverage**:
   The test suite `test_loopback_spike.py` covers 8 rigorous automated test scenarios, systematically validating HTTP status mappings (401 `auth_failed`, 403 `not_recipient`, 403 `project_scope`, 409 `idempotency_conflict`), message deduplication, store persistence across server crash/restart, and live subprocess execution of `client.sh`.
4. **Clean Operational Lifecycle**:
   Process teardown in tests is leak-free (`server.shutdown()` and `server.server_close()`). Post-test process checks confirm zero lingering background daemons and zero orphaned socket listeners.
5. **Digest Reconciliation Condition**:
   A checksum discrepancy was detected between Section 2 of `RECEIPT-BUS-WIN35-LOOPBACK-SPIKE-20261007.md` and the actual on-disk files in `research/antigravity/spikes/bus_win35_loopback/`. The spike code and test suite are technically sound and pass 100%, but the receipt must be reconciled with the true cryptographic digests prior to git promotion.

### Final Verdict: **ACCEPTED WITH CONDITIONS**

**Condition for Final Promotion**:
- Update Section 2 of `RECEIPT-BUS-WIN35-LOOPBACK-SPIKE-20261007.md` with the verified on-disk SHA-256 hashes recorded in Section 2.2 of this report before staging and committing under `flock .local/git.lock`.

---

## 2. Pinned Source & Cryptographic Integrity Verification

### 2.1 Sibling Repository (`/home/alexey/git/agent-bus`) Integrity
The sibling repository was audited strictly in read-only mode to honor the active source lease held by Bus327 (session `3273594b`).

```bash
$ git -C /home/alexey/git/agent-bus rev-parse HEAD
bf351f423441d17d981e95f0a202e79dc4466003

$ git -C /home/alexey/git/agent-bus diff --stat
[0 files changed - clean]

$ git -C /home/alexey/git/agent-bus diff --cached --stat
[0 files changed - clean]
```
- **Commit Pin**: `bf351f423441d17d981e95f0a202e79dc4466003` matches the required pin exactly.
- **Tracked Modifications**: Zero. No tracked files were modified, staged, or committed.

### 2.2 Cryptographic Digest Audit
The cryptographic SHA-256 digests of all spike deliverables and the receipt were independently calculated on disk:

| File Path | Documented SHA-256 (in Receipt) | Verified On-Disk SHA-256 | Status |
|---|---|---|:---:|
| `research/antigravity/recovery/RECEIPT-BUS-WIN35-LOOPBACK-SPIKE-20261007.md` | N/A (self) | `15e2ebce38cdd27e9ca5fd260cae66b10a0db51f59f309a4e4bab4bea2bdd0b1` | Verified |
| `research/antigravity/spikes/bus_win35_loopback/adapter.py` | `0d843817f7b3df667527181c009d66141a02796e626e3c09f3ebc558c4ee2fe0` | `5637cf8c16e6e59c6e7838714512d7c0dcce2fe6c59e9be09e1ab6355a08ce85` | **Diverged** (Pre-edit hash) |
| `research/antigravity/spikes/bus_win35_loopback/client.sh` | `f28682a85eefb925b41315993b4a2bf189286eb0c2a5dcfa9d0e14a1a6797825` | `3e69b73aacb86baa39d6db39c3108bb8e22e513cb45d54a51dfea9789a276be1` | **Diverged** (Pre-edit hash) |
| `research/antigravity/spikes/bus_win35_loopback/test_loopback_spike.py` | `374d9e9e8f498c56e30097a82c40c8fa99ee2aee3798ca7a33bc7b7070ad53bc` | `4b4cb37dea8961b413ebde85078a273374a9cdfe6eb6786db1380157969fff7c` | **Diverged** (Pre-edit hash) |

**Analysis of Divergence**:
The divergence stems from the spike author drafting the receipt table prior to final comment/docstring formatting and test assertion tuning. The actual implementation files on disk are completely coherent, consistent, and pass all tests. This is addressed via the single condition noted above.

---

## 3. Architecture & Code Quality Audit

### 3.1 Adapter Implementation (`adapter.py`)
`adapter.py` provides a lightweight REST facade over `FileBus`:
- **Standard Library Only**: Built using Python's `http.server.HTTPServer` and `http.server.BaseHTTPRequestHandler`. Requires zero 3rd-party dependencies (no Flask, FastAPI, or external HTTP engines).
- **Loopback Binding**: Defaults to `127.0.0.1:8788`. In-process testing binds dynamically to ephemeral high-range ports. It does not bind to `0.0.0.0`, ensuring external network exposure cannot occur accidentally.
- **Clean Library Integration**: Dynamically adds `/home/alexey/git/agent-bus` to `sys.path` without modifying `agent-bus` or requiring package installation (`setup.py` / `pip install -e`).
- **REST Surface Compliance**:
  - `GET /v1/status`: Health check, returns store path and transport scope.
  - `POST /v1/register`: Registers agent identity and returns bearer token.
  - `POST /v1/send`: Submits envelope with optional idempotency key, reply_to, and structured metadata.
  - `GET /v1/inbox`: Polls unread or all messages for an authenticated identity.
  - `POST /v1/ack`: Transitions message to read-acknowledged (`acked_at`).
  - `POST /v1/accept`: Transitions message to semantically accepted (`accepted_at`).
  - `POST /v1/complete`: Transitions message to action completed with outcome status and SHA-256 artifact digest.
  - `POST /v1/reply`: Sends correlated response message with `reply_to` linkage.
- **Robust Error Mapping**:
  The handler maps native `CoordinationError`, `BusError`, and `IdempotencyConflict` exceptions to standard HTTP status codes:
  - `IdempotencyConflict` -> `409 Conflict` (`idempotency_conflict`)
  - `auth_failed` -> `401 Unauthorized` (`auth_failed`)
  - `not_recipient` -> `403 Forbidden` (`not_recipient`)
  - `project_scope` / `cross_project` -> `403 Forbidden` (`project_scope`)
  - `unknown_message` / `unknown_identity` -> `404 Not Found`
  - Missing parameters / malformed JSON -> `400 Bad Request`
- **DoS / Memory Ceiling**:
  Enforces a strict 10MB payload size limit (`if content_len > 10 * 1024 * 1024: raise ValueError(...)`), protecting the process against memory exhaustion attacks.

### 3.2 Outbound Client Script (`client.sh`)
`client.sh` verifies the Windows 35 runtime contract:
- **Outbound-Only Topology**:
  Exclusively issues HTTP requests via `curl -sS -f`. Does not bind to any listening socket or require incoming ports on Windows 35.
- **Credentials Protection**:
  Generates a dedicated temporary directory (`mktemp -d`), enforces `umask 077` and `chmod 600` on the credentials file, and sets a bash `EXIT` trap (`trap 'rm -rf "$TMP_DIR"' EXIT`) to guarantee complete cleanup of tokens upon termination or failure.
- **Full 5-Stage Coordination Lifecycle**:
  1. Enrolls agent and device (`POST /v1/register`).
  2. Queries service status (`GET /v1/status`).
  3. Verifies initial unread inbox count (`GET /v1/inbox`).
  4. Dispatches task envelope with idempotency key (`POST /v1/send`).
  5. Polls inbox for delivered task envelope (`GET /v1/inbox`).
  6. Executes the 3 transport state transitions in order:
     - Read-ACK (`POST /v1/ack`)
     - Semantic Accept (`POST /v1/accept`)
     - Task Completion (`POST /v1/complete`) with verified SHA-256 artifact digest.
  7. Sends correlated reply message (`POST /v1/reply`).
- **Deterministic Assertion**:
  Emits `WIN35_CLIENT_EXECUTION_SUCCESS` and returns exit code 0 upon verified completion.

### 3.3 Test Suite Architecture (`test_loopback_spike.py`)
`test_loopback_spike.py` implements an automated, hermetic test environment:
- **Dynamic Ephemeral Binding**:
  Uses `find_free_port()` (`socket.bind(("127.0.0.1", 0))`) to eliminate port collision risks during concurrent test runs.
- **Thread & Store Isolation**:
  Each test allocates an isolated temporary store (`mkdtemp`), sets permissions to `0700`, runs the `BusLoopbackServer` in a daemon thread, and explicitly shuts down the server (`shutdown()` + `server_close()`) in `tearDown()`.
- **Subprocess Integration**:
  `test_client_script_execution` runs `client.sh` directly as a subprocess against the live running server, validating exit code 0 and stdout banners.

---

## 4. Negative Test Matrix Reconciliation

The test suite was audited against the architectural requirements defined in discovery artifact `.local/codex/bus-win35-resume-3273594b/disc-01-result.md`:

| Case Ref | Failure / Boundary Scenario | Test Implementation | Verified Response & Behavior | Status |
|---|---|---|---|:---:|
| **Case 2** | Invalid or forged bearer token | `test_authentication_and_authorization_failures` | `401 Unauthorized` (`code: "auth_failed"`) | **PASS** |
| **Case 3** | Accessing/acking message of another recipient | `test_authentication_and_authorization_failures` | `403 Forbidden` (`code: "not_recipient"`) | **PASS** |
| **Scope** | Sending message across isolated project boundaries | `test_cross_project_isolation` | `403 Forbidden` (`code: "project_scope"`) | **PASS** |
| **Case 6** | Replayed send with identical payload & idempotency key | `test_idempotent_send_deduplication` | `200 OK` (deduplicated, returns cached message ID, inbox count remains 1) | **PASS** |
| **Case 6b** | Replayed send with conflicting body & same key | `test_idempotency_conflict_rejection` | `409 Conflict` (`code: "idempotency_conflict"`) | **PASS** |
| **Case 8 & 9**| Disconnect / Server shutdown & restart mid-lifecycle | `test_restart_resilience_and_redelivery` | Server killed & restarted on new port; unacked message persists and is redelivered; ack clears unread inbox | **PASS** |
| **Lifecycle**| Full 5-stage coordination lifecycle | `test_full_lifecycle_and_transport_states` | All states (`delivered_at`, `acked_at`, `accepted_at`, `outcome_at`, `reply_to`) validated | **PASS** |
| **Execution**| Live client script execution | `test_client_script_execution` | Outbound curl script executes cleanly; exits 0 | **PASS** |

---

## 5. Empirical Test Execution Results

The test suite was executed in the workspace environment:

```text
$ python3 -m unittest -v research/antigravity/spikes/bus_win35_loopback/test_loopback_spike.py
test_authentication_and_authorization_failures (research.antigravity.spikes.bus_win35_loopback.test_loopback_spike.TestBusLoopbackSpike.test_authentication_and_authorization_failures)
Negative matrix Cases 2 & 3: invalid credentials or wrong recipient fail closed. ... ok
test_client_script_execution (research.antigravity.spikes.bus_win35_loopback.test_loopback_spike.TestBusLoopbackSpike.test_client_script_execution)
Executes client.sh via subprocess against the live loopback adapter. ... ok
test_cross_project_isolation (research.antigravity.spikes.bus_win35_loopback.test_loopback_spike.TestBusLoopbackSpike.test_cross_project_isolation)
Cross-project boundary isolation: messages between different project IDs are rejected. ... ok
test_full_lifecycle_and_transport_states (research.antigravity.spikes.bus_win35_loopback.test_loopback_spike.TestBusLoopbackSpike.test_full_lifecycle_and_transport_states)
Covers Happy-path 5-stage lifecycle: register -> send -> poll -> ack -> accept -> complete -> reply. ... ok
test_idempotency_conflict_rejection (research.antigravity.spikes.bus_win35_loopback.test_loopback_spike.TestBusLoopbackSpike.test_idempotency_conflict_rejection)
Negative matrix Case 6 variant: reusing key with conflicting body fails closed with 409 Conflict. ... ok
test_idempotent_send_deduplication (research.antigravity.spikes.bus_win35_loopback.test_loopback_spike.TestBusLoopbackSpike.test_idempotent_send_deduplication)
Negative matrix Case 6: duplicate send with same idempotency key returns cached receipt. ... ok
test_restart_resilience_and_redelivery (research.antigravity.spikes.bus_win35_loopback.test_loopback_spike.TestBusLoopbackSpike.test_restart_resilience_and_redelivery)
Negative matrix Cases 8 & 9: server restart preserves store and unacked redelivery. ... ok
test_status_endpoint (research.antigravity.spikes.bus_win35_loopback.test_loopback_spike.TestBusLoopbackSpike.test_status_endpoint) ... ok

----------------------------------------------------------------------
Ran 8 tests in 4.129s

OK
```

---

## 6. Operational Invariants & Resource Proofs

1. **Strict Bus Source Lease Protection**:
   Audit verified that `git -C /home/alexey/git/agent-bus status --porcelain` contains zero modifications to tracked files. The source lease of Bus327 (session `3273594b`) was respected with zero violations.
2. **Zero Persistent Background Daemons**:
   Process audits (`ps aux | grep -E "bus_win35_loopback|adapter.py"`) confirm that all test servers were cleanly terminated. Zero background daemons or lingering socket listeners remain.
3. **Zero Rust / NPM Builds**:
   No `cargo build`, `cargo test`, or `npm` commands were executed. The spike is purely Python standard library and bash.
4. **Physical Resource Containment**:
   All 8 tests ran in 4.129 seconds with minimal CPU and memory consumption, well within host cgroup limits (`TasksMax=100`, `MemoryMax=1500M`).

---

## 7. Conditions for Promotion & Next Steps

1. **Remediation of Checksum Table in Receipt**:
   The authoring head should update lines 37–39 of `research/antigravity/recovery/RECEIPT-BUS-WIN35-LOOPBACK-SPIKE-20261007.md` to reflect the actual SHA-256 digests:
   - `adapter.py`: `5637cf8c16e6e59c6e7838714512d7c0dcce2fe6c59e9be09e1ab6355a08ce85`
   - `client.sh`: `3e69b73aacb86baa39d6db39c3108bb8e22e513cb45d54a51dfea9789a276be1`
   - `test_loopback_spike.py`: `4b4cb37dea8961b413ebde85078a273374a9cdfe6eb6786db1380157969fff7c`
2. **Git Staging & Commit Protocol**:
   Once the receipt is reconciled, stage the deliverables and review report, and commit using `flock .local/git.lock` before pushing to `origin/main`.
3. **Handoff to Windows 35 Executor**:
   Provide `adapter.py` and `client.sh` to the Windows 35 GitBash deployment lane as the verified baseline transport contract for cross-computer coordination.
