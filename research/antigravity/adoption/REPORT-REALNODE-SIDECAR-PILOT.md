# Real Node+Sidecar Pilot Consumer Adoption Report — C1691

- **Executor**: real-node-consumer (`bfe48f0c-53b2-49b3-bee0-e709f54def79`, native harness subagent under `antigravity-head`, not an independently bound aplexer session)
- **Coordinator / Head**: antigravity-head (`46fdb644-9b58-4e2f-aab3-9be5e1e33337`)
- **Directives & Authority**: Codex Principal C1691 (`01a1054b-dadd-7680-beb7-357cc5d70a81`), C1692 (`01a10551-befd-7223-bfd4-12e442311e7e`), C1695 (`01a10558-8127-7982-890d-a65af1e2e944`), C1696 (`01a10559-1c16-7742-9a45-18aa4d630842`), C1699 (`01a10559-7dd5-75b2-a1a1-79a35becdb58`), coordination/antigravity.md §81–§82
- **Date**: 2026-10-04 07:18 CEST (05:18 UTC)
- **Target Base**: `proto/sdk-distribution-complete` @ commit `b2df985d3eedfdf345fceb966b18bed415d1187f` (tree `ca5ce587511aff02ad5088d8c7379c9455e57f21`)
- **Pre-existing Compiled Runtime**: `/home/alexey/git/agent-branches-integration/prototype/.build/node/src/local/main.js` (SHA256: `7747d511a4b8dfcf4d80dfcaf71015d8f5f42c783f2ade3be6590aaad5ffd14f`, Node v24.13.1)
- **Pre-existing Sidecar**: `/home/alexey/git/agent-branches-integration/prototype/local-artifacts/sidecar.mjs` (SHA256: `04a756286b0448734c051f88d1b330ed7b2356b71d1b170eca64db196a949a76`)
- **SDK Under Test**: `agent_branches` Python SDK (`client.py`, `cli.py`, `git_utils.py`) @ `b2df985`
- **Output Remote Ref**: `origin/proto/pilot-realnode-maintenance` @ commit `592a8ee7f18e578d716439dfb5cb672c9423793f`, tree `6287dac9f8f623f99c9fcc99f5e3c59f88584a02`
- **Scratch Workspace**: `/home/alexey/git/cloudflare-agent-git/.local/scratch/realnode-pilot/` (mode 0700, 3.2 MB, strictly <= 512 MB, zero `/tmp` growth)

---

## 1. Executive Summary & Pilot Scope (C1691 / C1696 / C1699)

Under Codex Principal directives C1691 and C1696, this pilot conducted an authentic consumer adoption evaluation comparing two real execution paths for a genuine repository maintenance task:

1. **Track 1 (Matched Ordinary Git Worktree Baseline):** Standard Git clone, checkout of base `b2df985`, applying documentation enhancement to `README.md`, executing the complete 22/22 client test suite (`python3 -m unittest -v tests/test_client.py`), and committing locally.
2. **Track 2 (Real Node+Sidecar Stack Integration):** Dynamic ephemeral port allocation, fresh ephemeral secret generation (mode 0600), background daemon execution of the compiled Node coordinator (`src/local/main.js` with `--disable-wasm-trap-handler --max-old-space-size=256`) and real Git Smart HTTP sidecar (`sidecar.mjs`), canonical repository provisioning via `POST /setup`, seeding the base commit, task registration through `AgentBranchesClient.create_task`, isolated fork clone via Git Smart HTTP using the per-task token, identical `README.md` enhancement, test suite execution (22/22 PASS), Git commit and push over Smart HTTP, push registration via `AgentBranchesClient.push`, status query, and graceful SIGTERM teardown.

### Key Outcomes:
- **Tree Equivalence**: Both tracks produced the **exact same tree hash**: `6287dac9f8f623f99c9fcc99f5e3c59f88584a02`.
- **Test Integrity**: Client test suite passed **22/22 (OK)** in both environments (`7.87s` baseline vs `7.96s` fork worktree). Note: the 22 client tests verify client SDK method contracts against a local server; they do not represent a complete end-to-end multi-actor product test suite.
- **Resource Footprint**: Both daemons ran with sampled resident memory well under the 100 MB guideline (Sidecar sampled ps RSS **75.89 MB**, Coordinator sampled ps RSS **76.88 MB**). Disk footprint was **3.2 MB** (strictly <= 512 MB budget). Zero `/tmp` growth.
- **Process Memory Model**: Memory limits operate under a cooperative process convention; host kernel `memory.max` in `session-8309.scope` is `max`, not a kernel-enforced per-PID or aggregate cgroup ceiling.
- **Conflict Warning Reality**: Exactly **0 warnings** observed, reflecting the physical reality of an uncontested single-actor maintenance task without concurrent collisions. This confirms absence of false-positive alarms, but does NOT serve as proof of concurrent collision detection or multi-actor production safety.
- **Operational Verdict**: **ADOPT (CONDITIONAL)** — the stack is functional and lightweight for local development, provided client tooling uses private credential mechanisms, canonical repo setup is explicitly sequenced, and Node runtimes are constrained by physical memory limits rather than strict virtual address ceilings.

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
| **Total Wall-Clock Time** | **7.920 s** | **9.395 s** (final clean scripted run; troubleshooting time UNKNOWN) | +1.475 s (+18.6%) |
| **Test Suite Execution (22/22)** | 7.870 s | 7.956 s | +0.086 s |
| **Non-Test Overhead** | 0.050 s | 1.439 s | +1.389 s (daemons, setup, HTTP network) |
| **Total Pipeline Steps** | 7 discrete steps | 13 discrete steps | +6 orchestration steps |
| **Tree SHA** | `6287dac9f8f623f99c9fcc99f5e3c59f88584a02` | `6287dac9f8f623f99c9fcc99f5e3c59f88584a02` | **Exact match (0 byte delta)** |
| **Resulting Commit SHA** | `93c9d4791ca515decc6c66d5714b4d746f8c0b2d` | `592a8ee7f18e578d716439dfb5cb672c9423793f` | Distinct timestamps & author commit shas |
| **Active Memory (Sampled ps RSS)** | ~18 MB (Python test runner) | Sidecar: initial 59.70 MB / final 75.89 MB; Coord: initial 62.63 MB / final 76.88 MB | Combined sampled RSS ~153 MB within cooperative 1500 MB budget |
| **Scratch Disk Usage** | 1.1 MB | 3.2 MB | +2.1 MB (bare git repos, state json, logs) |
| **Remote Push Target** | N/A (local worktree only) | `origin/proto/pilot-realnode-maintenance` | Verified live on GitHub remote |
| **Observed Radar Warnings** | N/A | **0 warnings** (uncontested single-actor state) | Zero false alerts; concurrent detection unproven here |

*Note on Developer Time:* The 9.395s metric reflects only the final automated scripted execution of Track 2. Prior manual exploration and troubleshooting of canonical setup and port binding took additional unmeasured developer time (recorded as UNKNOWN). The scripted runtime should not be conflated with total all-in engineering effort or causal adoption velocity.

---

## 4. Measured Daemon RSS and Wall-Clock Timings

### 4.1 Daemon Sampled Resident Memory Snapshots

Both background daemons were measured via `ps -o rss= -p <pid>` at startup and directly prior to teardown:

| Daemon | Initial Sampled RSS | Final Sampled RSS | Target Budget | Compliance |
| :--- | :--- | :--- | :--- | :--- |
| **Local Git Sidecar** (`sidecar.mjs`) | 59.70 MB (61,136 KB) | 75.89 MB (77,716 KB) | <= 100 MB guideline | **Within target** |
| **Compiled Coordinator** (`main.js`) | 62.63 MB (64,136 KB) | 76.88 MB (78,728 KB) | <= 100 MB guideline | **Within target** |
| **Combined Stack RSS** | 122.33 MB | 152.77 MB | <= 1500 MB cooperative pool | **Compliant** (cooperative convention) |

*Memory Enforcement Boundary:* Memory tracking is based on discrete `ps` RSS snapshots, not continuous hardware profiling or kernel cgroup counters. The host cgroup `session-8309.scope` has `memory.max = max`, so resource compliance relies on cooperative process admission and runtime flags (`--max-old-space-size=256`).

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
  Because this pilot ran an isolated single-actor maintenance job without concurrent peer edits against the same files, no merge conflict or AST overlap existed. The coordinator truthfully reported an empty `warnings` array (`[]`). No synthetic warnings or forced stubs were injected. This confirms that the stack does not emit spurious false-positive warnings, but it does NOT provide evidence of collision detection under concurrent load.

---

## 6. Remote Checkpoint Verification

The resolved maintenance commit was pushed from the pilot worktree to the canonical remote origin on GitHub:

```bash
git push origin proto/pilot-realnode-maintenance:refs/heads/proto/pilot-realnode-maintenance
```

- **Remote Branch Ref**: `refs/heads/proto/pilot-realnode-maintenance`
- **Remote Commit SHA**: `592a8ee7f18e578d716439dfb5cb672c9423793f`
- **Remote Tree SHA**: `6287dac9f8f623f99c9fcc99f5e3c59f88584a02`
- **Base Commit**: `b2df985d3eedfdf345fceb966b18bed415d1187f` (tree `ca5ce587511aff02ad5088d8c7379c9455e57f21`)
- **Verification Command**:
  ```bash
  $ git ls-remote origin proto/pilot-realnode-maintenance
  592a8ee7f18e578d716439dfb5cb672c9423793f refs/heads/proto/pilot-realnode-maintenance
  ```

---

## 7. Developer Friction Points & Ergonomics Analysis

Executing this pilot revealed three critical developer experience and architectural nuances:

### 7.1 Git Smart HTTP Authentication: Header vs URL and Process Exposure
- **Symptom**: Attempting `git push http://agent:<token>@127.0.0.1:<port>/repo.git` failed with `fatal: URL rejected: Port number was not a decimal number between 0 and 65535`.
- **Root Cause**: Sidecar tokens generated with query parameters (`art_v1_...?...@127.0.0.1`) break Git URL userinfo parsing.
- **Header Workaround**: Passing `-c http.extraHeader="Authorization: Bearer <token>"` bypasses URL encoding issues and keeps tokens out of remote HTTP server URL access logs.
- **Security Limitation**: Passing `-c http.extraHeader` puts the token directly into process `argv`, making it visible to local users via `ps aux` or `/proc/<pid>/cmdline`.
- **Recommended Production Fix**: Standardize on private Git credential helpers or temporary `~/.gitconfig` includes (mode 0600) rather than command-line arguments.

### 7.2 Coordinator Canonical Repository Setup Lifecycle
- **Symptom**: Calling `create_task` directly against an independently initialized sidecar repository name resulted in `HTTP 400: base_sha not found in canonical history`.
- **Root Cause**: The coordinator manages an authoritative canonical namespace (`agent-branches-canonical-<suffix>`) via `POST /setup`. Manual sidecar repo creation before coordinator setup causes namespace divergence.
- **Remediation**: Harness scripts must sequence `POST /setup` with `ADMIN_TOKEN` first, obtain the authoritative canonical repository name, seed baseline commits into that repository, and then register tasks.
- **Unmeasured Friction**: Initial troubleshooting of this sequencing required investigative trial steps; this time is unmeasured (UNKNOWN) and was excluded from the final 9.395s scripted benchmark.

### 7.3 Node 24 V8 Virtual Address Space Headroom & C1699 Falsification
- **Context**: On Node 24+, the V8 WebAssembly trap handler attempts a 4GB virtual address reservation.
- **Flag Mitigation**: Passing `--disable-wasm-trap-handler --max-old-space-size=256` eliminates the 4GB reservation, allowing the Node coordinator to launch in restricted environments.
- **C1699 Boundary Verification**: Empirical worker testing (01a10558-ea84) revealed that `--disable-wasm-trap-handler` is **not a universal fix for all virtual memory limits**:
  - Under `ulimit -v 1500000` (~1.43 GB virtual limit), the full `db4` compiled coordinator crashes with silent `SIGABRT` on its first request (8/8 failures).
  - Raising the virtual limit to `ulimit -v 1530000` (~1.46 GB virtual) succeeds (5/5 requests succeed).
  - Physical resident memory stays ~77 MB in both cases.
- **Conclusion**: The flags prevent the 4GB Wasm trap reservation, but Node base runtime and thread stacks still require ~1.46 GB of virtual address space. Deployments must enforce physical memory limits (RSS / cgroups) rather than tight virtual address limits (`ulimit -v`).

---

## 8. Unsteered Operational Decision

### Recommendation: **ADOPT (CONDITIONAL)**

#### Rationale for ADOPT:
1. **Low Overhead**: The entire real Node coordinator + Git Smart HTTP sidecar stack added only **1.47 seconds** of overhead over bare local Git operations in automated testing, with 85% of execution time consumed by running unit tests.
2. **True Git Parity**: Agents interact with authentic Git Smart HTTP endpoints. There are no simulated mocks or fake file trees. The worktree created is an actual Git repository with full commit history, object trees, and delta compression.
3. **Robust Isolation**: Per-task tokens isolate agent write permissions to their dedicated forks, preventing cross-agent corruption.
4. **Lightweight Footprint**: At ~150 MB combined RSS and 3.2 MB disk, multiple independent pilot lanes can run concurrently on developer workstations and CI nodes without resource starvation.

#### Conditions for Production Deployment:
1. **Private Credential Mechanism**: Migrate away from `-c http.extraHeader` on the command line to prevent token exposure in `ps` / `/proc`. Use temporary environment files or credential helpers.
2. **Deterministic Setup Flow**: Coordinator initialization must explicitly sequence `POST /setup` before initial task seeding.
3. **Physical Memory Limits Only**: Enforce physical cgroup limits (`memory.max`), avoiding strict virtual memory limits (`ulimit -v`) which cause silent Node 24 `SIGABRT` below 1.46 GB virtual space.
4. **Concurrent Multi-Actor Testing**: This pilot confirms zero false-positive warnings for a single uncontested actor; full validation requires concurrent multi-actor contention tests with verified AST/merge collisions.
