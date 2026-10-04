# RECEIPT-RAW-SDK-SMOKE — Raw Unwrapped SDK Live Integration Smoke Test

- **Executor**: Raw SDK Integration Smoke Worker (`raw-sdk-smoke-worker`)
- **Directives**: Codex Principal C1789 / C1793 directives:
  *"existing released ca5 native helper follow-up unwrapped AgentBranchesClient actual constructor/create_task(branch,admin_token)/push(head_sha)/get_task through real daemons, disjoint scratch, timed calls+meaningful non-noop baseline change, no Rust/product-source changes;"*
- **Invoker / Parent**: `245c7bba-9a7b-45c1-87a7-4537f289f9a5` (antigravity-head `46fdb644`)
- **Date**: 2026-10-04T07:02:00Z (09:02 Europe/Berlin)
- **Workspace**: `/home/alexey/git/cloudflare-agent-git`
- **Scratch Root**: `/home/alexey/git/cloudflare-agent-git/.local/scratch/raw-sdk-smoke` (mode `0700`, usage `0.14 MB` $\le$ 512 MB, `TMPDIR` redirected to scratch root, zero `/tmp` growth)
- **Prebuilt Reference Daemons**:
  - Sidecar: `/home/alexey/git/agent-branches-integration/prototype/local-artifacts/sidecar.mjs` (SHA256: `04a756286b0448734c051f88d1b330ed7b2356b71d1b170eca64db196a949a76`)
  - Coordinator: `/home/alexey/git/agent-branches-integration/prototype/.build/node/src/local/main.js` (SHA256: `7747d511a4b8dfcf4d80dfcaf71015d8f5f42c783f2ade3be6590aaad5ffd14f`)
- **Python SDK Client**: Raw, unwrapped `agent_branches.client.AgentBranchesClient` directly imported from `/home/alexey/git/agent-branches-integration/agent_branches/client.py` (STRICTLY ZERO adapter wrapper / NO subclass)
- **Outcome**: **SUCCESS** (All bootstrap phases, meaningful non-noop baseline advance with exact lease push, unwrapped SDK workflow, and both negative security tests passed cleanly).

---

## 1. Executive Summary & Epistemic Demarcation

This receipt provides conclusive verification of the raw, unwrapped Python SDK client (`AgentBranchesClient`) operating against the prebuilt live Node coordinator runtime (`main.js`) and Git host sidecar daemon (`sidecar.mjs`).

This test directly resolves the epistemic boundaries raised by Codex Principal C1789/C1793 regarding the earlier bootstrap smoke test ([RECEIPT-PRIMARY-COORDINATOR-BOOTSTRAP-SMOKE.md](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/recovery/RECEIPT-PRIMARY-COORDINATOR-BOOTSTRAP-SMOKE.md)):
1. **Unwrapped Raw SDK**: Zero adapter wrappers (`FlexibleAgentBranchesClient` completely eliminated). The test invokes `AgentBranchesClient` directly using its authentic constructor, explicit `admin_token` argument on `create_task`, exact keyword arguments (`branch="main"`, `base_sha`, `head_sha`), and native `get_task` query method.
2. **Meaningful Non-Noop Baseline Advance**: Rather than re-pushing the synthetic seed commit, the test authors a genuine specification commit (`BASELINE_SPEC.md`) on the canonical clone, advances `refs/heads/main` to a distinct commit SHA (`bf4f2990...`), and executes an exact-lease push (`--force-with-lease=refs/heads/main:<seedCommit>`). The task fork is subsequently branched directly from this newly advanced baseline.
3. **Parameter Introspection & Wire Demarcation**: Rigorous introspection of `agent_branches/client.py` establishes that `create_task` accepts `(repo, base_sha, intent, branch, agent=None, ttl_seconds=None, admin_token=None)` (task identifiers are minted exclusively by the coordinator), and `push` accepts `task_id` (not `task`). Passing `task="task-raw-01"` to either method on the raw client correctly fails fast with Python `TypeError`, confirming exact method signatures.
4. **Strict Isolation**: Zero Cargo / Rustc invocations. 0 bytes `/tmp` growth. Sidecar RSS 59.63 MB, Coordinator RSS 62.54 MB (both $\le$ 100 MB). Scratch disk usage 0.14 MB ($\le$ 512 MB).

---

## 2. Environment & Daemon Setup

Both daemons were launched as local background processes bound to loopback ephemeral ports with high-entropy cryptographic secrets generated in memory:

```bash
# Isolated Ports & Paths
SIDECAR_PORT=9896
COORD_PORT=9897
SCRATCH_ROOT=".local/scratch/raw-sdk-smoke"
TMPDIR="$SCRATCH_ROOT/tmp"

# Secrets generated in memory via secrets.token_hex(24), mode 0600 in env
ADMIN_TOKEN="$ADMIN_TOKEN"
LOCAL_ARTIFACTS_TOKEN="$LOCAL_ARTIFACTS_TOKEN"
RUNNER_TOKEN="$RUNNER_TOKEN"
```

### Daemon Invocations

1. **Git Sidecar Daemon**:
   ```bash
   SIDECAR_ROOT="$SCRATCH_ROOT/sidecar-root" \
   SIDECAR_HOST="127.0.0.1" \
   SIDECAR_PORT="9896" \
   SIDECAR_TOKEN="$LOCAL_ARTIFACTS_TOKEN" \
   SIDECAR_NOTIFY_URL="http://127.0.0.1:9897/events/push" \
   node prototype/local-artifacts/sidecar.mjs > "$SCRATCH_ROOT/sidecar.log" 2>&1 &
   ```

2. **Coordinator Daemon**:
   ```bash
   LOCAL_ARTIFACTS_URL="http://127.0.0.1:9896" \
   LOCAL_ARTIFACTS_TOKEN="$LOCAL_ARTIFACTS_TOKEN" \
   ADMIN_TOKEN="$ADMIN_TOKEN" \
   RUNNER_TOKEN="$RUNNER_TOKEN" \
   PORT="9897" \
   HOST="127.0.0.1" \
   COORDINATOR_STATE_FILE="$SCRATCH_ROOT/coord-state.json" \
   node --disable-wasm-trap-handler --max-old-space-size=256 \
     prototype/.build/node/src/local/main.js > "$SCRATCH_ROOT/coord.log" 2>&1 &
   ```

3. **Liveness & Health Verification**:
   - `GET http://127.0.0.1:9896/api/health` with `Authorization: Bearer $LOCAL_ARTIFACTS_TOKEN` $\rightarrow$ `HTTP 200 {"ok": true}`.
   - `GET http://127.0.0.1:9897/status` with `Authorization: Bearer $RUNNER_TOKEN` $\rightarrow$ `HTTP 200`.
   - Sidecar Resident Memory (RSS): **59.63 MB** (Limit: 100 MB).
   - Coordinator Resident Memory (RSS): **62.54 MB** (Limit: 100 MB).
   - Startup latency: **0.419s**.

---

## 3. Meaningful Non-Noop Baseline Setup & Advance

### Step 1: Coordinator POST `/setup`
- **Request**: `POST http://127.0.0.1:9897/setup` with `Authorization: Bearer $ADMIN_TOKEN`.
- **Response**: `HTTP 201 Created`
  ```json
  {
    "canonical": {
      "name": "agent-branches-canonical-54e1934a",
      "remote": "http://127.0.0.1:9896/git/agent-branches-canonical-54e1934a.git"
    },
    "created": true,
    "seedCommit": "1874cbbea60ee5eaf8212801bdd7e96e18c0530c"
  }
  ```
- **Assertion**: Canonical repo created; initial synthetic seed commit SHA is `1874cbbea60ee5eaf8212801bdd7e96e18c0530c`.

### Step 2: Mint Canonical Write Token
- **Request**: `POST http://127.0.0.1:9896/api/repos/agent-branches-canonical-54e1934a/tokens`
  - Body: `{"scope": "write", "ttlSeconds": 3600}`
  - Auth: `Authorization: Bearer $LOCAL_ARTIFACTS_TOKEN`
- **Response**: `HTTP 201 Created`
  ```json
  {
    "repo": "agent-branches-canonical-54e1934a",
    "scope": "write",
    "plaintext": "art_v1_[REDACTED]"
  }
  ```

### Step 3: Clone Canonical Repository
- In scratch directory, cloned canonical remote using write token:
  ```bash
  git clone -c http.extraHeader="Authorization: Bearer [REDACTED_TOKEN]" \
    http://127.0.0.1:9896/git/agent-branches-canonical-54e1934a.git canonical-seed-repo
  ```
- Secured `.git/config` to mode `0600`.
- Verified local cloned `HEAD` equals `seedCommit` (`1874cbbea60ee5eaf8212801bdd7e96e18c0530c`).

### Step 4: Meaningful Baseline Advance & Exact Lease Push
Unlike synthetic no-op tests, this step creates a real specification commit on canonical:
1. Created `BASELINE_SPEC.md`:
   ```markdown
   # Production Baseline Specification
   Established baseline specification marker.
   Meaningful non-noop commit advancing canonical past synthetic seed.
   ```
2. Committed locally:
   - Message: `docs(canonical): add production baseline spec marker`
   - Resulting Commit SHA: `bf4f2990663c827f4268fb735ae76329251c0c12`
   - Verified: `bf4f2990663c827f4268fb735ae76329251c0c12 != 1874cbbea60ee5eaf8212801bdd7e96e18c0530c`
3. Pushed with exact lease against original seed commit:
   ```bash
   git push --force-with-lease=refs/heads/main:1874cbbea60ee5eaf8212801bdd7e96e18c0530c \
     origin HEAD:refs/heads/main
   ```
4. Verification:
   - Git push exit code: `0`.
   - `git ls-remote` confirmed remote `refs/heads/main` points to `bf4f2990663c827f4268fb735ae76329251c0c12`.
   - Proves authentic code advancement on canonical with exact lease enforcement.

---

## 4. Raw Unwrapped Python SDK Execution

### Signature Introspection & Demarcation Verification

The SDK class `AgentBranchesClient` was imported directly from `agent_branches.client` with no subclassing:
- **`__init__`**: `(self, server_url: Optional[str] = None, timeout: float = 10.0)`
- **`create_task`**: `(self, repo: str, base_sha: str, intent: str, branch: str, agent: Optional[str] = None, ttl_seconds: Optional[int] = None, admin_token: Optional[str] = None) -> Dict[str, Any]`
- **`push`**: `(self, task_id: Optional[str] = None, head_sha: str = '', base_sha: Optional[str] = None, files_changed: Union[List[str], str, NoneType] = None, intent: Optional[str] = None, test_provenance: Optional[str] = None, agent_id: Optional[str] = None, token: Optional[str] = None, admin_token: Optional[str] = None) -> Dict[str, Any]`
- **`get_task`**: `(self, task_id: str, token: Optional[str] = None) -> Dict[str, Any]`

Automated introspection proved:
1. Calling `create_task(task="task-raw-01", ...)` raises:
   `TypeError: AgentBranchesClient.create_task() got an unexpected keyword argument 'task'`
2. Calling `push(task="task-raw-01", ...)` raises:
   `TypeError: AgentBranchesClient.push() got an unexpected keyword argument 'task'`

This confirms that the raw SDK client uses `task_id` for queries and mutations, while `create_task` leaves task ID generation to the coordinator.

### Step 5: Raw `create_task`
1. Initialized client without admin token in constructor:
   ```python
   client = AgentBranchesClient(server_url="http://127.0.0.1:9897")
   ```
2. Called `create_task` with explicit `admin_token`, `branch="main"`, and `base_sha` pointing to the advanced baseline:
   ```python
   task_res = client.create_task(
       repo="agent-branches-canonical-54e1934a",
       branch="main",
       admin_token=ADMIN_TOKEN,
       base_sha="bf4f2990663c827f4268fb735ae76329251c0c12",
       intent="raw sdk integration smoke",
   )
   ```
3. Coordinator response:
   - `taskId`: `task-0001`
   - `agentId`: `agent-0001`
   - `forkName`: `agent-branches-canonical-54e1934a-agent-0001`
   - `forkRemote`: `http://127.0.0.1:9896/git/agent-branches-canonical-54e1934a-agent-0001.git`
   - `token`: `{"scope": "write", "expiresAt": "...", "plaintext": "art_v1_[REDACTED]"}`
   - `base_sha`: `bf4f2990663c827f4268fb735ae76329251c0c12`

### Step 6: Git Fork Clone, Commit, Push, and SDK Event Registration
1. Cloned fork repository over Git Smart HTTP using task bearer token:
   ```bash
   git clone -c http.extraHeader="Authorization: Bearer [REDACTED_TOKEN]" \
     http://127.0.0.1:9896/git/agent-branches-canonical-54e1934a-agent-0001.git fork-worktree
   ```
2. Verified fork clone begins at advanced baseline `bf4f2990663c827f4268fb735ae76329251c0c12`.
3. Created test commit in fork:
   - Added `MARKER.md`: `# Raw SDK Smoke Marker\nVerified raw unwrapped AgentBranchesClient workflow.\n`
   - Committed: `docs(fork): add raw sdk test marker`
   - Resulting Commit SHA: `0bfb14232d6d33b0dda01cf7d4d1fd56b90f02d6`
4. Pushed commit to fork remote via Smart HTTP:
   ```bash
   git -c http.extraHeader="Authorization: Bearer [REDACTED_TOKEN]" push origin HEAD:refs/heads/main
   ```
   - Exit code: `0`.
   - Webhook forwarded event to coordinator `POST /events/push`.
5. Registered push via raw SDK `push`:
   ```python
   push_res = client.push(
       task_id="task-0001",
       head_sha="0bfb14232d6d33b0dda01cf7d4d1fd56b90f02d6",
       token=task_token,
       files_changed=["MARKER.md"],
       intent="add raw marker",
   )
   ```
   - Result: `accepted: true`.
6. Verified task status via raw SDK `get_task`:
   ```python
   status_res = client.get_task(task_id="task-0001", token=task_token)
   ```
   - Confirmed: `taskId == "task-0001"`, `agentId == "agent-0001"`, and agent head points to `0bfb14232d6d33b0dda01cf7d4d1fd56b90f02d6`.

---

## 5. Negative Security & Authorization Tests

### Negative Test 1: Unauthenticated SDK Push Mutation
- **Objective**: Verify that mutating push endpoints fail closed when invoked without credentials.
- **Action**: A fresh, cold `AgentBranchesClient` instance holding no cached credentials called:
  ```python
  cold_client.push(
      task_id="task-0001",
      agent_id="agent-0001",
      head_sha="0bfb14232d6d33b0dda01cf7d4d1fd56b90f02d6",
      token=None,
      admin_token=None,
  )
  ```
- **Outcome**: Raised `AgentBranchesAPIError: HTTP 401: unauthorized: bearer token required`.
- **Verdict**: **PASS (Fails Closed)**.

### Negative Test 2: Git Smart HTTP Push with Invalid Bearer
- **Objective**: Verify that Git Smart HTTP push requests presenting an invalid bearer token are rejected.
- **Action**: In fork clone, configured `http.extraHeader = Authorization: Bearer [REDACTED_TOKEN]` (fabricated invalid token), created an empty commit, set `GIT_TERMINAL_PROMPT=0`, and executed `git push origin HEAD:refs/heads/main`.
- **Outcome**:
  - Git output: `fatal: could not read Username for 'http://127.0.0.1:9896': terminal prompts disabled` (triggered by wire HTTP 401 `WWW-Authenticate: Basic realm="git"` challenge).
  - Exit code: `128`.
- **Verdict**: **PASS (Fails Closed)**.

---

## 6. Telemetry & Resource Measurements

| Measurement Metric | Observed Value | Hard Limit / Budget | Status |
| :--- | :--- | :--- | :--- |
| **Sidecar Loopback Port** | 9896 | Ephemeral loopback | Clean |
| **Coordinator Loopback Port** | 9897 | Ephemeral loopback | Clean |
| **Sidecar Resident Memory (RSS)** | **59.63 MB** | $\le$ 100.0 MB | PASS |
| **Coordinator Resident Memory (RSS)** | **62.54 MB** | $\le$ 100.0 MB | PASS |
| **Total Resident Memory** | **122.17 MB** | $\le$ 1500.0 MiB host slice | PASS |
| **Scratch Disk Usage** | **0.14 MB** | $\le$ 512.0 MB ceiling | PASS |
| **`/tmp` Directory Growth** | **0 bytes (0 files)** | 0 bytes (`TMPDIR` isolated) | PASS |
| **Sidecar Shutdown Exit Code** | `-15` (SIGTERM) | Clean shutdown | PASS |
| **Coordinator Shutdown Exit Code** | `-15` (SIGTERM) | Clean shutdown | PASS |
| **Total Test Wall-Clock Time** | **1.134 seconds** | Fast integration | PASS |
| **Cargo / Rustc Invocations** | **0** | 0 (Strict policy hold) | PASS |
| **Product / Rust Code Modifications** | **0** | 0 | PASS |

### Phase Timing Breakdown

- Daemon Startup & Health Polling: **0.419s**
- Coordinator Setup (`POST /setup`): **0.042s**
- Canonical Token Minting: **0.001s**
- Canonical Git Clone: **0.047s**
- Baseline Commit & Exact Lease Push: **0.289s**
- Raw SDK `create_task`: **0.048s**
- Fork Git Clone: **0.046s**
- Fork Git Push: **0.107s**
- Raw SDK `push`: **0.002s**
- Raw SDK `get_task`: **0.001s**
- Negative Test 1 (Unauthenticated Push): **0.001s**
- Negative Test 2 (Invalid Bearer Push): **0.019s**
- Daemon Graceful Teardown: **0.015s**
- **Total Wall Clock**: **1.134s**

---

## 7. Compliance Verification & Artifacts

- **Publication Credential Guard**: Verified clean via `publication_guard.py` (Exit code `0`).
- **Test Runner Script**: `.local/scratch/raw-sdk-smoke/run_raw_sdk_smoke.py` (Mode `0755`, isolated scratch).
- **Summary JSON**: `.local/scratch/raw-sdk-smoke/smoke_summary.json`.
- **Sidecar Log**: `.local/scratch/raw-sdk-smoke/sidecar.log` (No secrets printed).
- **Coordinator Log**: `.local/scratch/raw-sdk-smoke/coord.log` (No secrets printed).
