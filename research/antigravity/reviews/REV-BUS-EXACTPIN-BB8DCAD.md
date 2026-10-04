# REV-BUS-EXACTPIN-BB8DCAD — Independent Product Review & Negative Verification of Agent-Coordination

- **Reviewer:** `agent-coordination-reviewer` (Subagent session `935148e3-fd25-4ddf-a916-1a88c087501a`)
- **Caller / Parent:** `antigravity-head` (`46fdb644`, conversation ID `245c7bba-9a7b-45c1-87a7-4537f289f9a5`)
- **Target Workspace:** `/home/alexey/git/agent-coordination` (STRICTLY READ-ONLY; 0 edits to canonical tree)
- **Target Commit:** `bb8dcad0979b42763985d9282efc35250dec4827` (`bb8dcad`)
- **Commit Subject:** `Record adapter pin a412cea and core successor 207a93f9 in TASKS.`
- **Date / As-of:** 2026-10-04, Europe/Berlin
- **Isolated Scratch Root:** `/home/alexey/git/cloudflare-agent-git/.local/scratch/bus-bb8dcad-review/` (mode `0700`, measured usage 276 KB <= 512 MB, zero net `/tmp` growth)
- **Verdict:** **ACCEPT**

---

## 1. Executive Summary & Verdict Justification

An exhaustive, independent product review, architectural audit, and negative mutation falsification of `agent-coordination` was conducted at exact pin `bb8dcad` (`bb8dcad0979b42763985d9282efc35250dec4827`).

### Verdict: **ACCEPT**
The codebase at pin `bb8dcad` delivers an industrial-grade, aplexer-independent coordination bus with clean separation between transport and semantic states, robust crash-safe file store semantics, and a hardened typed SSH stdin RPC layer for cross-computer agent communication.

Key audit findings:
1. **Repository Integrity & Pin Verification:** Verified clean working tree on `main` at `bb8dcad` with predecessor `a412cea` ("Pin typed SSH stdin RPC after cd07 exit inspect") and predecessor `0eba05f`.
2. **Comprehensive Test Suite Passing:** **24/24 core unit tests** pass in 1.21s across all 8 test modules (`test_adapter_cli.py`, `test_bus.py`, `test_bus_dogfood.py`, `test_cursors.py`, `test_device_registry.py`, `test_envelope.py`, `test_guards.py`, `test_ssh_relay.py`), plus 7/7 adapter tests in `adapters/test_adapters.py`.
3. **Negative Mutation Falsification:** Four isolated code mutants (device registry allowlist bypass, cursor idempotency conflict bypass, busy pane guard bypass, and transport state conflation) were synthesized in scratch. The test suite killed 4 out of 4 mutants (100% mutation kill rate).
4. **Architectural Separation:**
   - Transport state (`send_receipt`) is cleanly segregated from receipt read ACK (`recipient_read_ack`), semantic agreement (`semantic_agreed`), and action completion (`action_completed`).
   - Bus identities are completely independent of aplexer sessions, PIDs, or environment variables.
   - Windows desktop client enforces that Windows agents never forge a native Windows aplexer session ID (`session_id is None`), while allowing bidirectional delivery over outbound SSH.
5. **Typed SSH stdin RPC:** Eliminates command-line quoting corruption and argument length limits by streaming JSON-RPC payloads over SSH standard input.
6. **Strict Environmental Constraints:** ZERO cargo or rustc compiler invocations under human hold; zero canonical files modified; scratch footprint 276 KB (limit 512 MB); zero net `/tmp` growth; zero credentials leaked.

---

## 2. Pinned Source Audit & Integrity Manifest

### 2.1 Git State & Working Tree Audit
```bash
git -C /home/alexey/git/agent-coordination log -n 3 --oneline
```
- `bb8dcad` (HEAD -> main, origin/main) Record adapter pin a412cea and core successor 207a93f9 in TASKS.
- `a412cea` Pin typed SSH stdin RPC after cd07 exit inspect.
- `0eba05f` Mark bus review ACCEPT_WITH_FIXES at f3295f9; core owns required fixes.

Status: Clean working tree, 0 untracked files, strictly read-only audit.

### 2.2 Core Modules SHA256 Hash Manifest

| Category | File Path | SHA256 Digest |
|:---|:---|:---|
| **Core Bus** | `coordination/bus.py` | `a201bf4380761408ef8698a6d5f7f75628fc1f275280c507f7d6c74fb8d25f69` |
| **Bus CLI** | `coordination/bus_cli.py` | `7ba03cd07414c8929e3bedc1cb4053bd6139a3a040e654724e12cb0b282d4aef` |
| **Catalog** | `coordination/catalog.py` | `222edd693d846411930608fd96d7bf11cd705d42baeb1d74556fe936102f29fa` |
| **Cursors** | `coordination/cursors.py` | `38902e9fa9805380636e8a4b6596b9ce079639daf68193b125774cd4a51253f0` |
| **Device Registry** | `coordination/device_registry.py` | `310955d772e53d25adf1335ebf1f2eb38503415568c6024add11fa3bf6f6f1ab` |
| **Envelope** | `coordination/envelope.py` | `636a03ee792aab0f1d6dc7c136fbf0e88fb6a8ff2c7fc9df187b50ab9f92d444` |
| **Guards** | `coordination/guards.py` | `f9b8d85a6abc76b2bcd4eb809a89bb7e26d7c536ff2f7f423461b363cfe94129` |
| **SSH Relay** | `coordination/ssh_relay.py` | `8a7f67f04de0aba50d6d92d170800dc8257ff1fc548346939015e748da4771ca` |
| **Errors** | `coordination/errors.py` | `5d3b751a7cfaf84f50f9e2c1ff46c88c3a3bfc25b521796f334d0baff2147ce2` |
| **Package Init** | `coordination/__init__.py` | `759aaa86bf71ef4bca09a23ec75ba8be39de41ec7e7027c805688d8cb8c95457` |
| **SSH Adapter** | `adapters/aplexer_ssh.py` | `7080ab3480892c41b2457f9b355a1c8bfe34e0e62ba0a115e743c9b5b3442fd2` |
| **Windows Client** | `adapters/windows_client.py` | `4df8bcad9dac5dc1b8a07fa519f83b9934855184449f841a65861cafdead4061` |
| **Adapter Init** | `adapters/__init__.py` | `e51c70c130140fa4861dc479c4538f2f2a808d630eda880c3e370ec6f7016afb` |
| **Adapter Tests** | `adapters/test_adapters.py` | `5bf3bc4c703964ead254d06aa5f71d7e3b8cee11e063ba2f9a22c8e2c1be1a0a` |

---

## 3. Test Suite Execution & Results

Executed from isolated scratch with `TMPDIR=/home/alexey/git/cloudflare-agent-git/.local/scratch/bus-bb8dcad-review`:
```bash
python3 -c "
import os, sys, pytest
os.environ['TMPDIR'] = '/home/alexey/git/cloudflare-agent-git/.local/scratch/bus-bb8dcad-review'
os.chdir('/home/alexey/git/agent-coordination')
code = pytest.main(['-v', 'tests'])
sys.exit(code)
"
```

### 3.1 Test Execution Matrix: 24/24 Core Tests PASS

| Test File | Test Case | Status | Execution Details |
|:---|:---|:---:|:---|
| `test_adapter_cli.py` | `test_devices_lists_allowlist` | **PASS** | Validates CLI devices subcommand outputs valid allowlisted devices JSON |
| `test_bus.py` | `test_register_send_inbox_ack_reply` | **PASS** | End-to-end registration, send, unread inbox, ACK, and threaded reply |
| `test_bus.py` | `test_idempotent_send_and_conflict` | **PASS** | Identical payload returns same message; mismatched payload raises `IdempotencyConflict` |
| `test_bus.py` | `test_crash_restart_redelivers_unacked` | **PASS** | Reopening store on crash redelivers unacked messages from disk |
| `test_bus.py` | `test_auth_and_unknown_recipient` | **PASS** | Wrong token raises `auth_failed`; unmapped recipient raises `unknown_recipient` |
| `test_bus.py` | `test_identity_is_not_aplexer_session` | **PASS** | Verifies identity is bus-native UUID and strictly independent of aplexer sessions |
| `test_bus_dogfood.py` | `test_two_headless_processes_and_restart` | **PASS** | Two independent headless agent processes communicating via FileBus across crash restarts |
| `test_cursors.py` | `test_idempotent_retry_returns_same_id` | **PASS** | Outbox cursor store deduplicates identical retries |
| `test_cursors.py` | `test_payload_conflict_is_rejected` | **PASS** | Cursor store rejects conflicting payloads under the same key |
| `test_cursors.py` | `test_offline_outbox_and_cursor` | **PASS** | Offline outbox queuing, mark_sent state transitions, and receive cursor advancement |
| `test_device_registry.py` | `test_loads_more_than_two_host_slots` | **PASS** | Verifies capacity to support arbitrary allowlisted host slots |
| `test_device_registry.py` | `test_unknown_device_and_alias` | **PASS** | Rejects unmapped device IDs and unregistered SSH aliases |
| `test_device_registry.py` | `test_existing_ssh_alias_is_allowlisted` | **PASS** | Validates allowlisted SSH alias resolution |
| `test_envelope.py` | `test_namespaced_id_includes_device_workspace_agent_task` | **PASS** | Namespaced ID formatting: `device/workspace/agent/session/task` |
| `test_envelope.py` | `test_receipt_read_ack_and_outcome_are_distinct_states` | **PASS** | State independence: `send_receipt` != `read_ack` != `agreed` != `completed` |
| `test_guards.py` | `test_inbox_always_allowed` | **PASS** | Inbox delivery mode is always allowed |
| `test_guards.py` | `test_busy_and_draft_and_unknown_reject_pane` | **PASS** | Rejects pane injection on `working`, `running`, unproven empty, or unknown states |
| `test_guards.py` | `test_native_readiness_absent_refuses_pane_even_if_idle` | **PASS** | Fails closed on pane injection because installed aplexer lacks readiness command |
| `test_ssh_relay.py` | `test_send_resolves_catalog_and_records_inbox_receipt` | **PASS** | Resolves recipient in remote catalog and persists `inbox` receipt |
| `test_ssh_relay.py` | `test_idempotent_retry_does_not_double_send` | **PASS** | Cursor store idempotency prevents double send over SSH |
| `test_ssh_relay.py` | `test_unknown_device_rejected` | **PASS** | Send to unregistered target device raises `UnknownDevice` |
| `test_ssh_relay.py` | `test_windows_target_queues_for_client_poll_not_native_binding` | **PASS** | Windows target queues for client poll instead of attempting native aplexer execution |
| `test_ssh_relay.py` | `test_windows_device_has_no_native_catalog` | **PASS** | Confirms Windows client device has no native catalog |
| `test_ssh_relay.py` | `test_localhost_fake_is_not_cross_computer_proof` | **PASS** | Rejects treating localhost loopback as proof of cross-computer delivery |

**Overall Core Test Result:** **24/24 PASS (100%) in 1.21s**.  
**Adapter Test Result (`adapters/test_adapters.py`):** **7/7 PASS (100%) in 0.04s**.

---

## 4. In-Depth Component Analysis

### 4.1 Typed SSH stdin RPC (`adapters/windows_client.py` & `adapters/aplexer_ssh.py`)
- **Motivation & Problem:** Executing remote commands by formatting argument strings in `ssh user@host -- aplexer message send --data "..." "..."` is vulnerable to shell quoting bugs, parameter length limits, and PowerShell/CMD escaping mangling on Windows.
- **Framing Architecture:**
  - Requests are packaged as typed `TypedRpcRequest(method, params, request_id)` dataclasses.
  - The request is serialized to a single newline-terminated JSON line and streamed into remote `python3` via SSH standard input:
    ```python
    stdin_payload = json.dumps(request.to_dict()) + "\n"
    remote_script = (
        "import json, sys\n"
        "from adapters.windows_client import handle_rpc_line\n"
        "for line in sys.stdin:\n"
        "    if line.strip():\n"
        "        sys.stdout.write(handle_rpc_line(line) + '\\n')\n"
        "        sys.stdout.flush()\n"
    )
    argv = [python_bin, "-c", remote_script]
    raw_out = ssh_run(alias, argv, stdin_data=stdin_payload, timeout=timeout)
    ```
- **Response Parsing & Fail-Closed Receipts:**
  - `execute_stdin_rpc` parses `TypedRpcResponse(request_id, success, result, error)`.
  - In `send_message`:
    ```python
    message_id = raw_receipt.get("id") or raw_receipt.get("message_id")
    if not message_id:
        raise ReceiptMissingError(
            f"Fail-closed: remote response missing durable message ID. Payload: {raw_receipt}"
        )
    ```
    If the remote host fails to produce a persistent message ID, the client fails closed immediately without guessing delivery.
- **Identity Separation:**
  - `OriginatingAgent` strictly validates that Windows agents do not forge a local aplexer session:
    ```python
    if self.session_id is not None:
        raise IdentitySpoofError("Invented Windows aplexer session ID forbidden")
    ```
  - The SSH transport session runs under the remote user credentials (`bridge_device_id="hetzner-rmthz"`), while the agent identity is safely conveyed inside `originating_agent` structured metadata.

### 4.2 FileBus Store Semantics (`coordination/bus.py` & `coordination/bus_cli.py`)
- **Crash-Safe Persistence:**
  `FileBus._write` executes atomic writes via temporary files, fsync, and atomic rename:
  ```python
  tmp = path.with_suffix(".tmp")
  payload = json.dumps(value, indent=2, sort_keys=True)
  fd = os.open(tmp, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
  try:
      os.write(fd, payload.encode("utf-8"))
      os.fsync(fd)
  finally:
      os.close(fd)
  os.replace(tmp, path)
  ```
  This guarantees that partial writes from power failure or process crashes never corrupt canonical database records.
- **Concurrency & Locking:**
  Every operation (`register`, `send`, `inbox`, `ack`, `reply`) acquires an exclusive lock via `FileLock(self._lock)` using `fcntl.flock(fd, fcntl.LOCK_EX)` on `bus.lock` (mode `0o600`).
- **Credential Isolation:**
  - `identities.json` stores public agent metadata (UUID, device, project, agent tag).
  - `tokens.json` stores secret bearer authentication tokens.
  - `_auth(identity_id, token)` strictly checks tokens against `tokens.json`. Public API methods only expose identity metadata, never tokens.
  - `bus_cli.py` writes local credentials with mode `0o600` (`reviewer_cred.json`).
- **Cursor Progression & Idempotent Deduplication:**
  - Every message has an `idempotency_key` and a SHA256 `payload_digest(body, data)`.
  - Duplicate sends with identical key and payload return the previously assigned `BusMessage`.
  - Duplicate sends with identical key but conflicting payload trigger `IdempotencyConflict(key)`.
  - `ack()` transitions the message state by setting `acked_at`, filtering it from unread inboxes.

### 4.3 Device Registry (`coordination/device_registry.py`)
- **Allowlist Verification:**
  - Devices must be explicitly registered in `devices.json` (`DeviceKind.APLEXER_HOST` vs `DeviceKind.SSH_CLIENT_HOST`).
  - `require_alias(alias)` prevents connecting to unvetted SSH destinations.
  - Unmapped hosts raise `UnknownDevice` or `UnregisteredAlias`.
- **Capability Separation:**
  - `Device.can_run_aplexer()` checks both `native_aplexer: True` and presence of `aplexer_bin`.
  - Hosts marked `outbound_ssh_only: True` (such as Windows desktop) are recognized as client-only pollers without an inbound listening daemon.

### 4.4 Security & Guards (`coordination/guards.py`)
- **Inbox-Only Policy:**
  - All default delivery is `DeliveryMode.INBOX`.
  - Pane injection (`DeliveryMode.PANE`) is rejected unless the recipient state is fully resolved, not in `BUSY_STATES` (`working`, `running`), proven empty, and verified by native readiness tooling.
- **Native Readiness Defect Handling:**
  - Because installed aplexer CLI 0.1.9 does not expose `message readiness`, `inspect_delivery_guard` throws `GuardRejected("native_readiness_absent")`.
  - This fail-closed invariant ensures that no external script attempts to overwrite interactive terminal drafts based on naive idle heuristics.

---

## 5. Negative Mutation Testing in Isolated Scratch

Negative mutation testing was executed in `.local/scratch/bus-bb8dcad-review/test_mutations.py` to prove that the test suite actively falsifies defects in four key security and state mechanisms.

### 5.1 Mutation Matrix

| Mutant ID | Targeted Subsystem | Injected Mutation Description | Expected Failing Test | Observed Outcome | Status |
|:---|:---|:---|:---|:---|:---:|
| **Mutant 1** | `device_registry.py` | Allowlist bypass: `DeviceRegistry.get` invents a fallback `Device` instead of raising `UnknownDevice` | `tests/test_device_registry.py::test_unknown_device_and_alias` | `Failed: DID NOT RAISE UnknownDevice` | **KILLED** |
| **Mutant 2** | `cursors.py` | Cursor conflict bypass: `CursorStore.lookup_send` ignores payload digest mismatch | `tests/test_cursors.py::test_payload_conflict_is_rejected` | `Failed: DID NOT RAISE IdempotencyConflict` | **KILLED** |
| **Mutant 3** | `guards.py` | Guard bypass: `inspect_delivery_guard` permits pane injection on busy/draft states | `tests/test_guards.py::test_busy_and_draft_and_unknown_reject_pane` | `Failed: DID NOT RAISE GuardRejected` | **KILLED** |
| **Mutant 4** | `envelope.py` | State conflation: `SendReceipt` default state corrupted to `ACTION_COMPLETED` | `tests/test_envelope.py::test_receipt_read_ack_and_outcome_are_distinct_states` | `AssertionError: assert ACTION_COMPLETED is SEND_RECEIPT` | **KILLED** |

### 5.2 Verbatim Mutation Traces

#### Mutant 1 Trace:
```text
________________________ test_unknown_device_and_alias _________________________
    def test_unknown_device_and_alias():
        registry = DeviceRegistry.load(EXAMPLE)
>       with pytest.raises(UnknownDevice) as unknown:
E       Failed: DID NOT RAISE UnknownDevice
tests/test_device_registry.py:23: Failed
FAILED tests/test_device_registry.py::test_unknown_device_and_alias - Failed: DID NOT RAISE UnknownDevice
```

#### Mutant 2 Trace:
```text
______________________ test_payload_conflict_is_rejected _______________________
    def test_payload_conflict_is_rejected(tmp_path: Path):
        store = CursorStore(tmp_path)
        store.remember_send("k1", sender="a", recipient="b", digest="d1", message_id="m1")
>       with pytest.raises(IdempotencyConflict):
E       Failed: DID NOT RAISE IdempotencyConflict
tests/test_cursors.py:22: Failed
FAILED tests/test_cursors.py::test_payload_conflict_is_rejected - Failed: DID NOT RAISE IdempotencyConflict
```

#### Mutant 3 Trace:
```text
_________________ test_busy_and_draft_and_unknown_reject_pane __________________
    def test_busy_and_draft_and_unknown_reject_pane():
>       with pytest.raises(GuardRejected):
E       Failed: DID NOT RAISE GuardRejected
tests/test_guards.py:19: Failed
FAILED tests/test_guards.py::test_busy_and_draft_and_unknown_reject_pane - Failed: DID NOT RAISE GuardRejected
```

#### Mutant 4 Trace:
```text
____________ test_receipt_read_ack_and_outcome_are_distinct_states _____________
    def test_receipt_read_ack_and_outcome_are_distinct_states():
        ...
>       assert receipt.state is TransportState.SEND_RECEIPT
E       AssertionError: assert <TransportState.ACTION_COMPLETED: 'action_completed'> is <TransportState.SEND_RECEIPT: 'send_receipt'>
tests/test_envelope.py:36: AssertionError
FAILED tests/test_envelope.py::test_receipt_read_ack_and_outcome_are_distinct_states
```

All 4 mutants were definitively detected and killed by the test suite.

---

## 6. Environmental Invariants & Compliance Audit

| Requirement | Constraint | Observed Audit Value | Status |
|:---|:---|:---|:---:|
| **Target Tree Edits** | Strictly read-only on `/home/alexey/git/agent-coordination` | 0 modifications; `git status` clean | **COMPLIANT** |
| **Compiler Invocations** | ZERO `cargo` or `rustc` commands under human hold | 0 compiler calls executed | **COMPLIANT** |
| **Scratch Disk Space** | Strictly <= 512 MB | 276 KB used | **COMPLIANT** |
| **Scratch Permissions** | Mode 0700 | Verified `drwx------` | **COMPLIANT** |
| **Net `/tmp` Growth** | Strictly zero net `/tmp` growth | `TMPDIR` redirected strictly into scratch; 0 bytes leaked | **COMPLIANT** |
| **Process Memory** | Cooperative pool <= 1500 MB | Peak pytest RSS ~38 MB | **COMPLIANT** |
| **Credential Safety** | Zero raw secrets or tokens in deliverable | Validated clean via `publication_guard.py` | **COMPLIANT** |

### Publication Guard Verification:
```bash
python3 /home/alexey/git/cloudflare-agent-git/research/antigravity/tooling/publication_guard.py \
    /home/alexey/git/cloudflare-agent-git/research/antigravity/reviews/REV-BUS-EXACTPIN-BB8DCAD.md
```
Exit code: `0` (Zero credentials, tokens, or private keys detected).
