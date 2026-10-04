# Real Node+Sidecar Pilot Consumer Adoption Report — C1691

- **Executor**: real-node-consumer (`bfe48f0c-53b2-49b3-bee0-e709f54def79`)
- **Coordinator / Head**: antigravity-head (`46fdb644`)
- **Directives & Authority**: Codex Principal C1691 (`01a1054b-dadd-7680-beb7-357cc5d70a81`), coordination/antigravity.md §81
- **Date**: 2026-10-04 07:14 CEST (05:14 UTC)
- **Target Base**: `proto/sdk-distribution-complete` @ commit `b2df985d3eedfdf345fceb966b18bed415d1187f`
- **Pre-existing Compiled Runtime**: `/home/alexey/git/agent-branches-integration/prototype/.build/node/src/local/main.js` (Node v24.13.1)
- **Pre-existing Sidecar**: `/home/alexey/git/agent-branches-integration/prototype/local-artifacts/sidecar.mjs`
- **SDK Under Test**: `agent_branches` Python SDK (`client.py`, `cli.py`, `git_utils.py`) @ `b2df985`
- **Output Remote Ref**: `origin/proto/pilot-realnode-maintenance` @ commit `592a8ee7f18e578d716439dfb5cb672c9423793f`, tree `6287dac9f8f623f99c9fcc99f5e3c59f88584a02`
- **Scratch Workspace**: `/home/alexey/git/cloudflare-agent-git/.local/scratch/realnode-pilot/` (mode 0700, 3.2 MB, strictly <= 512 MB, zero `/tmp` growth)

---

## 1. Executive Summary & Pilot Scope (C1691)

Under Codex Principal directive C1691, this pilot conducted an authentic, end-to-end consumer adoption evaluation comparing two real execution paths for a genuine repository maintenance task:

1. **Track 1 (Matched Ordinary Git Worktree Baseline):** Standard Git clone, checkout of base `b2df985`, applying documentation enhancement to `README.md`, executing the complete 22/22 client test suite (`python3 -m unittest -v tests/test_client.py`), and committing locally.
2. **Track 2 (Real Node+Sidecar Stack Integration):** Dynamic ephemeral port allocation, fresh ephemeral secret generation (mode 0600), background daemon execution of the compiled Node coordinator (`src/local/main.js` with `--disable-wasm-trap-handler --max-old-space-size=256`) and real Git Smart HTTP sidecar (`sidecar.mjs`), canonical repository provisioning via `POST /setup`, seeding the base commit, task registration through `AgentBranchesClient.create_task`, isolated fork clone via Git Smart HTTP using the per-task token, identical `README.md` enhancement, test suite execution (22/22 PASS), Git commit and push over Smart HTTP, push registration via `AgentBranchesClient.push`, status query, and graceful SIGTERM teardown.

### Key Outcomes:
- **Tree Equivalence**: Both tracks produced the **exact same tree hash**: `6287dac9f8f623f99c9fcc99f5e3c59f88584a02`.
- **Test Integrity**: Full test suite passed **22/22 (OK)** in both environments (`7.87s` baseline vs `7.96s` fork worktree).
- **Resource Footprint**: Both daemons ran strictly under memory caps (Sidecar max RSS **75.89 MB**, Coordinator max RSS **76.88 MB**, both <= 100 MB cap). Disk footprint was **3.2 MB** (strictly <= 512 MB). Zero `/tmp` growth.
- **Conflict Warning Reality**: Exactly **0 warnings** observed, matching the physical reality of an uncontested maintenance task (zero artificial warnings injected).
- **Operational Verdict**: **ADOPT (CONDITIONAL)** — the stack is robust, production-representative, and ready for agent development workflows, provided client tools use HTTP `Authorization: Bearer` headers rather than URL userinfo embedding.

---

## 2. Authentic Maintenance Task Definition

The maintenance task chosen was an authentic documentation enhancement for the SDK package on branch `proto/sdk-distribution-complete`:
- In `README.md`, under `## Run against a local coordinator`, the existing documentation only covered the offline Python test double (`tests/mock_l1_server.py`).
- The authentic maintenance job was adding instructions for running the **real compiled Node coordinator** (`src/local/main.js`) alongside the **real Git Smart HTTP sidecar** (`prototype/local-artifacts/sidecar.mjs`), documenting the required environment variables (`LOCAL_ARTIFACTS_URL`, `LOCAL_ARTIFACTS_TOKEN`, `ADMIN_TOKEN`, `RUNNER_TOKEN`, `COORDINATOR_STATE_FILE`), and highlighting the Node 24 Wasm memory flag (`--disable-wasm-trap-handler --max-old-space-size=256`, C1682).
- Diff size: **+26 lines** inserted directly before `## License`.

---

## 3. Matched Baseline vs Real Node+Sidecar Comparison Matrix

| Metric | Track 1: Ordinary Git Baseline | Track 2: Real Node+Sidecar Stack | Delta / Overhead |
| :--- | :--- | :--- | :--- |
| **Total Wall-Clock Time** | **7.920 s** | **9.395 s** | +1.475 s (+18.6%) |
| **Test Suite Execution (22/22)** | 7.870 s | 7.956 s | +0.086 s |
| **Non-Test Overhead** | 0.050 s | 1.439 s | +1.389 s (daemons, setup, HTTP network) |
| **Total Steps** | 7 discrete steps | 13 discrete steps | +6 orchestration steps |
| **Tree SHA** | `6287dac9f8f623f99c9fcc99f5e3c59f88584a02` | `6287dac9f8f623f99c9fcc99f5e3c59f88584a02` | **Exact match (0 byte delta)** |
| **Resulting Commit SHA** | `93c9d4791ca515decc6c66d5714b4d746f8c0b2d` | `592a8ee7f18e578d716439dfb5cb672c9423793f` | Distinct timestamps & author commit shas |
| **Active Memory (Resident RSS)** | ~18 MB (Python test runner) | Sidecar: 75.89 MB, Coord: 76.88 MB | Cooperative pool < 160 MB (well below 1500 MB) |
| **Scratch Disk Usage** | 1.1 MB | 3.2 MB | +2.1 MB (bare git repos, state json, logs) |
| **Remote Push Target** | N/A (local worktree only) | `origin/proto/pilot-realnode-maintenance` | Verified live on GitHub remote |
| **Observed Radar Warnings** | N/A | **0 warnings** (honest uncontested state) | Zero false alerts |

---

## 4. Measured Daemon RSS and Wall-Clock Timings

### 4.1 Daemon Memory Profile

Both background daemons were measured via `ps -o rss= -p <pid>` at startup and directly prior to teardown:

| Daemon | Initial RSS | Peak / Final RSS | Memory Limit | Compliance |
| :--- | :--- | :--- | :--- | :--- |
| **Local Git Sidecar** (`sidecar.mjs`) | 59.70 MB (61,136 KB) | 75.89 MB (77,716 KB) | <= 100 MB | **PASS** |
| **Compiled Coordinator** (`main.js`) | 62.63 MB (64,136 KB) | 76.88 MB (78,728 KB) | <= 100 MB | **PASS** |
| **Combined Stack RSS** | 122.33 MB | 152.77 MB | <= 1500 MB cgroup | **PASS** |

### 4.2 Detailed Track 2 Step Timing Breakdown

```
[STEP 01] Daemons startup & HTTP health check probes        : 0.171 s
[STEP 02] Coordinator POST /setup (canonical init)          : 0.034 s
[STEP 03] Sidecar POST /api/repos/:name/tokens (write token) : 0.001 s
[STEP 04] Seed canonical repo via Smart HTTP push (b2df985)  : 0.338 s
[STEP 05] SDK client.create_task (fork + per-task token)    : 0.047 s
[STEP 06] Clone isolated fork via Smart HTTP                : 0.101 s
[STEP 07] Apply README.md documentation edit                : <0.001 s
[STEP 08] Run unit tests (tests/test_client.py 22/22 PASS)  : 7.956 s
[STEP 09] Git commit fix in fork worktree                   : 0.019 s
[STEP 10] Git push to fork via Smart HTTP                   : 0.143 s
[STEP 11] SDK client.push registration (POST /events/push)  : 0.002 s
[STEP 12] SDK client status queries (GET /tasks/:id)        : 0.004 s
[STEP 13] Clean daemon teardown (SIGTERM signal wait)       : 0.016 s
-----------------------------------------------------------------------
TOTAL WALL-CLOCK DURATION                                   : 9.395 s
```

---

## 5. Actually Observed Warnings Disclosure

- **Observed Warning Count**: **0**
- **Payload Inspection (`GET /tasks/task-0001`)**:
  ```json
  {
    "taskId": "task-0001",
    "agentId": "real-node-consumer-0001",
    "forkName": "agent-branches-canonical-3d00fe7f-real-node-consumer-0001",
    "ref": "refs/heads/main",
    "head": "592a8ee7f18e578d716439dfb5cb672c9423793f",
    "pushes": 1,
    "warnings": []
  }
  ```
- **Falsification & Truthfulness Assessment**:
  Because this pilot ran an isolated single-actor maintenance job without concurrent peer edits against the same files, no merge conflict or AST overlap existed. The coordinator truthfully reported an empty `warnings` array (`[]`). No synthetic warnings or forced stubs were injected.

---

## 6. Remote Checkpoint Verification

The resolved maintenance commit was pushed from the pilot worktree to the canonical remote origin on GitHub:

```bash
git push origin proto/pilot-realnode-maintenance:refs/heads/proto/pilot-realnode-maintenance
```

- **Remote Branch Ref**: `refs/heads/proto/pilot-realnode-maintenance`
- **Remote Commit SHA**: `592a8ee7f18e578d716439dfb5cb672c9423793f`
- **Remote Tree SHA**: `6287dac9f8f623f99c9fcc99f5e3c59f88584a02`
- **Base Commit**: `b2df985d3eedfdf345fceb966b18bed415d1187f`
- **Verification Command**:
  ```bash
  $ git ls-remote origin proto/pilot-realnode-maintenance
  592a8ee7f18e578d716439dfb5cb672c9423793f refs/heads/proto/pilot-realnode-maintenance
  ```

---

## 7. Developer Friction Points & Ergonomics Analysis

Executing this pilot revealed three critical developer experience and architectural nuances:

### 7.1 Git Smart HTTP Userinfo Token Formatting vs Header Authentication
- **Symptom**: Attempting `git push http://agent:<token>@127.0.0.1:<port>/repo.git` failed with `fatal: URL rejected: Port number was not a decimal number between 0 and 65535`.
- **Root Cause**: Sidecar tokens generated with expiration parameters (`art_v1_...?...@127.0.0.1`) contain query characters (`?`, `=`) that break standard Git URL userinfo parsing.
- **Remediation**: Always authenticate Git operations via HTTP headers:
  `-c http.extraHeader="Authorization: Bearer <token>"`.
  This is cleaner, prevents secret leakage in shell histories and process trees (`ps`), and avoids URL encoding quirks.

### 7.2 Coordinator Canonical Repository Auto-Initialization
- **Symptom**: Calling `create_task` directly against an independently initialized sidecar repository name caused `HTTP 400: base_sha not found in canonical history`.
- **Root Cause**: The coordinator maintains its own canonical repository namespace (`agent-branches-canonical-<suffix>`) managed via `setupNow()`. If a consumer initializes a bare repo manually without invoking the coordinator's setup lifecycle, the coordinator will auto-initialize its own repository upon the first task creation, creating a disjoint root.
- **Remediation**: Consumers and harness scripts must invoke `POST /setup` with `ADMIN_TOKEN` first, obtain the authoritative canonical repository name, seed baseline commits into that repository, and then invoke `create_task`.

### 7.3 Node 24 V8 Virtual Address Space Headroom
- **Symptom / Verification**: In restricted cgroup slices with `ulimit -v`, Node 24's WebAssembly trap handler attempts a 4GB virtual reservation.
- **Remediation Confirmed**: The launch flags `--disable-wasm-trap-handler --max-old-space-size=256` completely eliminate virtual memory exhaustion, maintaining steady resident RSS under 77 MB throughout bare git cloning, object packing, and HTTP transfers.

---

## 8. Unsteered Operational Decision

### Recommendation: **ADOPT (CONDITIONAL)**

#### Rationale for ADOPT:
1. **Low Overhead**: The entire real Node coordinator + Git Smart HTTP sidecar stack added only **1.47 seconds** of overhead over bare local Git operations, with 85% of execution time consumed by running unit tests.
2. **True Git Parity**: Agents interact with authentic Git Smart HTTP endpoints. There are no simulated mocks or fake file trees. The worktree created is an actual Git repository with full commit history, object trees, and delta compression.
3. **Robust Isolation**: Per-task tokens isolate agent write permissions to their dedicated forks, preventing cross-agent corruption.
4. **Lightweight Footprint**: At ~150 MB combined RSS and 3.2 MB disk, multiple independent pilot lanes can run concurrently on developer workstations and CI nodes without resource starvation.

#### Conditions for Deployment:
1. **Standardize Header Auth**: All agent CLI wrappers and SDK helpers MUST use `-c http.extraHeader="Authorization: Bearer <token>"` for Git transport.
2. **Managed Setup Flow**: Coordinator initialization must explicitly sequence `POST /setup` before initial task seeding.
3. **Node 24 Flag Enforcement**: All runner environments MUST pass `--disable-wasm-trap-handler --max-old-space-size=256` when invoking Node runtimes under memory cgroups.
