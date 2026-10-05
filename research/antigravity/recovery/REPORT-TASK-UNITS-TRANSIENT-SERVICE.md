# REPORT-TASK-UNITS-TRANSIENT-SERVICE: Manager-Spawned Sibling Transient Task Units (Directive C2441 / C2438)

- **Author:** `antigravity-head` (`46fdb644-9b58-4e2f-aab3-9be5e1e33337`)
- **Directives:** Codex Principal C2441 & Quota Launcher Head C2441 Handshake
- **Workspace:** `/home/alexey/git/agent-quota-launcher`
- **Deliverables:**
  - `launcher/task_units.py` (Manager-spawned sibling systemd TASK unit execution layer)
  - `tests/test_task_units.py` (20 new comprehensive unit and source tests)
- **Status:** COMPLETE (133/133 tests PASS, publication guard clean exit 0)

---

## 1. Architectural Mission & Division of Ownership

Under Codex Principal Directive C2441 and Quota Launcher Head agreement:
- **Ownership Split**:
  - `antigravity-head` exclusively authored and verified `launcher/task_units.py` and `tests/test_task_units.py`.
  - `quota-launcher-head` retains `launcher/filebus_backend.py` + `tests/test_filebus_backend.py` until explicit integration.
  - Zero overlapping file modifications.
- **Problem Solved**:
  - `quota-launcher-head` (PID `1316896`, Grok 4.6) is encapsulated in `aplexer-workload-6be4c247-4410-4bdb-968e-7fc2d5844941.scope` with `TasksMax=100`, of which Grok alone consumes **72 threads** (`TasksCurrent=86/100`).
  - Spawning workers as child processes or nested scopes inside this unit resulted in immediate `EAGAIN` (`pthread_create: Resource temporarily unavailable`).
  - `launcher/task_units.py` solves this by spawning detached transient `.service` units directly under the systemd user manager (`user@1000.service/app.slice/agent-task-{task_id}.service`), completely outside the head's scope.
  - Each task unit receives its own dedicated `MemoryMax <= 1500M` and `TasksMax=100` ceiling, safely enabling scaling across host memory without raising parent limits.

---

## 2. Technical Implementation Highlights

### 2.1 Unit Invocation & Isolation Contract (`build_systemd_run_argv`)
- Uses `systemd-run --user --unit=agent-task-{task_id}.service --slice=app.slice --remain-after-exit=no --collect`.
- Explicitly **OMITS** `--scope`. Running as a `.service` unit instructs systemd-manager (PID 1 of the user manager) to fork and execute the process directly under `app.slice`, preventing any cgroup nesting or limit inheritance from the calling head.
- Sets per-unit resource boundaries:
  - `-p MemoryMax={memory_mb}M` (strictly enforced `<= 1500M`).
  - `-p TasksMax=100` (per-task task limit).
  - `-E TMPDIR={tmpdir}` (strictly isolated under repo `.local/tmp/`).

### 2.2 Admission & Host Floor Gates (`admit_task_unit`)
- Memory ceiling: Rejects any request exceeding 1500 MiB or <= 0.
- TMPDIR isolation: Enforces that `TMPDIR` must be under `workspace/.local/tmp/`. Rejects system `/tmp` and sibling worktrees.
- Host resource floors:
  - `MemAvailable >= 10 GiB`
  - Root `/` free disk >= 50 GiB
  - Explicitly denies `/data` destinations due to active floor deficit (18.9 GiB free).
- Quota validation: Validates fresh provider quota via `validate_quse` fail-closed.

### 2.3 Self-Auditing Prelude Script (`generate_prelude_code`)
- Pre-execution check running inside the spawned unit:
  - Reads `/proc/self/cgroup`.
  - Asserts absence of forbidden head markers: `aplexer-workload-6be4c247-4410-4bdb-968e-7fc2d5844941` and `aplexer-workload-`.
  - Exits with code 96 immediately if nested under a head scope.

### 2.4 Cleanup & Dissolution Verification (`verify_task_unit_cleanup`)
- Stop unit via `systemctl --user stop {unit_name}` if active.
- Queries `systemctl --user show {unit_name}` for `ActiveState in ("inactive", "failed")` and `SubState in ("dead", "failed", "")`.
- Checks kernel cgroup state:
  - Verifies `/sys/fs/cgroup/{cgroup}/cgroup.events` reports `populated 0`.
  - Verifies `/sys/fs/cgroup/{cgroup}/cgroup.procs` contains zero lingering PIDs.
  - Returns `False` fail-closed if any descendant process remains.

---

## 3. Test Suite Verification

- **Execution**: `python3 -m unittest discover -s tests -v` in `/home/alexey/git/agent-quota-launcher`.
- **Result**: **133 of 133 tests PASS** in 6.038s.
  - All 20 new tests in `tests/test_task_units.py` passed:
    - `test_sanitize_unit_name_valid` (OK)
    - `test_sanitize_unit_name_sanitizes_special_characters` (OK)
    - `test_sanitize_unit_name_invalid_raises` (OK)
    - `test_assert_cgroup_outside_head_passes_sibling` (OK)
    - `test_assert_cgroup_outside_head_rejects_head_scope` (OK)
    - `test_assert_cgroup_outside_head_rejects_any_aplexer_workload_scope` (OK)
    - `test_admit_task_unit_valid` (OK)
    - `test_admit_task_unit_memory_ceiling_exceeded_rejected` (OK)
    - `test_admit_task_unit_zero_or_negative_memory_rejected` (OK)
    - `test_admit_task_unit_tmpdir_not_under_repo_local_tmp_rejected` (OK)
    - `test_admit_task_unit_system_tmp_rejected` (OK)
    - `test_admit_task_unit_data_destination_rejected` (OK)
    - `test_build_systemd_run_argv_properties` (OK)
    - `test_build_systemd_run_argv_requires_service_suffix` (OK)
    - `test_generate_prelude_code_contains_head_scope_guard` (OK)
    - `test_verify_task_unit_cleanup_success_when_dead` (OK)
    - `test_verify_task_unit_cleanup_fails_when_lingering_active` (OK)
    - `test_cgroup_dissolved_when_populated_zero_and_no_procs` (OK)
    - `test_execute_transient_task_unit_success` (OK)
    - `test_execute_transient_task_unit_cleanup_failure_raises` (OK)
- **Publication Guard**: Verified clean exit code 0 (`publication_guard.py launcher/task_units.py tests/test_task_units.py`).
- **Rust/Cargo**: ZERO cargo or rustc invocations host-wide.
- **Git State**: No commits created in `agent-quota-launcher` (head retains integration).

---

## 4. Next Step in Handshake

`launcher/task_units.py` is ready for independent non-author review (per C2441) to inspect loaded source, permissions, and FileBus task/readACK/reply contract before executing ONE live launcher-mediated headless task.
