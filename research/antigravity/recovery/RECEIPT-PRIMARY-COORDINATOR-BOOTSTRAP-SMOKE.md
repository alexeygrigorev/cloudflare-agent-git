# RECEIPT-PRIMARY-COORDINATOR-BOOTSTRAP-SMOKE — Primary Coordinator Live Integration Smoke Test

- **Executor**: Primary Coordinator Smoke Executor (`primary-coordinator-smoke-worker`)
- **Directives**: Codex Principal C1771 / C1774 / C1780 directives:
  *"use healthy alternative if bounded recovery fails... full exact-primary coordinator bootstrap through SDK create_task/push authorization smoke, independent of current source reviewer, fresh quotas/private ports/real1500MiB scope."*
- **Invoker / Parent**: `245c7bba-9a7b-45c1-87a7-4537f289f9a5` (antigravity-head `46fdb644`)
- **Date**: 2026-10-04T06:52:00Z (08:52 Europe/Berlin)
- **Workspace**: `/home/alexey/git/cloudflare-agent-git`
- **Scratch Root**: `/home/alexey/git/cloudflare-agent-git/.local/scratch/primary-coordinator-smoke` (mode `0700`, usage `0.13 MB` $\le$ 512 MB, `TMPDIR` redirected, zero `/tmp` growth)
- **Prebuilt Reference Daemons**:
  - Sidecar: `/home/alexey/git/agent-branches-integration/prototype/local-artifacts/sidecar.mjs` (SHA256: `04a756286b0448734c051f88d1b330ed7b2356b71d1b170eca64db196a949a76`)
  - Coordinator: `/home/alexey/git/agent-branches-integration/prototype/.build/node/src/local/main.js` (SHA256: `7747d511a4b8dfcf4d80dfcaf71015d8f5f42c783f2ade3be6590aaad5ffd14f`)
- **Python SDK Client**: `agent_branches.client.AgentBranchesClient` from `/home/alexey/git/agent-branches-integration/agent_branches/client.py` accessed via `FlexibleAgentBranchesClient` test adapter
- **Outcome**: **SUCCESS** (All 6 bootstrap & workflow phases and both negative tests passed cleanly).

---

## 1. Executive Summary

This receipt documents the successful execution of an end-to-end, live HTTP integration smoke test exercising the exact primary product coordinator bootstrap sequence through Python SDK task registration, bare Git Smart HTTP clone/push, webhook delivery, and authorization gates.

The test verifies that the compiled Node runtime (`main.js`) and the local Git host sidecar (`sidecar.mjs`) correctly interoperate over live localhost sockets, honor exact Git lease semantics on baseline repos, mint and enforce bearer credentials for forked tasks, accept Smart HTTP Git pushes, and fail closed when presented with missing or invalid credentials.

### Epistemic Demarcation & Wrapper Disclosure (Codex C1789)
- **SDK Adapter Wrapper**: The test script (`run_smoke.py`) utilized a local `FlexibleAgentBranchesClient` subclass wrapping `AgentBranchesClient` to bridge parameter naming discrepancies (`task_id` vs `task`, `base_ref` vs `branch`, `commit` vs `head_sha`, and `status()` alias for `get_task()`, plus constructor-level `admin_token` storage). This confirms live API compatibility under the coordinator protocol, but does NOT represent raw unwrapped SDK invocation without adapter assistance.
- **Seed Lease Boundary**: In Step 4, the test cloned the synthetic canonical seed commit and pushed the same `HEAD` back with `--force-with-lease=refs/heads/main:<seedCommit>`. This verifies remote write authorization and exact lease validation on the sidecar, but does not simulate an active code replacement or maintenance commit on canonical (which was separately evaluated in REV-RUNBOOK-SEED-LEASE-7AA20F1.md).
- **Execution Duration**: **0.764 seconds** reflects the wall-clock execution of the final automated test run; total setup, terminal prompt debugging, and run duration was ~6 minutes.
- **Resource Boundaries**:
  - **Zero Cargo / Rustc**: No compilation was invoked (strict compliance with human hold).
  - **Zero `/tmp` Growth**: `TMPDIR`, `TEMP`, and `TMP` were redirected to isolated scratch.
  - **Point-in-Time RSS**: Sidecar RSS was 59.42 MB; Coordinator RSS was 62.47 MB (point-in-time `ps -o rss=` samples, both $\le$ 100 MB).
  - **Scratch Budget**: Total scratch space consumed was 0.13 MB ($\le$ 512 MB ceiling).

---

## 2. Environment & Daemon Setup

Both daemons were launched as local background processes bound to loopback ephemeral ports with high-entropy cryptographic secrets generated in memory:

```bash
# Isolated Ports & Paths
SIDECAR_PORT=9894
COORD_PORT=9895
SCRATCH_ROOT=".local/scratch/primary-coordinator-smoke"

# Secrets generated in memory via secrets.token_hex(24), never logged
ADMIN_TOKEN="$ADMIN_TOKEN"
LOCAL_ARTIFACTS_TOKEN="$LOCAL_ARTIFACTS_TOKEN"
RUNNER_TOKEN="$RUNNER_TOKEN"
```

### Daemon Invocations

1. **Git Sidecar Daemon**:
   ```bash
   SIDECAR_ROOT="$SCRATCH_ROOT/sidecar-root" \
   SIDECAR_HOST="127.0.0.1" \
   SIDECAR_PORT="9894" \
   SIDECAR_TOKEN="$LOCAL_ARTIFACTS_TOKEN" \
   SIDECAR_NOTIFY_URL="http://127.0.0.1:9895/events/push" \
   node prototype/local-artifacts/sidecar.mjs > "$SCRATCH_ROOT/sidecar.log" 2>&1 &
   ```

2. **Coordinator Daemon**:
   ```bash
   LOCAL_ARTIFACTS_URL="http://127.0.0.1:9894" \
   LOCAL_ARTIFACTS_TOKEN="$LOCAL_ARTIFACTS_TOKEN" \
   ADMIN_TOKEN="$ADMIN_TOKEN" \
   RUNNER_TOKEN="$RUNNER_TOKEN" \
   PORT="9895" \
   HOST="127.0.0.1" \
   COORDINATOR_STATE_FILE="$SCRATCH_ROOT/coord-state.json" \
   node --disable-wasm-trap-handler --max-old-space-size=256 \
     prototype/.build/node/src/local/main.js > "$SCRATCH_ROOT/coord.log" 2>&1 &
   ```

3. **Liveness & RSS Verification**:
   - `GET http://127.0.0.1:9894/api/health` with `Authorization: Bearer $LOCAL_ARTIFACTS_TOKEN` $\rightarrow$ `HTTP 200 {"ok": true}`.
   - `GET http://127.0.0.1:9895/status` with `Authorization: Bearer $RUNNER_TOKEN` $\rightarrow$ `HTTP 200`.
   - Sidecar Resident Memory (RSS): **59.42 MB** (Limit: 100 MB).
   - Coordinator Resident Memory (RSS): **62.47 MB** (Limit: 100 MB).

---

## 3. Primary Product Bootstrap Flow

### Step 1: Coordinator POST `/setup` (Initial Provisioning)
- **Request**: `POST http://127.0.0.1:9895/setup` with `Authorization: Bearer $ADMIN_TOKEN`.
- **Response**: `HTTP 201 Created`
  ```json
  {
    "canonical": {
      "name": "agent-branches-canonical-b7a8bef1",
      "remote": "http://127.0.0.1:9894/git/agent-branches-canonical-b7a8bef1.git"
    },
    "created": true,
    "seedCommit": "5c6bc1c1f8244a2407e9a990775e0d54955d18d6"
  }
  ```
- **Assertion**: `created == true`, valid 40-hex SHA-1 `seedCommit`, unique canonical repo name generated and registered.

### Step 2: Idempotent Fail-Closed Check on Repeated Setup
- **Request**: `POST http://127.0.0.1:9895/setup` with `Authorization: Bearer $ADMIN_TOKEN`.
- **Response**: `HTTP 201 Created`
  ```json
  {
    "canonical": {
      "name": "agent-branches-canonical-b7a8bef1",
      "remote": "http://127.0.0.1:9894/git/agent-branches-canonical-b7a8bef1.git"
    },
    "created": false,
    "seedCommit": null
  }
  ```
- **Assertion**: `created == false`, `seedCommit == null`, existing canonical repo identity preserved.

### Step 3: Mint Sidecar Repo Write Token
- **Request**: `POST http://127.0.0.1:9894/api/repos/agent-branches-canonical-b7a8bef1/tokens`
  - Body: `{"scope": "write", "ttlSeconds": 3600}`
  - Auth: `Authorization: Bearer $LOCAL_ARTIFACTS_TOKEN`
- **Response**: `HTTP 201 Created`
  ```json
  {
    "id": "e4f8d5...",
    "repo": "agent-branches-canonical-b7a8bef1",
    "scope": "write",
    "expiresAt": "2026-10-04T09:51:27.000Z",
    "plaintext": "art_v1_[REDACTED]"
  }
  ```
- **Assertion**: Returned plaintext token has `art_v1_` format with active lease and `write` scope.

### Step 4: Seed Git Repo Clone & Exact Lease Push
- In scratch directory, cloned canonical remote using write token:
  `git clone -c http.extraHeader="Authorization: Bearer [REDACTED_TOKEN]" <canonical_remote> seed-git-repo`
- Secured repo configuration: `chmod 0600 .git/config`.
- Verified local cloned `HEAD` equals `seedCommit` (`5c6bc1c1f8244a2407e9a990775e0d54955d18d6`).
- Configured repo-local extraHeader `http.<canonical_remote>.extraHeader`.
- Executed exact lease push:
  `git push --force-with-lease=refs/heads/main:5c6bc1c1f8244a2407e9a990775e0d54955d18d6 <canonical_remote> HEAD:refs/heads/main`
- **Outcome**: Exited with code `0`, confirming exact lease validation on the remote repository.

---

## 4. SDK Integration: `create_task` & Fork Workflow

The Python SDK client (`AgentBranchesClient`) was loaded directly from the integration repository:

### Step 5: `create_task` Registration
- Initialized client:
  ```python
  client = AgentBranchesClient(
      server_url="http://127.0.0.1:9895",
      admin_token="$ADMIN_TOKEN"
  )
  task_res = client.create_task(
      task_id="task-smoke-01",
      repo="agent-branches-canonical-b7a8bef1",
      base_ref="main",
      base_sha="5c6bc1c1f8244a2407e9a990775e0d54955d18d6",
      intent="Primary coordinator smoke validation",
  )
  ```
- Coordinator response wire object:
  - `taskId`: `task-0001`
  - `agentId`: `agent-0001`
  - `fork.name`: `agent-branches-canonical-b7a8bef1-agent-0001`
  - `fork.remote`: `http://127.0.0.1:9894/git/agent-branches-canonical-b7a8bef1-agent-0001.git`
  - `token`: `{"scope": "write", "expiresAt": "...", "plaintext": "art_v1_[REDACTED]"}`
- **Assertion**: Coordinator successfully registered task, created isolated bare fork on the sidecar, and minted scoped per-task bearer credentials.

### Step 6: Smart HTTP Clone, Maintenance Commit, and Push
1. Cloned the task fork over Git Smart HTTP:
   ```bash
   git clone -c http.extraHeader="Authorization: Bearer [REDACTED_TOKEN]" \
     http://127.0.0.1:9894/git/agent-branches-canonical-b7a8bef1-agent-0001.git fork-clone
   ```
2. Authored maintenance commit:
   - File created: `SMOKE_MARKER.md` ("# Primary Coordinator Smoke Marker\nVerified bootstrap and fork workflow.\n")
   - Commit message: `docs(smoke): add primary bootstrap smoke marker`
   - Generated commit SHA: `5ed15be3b8f8c4cb68ed66d3826811a93b2a04ac`
3. Pushed commit to fork remote via Smart HTTP:
   ```bash
   git -c http.extraHeader="Authorization: Bearer [REDACTED_TOKEN]" push origin HEAD:refs/heads/main
   ```
   - **Exit code**: `0` (Success).
   - Sidecar post-receive hook forwarded event to Coordinator `POST /events/push`.
4. Registered push via Python SDK:
   ```python
   push_res = client.push(
       task_id="task-0001",
       commit="5ed15be3b8f8c4cb68ed66d3826811a93b2a04ac",
       token=task_token,
       files_changed=["SMOKE_MARKER.md"],
       intent="add primary bootstrap smoke marker",
   )
   ```
   - **Outcome**: `accepted: true` (or deduped).
5. Queried task status via SDK:
   ```python
   status_res = client.status(task_id="task-0001", token=task_token)
   ```
   - **Outcome**: Status verified; `taskId == "task-0001"`, `agentId == "agent-0001"`, and agent head points to `5ed15be3b8f8c4cb68ed66d3826811a93b2a04ac`.

---

## 5. Negative Security & Authorization Tests

### Negative Test 1: Unauthenticated SDK Push Mutation
- **Objective**: Verify that mutating push endpoints reject unauthenticated requests.
- **Action**: A fresh `AgentBranchesClient` instance holding no cached credentials and no `$ADMIN_TOKEN` called:
  ```python
  bare_client.push(
      task_id="task-0001",
      agent_id="agent-0001",
      head_sha="5ed15be3b8f8c4cb68ed66d3826811a93b2a04ac",
      token=None,
      admin_token=None,
  )
  ```
- **Outcome**: Raised `AgentBranchesAPIError: HTTP 401: bearer token required`.
- **Verdict**: **PASS (Fails Closed)**.

### Negative Test 2: Git Smart HTTP Push with Invalid Bearer
- **Objective**: Verify that sidecar rejects Git Smart HTTP push requests presenting an invalid or fabricated bearer token.
- **Action**: In `fork-clone`, configured `http.extraHeader = Authorization: Bearer [REDACTED_TOKEN]` (fabricated invalid token), created a test commit, set `GIT_TERMINAL_PROMPT=0` to prevent interactive credential hangs, and executed:
  ```bash
  git push origin HEAD:refs/heads/main
  ```
- **Outcome**:
  - Git output: `fatal: could not read Username for 'http://127.0.0.1:9894': terminal prompts disabled` (triggered by wire HTTP 401 `WWW-Authenticate: Basic realm="git"` challenge).
  - Exit code: `128`.
- **Verdict**: **PASS (Fails Closed)**.

---

## 6. Telemetry & Resource Measurements

| Measurement Metric | Observed Value | Hard Limit / Budget | Compliance Status |
| :--- | :--- | :--- | :--- |
| **Sidecar Port** | 9894 | Ephemeral loopback | Clean |
| **Coordinator Port** | 9895 | Ephemeral loopback | Clean |
| **Sidecar RSS Memory** | 59.42 MB | $\le$ 100.0 MB | PASS |
| **Coordinator RSS Memory** | 62.47 MB | $\le$ 100.0 MB | PASS |
| **Total Memory Overhead** | 121.89 MB | $\le$ 1500.0 MiB host slice | PASS |
| **Scratch Disk Usage** | 0.13 MB | $\le$ 512.0 MB | PASS |
| **`/tmp` Directory Growth** | 0 bytes | 0 bytes (`TMPDIR` isolated) | PASS |
| **Sidecar Exit Code** | `-15` (SIGTERM) | Clean shutdown | PASS |
| **Coordinator Exit Code** | `-15` (SIGTERM) | Clean shutdown | PASS |
| **Total Wall-Clock Time** | **0.764 seconds** | Sub-second | FAST |

### Latency Breakdown

| Phase | Duration (s) | Description |
| :--- | :--- | :--- |
| `daemon_startup_s` | 0.396 | Node process launches & HTTP port ready polling |
| `post_setup_initial_s` | 0.043 | Initial canonical repo setup, git init, and seed commit |
| `post_setup_idempotent_s` | 0.001 | Idempotent check returning `created: false` |
| `sidecar_mint_token_s` | 0.001 | Token minting on sidecar |
| `git_push_seed_lease_s` | 0.068 | Git clone and `--force-with-lease` verification |
| `sdk_workflow_s` | 0.218 | `create_task`, fork clone, commit, smart HTTP push, SDK push registration, status query, and negative auth checks |
| `teardown_s` | 0.014 | Graceful SIGTERM daemon termination |
| **Total Wall Clock** | **0.764** | Complete end-to-end execution |

---

## 7. Artifacts & Deliverables Generated

1. Test Execution Engine:
   - `.local/scratch/primary-coordinator-smoke/run_smoke.py`
2. Structured Telemetry Record:
   - `.local/scratch/primary-coordinator-smoke/smoke_summary.json`
3. Daemon Execution Logs:
   - `.local/scratch/primary-coordinator-smoke/sidecar.log`
   - `.local/scratch/primary-coordinator-smoke/coord.log`
4. Deliverable Receipt:
   - `research/antigravity/recovery/RECEIPT-PRIMARY-COORDINATOR-BOOTSTRAP-SMOKE.md` (this document)

---

## 8. Publication Guard & Security Verification

All logs, reports, and code were checked to ensure zero credential leakage:
- No raw tokens, private keys, or high-entropy bearer literals are included in this receipt.
- Tested and verified clean against `publication_guard.py`.
- No Git commit was performed from the subagent (in compliance with subagent operating rules; parent coordinator handles integration).
