# Runtime Contract: REMOTE-AUTONOMY-SUPERVISOR-1830

Date: 2026-10-05
Author: antigravity-head-gemini-recovery (session 5e1abcdb-44d3-44c9-ba20-eb21f6235672)
Audience: codex-principal (93cf28f2), desktop-orchestrator (79ffb8c7), quota-launcher-head-gemini (a86056b5), agent-coordination-head-gemini (a84e443b)

## 1. Executive Summary & Custody

In accordance with `research/codex/remote-autonomy-1830-plan-20261005.md` and the authoritative human deadline of 16:30 UTC / 18:30 Europe/Berlin, this contract defines the runtime extension, receipt schema, and execution lifecycle for `REMOTE-AUTONOMY-SUPERVISOR-1830`.

The recovered Antigravity head (`antigravity-head-gemini-recovery [5e1abcdb]`) accepts sole custody of `REMOTE-AUTONOMY-SUPERVISOR-1830`. Custody extends the existing healthy supervision service rather than creating a competing duplicate production daemon.

---

## 2. Preserved Runtime Provenance & Inspection

Inspection conducted on 2026-10-05 at 13:46 UTC confirms:

- **Supervision Daemon PID**: 3265459 (`python3 scripts/supervision/service.py`)
  - **PPID**: 3265406 (`/home/alexey/.local/bin/aplexer worker --id 4914b3d1-b577-484b-ae0a-5f47dab74d87`)
  - **Started**: `Sun Oct  4 16:51:06 2026`
  - **Loaded Source Hash**: `scripts/supervision/service.py` sha256 `4cae0f3cbebb1afed62dfa9756031e36b8a89d767a3032e4883f1670bb208e81`
  - **Compiled Bytecode**: `scripts/supervision/__pycache__/service.cpython-312.pyc` (mtime 2026-10-04 16:50:00)
  - **Exclusive Lock**: `fcntl.flock(LOCK_EX)` on `/home/alexey/git/cloudflare-agent-git/.local/supervision/service.lock`
  - **State Directory**: `/home/alexey/git/cloudflare-agent-git/.local/supervision/` (mode 0700)
- **Parent Process Hierarchy**:
  - `PID 560806`: aplexer worker for `46fdb644` (preserved, alive).
  - `PID 560857`: Old AGY UI process in `Tsl+` (SIGSTOP only, zero concurrent writers, no group kill).
  - `PID 1608645`: `/usr/bin/python3 scripts/metrics/collect.py --loop --serve` (preserved, alive).
  - `PID 1508033`: `/home/alexey/.local/lib/zcodex/zcodex` (preserved, alive).
- **Current Supervision State**:
  - `status.json`: degraded=false, active_principals=["codex-principal"], storage used 9.06 MB / soft 134 MB / hard 268 MB.
  - Active pending message: `01a10c51-1e6f-7273-a917-8606744bfcdb` to codex-principal.
  - Exact ACK cursors and reconciliation logs preserved in `.local/supervision/events.jsonl`.

---

## 3. Core Deficiencies Addressed

Per desktop Luna monitoring (13:44 UTC) and codex-principal review (C2574):
1. **Lack of Terminal & Review Consumption**: `service.py` monitors principal readiness and task counts from `TASKS.json`, but does not ingest task-unit completion receipts or verify independent review acceptance before tasks are treated as completed.
2. **Repetitive Stale Notification Storms**: Scans the entire registry and emits repetitive full task lists (`Tasks: [project] ...`) every cooldown period, even when no substantive actionable change occurred.
3. **No Review-Gated Dependency Unblocking**: Model B dispatches without verified independent review of Model A's output, yielding mechanical execution rather than autonomous closed-loop delivery.

---

## 4. Contract Specifications: Receipt & Event Schema

### 4.1 Terminal Receipt Schema (`task_terminal_receipt.json`)
Every task-unit executor must emit a structured terminal receipt upon completion:
```json
{
  "task_id": "TASK-UUID-OR-CANONICAL-ID",
  "project_id": "agent-branches | agent-quota-launcher | agent-coordination | cloudflare-agent-git",
  "executor": {
    "session_id": "APLEXER-SESSION-ID",
    "tag": "EXACT-TAG",
    "engine": "antigravity | codex | opencode | zcodex",
    "workload_pid": 12345
  },
  "phase": "execution",
  "status": "completed-awaiting-review",
  "artifacts": [
    {
      "path": "path/to/artifact.py",
      "sha256": "abc...",
      "size_bytes": 1024
    }
  ],
  "first_tool_evidence": {
    "tool_name": "view_file",
    "timestamp": "2026-10-05T13:45:00Z",
    "summary": "Verified baseline tests pass"
  },
  "completed_at": "2026-10-05T13:50:00Z"
}
```

### 4.2 Independent Review Receipt Schema (`task_review_receipt.json`)
Before any dependent task B may be dispatched or task marked `accepted`/`done`, a distinct reviewer must emit:
```json
{
  "task_id": "TASK-UUID-OR-CANONICAL-ID",
  "review_task_id": "REVIEW-TASK-ID",
  "reviewer": {
    "session_id": "DISTINCT-REVIEWER-SESSION-ID",
    "tag": "DISTINCT-REVIEWER-TAG",
    "engine": "gemini | codex | opencode",
    "workload_pid": 67890
  },
  "target_receipt_sha256": "RECEIPT-SHA256",
  "verdict": "ACCEPTED | REJECTED",
  "review_evidence": {
    "test_command": "pytest tests/test_feature.py",
    "exit_code": 0,
    "tests_passed": 12,
    "tests_failed": 0,
    "negative_cases_tested": [
      "staged_secret_rejection",
      "push_failure_recovery",
      "clean_ahead_push"
    ]
  },
  "reviewed_at": "2026-10-05T13:55:00Z"
}
```

### 4.3 Actionable State Change Filtering
Supervision messages to principals/heads are restricted to:
1. `TASK_READY`: A previously blocked task has had all dependencies accepted by independent review.
2. `REVIEW_REQUIRED`: An execution task completed and awaits a distinct reviewer assignment.
3. `TASK_REJECTED`: An independent reviewer rejected an artifact; actionable repair required.
4. `STALL_DETECTED`: A task in `running` or `review` has exceeded its execution SLO without active tool progress.

If no actionable transition occurs, no redundant full-task notification is emitted.

---

## 5. Bounded Service Reload Architecture

To guarantee zero duplicate production daemons and preserve collector/metric continuity:
1. **Adapter Isolation**: The new receipt consumer and event filter logic are developed in an isolated module `scripts/supervision/terminal_consumer.py`.
2. **Deterministic Test Verification**: `scripts/supervision/test_terminal_consumer.py` tests receipt validation, review-gating, dedup filtering, and corrupt-receipt fail-closed handling.
3. **Controlled State Handoff**:
   - The reload process creates `.local/supervision/reload_intent.json` recording state beforeimages.
   - Touching `.local/supervision/stop` signals running PID 3265459 to exit within its 60-second polling cycle.
   - Once `service.lock` is released, the upgraded `service.py` acquires `service.lock`, validates the manifest, and resumes with zero lost events.
   - Collector PID 1608645 remains completely unaffected as it runs in an independent loop under parent PID 560806.

---

## 6. Backward Plan Milestones (UTC / Europe/Berlin)

| UTC | Berlin | Checkpoint | Required Evidence | Owner |
|---|---|---|---|---|
| **14:15** | 16:15 | Runtime Contract | This published contract + receipt schemas ACKed by Codex principal | Ant recovery head |
| **15:00** | 17:00 | Adapter Integration | Tested `terminal_consumer.py` + updated `service.py` ready in isolated branch | Delegated Worker (Ant-owned) |
| **15:45** | 17:45 | Negative Matrix | Test suite demonstrating rejection of unreviewed dependent dispatch, fake ACKs, corrupted receipts | Delegated Reviewer (Ant-owned) |
| **16:15** | 18:15 | No-Desktop Trial | Full repeated cycle: Model A -> Independent Review Accept -> Model B launch with zero desktop/Luna intervention | Heads & Supervisor |
| **16:30** | 18:30 | Autonomy Decision | Formal principal review and acceptance report | Codex Principal & Heads |

---

## 7. Coordination with AgentBranches CLI (`branches sync git`)

1. Candidate `1e57ed3` in `wt-branches-sync` is under correction by QL head (`a86056b5`) per Codex principal's 6-point critique (C2571/C2575).
2. Canonical `10d9d50` lease on `agent-branches` remains protected.
3. Antigravity head will verify the corrected patch against the 6-point negative matrix before canonical integration release.
