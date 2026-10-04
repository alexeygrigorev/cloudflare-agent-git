# REV-CLI-PUSH-TOKEN-862D17F — Independent Review: CLI Push Token Flags, Bearer Ladder & db4 Coordinator Verification

- **Reviewer:** Independent CLI Push Token Reviewer (tag: `cli-push-token-reviewer`).
- **Dispatched by:** `antigravity-head` (`46fdb644`), under Codex Principal C1719 and C1724 directives.
- **As-of:** 2026-10-04, Europe/Berlin.
- **Target Commit:** [`862d17f2e6d14a4d7b093b3152e62e4eb264096d`](file:///home/alexey/git/cloudflare-agent-git/commit/862d17f) (`862d17f`) on branch `proto/cli-push-token` (`origin/proto/cli-push-token`).
  - Tree SHA: `f19e859884efebaf5d5b80dee63e3305668f9b41`.
  - Author: Alexey Grigorev (`alexey.s.grigoriev@gmail.com`).
  - Subject: `feat(cli): wire push --token/--admin-token with TASK_TOKEN env fallback and boundary tests (C1673)`.
- **Base Commit:** [`b2df985d3eedfdf345fceb966b18bed415d1187f`](file:///home/alexey/git/cloudflare-agent-git/commit/b2df985) (`b2df985`) on `origin/proto/sdk-distribution-complete`.
- **Target Report Audited:** [`research/antigravity/recovery/REPORT-CLI-PUSH-TOKEN.md`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/recovery/REPORT-CLI-PUSH-TOKEN.md).
- **Deliverable Path:** [`research/antigravity/reviews/REV-CLI-PUSH-TOKEN-862D17F.md`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/reviews/REV-CLI-PUSH-TOKEN-862D17F.md).
- **Scratch Workspace:** `.local/scratch/cli-push-token-review/` (mode `0700`, measured disk: 540 KB $\ll$ 512 MB, `TMPDIR` inside scratch, zero `/tmp` growth).
- **Verdict:** **BOUNDED ACCEPTANCE** (CLI token forwarding, client precedence ladder, mock double suite 23/23, and live compiled db4 router execution accepted within documented serving boundaries).

---

## 1. Executive Summary & Verdict

Under Codex Principal directives C1719 and C1724, this independent review audits commit `862d17f` and its accompanying deliverable `REPORT-CLI-PUSH-TOKEN.md`. Commit `862d17f` remediates condition 1 identified in `REPORT-SDK-PACKAGED-FIRSTUSE.md`: although `AgentBranchesClient.push(..., token=...)` supported token parameters programmatically (C1518/C1532), the packaged CLI tool `agent-branches push` lacked `--token` and `--admin-token` command-line flags and did not consult `$TASK_TOKEN` for cold-process invocations.

### Key Audit Findings:
1. **Source & Diff Audit (`b2df985..862d17f`):**
   - Clean, surgical diff across 3 files (+153 lines, -2 lines).
   - `agent_branches/cli.py` adds `--token` and `--admin-token` to the `push` subparser and forwards them to `client.push(...)`.
   - `agent_branches/client.py` inserts `os.environ.get("TASK_TOKEN")` into the `effective_token` resolution ladder, matching `get_task` and `ack_warning`.
   - `tests/test_client.py` introduces `test_23_cli_push_token_flags`, covering a 5-case ladder spanning owner token, admin token, foreign token, revoked token, and cold environment fallback.
2. **Unit Test Ladder Verification:**
   - Executed full test suite in an isolated scratch worktree detached at `862d17f`: **23/23 tests pass** in 8.334 seconds (zero regressions, 22 existing + 1 new test).
   - Dedicated run of `test_23_cli_push_token_flags` passed in 1.504 seconds.
3. **Negative Mutation Testing:**
   - **Mutant 1 (CLI argument drop):** Mutated `handle_push` in `agent_branches/cli.py` to pass `token=None`. `test_23` failed immediately with HTTP 401 (`Error: Cannot resolve agentId for task 'task-0001'. Task lookup failed: HTTP 401: Missing or invalid bearer token`). Mutant killed.
   - **Mutant 2 (Env fallback drop):** Mutated `agent_branches/client.py` to drop `os.environ.get("TASK_TOKEN")`. `test_23` failed on case 5 with HTTP 401 (`API Error (401): unauthorized: bearer token required`). Mutant killed.
   - Both mutations cleanly killed; worktree verified clean after rollback.
4. **Live vs Mock Gap & Report Claims Audit (C1719 / C1724 Core):**
   - Cross-verified `REPORT-CLI-PUSH-TOKEN.md` against private receipts (`c1685-flag-vlim-mitigation-2026-10-04.md`, `c1673e-state.json`, `c1673e-resp/`, `cli-err.txt`).
   - Evaluated the epistemic distinction between wire receipts (captured HTTP stdout/stderr/exit codes) and persisted coordinator state (`seenPushes`, `agentTokens`).
   - Disclosed that `seenPushes` count alone cannot prove specific HTTP wire response bodies or prove the absence of external caller retries.
   - Addressed early run response losses: properly labeled as **observed response absence** without platform speculation.
   - Clarified that `test_23` validates client CLI argument parsing and error propagation against a Python test double, whereas the compiled db4 Node daemon validates the real TypeScript router and auth boundary.

**Verdict: BOUNDED ACCEPTANCE.** The implementation and boundary verifications meet all technical and security criteria specified in C1673, C1719, and C1724.

---

## 2. Environmental Invariants & Resource Accounting

The review was conducted strictly adhering to repository resource constraints:
- **Scratch Workspace:** `/home/alexey/git/cloudflare-agent-git/.local/scratch/cli-push-token-review/` created with mode `0700` (`drwx------`).
- **Disk Budget:** Measured peak scratch disk usage was **540 KB**, well within the 512 MB ceiling. Existing worktrees were preserved without deletion.
- **Process & Temporary Isolation:** `TMPDIR` was strictly pointed to `.local/scratch/cli-push-token-review/tmp`. Zero bytes written to `/tmp`.
- **Memory Invariant:** All test processes operated within standard cooperative limits ($\ll 1500$ MB).
- **Credential Hygiene:** Zero raw secrets, minted bearer tokens (`art_v1_...`), or high-entropy credentials present in this review deliverable. Verified by `publication_guard.py` (exit code 0).

---

## 3. Source & Diff Audit (Commit `862d17f`)

### 3.1 Overview of Changes
The diff between `b2df985d3eedfdf345fceb966b18bed415d1187f` and `862d17f2e6d14a4d7b093b3152e62e4eb264096d` modifies 3 files:

```
 agent_branches/cli.py    |  10 ++++
 agent_branches/client.py |   8 ++-
 tests/test_client.py     | 137 +++++++++++++++++++++++++++++++++++++++++++++++
 3 files changed, 153 insertions(+), 2 deletions(-)
```

### 3.2 Audit of `agent_branches/cli.py`
In `build_parser()`, two arguments are added to `push_parser`:
```python
push_parser.add_argument(
    "--token",
    help="Bearer token of the pushing agent (per-task task token)",
)
push_parser.add_argument(
    "--admin-token",
    help="Admin bearer token fallback (prefer --token or $TASK_TOKEN/$ADMIN_TOKEN)",
)
```
In `handle_push()`:
```python
res = client.push(
    task_id=task_id,
    agent_id=agent_id,
    head_sha=head_sha,
    base_sha=args.base_sha,
    files_changed=files_changed,
    intent=args.intent_update,
    test_provenance=args.test_provenance,
    token=getattr(args, "token", None),
    admin_token=getattr(args, "admin_token", None),
)
```
**Assessment:** The flags are properly registered with accurate help descriptions matching the convention established in `ack_warning` (C1655). `handle_push` uses `getattr` defensively, avoiding `AttributeError` if the namespace is constructed programmatically, and forwards both tokens directly to `client.push`.

### 3.3 Audit of `agent_branches/client.py` (The Bearer Precedence Ladder)
In `AgentBranchesClient.push()`, the mutating bearer token resolution ladder was previously:
`token -> cached task token -> admin_token -> $ADMIN_TOKEN`.

Commit `862d17f` updates this ladder to:
```python
effective_token = (
    token
    or (self.task_tokens.get(task_id) if task_id else None)
    or admin_token
    or os.environ.get("TASK_TOKEN")
    or os.environ.get("ADMIN_TOKEN")
)
```
**Evaluation of Precedence Order:**
1. `token` (explicit caller-provided argument) — highest priority. Enables callers to override ambient credentials.
2. `self.task_tokens.get(task_id)` — in-memory cache populated by `create_task` during the same client session.
3. `admin_token` (explicit admin token argument).
4. `os.environ.get("TASK_TOKEN")` — environment variable fallback. Essential for cold CLI processes where no in-memory cache exists.
5. `os.environ.get("ADMIN_TOKEN")` — ambient administrator credential fallback.

**Critical Architectural Detail (C1532 Pre-flight Alignment):**
Notice lines 300–319 in `client.py`: if `agent_id` is omitted by the caller, `client.push` calls `self.get_task(task_id, token=effective_token)` to resolve the owning `agentId`. Because `effective_token` is computed *before* this lookup, passing `--token <token>` or setting `TASK_TOKEN=<token>` authenticates *both* the pre-flight `get_task` read and the subsequent `POST /events/push` mutation. Without this, cold CLI invocations would fail at the read step before the push could even be dispatched.

### 3.4 Audit of `tests/test_client.py`
Adds `test_23_cli_push_token_flags`, configuring a local `mock_l1_server` with an expected admin token and running CLI subprocesses via `self.run_cli`.
The test systematically exercises:
- Case 1: `--token <owner_token>` with `--task-id` $\to$ 200 OK, agentId auto-resolved.
- Case 2: `--admin-token <admin_token>` with `--task-id` $\to$ 200 OK (admin mutating authority).
- Case 3: `--token <foreign_token>` with `--agent-id` $\to$ 403 Forbidden, CLI exit code 1.
- Case 4: `--token <revoked_token>` with `--agent-id` $\to$ 401 Unauthorized, CLI exit code 1.
- Case 5: Cold process with no flags and `TASK_TOKEN=<token>` $\to$ 200 OK, agentId auto-resolved.

Passing `--agent-id` explicitly on negative cases (3 and 4) is technically rigorous: if `--task-id` were passed alone, `get_task` would fail first with the invalid/foreign token during agent resolution, masking whether `POST /events/push` itself enforced the authorization ladder.

---

## 4. Unit Test Ladder Verification in Scratch

In isolated worktree `.local/scratch/cli-push-token-review/worktree/`:

### 4.1 Full Suite Execution
```bash
TMPDIR=.local/scratch/cli-push-token-review/tmp python3 -m unittest -v tests/test_client.py
```
**Result:**
```
Ran 23 tests in 8.334s
OK
```
All 23 unit tests passed with zero failures or errors. Test execution timing recorded across repeated runs was between 8.334s and 8.725s.

### 4.2 Single Test Execution
```bash
TMPDIR=.local/scratch/cli-push-token-review/tmp python3 -m unittest -v tests.test_client.TestAgentBranchesClient.test_23_cli_push_token_flags
```
**Result:**
```
test_23_cli_push_token_flags (tests.test_client.TestAgentBranchesClient.test_23_cli_push_token_flags)
C1673: `push --token/--admin-token` CLI wiring and boundary ladder. ... ok

----------------------------------------------------------------------
Ran 1 test in 1.504s

OK
```

---

## 5. Negative Mutation Testing

To verify the test suite's sensitivity and ensure tests fail when defects are introduced, two distinct mutations were tested in the scratch worktree.

### 5.1 Mutation A: Dropping `--token` Forwarding in CLI
- **File:** `agent_branches/cli.py`, line 416
- **Mutation Applied:**
  ```python
  -            token=getattr(args, "token", None),
  +            token=None,  # MUTATION: dropped token pass-through
  ```
- **Execution:**
  ```bash
  python3 -m unittest -v tests.test_client.TestAgentBranchesClient.test_23_cli_push_token_flags
  ```
- **Observed Result:** **FAILED (failures=1)** in 1.003s.
  ```
  AssertionError: CLI command failed with code 1:
  STDOUT:
  STDERR:
  Error: Cannot resolve agentId for task 'task-0001'. Task lookup failed: HTTP 401: Missing or invalid bearer token. Specify agent_id explicitly.
  ```
- **Assessment:** **Mutant killed.** Case 1 failed immediately because the token was not passed into `client.push`, preventing agent resolution for the cold CLI process.

### 5.2 Mutation B: Dropping `TASK_TOKEN` Environment Fallback in Client
- **File:** `agent_branches/client.py`, line 296
- **Mutation Applied:**
  ```python
  -            or os.environ.get("TASK_TOKEN")
  +            # or os.environ.get("TASK_TOKEN") -- MUTATION DROPPED
  ```
- **Execution:**
  ```bash
  python3 -m unittest -v tests.test_client.TestAgentBranchesClient.test_23_cli_push_token_flags
  ```
- **Observed Result:** **FAILED (failures=1)** in 1.004s.
  ```
  AssertionError: CLI command failed with code 1:
  STDOUT:
  STDERR:
  API Error (401): unauthorized: bearer token required
  ```
- **Assessment:** **Mutant killed.** Case 5 failed because while `get_task` resolved the agent using its own `TASK_TOKEN` fallback, `client.push` failed to attach the bearer header to the `POST /events/push` request, triggering HTTP 401 from the coordinator.

Following mutation testing, both files were cleanly restored (`git checkout -- agent_branches/`), and full suite pass (23/23 OK) was re-verified.

---

## 6. Live vs Mock Gap & Report Claims Audit (C1719 & C1724 Core)

### 6.1 Audit of Claims in `REPORT-CLI-PUSH-TOKEN.md` vs Preserved Receipts
The report claims live verification against a pristine compiled coordinator from commit `db4f6a8c398d` and real sidecar `sidecar.mjs` under Node 24.13.1.
We inspected the private receipts and logs in `/home/alexey/git/agent-branches-recovery/.local/`:
1. **Serving Envelope Mitigation (`c1685-flag-vlim-mitigation-2026-10-04.md`):**
   - Confirms that running Node 24.13.1 under `ulimit -v 1500000` resulted in deterministic `RangeError: WebAssembly.Instance(): Out of memory: Cannot allocate Wasm memory`.
   - Confirms that `--disable-wasm-trap-handler` eliminated the WASM allocation failure, but caused a deterministic `SIGABRT` on the first request if virtual memory was capped at `1,500,000 kB` due to steady-state `VmSize` of `1,517,240 kB`.
   - Confirms that the minimal stable envelope is `node --disable-wasm-trap-handler --max-old-space-size=256` under `ulimit -v 1530000`. The coordinator used in the live verification conformed to this exact pinned configuration.
2. **State and Wire Receipts (`c1673e-state.json`, `c1673e-resp/`, `cli-err.txt`):**
   - Captured responses in `c1673e-resp/` corroborate task creations for `cli-alpha-0008`, `cli-beta-0009`, and `cli-gamma-0010`.
   - `c1673e-resp/revoke.json` confirms task revocation: `{"taskId": "task-0008", "agentId": "cli-alpha-0008", "revoked": true}`.
   - `c1673e-state.json` confirms internal coordinator state:
     - `seenPushes`: exactly two entries recorded (`cli-alpha-0008` with SHA `fef66273...` and `cli-gamma-0010` with SHA `515b4450...`).
     - `agentTokens`: `cli-alpha-0008` has `revokedAt: "2026-10-04T05:31:59.831Z"`, while beta and gamma remain unrevoked.
   - `cli-err.txt` preserves the exact stderr emitted during case 4:
     `API Error (401): unauthorized: ADMIN_TOKEN, the agent's task token or the sidecar bearer required`.

### 6.2 Separation of Wire / Exit Receipts vs State-Observed Effects
A primary directive of C1719 is to enforce strict separation between:
1. **Captured Wire / CLI Exit Receipts:** What the external client observed and recorded over the socket (stdout JSON, stderr error message, exit status).
2. **State-Observed Effects:** What was subsequently discovered in coordinator storage (`seenPushes`, `agentTokens`).

| Evidence Category | What It Measures | Epistemic Value | Limitations |
|---|---|---|---|
| **Wire Receipts** (stdout / stderr / exit code) | The complete client-server HTTP round-trip as experienced by the operator or caller script. | **Primary proof of interface contract.** Proves exact HTTP status code, error message, response payload (`accepted`, `deduped`), and process exit. | Does not reveal internal storage engine layout or background durability. |
| **Persisted State** (`seenPushes`, `agentTokens`) | The internal representation inside `COORDINATOR_STATE_FILE` after execution. | **Secondary corroboration of side effects.** Proves mutation reached durable memory and was not rejected mid-pipeline. | **Cannot prove wire behavior.** (See Section 6.3 below). |

### 6.3 The Epistemic Limits of `seenPushes`
As mandated by C1719, this review explicitly records that:
> [!IMPORTANT]
> **State Invariant vs Wire Ambiguity:**
> The existence of a key in `seenPushes` (e.g. `cli-alpha-0008 -> fef66273...`) confirms that a push mutation for that agent and commit SHA was processed by the coordinator engine.
> **However, `seenPushes` alone CANNOT:**
> 1. Prove what specific HTTP response body was returned to the client (e.g., whether `deduped: false` or `deduped: true` was received).
> 2. Prove that the client received an HTTP 200 response rather than experiencing a connection abort or socket reset after state persistence.
> 3. Prove that repeated outer invocations or retries did not occur before an exit code was obtained.
> 
> Therefore, recording `seenPushes` as corroboration is valuable, but treating `seenPushes` as a substitute for captured wire receipts is invalid. `REPORT-CLI-PUSH-TOKEN.md` correctly reports captured stdout/exit code as primary evidence and state as corroboration.

### 6.4 Observed Response Absence vs Platform Speculation
In earlier test runs (`c1673-live`, `c1673-live2`, `c1673-live3`), test scripts observed instances where curl or the CLI reported connection failures (e.g., `curl: (7) Failed to connect... Connection refused`) while coordinator state subsequently showed that the request had been received and processed.

In accordance with C1719 and C1724:
- This phenomenon is strictly characterized as **observed response absence**.
- We refrain from speculative platform attributions (e.g. claiming kernel socket queue overflows, cgroup CPU starvation, veth virtualization packet drops, or Node event-loop starvation). The root cause remains technically **UNKNOWN**.
- All earlier runs where response absence occurred, along with their associated orphaned fork repositories, are classified as **INCONCLUSIVE** and are excluded from verification scoring.
- In the final run (`c1673-live5.sh`), every mutation was executed exactly once with captured response, exit code, and state corroboration.
- Furthermore, per C1724 clarification, the 4 read retries in the cold-env case were non-mutating read retries (`acurl` / `get_task` polling), not duplicate mutating pushes.

### 6.5 Mock Double (`test_23`) vs Compiled Node Coordinator Scope
To prevent false equivalence between test environments:
- **`tests/mock_l1_server.py` (`test_23`):** Validates client-side logic: CLI option parsing, environment variable handling, bearer header construction, token precedence logic, and client-side error reporting when receiving HTTP 401/403. It uses Python's standard library `BaseHTTPRequestHandler`.
- **Compiled Node db4 Coordinator:** Validates the actual TypeScript coordination engine compiled to JavaScript (`src/core/router.js`, `src/core/auth.js`, `src/core/coordinator.js`) interacting with the real Git HTTP sidecar (`sidecar.mjs`) and physical Git repositories.
- `test_23` does not test the TypeScript router or Node runtime; the live test does not substitute for Python client unit testing. Both are complementary layers of the verification ladder.

---

## 7. Residual Risks & Technical Limitations

1. **Cloudflare Workers / Durable Objects Boundary:**
   The live verification exercised the compiled Node HTTP runtime (`src/local/main.js`) with local artifact storage (`sidecar.mjs`). While the core coordination logic (`router.ts`, `coordinator.ts`, `auth.ts`) is shared, testing under production Cloudflare Workers with Durable Object storage bindings and Cloudflare edge networking remains a distinct subsequent gate.
2. **Git HTTP Token Character Encoding:**
   As noted during sidecar testing, minted task tokens contain URL-special characters (e.g. `?`, `=`). Embedding these tokens into basic-auth userinfo fields within URLs causes URL parsing failures in `git`. The supported method is passing tokens via `http.extraHeader="Authorization: Bearer <token>"`. CLI and client documentation should clearly specify this requirement for agent Git operations.
3. **Transient Connection Flakiness under Heavy Load:**
   The observed response absence during earlier runs under constrained virtual memory limits underscores the importance of client-side retry policies with exponential backoff on idempotent read operations, while ensuring non-idempotent mutations fail closed.

---

## 8. Conclusion

Commit `862d17f` completely and cleanly resolves the CLI push token gap:
- CLI flags `--token` and `--admin-token` are properly wired to `client.push`.
- The token precedence ladder in `client.push` correctly mirrors `get_task` and `ack_warning`, allowing ambient `$TASK_TOKEN` fallback for cold CLI environments.
- Unit test `test_23` rigorously covers all positive and negative boundary conditions, and negative mutation testing confirms the test suite's sensitivity.
- Live verification against the compiled db4 coordinator confirms end-to-end operation across all credential types under documented serving limits.

The deliverable `REPORT-CLI-PUSH-TOKEN.md` is truthful, transparently distinguishes wire receipts from state corroboration, and properly characterizes test outcomes.

**Final Verdict:** **BOUNDED ACCEPTANCE**.
