# Multi-Agent Coordination Dogfood Evidence: Agent Branches Development

**Author:** antigravity-head (`46fdb644-9b58-4e2f-aab3-9be5e1e33337`)  
**Lane:** `a16-runtime-protocol` / Agent Branches L2 Client & L3 Advisory Radar  
**Date:** 2026-10-03 (Europe/Berlin)  
**Authority:** Human Message 35 (Dictated 15:15 CEST, `experiment/USER-INSTRUCTIONS.md`, commit `3a4ed8d`), Claude Principal directives (`01a101de-ec95`, `01a101e0-e687`), and Codex Principal directives (C-1321, C-1323).

---

## 1. Executive Summary: The Real Struggle of Concurrent Agent Development

Human Message 35 states the core objective:
> *"make sure that the heads run a lot of sub agents so we can actually experience that multi-agent core flow... I want to see them struggle with parallel work right so that's the point of this project to be able to use"*

In response, `antigravity-head` scaled execution capacity across **4 concurrent subagent executors** operating in isolated worktrees and scopes:
1. `l3-radar-builder` (`00ea32c5`): L3 radar engine on `proto/l3-radar`.
2. `l2-client-builder` (`98576653`): L2 CLI & client library on `proto/l2-client`.
3. `l3-radar-dogfood-producer` (`ed37ae34`): Concurrency stress & RAM benchmark on `proto/l3-radar-bench`.
4. `l1-l2-l3-integration-tester` (`f197d26f`): End-to-end integration test suite on `proto/integration`.

This document records the exact friction, collisions, lock contention, interface drift, and resource bottlenecks encountered and solved during live concurrent execution.

---

## 2. Friction Case Ledger

### Friction Event 1: Worktree File Collision Between Concurrent Sub-Lanes
- **Timestamp:** 2026-10-03 15:07:30 CEST
- **Actors:** `l3-radar-builder` (authoring export adapter) vs `l3-radar-dogfood-producer` (running benchmark).
- **Incident:** Both executors were initially assigned to workspace `/home/alexey/git/agent-branches-l3-radar`. While `l3-radar-builder` was editing `radar/engine.py` and running unit tests, `l3-radar-dogfood-producer` was preparing to create benchmark test fixtures. Had they operated in the same working tree, uncommitted edits and test executions would have clobbered each other's files.
- **Intervention:** Claude Principal flagged the placement risk (`01a101e0-e687`). `antigravity-head` immediately isolated the dogfood producer into a dedicated worktree:
  ```bash
  git worktree add /home/alexey/git/agent-branches-l3-bench -b proto/l3-radar-bench proto/l3-radar
  ```
- **Consequence / Friction:** Worktree creation required serializing on `.local/git.lock`. Branch `proto/l3-radar-bench` branched from `1632a31` and temporarily lacked `aa60a79` (which was concurrently committed by `l3-radar-builder`), requiring a fast-forward `git pull origin proto/l3-radar` into the bench worktree.
- **Lesson for Agent Branches:** Concurrent agents working in the same conceptual direction MUST be allocated isolated forks or worktrees. Single shared worktrees guarantee uncommitted state clobbering.

---

### Friction Event 2: Coordination Scope Collision on Shared Tasks File
- **Timestamp:** 2026-10-03 15:02:10 – 15:06:50 CEST
- **Actors:** `antigravity-head` vs `public-journal-site` (`088a2387`).
- **Incident:** Claude Principal directed `antigravity-head` to update task rows in `coordination/TASKS.json` (parking frozen infra, activating L2/L3). However, `public-journal-site` held a persistent declared edit scope over `coordination/TASKS.json`. Under aplexer rules, editing without agreement violates scope isolation.
- **Intervention:**
  1. `antigravity-head` sent an aplexer message (`01a101db-befe`) requesting scope clearance.
  2. Waited ~4 minutes for `public-journal-site` to finish its publication round.
  3. Received explicit release reply (`01a101df-48ae`): *"Proceed under the locks, public-journal-site is not currently writing to TASKS.json."*
  4. Acquired `.local/task-registry.lock` and `.local/git.lock`, verified latest remote commits on `main`, applied JSON transform, and pushed commit `3f81f57`.
- **Consequence / Friction:** 4 minutes of coordinator waiting time; required lock serialization across two separate locks (`task-registry.lock` and `git.lock`).
- **Lesson for Agent Branches:** Shared mutable registry files create severe serial bottlenecks. Declarative task submission via HTTP APIs (like L1 `POST /tasks`) avoids lock contention entirely.

---

### Friction Event 3: Interface & Wire Contract Drift Across Disjoint Builders
- **Timestamp:** 2026-10-03 15:03:00 – 15:05:00 CEST
- **Actors:** L1 Scaffold builder (`claude-exec-l1b` on `proto/l1-scaffold`) vs L3 Radar builder (`l3-radar-builder` on `proto/l3-radar`).
- **Incident:** Independent implementations diverged in subtle but breaking ways:
  - L1 defined `RadarPairResult` with `heads: { a: string, b: string }` and `evidence: string`.
  - L3 defined `PairResult` with `heads: { agentId: sha }` and `evidence: Dict[str, Any]` containing structured test diagnostics (`tests_collected`, `exit_code`, `test_output_tail`).
  - L1 coordinator assumed check results evaluated at current heads, risking stamping stale checks onto newly pushed commits.
- **Intervention:** Codex Principal C-1321 and Claude Principal `01a101dd-a726` halted informal casting and codified **CONTRACT v0.1**:
  - Global `vector: { [agentId]: sha }` on payload.
  - If `payload.vector != coordinator.heads`, L1 returns HTTP 409 Conflict (`stale_vector`).
  - Evidence preserves full structured object dictionary.
  - L3 implemented `export_l1_payload()` in commit `aa60a79`.
  - L2 client implemented `StaleVectorError` handling in `client.py`.
- **Consequence / Friction:** Required refactoring in both L1 and L3; excising ad-hoc serializers; building strict schema validation tests.
- **Lesson for Agent Branches:** Multi-agent development without a strict versioned contract causes silent type degradation (e.g. stringifying rich test objects or dropping fields). Contracts must be enforced at the boundary with automated schema validation.

---

### Friction Event 4: Host Memory (RAM) vs Process Isolation Bottleneck
- **Timestamp:** 2026-10-03 14:30:00 – 15:03:00 CEST
- **Context:** Human message 35 explicitly identified that the primary execution pain was RAM exhaustion from queued parallel tests, not disk space.
- **Incident:** L3 Advisory Radar initially explored custom in-memory callable test runners (`test_runner: Callable`). To isolate arbitrary user callables, L3 implemented `os.fork()` + pipe IPC + pickle serialization. This introduced:
  - Deserialization security attack surface.
  - Worker process leaks under timeout conditions.
  - Risk of child processes exhausting host memory.
- **Intervention (C-1320 Scope Cut):**
  - Accepted Codex Principal C-1320 challenge: cut custom callback API and pickle IPC completely from MVP (commit `1632a31`, deleting 240 lines).
  - Unified exclusively on hardened CLI runner (`test_command: List[str]`):
    - `shell=False` ALWAYS via `shlex.split`.
    - Strict resource bounds via `preexec_fn=_preexec_limits`: `RLIMIT_CPU=15s`, `RLIMIT_AS=1024MB`, `RLIMIT_FSIZE=50MB`.
    - Process group isolation via `os.setsid()` and `os.killpg(signal.SIGKILL)` on timeout.
    - Explicit process reaping (`p.communicate()`) preventing zombie processes.
- **Measured Host RAM State:**
  - `MemTotal`: 64,223 MB (~64 GB)
  - `MemAvailable`: 38,350 MB (~38 GB, safely exceeding the >= 10 GiB gate)
  - `SwapUsed`: 21,682 MB
- **Lesson for Agent Branches:** Dynamic code execution in multi-agent environments must enforce strict OS-level cgroup/rlimit process memory boundaries. Language-level callbacks without memory limits inevitably cause host RAM exhaustion.

---

## 3. Active Concurrency Footprint

| Agent Tag | Harness ID | Worktree | Branch | Role & Active Task | Resource Guard |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `antigravity-head` | `46fdb644` | `cloudflare-agent-git` | `main` | Head of lane, principal coordination, oversight | Host interactive |
| `l3-radar-builder` | `00ea32c5` | `agent-branches-l3-radar` | `proto/l3-radar` | CONTRACT v0.1 export adapter (`aa60a79`) | Memory rlimit 1024MB |
| `l2-client-builder` | `98576653` | `agent-branches-l2-client` | `proto/l2-client` | POST /checks CLI + 409 StaleVectorError | Minimal urllib |
| `l3-radar-dogfood-producer` | `ed37ae34` | `agent-branches-l3-bench` | `proto/l3-radar-bench` | 5-agent concurrency matrix stress benchmark | Monitored RSS |
| `l1-l2-l3-integration-tester` | `f197d26f` | `agent-branches-integration` | `proto/integration` | End-to-end integration & negative stale test | Ephemeral port |

---

## 4. Summary of Principles for Scaled Multi-Agent Coordination

1. **Explicit Worktree Boundaries:** Never let two active writers share a git worktree. Even if they promise to edit different files, build artifacts, git locks, and test caches collide.
2. **Lock Serialization:** Lock contention is a real operational cost. Minimize shared state files; prefer append-only or versioned immutable data.
3. **Fail-Closed Contracts:** When contracts diverge, fail closed immediately. Never silently cast dictionaries to strings or drop unparsed fields.
4. **Hard Memory Ceilings:** Host RAM is the critical bottleneck under parallel test execution. All spawned test execution processes must run with explicit address-space rlimits (`RLIMIT_AS`) and process group termination.
