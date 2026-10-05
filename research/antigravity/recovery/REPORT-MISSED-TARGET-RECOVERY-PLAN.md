# Missed Target Recovery Plan — 50 Concurrently Active Task Workers

**Date**: 2026-10-05T12:10:00+02:00 (10:10:00 UTC)  
**Author**: `antigravity-head` (`46fdb644-9b58-4e2f-aab3-9be5e1e33337`)  
**Authority**: Direct human instruction `experiment/human-missed-target-recovery-plan-20261005.txt` and Desktop Orchestrator C2457/C2460 directives.  
**Governing Standard**: OPERATING-MODEL.md, RESOURCE-POLICY.md.

---

## 1. Target vs. Actual Measured Result

| Dimension | Target | Actual Measured Result | Measurement Timestamp & Source |
| :--- | :--- | :--- | :--- |
| **Active Task Workers** | 50 concurrently active workers executing useful tasks | **0 active task workers** | 2026-10-05T10:07:21Z–10:08:00Z UTC (Codex C2460 independent census across all worktrees) |
| **Execution Path** | Agent Quota Launcher | Launcher pipeline held pending API repair + CLI lock fix | `.local/launches/C2449-roster.json` (rewritten at 09:59:12Z) |
| **Fleet Coverage** | Full host census | 3 legacy dashboard workers completed/released; 0 active task units in `systemctl --user list-units agent-task-*` | Scoped list across `experiment`, `launcher`, `dashboard`, `coordination`, `bus` |
| **Prior Empirical Execution** | Real model task validation | `agent-task-c2443-sibling-census3.service` completed in 181.1s (exit 0) | `.local/launches/c2443-sibling-census.md` (mtime 09:38:52Z, receipt 09:39:02Z; earns 0 current-active credit) |

---

## 2. Evidence-Based Explanation of Confirmed Causes vs. Unknowns

### Confirmed Root Causes

1. **API Signature Discrepancy (`validate_quse` TypeError)**:
   - *Evidence*: Tasks `c2445` failed admission immediately before model spawn with `TypeError: validate_quse() got an unexpected keyword argument 'provider'`.
   - *Diagnosis*: `launcher.admission.validate_quse(quse_data, task_requirements=None)` accepts positional `quse_data` and optional `task_requirements`. The initial fail-closed patch in `launcher/task_units.py` invoked `validate_quse(quse_json, provider=provider)`.
   - *Status*: **FIXED** by `antigravity-head` in `launcher/task_units.py` commit. `admit_task_unit` now calls `validate_quse(quse_json)` and explicitly validates that the requested provider is present in `valid_routes`. 25/25 unit tests pass, and full 144-test suite passes.

2. **Launcher Controller Scope Bottleneck (Synchronous Pump Threads)**:
   - *Evidence*: Codex C2455 empirical observation: interactive head cgroup (`aplexer-workload-...`) operates near 74–90 tasks out of `TasksMax=100`.
   - *Diagnosis*: `execute_transient_task_unit` initially ran `systemd-run --pipe` and spawned 2 Python pump threads (`out_thread` and `err_thread`) in the controller process for every active task. Running 50 workers concurrently would spawn 50 PIDs + 100 threads in the controller process, immediately exhausting the head's 100-task limit.
   - *Status*: **FIXED** by `antigravity-head` in `launcher/task_units.py`. Replaced pipe-pump mechanism with native systemd file redirection (`-p StandardOutput=file:... -p StandardError=file:...`). Added `spawn_transient_task_unit` for asynchronous fire-and-forget execution with 0 lingering threads/PIDs in the controller process.

3. **Global Launch Lock Serialization in CLI**:
   - *Evidence*: Codex C2456 audit of `launcher/cli.py` (`run_task_units`): `launch.lock` was initially held across the entire execution duration, forcing all tasks to run sequentially.
   - *Diagnosis*: Lock scope must cover only atomic claim and terminal reconciliation, releasing before execution.
   - *Status*: **FIXED** by `quota-launcher-head` in `launcher/cli.py`. Lock is released before execution and re-acquired for terminal state updates. 4/4 CLI tests pass. Independent non-author review currently running under subagent `03e10418`.

### Unknowns & Epistemic Boundaries
- **Uninstrumented Fleet Headless Sessions**: Other background sessions outside the 4 competition repositories remain uninstrumented and cannot be presumed to be 0 or 50.
- **Provider Concurrency Thresholds**: While host memory (`MemAvailable = 34.4 GiB`) and root disk (`64.1 GiB`) safely support concurrency, upstream provider rate limits on concurrent API streams (e.g. Grok, Z.AI) during 50-worker bursts remain to be measured under empirical load.

---

## 3. Corrective Steps & Execution Roadmap

| Step | Action | Owner | Dependencies | Expected Outcome | Verification |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Step 1** | Independent Non-Author Review of QL CLI backend | `antigravity-head` (subagent `03e10418`) | QL `cli.py` + `test_cli_backend.py` | Deliver `REV-QL-CLI-TASK-UNITS-C2458.md` with FULL ACCEPTANCE | 4/4 tests PASS, publication guard exit 0 |
| **Step 2** | Non-Author Pin Review of repaired `task_units.py` | `quota-launcher-head` | Ant commit on `task_units.py` | QL sign-off on API signature, provider quota gate, and invocation ID tracking | 25/25 unit tests PASS |
| **Step 3** | Adaptive Batch Task Decomposition | `antigravity-head` & `quota-launcher-head` | Steps 1 & 2 complete | 10–20 ready, non-overlapping tasks decomposed from `DELIVERY-BACKLOG.json` (Dashboard tasks, Cross-Computer tests, Website docs) | FileBus task queue populated |
| **Step 4** | Incremental Scale-Out (Phase 1: 10 workers) | `quota-launcher-head` & `antigravity-head` | Step 3 complete | 10 concurrent active workers launched via `python3 -m launcher run --backend task-units` | `systemctl --user list-units "agent-task-*.service"` shows 10 active units |
| **Step 5** | Ramp to 50 Concurrent Active Workers | `quota-launcher-head` & `antigravity-head` | Phase 1 stable, host telemetry nominal | 50 concurrent active workers running useful tasks across available routes (ZCode GLM-5.3-Flash, Grok 4.6, Space Bunny, Muse Spark) | Independent census confirms 50 active PIDs under `app.slice` |

**Target Completion Time**: Next Checkpoint (12:35 Berlin / 10:35 UTC).

---

## 4. Verification Methods

1. **Systemd Transient Unit State**:
   ```bash
   systemctl --user list-units "agent-task-*.service" --state=active
   ```
   Must return exactly the count of active units (e.g., 10, then 50).
2. **Kernel CGroup & Memory Accounting**:
   ```bash
   cat /sys/fs/cgroup/user.slice/user-1000.slice/user@1000.service/app.slice/cgroup.procs | wc -l
   ```
   Must reflect independent worker placement outside `aplexer-workload-*`.
3. **Task State & Semantic Artifacts**:
   - `tasks.sqlite` in `agent-quota-launcher` reflects `state = 'starting'` or `'running'`, followed by `'completed-awaiting-review'` with real output artifacts.
   - Zero duplicate task leases.
   - Zero invented passes or synthetic hashes.

---

## 5. Risks and Hard Constraints

1. **Host Floor Constraints**:
   - `MemAvailable >= 10 GiB` (Current: 34.4 GiB $\rightarrow$ capacity for up to $24.4 \text{ GiB} / 512 \text{ MiB} \approx 47$ workers at 512M, or up to 60 workers if lightweight workers consume 300M).
   - Root disk free $\ge 50 \text{ GiB}$ (Current: 64.1 GiB $\rightarrow$ allows ~14 GiB total disk usage across all `.local/tmp` workspaces).
   - `/data` strictly denied (18.9 GiB free, below 50 GiB floor).
2. **Provider Quotas & Gates**:
   - OpenAI Codex: 15% reserve gate strictly enforced.
   - Grok / Z.AI: Fresh quota windows checked fail-closed before admission.
3. **Disjoint Workspace Ownership**:
   - All worker temp directories strictly isolated under `<repo>/.local/tmp/<task_id>`.
   - Zero concurrent writes to identical canonical paths.
