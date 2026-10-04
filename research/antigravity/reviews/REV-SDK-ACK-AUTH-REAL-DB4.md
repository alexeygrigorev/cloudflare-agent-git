# REV-SDK-ACK-AUTH-REAL-DB4 — Independent Security & Boundary Verification: Remediated SDK ack_warning against Compiled db4 Node Coordinator

- **Reviewer:** Independent SDK ACK-Auth Reviewer (tag: `sdk-ack-auth-reviewer`, conversation ID `18d07577-9e17-4ab8-a68c-c811b8f4859c`).
- **Dispatched by:** `antigravity-head` (`46fdb644`), re-engaged under Codex Principal C1671 directive:
  *"ReviewerAnt authored b2note fix => re-engage independent18d or other distinct reviewer to inspect exactb2/27a and rerun meaningful Node auth+note/CLI regressions. No own head patch selfreview as finalindependent signoff."*
- **As-of:** 2026-10-04, Europe/Berlin.
- **Target SDK Commits on `origin/proto/sdk-distribution-complete`:**
  - `27a86fea3bbf57e5b8dad4101dd918d1170c6385` (*"fix(sdk): ack_warning sends bearer auth and agent body per proto contract (C1655)"*, author: `4abc725c`)
  - `b2df985d3eedfdf345fceb966b18bed415d1187f` (*"fix(sdk): map action to note in ack_warning payload for db4 router contract (C1669)"*, author: Alexey Grigorev)
- **Target Coordinator Runtime:**
  - Pinned commit: `db4f6a8c398d69f0e19072c41cb4b453b7dd1b71` (`proto/integration-auth-matrix`)
  - Compiled Node build: `/home/alexey/git/agent-branches-integration/prototype/.build/node/`
  - Modules exercised: `src/core/router.js`, `src/core/coordinator.js`, `src/core/auth.js`, `src/local/runtime.js`, `test/node/fakes.js`
- **Test Double Reference:** `tests/mock_l1_server.py` on `proto/sdk-distribution-complete` @ commit [`b2df985d3eedfdf345fceb966b18bed415d1187f`](file:///home/alexey/git/agent-branches-recovery/tests/mock_l1_server.py).
- **Target Deliverable Path:** [`research/antigravity/reviews/REV-SDK-ACK-AUTH-REAL-DB4.md`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/reviews/REV-SDK-ACK-AUTH-REAL-DB4.md).
- **Scratch Workspace:** `.local/scratch/sdk-ack-auth-review/` (mode `0700`, disk consumption: 40 KB $\ll$ 512 MB, `TMPDIR` inside scratch, zero `/tmp` growth).
- **Verdict:** **ACCEPT_REMEDIATED_SOURCE** (scoped strictly to compiled db4 Node router/auth HTTP boundary over FakeArtifacts/in-memory store).

---

## 1. Executive Summary & Review Scope

Under Codex Principal directive C1671, this independent review was conducted by a distinct reviewer (`sdk-ack-auth-reviewer`, conversation ID `18d07577`) to prevent self-review of the `b2df985` note-mapping fix. This review independently inspects the exact source diffs of commits `27a86fe` and `b2df985` on `origin/proto/sdk-distribution-complete`, records compiled JavaScript Merkle/digest provenance against the real `db4f6a8` coordinator in `prototype/.build/node/`, and executes the complete 16/16 boundary regression suite over the compiled Node HTTP runtime.

### Summary of Independent Findings:
1. **Source Inspection (`27a86fe` & `b2df985`):**
   - Verified that `27a86fea3bbf` resolves the missing bearer header defect identified in `REV-SDK-ACK-AUTH`: `ack_warning()` now accepts `agent`, `token`, and `admin_token`, resolves `effective_token` and `effective_agent` before network transmission, attaches `Authorization: Bearer <token>`, and fails fast with `ValueError` when `agent` cannot be resolved.
   - Verified that `b2df985d3eed` maps `action` to `note` in the outgoing JSON payload (`"action": action, "note": action`), aligning client semantics with the TypeScript coordinator contract where `coordinator.ackWarning` records `note: typeof body.note === "string" ? body.note : undefined`.
   - Verified that CLI flags (`--token`, `--admin-token`, `--agent`) were cleanly exposed on the `ack` command in `agent_branches/cli.py`.
   - Verified that `tests/mock_l1_server.py` now enforces `agent` body validation and `check_mutating_auth`, eliminating the double mask identified in the initial review.
2. **Compiled JS Provenance & Integrity:**
   - Compiled JavaScript files in `/home/alexey/git/agent-branches-integration/prototype/.build/node/` were verified against TypeScript compiler build `tsc -p tsconfig.node.json` (exit code 0).
   - Exact sha256 digests were recorded for all critical router, auth, coordinator, and fake runtime modules.
3. **Execution of 16/16 Boundary Suite:**
   - All 16 boundary cases executed cleanly against the compiled Node HTTP daemon listening on `127.0.0.1`.
   - Every security invariant was verified: missing `agent` rejected with HTTP 400 before auth, missing bearer rejected with HTTP 401, cross-agent token rejected with HTTP 403, revoked token rejected with HTTP 401, and runner token rejected with HTTP 401.
   - Authorized flows succeeded with HTTP 200 via owner task token, admin token fallback, and cold-client `$TASK_TOKEN` environment fallback.
   - Case 10 decisively confirmed that `acks[0].note == "merged_locally"`, proving that commit `b2df985` properly persists the acknowledgement note in coordinator state.
   - CLI launcher execution with `--token` flag and `$ADMIN_TOKEN` environment variable passed with exit code 0.

---

## 2. Scope Disclosure

> [!IMPORTANT]
> **Boundary Testing Scope Disclosure:**
> The Node test daemon used in this review (`node_server.mjs`, importing `makeRig` from `prototype/.build/node/test/node/fakes.js` and `serveCoordinator` from `prototype/.build/node/src/local/runtime.js`) utilizes `FakeArtifacts`, `FakeGitHost`, and `MemoryCoordinationStore` (in-memory state store).
> 
> This architecture provides **authentic compiled router and authentication HTTP boundary coverage**, executing the exact JavaScript code compiled from `prototype/src/core/router.ts` and `prototype/src/core/auth.ts`. It does **not** evaluate real physical Git sidecar subprocesses, live git-http transfers, or production Cloudflare Worker Durable Object bindings.

---

## 3. Commit & Artifact Identification

### 3.1 SDK Commits Audited (on `origin/proto/sdk-distribution-complete`)
| Commit SHA | Author | Subject | Diff Scope |
|---|---|---|---|
| `27a86fea3bbf57e5b8dad4101dd918d1170c6385` | `4abc725c` | `fix(sdk): ack_warning sends bearer auth and agent body per proto contract (C1655)` | `agent_branches/client.py`, `agent_branches/cli.py`, `tests/mock_l1_server.py`, `tests/test_client.py` |
| `b2df985d3eedfdf345fceb966b18bed415d1187f` | Alexey Grigorev | `fix(sdk): map action to note in ack_warning payload for db4 router contract (C1669)` | `agent_branches/client.py` (+4, -1) |

### 3.2 Exact Python File Blobs at Commit `b2df985d3eedfdf345fceb966b18bed415d1187f`
Blob hashes verified via `git ls-tree b2df985d3eedfdf345fceb966b18bed415d1187f`:
- `agent_branches/client.py`: `564838d3b45be1232c9586d86dae50605d7cbc35`
- `agent_branches/cli.py`: `96ae714f0a2808cff8843ed6707c039e742f7080`
- `tests/mock_l1_server.py`: `0b6ee2de4cbc379bd2ad28f2b6b6fa60273caeee`
- `tests/test_client.py`: `23cd77e6cd6f181a01fedb7a2ed98a12e5a09684`

### 3.3 Compiled Node JavaScript Artifacts & SHA256 Digests
Directory: `/home/alexey/git/agent-branches-integration/prototype/.build/node/`
Compilation command: `tsc -p tsconfig.node.json` (exit status: `0`, zero warnings/errors).

| Source Path | Relative Compiled Path | SHA256 Hex Digest |
|---|---|---|
| `src/core/router.ts` | `src/core/router.js` | `573b58005454eb55a505a2aa1bfc72eb2b74d2778c6d2adc670f979fc8446fcd` |
| `src/core/coordinator.ts` | `src/core/coordinator.js` | `87c34a995bb68b6ab585a565dacdaa4a16802eb3a0690f70e73898642ca755f9` |
| `src/core/auth.ts` | `src/core/auth.js` | `c1e70d81c2f230ad88c37b4d4ef129ee9b55cf918346c92afa5396197332f2f6` |
| `src/local/runtime.ts` | `src/local/runtime.js` | `f060cab4721ebe265cc6cccbb8b6314ef3a5a2ac84c859b1745ae510105ef9e6` |
| `test/node/fakes.ts` | `test/node/fakes.js` | `4b2cb06c141f6b1d69f20b866cad99d3b70ac697d13e0e659fb837a551fa32fe` |

---

## 4. Deep Inspection of Source Diffs

### 4.1 Commit `27a86fea3bbf` Inspection
In `agent_branches/client.py`:
- **Signature Expansion:**
  ```python
  def ack_warning(
      self,
      warning_id: str,
      task_id: Optional[str] = None,
      action: str = "acknowledged",
      agent: Optional[str] = None,
      token: Optional[str] = None,
      admin_token: Optional[str] = None,
  ) -> Dict[str, Any]:
  ```
- **Token Resolution Ladder:**
  Resolves `effective_token` through: explicit `token` $\to$ cached `self.task_tokens.get(task_id)` $\to$ explicit `admin_token` $\to$ `$TASK_TOKEN` $\to$ `$ADMIN_TOKEN`.
- **Pre-flight Agent Resolution & Fail-Fast:**
  `router.ts` checks `body.agent` before checking credentials (answering 400 when missing). `client.py` now resolves `effective_agent` via `agent`, `self.task_to_agent`, or `self.get_task(task_id, token=effective_token)`. If no agent can be resolved, it raises `ValueError` immediately on the client side.
- **Authorization Header Attachment:**
  ```python
  req_headers: Optional[Dict[str, str]] = None
  if effective_token:
      req_headers = {"Authorization": f"Bearer {effective_token}"}
  return self._request(
      "POST", f"/warnings/{encoded_id}/ack", payload, headers=req_headers
  )
  ```
- **CLI Exposure (`agent_branches/cli.py`):**
  Added `--agent`, `--token`, and `--admin-token` arguments to the `ack` subcommand, passing them directly to `client.ack_warning(...)`.
- **Mock Double Alignment (`tests/mock_l1_server.py`):**
  In `POST /warnings/<id>/ack`, added:
  ```python
  agent = body.get("agent")
  if not isinstance(agent, str) or not agent:
      self._send_json(400, {"error": "agent is a required string"})
      return
  if self.state.expected_admin_token is not None:
      err = self.state.check_mutating_auth(
          self.headers.get("Authorization", ""), agent
      )
      if err:
          self._send_json(err[0], err[1])
          return
  ```
  This unmasks the test double, enforcing that tests exercise authentic authentication headers.

### 4.2 Commit `b2df985d3eed` Inspection
In `agent_branches/client.py` lines 429–436:
```python
payload: Dict[str, Any] = {
    "action": action,
    "note": action,
    "agent": effective_agent,
}
```
**Rationale & Contract Alignment:**
In `prototype/src/core/router.ts` (lines 542–545):
```typescript
const result = await coordinator.ackWarning(decodeURIComponent(ackMatch[1]), {
  agent: body.agent,
  note: typeof body.note === "string" ? body.note : undefined,
});
```
The coordinator router checks for `body.note`. When `client.py` sent only `{"action": action}`, `body.note` was evaluated as `undefined`, causing the warning ack record in coordinator state to lose the human-readable action string. Mapping `"note": action` alongside `"action": action` maintains backward compatibility with legacy consumers while ensuring the action is stored in the coordinator's audit log.

---

## 5. Execution Evidence: 16/16 Boundary Test Suite

The boundary suite was executed independently via `.local/scratch/sdk-ack-auth-review/run_16_boundary_suite.py` against the compiled Node server on `127.0.0.1`.

### 5.1 Results Table
| Case # | Description | Target Route & Conditions | Expected Verdict | Observed Result | Pass/Fail |
|---|---|---|---|---|---|
| **Case 1** | Repository Setup | `POST /setup` with `ADMIN_TOKEN` | HTTP 201/200, seedCommit generated | `code=201`, seed=`0000000000000000000000000000000000000001` | **PASS** |
| **Case 2** | Task Creation (Alpha) | `POST /tasks` with `agent="actor-alpha"` | HTTP 201, task token minted | `code=201`, taskId=`task-0001`, agent=`actor-alpha-0001` | **PASS** |
| **Case 3** | Task Creation (Beta) | `POST /tasks` with `agent="actor-beta"` | HTTP 201, task token minted | `code=201`, taskId=`task-0002`, agent=`actor-beta-0002` | **PASS** |
| **Case 4** | Warning Generation | `POST /checks` with conflict pair `[alpha, beta]` | HTTP 200, warning record created | `code=200`, created warn-id=`warn-1` | **PASS** |
| **Case 5** | Missing `agent` in Body | `POST /warnings/:id/ack` with `{task_id, action}` | HTTP 400 Bad Request (before auth ladder) | `code=400`, error=`agent is a required string` | **PASS** |
| **Case 6** | Missing Authorization | `POST /warnings/:id/ack` with `{agent}` but no bearer | HTTP 401 Unauthorized | `code=401`, error=`unauthorized: bearer token required` | **PASS** |
| **Case 7** | Foreign Agent Token | `POST /warnings/:id/ack` for Alpha using Beta's token | HTTP 403 Forbidden | `code=403`, error=`forbidden: this token belongs to actor-beta-0002, not actor-alpha-0001` | **PASS** |
| **Case 8** | Revoked Agent Token | `POST /warnings/:id/ack` using revoked Beta token | HTTP 401 Unauthorized | `code=401`, error=`unauthorized: ADMIN_TOKEN, the agent's task token or the sidecar bearer required` | **PASS** |
| **Case 9** | Owner Task Token via SDK | `client.ack_warning(token=token_a)` | HTTP 200 OK, ack recorded | `code=200`, acks count=1, last_ack_agent=`actor-alpha-0001` | **PASS** |
| **Case 10** | Persisted Note Check | Assert `acks[0].note == "merged_locally"` | Matches `action` passed via SDK | `persisted note='merged_locally'` | **PASS** |
| **Case 11** | Admin Token Fallback | `client.ack_warning(admin_token=ADMIN_TOKEN)` | HTTP 200 OK | `code=200`, acks count=2, note=`admin_override` | **PASS** |
| **Case 12** | Cold Client `$TASK_TOKEN` | Fresh client without cache, env `$TASK_TOKEN` | HTTP 200 OK (resolves agent via `get_task`) | `code=200`, acks count=3, note=`cold_env_ack` | **PASS** |
| **Case 13** | CLI `--token` Flag | `./agent-branches ack --token <token>` | RC 0, output formatted | `rc=0`, output: `WARNING ACKNOWLEDGED` | **PASS** |
| **Case 14** | CLI `$ADMIN_TOKEN` Env | `./agent-branches ack` with `$ADMIN_TOKEN` env | RC 0, output formatted | `rc=0`, output: `WARNING ACKNOWLEDGED` | **PASS** |
| **Case 15** | Client Fail-Fast Missing Agent | `client.ack_warning()` with no agent/task | Client-side `ValueError` | `raised=True`, `ValueError: Cannot resolve agent for warning 'warn-arbitrary' ...` | **PASS** |
| **Case 16** | Runner Token Rejected | `POST /warnings/:id/ack` with `RUNNER_TOKEN` | HTTP 401 Unauthorized (runner is read-only) | `code=401`, error=`unauthorized: ADMIN_TOKEN, the agent's task token or the sidecar bearer required` | **PASS** |

### 5.2 Test Execution Transcript
```text
$ TMPDIR=.local/scratch/sdk-ack-auth-review/tmp python3 .local/scratch/sdk-ack-auth-review/run_16_boundary_suite.py
[INFO] Real compiled db4 coordinator running on http://127.0.0.1:43653
[PASS] Case 1: Setup Repository (POST /setup) - code=201, seed=0000000000000000000000000000000000000001
[PASS] Case 2: Task Creation Alpha (POST /tasks) - code=201, taskId=task-0001, agent=actor-alpha-0001
[PASS] Case 3: Task Creation Beta (POST /tasks) - code=201, taskId=task-0002, agent=actor-beta-0002
[PASS] Case 4: Mint Warning (POST /checks) - code=200, warn_id=warn-1
[PASS] Case 5: Missing agent -> 400 Bad Request (before auth) - code=400, error=agent is a required string
[PASS] Case 6: Missing Authorization header -> 401 Unauthorized - code=401, error=unauthorized: bearer token required
[PASS] Case 7: Foreign valid agent token -> 403 Forbidden - code=403, error=forbidden: this token belongs to actor-beta-0002, not actor-alpha-0001
[PASS] Case 8: Revoked agent token -> 401 Unauthorized - code=401, error=unauthorized: ADMIN_TOKEN, the agent's task token or the sidecar bearer required
[PASS] Case 9: Owner task token -> 200 OK via SDK - acks count=1, last_ack_agent=actor-alpha-0001
[PASS] Case 10: Persisted note check (verifies b2df985) - persisted note='merged_locally'
[PASS] Case 11: Admin token fallback -> 200 OK via SDK - acks count=2, last_ack_note=admin_override
[PASS] Case 12: Cold client $TASK_TOKEN fallback -> 200 OK via SDK - acks count=3, note=cold_env_ack
[PASS] Case 13: CLI --token flag -> RC 0 - rc=0, stdout snippet: ========================================
  WARNING ACKNOWLED
[PASS] Case 14: CLI $ADMIN_TOKEN env -> RC 0 - rc=0, stdout snippet: ========================================
  WARNING ACKNOWLED
[PASS] Case 15: Fail-fast missing agent in client -> ValueError - raised=True, msg=Cannot resolve agent for warning 'warn-arbitrary'. Task lookup failed or task record is missing agentId. Specify agent explicitly.
[PASS] Case 16: Runner token rejected on ACK -> 401 - code=401, error=unauthorized: ADMIN_TOKEN, the agent's task token or the sidecar bearer required

======================================================================
SUMMARY: 16/16 BOUNDARY CHECKS PASSED ON REAL COMPILED DB4 NODE COORDINATOR
======================================================================
```

### 5.3 SDK Regression Test Suite Confirmation
In addition to the 16 boundary tests, the full regression suite in `/home/alexey/git/agent-branches-recovery` was re-verified:
```text
$ cd /home/alexey/git/agent-branches-recovery && python3 -m unittest tests/test_client.py
......................
----------------------------------------------------------------------
Ran 22 tests in 7.783s

OK
```
Zero regressions observed.

---

## 6. Publication Credential Guard

The deliverable report was evaluated with the publication credential scanner:
```text
$ python3 research/antigravity/tooling/publication_guard.py research/antigravity/reviews/REV-SDK-ACK-AUTH-REAL-DB4.md
Scanned 1 paths (1 files). Violations: 0. Status: PASS
```
Zero secrets, raw tokens, or private environmental configurations leaked.

---

## 7. Operational Invariants Compliance

- **Process Memory Limits:** Kept strictly within cooperative slice ($\le 1500$M).
- **Disk & Scratch Space:** Total scratch directory size is 40 KB, strictly bounded $\le 512$ MB.
- **Environment Sanitation:** `TMPDIR` redirected exclusively to `.local/scratch/sdk-ack-auth-review/tmp/`. Zero writes to `/tmp`.
- **Git Working Tree:** Subagent created zero git commits, staged changes, or branch modifications.

---

## 8. Final Verdict

**VERDICT: ACCEPT_REMEDIATED_SOURCE** (scoped strictly to compiled db4 Node router/auth HTTP boundary over FakeArtifacts/in-memory store).

The source remediation in commits `27a86fea3bbf57e5b8dad4101dd918d1170c6385` and `b2df985d3eedfdf345fceb966b18bed415d1187f` completely and correctly resolves the SDK warning acknowledgement authentication defect and note persistence impedance. The changes adhere strictly to the compiled `db4f6a8` coordinator protocol contract, pass all 16/16 boundary checks, and introduce zero regressions to the distribution package.
