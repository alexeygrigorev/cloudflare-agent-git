# REV-QL-FILEBUS-BACKEND — Independent Technical Audit of Quota Launcher Headless FileBus Backend (Directives C2437, C2438, C2441 & C2443)

- **Target Module Under Audit (READ-ONLY):** [`/home/alexey/git/agent-quota-launcher/launcher/filebus_backend.py`](file:///home/alexey/git/agent-quota-launcher/launcher/filebus_backend.py)
  * File Size: 4,361 bytes (117 LOC)
  * SHA256 Checksum: `37878218a7bc241585f31022acb2c39553cbc9e36ffd80f41ee3ee208ce96fe5`
- **Target Canonical Test Suite:** [`/home/alexey/git/agent-quota-launcher/tests/test_filebus_backend.py`](file:///home/alexey/git/agent-quota-launcher/tests/test_filebus_backend.py)
  * File Size: 5,296 bytes (153 LOC)
  * SHA256 Checksum: `3b0d12d6b8845075325d23622ca183b5ffc3fcc8da601a5f1b4c6f70b94e8564`
- **Related Task Units Module:** [`/home/alexey/git/agent-quota-launcher/launcher/task_units.py`](file:///home/alexey/git/agent-quota-launcher/launcher/task_units.py)
  * File Size: 14,594 bytes (451 LOC)
- **Governing Directives:** Codex Principal Directives C2437, C2438, C2441, C2443; Operating Model Reset ([`coordination/OPERATING-MODEL.md`](file:///home/alexey/git/cloudflare-agent-git/coordination/OPERATING-MODEL.md)); User Messages 21, 26, 31, 32, 34
- **Auditor / Challenger:** Independent Non-Author Reviewer (`filebus-backend-reviewer`, Subagent under `antigravity-head`)
- **Parent Orchestrator:** `antigravity-head` (`46fdb644-9b58-4e2f-aab3-9be5e1e33337`, ID `245c7bba-9a7b-45c1-87a7-4537f289f9a5`)
- **Audit Timestamp:** `2026-10-05T09:32:00Z` / `2026-10-05T11:32:00+02:00`
- **First-Action Artifact:** [`.local/scratch/review-filebus-backend/first-action.json`](file:///home/alexey/git/cloudflare-agent-git/.local/scratch/review-filebus-backend/first-action.json) (mode `0600`)
- **Scratch Workspace:** `.local/scratch/review-filebus-backend/` (mode `0700`, disk: 20 KB $\le$ 512 MB ceiling, net `/tmp` growth = 0 bytes)
- **Invariants Enforced:**
  * STRICTLY READ-ONLY audit of `/home/alexey/git/agent-quota-launcher` (zero repo modifications)
  * ZERO `cargo` / `rustc` compiler invocations host-wide under human hold
  * Memory $\le$ 1500 MB cooperative pool
  * Zero raw secrets or tokens
- **Verdict:** **FULL ACCEPTANCE**

---

## 1. Executive Summary & Review Verdict

Under Codex Principal Directives C2441 and C2443, this independent non-author technical audit evaluates the headless FileBus backend implementation authored for Agent Quota Launcher in [`launcher/filebus_backend.py`](file:///home/alexey/git/agent-quota-launcher/launcher/filebus_backend.py) and its unit test suite [`tests/test_filebus_backend.py`](file:///home/alexey/git/agent-quota-launcher/tests/test_filebus_backend.py).

The audit verified all five core design pillars of the FileBus backend:
1. **Typed Worker Identity (`FILEBUS_IDENTITY_REQUIRED`):** All 7 mandatory fields (`task_id`, `bus_identity`, `task_message_id`, `ack_id`, `reply_id`, `outcome`, `provider`) are strictly required non-empty strings, with outcome restricted to a validated 4-state lifecycle enum (`accepted`, `completed`, `failed`, `blocked`).
2. **Fail-Closed Exclusion of Native Whoami:** `is_native_whoami()` and `validate_filebus_identity()` strictly detect and reject native aplexer session records containing cgroup and socket markers (`worker_cgroup`, `workload_cgroup`, `socket_path`), categorically preventing interactive TUI sessions from masquerading as headless FileBus workers.
3. **Headless Admission & Strict Host Floors:** `admit_headless()` integrates canonical quota admission (`validate_quse`) and resource checks (`check_resources`), strictly bounds worker memory to $\le$ 1500 MiB, enforces host MemAvailable $\ge$ 10 GiB and filesystem free $\ge$ 50 GiB, and confines temporary execution scratch to repo-owned `.local/tmp`, explicitly rejecting `/tmp`.
4. **Fail-Closed Dispatch Fencing:** `dispatch_headless_task()` strictly refuses live task spawns pending verification of manager-spawned sibling systemd task units outside the head cgroup (`aplexer-workload-6be4c247-4410-4bdb-968e-7fc2d5844941.scope`). The documented wiring target is [`launcher/task_units.py`](file:///home/alexey/git/agent-quota-launcher/launcher/task_units.py)::`execute_transient_task_unit()`.
5. **Canonical Store Integration:** `plan_filebus_task()` queues tasks idempotently into SQLite with `state="queued"` and `BLOCKED_REASON` without live worker spawning, while `attach_filebus_identity()` verifies task existence, identity match, and writes formatted receipt records.

Across testing:
- **Canonical FileBus Suite:** 9 of 9 unit tests passed in 0.487s.
- **Quota Launcher Full Regression Suite:** 133 of 133 tests passed in 5.513s with zero regressions.
- **Independent Adversarial Suite:** 8 of 8 edge-case and mutation tests passed in 0.337s.

**Verdict: FULL ACCEPTANCE.**

---

## 2. Cryptographic Checksums & Code Verification

Both files under audit were cryptographically hashed and inspected:

| File | Size (Bytes) | LOC | SHA256 Checksum |
|---|---|---|---|
| [`launcher/filebus_backend.py`](file:///home/alexey/git/agent-quota-launcher/launcher/filebus_backend.py) | 4,361 | 117 | `37878218a7bc241585f31022acb2c39553cbc9e36ffd80f41ee3ee208ce96fe5` |
| [`tests/test_filebus_backend.py`](file:///home/alexey/git/agent-quota-launcher/tests/test_filebus_backend.py) | 5,296 | 153 | `3b0d12d6b8845075325d23622ca183b5ffc3fcc8da601a5f1b4c6f70b94e8564` |

---

## 3. Detailed Technical Audit Findings

### 3.1 Typed FileBus Identity Contract (`FILEBUS_IDENTITY_REQUIRED`)

In `launcher/filebus_backend.py` (lines 17–25, 40–51):
```python
FILEBUS_IDENTITY_REQUIRED = (
    "task_id",
    "bus_identity",
    "task_message_id",
    "ack_id",
    "reply_id",
    "outcome",
    "provider",
)

def validate_filebus_identity(record: dict) -> bool:
    if not isinstance(record, dict):
        return False
    if is_native_whoami(record):
        return False
    for key in FILEBUS_IDENTITY_REQUIRED:
        val = record.get(key)
        if not val or not isinstance(val, str):
            return False
    if record.get("outcome") not in ("accepted", "completed", "failed", "blocked"):
        return False
    return True
```

**Audit Analysis:**
- **Exact Field Count:** Exactly 7 fields are required. Missing any single field immediately yields `False`.
- **Type Rigor:** The validation strictly requires non-empty strings (`not val or not isinstance(val, str)`). Integer IDs, nulls, booleans, empty strings, and dictionary subtrees are rejected.
- **Outcome Enum Guard:** `record.get("outcome")` is checked against an explicit whitelist `("accepted", "completed", "failed", "blocked")`. Non-standard status strings (such as `"success"`, `"pass"`, `"running"`, or `"COMPLETED"`) are rejected fail-closed.
- **Input Type Guard:** Non-dictionary inputs (`None`, strings, lists) safely return `False` without raising unhandled exceptions.

### 3.2 Strict Differentiation from Native `aplexer whoami`

In `launcher/filebus_backend.py` (lines 27, 34–38):
```python
NATIVE_WHOAMI_MARKERS = ("worker_cgroup", "workload_cgroup", "socket_path")

def is_native_whoami(record: dict) -> bool:
    if not isinstance(record, dict):
        return False
    return any(k in record for k in NATIVE_WHOAMI_MARKERS)
```

**Audit Analysis:**
- Native `aplexer whoami --json` records identify interactive TUI panes containing daemon sockets and systemd scopes (e.g., `worker_cgroup: "/user.slice/user-1000.slice/session-8309.scope"`, `socket_path: "/run/user/1000/aplexer/sessions/.../control.sock"`).
- `validate_filebus_identity()` invokes `is_native_whoami()` as its very first sanity check. If *any* marker is present, validation returns `False`.
- Furthermore, `attach_filebus_identity()` invokes `validate_filebus_identity()` before interacting with the store or filesystem, raising `FileBusBackendError("invalid FileBus identity")` if a native record is submitted.
- **Architectural Significance:** This guarantees that an agent or runner cannot substitute its own interactive session context for a genuine headless FileBus worker dispatch receipt.

### 3.3 Headless Admission & Resource Containment (`admit_headless`)

In `launcher/filebus_backend.py` (lines 54–65):
```python
def admit_headless(quse_json, memory_mb, workspace, tmpdir, active_mem_mb=0, active_disk_mb=0):
    """Reuse canonical admission. Fail-closed. Does not raise pids.max."""
    validate_quse(quse_json)
    if int(memory_mb) > 1500:
        raise FileBusBackendError("worker memory exceeds 1500M ceiling")
    check_resources(int(memory_mb), workspace, tmpdir, active_mem_mb, active_disk_mb,
                    repo_root=workspace)
    tmp = Path(tmpdir).resolve()
    root = Path(workspace).resolve() / ".local" / "tmp"
    if not tmp.is_relative_to(root):
        raise FileBusBackendError("TMPDIR must be under repo .local/tmp")
    return True
```

**Audit Analysis:**
- **Memory Ceiling:** Enforces an absolute upper bound of 1500 MiB (`int(memory_mb) > 1500`). Any request exceeding this limit is immediately aborted.
- **Quota Validation:** Calls canonical `validate_quse()`, verifying fresh window evidence and failing closed on invalid or expired quotas.
- **Host Resource Floors:** Calls canonical `check_resources()`, asserting:
  * Host MemAvailable $\ge$ 10 GiB floor minus active reservations and requested memory.
  * Host filesystem free $\ge$ 50 GiB floor plus reservations and 512 MiB spike budget.
  * Rejection of system `/tmp`.
- **TMPDIR Isolation Defense-in-Depth:** In addition to `check_resources()`, `admit_headless()` performs its own explicit path resolution check requiring `tmp.is_relative_to(repo_root / ".local" / "tmp")`, preventing directory traversal or symlink attacks.
- **PID Invariant:** Does not raise `pids.max` or modify cgroup hierarchies directly during admission.

### 3.4 Headless Task Dispatch Fencing & Transient Unit Wiring Path

In `launcher/filebus_backend.py` (lines 68–84):
```python
def dispatch_headless_task(payload: dict) -> dict:
    """Fail-closed until transient task-unit path is source-tested.

    Nested `aplexer start` from quota-launcher-head inherits the head
    100-pid/1500M cgroup (C2438). Sidecar/coordinator already live in
    session-10825.scope outside that unit; this function still refuses
    live spawn until a tested systemd-run --user transient unit recipe
    exists that does not raise parent limits.
    """
    if payload.get("backend") != "filebus":
        raise FileBusBackendError("backend must be filebus")
    raise FileBusBackendError(
        "live filebus dispatch held: missing source-tested transient "
        "task unit outside aplexer-workload-6be4c247; sidecar session-10825 "
        "is outside head cgroup but has no documented spawn API"
    )
```

**Audit Analysis:**
- **Strict Fail-Closed Status:** `dispatch_headless_task()` validates backend `"filebus"` and unconditionally raises `FileBusBackendError`, preventing premature live worker launches.
- **Root Cause Fencing:** Explains Directive C2438: spawning nested `aplexer start` instances from within `quota-launcher-head` causes children to be trapped in the head's 100-PID / 1500 MiB scope (`aplexer-workload-6be4c247...`), risking parent exhaustion.
- **Wiring Roadmap to `launcher/task_units.py`:**
  * The sibling module [`launcher/task_units.py`](file:///home/alexey/git/agent-quota-launcher/launcher/task_units.py) has implemented `execute_transient_task_unit()`.
  * `execute_transient_task_unit()` invokes `systemd-run --user --unit=agent-task-<id>.service --slice=app.slice -p MemoryMax=1500M -p TasksMax=100 ...` (detached service unit, strictly omitting `--scope`).
  * It injects an isolation prelude (`generate_prelude_code()`) that checks `/proc/self/cgroup` and kills the process if nested under any `aplexer-workload-` scope.
  * It verifies post-execution cleanup (`verify_task_unit_cleanup()`) checking `cgroup.events` `populated == 0` and zero lingering PIDs.
  * Once end-to-end integration is authorized, `dispatch_headless_task()` can directly invoke `execute_transient_task_unit()` without altering the fail-closed identity and admission boundaries.

### 3.5 Store Integration & Receipt Persistence

In `launcher/filebus_backend.py` (lines 86–116):
```python
BLOCKED_REASON = (
    "filebus queued; live dispatch held until launcher/task_units.py "
    "source-tests a manager-spawned sibling TASK unit outside the head cgroup"
)

def plan_filebus_task(store: Store, task_id: str, idempotency_key: str, payload: dict,
                      paths, memory_mb=1500, disk_mb=512) -> str:
    """Queue a FileBus task in the canonical Store. Does not spawn a worker."""
    if payload.get("backend") != "filebus":
        raise FileBusBackendError("backend must be filebus")
    if int(memory_mb) > 1500:
        raise FileBusBackendError("worker memory exceeds 1500M ceiling")
    queued = store.submit_task(task_id, idempotency_key, payload, paths, memory_mb, disk_mb)
    store.record_reason(queued, BLOCKED_REASON)
    return queued

def attach_filebus_identity(store: Store, task_id: str, identity: dict, receipt_path: str) -> dict:
    """Persist a typed FileBus identity receipt. Native whoami is rejected."""
    if not validate_filebus_identity(identity):
        raise FileBusBackendError("invalid FileBus identity")
    task = store.get_task(task_id)
    if task is None:
        raise FileBusBackendError("unknown task_id")
    if identity["task_id"] != task_id:
        raise FileBusBackendError("identity.task_id mismatch")
    path = Path(receipt_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(identity, indent=2, sort_keys=True) + "\n")
    return identity
```

**Audit Analysis:**
- **Planning Isolation:** `plan_filebus_task()` enters the task into the SQLite database with `state="queued"` and records `BLOCKED_REASON`. It does *not* invoke `dispatch_task` or spawn background processes.
- **Idempotency & Path Leases:** Reuses `store.submit_task()`, which enforces lease path conflict checks and idempotency key constraints.
- **Store Verification on Attachment:** `attach_filebus_identity()` verifies that `task_id` actually exists in the store before saving any receipt.
- **ID Consistency:** Asserts `identity["task_id"] == task_id`.
- **Deterministic Persistence:** Writes formatted JSON with `indent=2, sort_keys=True` to the specified receipt path.

---

## 4. Empirical Test Suite Verification

### 4.1 Canonical Test Suite Execution

Executed canonical unit tests via `unittest discover`:
```bash
PYTHONPATH=/home/alexey/git/agent-quota-launcher python3 -m unittest discover \
  -s /home/alexey/git/agent-quota-launcher/tests -p "test_filebus_backend.py" -v
```

**Results:**
```text
test_tmp_not_under_repo_rejected (test_filebus_backend.FileBusAdmissionTests.test_tmp_not_under_repo_rejected) ... ok
test_dispatch_does_not_call_aplexer (test_filebus_backend.FileBusDispatchTests.test_dispatch_does_not_call_aplexer) ... ok
test_wrong_backend_rejected (test_filebus_backend.FileBusDispatchTests.test_wrong_backend_rejected) ... ok
test_complete_filebus_identity_accepted (test_filebus_backend.FileBusIdentityTests.test_complete_filebus_identity_accepted) ... ok
test_missing_ack_rejected (test_filebus_backend.FileBusIdentityTests.test_missing_ack_rejected) ... ok
test_native_whoami_is_rejected (test_filebus_backend.FileBusIdentityTests.test_native_whoami_is_rejected) ... ok
test_attach_identity_roundtrip (test_filebus_backend.FileBusStoreTests.test_attach_identity_roundtrip) ... ok
test_attach_rejects_native_whoami (test_filebus_backend.FileBusStoreTests.test_attach_rejects_native_whoami) ... ok
test_plan_queues_blocked_without_spawn (test_filebus_backend.FileBusStoreTests.test_plan_queues_blocked_without_spawn) ... ok

----------------------------------------------------------------------
Ran 9 tests in 0.487s

OK
```

### 4.2 Full Agent Quota Launcher Regression Suite

Executed the entire test suite across all modules in `agent-quota-launcher`:
```bash
PYTHONPATH=/home/alexey/git/agent-quota-launcher python3 -m unittest discover \
  -s /home/alexey/git/agent-quota-launcher/tests -v
```
**Results:** **133 of 133 tests passed in 5.513s** with zero failures or regressions.

### 4.3 Independent Adversarial Test Suite

An independent test script was authored and executed in scratch ([`.local/scratch/review-filebus-backend/test_adversarial_filebus.py`](file:///home/alexey/git/cloudflare-agent-git/.local/scratch/review-filebus-backend/test_adversarial_filebus.py)):

| Test Case | Scenario Evaluated | Result |
|---|---|---|
| `test_non_dict_inputs` | Passing `None`, strings, ints, lists, bools to `is_native_whoami` & `validate_filebus_identity` | PASSED (safe `False`) |
| `test_individual_native_markers` | Corrupting valid identity with individual markers (`worker_cgroup`, `workload_cgroup`, `socket_path`) | PASSED (rejected) |
| `test_all_required_fields_non_empty_string` | Corrupting each of the 7 fields with `""`, `None`, integers, lists, dicts | PASSED (all rejected) |
| `test_outcome_enum_strictness` | Whitelist checks (`accepted`, `completed`, `failed`, `blocked`) vs invalid outcomes (`running`, `success`, `pass`, `error`) | PASSED |
| `test_memory_ceiling_admit_headless` | Requesting 1501 MiB memory in `admit_headless()` | PASSED (raises `FileBusBackendError`) |
| `test_memory_ceiling_plan_filebus_task` | Requesting 1501 MiB memory in `plan_filebus_task()` | PASSED (raises `FileBusBackendError`) |
| `test_plan_filebus_task_backend_mismatch` | Submitting task with `backend: "aplexer"` to `plan_filebus_task()` | PASSED (raises `FileBusBackendError`) |
| `test_attach_unknown_task_and_mismatch` | Attempting identity attachment on non-existent task or mismatched task ID | PASSED (raises `FileBusBackendError`) |

**Result:** **8 of 8 adversarial tests passed in 0.337s.**

---

## 5. Security & Isolation Invariant Checklist

| Invariant / Check | Requirement | Audit Evidence | Status |
|---|---|---|---|
| **Zero Workspace Mutations** | Strictly read-only audit of `agent-quota-launcher` | `git status --porcelain` showed zero changes to working directory | PASS |
| **No Cargo/Rust Invocation** | Zero `cargo` or `rustc` commands executed | Audit performed entirely in Python standard library | PASS |
| **Memory Cooperative Ceiling** | Process RSS $\le$ 1500 MiB cooperative pool | Max RSS during tests $\le$ 45 MB | PASS |
| **Scratch Space Bounds** | Scratch dir $\le$ 512 MB, mode `0700`, net `/tmp` growth = 0 | `.local/scratch/review-filebus-backend/` size 20 KB, mode `0700` | PASS |
| **Credential & Token Privacy** | Zero raw bearer tokens, secrets, or proxy URLs in deliverable | Validated via `publication_guard.py` | PASS |
| **Fail-Closed Execution** | Missing or invalid identity/admission fails closed | All invalid inputs raise typed exceptions or return `False` | PASS |

---

## 6. Review Conclusion & Final Verdict

The implementation of [`launcher/filebus_backend.py`](file:///home/alexey/git/agent-quota-launcher/launcher/filebus_backend.py) and [`tests/test_filebus_backend.py`](file:///home/alexey/git/agent-quota-launcher/tests/test_filebus_backend.py) satisfies all design specifications and safety criteria mandated under Directives C2437, C2438, C2441, and C2443:
- Fully validates typed FileBus identities while categorically blocking native TUI aplexer records.
- Preserves canonical host resource admission and strict $\le$ 1500 MiB memory ceilings.
- Restricts temporary workspace directory to repo `.local/tmp`.
- Keeps live task dispatch safely gated until sibling systemd task unit execution outside the head cgroup is integrated.
- Integrates seamlessly with SQLite store persistence and receipts.

**Final Verdict: FULL ACCEPTANCE**
