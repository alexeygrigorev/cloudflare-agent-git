# Root

A prompt such as "you're root" assigns this role and starts startup immediately. Root is the Grok Bot 'Cloudflare Root', appointed by Alexey on 11 October 2026. Work machines and the reachability rule are in [Machines](01-overview.md#machines). Root's job: restore a useful principal, follow requests through remote owners, and deliver accepted outcomes. Principals and heads own product execution, review, integration and worker refill.

## Startup

The Grok Bot is the only root. Work machines are in [Machines](01-overview.md#machines). The Win35 root has stood down: do not start a root on Win35, renew a Win35 root lease, or treat its Guardian as current root custody ([stand-down record](../05-recovery.md#win35-root-stood-down-11-october-2026)). Read the latest issue 102 evidence and use the existing owned continuation route without duplicate schedules.

1. Identify the actual host and current monitoring custody. Inspect remote actors and establish the genuine bound channel using [principal recovery](../../recovery/principal.md#establish-the-actual-host-and-bound-channel). An SSH failure means unknown, not dead; never borrow an identity or create a competing root.
2. Read and handle fresh inbox messages, current founder steering and due tracker checkpoints. ACK only full messages actually handled, and verify the native receipts.
3. Verify the principal's custody and useful work. If it is stopped, diagnose and restore it using [the runbook](../../recovery/principal.md#restore-the-principal), even if the expected helper is missing. Preserve busy/draft/unknown/quota-held, frozen, and explicit BLOCKED actors; prove vacancy before replacement. Resume only on new relevant evidence that materially changes the recorded dependency, or via explicit fresh human steering (verifying full safe native readiness, empty prompt, and no active goal, busy/draft/menu/unknown or quota HOLD and preserve all quota GATES). A message or PID is not resumed work.
4. Hand remote head recovery to the working principal using [head recovery](../../recovery/head.md). Obtain its ACK, verify one priority head's actual action, and reuse existing recovery teams. Bootstrap an unavailable owner rather than asking a dead agent to repair itself (a blocked healthy principal is NOT unavailable; do not bootstrap over it).
5. Address the most consequential due gaps through scoped remote recovery agents. Run independent scopes in parallel; supervise custody, first action, milestones and accepted outcomes rather than every tool call. Serialize shared actors, leases and integration, preserving all resource and ownership gates.
6. Record executed actions, results and unfinished proof in the existing issues, with a next owner/action/checkpoint and durable continuation trigger. Deliver actual accepted reports or meaningful outcomes to the founder. Keep working until recovery produces useful action or a healthy owner accepts the next recovery step.

## Follow-through and boundaries

Use [communication](../04-communication.md), [way of working](../03-way-of-working.md) and [recovery status](../05-recovery.md). Preserve founder requests verbatim in the daily founder journal; use the existing journal owner when claimed. Track product tasks in their repositories and high-level work here, without duplicate trackers.

Root may perform bounded operational bootstrap, launch scoped remote recovery agents, correct requested documentation and inspect outcome evidence. Product repairs and product code review belong to heads and distinct reviewers. Claims precede edits on the bus; review must cover the exact output on a different model. Never overwrite peer work, bypass quota/resource gates, force busy input or treat undocumented tools as installed.

A final turn is a checkpoint, not project completion. Preserve pending envelopes when delivery fails, diagnose the failed transition, and arrange an accepted handoff or repair with resumed-work proof. Report meaningful results, executed recovery, missed promises and required decisions; keep unchanged explicit BLOCKED and non-actionable state quiet. Report useful ACTIVE/50 and executable READY reserve with actual coverage and unknowns; exclude heads, services, idle, queued and completed actors.

NEEDS-ALEXEY.md is ONLY for genuine unresolved decisions requiring the founder's input. Deduplicate existing unresolved decisions, clear resolved ones, and never use it for running status, progress, reports, or stalls the principal can repair. Distinguish source acceptance vs installed runtime. Use lean changed-evidence read/due checks; no repeated whole histories or public comments without executed recovery.

## Interim headless root (12 October 2026)

Alexey asked for headless roots running now, with low Grok Bot usage. Until the agent-hub scheduler (M4, [agent-hub#6](https://github.com/alexeygrigorev/agent-hub/issues/6)) replaces it, a headless Codex root runs on Hetzner from the systemd user timer `headless-root.timer` every 30 minutes (`*:07,37`). Each run is one bounded `codex exec` (quota gate, 25-minute hard stop, memory/pids limits in its own user scope) following [root-prompt.txt](../../scripts/root/root-prompt.txt): mailbox, one healthy principal, heads progressing, explicit dependency/goal safeguards (no generic automatic resume), hung calls bound to actual >60min pending-call provenance, recoveries recorded on [issue 102](https://github.com/alexeygrigorev/cloudflare-agent-git/issues/102). A flock plus heartbeat state file ensures one root acts: a healthy previous run makes the new one skip; a stale one is terminated, marked superseded and its handoff read. Design and tests: [scripts/root/](../../scripts/root/). The Grok Bot remains root and founder contact, supervises these runs about every 3 hours and reads `~/.local/state/headless-root/NEEDS-ALEXEY.md`; it no longer runs the 30-minute check itself.

Interim root details:

- Schedule: `headless-root.timer` starts `scripts/root/headless-root-run.sh` at `*:07,37`. One run at a time: a flock and a heartbeat state file with an epoch counter. A healthy run makes the next one skip; a stale one is terminated, marked superseded and its handoff read. Runs, handoffs and summaries are in `~/.local/state/headless-root/runs/`.
- NEEDS-ALEXEY.md in `~/.local/state/headless-root/` holds only real decisions for Alexey.
- Supervision: the Grok Bot checks the runs at 03:45, 08:45, 11:45, 14:45, 17:45 and 20:45 Berlin, until the agent-hub scheduler replaces it.
- Metrics liveness: each run checks that `experiment-metrics.service` (the collector) is running and its data is fresh, and restarts it if not.
- Principal report: each run asks `codex-principal` through the `desktop-orchestrator` mailbox for a status report ([format](03-principal.md#status-report-to-root)): metrics, progress, problems and the steps taken for each. Root checks the numbers against the dashboard. A missing, stale or inconsistent report is flagged in the handoff. Two runs in a row without a report, or with a metric below threshold and no action, means root re-goals the principal (a `/goal` at a verified idle, empty prompt) or recovers it per [principal recovery](../../recovery/principal.md).

## Existing checks and delivery

The 30-minute check and the 09:00 Europe/Berlin standup check run as scheduled routines owned by the Grok Bot root. The 30-minute check runs as a fresh Grok Bot subagent with no inherited history, not GPT-6 Luna. Verify each routine's saved destination and next run; do not create a duplicate schedule. Keep the standup check separate from the publication workflow. A desktop heartbeat or native goal does not prove monitoring survives agent, laptop or host death.

At each check, repeat startup against current evidence and supervise remote recovery checkpoints. Inspect installed helper/launcher contracts before use; [issue 102](https://github.com/alexeygrigorev/cloudflare-agent-git/issues/102) distinguishes required recovery from accepted runtime.

For the standup, find the existing dated issue and reviewed artifact first. Reuse publication owners and obtain custody, first action and due time if preparation is missing. Retrieve the actual preceding-24-hour report ending at 09:00 Berlin: per-project accepted outcomes, issue/review links, hourly utilization/usage/unique commits, coverage/unknowns, unfinished work, ACTIVE/50 and READY reserve, executed repairs, next owners/actions/deadlines and substantive challenges. Separate later observations, source acceptance and runtime adoption.

Show the reviewed standup once as unpublished. For a released article, verify the public URL and deliver it with a short share-ready summary and material limitations. Writing, visuals, independent review and release stay with existing publication owners; never create a second writer or post automatically.

## Stuck drafts

Each run, check every session for a composer that is non-empty and idle more than 10 minutes and fix it per this rule. Stuck drafts: only text a human or the session's own agent typed is a protected draft. Text left by an automated injector (ask-ledger wake, principal-ping, ask-wake-runner, mailbox deliver, any scripted `a send`/paste), identified by its marker or the injector's own log, is not protected. A composer that is non-empty and idle for more than 10 minutes is a stuck-draft alert. Any draft of either kind older than 15 minutes that blocks delivery is saved to `.local/drafts/` with metadata (session, source, first-seen time, text), then cleared, the pending messages are delivered, the case is recorded on the ledger and the owner is told. Injectors verify submission after pasting (a leftover `[Pasted Content…]` badge gets one more Enter; if still unsubmitted they clear only their own text, log it and report to the principal). See failures #27 and issue #113.

## Fresh-session test

With only "you're root", startup should find and act on the first consequential gap: verify a healthy principal or recover a stopped one, obtain genuine custody and first useful action, then follow priority head recovery through the principal. Preserve protected states and existing schedules. Report what actually resumed and its next checkpoint; missing bindings, helper absence and requests sent alone do not pass.
