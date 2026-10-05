# Active-Worker Census & 50-Agent Concurrency Bottleneck Audit

- **Date:** 2026-10-05T09:05:00Z (11:05 CEST)
- **Author:** Independent Active-Worker Census Auditor (`census-auditor`, conversation `a3d4f3f5-c6a7-495f-b9a0-6289b2c69b22`)
- **Authority:** Codex Principal Directive C2431 under direct human instruction `experiment/human-fifty-distinct-active-task-agents-20261005.txt`
- **Parent Actor:** Antigravity Head (`antigravity-head`, session `46fdb644`, conversation `245c7bba-9a7b-45c1-87a7-4537f289f9a5`)
- **Deliverables:**
  - Structured Census Metric: [`.local/metrics/active_worker_census_20261005.json`](file:///home/alexey/git/cloudflare-agent-git/.local/metrics/active_worker_census_20261005.json) (mode 0600)
  - Empirical Audit Report: [`research/antigravity/recovery/REPORT-ACTIVE-WORKER-CENSUS.md`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/recovery/REPORT-ACTIVE-WORKER-CENSUS.md)
- **Publication Guard:** Verified via `research/antigravity/tooling/publication_guard.py` (Rule C1601/C1614 clean, zero credentials/tokens).

---

## 1. Executive Summary & Audit Context

On October 5, 2026, the human operator issued a direct instruction:
> *"I want 50 agents running right now on different tasks. we have a lot of tasks based on my intake."*  
> (`experiment/human-fifty-distinct-active-task-agents-20261005.txt`)

Concurrently, `aplexer list` displays exactly 50 multiplexer sessions across the host machine, creating the surface impression that 50 agents may already be running or could immediately be dispatched. Under Codex Principal Directive C2431 and Quota Launcher review C2429/C2430, this independent audit was commissioned to conduct an empirical, non-self-counting census of all currently active agents, project heads, subagents, and monitoring services, to deduplicate shared parent sessions, and to evaluate the physical and operational capacity limits toward running 50 concurrent agents.

### Key Audit Findings

1. **Host-Wide Multiplexer vs. Competition Reality:**
   - Total host `aplexer` sessions: **50 sessions**.
   - Competition workspace sessions: **16 sessions** (across `cloudflare-agent-git`, `agent-dashboard`, `agent-quota-launcher`, and `agent-coordination`).
   - Non-competition host sessions: **34 sessions** (in unrelated host repositories: `dataops`, `dapier`, `relay`, `pocketshell`, `telegram-writing-assistant`, `course-management-platform`, `tmp/*`).
2. **Actor Categorization (Four Mutually Exclusive Sets in Competition):**
   - **Persistent Coordinators (5):** `codex-principal`, `antigravity-head`, `quota-launcher-head`, `agent-dashboard-head`, and `public-journal-site`.
   - **Active Task Workers (2 live, 4 recently delivered):**
     - Live: `daily-journal-correction-20261005` (headless Codex PID 2302045) and `census-auditor` (native harness subagent `a3d4f3f5`).
     - Recently completed with verified disk artifacts: `dashboard-tasks-implementer` (`64c2fff8`), `ql-contained-executor` (`e4035a18`), `zcode-route-specialist` (`79e46f7b`), and `tracker-visual-reviewer` (`3bc11aa4`).
   - **Persistent Services & Monitoring Daemons (6):** `metrics-collector` (PID 1608645, port 8766), `experiment-supervision` (PID 3265459), `desktop-orchestrator` (PID 2599946), `quota-platform-sidecar` (PID 1453156), `quota-platform-coordinator` (PID 1453354), and `agent-branches-local-dev` (workerd/wrangler stack on port 8797).
   - **Idle, Waiting, Ended, or Blocked Sessions (6 in competition, 30 in non-competition):** e.g., `ad-frontend-exec` (idle opencode), `ad-backend-exec` (waiting grok), `ad-independent-reviewer` (idle agy), `quota-launcher-reviewer-z` (terminated cleanly with SIGTERM per C2432), `agent-coordination-head` (exited), and `principal-snapshot-recovery` (exited).
3. **Hard Bottlenecks Preventing Immediate 50-Agent Dispatch:**
   - **Memory Bottleneck:** Available memory is **34.43 GiB** (`MemAvailable: 36,098,332 kB`). Enforcing the mandatory **10.0 GiB host safety floor** leaves **24.43 GiB** of usable memory. At the standard cooperative budget of **1.5 GiB per agent**, the host can safely run at most **16 concurrent heavy agents** `(34.43 - 10) / 1.5 = 16.28`. Lightweight 300 MB headless workers could theoretically scale to ~80 processes, but full LLM harnesses (Antigravity RSS 1.0–3.8 GB, Opencode RSS ~750 MB, ZCodex RSS ~360 MB) cannot exceed 16–25 instances without breaching the floor and triggering the Linux OOM killer.
   - **Disk Storage Bottleneck:** Root partition `/` has **63.26 GiB** free against the **50.5 GiB safety floor**, leaving an operating margin of only **12.76 GiB**. More critically, the `/data` partition has only **18.96 GiB** free against its **50.0 GiB safety floor**, representing an active **31.04 GiB deficit**. Spawning 50 agents creating isolated worktrees or build caches (average 500 MB each = 25 GB) would immediately breach the root disk safety floor and exhaust host disk space.
   - **Process & Thread Cgroup Limits:** Systemd session scopes enforce strict `TasksMax=100` limits in certain cgroups (e.g. Scope 181a). Under concurrent execution, multi-threaded node/browser runtimes exhaust threads, resulting in `pthread_create: Resource temporarily unavailable` failures (as reproduced by Quota Launcher in C2429/C2430). The user session file descriptor limit (`ulimit -n`) is set to 1024.
   - **Provider Quota Headroom:** Grok weekly quota is at **64.0%** with **0 banked resets** (resets in 15h); Z.AI GLM-5.3-Flash is at **88.0% (5h)** / **64.0% (7d)** with 5 banked resets, but is currently outside the 17:00–03:00 Berlin free campaign window; Codex is at **56.0%** (above the 15% reserve floor); Claude is at **49.0%** (strictly reserved for Opus journal writing); Gemini 5h limit is at **63.83%** (resets in 2h). A simultaneous burst of 50 agents would deplete Grok within hours and hit Gemini rate limits.
   - **Task Decomposition Bottleneck:** In [`coordination/TASKS.json`](file:///home/alexey/git/cloudflare-agent-git/coordination/TASKS.json), out of 148 tracked tasks, exactly **2 tasks** are in status `ready` (`frozen-harness-consumer` and `a05-same-task-baseline`), and **17 tasks** are in status `queued`. The human intake has not been decomposed into 50 distinct, isolated, non-overlapping work packages with verified file boundaries and acceptance criteria. Spawning 50 agents without decomposed tasks would cause severe file contention, git lock collisions, and duplicate writer errors.

---

## 2. Comprehensive Census & Deduplication

### 2.1 Methodology & Deduplication Policy

To avoid deceptive headcount inflation:
1. **Separation of Multiplexer Presence vs. Productive Work:** Presence in `aplexer list` or the process table reflects process occupancy, not active task execution. Workers in prompt loops, idle states, or completed phases are classified separately.
2. **Honest Native Harness PID Accounting:** Antigravity native harness subagents share the parent process PID (`560857`) and cgroup. Each subagent is identified by its distinct conversation UUID and verified disk deliverables, without forging separate artificial system PIDs.
3. **Workspace Boundary Isolation:** The 34 sessions running in other user repositories (`dataops`, `dapier`, `relay`, etc.) are cataloged as non-competition host background, preventing confusion with Cloudflare competition execution.

### 2.2 Category A: Persistent Coordinators (Principals & Project Heads)

| Actor ID | Canonical Role | Workspace | Engine | Worker PID | Workload PID | Memory (RSS) | Reported State | Primary Function |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `codex-principal` | Principal Coordinator | `cloudflare-agent-git` | Codex / Node | 2729320 | 2729401 | 38.0 MB | working | Principal oversight, cross-team directives, peer challenge |
| `antigravity-head` | Autonomous Dept Head | `cloudflare-agent-git` | Antigravity | 560806 | 560857 | 3,847.6 MB | working | Autonomous department lead, harness subagent coordination |
| `quota-launcher-head` | Project Head | `agent-quota-launcher` | Grok (grok-4.6) | 1316873 | 1316896 | 218.1 MB | waiting | Quota launcher orchestration, admission testing |
| `agent-dashboard-head` | Project Head | `agent-dashboard` | ZCodex | 1507995 | 1508033 | 362.0 MB | idle | Dashboard lane orchestration, private tracker oversight |
| `public-journal-site` | Publication Head | `cloudflare-agent-git` | Antigravity | 2806951 | 2807007 | 1,089.6 MB | working | Public website, daily journal release, design quality |

*Total Persistent Coordinators: 5*

---

### 2.3 Category B: Active Task Workers

Genuinely running workers executing a specific, bounded task with verified first-action artifacts on disk:

| Worker ID / Tag | Harness / Engine | Task ID & Description | PID / Subagent Conv | Status | Memory (RSS) | Verified Disk Artifacts |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `daily-journal-correction-20261005` | Codex (Headless CLI) | `t-daily-journal-correction-20261005`: Authoring Oct 5 daily journal correction | PID 2302045 (Children: 2302060, 2302062, 2303043, 2310083) | **Running** | 48.8 MB | `.local/journal/correction-20261005/events.jsonl` (1.3 MB)<br>`.local/journal/correction-20261005/progress.md`<br>`.local/journal/correction-20261005/final-fix-pin.json` |
| `census-auditor` | Antigravity Native Subagent | `t-census-audit-c2431-20261005`: Active worker census & 50-agent capacity audit | `a3d4f3f5-c6a7-495f-b9a0-6289b2c69b22` (Parent PID 560857) | **Running** | Shared Harness | `.local/scratch/census-audit/aplexer_snapshot.json`<br>`.local/metrics/active_worker_census_20261005.json`<br>`research/antigravity/recovery/REPORT-ACTIVE-WORKER-CENSUS.md` |
| `dashboard-tasks-implementer` | Antigravity Native Subagent | `private-dashboard-tasks-tracker`: Private task tracker & usability suite | `64c2fff8-c0ea-4343-a619-f69d291920cf` (Parent PID 560857) | Completed (09:01Z) | Shared Harness | `research/antigravity/recovery/REPORT-DASHBOARD-TASKS-USABILITY.md`<br>`research/antigravity/recovery/dashboard-tasks-tracker-and-usability.patch` (134 KB) |
| `ql-contained-executor` | Antigravity Native Subagent | `ql-c2417-provenance-and-attribution`: QL provenance repair & admission | `e4035a18-cc9d-4707-a1b8-cdfd4451f714` (Parent PID 560857) | Completed (09:01Z) | Shared Harness | `agent-quota-launcher/.local/launches/C2432-cgroup.json`<br>`agent-quota-launcher/.local/c2432-reviewer-z-term.txt` |
| `zcode-route-specialist` | Antigravity Native Subagent | `zcode-route-health-diagnosis`: ZCode route & usability diagnostic | `79e46f7b-9162-4aae-b638-17e90cc737a9` (Parent PID 560857) | Completed (08:59Z) | Shared Harness | `research/antigravity/recovery/REPORT-ZCODE-ROUTE-DIAGNOSIS.md` (22 KB) |
| `tracker-visual-reviewer` | Antigravity Native Subagent | `t-tracker-visual-review-20261005`: Pixel inspection of 1440x1000 screenshots | `3bc11aa4-20ea-48df-8038-ffc84da39ee6` (Parent PID 560857) | Completed (09:00Z) | Shared Harness | `.local/scratch/visual-review/desktop-1440.png`<br>Verification receipt in subagent transcript |

*Total Active Task Workers: 2 live concurrent, 4 recently delivered.*

---

### 2.4 Category C: Persistent Services & Monitoring Daemons

Infrastructure daemons, API collectors, and local dev servers supporting the competition:

| Service Name | Type / Implementation | Port | PID(s) | Memory (RSS) | Command Line | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `metrics-collector` | Python Daemon | 8766 | 1608645 | 64.6 MB | `/usr/bin/python3 scripts/metrics/collect.py --loop --serve --interval 60 --port 8766` | Live (200 OK) |
| `experiment-supervision` | Python Aplexer Service | - | 3265459 (worker 3265406) | 20.5 MB | `python3 scripts/supervision/service.py` | Running |
| `desktop-orchestrator` | Python Aplexer Bridge | - | 2599946 (worker 2599863) | 13.2 MB | `python3 scripts/orchestrator-channel-v2.py` | Running |
| `quota-platform-sidecar` | Node Service | - | 1453156 (worker 1453148) | 77.3 MB | `node sidecar.mjs` | Running |
| `quota-platform-coordinator`| Node Daemon | - | 1453354 (worker 1453321) | 77.6 MB | `node main.js` | Running |
| `agent-branches-local-dev` | Workerd / Wrangler Dev Stack | 8797 | 2189553, 2208126, 2264770, 2264861, 2265348, etc. | ~210 MB | `wrangler dev --local --port 8797` (workerd prototype) | Running |

*Total Persistent Services: 6*

---

### 2.5 Category D: Idle, Waiting, Ended, or Blocked Sessions

#### In Competition Workspaces:
1. `ad-frontend-exec` (`fa49c91e`, opencode, PID 1803972/1803979): Memory 749.7 MB. Reported `idle`. Task completed; pane waiting for new prompt.
2. `ad-backend-exec` (`82f06339`, grok, PID 1724958/1724960): Memory 102.6 MB. Reported `waiting`. Prompt completed; waiting for interactive input.
3. `ad-independent-reviewer` (`96a4693f`, agy, PID 1840833/1840902): Memory 142.7 MB. Reported `idle`. Review deliverable finished; session idle.
4. `quota-launcher-reviewer-z` (`603a93a7`, PID 2981885/2981909): **Terminated / Exited**. Cleanly shut down with SIGTERM by `quota-launcher-head` per C2432 following delivery of `reviews/QL-CORE-003-4c2bfec.md`.
5. `agent-coordination-head` (`81e8010c`, PID 2292031): **Exiting / Dead**. Workload process exited.
6. `principal-snapshot-recovery` (`5d47d025`, PID 2716049): **Exiting / Dead**. Recovery task completed.

#### Non-Competition Host Sessions (34 Total):
- `dataops` (6 sessions): `main` (grok, working), `inbox` (grok, working, 100% CPU), `models` (grok, waiting), `invoice-ux` (codex, working), `worktrees` (codex, idle), `login` (codex, idle).
- `dapier` (5 sessions): `agents-load`, `flows`, `invoice-automation`, `plugings`, `incoice` (all idle).
- `dakit` (1 session): `main` (grok, working).
- `relay` (4 sessions): `aisl-email-parity`, `ux`, `aisl`, `ui` (all idle).
- `pocketshell` / `pocketshell-site` (4 sessions): `google`, `new-ui`, `redesign`, `relay` (idle/waiting).
- `aplexer` (2 sessions): `hooks`, `svg` (idle).
- Other standalone/tmp repos (12 sessions): `course-management-*`, `ods-berlin-bot`, `scanlet`, `telegram-writing-assistant`, `tmp/*`.

---

## 3. Host Resource Measurement & 50-Agent Bottleneck Analysis

### 3.1 Host Memory Capacity Calculation

Empirical measurement from `/proc/meminfo`:
```text
MemTotal:       65,765,232 kB  (62.72 GiB)
MemFree:           875,716 kB  ( 0.83 GiB)
MemAvailable:   36,098,332 kB  (34.43 GiB)
Buffers:         1,454,068 kB  ( 1.39 GiB)
Cached:         23,655,588 kB  (22.56 GiB)
SwapTotal:      33,554,428 kB  (32.00 GiB)
SwapFree:       15,899,328 kB  (15.16 GiB)
SwapUsed:       17,655,100 kB  (16.84 GiB)
```

#### Capacity Formula & Safety Floor:
- Mandatory host stability floor: **10.0 GiB**
- Usable memory headroom:
  $$\text{MemAvailable} - \text{Floor} = 34.43\text{ GiB} - 10.0\text{ GiB} = 24.43\text{ GiB}$$
- Standard per-agent cooperative budget: **1.5 GiB** (1500 MB)
- Maximum concurrent heavy agents:
  $$\text{Max Heavy Workers} = \left\lfloor \frac{24.43\text{ GiB}}{1.465\text{ GiB}} \right\rfloor = 16\text{ workers}$$

#### Analysis:
If agents are lightweight headless scripts consuming ~200–300 MB RSS, the host can theoretically support 30–50 processes. However, realistic coding agents running LLM CLI harnesses consume substantially more memory:
- `antigravity-head`: 3,847.6 MB RSS
- `public-journal-site` (agy): 1,089.6 MB RSS
- `opencode`: 749.7 MB RSS
- `zcodex`: 362.0 MB RSS
- `grok`: 218.1 MB RSS

Spawning 50 full LLM harness processes would require between **50 GiB and 100 GiB** of resident memory, far exceeding the 24.43 GiB usable headroom and forcing aggressive swapping or triggering OOM termination of critical principal and supervision processes.

---

### 3.2 Disk Storage Bottleneck & Partition Imbalance

Empirical measurement via `shutil.disk_usage`:
```text
Root Partition (/):
  Total: 435.90 GiB | Used: 350.43 GiB | Free: 63.26 GiB
  Safety Floor: 50.50 GiB | Usable Operating Margin: 12.76 GiB

Data Partition (/data):
  Total: 468.38 GiB | Used: 425.56 GiB | Free: 18.96 GiB
  Safety Floor: 50.00 GiB | Floor Deficit: -31.04 GiB (CRITICAL VIOLATION)
```

#### Analysis:
1. **Root Margin Constraint:** The root partition has only **12.76 GiB** of free space remaining before breaching the 50.5 GiB safety threshold.
2. **Data Floor Breach:** `/data` is already deep in violation of the 50.0 GiB safety floor, with only 18.96 GiB free (a 31.04 GiB deficit).
3. **Workspace Expansion Risk:** Each independent agent requires isolated files, npm dependencies, temporary caches, or worktrees. At an average footprint of 400–600 MB per workspace/worktree:
   $$50\text{ agents} \times 500\text{ MB} = 25.0\text{ GB}$$
   Launching 50 concurrent workspaces would immediately consume the remaining 12.76 GiB margin on `/` and trip the emergency disk guard, risking host write failures.

---

### 3.3 Process, Thread, and Cgroup Limits

1. **Systemd Scope `TasksMax=100` Constraint:**  
   As documented in Quota Launcher C2429/C2430 and Scope 181a diagnostics, systemd login scopes and containerized wrappers frequently apply `TasksMax=100`. Complex agent processes (Node.js runtime, esbuild workers, Chrome headless instances, and LLM background thread pools) rapidly spawn 40–80 threads each. When multiple workers are launched in the same slice, `pthread_create` fails with:
   ```text
   Resource temporarily unavailable (EAGAIN)
   ```
2. **File Descriptor Limits:**  
   The user session `ulimit -n` is strictly set to **1024 open files**. Agents maintaining open sockets to the local metrics server, aplexer control pipes, git lockfiles, and file watchers will quickly exhaust 1024 file descriptors under high concurrency.

---

### 3.4 Provider Quota Headroom & Rate Limits

Empirical verification from `quse --json`:

```text
1. Grok (xAI grok-4.6):
   - 7-Day Window Remaining: 64.0% (resets 2026-10-06T00:08:17Z, in ~15h)
   - Banked Resets Available: 0
   - Assessment: Moderate capacity, but zero replenishment safety margin.

2. Z.AI (GLM-5.3-Flash):
   - 5-Hour Window Remaining: 88.0% (resets 2026-10-05T12:52:13Z, in ~3h)
   - 7-Day Window Remaining: 64.0% (resets 2026-10-06T15:47:28Z)
   - Banked Resets Available: 5 (weekly resets)
   - Assessment: Highest quota headroom. Free promotional window applies 17:00-03:00 Berlin (currently outside window at 11:05 Berlin).

3. OpenAI Codex:
   - 7-Day Window Remaining: 56.0% (resets 2026-10-09T21:13:31Z)
   - Banked Resets Available: 2
   - Reserve Gate: Mandatory 15.0% floor (current: 56.0% > 15.0%, PASS)

4. Claude (Anthropic Opus / Sonnet):
   - 5-Hour Window Remaining: 99.0%
   - 7-Day Window Remaining: 49.0% (resets 2026-10-08T14:59:59Z)
   - Policy: Strictly reserved for Claude Opus daily journal prose and critical review gates. Prohibited for generic worker batching.

5. Gemini / Antigravity:
   - 5-Hour Window Remaining: 63.83% (resets 2026-10-05T11:24:26Z, in ~2h)
   - 7-Day Window Remaining: 64.08% (resets 2026-10-09T08:09:37Z)
   - Assessment: Healthy headroom, but 5h rolling window enforces rate limit smoothing.
```

#### Analysis:
Dispatched across 50 workers, a high-frequency polling or retry loop would consume the remaining 64% Grok weekly quota in less than 4 hours, and would hit the Gemini 5-hour rolling limit within 30–45 minutes. Sustainable concurrency requires provider-aware rate limiting and task scheduling.

---

### 3.5 Task Decomposition Deficit

An essential operational invariant of the autonomous development model is **task isolation**: every running executor must own a concrete, decomposed task with explicit input contracts, bounded deliverables, and non-overlapping file write paths.

An inspection of [`coordination/TASKS.json`](file:///home/alexey/git/cloudflare-agent-git/coordination/TASKS.json) demonstrates:
- **Total tasks recorded:** 148
- **Tasks Completed / Done / Integrated:** 101 tasks
- **Tasks Blocked / Held:** 4 tasks
- **Tasks Currently Running:** 18 tasks (including prospective and handoff trackers)
- **Tasks in Status `ready`:** **2 tasks** (`frozen-harness-consumer`, `a05-same-task-baseline`)
- **Tasks in Status `queued`:** **17 tasks**

#### Analysis:
There are currently only **19 actionable tasks** (2 ready + 17 queued) in the entire project repository. The raw human intake ("we have a lot of tasks based on my intake") represents high-level user intent, not 50 actionable, spec'd engineering work packages. Attempting to immediately dispatch 50 agents would result in:
1. Multiple agents claiming the same task IDs.
2. Concurrent edits to the same files, triggering git lock contention on `.local/git.lock` and merge conflicts.
3. Unproductive spinning and quota waste without verifiable deliverables.

---

## 4. Empirical Census Summary Table

| Category | Description | Count (Live / Active) | Count (Delivered / Idle) | Key Examples |
| :--- | :--- | :---: | :---: | :--- |
| **A. Persistent Coordinators** | Principals & Named Project Heads | **5** | 0 | `codex-principal`, `antigravity-head`, `quota-launcher-head`, `agent-dashboard-head`, `public-journal-site` |
| **B. Active Task Workers** | Bounded executors with verified disk artifacts | **2** | 4 | `daily-journal-correction-20261005` (live), `census-auditor` (live), `dashboard-tasks-implementer` (delivered), `ql-contained-executor` (delivered) |
| **C. Persistent Services** | Monitoring, telemetry collectors, and dev servers | **6** | 0 | `metrics-collector` (port 8766), `experiment-supervision`, `desktop-orchestrator`, `agent-branches-local-dev` (port 8797) |
| **D. Idle / Ended Sessions** | Exited scripts, completed reviews, waiting panes | 0 | **6** (comp) + **30** (non-comp) | `ad-frontend-exec` (idle opencode), `quota-launcher-reviewer-z` (cleanly terminated), `agent-coordination-head` (exited) |
| **Host Multiplexer Total** | All panes visible in `aplexer list` | **13** (working/running) | **37** (idle/waiting/exited) | Exactly 50 host multiplexer panes across all repositories |

---

## 5. Architectural Recommendations for Scaling Concurrency

To safely scale toward the human objective of high concurrent agent throughput without risking host failure or quota exhaustion:

1. **Decompose the Intake into 30–50 Isolated Work Packages:**  
   Project heads (`antigravity-head`, `quota-launcher-head`, `agent-dashboard-head`) must break down queued backlogs into distinct, bounded tasks with isolated file ownership (e.g. distinct subdirectories in `research/`, `tooling/`, or isolated worktrees).
2. **Implement Two-Tier Concurrency Allocation:**  
   - Tier 1: **12–16 Full Interactive/LLM Agents** (allocated across the 4 active projects based on the 24.43 GiB usable memory ceiling).
   - Tier 2: **Lightweight Headless Observers / Checkpoint Reviewers** (executing via bounded subagent turns or ephemeral Python scripts under strict 200 MB caps).
3. **Respect Physical Safety Floors:**  
   - Maintain the **10.0 GiB `MemAvailable` floor** strictly; throttle new agent starts when available memory drops below 12 GiB.
   - Address the **`/data` 31.04 GiB floor deficit** before placing any new agent checkouts or caches on `/data`. Keep new scratch/worktree allocations on `/` strictly bounded under 100 MB per task.
4. **Time-Aware Quota Routing:**  
   Direct high-volume batch tasks to Z.AI GLM-5.3-Flash during the 17:00–03:00 Berlin promotional campaign window to preserve Grok weekly allowance and Gemini 5-hour rolling quotas.
5. **Enforce Clean Process Lifecycle & Pruning:**  
   Follow Quota Launcher's C2432 pattern: immediately send SIGTERM to completed task workers upon artifact delivery rather than allowing idle multiplexer panes to accumulate and consume kernel tasks.

---

## 6. Verification & Invariants Check

- **Publication Credential Guard:**
  ```bash
  python3 research/antigravity/tooling/publication_guard.py research/antigravity/recovery/REPORT-ACTIVE-WORKER-CENSUS.md
  # Exit code: 0 (PASS, zero secrets, zero bearer tokens, zero unredacted URLs)
  ```
- **Rust/Cargo Invariant:** ZERO cargo/rustc invocations.
- **Repository Integrity:** ZERO edits or writes to canonical repositories.
- **Scratch Budget:** Scratch directory `.local/scratch/census-audit/` footprint is **0.68 MB** (strictly $\le 512\text{ MB}$).
- **Deliverable Permissions:** Structured JSON `.local/metrics/active_worker_census_20261005.json` set to mode `0600`.
