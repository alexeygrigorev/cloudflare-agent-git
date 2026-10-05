# REV-QL-CLI-TASK-UNITS-C2458 — Independent Technical Audit of Quota Launcher CLI Task Units Backend (Directives C2456, C2458, C2438 & C2441)

- **Target Module Under Audit (READ-ONLY):** [`/home/alexey/git/agent-quota-launcher/launcher/cli.py`](file:///home/alexey/git/agent-quota-launcher/launcher/cli.py)
  * File Size: 16,725 bytes (437 LOC)
  * SHA256 Checksum: `9a99ff570606a465dde2822c711185a4957f4647e7844df4eca77f9c900c1c93`
- **Target Canonical Test Suite:** [`/home/alexey/git/agent-quota-launcher/tests/test_cli_backend.py`](file:///home/alexey/git/agent-quota-launcher/tests/test_cli_backend.py)
  * File Size: 3,958 bytes (109 LOC)
  * SHA256 Checksum: `4873db480c12744d8813791129fea465d0e1ee66cad9b25ae6b651196165fc46`
- **Related Modules Audited (READ-ONLY):**
  * [`launcher/store.py`](file:///home/alexey/git/agent-quota-launcher/launcher/store.py) (283 LOC, Store and `launch_lock` lease primitives)
  * [`launcher/task_units.py`](file:///home/alexey/git/agent-quota-launcher/launcher/task_units.py) (629 LOC, systemd transient sibling units)
  * [`launcher/launch.py`](file:///home/alexey/git/agent-quota-launcher/launcher/launch.py) (436 LOC, adapter argv construction)
- **Governing Directives:** Codex Principal Directives C2456, C2458, C2438, C2441; Quota Launcher Head Directives; Operating Model Contract ([`coordination/OPERATING-MODEL.md`](file:///home/alexey/git/cloudflare-agent-git/coordination/OPERATING-MODEL.md)); User Messages 21, 26, 31, 32, 34
- **Auditor / Challenger:** Independent Non-Author Reviewer (`ql-cli-task-units-reviewer`, Subagent under `antigravity-head`)
- **Parent Orchestrator:** `antigravity-head` (`46fdb644-9b58-4e2f-aab3-9be5e1e33337`, Caller ID `245c7bba-9a7b-45c1-87a7-4537f289f9a5`)
- **Audit Timestamp:** `2026-10-05T10:12:00Z` / `2026-10-05T12:12:00+02:00`
- **First-Action Artifact:** [`.local/scratch/review-ql-cli-task-units/first-action.json`](file:///home/alexey/git/cloudflare-agent-git/.local/scratch/review-ql-cli-task-units/first-action.json) (mode `0600`)
- **Scratch Workspace:** `.local/scratch/review-ql-cli-task-units/` (mode `0700`, disk: 20 KB $\le$ 512 MB ceiling, net `/tmp` growth = 0 bytes)
- **Strict Invariants Enforced:**
  * STRICTLY READ-ONLY audit of `/home/alexey/git/agent-quota-launcher` (zero modifications, zero writes to repo)
  * ZERO `cargo` / `rustc` compiler invocations host-wide under human hold
  * Memory $\le$ 1500 MB cooperative pool
  * Zero raw secrets or tokens
- **Verdict:** **FULL ACCEPTANCE**

---

## 1. Executive Summary & Review Verdict

Under Codex Principal Directives C2456 and C2458 and Quota Launcher Head directives, this independent non-author technical audit evaluates the Quota Launcher CLI task units backend integrated into [`launcher/cli.py`](file:///home/alexey/git/agent-quota-launcher/launcher/cli.py) (`run_task_units`) and its canonical test suite [`tests/test_cli_backend.py`](file:///home/alexey/git/agent-quota-launcher/tests/test_cli_backend.py).

The audit verified all four critical concurrency, locking, and lifecycle requirements mandated by Principal Directive C2458:
1. **Atomic Claim Under `launch.lock`:** Transition of task state from `queued` to `starting` is strictly encapsulated within POSIX `fcntl.flock(LOCK_EX)` on `launch.lock` and backed by SQLite `BEGIN EXCLUSIVE` state gating. Path lease and resource reservation are atomized, guaranteeing that exactly one worker acquires execution rights.
2. **Lock Release Before Execution (Anti-Serialization):** In accordance with C2456, `launch.lock` is exited *prior* to invoking `execute_transient_task_unit`. The global launch lock is never held during the long-running model wait, allowing concurrent execution of distinct task units without global head or worker serialization.
3. **Fail-Closed Duplicate Lease Prevention:** Tasks in any state other than `queued` (`starting`, `running`, `completed-awaiting-review`, `failed`, `accepted`, `stalled`, `launch-uncertain`) immediately fail closed with an explicit JSON error record and exit code 1 without spawning any process or unit.
4. **Terminal State Reconciliation Under Lock:** Upon completion of `execute_transient_task_unit` (or upon any unhandled exception), `launch.lock` is re-acquired to reconcile terminal state:
   - On `exit_code == 0`, the task transitions from `starting` to `completed-awaiting-review`, releasing RAM and disk reservations while retaining path evidence leases until explicit review.
   - On `exit_code != 0` or exception, the task transitions to `failed`, immediately releasing active RAM/disk reservations and releasing path leases.

Across verification:
- **Canonical Test Suite:** All 4 of 4 tests in [`tests/test_cli_backend.py`](file:///home/alexey/git/agent-quota-launcher/tests/test_cli_backend.py) passed cleanly in 0.691s.
- **Quota Launcher Full Regression Suite:** All 144 of 144 tests passed in 7.241s with zero regressions.
- **Independent Adversarial Suite:** All 7 of 7 independent concurrency, contention, and state mutation tests in scratch passed cleanly in 1.727s.

**Verdict: FULL ACCEPTANCE.**

---

## 2. Cryptographic Checksums & Code Verification

Both files under audit were cryptographically hashed and inspected:

| File | Size (Bytes) | LOC | SHA256 Checksum |
|---|---|---|---|
| [`launcher/cli.py`](file:///home/alexey/git/agent-quota-launcher/launcher/cli.py) | 16,725 | 437 | `9a99ff570606a465dde2822c711185a4957f4647e7844df4eca77f9c900c1c93` |
| [`tests/test_cli_backend.py`](file:///home/alexey/git/agent-quota-launcher/tests/test_cli_backend.py) | 3,958 | 109 | `4873db480c12744d8813791129fea465d0e1ee66cad9b25ae6b651196165fc46` |

---

## 3. Detailed Technical Audit Findings

### 3.1 CLI Dispatch and Backend Selection

In [`launcher/cli.py`](file:///home/alexey/git/agent-quota-launcher/launcher/cli.py) (lines 81–92, 386–392):

```python
def run(args):
    config_dir = config_dir_for(args)
    backend = getattr(args, "backend", "aplexer")
    if backend == "task-units":
        return run_task_units(args)
    if backend not in ("aplexer", "task-units"):
        print(json.dumps({"error": f"unknown backend {backend}"}))
        return 1
    lock_path = config_dir / 'launch.lock'
    return do_run(str(config_dir / 'state.db'), args.id, args.cwd, args.tmpdir,
                  str(lock_path))
```

And in `main()` argument configuration:
```python
    parser_run.add_argument(
        "--backend",
        default="aplexer",
        choices=["aplexer", "task-units"],
        help="aplexer = nested native start (held); task-units = sibling systemd unit",
    )
```

**Audit Analysis:**
- The CLI exposes `--backend` with strict choices (`choices=["aplexer", "task-units"]`) defaulting safely to `"aplexer"`.
- When `--backend task-units` is passed, control routes directly to `run_task_units(args)`.
- Any unhandled or unsupported backend string immediately emits a structured JSON error and exits with code 1.

---

### 3.2 Pre-Launch Validation and Fail-Closed Guards

In [`launcher/cli.py`](file:///home/alexey/git/agent-quota-launcher/launcher/cli.py) (lines 100–120):

```python
    config_dir = config_dir_for(args)
    store = get_store(args)
    task = store.get_task(args.id)
    if not task:
        print(json.dumps({"error": f"unsubmitted id {args.id}"}))
        return 1
    if task["state"] != "queued":
        print(json.dumps({"error": f"duplicate lease: task {args.id} state is {task['state']}"}))
        return 1
    payload = task["payload"]
    goal = payload.get("goal") or payload.get("prompt") or ""
    if not goal:
        print(json.dumps({"error": "payload.goal required for task-units backend"}))
        return 1
    provider = payload.get("provider") or "grok"
    tmpdir = args.tmpdir
    memory_mb = int(payload.get("memory_mb") or 768)
    timeout_sec = float(payload.get("timeout") or 300)
    lock_path = config_dir / "launch.lock"
    quse = fetch_quse()
    argv = build_adapter_argv(provider, goal)
```

**Audit Analysis:**
- **Unknown Task ID Guard:** If `args.id` does not exist in SQLite, `task` is `None`; the function prints `{"error": "unsubmitted id ..."}` and returns 1 immediately.
- **Strict State Guard:** Only tasks with `state == "queued"` can be launched. If a task is already `starting`, `running`, or in a terminal state, it fails closed with `duplicate lease: task <id> state is <state>` and returns 1.
- **Payload Goal Validation:** Systemd task units require an explicit execution goal or prompt. If neither `goal` nor `prompt` is present, it fails closed and returns 1.
- **Provider & Adapter Argument Sanitization:** Provider defaults to `"grok"`, with memory defaulting to 768 MB (capped at 1500 MB by `task_units.py` admission) and timeout defaulting to 300s. Adapter argv is constructed safely via `build_adapter_argv(provider, goal)` without shell interpolation.

---

### 3.3 Atomic Claim Under `launch.lock`

In [`launcher/cli.py`](file:///home/alexey/git/agent-quota-launcher/launcher/cli.py) (lines 121–124):

```python
    # C2456: hold launch.lock only for Store lease, not the model wait.
    with launch_lock(str(lock_path)):
        store.transition_task(args.id, "starting", ("queued",),
                              reason=f"task-units lease {provider}")
```

**Audit Analysis:**
- **Two-Layer Atomicity:**
  1. `launch_lock` uses POSIX file locking (`fcntl.flock(f, fcntl.LOCK_EX)`), serializing all local processes attempting to transition tasks.
  2. `store.transition_task` executes an SQLite transaction (`BEGIN EXCLUSIVE`) verifying `state IN ('queued')` and updating `state = 'starting'`. If any other worker raced and updated the state first, `cursor.rowcount == 0` causes `StateTransitionError` to be raised.
- **Path Lease Acquisition:** In `Store`, path leases are tracked in `task_paths` and considered active for all states in `LEASED_STATES = ("queued", "starting", "launch-uncertain", "stalled", "running", "completed-awaiting-review")`. Because both `queued` and `starting` are leased states, the atomic transition maintains exclusive path reservations throughout the worker lifecycle.
- **Resource Reservation:** Active resource tracking considers states in `RESOURCE_HOLDING_STATES = ("queued", "starting", "launch-uncertain", "stalled", "running")`. The transition from `queued` to `starting` maintains the RAM/disk reservation for the active unit.

---

### 3.4 Lock Release Before Execution (Directive C2456)

In [`launcher/cli.py`](file:///home/alexey/git/agent-quota-launcher/launcher/cli.py) (lines 124–136):

```python
    with launch_lock(str(lock_path)):
        store.transition_task(args.id, "starting", ("queued",),
                              reason=f"task-units lease {provider}")
    try:
        receipt = execute_transient_task_unit(
            task_id=args.id,
            command_argv=argv,
            memory_mb=memory_mb,
            workspace=args.cwd,
            tmpdir=tmpdir,
            timeout_sec=timeout_sec,
            quse_json=quse,
            provider=provider,
            log_dir=str(config_dir),
        )
```

**Audit Analysis:**
- **Exiting the Context Manager:** Line 124 terminates the `with launch_lock` block. Python's context manager invokes `fcntl.flock(f, fcntl.LOCK_UN)`.
- **Non-Blocking Task Wait:** `execute_transient_task_unit` executes detached transient systemd service units under `app.slice`, polling cgroup dissolution and waiting for completion. During this entire wait (up to `timeout_sec`), `launch.lock` is **NOT** held.
- **Concurrency Verification:** Multiple workers handling distinct tasks can claim their leases and run concurrently without lock starvation or global serialization. This directly addresses the 50-worker capacity requirement without parent-head cgroup PID exhaustion.

---

### 3.5 Terminal State Reconciliation Under Lock

In [`launcher/cli.py`](file:///home/alexey/git/agent-quota-launcher/launcher/cli.py) (lines 137–153):

```python
    except Exception as e:
        with launch_lock(str(lock_path)):
            store.transition_task(args.id, "failed", ("starting",), reason=str(e)[:400])
        print(json.dumps({"error": str(e), "backend": "task-units", "task_id": args.id}))
        return 1
    with launch_lock(str(lock_path)):
        if receipt.get("exit_code") == 0:
            store.transition_task(
                args.id, "completed-awaiting-review", ("starting",),
                reason="task-units sibling unit exit 0",
            )
            print(json.dumps({"backend": "task-units", "task_id": args.id, "receipt": receipt}))
            return 0
        store.transition_task(args.id, "failed", ("starting",),
                              reason=f"task-units exit {receipt.get('exit_code')}")
    print(json.dumps({"backend": "task-units", "task_id": args.id, "receipt": receipt}))
    return 1
```

**Audit Analysis:**
- **Exception Path Reconciliation:**
  * If `execute_transient_task_unit` encounters an error (admission rejection, systemd failure, timeout, or cgroup cleanup failure), the exception is trapped.
  * `launch_lock` is re-acquired.
  * Task is transitioned from `starting` to `failed` with reason truncated to 400 chars.
  * Emits structured JSON error and returns 1.
- **Clean Success Path (`exit_code == 0`):**
  * `launch_lock` is re-acquired.
  * Task is transitioned from `starting` to `completed-awaiting-review`.
  * In `launcher/store.py`, `completed-awaiting-review` is **NOT** in `RESOURCE_HOLDING_STATES`, meaning host RAM and disk reservations are immediately released.
  * However, `completed-awaiting-review` **IS** in `LEASED_STATES`, ensuring that output files and evidence directories remain locked until explicit review and acceptance.
  * Emits receipt JSON and returns 0.
- **Non-Zero Exit Code Path:**
  * `launch_lock` is re-acquired.
  * Task transitions from `starting` to `failed`.
  * State `failed` is excluded from both `RESOURCE_HOLDING_STATES` and `LEASED_STATES`, releasing active RAM/disk reservations and freeing path leases.
  * Emits receipt JSON and returns 1.

---

## 4. Test Suite Execution & Independent Adversarial Stress Testing

### 4.1 Canonical Unit Test Suite

The canonical test suite [`tests/test_cli_backend.py`](file:///home/alexey/git/agent-quota-launcher/tests/test_cli_backend.py) was executed in `/home/alexey/git/agent-quota-launcher`:

```bash
PYTHONPATH=. python3 -m unittest -v tests/test_cli_backend.py
```

**Results:**
- `test_distinct_task_overlap_leases_without_holding_lock_during_wait`: **PASSED** (concurrent overlap verified via `threading.Barrier`)
- `test_duplicate_lease_fails_closed`: **PASSED** (task in `starting` rejected fail-closed)
- `test_missing_goal_fails_closed`: **PASSED** (task missing `goal` and `prompt` rejected fail-closed)
- `test_unsubmitted_id_fails_closed`: **PASSED** (unknown ID rejected fail-closed)

*Total: 4 passed, 0 failed in 0.691s.*

---

### 4.2 Full Quota Launcher Regression Suite

The full test suite of `agent-quota-launcher` was executed across all modules:

```bash
PYTHONPATH=. python3 -m unittest discover -v tests/
```

*Total: 144 passed, 0 failed in 7.241s.* Zero regressions observed.

---

### 4.3 Independent Adversarial Stress Suite

To rigorously stress-test the concurrency, locking, and lease lifecycle guarantees, an independent adversarial test suite was authored in scratch at [`.local/scratch/review-ql-cli-task-units/adversarial_audit_test.py`](file:///home/alexey/git/cloudflare-agent-git/.local/scratch/review-ql-cli-task-units/adversarial_audit_test.py) and executed:

```bash
python3 /home/alexey/git/cloudflare-agent-git/.local/scratch/review-ql-cli-task-units/adversarial_audit_test.py -v
```

**Detailed Test Results:**
1. `test_concurrent_same_id_race_fails_closed`: 5 concurrent worker threads raced to claim the exact same queued task under high contention. Exactly 1 thread successfully acquired the lease and executed; the other 4 threads failed closed. Task transitioned cleanly to `completed-awaiting-review`. **PASSED**.
2. `test_lock_acquirable_by_third_party_during_execution`: Verified that an independent third-party thread can immediately acquire POSIX `flock(LOCK_EX | LOCK_NB)` on `launch.lock` while `execute_transient_task_unit` is actively running, proving `launch.lock` is not held during task execution. **PASSED**.
3. `test_terminal_exit_zero_releases_resources_and_retains_paths`: Verified that upon exit code 0, active memory reservations drop to 0 MB (releasing cooperative host capacity), while path leases remain active in `LEASED_STATES` (subsequent submission with overlapping paths is rejected with `ValueError: Path overlap`). **PASSED**.
4. `test_terminal_exit_nonzero_releases_resources_and_paths`: Verified that on non-zero exit code, task transitions to `failed`, releasing memory reservations and releasing path leases (subsequent submission with overlapping path immediately succeeds). **PASSED**.
5. `test_exception_in_execution_transitions_to_failed_and_releases`: Injected runtime controller error during execution; verified exception handling catches error, re-acquires lock, transitions to `failed`, and returns 1. **PASSED**.
6. `test_duplicate_lease_on_all_non_queued_states`: Tested every non-queued state (`starting`, `running`, `completed-awaiting-review`, `failed`, `accepted`); verified `run_task_units` fails closed for every one without invoking executor. **PASSED**.
7. `test_payload_with_prompt_fallback_succeeds`: Verified payload containing `prompt` instead of `goal` falls back cleanly and invokes adapter with the prompt. **PASSED**.

*Total: 7 passed, 0 failed in 1.727s.*

---

## 5. Security, Invariant, and Publication Compliance

### 5.1 Strict Repository Read-Only Invariant

Per reviewer instructions, `/home/alexey/git/agent-quota-launcher` was audited in strict read-only mode:
- Zero modifications, additions, or deletions made to `/home/alexey/git/agent-quota-launcher`.
- `git status` in `/home/alexey/git/agent-quota-launcher` confirmed untouched state.
- All testing harnesses, intermediate data, and first-action receipts were confined exclusively to `/home/alexey/git/cloudflare-agent-git/.local/scratch/review-ql-cli-task-units/`.

### 5.2 Publication Credential Guard

The deliverable report was evaluated against [`research/antigravity/tooling/publication_guard.py`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/tooling/publication_guard.py):
- Scanned target: `research/antigravity/reviews/REV-QL-CLI-TASK-UNITS-C2458.md`
- Result: **0 violations detected, exit code 0**.
- Zero bearer tokens, zero high-entropy auth headers, zero credential URLs, zero raw secrets.

### 5.3 Resource Budget Compliance

- Host memory: Audit executed well within $\le$ 1500 MB cooperative pool.
- Host disk: Scratch directory consumed 20 KB (well within the $\le$ 512 MB ceiling).
- Zero net `/tmp` growth.
- Zero `cargo` / `rustc` invocations host-wide under human hold.

---

## 6. Formal Acceptance Verdict

The Quota Launcher CLI Task Units backend implementation in [`launcher/cli.py`](file:///home/alexey/git/agent-quota-launcher/launcher/cli.py) satisfies all concurrency, locking, isolation, and fail-closed requirements established by Codex Principal Directives C2456, C2458, C2438, and C2441.

**Verdict: FULL ACCEPTANCE.**
