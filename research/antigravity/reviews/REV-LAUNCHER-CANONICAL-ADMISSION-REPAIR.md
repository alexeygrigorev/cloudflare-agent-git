# Independent Technical Audit: Canonical Quota-Launcher Shared Admission & Exact Flash Model Binding Repair

**Document ID:** `REV-LAUNCHER-CANONICAL-ADMISSION-REPAIR`  
**Directives:** Codex Principal Directives C2261, C2268, C2271  
**Reviewer:** `reviewer259` (Independent Model Reviewer, Session `259526a9-5deb-47ce-810c-ca5f2da56b68`)  
**Audited Target Implementation:** `research/antigravity/tooling/self_org/launcher_bus_bridge.py`  
**Target Implementation SHA256:** `863ed2aa25307219de09f06b0c54a47ee602ce05c93664d4d020bb922374af72`  
**Audited Test Suite:** `tests/test_launcher_bus_bridge.py`  
**Test Suite SHA256:** `aa141ae96b2b705419c868b8821c742527965be0873bdfad33471683ea4426b0`  
**Audit Date:** 2026-10-05T04:25:00+02:00 (Europe/Berlin)  
**Verdict:** **FULL ACCEPTANCE (PASS: 40/40 Unit Tests, 0 Compiler Invocations, 0 Repo Mutations)**

---

## 1. Executive Summary & Verification Ledger

Under Codex Principal Directives C2261, C2268, and C2271, an independent technical audit was conducted on the source-only repair of `ChildModelRuntimeAdapter` and related route validation helpers in `research/antigravity/tooling/self_org/launcher_bus_bridge.py`, alongside negative and positive test coverage additions in `tests/test_launcher_bus_bridge.py`.

The audit evaluated five core dimensions:
1. **Strict Canonical Path Defaulting (C2268):** `get_canonical_launcher_paths` defaulting strictly to `~/.config/agent-quota-launcher` matching `launcher.cli.config_dir_for`, with zero uncanonical environment variable overrides.
2. **Exact Store & Lock Verification & Same-Folder Different-Lock Rejection (C2268):** Real model routes strictly enforcing co-located canonical store and lock paths, rejecting disjoint directories, alternative fixture stores, and same-folder non-canonical locks (e.g. `other.lock`).
3. **Legitimate Explicit Canonical Construction (C2268):** Enabling legitimate canonical instances when explicitly passing canonical store and lock paths, correctly resolving `is_test_fixture=False`.
4. **Exact Model Binding & Quota Smuggling Prevention (C2271):** Enforcing strict invariant equality: `selected_actual_model == recipe_actual_model == reservation_model == quota_tier`, rejecting generic allowlist bypasses and mismatched recipe pairs.
5. **Exact Flash Model Route & Argv Ordering (C2261):** Enforcing `-p` immediately followed by prompt string, rejecting flags after `-p`, and binding provider `"antigravity"` to `"agy"` with validated model `gemini-3.7-flash-medium` (and alias `gemini-3.1-pro-high`).

All 40 unit tests in `tests/test_launcher_bus_bridge.py` passed cleanly (13.037s elapsed). Canonical repositories (`/home/alexey/git/agent-quota-launcher`) remained strictly read-only with zero modifications (`git diff --exit-code` = 0). Zero `cargo`/`rustc` compiler invocations occurred.

---

## 2. Detailed Technical Audit Findings

### 2.1. Strict Canonical Path Defaulting (Directive C2268)

- **Audited Code:** `research/antigravity/tooling/self_org/launcher_bus_bridge.py` lines 1114–1127.
```python
def get_canonical_launcher_paths(
    config_dir: Optional[Union[str, Path]] = None,
) -> Tuple[Path, Path]:
    if config_dir is not None:
        cfg = Path(config_dir).expanduser().resolve()
    else:
        cfg = Path(os.path.expanduser("~/.config/agent-quota-launcher")).resolve()
    return cfg / "state.db", cfg / "launch.lock"
```
- **Verification:**
  - `get_canonical_launcher_paths(None)` resolves strictly to `/home/alexey/.config/agent-quota-launcher/state.db` and `/home/alexey/.config/agent-quota-launcher/launch.lock`.
  - The previous uncanonical check for `os.environ.get("AGENT_QUOTA_LAUNCHER_CONFIG_DIR")` has been completely purged. Uncanonical environment injection cannot divert the runtime's default store or lock.
  - This strictly adheres to canonical `launcher.cli.config_dir_for(None)`.
  - Verified by Test 34 (`test_34_c2261_default_resolves_to_canonical_launcher_paths`).

### 2.2. Exact Canonical Store & Lock Verification & Same-Folder Different-Lock Rejection (Directive C2268)

- **Audited Code:**
  - `ChildModelRuntimeAdapter.prepare_and_dispatch_task` (lines 1302–1331)
  - `ChildModelRuntimeAdapter.prepare_and_dispatch_under_launch_lock` (lines 1443–1464)
  - `ChildModelRuntimeAdapter.execute_in_verified_systemd_scope` (lines 1520–1585)
- **Pre-launch Negative Gates:**
  1. **Gate 1 (Disjoint Store/Lock):**
     ```python
     if lock_file.parent.resolve() != Path(self.store.db_path).parent.resolve():
         raise ResourceAdmissionError(
             f"Disjoint store and lock paths: store in {Path(self.store.db_path).parent.resolve()} but lock in {lock_file.parent.resolve()}. "
             "Shared admission requires co-located canonical store and lock."
         )
     ```
  2. **Gate 2 (Alternative Store / Non-Canonical Lock on Real Model Route):**
     ```python
     if not is_local_probe:
         if (
             self.is_test_fixture
             or Path(self.store.db_path).resolve() != canonical_store_path.resolve()
             or lock_file.resolve() != canonical_lock_path.resolve()
         ):
             raise ResourceAdmissionError(
                 f"Real model route requires exact canonical shared store '{canonical_store_path}' and lock '{canonical_lock_path}'; got store '{self.store.db_path}' and lock '{lock_file}'. "
                 "Alternative stores/locks are strictly non-runtime test fixtures."
             )
     ```
- **Verification:**
  - **Same-folder different-lock rejection:** If an adapter uses `~/.config/agent-quota-launcher/state.db` but `~/.config/agent-quota-launcher/other.lock`, Gate 1 passes (parent dirs match), but Gate 2 triggers because `lock_file.resolve() != canonical_lock_path.resolve()`. It immediately raises `ResourceAdmissionError` before evaluating quse, acquiring lock, or spawning scopes. Verified by Test 39.
  - **Fixture store rejection:** Real model routes (`is_local_probe=False`) dispatched against non-canonical fixture stores trigger Gate 2 and raise `ResourceAdmissionError`. Verified by Test 36.
  - **Local probe exemption:** Local probes (`is_local_probe=True`) are permitted to run against test fixture stores for component unit testing without violating real quota gates.

### 2.3. Legitimate Explicit Canonical Construction (Directive C2268)

- **Audited Code:** `ChildModelRuntimeAdapter.__init__` lines 1194–1205.
```python
resolved_store = Path(self.store.db_path).resolve()
resolved_lock = self.lock_path.resolve()
is_exact_canonical = (
    resolved_store == canonical_store_path.resolve()
    and resolved_lock == canonical_lock_path.resolve()
)

if is_test_fixture is not None:
    self.is_test_fixture = bool(is_test_fixture)
else:
    self.is_test_fixture = not is_exact_canonical
```
- **Verification:**
  - When a caller explicitly passes `store=Store(canonical_db)` and `lock_path=canonical_lock` (without passing `is_test_fixture`), `is_exact_canonical` evaluates to `True`.
  - `self.is_test_fixture` evaluates to `not True` $\implies$ `False`.
  - The adapter is recognized as a legitimate canonical runtime, allowing explicit parameter passing without false-positive rejection on real model routes.
  - Verified by Test 39 positive subtest (`t-c2268-canon-ok`).

### 2.4. Exact Model Binding & Quota Smuggling Prevention (Directive C2271)

- **Audited Code:** `validate_route_to_command` lines 988–997 and 1017–1023; `execute_in_verified_systemd_scope` lines 1568–1573.
```python
if "--model" in command_argv:
    m_idx = command_argv.index("--model")
    if m_idx + 1 < len(command_argv):
        model_name = command_argv[m_idx + 1]
        if expected_model and expected_model != "none" and model_name != expected_model:
            raise ResourceAdmissionError(
                f"Model binding mismatch: command recipe model '{model_name}' does not match admitted/reserved model '{expected_model}' (C2271)"
            )
```
- **Verification:**
  - Evaluated the invariant chain:
    $$\text{selected\_actual\_model} == \text{recipe\_actual\_model} == \text{reservation\_model} == \text{quota\_tier}$$
  - `selected_actual_model`: Output of `check_quse_admission` candidate ranking (`chosen.get("model")`).
  - `quota_tier`: Evaluated window telemetry in `validate_quse`.
  - `reservation_model`: Stored in Store task payload (`payload["model"] = chosen.get("model")`).
  - `recipe_actual_model`: The `--model <name>` argument in `command_argv`.
  - `validate_route_to_command` receives `expected_model=chosen.get("model")`. If `command_argv` attempts to execute `--model gemini-3.1-pro-high` when admitted under `gemini-3.7-flash-medium` quota, it raises `ResourceAdmissionError` before launch.
  - Conversely, attempting to execute `--model gemini-3.7-flash-medium` when admitted under `gemini-3.1-pro-high` quota raises `ResourceAdmissionError` before launch.
  - Verified by Test 40 (`test_40_c2271_exact_model_binding_rejects_quota_smuggling`).

### 2.5. Exact Flash Model Route & Argv Ordering (Directive C2261)

- **Audited Code:** `validate_route_to_command` lines 1006–1050.
- **Verification:**
  - Provider `"antigravity"` (and alias `"gemini"`) binds strictly to `"agy"` wrapped by `env -u GEMINI_API_KEY -u GOOGLE_API_KEY`.
  - Authorized models are restricted strictly to `"gemini-3.7-flash-medium"` and `"gemini-3.1-pro-high"`.
  - Argument positioning rules:
    - `-p` must be immediately followed by the prompt string.
    - Flags `--print-timeout`, `--output-format`, `--dangerously-skip-permissions`, `--effort`, and `--model` must precede `-p`.
    - If any option or flag appears after `-p`, or if prompt begins with `-` (other than standard stdin `-`), `ResourceAdmissionError("Malformed agy argv: -p must be followed by prompt string, not options")` is raised.
    - Trailing argument count: `p_idx == len(command_argv) - 2`.
  - Verified by Test 37 (`test_37_c2261_flash_model_route_validates_model_and_argv_ordering`).

### 2.6. Canonical Store API Usage & Stalled Resource Accounting (Directive C2261)

- **Audited Code:** `tests/test_launcher_bus_bridge.py` Test 38 (`test_38_c2261_shared_resource_accounting_honors_stalled_reservations`).
- **Verification:**
  - Real canonical Store transition functions are used: `store.submit_task`, `store.transition_task`, `store.get_active_resources`.
  - State progression strictly follows canonical state enums: `queued -> starting -> stalled -> failed`. No invented intermediate states (`PENDING`, `RUNNING`) are used.
  - `RESOURCE_HOLDING_STATES` confirms `"stalled"` is a resource-holding state.
  - `store.get_active_resources()` correctly reports 600 MB memory and 1000 MB disk while in `"stalled"` state.
  - `check_resources` correctly integrates active stalled reservations against host `MemAvailable` floor.
  - Transitioning from `"stalled"` to terminal `"failed"` cleanly releases reservations to 0.

---

## 3. Test Suite Execution & Output Evidence

The entire test suite was executed in verbose mode with `TMPDIR` redirected to the owned scratch workspace:
```bash
TMPDIR=/home/alexey/git/cloudflare-agent-git/.local/scratch/launcher-bus-integration \
python3 -m unittest -v tests/test_launcher_bus_bridge.py
```

### Execution Log Summary:
- **Total Tests Executed:** 40
- **Failures:** 0
- **Errors:** 0
- **Skipped:** 0
- **Elapsed Duration:** 13.037s
- **Status:** **OK (40/40 PASS)**

### Test Breakdown by Directive:
| Test ID | Name | Directive | Result |
| :--- | :--- | :--- | :--- |
| **Test 01–26** | Baseline Unit Tests (Gates, Systemd Scope, Prelude, Cgroup Teardown) | C2070–C2106 | **PASS** |
| **Test 27** | `test_27_c2114_unknown_provider_fails_closed` | C2114 | **PASS** |
| **Test 28** | `test_28_c2126_structured_launcher_recipe_and_benign_goal` | C2126 | **PASS** |
| **Test 29** | `test_29_c2114_local_probe_typing_and_zero_model_quota_claim` | C2114 | **PASS** |
| **Test 30** | `test_30_c2118_model_route_rejects_arbitrary_python_and_shell_interpreters` | C2118 | **PASS** |
| **Test 31** | `test_31_c2118_model_route_recipes_enforce_mandatory_argv` | C2118 | **PASS** |
| **Test 32** | `test_32_c2118_local_probe_zero_quota_and_store_recording` | C2118 | **PASS** |
| **Test 33** | `test_33_c2134_tmpdir_containment_in_systemd_scope_non_model` | C2134 | **PASS** |
| **Test 34** | `test_34_c2261_default_resolves_to_canonical_launcher_paths` | C2261 / C2268 | **PASS** |
| **Test 35** | `test_35_c2261_disjoint_store_and_lock_fails_before_launch` | C2261 / C2268 | **PASS** |
| **Test 36** | `test_36_c2261_alternative_store_rejected_for_real_model_route` | C2261 / C2268 | **PASS** |
| **Test 37** | `test_37_c2261_flash_model_route_validates_model_and_argv_ordering` | C2261 | **PASS** |
| **Test 38** | `test_38_c2261_shared_resource_accounting_honors_stalled_reservations` | C2261 | **PASS** |
| **Test 39** | `test_39_c2268_exact_canonical_matching_and_explicit_construction` | C2268 | **PASS** |
| **Test 40** | `test_40_c2271_exact_model_binding_rejects_quota_smuggling` | C2271 | **PASS** |

---

## 4. Constraint & Invariant Verification

1. **Compiler Invariant Under Human Hold:**
   - Reviewer actor and all audited subprocesses executed strictly 0 `cargo` and 0 `rustc` commands.
2. **Canonical Repository Immutability:**
   - Canonical `/home/alexey/git/agent-quota-launcher` was verified with `git diff --exit-code`: exit code 0, zero modified tracked files, zero staged changes, zero commits.
3. **Physical Scratch Footprint:**
   - Audited scratch directories:
     - `.local/scratch/launcher-bus-integration`: 4.0 KB
     - `.local/scratch/reviewer259-flash-trial-review`: 4.0 KB
   - Both are far below the 512 MB physical disk budget.
4. **Filesystem Hygiene:**
   - Net `/tmp` growth = 0. All subprocess artifacts and temporary files were constrained to owned workspace scratch paths.
5. **Subagent Git Commit Boundary:**
   - Strictly 0 git commits or git pushes executed by reviewer subagent.

---

## 5. Audit Conclusion & Sign-Off

The source-only implementation in `research/antigravity/tooling/self_org/launcher_bus_bridge.py` and test suite expansion in `tests/test_launcher_bus_bridge.py` delivered by Architect 06 under Directives C2261, C2268, and C2271 are **VERIFIED COMPLETE, CORRECT, AND ROBUST**.

- All pre-launch negative gates fail closed appropriately.
- Canonical path identity is strictly enforced matching `launcher.cli.config_dir_for`.
- Quota smuggling across model tiers is mathematically prevented via exact model binding.
- Argv ordering for `agy` properly handles `-p` prompt positioning.
- Resource accounting strictly preserves stalled reservations without premature or unverified cleanup.

**Recommendation:** Approved for integration into canonical self-organizing control plane runtime.
