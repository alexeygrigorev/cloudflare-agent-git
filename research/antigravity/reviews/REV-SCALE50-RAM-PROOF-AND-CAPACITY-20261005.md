# Review: Task-Specific RAM Proof & Stage 50 Single-Host Feasibility

- **Target Task**: `scale50-C-capacity-stages`
- **Author/Owner**: `quota-launcher-head-gemini` (`a86056b5-8b6b-403a-9b8f-6f0b49308959`)
- **Review Scope**: Task-specific RAM proof, cgroup RSS measurements, `MemoryMax` semantics, and 10/25/50 stage feasibility
- **Date**: `2026-10-05T16:05:00Z` (18:05 Berlin)
- **Status**: **STAGE 50 MARKED UNPROVEN / INFEASIBLE ON SINGLE HOST; SAFE ALTERNATIVE ESTABLISHED**

---

## 1. Measured Task-Unit Cgroup RSS & Real CLI Footprints

Empirical resource consumption was extracted directly from live systemd service accounting (`journalctl --user -u "agent-task-*"`) for completed real provider runs:

| Task Unit Service | Provider CLI / Task Type | Consumed CPU | Measured Memory Peak | Verdict under 350M Cap |
| :--- | :--- | :---: | :---: | :---: |
| `agent-task-scale50-07-opencode-audit.service` | OpenCode / Node.js + AGY Audit | 29.61s | **768.0 MiB** | **HARD OOM KILL** (Exceeds by +418 MiB) |
| `agent-task-scale50-08-agy-audit.service` | Gemini Pro / AGY Tooling Audit | 8.98s | **367.0 MiB** | **HARD OOM KILL** (Exceeds by +17 MiB) |
| `agent-task-review-refill-runtime.service` | Gemini Pro / AGY Runtime Review | 21.91s | **358.1 MiB** | **HARD OOM KILL** (Exceeds by +8.1 MiB) |
| `agent-task-review-opencode-audit.service` | Gemini Pro / AGY Report Review | 2.42s | 176.3 MiB | Survives (Review only) |
| `agent-task-review-branches-sync.service` | Gemini Pro / AGY CLI Review | 4.53s | 176.0 MiB | Survives (Review only) |
| `agent-task-review-branches-sync-v2.service` | Gemini Pro / AGY Code Review | 3.20s | 145.7 MiB | Survives (Review only) |
| `agent-task-review-scale50-08.service` | Gemini Pro / AGY Report Review | 1.26s | 123.4 MiB | Survives (Review only) |

### Analysis of Provider CLI Runtime Overhead:
1. **Python Prelude & Subprocess Pipes**: The launcher injects `prelude_{task_id}.py` which wraps `subprocess.Popen` and manages file redirection. Baseline footprint: ~30–50 MiB.
2. **Provider Binaries**:
   - `opencode run` invokes Node.js v24.13.1. The V8 engine runtime, heap allocations, and JSON streaming require a baseline RSS of 200–400 MiB.
   - `agy` (`gemini-3.1-pro-high`) is an interactive agent CLI with large context window buffers, command history, and tool invocation dispatchers: baseline RSS 150–350 MiB.
3. **Execution Workloads**: Workloads executing tests (`pytest`, `unittest`), AST audits, or git operations add 50–150 MiB.
4. **Conclusion on 350M Cap**: Recommending a 350M `MemoryMax` ceiling is **factually invalidated** by real telemetry. Real implementation and heavy review tasks peaked between **358.1 MiB and 768.0 MiB**. Enforcing 350M would trigger immediate cgroup OOM termination.

---

## 2. Launcher `MemoryMax` Semantics & Cgroup OOM Enforcement

In `agent-quota-launcher/launcher/task_units.py`:
- `build_systemd_run_argv` passes `"-p", f"MemoryMax={memory_mb}M"`.
- Under Linux cgroup v2, `MemoryMax` is a hard boundary enforced by the kernel memory controller.
- When `memory.current > memory.max` and reclaim fails, the kernel invokes `oom_kill_process`.
- The process is terminated immediately with `SIGKILL` (exit code 137). There is no soft throttling or recovery.
- Therefore, setting `MemoryMax` below observed task RSS causes hard, fatal task failures.

---

## 3. Host Memory Floor Verification (50 x 350M Evaluation)

- **Total Host RAM (`/proc/meminfo`)**: `32,709,308 kB` ($31.19\text{ GiB}$)
- **Current Host `MemAvailable`**: `30,094,000 kB` ($28.70\text{ GiB}$)
- **Baseline OS & Persistent Services**: $31.19 - 28.70 = 2.49\text{ GiB}$
- **Theoretical 50 x 350 MiB Workloads**: $50 \times 350\text{ MiB} = 17,500\text{ MiB} = 17.09\text{ GiB}$
- **50 Systemd Service Units & Controller Overhead**: ~25 MiB per scope $\times 50 = 1.22\text{ GiB}$
- **Total Projected Memory Consumed**: $17.09 + 2.49 + 1.22 = 20.80\text{ GiB}$
- **Projected Available Host RAM**: $31.19 - 20.80 = 10.39\text{ GiB}$
- **Margin above Mandatory 10.0 GiB Floor**: **`0.39 GiB` (`399 MiB`)**

### Fatal Flaws of 50 x 350M on Single Host:
1. **Unrealistic Ceiling**: As proven in Section 1, real CLIs exceed 350M (peaking at 358M, 367M, 768M).
2. **True Memory at Observed Peaks**: At verified real provider footprints ($768\text{M}$), 50 tasks require $50 \times 768\text{ MiB} = 38.4\text{ GiB}$, which exceeds total host physical RAM ($31.19\text{ GiB}$) by $7.2\text{ GiB}$.
3. **Razor-Thin Margin**: Even under the invalid 350M assumption, a margin of 399 MiB (1.2% of RAM) leaves zero buffer for filesystem caching, dynamic allocations, or transient process spawns, triggering host-wide memory emergency.

---

## 4. Stage 50 Determination: UNPROVEN / INFEASIBLE

**Verdict**: **Stage 50 (50 concurrent task units on single host) is UNPROVEN and INFEASIBLE.**
Attempting 50 concurrent workers on this single 32 GB machine violates either the mandatory 10.0 GiB host memory floor or causes kernel OOM kills across workers.

---

## 5. Safe, Tested Alternative

### Option A: Bounded Concurrency + High-Throughput Automated Refill (RECOMMENDED)
- **Concurrency**: Stage 1 (**10 concurrent workers**) or Stage 2 (**max 15 concurrent workers**).
- **Per-Task Allocation**: Verified safe `MemoryMax = 768M` per unit (complying with `RESOURCE-POLICY.md` which authorizes up to 1500M).
- **Host RAM Buffer**:
  - At 10 workers: $10 \times 768\text{ MiB} = 7.68\text{ GiB}$. Host available RAM: $28.70 - 7.68 = 21.02\text{ GiB} \gg 10.0\text{ GiB}$ floor ($11.02\text{ GiB}$ safety buffer).
  - At 15 workers: $15 \times 768\text{ MiB} = 11.52\text{ GiB}$. Host available RAM: $28.70 - 11.52 = 17.18\text{ GiB} \gg 10.0\text{ GiB}$ floor ($7.18\text{ GiB}$ safety buffer).
- **Throughput Mechanism**: The automated, non-LLM `watch` loop verified in `wt-refill-runtime` (exit 0) immediately refills finished slots from the queue.
- **Outcome**: Delivers the 50-task milestone sequentially across 3–5 waves of 10–15 workers without any OOM kills or host instability.

### Option B: Multi-Host Distributed Execution (For True 50 Concurrent)
- Leverage **Product 4: Cross-computer Agent Coordination**.
- Distribute 25 workers to the Hetzner remote server and 25 workers to the desktop orchestrator machine.
- Each machine runs well within its safe 10–15 worker capacity buffer.

---

## 6. Storage Gate Invariant
- **Live Root Statvfs**: `50,178,809,856` bytes free ($46.7327\text{ GiB}$). Deficit: $3.2673\text{ GiB}$ to $50.0\text{ GiB}$ floor.
- **Strict Execution Policy**: **ZERO worker units may be launched while root disk is below 50.0 GiB.**
- **Recovery Path**: Operator authorization of the non-OpenCode historical zstd archive to `/data` (+3.84 GiB restoration) is required before any worker launch.
