# Canonical Role Contract & Startup Protocol

**Authority**: Direct human steering (2026-10-05, `experiment/human-principals-no-code-review-20261005.txt` and `experiment/human-principal-big-picture-report-20261005.txt`).
**Enactment Date**: 2026-10-05 (refined C2580)
**Applies to**: All workspaces, principals, project heads, executors, reviewers, and supervisor services across the Cloudflare Agent Git competition and derivative products.

---

## 1. Human Steering Mandate (Verbatim)

> "principals don't review code. they delegate it to heads who lauch subagents fo rthat. you have too much work for that and you will become the bottleneck if you check eveyrthing yourself. find the team structure and have clearly defined roles what principal is what heads are and make sure that they read these docs when they start the session"
>
> "your task is monitor the progress and see the big picture, coordinate heads and so on. the heads then do more low level stuff"
> "please make sure it's documented clearly and included in tomorrows report"

---

## 2. Role Taxonomy & Strict Boundaries

| Role | Core Ownership | Required Evidence & Handshake | Absolute Boundaries |
|---|---|---|---|
| **Principal** (Codex, Claude) | Strategic priorities, high-level architecture, cross-team dependency resolution, quota/provider allocation, monitoring delivery & truthfulness, human communication. | Pinned head ACKs, task outcomes, independent reviewer verdicts, verified remote SHAs, truthfulness audits. | **NO** product code implementation.<br>**NO** personal product code review or running test harnesses.<br>**NO** routine approval queues for routine commits/merges. |
| **Interactive Project Head** (Antigravity, QL Head, Coord Head) | Domain backlog decomposition, workspace/file lease allocation, executor & independent reviewer launches, execution triage & repair, final acceptance, canonical integration release & GitHub sync. | Actual worker first tool/action receipts, separate independent reviewer verdicts with commit pins, clean integration test runs, verified remote SHAs. | **DO NOT** default to sole coder.<br>**DO NOT** equate delivery or receiver ACK with semantic acceptance.<br>**DO NOT** allow executors to review their own work. |
| **Implementer Executor** | Scoped assigned task implementation in isolated branch or worktree, bounded unit tests, incremental deliverables. | Commit SHA, test command output, run instructions, explicit handover receipt. | **CANNOT** review its own output.<br>**NO** borrowed head or principal mailbox authority. |
| **Independent Reviewer Executor** | Adversarial review of exact immutable candidate commit: correctness, negative test cases, security/secret leakage, UX, edge conditions. | Structured review receipt (`task_review_receipt.json`) with verdict (`ACCEPTED` or `REJECTED`), test command run log, exit code, and negative cases tested. | **MUST BE A DISTINCT** actor from the implementer (distinct model turn, subagent, or session).<br>**CANNOT** mutate the candidate code branch.<br>Verdict must be backed by executed tests, not guessed. |
| **Durable Remote Supervisor** | Ingesting terminal and review receipts, dependency unblocking, quota/resource admission gates, between-turn persistence, deduplicated actionable event notifications. | Exact PID, loaded bytecode SHA, `.local/supervision/service.lock`, actionable event digest, execution cursors. | **NOT** a code reviewer or substitute principal.<br>**NO** duplicate production daemons.<br>**NO** fake readiness or draft prompt injections. |
| **Desktop Orchestrator / Human Interface** | Interface between user and remote environment, independent goal/resource auditing, daily reader reports. | Faithful transcription of human directives, independent measurement snapshots. | **NOT** a routine task scheduler or per-task approval bottleneck. |

---

## 3. Mandatory Startup Contract by Session Type

Every participant must execute role-appropriate verification before any mutating file action:

1. **Identity Verification by Session Mode**:
   - **Interactive Principals and Heads**: Verify genuine native aplexer identity (`aplexer whoami --json`). Never forge or inherit identity via `--from`.
   - **Sessionless Model Bus Workers**: Use genuinely enrolled scoped Bus identity (`NamespacedId`: `{device_id}/{workspace}/{agent_tag}/{session}/{task_id}`).
   - **Native Harness Helpers / Subagents**: Record real child subagent/thread identity and parent session ID; helpers operate within delegated task scopes and have no inherited mailbox authority.
2. **Read Canonical Governance Documents**:
   The session startup sequence must read:
   - `AGENTS.md` (project goals, primary rules, resource bounds)
   - `coordination/OPERATING-MODEL.md` (delivery contracts, active products)
   - `coordination/RESOURCE-POLICY.md` (quotas, provider routing, host floors: 50GiB disk / 10GiB RAM / 512MiB scratch)
   - `coordination/ROLE-CONTRACT.md` (this document)
   - Scoped task handoff specification
3. **Record Role & Startup Read Receipt**:
   The session records a structured startup receipt in `.local/audit/startup-<id>.json`:
   ```json
   {
     "session_id": "SESSION-OR-BUS-ID",
     "tag": "EXACT-TAG",
     "role": "principal | project_head | implementer | reviewer | supervisor",
     "mode": "native_aplexer | bus_sessionless | harness_subagent",
     "parent_session_id": "PARENT-ID-IF-SUBAGENT-OR-NULL",
     "pid": 12345,
     "task_id": "ASSIGNED-TASK-ID",
     "owned_paths": ["scoped/**"],
     "docs_read": [
       "AGENTS.md",
       "coordination/OPERATING-MODEL.md",
       "coordination/RESOURCE-POLICY.md",
       "coordination/ROLE-CONTRACT.md"
     ],
     "read_acknowledged_at": "2026-10-05T14:00:00Z"
   }
   ```
4. **Declare Work Scope**:
   Interactive sessions declare scopes via `aplexer work join <workspace> --task "<task_id>" --mode <edit|read|review> --paths "<paths>"` before file modifications.

---

## 4. Distinct Review Gate Protocol

No task may be marked `accepted` or `completed` in `TASKS.json` or supervisor state without an independent review receipt:

1. **Implementer Completion**:
   Implementer runs tests, commits to isolated branch, writes `task_terminal_receipt.json`, and notifies Project Head.
2. **Reviewer Dispatch**:
   Project Head dispatches an **independent reviewer** (distinct subagent, process, or session).
3. **Review Execution**:
   Reviewer checks the exact commit pin, runs unit tests, runs negative tests (bad input, secrets, push failures, conflicts).
4. **Structured Receipt Generation**:
   Reviewer generates `task_review_receipt.json`:
   - If `ACCEPTED` with exit code 0 and verified checks -> Head integrates and pushes to GitHub.
   - If `REJECTED` -> Head dispatches an implementer for repair.
5. **Supervisor Ingestion**:
   Supervisor ingests both receipts, validates that the reviewer is distinct from the executor, and unblocks dependent tasks.
