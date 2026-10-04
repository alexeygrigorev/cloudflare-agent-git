# REV-BUS-EXACTPIN-BB8DCAD — Independent Review & Durability Defect Audit of Agent-Coordination

- **Reviewer:** `agent-coordination-reviewer` (Subagent session `935148e3-fd25-4ddf-a916-1a88c087501a`)
- **Caller / Parent:** `antigravity-head` (`46fdb644`, conversation ID `245c7bba-9a7b-45c1-87a7-4537f289f9a5`)
- **Directives:** Codex Principal C2071 / C2072 Review Steering & Durability Directives
- **Target Workspace:** Strictly private local workspace clone at `/home/alexey/git/agent-coordination` (STRICTLY READ-ONLY; 0 canonical edits; NOT a verified public agent-bus remote parity manifest)
- **Target Commit:** `bb8dcad0979b42763985d9282efc35250dec4827` (`bb8dcad`)
- **Commit Subject:** `Record adapter pin a412cea and core successor 207a93f9 in TASKS.`
- **Date / As-of:** 2026-10-04, Europe/Berlin
- **Isolated Scratch Root:** `/home/alexey/git/cloudflare-agent-git/.local/scratch/bus-bb8dcad-review/` (mode `0700`, measured usage 290 KB <= 512 MB, owned repository scratch containment)
- **Verdict:** **REQUEST CHANGES / BOUNDED AUDIT OF LEGACY PIN**

---

## 1. Executive Summary & Verdict Justification

An exhaustive, independent product review, architectural audit, and negative durability falsification of `agent-coordination` was conducted at exact local pin `bb8dcad` (`bb8dcad0979b42763985d9282efc35250dec4827`).

### Verdict: **REQUEST CHANGES / BOUNDED AUDIT OF LEGACY PIN**
While the repository at pin `bb8dcad` demonstrates that all 24 offline functional unit tests and 4 negative mutation tests pass cleanly, deep architectural audit under Codex Principal C2071/C2072 reveals that **pin `bb8dcad` is a legacy adapter pin that fails to integrate core successor `207a93f9` durability fixes**.

The core store in `coordination/bus.py` harbors three critical durability and crash-safety defects:
1. **Short-Write Vulnerability in `_write`:** `os.write(fd, payload)` is executed once without a write loop. Large payloads or partial writes write truncated bytes before `os.fsync`, producing corrupted JSON files upon atomic rename.
2. **Missing Directory Fsync:** `_write` syncs the file descriptor (`os.fsync(fd)`) and renames (`os.replace(tmp, path)`), but **never fsyncs the parent directory**. On host power loss or kernel panic, directory entry updates may be lost, violating POSIX durability guarantees.
3. **Non-Transactional Registration Tearing:** `register()` writes `identities.json` and `tokens.json` as two independent, non-transactional disk writes. A process crash or power loss between the two writes permanently corrupts authentication state, leaving orphaned identities whose tokens can never be validated.
4. **Stale Core Pin Provenance:** The commit subject of `bb8dcad` explicitly records: `"Record adapter pin a412cea and core successor 207a93f9 in TASKS."` The core successor fixes (`207a93f9`) were not applied to this branch, and public `agent-bus` HEAD remains pinned at `f3295f99e188719f5df9fccb22706d8a0e5bb8f8`.

---

## 2. Critical Durability & Crash-Safety Defect Falsification

A dedicated negative testbed (`test_durability_flaws.py`) was executed in isolated scratch (`.local/scratch/bus-bb8dcad-review/`) to demonstrate and verify each architectural flaw.

### 2.1 Flaw 1: Short-Write Vulnerability in `FileBus._write`
In `coordination/bus.py` (lines 108–117):
```python
def _write(self, path: Path, value: Any) -> None:
    tmp = path.with_suffix(".tmp")
    payload = json.dumps(value, indent=2, sort_keys=True)
    fd = os.open(tmp, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
    try:
        os.write(fd, payload.encode("utf-8"))  # BUG: single write, no while loop!
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(tmp, path)
```
- **Vulnerability:** Under POSIX semantics, `os.write()` is permitted to write fewer bytes than requested (e.g. under pipe/buffer pressure, signal interruption, or large message envelopes). Because there is no `while written < len(data):` loop, a short write writes a truncated buffer.
- **Test Falsification (`test_flaw_1_short_write_causes_corrupted_json`):**
  When `os.write` returns partial bytes, `FileBus._write` proceeds to `os.fsync` and `os.replace`. Subsequent `_read()` calls fatally fail with:
  ```text
  json.decoder.JSONDecodeError: Unterminated string starting at: line 2 column 12 (char 13)
  ```
  **Outcome:** Fatal store corruption. A robust implementation requires looping until all bytes are written.

### 2.2 Flaw 2: Missing Parent Directory `fsync`
- **Vulnerability:** In `_write()`, `os.replace(tmp, path)` updates the directory entry linking `path` to the newly written inode. However, the parent directory file descriptor is never opened or fsynced (`os.fsync(dir_fd)`).
- **Durability Boundary Analysis:**
  - *Process Crash:* Inode and buffer cache survive in kernel page cache; the renamed file is visible to other processes on restart.
  - *Host Power Loss / Kernel Panic:* Directory metadata in disk volatile cache is not committed. Upon reboot, the directory may point to the old file, a zero-length file, or an unlinked inode, breaking the claim of crash-restart durability.

### 2.3 Flaw 3: Non-Transactional Registration Tearing
In `coordination/bus.py` (lines 119–143):
```python
def register(self, ...) -> tuple[BusIdentity, str]:
    with FileLock(self._lock):
        identities = self._read(self._identities, {})
        tokens = self._read(self._tokens, {})
        ...
        self._write(self._identities, identities)  # Step 1: Write identities.json
        # CRASH WINDOW: If process dies here, identities.json is updated, but tokens.json is NOT!
        self._write(self._tokens, tokens)          # Step 2: Write tokens.json
        return ident, token
```
- **Vulnerability:** Agent registration spans two independent atomic file replacements. If an interrupted execution or power cut occurs between Step 1 and Step 2, `identities.json` records the new agent UUID, but `tokens.json` has no corresponding bearer token.
- **Test Falsification (`test_flaw_2_registration_tearing_leaves_orphaned_unusable_identity`):**
  Simulating an interruption after `identities.json` write demonstrates that post-crash:
  1. `identities.json` contains `identity_id: "93918f19-..."`.
  2. `tokens.json` is missing the token entirely.
  3. All subsequent calls to `_auth(ident_id, token)` fail permanently with:
     ```text
     BusError: auth_failed:93918f19-4231-42f4-981e-2d405ad5c8e4
     ```
  **Outcome:** The identity is permanently orphaned and unusable. Registration state must either be stored in a single unified transactional record or repaired with two-phase rollback/journaling.

### 2.4 Flaw 4: Stale Core Pin Provenance
Inspection of `coordination/TASKS.json` confirms:
```json
"pins": {
  "agent-coordination": "a412ceaad7aa3f8254c524161b8cb4b2725480f4",
  "agent-bus": "f3295f99e188719f5df9fccb22706d8a0e5bb8f8"
}
```
Commit `bb8dcad` is titled `"Record adapter pin a412cea and core successor 207a93f9 in TASKS."`
The successor commit `207a93f9` (containing durability fixes) was never cherry-picked or integrated into this workspace. Public `agent-bus` HEAD remains `f3295f99`. Therefore, `bb8dcad` represents an unpatched, legacy snapshot of the core store.

---

## 3. Pinned Source Audit & Integrity Manifest

### 3.1 Git State & Working Tree Audit
```bash
git -C /home/alexey/git/agent-coordination log -n 3 --oneline
```
- `bb8dcad` (HEAD -> main, origin/main) Record adapter pin a412cea and core successor 207a93f9 in TASKS.
- `a412cea` Pin typed SSH stdin RPC after cd07 exit inspect.
- `0eba05f` Mark bus review ACCEPT_WITH_FIXES at f3295f9; core owns required fixes.

Status: Clean working tree, 0 untracked files, strictly read-only audit.

### 3.2 Core Modules SHA256 Hash Manifest

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

## 4. Test Suite Execution & Offline Results

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

### 4.1 Core Unit Test Results: 24/24 PASS (Offline Local Baseline)

| Test File | Test Case | Status | Execution Details |
|:---|:---|:---:|:---|
| `test_adapter_cli.py` | `test_devices_lists_allowlist` | **PASS** | Validates CLI devices subcommand outputs valid allowlisted devices JSON |
| `test_bus.py` | `test_register_send_inbox_ack_reply` | **PASS** | Normal registration, send, inbox, ACK, and threaded reply in local store |
| `test_bus.py` | `test_idempotent_send_and_conflict` | **PASS** | Identical payload returns same message; mismatched payload raises `IdempotencyConflict` |
| `test_bus.py` | `test_crash_restart_redelivers_unacked` | **PASS** | Process restart redelivers unacked messages from disk (in-memory crash model) |
| `test_bus.py` | `test_auth_and_unknown_recipient` | **PASS** | Wrong token raises `auth_failed`; unmapped recipient raises `unknown_recipient` |
| `test_bus.py` | `test_identity_is_not_aplexer_session` | **PASS** | Verifies identity is bus-native UUID and independent of aplexer sessions |
| `test_bus_dogfood.py` | `test_two_headless_processes_and_restart` | **PASS** | Two independent headless agent processes communicating via FileBus |
| `test_cursors.py` | `test_idempotent_retry_returns_same_id` | **PASS** | Outbox cursor store deduplicates identical retries |
| `test_cursors.py` | `test_payload_conflict_is_rejected` | **PASS** | Cursor store rejects conflicting payloads under the same key |
| `test_cursors.py` | `test_offline_outbox_and_cursor` | **PASS** | Offline outbox queuing, mark_sent state transitions, and cursor advancement |
| `test_device_registry.py` | `test_loads_more_than_two_host_slots` | **PASS** | Verifies capacity to parse multiple allowlisted host slots from JSON |
| `test_device_registry.py` | `test_unknown_device_and_alias` | **PASS** | Rejects unmapped device IDs and unregistered SSH aliases |
| `test_device_registry.py` | `test_existing_ssh_alias_is_allowlisted` | **PASS** | Validates allowlisted SSH alias resolution |
| `test_envelope.py` | `test_namespaced_id_includes_device_workspace_agent_task` | **PASS** | Namespaced ID formatting: `device/workspace/agent/session/task` |
| `test_envelope.py` | `test_receipt_read_ack_and_outcome_are_distinct_states` | **PASS** | State independence: `send_receipt` != `read_ack` != `agreed` != `completed` |
| `test_guards.py` | `test_inbox_always_allowed` | **PASS** | Inbox delivery mode is always allowed |
| `test_guards.py` | `test_busy_and_draft_and_unknown_reject_pane` | **PASS** | Rejects pane injection on `working`, `running`, unproven empty, or unknown states |
| `test_guards.py` | `test_native_readiness_absent_refuses_pane_even_if_idle` | **PASS** | Fails closed on pane injection because installed aplexer lacks readiness command |
| `test_ssh_relay.py` | `test_send_resolves_catalog_and_records_inbox_receipt` | **PASS** | Resolves recipient in mocked catalog and persists `inbox` receipt |
| `test_ssh_relay.py` | `test_idempotent_retry_does_not_double_send` | **PASS** | Cursor store idempotency prevents double send over mocked transport |
| `test_ssh_relay.py` | `test_unknown_device_rejected` | **PASS** | Send to unregistered target device raises `UnknownDevice` |
| `test_ssh_relay.py` | `test_windows_target_queues_for_client_poll_not_native_binding` | **PASS** | Windows target queues for client poll instead of attempting native aplexer execution |
| `test_ssh_relay.py` | `test_windows_device_has_no_native_catalog` | **PASS** | Confirms Windows client device has no native catalog |
| `test_ssh_relay.py` | `test_localhost_fake_is_not_cross_computer_proof` | **PASS** | Code-level assertion confirming localhost loopback is not cross-computer proof |

**Overall Core Test Result:** **24/24 PASS (100%) in 1.21s**.  
**Adapter Test Result (`adapters/test_adapters.py`):** **7/7 PASS (100%) in 0.04s**.

---

## 5. Negative Mutation Testing in Isolated Scratch

Negative mutation testing was executed in `.local/scratch/bus-bb8dcad-review/test_mutations.py` to confirm that the existing test suite falsifies defects in four key security and state mechanisms.

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

---

## 6. Critical Epistemic Demarcation & Pending Unverified Items (C2071)

### 6.1 Bounding Single-Host Unit Tests
- The passing tests in `tests/test_ssh_relay.py` utilize `FakeTransport` classes that intercept commands in-memory.
- **Unit tests and callback mocks on a single host do NOT prove real cross-host or Windows execution.**
- In live operation, SSH connections encounter network partitions, host key verification changes, latency timeouts, and identity mapping issues. In particular, **unbound SSH identity denial** remains a previously observed real failure mode on live remote aplexer daemons that local callback tests do not clear.

### 6.2 Pending Unverified Capabilities (Real-World Gates)
1. **Genuine Two-Computer / Cross-Host Network Execution:** Verification of bidirectional message transit between Hetzner and an independent external host over live SSH network transport.
2. **Actual Windows Client Execution:** Verification of `adapters/windows_client.py` running natively on an authentic physical or virtual Windows host against a remote aplexer bridge.
3. **Real-Model Multi-Agent Dogfooding:** Live operational verification where autonomous LLM agents (Claude, Codex, Antigravity, Grok) actively exchange production tasks and reviews across machines using the bus.

---

## 7. Required Fixes Before Final Promotion

To resolve the durability blockers identified under C2072, the following changes must be applied to `coordination/bus.py` in successor integration:
1. **Looping `os.write`:**
   ```python
   def _write_all(fd: int, data: bytes) -> None:
       written = 0
       while written < len(data):
           n = os.write(fd, data[written:])
           if n <= 0:
               raise OSError("write failed or returned 0")
           written += n
   ```
2. **Directory `fsync` on Rename:**
   ```python
   os.replace(tmp, path)
   dir_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
   try:
       os.fsync(dir_fd)
   finally:
       os.close(dir_fd)
   ```
3. **Transactional Registration Record:**
   Combine `identities` and `tokens` into a unified transactional record or journal so that a crash never leaves an orphaned identity without a token.
4. **Integrate Core Successor `207a93f9`:**
   Update the workspace pin to integrate successor `207a93f9` and align with public `agent-bus` HEAD (`f3295f99`).

---

## 8. Environmental Invariants & Compliance Audit

| Requirement | Constraint | Observed Audit Value | Status |
|:---|:---|:---|:---:|
| **Target Tree Edits** | Strictly read-only on `/home/alexey/git/agent-coordination` | 0 modifications; `git status` clean | **COMPLIANT** |
| **Compiler Invocations** | ZERO `cargo` or `rustc` commands under human hold | 0 compiler calls executed | **COMPLIANT** |
| **Scratch Disk Space** | Strictly <= 512 MB | 290 KB used | **COMPLIANT** |
| **Scratch Permissions** | Mode 0700 | Verified `drwx------` | **COMPLIANT** |
| **Temporary File Policy** | Scratch containment within repository boundary | `TMPDIR` redirected to `.local/scratch/bus-bb8dcad-review/` | **COMPLIANT** |
| **Process Memory** | Cooperative pool <= 1500 MB | Peak pytest RSS ~38 MB | **COMPLIANT** |
| **Credential Safety** | Zero raw secrets or tokens in deliverable | Validated clean via `publication_guard.py` | **COMPLIANT** |

### Scratch Containment vs. OS-Level Proof Note:
Subagent execution enforced a strict repository containment policy: all test and scratch operations redirected `TMPDIR` into `.local/scratch/bus-bb8dcad-review/` (mode `0700`). In accordance with C2071, this is recorded as an owned containment policy rather than an OS-level proof of zero temporary file allocation across unmonitored background system daemons.

### Publication Guard Verification:
```bash
python3 /home/alexey/git/cloudflare-agent-git/research/antigravity/tooling/publication_guard.py \
    /home/alexey/git/cloudflare-agent-git/research/antigravity/reviews/REV-BUS-EXACTPIN-BB8DCAD.md
```
Exit code: `0` (Zero credentials, tokens, or private keys detected).
