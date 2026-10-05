# Independent Technical Audit: Canonical Quota-Launcher Shared Admission, Exact Flash Model Binding & Epistemic Boundaries

**Document ID:** `REV-LAUNCHER-CANONICAL-ADMISSION-REPAIR`  
**Directives:** Codex Principal Directives C2261, C2268, C2271, C2277, C2281  
**Reviewer:** `reviewer259` (Independent Model Reviewer, Session `259526a9-5deb-47ce-810c-ca5f2da56b68`)  
**Audited Target Implementation:** `research/antigravity/tooling/self_org/launcher_bus_bridge.py`  
**Target Implementation SHA256:** `ac372b1f16cc9508dd26a8d94e343526775ef7a0c5e7c01a023065e9ce8b2686`  
**Audited Test Suite:** `tests/test_launcher_bus_bridge.py`  
**Test Suite SHA256:** `fb158b9868ed54bfc41faf3efd1b07ac0d1840acfe2351d5911d78299c656e6e`  
**Audit Date:** 2026-10-05T04:35:00+02:00 (Europe/Berlin)  
**Verdict:** **BOUNDED SOURCE ACCEPTANCE ONLY; MODEL RUNTIME EXECUTION REMAINS HELD**

---

## 1. Executive Summary & Verification Scope

Under Codex Principal Directives C2261, C2268, C2271, C2277, and C2281, an exhaustive independent technical audit was conducted on the source repairs in `research/antigravity/tooling/self_org/launcher_bus_bridge.py` and the expanded regression suite in `tests/test_launcher_bus_bridge.py`.

The audit evaluated eight core technical and architectural dimensions:
1. **Strict Canonical Path Defaulting (C2268):** Ensuring `get_canonical_launcher_paths` strictly resolves to `~/.config/agent-quota-launcher/(state.db, launch.lock)` matching `launcher.cli.config_dir_for`, with uncanonical environment overrides (`AGENT_QUOTA_LAUNCHER_CONFIG_DIR`) completely purged.
2. **Exact Store & Lock Verification & Same-Folder Different-Lock Rejection (C2268):** Requiring exact file identity equality for real model routes (`store.db_path.resolve() == canonical_store_path.resolve()` AND `lock_file.resolve() == canonical_lock_path.resolve()`), rejecting disjoint directories, non-canonical fixture stores, and same-folder non-canonical locks (e.g. `other.lock`).
3. **Legitimate Explicit Canonical Construction (C2268):** Supporting explicit instantiation with canonical store and lock paths, correctly recognizing them as legitimate canonical instances (`is_test_fixture=False`).
4. **Rejection of `quse_override` on Real Model Routes (C2277):** Enforcing that simulated quota telemetry is strictly rejected on real model routes (`not is_local_probe and not self.is_test_fixture`), raising `QuotaAdmissionError` before launch.
5. **Split-Filesystem / Multi-Mount Host Admission Gates (C2277):** Extending host disk admission to inspect target mounts backing `cwd` and `tmpdir` in addition to root `/`, failing closed if any volume falls below 50 GiB free space.
6. **Exact Model Binding & Shared Quota Pool Demarcation (C2271 / C2281):** Enforcing strict invariant equality between admitted model and recipe command (`selected_actual_model == recipe_actual_model == reservation_model == quota_tier`), while documenting that Gemini Flash and Pro consume a shared quota pool proportionally.
7. **Exact Flash Model Route & Argv Ordering (C2261):** Enforcing strict argument ordering for `agy` (`-p` immediately followed by prompt; flags preceding `-p`), binding `"antigravity"` to `"agy"` with validated model `gemini-3.7-flash-medium` (and alias `gemini-3.1-pro-high`).
8. **Canonical Store API & Stalled Reservation Accounting (C2261):** Enforcing real state enums (`queued -> starting -> stalled -> failed`) and verifying that `stalled` tasks retain active reservations in Store and resource calculations until explicitly failed.

All 42 unit tests in `tests/test_launcher_bus_bridge.py` passed cleanly (12.548s elapsed). Canonical repositories (`/home/alexey/git/agent-quota-launcher`) remained strictly immutable (`git diff --exit-code` = 0). Compiler hold was strictly maintained (0 `cargo`/`rustc` calls).

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
- **Determination:**
  - `get_canonical_launcher_paths(None)` resolves strictly to `/home/alexey/.config/agent-quota-launcher/state.db` and `/home/alexey/.config/agent-quota-launcher/launch.lock`.
  - The previous uncanonical check for `os.environ.get("AGENT_QUOTA_LAUNCHER_CONFIG_DIR")` has been completely purged. Ambient environment variables cannot divert the runtime's default store or lock.
  - Matches canonical `launcher.cli.config_dir_for(None)` exactly.
  - Verified by Test 34 (`test_34_c2261_default_resolves_to_canonical_launcher_paths`).

### 2.2. Exact Canonical Store & Lock Verification & Lock Timing (Directives C2268 & C2277)

- **Audited Code:**
  - `prepare_and_dispatch_task` (lines 1320–1355)
  - `prepare_and_dispatch_under_launch_lock` (lines 1465–1495)
  - `execute_in_verified_systemd_scope` (lines 1540–1610)
- **Pre-launch Negative Gates:**
  1. **Gate 1 (Disjoint Store/Lock Directory Origin):**
     ```python
     if lock_file.parent.resolve() != Path(self.store.db_path).parent.resolve():
         raise ResourceAdmissionError(
             f"Disjoint store and lock paths: store in {Path(self.store.db_path).parent.resolve()} but lock in {lock_file.parent.resolve()}. "
             "Shared admission requires co-located canonical store and lock."
         )
     ```
  2. **Gate 2 (Exact Canonical File Identity on Real Model Routes):**
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
- **Determination & Timing Clarification:**
  - **Lock Timing Clarification (C2277):** In `execute_in_verified_systemd_scope`, lock verification occurs inside `launch_lock(str(lock_file))` prior to any provider child process spawning.
  - **Same-folder different-lock rejection:** If an adapter references `~/.config/agent-quota-launcher/state.db` but `~/.config/agent-quota-launcher/other.lock`, Gate 1 passes (same folder), but Gate 2 fails closed because `lock_file.resolve() != canonical_lock_path.resolve()`, raising `ResourceAdmissionError` before launch. Verified by Test 39.
  - **Fixture store rejection:** Real model routes (`is_local_probe=False`) dispatched against non-canonical fixture stores trigger Gate 2 and raise `ResourceAdmissionError`. Verified by Test 36.

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
- **Determination:**
  - When explicitly passing `store=Store(canonical_db)` and `lock_path=canonical_lock` (with `is_test_fixture=None`), `is_exact_canonical` evaluates to `True`.
  - `self.is_test_fixture` evaluates to `not True` $\implies$ `False`.
  - The adapter is correctly recognized as a legitimate canonical runtime, allowing explicit parameter passing without false-positive rejections.
  - Verified by Test 39 positive subtest (`t-c2268-canon-ok`).

### 2.4. Rejection of `quse_override` on Real Model Routes (Directive C2277)

- **Audited Code:** Lines 1357–1361, 1496–1501, 1574–1579.
```python
# Pre-launch negative gate: reject quse_override on real model routes (C2277)
if not is_local_probe and not self.is_test_fixture and quse_override is not None:
    raise QuotaAdmissionError(
        "quse_override is strictly forbidden for real model routes; fresh canonical telemetry fetch is required (C2277)"
    )
```
- **Determination:**
  - Prevents caller from injecting mock, synthetic, or bypassed quota telemetry into real model execution.
  - When `is_local_probe=False` and `is_test_fixture=False`, passing `quse_override` immediately raises `QuotaAdmissionError` before launch.
  - Simulated telemetry is strictly restricted to local probes (`is_local_probe=True`) or explicit non-runtime test fixtures (`is_test_fixture=True`).
  - Verified by Test 41 (`test_41_c2277_real_model_route_rejects_quse_override`).

### 2.5. Split-Filesystem / Multi-Mount Host Admission Gates (Directive C2277)

- **Audited Code:** `check_host_admission` lines 1250–1268.
```python
# Multi-Mount / Split-Filesystem Host Admission Gates (C2277)
if paths_to_check:
    for p_raw in paths_to_check:
        p = Path(p_raw).resolve()
        stat_target = p
        while not stat_target.exists() and stat_target.parent != stat_target:
            stat_target = stat_target.parent
        try:
            target_stat = os.statvfs(str(stat_target))
            target_disk_free = target_stat.f_bavail * target_stat.f_frsize
            if target_disk_free < min_disk_floor:
                raise ResourceAdmissionError(
                    f"Filesystem for path '{p}' has {target_disk_free / (1024**3):.2f} GiB free below 50 GiB floor (C2277)"
                )
        except OSError as exc:
            raise ResourceAdmissionError(
                f"Cannot stat filesystem for path '{p}': {exc}"
            ) from exc
```
- **Determination:**
  - In addition to checking root `/` for $\ge$ 50 GiB free space, `check_host_admission(paths_to_check=[cwd_path, tmpdir_path])` inspects the exact filesystem volume backing `cwd` and `tmpdir`.
  - Handles non-existent nested paths by traversing up to existing mount roots.
  - If a split filesystem mount (e.g. separate `/scratch` or `/local`) has $< 50\text{ GiB}$ free space, `ResourceAdmissionError` is raised before launch with zero child process spawning.
  - Verified by Test 42 (`test_42_c2277_split_filesystem_below_disk_floor_fails_closed`).

### 2.6. Exact Model Binding & Shared Quota Pool Demarcation (Directives C2271 & C2281)

- **Audited Code:** `validate_route_to_command` lines 988–997 and 1017–1023.
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
- **Invariant Verification:**
  $$\text{selected\_actual\_model} == \text{recipe\_actual\_model} == \text{reservation\_model} == \text{quota\_tier}$$
  - `selected_actual_model`: Derived from canonical ranking (`chosen.get("model")`).
  - `recipe_actual_model`: `--model <name>` in `command_argv`.
  - `reservation_model`: Stored in Store task payload (`payload["model"]`).
  - `quota_tier`: Window telemetry evaluated in `validate_quse`.
  - Attempting to run `--model gemini-3.1-pro-high` under `gemini-3.7-flash-medium` quota reservation raises `ResourceAdmissionError` before launch (and vice versa).
  - Verified by Test 40 (`test_40_c2271_exact_model_binding_rejects_quota_smuggling`).
- **Epistemic Boundaries & Codex C2281 Insight:**
  - **Shared Quota Group:** Gemini Flash (`gemini-3.7-flash-medium`) and Gemini Pro (`gemini-3.1-pro-high`) draw against the same underlying Google Antigravity account quota pool, which is consumed proportionally (Pro requests consume a greater fraction of the shared limit than Flash requests).
  - **Epistemic Demarcation:** While the code strictly binds the admitted model name to the command argv recipe to prevent internal entitlement drift, this consistency is enforced at the source/adapter layer and bounded by raw provider telemetry granularity. It does not constitute an unmeasured mathematical proof of independent upstream provider quotas. Claims of upstream quota separation are rejected.

### 2.7. Exact Flash Model Route & Argv Ordering (Directive C2261)

- **Audited Code:** `validate_route_to_command` lines 1006–1050.
- **Determination:**
  - Provider `"antigravity"` (and alias `"gemini"`) binds strictly to `"agy"` wrapped by `env -u GEMINI_API_KEY -u GOOGLE_API_KEY`.
  - Authorized models are restricted strictly to `"gemini-3.7-flash-medium"` and `"gemini-3.1-pro-high"`.
  - Argument positioning rules:
    - `-p` must be immediately followed by the prompt string.
    - Flags `--print-timeout 0`, `--output-format text`, `--dangerously-skip-permissions`, `--effort`, and `--model` must precede `-p`.
    - If any option or flag appears after `-p`, `ResourceAdmissionError("Malformed agy argv: -p must be followed by prompt string, not options")` is raised.
    - Trailing argument count: `p_idx == len(command_argv) - 2`.
  - Verified by Test 37 (`test_37_c2261_flash_model_route_validates_model_and_argv_ordering`).

### 2.8. Canonical Store API & Stalled Reservation Accounting (Directive C2261)

- **Audited Code:** `tests/test_launcher_bus_bridge.py` Test 38.
- **Determination:**
  - State transitions strictly follow canonical states: `queued -> starting -> stalled -> failed` (no invented states).
  - `RESOURCE_HOLDING_STATES` confirms `"stalled"` is a resource-holding state.
  - `store.get_active_resources()` confirms that tasks in `"stalled"` state retain memory and disk reservations.
  - `check_resources` accurately integrates active stalled reservations against host `MemAvailable` floor.
  - Transitioning from `"stalled"` to terminal `"failed"` cleanly releases reservations to 0.
  - Verified by Test 38 (`test_38_c2261_shared_resource_accounting_honors_stalled_reservations`).

---

## 3. Test Suite Execution & Output Evidence

The entire test suite was executed in verbose mode with `TMPDIR` redirected to the owned scratch workspace:
```bash
TMPDIR=/home/alexey/git/cloudflare-agent-git/.local/scratch/launcher-bus-integration \
python3 -m unittest -v tests/test_launcher_bus_bridge.py
```

### Execution Log Summary:
- **Total Tests Executed:** 42
- **Failures:** 0
- **Errors:** 0
- **Skipped:** 0
- **Elapsed Duration:** 12.548s
- **Status:** **OK (42/42 PASS)**

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
| **Test 40** | `test_40_c2271_exact_model_binding_rejects_quota_smuggling` | C2271 / C2281 | **PASS** |
| **Test 41** | `test_41_c2277_real_model_route_rejects_quse_override` | C2277 | **PASS** |
| **Test 42** | `test_42_c2277_split_filesystem_below_disk_floor_fails_closed` | C2277 | **PASS** |

---

## 4. Constraint & Invariant Verification

1. **Compiler Invariant Under Human Hold:**
   - Strictly 0 `cargo` and 0 `rustc` compiler invocations across reviewer and audited subprocesses.
2. **Canonical Repository Immutability:**
   - Canonical `/home/alexey/git/agent-quota-launcher` was verified with `git diff --exit-code`: exit code 0, zero modified tracked files, zero staged changes, zero commits.
3. **Physical Scratch Footprint:**
   - Audited scratch directories:
     - `.local/scratch/launcher-bus-integration`: 4.0 KB
     - `.local/scratch/reviewer259-flash-trial-review`: 4.0 KB
   - Both are strictly $\le$ 512 MB physical disk budget.
4. **Filesystem Hygiene:**
   - Net `/tmp` growth = 0. All subprocess artifacts and temporary files were constrained to owned workspace scratch paths.
5. **Subagent Git Commit Boundary:**
   - Strictly 0 git commits or git pushes executed by reviewer subagent.

---

## 5. Audit Conclusion & Formal Verdict

The source repairs in `research/antigravity/tooling/self_org/launcher_bus_bridge.py` and the regression suite in `tests/test_launcher_bus_bridge.py` delivered by Architect 06 under Directives C2261, C2268, C2271, C2277, and C2281 have been audited and verified.

All pre-launch gates, multi-mount disk validations, exact model bindings, and canonical path checks pass without error. However, under Directive C2277 and existing project governance, live runtime execution of external model endpoints remains unapproved.

**Formal Determination:**  
**BOUNDED SOURCE ACCEPTANCE ONLY; MODEL RUNTIME EXECUTION REMAINS HELD**
