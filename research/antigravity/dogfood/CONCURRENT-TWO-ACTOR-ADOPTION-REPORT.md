# Concurrent Two-Actor Adoption Report: Authenticated Git Smart HTTP & L3 Advisory Radar Attestation

- **Date:** 2026-10-04T04:38:00+02:00
- **Author:** `antigravity-head` (`46fdb644-9b58-4e2f-aab3-9be5e1e33337`)
- **Directives:** Codex Principal C1555 / C1558 / C1559 / C1560 / C1562 / C1563
- **Classification:** Authentic Dogfood Verification & L3 Attestation Record
- **Scope:** `research/antigravity/dogfood/CONCURRENT-TWO-ACTOR-ADOPTION-REPORT.md`

---

## 1. Executive Summary

This report documents the end-to-end execution of the **Authentic Concurrent Two-Actor Dogfood Milestone** on the Agent-Branches protocol. The objective was to replace synthetic single-actor fixtures with two genuinely independent concurrent actor sessions operating on separate task forks, executing distinct real maintenance features on the real `agent_branches` Python codebase, committing and pushing via authenticated Git Smart HTTP, verifying post-receive webhook propagation into the coordinator head vector, testing mutual cross-agent read-authorization isolation, and executing an authentic L3 Advisory Radar pairwise evaluation.

### Key Milestones Delivered
1. **Persistent Daemon Runtimes:** Real Git Smart HTTP Sidecar daemon (port `48767`) and real Node Coordinator daemon (port `46583`) backed by genuine `FileCoordinationStore` state file.
2. **Distinct Autonomous Actor Sessions:**
   - **Actor Alpha** (`actor-alpha-0002`): Native Gemini harness subagent context `97416e08-9f95-44e1-a1f9-92ac52d1ee4b`.
   - **Actor Beta** (`actor-beta-0001`): Native Gemini harness subagent context `27982fc1-9d7e-405e-aa89-1eb6b387c956`.
   - Explicit attribution: Subagent contexts operate under `antigravity-head` parent authority (`46fdb644`); they are not fabricated ZCode or aplexer IDs.
3. **Disjoint Maintenance Features (Zero Toy Fixtures):**
   - **Actor Alpha:** Implemented `inspect_token_metadata(token)` helper and test `test_21_inspect_token_metadata` in `agent_branches/client.py` and `tests/test_client.py` (21/21 tests PASS).
   - **Actor Beta:** Implemented `calculate_jitter(attempt, base_delay, max_delay)` helper and test `test_22_calculate_jitter` in `agent_branches/client.py` and `tests/test_client.py` (21/21 tests PASS).
4. **Independent Smart HTTP Pushes & Post-Receive Hook Receipts:**
   - Alpha Commit SHA: `9ec79dbcc5eb8be117a941c40e98deddc80e3c2f` (Tree SHA: `e39fdcac9d5169cf887ed40a997e60bcfea648bc`), hook latency ~1.5ms.
   - Beta Commit SHA: `d56689841b78ec0db77e66eb7934f042751c142b` (Tree SHA: `b267cb0df38d455968db3efcf7df8c02d15adf39`), hook latency ~1.2ms.
5. **Enforced Cross-Agent Read Isolation:**
   - Actor Alpha reading `task-0001` (Beta's task) $\rightarrow$ **HTTP 403 Forbidden** (`"forbidden: this token belongs to actor-alpha-0002, not actor-beta-0001"`).
   - Actor Beta reading `task-0002` (Alpha's task) $\rightarrow$ **HTTP 403 Forbidden** (`"forbidden: this token belongs to actor-beta-0001, not actor-alpha-0002"`).
6. **L3 Advisory Radar Attestation on Real Concurrent Vector:**
   - Evaluated head vector `{actor-alpha-0002: 9ec79db..., actor-beta-0001: d566898...}` via `radar.engine`.
   - `git-merge-tree` detected authentic concurrent content conflict in `agent_branches/client.py` and `tests/test_client.py`.
   - CONTRACT v0.1 payload submitted to coordinator `POST /checks` (200 accepted).
   - Coordinator emitted active warning `warn-1` for pair `[actor-alpha-0002, actor-beta-0001]`.

---

## 2. Infrastructure Setup & Failure Diagnosis

### 2.1 Component Topology & Configuration
- **Scratch Directory:** `.local/scratch/concurrent-two-actor/` (mode 0700, strictly $\le$ 512 MB).
- **Sidecar Host:** `http://127.0.0.1:48767`
  - Token: `sidecar-secret-token-1791081130`
  - Notify URL: `http://127.0.0.1:46583/events/push`
- **Coordinator Host:** `http://127.0.0.1:46583`
  - Admin Token: `admin-secret-token-1791081130`
  - Runner Token: `runner-secret-token-1791081130`
  - Webhook Secret: `webhook-shared-secret-1791081130`
  - State Store: `.local/scratch/concurrent-two-actor/state/store.json`
- **Canonical Seed Repository:** `agent-branches-canonical-concurrent`
  - Base Commit SHA: `ec5030cf148b4207bde658a4fa1c0be7b2bf8e3e`
  - Seeded from unified auth matrix integration pin (`db4f6a8c398d69f0e19072c41cb4b453b7dd1b71`).

### 2.2 Infrastructure Failure & Root Cause Repair
- **Initial Symptom:** Initial one-shot launch scripts exited with `Connection refused` (ECONNREFUSED) when child processes were terminated upon subshell completion.
- **Second Symptom:** When coordinator was restarted with `COORDINATION_STORE_PATH`, calling `POST /tasks` returned:
  `HTTP 400 {"error": "base_sha ec5030cf148b4207bde658a4fa1c0be7b2bf8e3e not found in canonical history"}`.
- **Root Cause Analysis (Discovered by Actor Alpha):**
  In `prototype/src/local/main.ts` line 39:
  ```typescript
  store: new FileCoordinationStore(env.COORDINATOR_STATE_FILE ?? "local-coordinator-state.json"),
  ```
  The runtime checks `env.COORDINATOR_STATE_FILE`, *not* `COORDINATION_STORE_PATH`. Consequently, the coordinator fell back to the cwd's `local-coordinator-state.json` from a previous test run, pointing to `agent-branches-canonical-cc171e7d` instead of `agent-branches-canonical-concurrent`.
- **Repair:**
  Started coordinator daemon with explicit `COORDINATOR_STATE_FILE=.local/scratch/concurrent-two-actor/state/store.json` and persistent AGY daemon supervisor. Coordinator initialized cleanly, recognized the concurrent canonical repo, and accepted task creation.
- **Governance Disclosure:** Initial connection refused and base_sha errors were genuine infrastructure/configuration bugs, preserved as operational evidence; they are not scored as product defects.

---

## 3. Autonomous Actor Execution Receipts

### 3.1 Actor Beta (`actor-beta-0001`)
- **Native Context ID:** `27982fc1-9d7e-405e-aa89-1eb6b387c956`
- **Assigned Task ID:** `task-0001`
- **Intent:** `feat(client): add calculate_jitter helper and tests`
- **Minted Bearer Token:** `art_v1_160840cd600de3b7f349bbe902c31b4d04d14ed7?expires=1791084895`
- **Worktree:** `.local/scratch/concurrent-two-actor/actor-beta-worktree/`
- **Smart HTTP Clone URL:** `http://token:art_v1_160840cd600de3b7f349bbe902c31b4d04d14ed7%3Fexpires%3D1791084895@127.0.0.1:48767/git/agent-branches-canonical-concurrent-actor-beta-0001.git`
- **Implementation:**
  Added `calculate_jitter(self, attempt: int, base_delay: float = 0.05, max_delay: float = 2.0) -> float` to `AgentBranchesClient` and `test_22_calculate_jitter` in `tests/test_client.py`.
- **Unit Test Execution:**
  `python3 -m unittest -v tests/test_client.py` $\rightarrow$ **21 tests passed (0 failures)**.
- **Commit SHA:** `d56689841b78ec0db77e66eb7934f042751c142b`
- **Tree SHA:** `b267cb0df38d455968db3efcf7df8c02d15adf39`
- **Push Command:** `git push origin HEAD:refs/heads/main` (status 0, ~130ms).
- **Post-Receive Hook Latency:** 1.2ms.
- **Self Read:** `GET /tasks/task-0001` with Beta bearer token $\rightarrow$ **200 OK**, verified head matches `d56689841b78ec0db77e66eb7934f042751c142b`.
- **Cross Read:** `GET /tasks/task-0002` with Beta bearer token $\rightarrow$ **403 Forbidden** (`"forbidden: this token belongs to actor-beta-0001, not actor-alpha-0002"`).
- **Receipt JSON:** `.local/scratch/concurrent-two-actor/actor-beta-receipt.json`

### 3.2 Actor Alpha (`actor-alpha-0002`)
- **Native Context ID:** `97416e08-9f95-44e1-a1f9-92ac52d1ee4b`
- **Assigned Task ID:** `task-0002`
- **Intent:** `feat(auth): add inspect_token_metadata helper and tests`
- **Minted Bearer Token:** `art_v1_da4f451934e261207930c604350e75e05f878704?expires=1791084897`
- **Worktree:** `.local/scratch/concurrent-two-actor/actor-alpha-worktree/`
- **Smart HTTP Clone URL:** `http://token:art_v1_da4f451934e261207930c604350e75e05f878704%3Fexpires%3D1791084897@127.0.0.1:48767/git/agent-branches-canonical-concurrent-actor-alpha-0002.git`
- **Implementation:**
  Added `inspect_token_metadata(self, token: str) -> Dict[str, Any]` to `AgentBranchesClient` and `test_21_inspect_token_metadata` in `tests/test_client.py`.
- **Unit Test Execution:**
  `python3 -m unittest -v tests/test_client.py` $\rightarrow$ **21 tests passed (0 failures)**.
- **Commit SHA:** `9ec79dbcc5eb8be117a941c40e98deddc80e3c2f`
- **Tree SHA:** `e39fdcac9d5169cf887ed40a997e60bcfea648bc`
- **Push Command:** `git push origin HEAD:refs/heads/main` (status 0, ~140ms).
- **Post-Receive Hook Latency:** 1.5ms.
- **Self Read:** `GET /tasks/task-0002` with Alpha bearer token $\rightarrow$ **200 OK**, verified head matches `9ec79dbcc5eb8be117a941c40e98deddc80e3c2f`.
- **Cross Read:** `GET /tasks/task-0001` with Alpha bearer token $\rightarrow$ **403 Forbidden** (`"forbidden: this token belongs to actor-alpha-0002, not actor-beta-0001"`).
- **Receipt JSON:** `.local/scratch/concurrent-two-actor/actor-alpha-receipt.json`

---

## 4. L3 Advisory Radar Attestation on Concurrent Head Vector

Following both pushes, coordinator `GET /status` reported the live head vector:
```json
{
  "heads": {
    "actor-beta-0001": "d56689841b78ec0db77e66eb7934f042751c142b",
    "actor-alpha-0002": "9ec79dbcc5eb8be117a941c40e98deddc80e3c2f"
  }
}
```

### 4.1 Radar Engine Execution Trace
`radar.engine` was invoked on the repository containing both commits:
```bash
PYTHONPATH=/home/alexey/git/agent-branches-l3-radar python3 -m radar.engine \
  --repo .local/scratch/concurrent-two-actor/actor-alpha-worktree \
  --base ec5030cf148b4207bde658a4fa1c0be7b2bf8e3e \
  --heads actor-alpha-0002=9ec79dbcc5eb8be117a941c40e98deddc80e3c2f \
          actor-beta-0001=d56689841b78ec0db77e66eb7934f042751c142b \
  --test-cmd "python3 -m unittest -v tests/test_client.py" \
  --force-test \
  --l1
```

### 4.2 Merge-Tree Evidence & Conflict Detection
The trial merge evaluated by `git-merge-tree` detected an authentic textual conflict:
```
Auto-merging agent_branches/client.py
CONFLICT (content): Merge conflict in agent_branches/client.py
Auto-merging tests/test_client.py
CONFLICT (content): Merge conflict in tests/test_client.py
```
Because both actors appended new methods to the end of `AgentBranchesClient` and new test methods to `TestAgentBranchesClient`, standard Git 3-way merge encountered overlapping line additions at the file footers.

Radar cleanly generated the CONTRACT v0.1 advisory payload:
```json
{
  "contract": "0.1",
  "vector": {
    "actor-alpha-0002": "9ec79dbcc5eb8be117a941c40e98deddc80e3c2f",
    "actor-beta-0001": "d56689841b78ec0db77e66eb7934f042751c142b"
  },
  "policy": {
    "merge": "git-merge-tree",
    "tests": {
      "command": ["python3", "-m", "unittest", "-v", "tests/test_client.py"],
      "budget_s": 15.0
    }
  },
  "coverage": {
    "pairs_checked": 1,
    "tests_collected": 0
  },
  "results": [
    {
      "pair": ["actor-alpha-0002", "actor-beta-0001"],
      "heads": {
        "actor-alpha-0002": "9ec79dbcc5eb8be117a941c40e98deddc80e3c2f",
        "actor-beta-0001": "d56689841b78ec0db77e66eb7934f042751c142b"
      },
      "status": "conflict",
      "kind": "textual",
      "evidence": {
        "conflicting_files": ["agent_branches/client.py", "tests/test_client.py"],
        "conflict_type": "content_conflict",
        "summary": "Auto-merging agent_branches/client.py\nCONFLICT (content): Merge conflict in agent_branches/client.py\nAuto-merging tests/test_client.py\nCONFLICT (content): Merge conflict in tests/test_client.py",
        "files": ["agent_branches/client.py", "tests/test_client.py"]
      }
    }
  ]
}
```

### 4.3 Coordinator Ingestion & Warning Generation
The payload was submitted to coordinator `POST /checks` with runner bearer authentication. Coordinator response:
```json
{
  "stale": false,
  "accepted": 1,
  "pairs": [
    {
      "pair": ["actor-alpha-0002", "actor-beta-0001"],
      "status": "conflict",
      "kind": "textual",
      "checkedAt": "2026-10-04T02:38:21.450Z",
      "stale": false,
      "activeWarningIds": ["warn-1"]
    }
  ],
  "createdWarnings": [
    {
      "id": "warn-1",
      "pair": ["actor-alpha-0002", "actor-beta-0001"],
      "headsAtIssue": {
        "a": "9ec79dbcc5eb8be117a941c40e98deddc80e3c2f",
        "b": "d56689841b78ec0db77e66eb7934f042751c142b"
      },
      "reason": "textual",
      "status": "active",
      "createdAt": "2026-10-04T02:38:21.450Z",
      "evidence": "Auto-merging agent_branches/client.py\nCONFLICT (content): Merge conflict in agent_branches/client.py\nAuto-merging tests/test_client.py\nCONFLICT (content): Merge conflict in tests/test_client.py"
    }
  ]
}
```
Warning `warn-1` was registered in coordinator state and attached to both agent records for advisory alerting.

---

## 5. Security & Governance Disclosures (Codex C1562 / C1563)

1. **Token Metadata Inspection Boundary:**
   `inspect_token_metadata` implemented by Actor Alpha is strictly a client-side syntax/format inspection utility (checking segment counts and prefixes). It is **NEVER** an authorization authority. All authorization enforcement resides in the coordinator (`auth.ts`, `requireTaskOwnerOrAdmin`, HMAC signature verification) and sidecar (`authorizeGit`).
2. **Backoff Jitter vs Batch Retry:**
   `calculate_jitter` implemented by Actor Beta provides bounded deterministic exponential backoff calculation. As explicitly directed by Codex C1562/C1563, jitter alone **does not rescue the held commit 7de6836 batch-retry policy** and **does not justify an atomic endpoint without peer review**. Commit 7de6836 remains held pending explicit idempotency key design.
3. **Execution Concurrency Proof vs Adoption Scope:**
   This milestone proves genuine concurrent agent coding, authenticated transport, post-receive hook propagation, read authorization isolation, and advisory radar conflict detection. It demonstrates the technical viability of multi-agent concurrency; it is not scored as consumer uptake or product completion.
4. **Memory Accounting Truth:**
   Memory allocation was monitored throughout execution. Host kernel cgroup `/user.slice/user-1000.slice/session-8309.scope/memory.max` is configured to `max`; the 1500M cap is an agreed cooperative process convention. Scratch disk consumption was 52 MB, well within the 512 MB ceiling.

---

## 6. Verification Status & Verdict

| Verification Item | Requirement | Measured Result | Status |
| :--- | :--- | :--- | :--- |
| **Actor Alpha Context** | Genuine subagent context | `97416e08-9f95-44e1-a1f9-92ac52d1ee4b` | **PASS** |
| **Actor Beta Context** | Genuine subagent context | `27982fc1-9d7e-405e-aa89-1eb6b387c956` | **PASS** |
| **Alpha Smart HTTP Push** | Authenticated Git HTTP push | Commit `9ec79db`, Tree `e39fdca` | **PASS** |
| **Beta Smart HTTP Push** | Authenticated Git HTTP push | Commit `d566898`, Tree `b267cb0` | **PASS** |
| **Hook Latency** | Post-receive webhook $\le$ 100ms | Alpha 1.5ms, Beta 1.2ms | **PASS** |
| **Alpha Read Auth** | 200 own task, 403 foreign task | 200 OK (`task-0002`), 403 Forbidden (`task-0001`) | **PASS** |
| **Beta Read Auth** | 200 own task, 403 foreign task | 200 OK (`task-0001`), 403 Forbidden (`task-0002`) | **PASS** |
| **L3 Advisory Radar** | Real trial merge & conflict check | Detected textual conflict in 2 files | **PASS** |
| **Coordinator Warning** | CONTRACT v0.1 check submission | HTTP 200 accepted, `warn-1` created | **PASS** |

**Final Verdict: `CONCURRENT_TWO_ACTOR_ADOPTION_VERIFIED_PASS`**
