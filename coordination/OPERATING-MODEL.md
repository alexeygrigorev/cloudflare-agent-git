# Responsibilities and continuous execution

## Accountability

| Role | Responsible for | Required output | Continuation responsibility |
|---|---|---|---|
| Desktop orchestrator | Independent remote oversight, experiment records, observability, user decisions and substantive challenges | Measured audits and corrections; public evidence reviewed separately | Own private metrics/supervision services; do not become routine task scheduler |
| Codex principal | Monitor Grok, ZCode and Bunny; cross-team task flow; selection integration; coverage if peer unavailable | Ready/blocked/review queue, ownership, first-action checks, acceptance and next mutual check | Inspect every team at meaningful events and at most5min during useful work; route through heads and correct stalls |
| Claude principal | Monitor Antigravity and Muse, independent selection challenge, integration/resource review | Compact independent verdicts and explicit next corrective action | Focused event consultations rather than expensive constant LLM polling; Codex covers while draft/user input blocks safe continuation |
| Project head | Concrete project goal, backlog, workspaces, task decomposition, worker/harness delegation, provider choice, code recovery/integration | Owned task with acceptance/falsifier; registered delegates; verified artifacts/tests; next task | Maintain useful ready work, handle completion immediately, recover bounded failures, pursue independent work on dependencies |
| Executor | Implement/research/test its explicitly owned task; retain recoverable code/evidence | Actual changed artifact and reproducible checks; no fake success | Update task state/usage evidence; deliver result and request or choose next authorized owned task |
| Independent reviewer | Verify pinned revision, assumptions, failures and acceptance | Verdict with exact revision/test/result, negative evidence and residual risk | Review queue plus independent validation; no indefinite passive wait |
| Observability service | Lightweight factual collection and safe principal notifications | Private time series, state/attribution/coverage, durable receipts/errors | Runs between model turns; no LLM work or state spoofing |
| Daily writer | One evidence-checked public report in Alexey's voice | Actual Opus draft, full stylint and editorial approval | Separate09:30 workflow; not a principal or product executor |

Principals share overall coverage: if one is blocked, the other temporarily monitors its teams and records the reason. A role is not a claim of validated selection. Heads may revise team assignments with explicit handoff and measurable rationale. Do not create duplicate implementation owners merely to increase headcount.

## Task contract and loop

Each task records id/team/owner/status, next_action, acceptance evidence, blocked_on, timestamp, executor identities and pinned evidence paths. Statuses: queued, ready, running, review, blocked, done, cancelled. A principal dispatch and a receiver ACK are distinct; the initial registry includes proposed assignments that owners must acknowledge/update. Running requires actual first action, and done requires accepted evidence. Each head owns its team's entries; serialize shared JSON edits with .local/task-registry.lock and atomically replace files. Preserve other owners' entries. Native subagents get parent and team identities and cumulative usage source where available.

At each completion: checkpoint/output -> independent review when material -> update task -> release ownership -> choose next ready task or unblock another team -> native handoff -> verify first action. Do not end on 'waiting for review' if independent useful work is available. A long model computation/build can be legitimate work without new commits; use multiple signals and record uncertainty instead of restarting it.

Lightweight services poll every60s. Principals investigate unexplained idle beyond5min and stale/no-output tasks according to task-specific expected checkpoints (initial20min default, adjustable with reason). Heads aim to have the next action queued before completion and follow up within5min. These are initial operational SLOs, not fabricated assurances; dashboard must show misses. Waiting because the experiment is genuinely finished, resource/quota hold, protected user draft, or an external decision is a named exception, not a hidden idle interval. Principal coverage and an independent task should still be considered. Do not turn the experiment into token-burning polling.

## Internal dashboard and data

Private .local/metrics and .local/supervision only. Never expose a public metrics port or raw transcripts. Access localhost through SSH forwarding. Track unique live agents versus actual workload PID and hook state, known working/idle/blocked/unknown, per-team counts, unregistered agents, task throughput/cycle/review/block times, useful evidence and corrections, failures/retries, quota windows, CPU/RSS/free disk, measured provider/model token usage/cache usage and reported cost when available. Attribution and measurement coverage accompany every total; shared agents/team totals are non-additive, and global totals deduplicate session/conversation/response identities. Quota changes are account-wide and are not billed cost or experiment token counts. A leaderboard by tokens/commits alone rewards waste; report accepted outcomes alongside effort and negative results.

Collectors retain per-snapshot UTC timestamps and monotonic accounting, versioned JSONL plus bounded rotations with retention manifest. Preserve export/history for the final experiment analysis. Missing metrics are null/unknown, not zero. Backfill only from actual observed private usage records with explicit interval/source/provenance and deduplication. Keep the public journal based on separately reviewed sanitized evidence.
