# Physical Storage & Isolation Benchmark: Workspace-Doctor vs Naive Copies vs Flawed All-Hardlink Baseline

**Author:** Antigravity (`agy` / Gemini 3.8 Flash, `antigravity-head`)  
**Date:** 2026-10-02  
**Harness & Artifacts:** `research/antigravity/r8_physical_storage_isolation.py`, results in `research/antigravity/r8_physical_storage_results.json`.  
**Directives Answered:** User Message 22 & Orchestrator `HEARTBEAT2024` / `MILESTONES2024`.

---

## 1. Problem & Architectural Rationale

The user and Claude identified that naive Git worktrees rapidly exhaust host disk storage (Claude scan measured 111.7 GiB across 472 worktrees), primarily driven by duplicated dependencies.

Earlier, ZCode proposed an "all-hardlink" store (U7 benchmark claiming 67.8% savings). However, Desktop Orchestrator discovered a critical fatal defect: ZCode's benchmark hardlinked **writable source files** as well as dependencies. When one agent modified a source file in its worktree, it mutated the underlying shared inode, silently corrupting the source code of other concurrent agents and the parent repository.

This benchmark establishes a real physical test of the **Workspace-Doctor** architecture:
1. **Shared Immutable Dependencies:** Dependencies (`node_modules`) are shared via hardlinks from a central immutable package cache.
2. **Independent Writable Source:** Source files (`src/`, configs) are independent physical copies per worktree (never hardlinked across tasks).
3. **Separated Mutable Build Outputs:** Build artifacts (`dist/`, `.wrangler/`) are strictly isolated per task.

---

## 2. Experimental Setup & Methodology

The benchmark creates a realistic TypeScript/Node Cloudflare Worker repository in a scratch filesystem (`/tmp` on NVMe, physical 1-byte block measurement `du -s -B1` and joint deduplication `du -c -s -B1`).

### Three Architectures Evaluated:
1. **Architecture A (Naive Worktrees / Full Copies):** Independent copies of `.git`, `src`, `node_modules`, and build artifacts for Task 1 and Task 2.
2. **Architecture B (Flawed All-Hardlinks Baseline):** Emulates ZCode U7 by hardlinking all files, including `src/` and build outputs, across Task 1 and Task 2.
3. **Architecture C (Workspace-Doctor):** Shared immutable `node_modules` (hardlinked from central store), independent `src/` copies, separated `dist/` build outputs.

### Concurrent Workload & Isolation Invariants:
Two concurrent tasks run simultaneously via parallel threads:
- **Task 1:** Edits `src/auth.ts` (`authenticate(token) === 'task1_token'`) and executes the build script.
- **Task 2:** Edits `src/routes.ts` (`routes = ['/api/task2/orders', ...]`) and executes the build script.

**Verification Invariants:**
- **Source Isolation:** Task 2's `src/auth.ts` MUST NOT contain Task 1's edit, and Task 1's `src/routes.ts` MUST NOT contain Task 2's edit.
- **Build Isolation:** Task 1's `dist/bundle.js` MUST NOT contain Task 2's routes, and Task 2's bundle MUST NOT contain Task 1's token.

---

## 3. Measured Physical Results (Like-for-Like Byte Union)

| Metric | Arch A: Naive Copies | Arch B: All-Hardlinked (Flawed) | Arch C: Workspace-Doctor |
| :--- | :---: | :---: | :---: |
| **Source Isolation** | **PASS (True)** | **FAIL (False)** | **PASS (True)** |
| **Build Isolation** | **PASS (True)** | **FAIL (False)** | **PASS (True)** |
| **Task 1 Allocated Bytes** | 22,786,048 B (21.73 MiB) | 22,786,048 B (21.73 MiB) | 22,786,048 B (21.73 MiB) |
| **Task 2 Allocated Bytes** | 22,786,048 B (21.73 MiB) | 22,786,048 B (21.73 MiB) | 22,786,048 B (21.73 MiB) |
| **Summed Apparent Bytes** | 45,572,096 B (43.46 MiB) | 45,572,096 B (43.46 MiB) | 45,572,096 B (43.46 MiB) |
| **Joint Physical Union Bytes** | **45,572,096 B (43.46 MiB)** | **23,273,472 B (22.19 MiB)** | **23,445,504 B (22.36 MiB)** |
| **Real Physical Disk Savings** | **0 B (0.0%)** | 22,298,624 B (48.93%) | **22,126,592 B (48.55%)** |
| **Overhead vs Unsafe Baseline**| — | baseline | **+172,032 B (+0.7%)** |

### Task 1 Physical Category Split (`du -s -B1`):
- **Dependencies (`node_modules`):** 22,429,696 B (21.39 MiB) $\rightarrow$ **98.44%** of workspace
- **Git Metadata (`.git`):** 237,568 B (232 KiB) $\rightarrow$ **1.04%** of workspace
- **Mutable Build Output (`dist` + `.wrangler`):** 81,920 B (80 KiB) $\rightarrow$ **0.36%** of workspace
- **Writable Source (`src` + configs):** 20,480 B (20 KiB) $\rightarrow$ **0.09%** of workspace

---

## 4. Architectural Analysis & Findings

1. **Failure of All-Hardlink Baselines (Arch B):**
   - The benchmark decisively caught the fatal flaw: when Task 1 edited `src/auth.ts`, the shared filesystem inode was mutated in-place. Task 2 immediately observed Task 1's uncommitted token (`source_isolated: false`), and Task 2's build bundle was corrupted (`build_isolated: false`).
   - Claiming 67.8% disk savings by hardlinking writable sources is an unsafe upper bound that cannot be used in multi-agent workflows.

2. **Viability of Workspace-Doctor (Arch C):**
   - Workspace-Doctor achieved **48.55% physical disk savings across 2 concurrent tasks** (reducing physical footprint from 43.46 MiB to 22.36 MiB) while preserving **100% source and build isolation**.
   - The cost of full source and build isolation is merely **172 KiB (0.7% overhead)** compared to the unsafe all-hardlink approach, because writable sources and build directories represent only 0.45% of the total workspace footprint.

3. **Multi-Agent Scaling Projection (Physical Extents):**
   - For $N=5$ concurrent agents:
     - Naive copies: $5 \times 21.73 \text{ MiB} = 108.65 \text{ MiB}$.
     - Workspace-Doctor: $21.39 \text{ MiB (shared deps)} + 5 \times (0.23 + 0.08 + 0.02) \text{ MiB} \approx 23.04 \text{ MiB}$ (**78.8% physical disk savings**).
   - For $N=10$ concurrent agents:
     - Naive copies: $217.3 \text{ MiB}$.
     - Workspace-Doctor: $21.39 + 10 \times 0.33 \approx 24.69 \text{ MiB}$ (**88.6% physical disk savings**).

4. **Honest Scope Calibration ("No claim fixes user disk until real result"):**
   - This experiment validates the physical storage and isolation mechanics under synthetic multi-file Worker repositories.
   - It does **NOT** claim to have fixed user disk across existing worktrees (zero user worktrees were cleaned or altered).
   - Real-world adoption requires validating package manager behavior (e.g. preventing npm/yarn from replacing hardlinks with copies during `install`) and integrating safe lifecycle hooks.
