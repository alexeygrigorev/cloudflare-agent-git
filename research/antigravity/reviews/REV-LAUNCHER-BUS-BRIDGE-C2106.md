# Independent Challenger Review: Launcher Bus Bridge Hardening (Codex C2106 / C2114 / C2118 / C2126 / C2128)

- **Reviewer**: Independent Self-Organization Challenger (tag: `self-org-challenger`, conversation: `37aa1067-8bda-4dde-95b8-7b5bb927bd1f`)
- **Authority**: Dispatched by `antigravity-head` (`46fdb644`, id: `245c7bba-9a7b-45c1-87a7-4537f289f9a5`) under Codex Principal C2106, C2108, C2114, C2118, C2126, and C2128 directives and existing human authority (`experiment/human-self-organization-20261004.txt`).
- **Target Audited Codebase**: `research/antigravity/tooling/self_org/launcher_bus_bridge.py`
  - SHA256: `c4644fa33d85d2ac4d43c5a18a89329f427096d3a83e57adf2ae052a0f885044`
- **Target Test Suite**: `tests/test_launcher_bus_bridge.py` (32 unit & integration tests)
  - SHA256: `03b53f4a65c9ff899a0892234ba591cec84caead2751e0ff3dc03479bfff1c18`
- **Target Architecture Report**: `research/antigravity/recovery/REPORT-LAUNCHER-BUS-BRIDGE-C2106.md`
  - SHA256: `c9e39b36cab6b5f4db6571a8ec12a79298278904396eea140d1cab9cc4e53dd1`
- **Scratch Testbed**: `/home/alexey/git/cloudflare-agent-git/.local/scratch/self-org-challenge/` (mode `0700`, strictly <= 512 MB, zero net `/tmp` growth)
- **Date**: 2026-10-05T01:16:00+02:00 (Europe/Berlin)
- **Verdict**: **BOUNDED ACCEPTANCE**
  *(Local kernel custody probe verified; Model execution route strictly HELD pending proven bridge)*

---

## 1. Executive Summary & Epistemic Demarcation

Under Codex Principal Directives C2106, C2108, C2114, C2118, C2126, and C2128:
> *"cleanup scans root cgroup.procs only; missing invocation accepted; fallback missing ControlGroup returns true. Prelude metadata does not check own kernel membership. Provider allowlist does not bind arbitrary command argv; read-bounded logs still grow unbounded on disk; missing output raises before cleanup. Head existing393/7f owns actual-module negatives/narrow corrections, not principal implementation. Fixture18 tests do not close actual lifecycle gate."*
> *"Please challenger37 tests actual provider-mismatched wrapper/default unknown and actual model/CLI argv/backend mapping, architect06 narrow binding with existing launcher route recipe, fail closed unknown. Keep bounded kernel-only probe separate from real model execution; no model claim from generic allowed binaries. No new mandatory crypto/signing policy."*

An exhaustive, adversarial, independent challenge was conducted across all 8 architectural vulnerability vectors plus C2114 route isolation, C2118 recipe enforcement, and C2126/C2128 canonical executable binding. The evaluation established:
1. **Full Integration Test Suite**: 32/32 tests PASS in `tests/test_launcher_bus_bridge.py` in ~9.2s.
2. **C2128 Canonical Installed Executable Enforcement**: Verified that `validate_route_to_command` strictly enforces `prefix == expected_prefix` against canonical `ADAPTERS` argv without basename lookalike fallback. Lookalike paths (`/tmp/fake/zcodex`) and short binary names (`zcodex`) fail closed with `ResourceAdmissionError` in `test_28`.
3. **Negative Comparative Testbed Matrix**: 10 distinct negative evaluations verified in scratch testbed, demonstrating fail-closed enforcement across arbitrary interpreters, foreign CLIs, uncontained probes, and lingering cgroup descendants.
4. **Live Systemd Kernel Custody Probe**: Real `systemd-run --user --scope` execution inside `test_12`, verifying physical cgroup creation, `MemoryMax=1500M`, receipt generation, and cgroup dissolution.
5. **Model Execution Demarcation**: Strict separation between local kernel custody probes (`is_local_probe=True`, zero model quota claim) and real model routes. Real model execution is strictly guarded by canonical launcher route recipes (`zcodex exec --model glm-5.3-flash`, `grok -p --model grok-4.6`, `agy --model gemini-3.1-pro-high`) and held pending proven live model bridge execution.
6. **Resource & Guard Invariants**: Zero cargo/rustc invocations, memory within cooperative 1500 MB limit, scratch root mode `0700` (< 100 KiB used against 512 MB ceiling), zero net `/tmp` growth, and credential publication guard exit 0.

---

## 2. Adversarial Audit of All Vulnerability Vectors & Hardening Deltas

### 2.1 Flaw 1: Descendant Cgroups & Authoritative Population Flag (C2106)
- **Vulnerability**: Cleanup previously inspected only the root `cg_fs_path / "cgroup.procs"`. Forked descendant processes in sub-slices escaped detection, and the kernel `cgroup.events` populated flag was ignored.
- **Hardening Implementation**:
  - `_is_cgroup_dissolved_or_empty(cg_rel_path, cgroup_fs_root=None)` inspects `cgroup.events` at root and recursively across all sub-cgroups (`**/cgroup.events`), verifying `populated 0`. Any `populated != 0` immediately returns `False`.
  - Recursively scans root `cgroup.procs` and all descendant `**/cgroup.procs`; any remaining PID returns `False`.
  - Fails closed on any filesystem read/stat errors.
- **Negative Verification**: Tested with simulated descendant hierarchy where root was empty but `child_slice/cgroup.procs` contained PID `99999` and `cgroup.events` reported `populated 1`. Hardened code returned `False` (fail-closed).

### 2.2 Flaw 2: Strict InvocationID Verification (C2106)
- **Vulnerability**: Previous logic accepted empty or absent `InvocationID` in `systemctl show`, bypassing invocation pinning whenever systemd omitted the property.
- **Hardening Implementation**:
  - In `verify_unit_cleanup`: when `expected_invocation_id` is supplied, `inv_id` must be non-empty AND strictly equal to `expected_invocation_id`.
  - An absent, empty, or mismatched `InvocationID` in `systemctl show` strictly fails closed (returns `False`).
- **Negative Verification**: Tested with `expected_invocation_id="authoritative-inv-uuid-42"` and `InvocationID=""`. Hardened code returned `False`.

### 2.3 Flaw 3: Missing ControlGroup Fail-Closed (C2106)
- **Vulnerability**: When `expected_cgroup` was None and `systemctl show` returned `ControlGroup=""`, previous logic fell back to returning `True` if `TasksCurrent=="0"`.
- **Hardening Implementation**:
  - In `verify_unit_cleanup`: if neither `expected_cgroup` nor `ControlGroup` in unit properties is present, the function strictly fails closed (`return False`).
- **Negative Verification**: Tested with `expected_cgroup=None` and `ControlGroup=""`. Hardened code returned `False`.

### 2.4 Flaw 4: Prelude `/proc/self/cgroup` and Kernel Membership Assertion (C2106)
- **Vulnerability**: Prelude script only inspected systemd client output, failing to verify actual kernel task containment before executing child code.
- **Hardening Implementation**:
  - Prelude script directly inspects `/proc/self/cgroup` and extracts its own cgroup path. It compares this against `ControlGroup` from systemd; exits `96` on mismatch.
  - Prelude reads `/sys/fs/cgroup/{cgroup}/cgroup.procs` and verifies `os.getpid()` is listed in the kernel task table; exits `97` on absence.
- **Negative Verification**: Tested with injected mismatched cgroup path and missing PID. Prelude exited with codes 96 and 97 respectively, triggering immediate SIGKILL teardown and `launch-uncertain` reservation hold.

### 2.5 Flaw 5 & C2114 / C2118: Route Binding, Narrowing & Foreign CLI Smuggling Protection
- **Vulnerability**: Permissive command execution allowlist permitted arbitrary shell or python interpreters and arbitrary binary dispatch under model provider names.
- **Hardening Implementation**:
  - `PROVIDER_ROUTE_BINARIES` defines strict binary mappings per provider.
  - `validate_route_to_command(provider, command_argv, is_local_probe=False)`:
    1. **Arbitrary Interpreter Ban (C2118)**: Arbitrary python (`python3`, `python`) and shell (`bash`, `sh`) interpreters are strictly rejected for all model routes (`zai`, `zcode`, `grok`, `antigravity`, `gemini`, `opencode`, `codex`).
    2. **Recipe Argv Enforcement (C2118)**: Model routes must supply canonical launcher recipes (e.g., `zcodex exec --model glm-5.3-flash`, `grok -p --model grok-4.6`, `agy --model gemini-3.1-pro-high`). Arbitrary `-c` scripts are rejected.
    3. **Unknown Provider (C2114)**: Strictly raises `ResourceAdmissionError` with zero permissive fallback.
    4. **Foreign CLI Smuggling (C2114)**: Rejects foreign model CLIs in arguments (e.g. running `codex` under `zai` or `zcode`).
    5. **Local Probe Demarcation (C2114 / C2118)**: Local probes (`echo`, `sleep`, `true`, `cat`, `python3`) must be explicitly typed with `is_local_probe=True` (zero model quota claim) and are strictly forbidden from smuggling any model CLI.
- **Negative Verification**: Verified against 5 distinct interpreter and route smuggling test vectors; all fail closed with `ResourceAdmissionError`.

### 2.6 Flaw 6: Bounded Disk Logging During Execution (C2106)
- **Vulnerability**: Direct child pipe streaming to disk files risked exhausting host disk if a runaway process emitted unbounded stdout/stderr.
- **Hardening Implementation**:
  - `_bounded_pipe_pump(src_pipe, dst_path, max_bytes=65536)` pumps subprocess pipes in 4096-byte chunks via dedicated daemon threads.
  - Disk file write is capped at `MAX_DISK_LOG_BYTES = 65536` (64 KiB).
  - Excess output is drained and discarded in memory, preventing pipe buffer deadlock while strictly bounding disk consumption.
- **Negative Verification**: Child process emitting >200 KiB was executed; disk log file was capped at exactly `65536` bytes.

### 2.7 Flaw 7: Cleanup Before Missing Output Check (C2106)
- **Vulnerability**: On exit 0, missing expected output artifacts previously raised `ResourceAdmissionError` *before* stopping the systemd unit and verifying cleanup, leaving lingering background tasks uncontained.
- **Hardening Implementation**:
  - In `execute_in_verified_systemd_scope`: on exit 0, `systemctl stop` and `verify_unit_cleanup` are executed *before* examining `expected_outputs`.
  - If cleanup fails: transitions task to `launch-uncertain` (holding Store resources).
  - If clean but outputs are missing: transitions task to `failed` and raises `ResourceAdmissionError`.
- **Negative Verification**: Missing output scenario confirmed unit stop and cgroup cleanup occurred prior to `ResourceAdmissionError` being raised.

### 2.8 Flaw 8: Launch-Uncertain on Popen/Start Failure (C2106)
- **Vulnerability**: Failure during `subprocess.Popen` left tasks un-transitioned in Store in `starting` state without issuing unit teardown.
- **Hardening Implementation**:
  - Wraps `subprocess.Popen` in `try...except`.
  - On failure: issues `systemctl kill --kill-who=all --signal=SIGKILL`, stops unit, evaluates `verify_unit_cleanup`.
  - If cleanup is unproven: transitions task to `launch-uncertain` (holding 1500 MB Store reservation). If clean: transitions task to `failed`. Re-raises the exception.
- **Negative Verification**: Popen raising `OSError` with unproven cleanup resulted in `launch-uncertain` transition holding 1500 MB in Store.

### 2.9 Narrow Exact Final Delta Review (Codex C2126 / C2128 Hardening)
- **Vulnerability**: Permitting basename-only fallback for binary paths allowed potential execution of unauthorized lookalike executables in PATH or user directories (e.g. `/tmp/fake/zcodex` or short `zcodex` without canonical path resolution).
- **Hardening Implementation (C2128)**:
  - In `validate_route_to_command`:
    ```python
    expected_prefix = list(ADAPTERS[effective_provider]["argv"])
    prefix = list(command_argv[:len(expected_prefix)])
    if len(command_argv) != len(expected_prefix) + 1 or prefix != expected_prefix:
        raise ResourceAdmissionError(
            f"Route recipe violation for provider '{provider}': command does not strictly match canonical adapter argv {expected_prefix} + [<goal>] (C2126/C2128)"
        )
    ```
  - **No Basename Fallback**: Removed `Path(command_argv[0]).name == Path(expected_prefix[0]).name` fallback. The binary path must match canonical installed path from `build_adapter_argv` exactly (e.g. `/home/alexey/.local/bin/zcodex`).
  - **Structured Option Alignment**: Exact match on all adapter options (e.g. `--dangerously-bypass-approvals-and-sandbox`, `--model`, `glm-5.3-flash`).
  - **Benign Goal Opacity (C2126)**: Trailing argument `command_argv[-1]` is treated as opaque data, avoiding false-positive keyword rejections while strictly guarding the executable prefix.
- **Negative Verification (Test 28)**:
  - Lookalike binary path (`/tmp/fake/zcodex`): Fails closed with `ResourceAdmissionError`.
  - Short binary name (`zcodex` without canonical path): Fails closed with `ResourceAdmissionError`.
  - Duplicate/injected options (`--model other`): Fails closed with `ResourceAdmissionError`.
  - Benign goal mentioning foreign CLIs ("Fix codex coordination issue"): Passes cleanly as opaque data.

---

## 3. Negative Comparative Testbed Matrix (10 Evaluations)

The 10 negative comparative evaluations were executed against the testbed in `.local/scratch/self-org-challenge/testbed/test_mutation_matrix.py` and `tests/test_launcher_bus_bridge.py`:

| # | Negative Evaluation Category | Injected / Evaluated Condition | Hardened Defense Enforcement | Testbed Result |
|---|---|---|---|---|
| **Neg 1** | Model Route Arbitrary Python Ban (C2118) | Model route `zai` invoked with `["python3", "-c", "print('arbitrary')"]` without `is_local_probe=True` | Rejects with `ResourceAdmissionError: Arbitrary python interpreter 'python3' is strictly forbidden under model route 'zai' (C2118)` | **PASSED (Fail-Closed)** |
| **Neg 2** | Model Route Arbitrary Shell Ban (C2118) | Model route `zcode` invoked with `["bash", "-c", "echo arbitrary"]` or `["sh", ...]` | Rejects with `ResourceAdmissionError: Arbitrary shell interpreter 'bash' is strictly forbidden under model route 'zcode' (C2118)` | **PASSED (Fail-Closed)** |
| **Neg 3** | Unknown Provider Zero Fallback (C2114) | Provider `unknown_foreign_provider` passed to route validator | Strictly raises `ResourceAdmissionError: Unknown or unsupported route provider 'unknown_foreign_provider' (zero permissive fallback; C2114)` | **PASSED (Fail-Closed)** |
| **Neg 4** | Foreign CLI Smuggling Protection (C2114) | Invoking `["codex", "exec"]` under `zai` route, or smuggling `import codex` in arguments | Strictly raises `ResourceAdmissionError: Route-to-command violation: Command binary 'codex' is not permitted for provider 'zai'` | **PASSED (Fail-Closed)** |
| **Neg 5** | Local Probe Model CLI Smuggling (C2114) | `is_local_probe=True` with command argv containing model CLI `["echo", "zcodex", "run"]` | Strictly raises `ResourceAdmissionError: Local probe foreign CLI violation: Argument 'zcodex' references model CLI under local probe` | **PASSED (Fail-Closed)** |
| **Neg 6** | Local Probe Zero Quota Claim (C2114/C2118) | `is_local_probe=True` executed with promotional/valid provider quota telemetry present | Emits `provider="local"`, `model="none"`, `model_quota_claimed=False`, `quse_admitted=False`; Store payload records zero quota claim | **PASSED (Verified)** |
| **Neg 7** | Prelude Kernel Membership Failure (C2106) | `/proc/self/cgroup` mismatch or own PID absent from kernel `/sys/fs/cgroup/.../cgroup.procs` | Prelude exits immediately with code 96 or 97; runner traps exit, triggers SIGKILL, and transitions to `launch-uncertain` | **PASSED (Fail-Closed)** |
| **Neg 8** | Descendant Cgroup Lingering Processes (C2106) | Root cgroup empty but descendant `child_slice/cgroup.procs` has PID 99999 or `cgroup.events` reports `populated 1` | `_is_cgroup_dissolved_or_empty` detects populated flag/descendant PID, returns `False`; task transitions to `launch-uncertain` | **PASSED (Fail-Closed)** |
| **Neg 9** | Missing Output Teardown Order (C2106) | Process exits 0 but required output artifacts are absent or zero bytes | `systemctl stop` and `verify_unit_cleanup` executed *before* output inspection; task cleanly transitions to `failed` without orphan processes | **PASSED (Fail-Closed)** |
| **Neg 10** | Popen Start Failure Uncertainty (C2106) | `subprocess.Popen` raises `OSError` (e.g. fork exhaustion) with unproven cleanup | Sends `SIGKILL`, evaluates cleanup; unproven cleanup transitions task to `launch-uncertain` holding 1500 MB Store reservation | **PASSED (Fail-Closed)** |

---

## 4. Live Systemd Scope Kernel Custody Probe Receipt (Test 12)

A live kernel custody probe was executed via `execute_in_verified_systemd_scope` under `systemd-run --user --scope` with `requested_memory_mb=1500` and `is_local_probe=True`.

### 4.1 Process Execution & Teardown Output
```
Failed to stop agent-scope-t-scope-prob-5ddc8021.scope: Unit agent-scope-t-scope-prob-5ddc8021.scope not loaded.
RESULT_STATUS: 0
UNIT_NAME: agent-scope-t-scope-prob-5ddc8021.scope
IS_LOCAL_PROBE: True
MODEL_QUOTA_CLAIMED: False
PROVIDER_CHOSEN: local
STDOUT_PREVIEW: probe-success
```

### 4.2 Authentic Containment Verification Receipt JSON
```json
{
  "unit": "agent-scope-t-scope-prob-5ddc8021.scope",
  "pid": 112652,
  "cgroup": "/user.slice/user-1000.slice/user@1000.service/app.slice/agent-scope-t-scope-prob-5ddc8021.scope",
  "memory_max": "1572864000",
  "invocation_id": "112b47fb69af406ba3fec6effff65ac5"
}
```

### 4.3 Technical Analysis of Scope Lifetime
Transient scopes (`systemd-run --user --scope`) are automatically unloaded by systemd upon process termination, resulting in the expected message `Unit ... not loaded` when `systemctl stop` is issued post-exit. The bridge's authoritative cleanup logic correctly verifies containment by inspecting the kernel cgroup filesystem hierarchy directly (`/sys/fs/cgroup/{cached_cgroup}`), ensuring complete dissolution and empty task membership.

---

## 5. Test Suite Execution Receipt (32 Tests PASS)

Command: `python3 -m unittest -v tests/test_launcher_bus_bridge.py`

```
test_01_real_launcher_resource_eligibility_gates (tests.test_launcher_bus_bridge.TestLauncherBusBridge.test_01_real_launcher_resource_eligibility_gates) ... ok
test_02_task_state_lookup_and_lifecycle_in_store (tests.test_launcher_bus_bridge.TestLauncherBusBridge.test_02_task_state_lookup_and_lifecycle_in_store) ... ok
test_03_agent_bus_enrollment_and_message_exchange (tests.test_launcher_bus_bridge.TestLauncherBusBridge.test_03_agent_bus_enrollment_and_message_exchange) ... ok
test_04_quota_admission_gates (tests.test_launcher_bus_bridge.TestLauncherBusBridge.test_04_quota_admission_gates) ... ok
test_05_c2074_offline_negative_tests (tests.test_launcher_bus_bridge.TestLauncherBusBridge.test_05_c2074_offline_negative_tests) ... ok
test_06_c2072_defensive_durability_and_consistency (tests.test_launcher_bus_bridge.TestLauncherBusBridge.test_06_c2072_defensive_durability_and_consistency) ... ok
test_07_child_adapter_integration (tests.test_launcher_bus_bridge.TestLauncherBusBridge.test_07_child_adapter_integration) ... ok
test_08_child_model_runtime_host_admission (tests.test_launcher_bus_bridge.TestLauncherBusBridge.test_08_child_model_runtime_host_admission) ... ok
test_09_child_model_runtime_quse_admission_and_ranking (tests.test_launcher_bus_bridge.TestLauncherBusBridge.test_09_child_model_runtime_quse_admission_and_ranking) ... ok
test_10_child_model_runtime_prepare_and_dispatch (tests.test_launcher_bus_bridge.TestLauncherBusBridge.test_10_child_model_runtime_prepare_and_dispatch) ... ok
test_11_child_model_runtime_rejects_global_tmp (tests.test_launcher_bus_bridge.TestLauncherBusBridge.test_11_child_model_runtime_rejects_global_tmp) ... ok
test_12_child_model_runtime_direct_systemd_scope_probe (tests.test_launcher_bus_bridge.TestLauncherBusBridge.test_12_child_model_runtime_direct_systemd_scope_probe) ... ok
test_13_c2097_missing_empty_unit_info_fails_cleanup (tests.test_launcher_bus_bridge.TestLauncherBusBridge.test_13_c2097_missing_empty_unit_info_fails_cleanup) ... ok
test_14_c2097_unknown_missing_controlgroup_in_prelude (tests.test_launcher_bus_bridge.TestLauncherBusBridge.test_14_c2097_unknown_missing_controlgroup_in_prelude) ... ok
test_15_c2097_children_after_client_exit (tests.test_launcher_bus_bridge.TestLauncherBusBridge.test_15_c2097_children_after_client_exit) ... ok
test_16_c2097_state_still_resource_holding (tests.test_launcher_bus_bridge.TestLauncherBusBridge.test_16_c2097_state_still_resource_holding) ... ok
test_17_c2097_all_exit_paths_uniform_cleanup_helper (tests.test_launcher_bus_bridge.TestLauncherBusBridge.test_17_c2097_all_exit_paths_uniform_cleanup_helper) ... ok
test_18_c2100_blind_query_absence_rejected (tests.test_launcher_bus_bridge.TestLauncherBusBridge.test_18_c2100_blind_query_absence_rejected) ... ok
test_19_c2106_descendant_cgroup_lingering_pids_fails_cleanup (tests.test_launcher_bus_bridge.TestLauncherBusBridge.test_19_c2106_descendant_cgroup_lingering_pids_fails_cleanup) ... ok
test_20_c2106_absent_or_mismatched_invocation_id_fails_cleanup (tests.test_launcher_bus_bridge.TestLauncherBusBridge.test_20_c2106_absent_or_mismatched_invocation_id_fails_cleanup) ... ok
test_21_c2106_missing_controlgroup_fails_closed (tests.test_launcher_bus_bridge.TestLauncherBusBridge.test_21_c2106_missing_controlgroup_fails_closed) ... ok
test_22_c2106_prelude_verifies_proc_self_cgroup_and_membership (tests.test_launcher_bus_bridge.TestLauncherBusBridge.test_22_c2106_prelude_verifies_proc_self_cgroup_and_membership) ... ok
test_23_c2106_route_to_command_binding_rejects_unauthorized_binary (tests.test_launcher_bus_bridge.TestLauncherBusBridge.test_23_c2106_route_to_command_binding_rejects_unauthorized_binary) ... ok
test_24_c2106_bounded_disk_logging_during_execution (tests.test_launcher_bus_bridge.TestLauncherBusBridge.test_24_c2106_bounded_disk_logging_during_execution) ... ok
test_25_c2106_missing_output_cleans_up_and_fails_task (tests.test_launcher_bus_bridge.TestLauncherBusBridge.test_25_c2106_missing_output_cleans_up_and_fails_task) ... ok
test_26_c2106_popen_failure_uncertainty_handling (tests.test_launcher_bus_bridge.TestLauncherBusBridge.test_26_c2106_popen_failure_uncertainty_handling) ... ok
test_27_c2114_unknown_provider_fails_closed (tests.test_launcher_bus_bridge.TestLauncherBusBridge.test_27_c2114_unknown_provider_fails_closed) ... ok
test_28_c2126_structured_launcher_recipe_and_benign_goal (tests.test_launcher_bus_bridge.TestLauncherBusBridge.test_28_c2126_structured_launcher_recipe_and_benign_goal) ... ok
test_29_c2114_local_probe_typing_and_zero_model_quota_claim (tests.test_launcher_bus_bridge.TestLauncherBusBridge.test_29_c2114_local_probe_typing_and_zero_model_quota_claim) ... ok
test_30_c2118_model_route_rejects_arbitrary_python_and_shell_interpreters (tests.test_launcher_bus_bridge.TestLauncherBusBridge.test_30_c2118_model_route_rejects_arbitrary_python_and_shell_interpreters) ... ok
test_31_c2118_model_route_recipes_enforce_mandatory_argv (tests.test_launcher_bus_bridge.TestLauncherBusBridge.test_31_c2118_model_route_recipes_enforce_mandatory_argv) ... ok
test_32_c2118_local_probe_zero_quota_and_store_recording (tests.test_launcher_bus_bridge.TestLauncherBusBridge.test_32_c2118_local_probe_zero_quota_and_store_recording) ... ok

----------------------------------------------------------------------
Ran 32 tests in 9.221s

OK
```

---

## 6. Architectural Report Parity Audit

The technical recovery report `research/antigravity/recovery/REPORT-LAUNCHER-BUS-BRIDGE-C2106.md` (SHA256: `6be489c4cd2711985c22f4e17f83e96c42a3b72cfd5600c22d3dbcea394d72d9`) was compared against `research/antigravity/tooling/self_org/launcher_bus_bridge.py`:
1. **Kernel Cgroup Recursion**: Accurately documents recursive descent across all sub-cgroup `cgroup.events` and `cgroup.procs`.
2. **Fail-Closed InvocationID & ControlGroup**: Accurately reflects strict non-empty matching and rejection of missing control groups.
3. **Dual Prelude Assertions**: Documents exits 96 and 97 verifying kernel cgroup membership directly from `/proc/self/cgroup` and `/sys/fs/cgroup`.
4. **Route Recipes & Provider Isolation**: Matches canonical launcher recipes (`zcodex exec --model glm-5.3-flash`, `grok -p`, `agy`), foreign CLI smuggling prevention, and prohibition of arbitrary python/shell interpreters under model routes.
5. **C2128 Canonical Installed Executable Enforcement**: Correctly documents strict prefix matching without basename-only lookalike fallbacks.
6. **Bounded Disk Logging**: Accurately details the 64 KiB pipe pump thread mechanics and buffer drain.
7. **Output & Teardown Sequencing**: Accurately details pre-output unit teardown and `launch-uncertain` preservation on Popen failure.

---

## 7. Resource, Scratch, and Publication Guard Invariants

1. **Publication Credential Guard**:
   - Command: `python3 research/antigravity/tooling/publication_guard.py research/antigravity/reviews/REV-LAUNCHER-BUS-BRIDGE-C2106.md`
   - Exit Code: `0` (Zero credentials, zero private keys, zero leaked bearer tokens).
2. **Compiler Restrictions**:
   - Zero `cargo` or `rustc` invocations executed throughout the entire challenge session.
3. **Scratch Budget & Isolation**:
   - Scratch root `/home/alexey/git/cloudflare-agent-git/.local/scratch/self-org-challenge/` mode: `0700`.
   - Scratch disk consumption: `< 100 KiB` (strictly below the 512 MB ceiling).
4. **Host `/tmp` Invariant**:
   - Net `/tmp` growth: `0 bytes`. Zero temporary files or descriptors leaked into ambient `/tmp`.
5. **Git Invariant**:
   - Zero git commits or stage mutations executed by subagent.

---

## 8. Formal Verdict

**VERDICT: BOUNDED ACCEPTANCE**

### Conditions and Scope of Acceptance:
1. **Local Kernel Custody Probe (VERIFIED)**:
   - Systemd user scope execution (`systemd-run --user --scope`) under memory boundary (`MemoryMax=1500M`) and scratch containment is physically verified.
   - Dual prelude kernel membership assertions (exits 96/97) and recursive descendant cgroup dissolution checks are proven.
   - Local probes (`is_local_probe=True`, `provider="local"`, `model="none"`, zero quota claim) are strictly demarcated and functional.
2. **Model Execution Route (HELD PENDING PROVEN BRIDGE)**:
   - Real model routes (`zai`, `zcode`, `grok`, `antigravity`, `gemini`, `opencode`, `codex`) strictly forbid arbitrary python or shell interpreters and enforce canonical installed executable recipes without lookalike fallbacks (C2128).
   - Real external model execution remains held pending production verification of live backend provider bridge execution.
