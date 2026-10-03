# Agent Branches: L2 Agent Client & L3 Radar Engine Architecture Contract

**Status:** APPROVED FOR IMPLEMENTATION (Refocus 2026-10-03, Claude Principal + Codex Principal C-1303)  
**Owners:** `antigravity-head` (`46fdb644`)  
**Target Lanes:**
- **L2 Agent Client:** Branch `proto/l2-client` (CLI + MCP tool suite)
- **L3 Advisory Radar Engine:** Branch `proto/l3-radar` (In-memory pairwise trial-merge + budgeted semantic test runner)

---

## 1. System Topology & Responsibilities

```
+-------------------------------------------------------------------------+
|                  Cloudflare Workers + Durable Objects                   |
|                  L1 Coordinator & Storage Scaffold                      |
|  - POST /tasks        - POST /events/push                               |
|  - GET /status        - GET /tasks/:id                                  |
|  - POST /warnings/:id/ack                                               |
+--------------------+--------------------------------+-------------------+
                     ^                                ^
                     | HTTP API                       | Webhook / Dispatch
                     |                                v
+--------------------+--------------+   +-------------+-------------------+
|          L2 Agent Client          |   |        L3 Radar Engine          |
|    CLI & Optional MCP Server      |   |   Pairwise Trial-Merge & Tests  |
| - Registers agent task & intent   |   | - Fast in-memory git merge-tree |
| - Pushes WIP commit heads         |   | - Budgeted combined-tree tests  |
| - Polls status & active warnings  |   | - Output: Warning or UNKNOWN    |
| - Acknowledges warnings           |   | - Never 'safe' by default       |
+-----------------------------------+   +---------------------------------+
```

---

## 2. L2 Agent Client Contract

### 2.1 CLI Interface (`agent-branches`)

```bash
# 1. Register a new task / branch fork
agent-branches task create \
  --repo <repo_url> \
  --base-sha <commit_sha> \
  --intent "Refactoring auth middleware to use JWT" \
  --branch "feat/jwt-auth"

# 2. Push WIP commit head & notify coordinator
agent-branches push \
  --task-id <task_uuid> \
  --head-sha <commit_sha> \
  --intent-update "Updated schema validation" \
  --test-provenance "vitest: 14 passed"

# 3. Query status & check for warnings
agent-branches status --task-id <task_uuid> [--json]

# 4. Acknowledge an active conflict warning
agent-branches ack \
  --task-id <task_uuid> \
  --warning-id <warning_uuid> \
  --action "rebased_locally"
```

### 2.2 Model Context Protocol (MCP) Interface (Optional)
For agents operating in native MCP harnesses:
- `branches_create_task(repo, base_sha, intent, branch)`
- `branches_push_wip(task_id, head_sha, intent_update, test_provenance)`
- `branches_get_status(task_id)`
- `branches_ack_warning(task_id, warning_id, action)`

---

## 3. L3 Advisory Radar Engine Contract (Consumer View of L1 CONTRACT.md)

*Note: `prototype/CONTRACT.md` on branch `proto/l1-scaffold` serves as the authoritative single source of truth for coordinator routes and radar hooks.*

### 3.1 Pairwise Textual Trial Merge (`git merge-tree --write-tree`)
- **Mechanism:** Leverages Git 2.43+ `git merge-tree --write-tree --merge-base=<base_sha> <headA_sha> <headB_sha>` directly against the repository's local object store.
- **Properties:**
  - Computationally lightweight (~5 ms per pair, as proven in S-C1: 45 trial merges in 0.24 s).
  - No checkouts, no working tree mutation.
  - Note on storage: `git merge-tree --write-tree` writes tree objects to the Git object database; object growth is bounded and periodically measured.
  - Returns `tree_sha` on clean merge (returncode 0).
  - Returns conflicting files and conflict sections on conflict (returncode 1).

### 3.2 Budgeted Combined-Tree Test Runner
- If textual merge succeeds:
  - For pairs touching shared modules or high-overlap components:
  - Allocate bounded test execution budget ($T \le 15$s) running inside isolated process groups (`os.setsid` / `SIGKILL` on timeout) under sanitized minimal environments.
  - Safe archive extraction: enforces strict path boundary validation (`os.path.commonpath`) and rejects symlinks pointing outside the workspace.
  - Test evidence requirement: positive evidence of $>0$ collected and executed tests passing. Zero collected tests is treated as `unknown` (reason: `no_tests_collected`), never as a silent pass.
  - If tests pass $\to$ `status = "clean"`.
  - If tests fail $\to$ `status = "conflict"`, `kind = "test"`.

### 3.3 Status Enum & Strict Fail-Closed Invariants
Output contract emitted by the Radar:
```json
{
  "pair": ["agent-uuid-A", "agent-uuid-B"],
  "heads": {
    "agent-uuid-A": "sha_head_A",
    "agent-uuid-B": "sha_head_B"
  },
  "status": "conflict" | "clean" | "unknown" | "not_checked",
  "kind": "textual" | "test" | null,
  "evidence": {
    "conflicting_files": ["src/auth.ts"],
    "conflict_type": "content_conflict",
    "details": "Conflict markers at lines 42-58"
  },
  "warning": { ... } // Present ONLY when status == 'conflict'
}
```

**Core Invariants:**
1. **Never 'Safe' by Default:** If a pair has unmerged objects, missing test suites, or execution times out, the outcome is strictly marked `"unknown"` or `"not_checked"`. Disjoint/no-overlap files without executed tests report `"not_checked"` or `"unknown"`, never `"clean"`.
2. **Deterministic & Bounded:** Merge matrix calculations are bounded to active concurrent tasks ($N \le 10$).
3. **Ordinary Git Fallback:** All operations preserve standard Git commit graphs and branch references; no proprietary repository format.

---

## 4. Worktree & Concurrency Allocation
- **L2 Client Worktree:** `/home/alexey/git/agent-branches-l2-client` (Branch: `proto/l2-client`)
- **L3 Radar Worktree:** `/home/alexey/git/agent-branches-l3-radar` (Branch: `proto/l3-radar`)
- **Storage Policy:** Lightweight worktrees sharing underlying `.git` object store; node_modules capped at $\le 512$ MiB.
