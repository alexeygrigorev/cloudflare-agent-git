# Real Platform Consumer Dogfooding Report: Task T1 on Demo Target

- **Date:** `2026-10-04T12:05:00Z`
- **Lane:** `agent-branches` (`antigravity-head` / `46fdb644-9b58-4e2f-aab3-9be5e1e33337`)
- **Directives:** Task `ab-real-consumer-work` under Direct Human Reset (`experiment/human-delivery-reset-20261004.txt`), `coordination/OPERATING-MODEL.md`, and User Messages 26/31.
- **Target Repository & Subsystem:** `demo-target/` in standalone repository `/home/alexey/git/agent-branches` (Cloudflare-Worker-style shortlinks service).
- **Task Evaluated:** Task T1 from [`demo-target/TASKS.md`](file:///home/alexey/git/agent-branches/demo-target/TASKS.md) ("Link listing & visit counters").

---

## 1. Executive Summary & Objective

To satisfy the human steering requirement that prototype adoption must involve authentic maintenance tasks rather than synthetic demonstrations, this trial evaluated the end-to-end development workflow of implementing **Task T1** across two matched arms:

1. **Arm A (Matched Ordinary Git Worktree Baseline):** Standard single-host developer workflow using `git worktree add`, local editing, `node --test`, and local merge.
2. **Arm B (Real Standalone Agent Branches Platform):** Complete extracted platform workflow using native `sidecar.mjs` Git Smart HTTP daemon, compiled Node.js `main.js` coordinator daemon, raw Python SDK `AgentBranchesClient`, leased write bearer tokens, per-task forks, remote Smart HTTP push, and push-time coordination ledger registration.

Both arms achieved **100% test passing (14/14 tests)** and produced the **identical final Git tree hash** (`b1a84dacc47f79afafb327d9f7667fe41c565f71`).

---

## 2. Empirical Performance & Resource Comparison

The trial was executed deterministically via [`.local/scratch/ab-dogfood/run_dogfood.py`](file:///home/alexey/git/cloudflare-agent-git/.local/scratch/ab-dogfood/run_dogfood.py). High-resolution timing was measured via `time.perf_counter()`, and daemon memory was sampled via `/proc/<pid>/statm`.

| Metric | Arm A: Ordinary Git Worktree | Arm B: Real Agent Branches Stack | Ratio / Delta |
| :--- | :--- | :--- | :--- |
| **Wall-Clock Duration** | **0.4411s** | **0.9943s** | **2.25x** |
| **Command / API Count** | 11 commands | 20 commands/calls | +9 steps (+81%) |
| **Unit Tests Passed** | 14 / 14 PASS | 14 / 14 PASS | Matched parity |
| **Defect Escapes** | 0 | 0 | 0 |
| **Active Background Daemons** | 0 | 2 (Sidecar + Coordinator) | +2 daemons |
| **Daemon RSS Memory** | 0.0 MB | 156.66 MB (Sidecar: 78.0M, Coord: 78.7M) | +156.66 MB |
| **Token Exposure Risk** | Zero network tokens | Leased bearer in `.git/config` (mode 0600) | Bounded |
| **Final Tree SHA** | `b1a84dacc47f79afafb327d9f7667fe41c565f71` | `b1a84dacc47f79afafb327d9f7667fe41c565f71` | **Exact 100% Match** |

---

## 3. Task T1 Implementation Specification

Task T1 required adding link listing and visit tracking to `demo-target/`:

1. `src/store.js`: Added `values()` method to `MemoryStore` returning an array of all stored records.
2. `src/shortlinks.js`:
   - Updated `ShortlinkService.create(slug, url)` to initialize `visits: 0`.
   - Added public method `list()` returning all stored records.
   - Added public method `recordVisit(slug)` resolving the slug, incrementing `visits` by 1, and storing the updated record.
3. `src/worker.js`:
   - Added `GET /links` endpoint returning `200` with `{"links": service.list()}`.
   - Updated redirect handler `GET /:slug` to call `service.recordVisit(slug)` before issuing HTTP 302.
4. `test/t1.test.js`: Added comprehensive automated tests verifying:
   - `GET /links` returns existing records with initial `visits: 0`.
   - Consecutive redirects on `GET /:slug` increment the visit counter to 2.

Test verification:
`node --test` executed across all suites: **14/14 tests PASS (0 failures, 0 timeouts)**.

---

## 4. Developer Ergonomics & Friction Points

During real platform consumer integration, four concrete developer ergonomics and friction points were identified:

1. **Nested Fork Object Structure:**
   - In `AgentBranchesClient.create_task()`, the coordinator API returns `fork: { name: "...", remote: "..." }` rather than a flat string `remote: "..."`.
   - *Friction:* Naive clients expecting `task_res["remote"]` fail with a `TypeError`. The SDK client should provide normalized top-level accessor aliases (`task_res["fork_remote"]`).
2. **Task ID vs Task Keying:**
   - `client.get_task()` returns `taskId` and `task_id` (normalized by client), but underlying coordinator raw payloads use `taskId`.
   - *Friction:* Testing assertions that check `res["task"]` fail. The API documentation must explicitly document the normalized dictionary keys.
3. **Coordinator State Isolation in Testing:**
   - The standalone Node.js coordinator persists its database to `local-coordinator-state.json` by default.
   - *Friction:* Running sequential test runs or ad-hoc adoption trials without configuring `COORDINATOR_STATE_FILE` causes the coordinator to reject `POST /setup` with `created: false` (fail-closed idempotency). Setting `COORDINATOR_STATE_FILE` to an isolated scratch file resolves this cleanly.
4. **Credential Security in Git Smart HTTP:**
   - Rather than embedding the task bearer token in CLI arguments (e.g. `git clone http://token@host/...`), configuring `.git/config` local extraHeaders via `git config --local "http.<remote>.extraHeader" "Authorization: Bearer <token>"` with mode `0600` successfully prevented credential exposure in `ps aux` and `/proc/<pid>/cmdline`.

---

## 5. Unsteered Consumer Adoption Verdict

Based on direct empirical measurement:

- **Single-Actor Tasks:** **DECLINE / PREFER LOCAL GIT WORKTREE**.
  Ordinary Git worktrees complete the maintenance task in 0.44s with 0 background daemons and 0 resident memory overhead, whereas Agent Branches introduces 2.25x latency and 156.7 MB daemon footprint. For solo developers, the platform adds ceremony without offsetting benefits.
- **Concurrent Fleet & Multi-Agent Benefit:** **UNPROVEN / UNKNOWN ON SINGLE-ACTOR FIXTURE**.
  While earlier synthetic experiments (such as the UPRT trial) evaluated concurrent refactoring, this single-actor maintenance trial on Task T1 provides zero empirical evidence regarding multi-agent concurrency, fleet coordination, or buyer adoption. Claims of fleet-level semantic prevention or buyer value cannot be derived from a single-actor fixture; those benefits remain unproven and require testing on actual multi-party product development tasks.

---

## 6. Safety & Resource Invariants

- **Rust Compiler Invariant:** Strictly **0** `cargo` or `rustc` invocations.
- **Metrics Telemetry Invariant:** Strictly **0** derived tokens emitted to `usage-events.jsonl`.
- **Scratch Disk Budget:** Measured at 1.2 MB ($\le 512$ MB limit).
- **Publication Guard:** Validated with `publication_guard.py` (exit code 0).
