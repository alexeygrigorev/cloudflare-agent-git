# Safe head continuation and unavailable-provider recovery — 5 October 2026

Author: native helper `/root/head_continuation_recovery`, parent `/root`; scoped independent administrative/research angle. This is a proposed head-owned implementation contract, not runtime acceptance. No supervisor implementation, new service or Rust build was performed.

## Observed failure and actual administrative repair

Existing Ant head `d78eeba5-7a0a-4b69-8a19-ca9d10b21371` completed useful batches then ended at19:08UTC. Its provider timer967 did **not** fail: native task log records a successful one-shot900-second timer firing18:52:39UTC; live trajectory step971 contains its HIGH-priority continuation message. No further timer scheduling follows step967 through final1676. The failure is lack of a durable next trigger after a one-shot completed. Recreating that same one-shot repeats the vulnerability.

Native Stop reported idle1791227310251, while laterPTY activity invalidated readiness. An empty visible composer alone did not authorize native delivery. Existing pending envelope remains pending; its recipient identity cannot be silently rebound.

A bounded administrative recovery preserved private liveSQLite snapshot (`quick_check=ok`), PTY history, session record and timer log (~18.7MB). Supported exact-session TERM stopped onlyd78; workload579323 disappeared and protectedSIGSTOP560857 remained. Successor `36751672-c403-4ea8-9f53-9a0466434a37`, tag `ant-head-continuation-resume-20261005`, started via installed `aplexer start`, headcap1500MiB/100pids. Startup is interactive and resumes livefork `ea14b401-20e9-4e48-ab08-d15be08da30d`, not staleoriginal245c7bba (originalDB ended10:52UTC). KnownGemini57.12%weekly/90.01%5h and currentdisk~49GiB passed the principal's enacted20GiB hardfloor. Startup Working is observed; genuine ACK, useful action and autonomous second cycle remain separate acceptance requirements.

Private admin evidence is under `.local/recovery/ant-head-continuation-assessment-20261005/`; never publish raw histories/logs. Installed AGY hooks have PreInvocation+Stop, which do not independently wake an idle recipient. There is no installedaplexer restart verb. Native fork IDs must be discovered from actual runtime history before resuming.

## Existing service owns recurring mechanical supervision

Use the already-running `scripts/supervision/service.py`, its existingservice.lock and private state/spool. Do not create a parallel scheduler. `run`, `idle_episode`, `task_event`, `check_pending_slo`, `recorded_send`, `may_deliver`, `eligible`, `composer`, `quota_allowed`, and `command` provide the existing seams. `terminal_consumer.py` consumes worker outcomes; `ack_reconciliation.py` preserves exact ACK semantics; `retention.py` handles bounded private retention/storage errors. Heads assign scoped executor and separate reviewer before modifying these peer-owned modules.

Completion/dependency/failure events create one durable action keyed by `(project, task, terminal receipt digest, head generation)`. Existing polling every60seconds reconciles lost events and due actions. It does not spend model tokens just to poll. Persist the next_due timestamp and outstanding action before returning a cycle; service restart resumes overdue actions from that cursor. A callback owner survives model-turn termination; an AGY timer can supplement this but cannot be the sole continuation authority.

Initial operational objective: completion to next useful owned task within5minutes; missed useful idle investigated after5minutes. A known provider/resource/protected-draft hold records reason, repair owner, check deadline, independent criterion and resume task. Mechanical checkpoints repeat while unresolved, without repeatedly launching a model or repeatedly injecting an unchanged message. Unknowns remain explicit.

## Guarded wake and stale-state recovery

Resolve the current registered exact recipientUUID/workspace/generation, verify the service's genuine sender identity, then native read-only readiness plus fresh composer inspection. Native idle provenance, no laterPTY activity, nonbusy phase and empty composer are all required. Deliver the **existing exact queued envelope** once through supported `message deliver`; obtain an ownership ACK and actual first action. Never substitute transport submission for execution. Busy/readiness rejection retains the same envelope and next-check cursor. Delivery uncertain freezes retransmission until reconciled; no second envelope or extraEnter.

A periodic ping is legitimate only when there is a concrete ready queue, due dependency check or owned repair. It must not inject into a busy pane or human draft. Old hook timestamps plus empty screen do not allow readiness fabrication. A capture does not refresh native idle. No hidden hook invocation, APLEXER override, borrowed sender identity or manually reportedidle is permitted.

When native readiness remains rejected because idle provenance is invalidated, record an administrative lifecycle repair rather than weakening eligibility. Recovery requires exact session ownership/custody; no active local or detached workers/writers/tasks; empty draft; preservation of actual livefork/history; known scoped stop semantics and cgroup membership; fresh admission/growth/provider evidence; and safe successor custody. Samehead repeated errors are not grounds to stop unknown children. A timed-out stop or uncertainstart must be reconciled before another launch. Never stop protected46fdb644 or wholeCoordcgroup shared by a QL child.

## Provider unavailable: useful fallback with fencing

A provider error/unknown quota/limit/cutoff fails closed for new work. Preserve useful running jobs and existing private history. The affected head selects a freshly verified eligible preferred alternative through the maintained Agent Launcher, with an explicitly owned ready task and independent reviewer. Existing task IDs, immutable source pins, expected artifact, dirtywork leases and accepted cursor survive; provider identity changes do not imply task ownership release.

Use a single durable generation lease for headcustody and one action reservation per terminal-event key. Before fallback allocation, ensure oldhead is stopped/retired or explicitly relinquishes that specific task; no duplicate writer. New generation records actual nativeidentity/parent/provider, startup receipt, ownershipACK and first tool. A differentprovider cannot claim old mailbox ACKs. Mark superseded requests with an explicit reference, not fabricated delivery to a differentrecipient. The principal owns native routing until the genuine newhead ACKs.

If no provider passes admission, retain a named quota/resource hold and recurring mechanical recheck, continue ready nonmodel administrative work only where useful, and alert the principal once per changed blockage. Do not buy capacity, treat unknown as healthy, exceed fixedZAI26, crossCodex15% or Grok5% cutoff, or count queued/controllers as activeworkers. Projected disk free after outstanding reservations and candidate growth must retain20GiB; below30GiB allows eligiblelaunch plus one durably deduplicated bounded cleanup owner, preserving worktrees and recoverable source. No periodic model-only busywork.

## Independent runtime acceptance: two jobs and failure injection

Head and reviewer must demonstrate on existing maintained infrastructure:

1. A real owned JobA produces an artifact/terminalreceipt, distinct reviewer accepts a pinned change, eventconsumer advances cursor, and head starts useful JobB with genuine firsttool. Principal and desktop provide no manual wake betweenA andB. Observe exact IDs/times, useful outputs and accepted verdicts.
2. Restart the existing supervisor afterA receipt but beforeBdispatch, then again afterBreservation but beforedelivery confirmation. Prove no lost dueaction and no duplicate writer/envelope/job; restart solely uses preserved custody/cursor.
3. Inject busyrecipient, protecteddraft, laterPTY thanidle, notready, deliveryuncertain, mailboxlock, stalegeneration and disk/projectedgrowth rejection. Verify no paneinput or dispatch; owner/check/resume persists. A protecteddraft remains byte-identical.
4. Make the primary provider quota unknown/error/atcutoff. Verify failclosed and a freshhealthy alternate runs the same explicitly handed-off nexttask once; oldproductivejob remains untouched. Repeat with nohealthyprovider and verify truthfulhold plus durable nonmodel checks.
5. Kill/pause the principal's availability without touching protectedpanes. Existingremote service must drive nexttask/recovery and independent acceptance. An installedtimer, PID, sourceunit test or manualorchestrator wake is insufficient.

Head owns implementation/review/integration/recovery; principal monitors ownership, subsequent actual useful cycles and provider/resource evidence. This design's strongest falsification is a supervisor restart producing duplicateB or an unchanged idle head requiring another humanwake.
