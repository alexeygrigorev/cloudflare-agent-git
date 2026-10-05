# Independent Peer Review: Agent Quota Launcher Commit a91aaea (20GiB Disk Floor, Narrowed Dead Status, and Per-Task Dependency Refill)

**Date & Time**: 2026-10-05T21:12:00Z (23:12:00 Berlin)  
**Auditor / Reviewer**: `antigravity` (Gemini subagent `22e44b40-2d32-4e91-8498-749759fde9ad`)  
**Parent Caller**: `ea14b401-20e9-4e48-ab08-d15be08da30d`  
**Target Repository**: `/home/alexey/git/agent-quota-launcher`  
**Audited Commit**: `a91aaea6a736629d7e277aedc43b783bfcbbfc99`  
**Commit Message**: `fix(launcher): lower disk floor to 20GiB, narrow dead status, and support per-task review dependencies`  
**Verdict**: **ACCEPTED**

---

## 1. Executive Summary & Audit Matrix

This independent review inspects commit `a91aaea6a736629d7e277aedc43b783bfcbbfc99` in `/home/alexey/git/agent-quota-launcher`. The commit resolves three critical bottlenecks in launcher execution and review coordination:

1. **Host Disk Floor Recalibration**: Lowered `MIN_DISK_FREE_BYTES` from 50 GiB to 20 GiB hard floor (`20 * 1024 * 1024 * 1024`), added `WARN_DISK_FREE_BYTES = 30 * 1024 * 1024 * 1024` (30 GiB cleanup warning), and updated the admission error message to assert `free < 20GiB floor`.
2. **Narrowed Native Process Death Classification**: Modified `launcher/launch.py:native_status()` so that non-zero returncodes from `aplexer status` are only classified as `"dead"` if stdout/stderr explicitly confirms `"no session tagged"` or `"has ever existed"`; transient or unknown failures safely return `"unknown"`.
3. **Per-Task Review Dependency Refill**: Refactored `launcher/watch.py:_next_dispatchable()` to default to `wait_for_review='dependencies'`. In dependency mode, tasks only wait for explicit predecessor tasks designated via `depends_on` or `dependencies`. Queued independent tasks dispatch immediately even if another unrelated task is in `completed-awaiting-review`. Path lease exclusion across active tasks is strictly maintained.
4. **CLI Review-Gated Refill Parameterization**: Updated `launcher/cli.py:accept()` to explicitly supply `wait_for_review="dependencies"` to `watch_loop()`.
5. **Comprehensive Verification**: Executed the full test suite via `pytest -v` across all unit, admission, resource, capacity, telemetry, and watch modules; all 197/197 tests passed cleanly (100% pass rate).

| # | Audit Item | Required Specification | Measured Implementation & Evidence | Result |
|---|---|---|---|:---:|
| **1** | Disk floor constants & error message | `MIN_DISK_FREE_BYTES == 20 GiB`, `WARN_DISK_FREE_BYTES == 30 GiB`, error asserts `free < 20GiB floor` | `launcher/resources.py` lines 9-10 & 47, 50; verified in `tests/test_resources.py` | **PASS** |
| **2** | Narrowed native status death | Only non-zero rc with `"no session tagged"` or `"has ever existed"` yields `"dead"`; other errors yield `"unknown"` | `launcher/launch.py` lines 213–217; verified logic branches and error handling | **PASS** |
| **3** | Dependency-based queue refill | `_next_dispatchable` defaults to `wait_for_review='dependencies'`, checks `depends_on`/`dependencies` states, dispatches independent tasks, enforces path leases | `launcher/watch.py` lines 64–140; verified with unit tests in `tests/test_watch.py` | **PASS** |
| **4** | CLI accept refill argument | `accept()` passes `wait_for_review='dependencies'` | `launcher/cli.py` line 399; verified in `test_accept_triggers_refill_dispatch` | **PASS** |
| **5** | Full regression test suite | Full test suite passes 197/197 tests via `pytest -v` | `pytest -v`: **197 passed in 15.12s** | **PASS** |

---

## 2. Detailed Technical Verification

### 2.1 Disk Floor Calibration (`launcher/resources.py`)
In `launcher/resources.py`:
- `MIN_DISK_FREE_BYTES = 20 * 1024 * 1024 * 1024` (21,474,836,480 bytes, 20 GiB).
- `WARN_DISK_FREE_BYTES = 30 * 1024 * 1024 * 1024` (32,212,254,720 bytes, 30 GiB).
- In `check_resources()`:
  ```python
  task_disk = min(int(requested_disk_mb or 0) * 1024 * 1024, MAX_DISK_SPIKE_BYTES)
  required_free = MIN_DISK_FREE_BYTES + (active_disk_mb * 1024 * 1024) + task_disk

  if cwd_stat.free < required_free:
      raise ValueError(f"cwd filesystem free < 20GiB floor + required disk ({required_free} B)")

  if tmp_stat.free < required_free:
      raise ValueError(f"tmpdir filesystem free < 20GiB floor + required disk ({required_free} B)")
  ```
- **Live Empirical Context**: Measured root filesystem `/` has 49.30 GiB available (52,931,309,568 bytes). Under the earlier 50 GiB floor, the launcher was completely deadlocked despite ~50 GiB of available storage. Under the 20 GiB hard floor + 30 GiB cleanup warning, the host has +29.30 GiB headroom above the hard floor, allowing normal operational launches without compromising system stability.
- **Unit Test Update**: `tests/test_resources.py:test_disk_floor` updated mock disk usage from 51 GiB to 21 GiB and verifies matching regex `free < 20GiB`.

### 2.2 Narrowed Native Status Death Classification (`launcher/launch.py`)
In `launcher/launch.py:native_status(tag, timeout=15)`:
- Previously, any non-zero exit code from `aplexer status` was classified as `"dead"`. This was dangerous because transient CLI failures, lock contention, or subprocess errors could falsely trigger process death handling while the process was still executing or unknown.
- Modified implementation (lines 213–217):
  ```python
  if res.returncode != 0:
      err = (res.stderr or res.stdout or "").strip()
      if "no session tagged" in err or "has ever existed" in err:
          return "dead", f"aplexer status rc={res.returncode}: {err[:200]}"
      return "unknown", f"aplexer status error rc={res.returncode}: {err[:200]}"
  ```
- Any error output that does not explicitly confirm that no session tagged with that run tag exists now safely returns `("unknown", ...)`. In `complete()` and `fail()`, an unknown status correctly rejects transitions requiring positive proof of death.

### 2.3 Dependency-Aware Queue Refill & Path Leases (`launcher/watch.py`)
In `launcher/watch.py`:
- Function signature:
  `def _next_dispatchable(store, wait_for_review="dependencies"):`
- **Global Mode Preserved**: If `wait_for_review == "global"`, any task in `completed-awaiting-review` blocks the queue refill, preserving backwards compatibility.
- **Per-Task Dependency Mode**: `check_dependencies = wait_for_review in (True, "dependencies", "per-task")`.
  - For each candidate task in `queued`, parses its payload:
    `raw_deps = payload.get("depends_on") or payload.get("dependencies") or []`
  - Supports string, list, tuple, or set of predecessor IDs.
  - Queries `store.get_task(dep_id_str)`: if not found or if `dep_task.get("state") != "accepted"`, marks the task as blocked:
    `blocked = f"dependency {dep_id_str} not accepted (state: {dep_state})"`
  - If a task is blocked on an unaccepted predecessor, it logs/records reason and evaluates the next queued task.
- **Independent Task Dispatch**: If a queued task has no unaccepted dependencies, it proceeds immediately to path lease validation.
- **Path Lease Overlap**:
  - Validates requested paths against all active leases via `store.get_active_paths(conn, exclude_task_id=task_id)`.
  - Rejects overlapping paths bidirectionally (`req_p.is_relative_to(act_p) or act_p.is_relative_to(req_p)`).
- **Watcher Loop**: In `watch_loop()`, defaults to:
  `wait_for_review = getattr(args, 'wait_for_review', "dependencies")`.

### 2.4 CLI Integration (`launcher/cli.py`)
In `launcher/cli.py:accept(args)`:
- After transitioning a completed task to `accepted`:
  ```python
  if getattr(args, "refill", True):
      from types import SimpleNamespace
      from launcher.watch import watch_loop
      config_dir = config_dir_for(args)
      refill_args = SimpleNamespace(
          config_dir=config_dir,
          backend=getattr(args, "backend", "task-units"),
          once=True,
          wait_for_review="dependencies",
      )
      print(f"triggering automated review-gated refill after acceptance of {args.id}")
      try:
          watch_loop(refill_args, max_passes=1)
      except Exception as e:
          print(f"refill dispatch error: {e}")
  ```
- Passes `wait_for_review="dependencies"`, ensuring that upon acceptance of a predecessor task, any waiting dependent tasks (or independent backlog items) are dispatched without an arbitrary global queue stall.

---

## 3. Test Suite & Verification Results

Full test suite execution in `/home/alexey/git/agent-quota-launcher`:
```bash
pytest -v
```

Execution Summary:
- Total tests collected: 197
- Passed: 197
- Failed: 0
- Skipped: 0
- Execution time: 15.12s
- Pass Rate: **100% (197/197)**

Key Regression Tests Verified:
1. `tests/test_resources.py::TestResources::test_disk_floor`: PASSED
2. `tests/test_resources.py::TestResources::test_active_reservations_counted`: PASSED
3. `tests/test_watch.py::WatchRefillTests::test_independent_tasks_dispatch_when_another_awaiting_review`: PASSED
4. `tests/test_watch.py::WatchRefillTests::test_accept_triggers_refill_dispatch`: PASSED
5. `tests/test_watch.py::WatchRefillTests::test_derive_task_tmpdir_contained`: PASSED
6. `tests/test_watch.py::WatchRefillTests::test_run_task_units_does_not_trigger_refill_on_exit_zero`: PASSED
7. `tests/test_watch.py::WatchRefillTests::test_watch_loop_dispatches_with_task_local_tmpdir_not_args_tmpdir`: PASSED
8. `tests/test_watch.py::WatchRefillTests::test_watch_loop_waits_for_unreviewed_tasks`: PASSED

---

## 4. Final Verdict

**VERDICT: ACCEPTED**

Commit `a91aaea6a736629d7e277aedc43b783bfcbbfc99` adheres strictly to all stated architectural, safety, and operational constraints. Disk admission correctly reflects the 20 GiB hard floor / 30 GiB cleanup warning; native process status avoids false-positive death classifications; queue refill unblocks independent tasks while strictly enforcing per-task dependency acceptance and path leases; and all 197 tests pass without regression.
