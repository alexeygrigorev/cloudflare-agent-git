# Research: making a human request reach an accepted outcome

Authority: [verbatim human request](../../experiment/human-request-outcome-process-20261007.txt). Research completed7October2026 using primary documentation and a read-only audit of existing maintained code. This is mechanism research and a proposed operating contract, not a claim of installed enforcement. No new workflow platform, service, cloud purchase or product implementation was performed by the research helpers.

## Findings

The missing link is a durable obligation with a monitored next transition. A message may be delivered while its owner never reads it; an owner may ACK without starting; source may pass tests while the installed process stays unchanged; a completed task may never reach review or refill. Durable state, semantic evidence, due timers, fenced recovery and separate acceptance must cover every transition. Better prompts and additional reminders cannot replace these mechanisms.

The contract is not a guarantee that every request is feasible. Acceptance objective: no authorized request silently disappears; it becomes owned useful execution, an executed repair/handoff, or a concrete, prepared decision outside current authority. Current incomplete enforcement does not yet provide that guarantee. The human must not be the timeout, missing-owner detector or routine scheduler.

## Primary-source evidence and design consequences

| Primary source | Relevant mechanism | Project adaptation and limitation |
|---|---|---|
| [Temporal Event History](https://docs.temporal.io/encyclopedia/event-history) | Durable event history supports resuming orchestration after process loss | Preserve intake/assignment/ACK/action/result/review/recovery events in the existing store; reconstruct obligations from records. Do not install Temporal. Persist actual model output/tool intent rather than re-asking a model and calling it deterministic replay. Orchestration history does not prove external effects succeeded. |
| [Temporal activity failure detection](https://docs.temporal.io/encyclopedia/detecting-activity-failures) | Separate waiting-for-worker, per-attempt, overall-task and heartbeat timeouts | Distinguish missing owner/first action from slow useful computation; bound total retries. Requeueing the same failed route does not establish recovery. A task-specific checkpoint is needed, not just delivery age. |
| [AWS transactional outbox](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html) | Commit state change and notification obligation together | Existing dispatcher consumes a committed obligation; stable IDs and recipient dedup preserve retries. Separate task JSON and message writes are not one transaction. Delivery can duplicate; idempotent receivers remain necessary. This is a design reference, not authorization for AWS deployment. |
| [AWS Builders' Library: safe retries](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/) | Stable caller intent keys make supported repeated operations safe | Keep request/operation ID and parameters across retry; reject same key with changed intent. Reconcile an ambiguous mutation's receipt/actual state first. Targets without this contract cannot provide universal exactly-once effects. |
| [etcd lock and fencing example](https://github.com/etcd-io/etcd/blob/main/contrib/lock/README.md) | Writes validate a lease's fencing generation | Every owner transition/integration write rejects an older epoch. Merely expiring a lease cannot stop a paused worker from later writing; validation must exist at the resource. Reuse current role/launcher fencing, not another lock server. |
| [LangGraph interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts) | Persist genuine decision waits and resume stable workflow identity | Capture exact action/scope/authority needed. Ordinary authorized work continues; do not ask approval for routine repair. Resumption may rerun a node, so earlier mutations need idempotency or separation. Do not introduce LangGraph as a competing runtime. |
| [Google SRE alerting on SLOs](https://sre.google/workbook/alerting-on-slos/) | Alert on user-facing service objectives and actionable violations | Measure request-to-owner/start/accepted outcome and recovery bounds. Route violations to the actual repair owner. Aggregate fleet alerts cannot replace each important request's due timer. |
| [Google SRE release engineering](https://sre.google/sre-book/release-engineering/) | Pin repeatable releases and deployed configuration | Review the exact artifact, record the loaded version/configuration/store and verify installed behavior. A source commit or reload does not prove a useful task/continuation outcome. |
| [Google SRE monitoring](https://sre.google/workbook/monitoring/) | Fresh structured observations distinguish diagnosis from health counters | Use event IDs, task/generation, outcome and coverage; derive actionable metrics from the same evidence. Process presence/aggregate running labels do not prove execution. Stale observations can prompt incorrect recovery. |
| [Google SRE eliminating toil](https://sre.google/workbook/eliminating-toil/) | Repeated manual interventions indicate work to automate or eliminate | Count human reminders/manual rescues, investigate repeated patterns and repair the maintained path. Additional human status messages are not a reduction in toil; automation must retain diagnosability. |
| [Google SRE implementing SLOs](https://sre.google/workbook/implementing-slos/) | Objectives need agreed measurement, ownership and consequences | Initial timing targets are operational proposals for principal/head adoption, not sourced universal constants. Record coverage and misses; a stated target is not an installed timer. |

## Why current controls are insufficient

Read-only audit inspected Hetzner checkout HEAD `0dc65cf72006a7f9352e5270a690ec65bed52bf1`, remote origin/main `8845fce6795eba7b23f0e6c3f4c0cbbea7d4dc0c`, and modified on-disk supervisor source. These are different evidence levels; no running process's loaded Python version was established by this audit. No tests, deployments or product edits were performed.

| Existing path | What source implements | Missing enforcement to verify/repair |
|---|---|---|
| `scripts/delivery/tasks_guard.py`, `validate_task_update`, `safe_update_tasks_file` | CAS/hash, IDs/history preservation, guarded atomic updates | Inspected caller search found tests/docs but no established production wiring. It does not validate genuine ownerACK→firsttool→review→acceptance. |
| Launcher `launcher/store.py`, `transition_task`, `complete_task`, `accept_task` | State predecessor constraints | Accepted state/reviewer string alone do not establish distinct pinned review. |
| `launcher/review_receipt.py`, `validate_review_receipt` | Reviewer independence, first-tool/timing/hash checks | `launcher/cli.py accept` directly calls store acceptance in inspected source; validator coverage of every API is not established. Witness policy requires explicit choice. |
| `launcher/cli.py accept`, `launcher/watch.py _next_dispatchable` | Acceptance/refill and dependency selection | Refill error can be printed while acceptance returns zero; durable owned recovery obligation is not guaranteed. A result may be accepted while continuation fails. |
| Supervisor `bridge_ready_task_to_launcher`, `drain_launcher_queues` | Persistent enqueue receipt and maintained watcher invocation | Candidate-store/direct-SQL selection does not prove authoritative loaded store or an executable owned READY contract. Preserve divergent-store history. |
| Supervisor `idle_episode`, `eligible`, `check_pending_slo`, `task_event`, `recorded_send`, `may_deliver` | Idle/delivery checks, persisted sends, guarded wake | Delivery age/status digests are not comprehensive first-action/progress/review/result deadlines. Existing protected prompt checks must remain. |
| `scripts/supervision/failover_integration.py`, `run_failover_tick` | Role authority integration | Inspected source treats `reported_state=None` as ready and supplies `draft=False, quota_ok=True` defaults. This violates the intended fail-closed contract; distinct review/loaded-path investigation required, not a claimed production incident. Source SHA256 `016a8d671cf5040717df885a0d4f8cef02c83bfb25fc395c06fec62953609669`. |
| Failover `SupervisorBusAdapter.send` | Reuses completed send receipts | Existing unresolved intent without receipt does not appear to freeze resend as main-service `recorded_send` does. Ambiguous-send risk requires owner review and pinned repair before adoption. |

The documented continuation gap showed repeated readiness refusals and escalation to an obsolete owner while watchers kept running. Win35's execution owner completed discovery and then stayed idle; physical secure deployment remained absent. These incidents support transition-level monitoring and received recovery custody. They do not justify bypassing busy/draft/unknown guards, repeating uncertain mutations, adding services or treating manual rescues as autonomy.

## Alternatives considered

- **More detailed prompts/checklists:** useful startup guidance, but a final model turn can still abandon the obligation. Retain as an interface to enforceable state, not the enforcement mechanism.
- **More frequent desktop pings:** catches some failures but creates laptop/human dependency and busy-pane risk. Use event/due checks in the existing owned remote supervisor and verify absent-root recovery.
- **Another monitor or commercial workflow engine:** mature ideas are useful, but migration adds conflicting custody, services, costs and another unaccepted path. Reuse current launcher/store/supervisor/Bus; adopt mechanisms incrementally under existing owners.
- **Automatic unlimited retry/reassignment:** risks duplicate effects, quota breaches and concurrent writers. Use reconciled intents, bounded attempts, validated epochs and genuine handoffs.
- **One root doing all code and reviews:** may hide coordination failure temporarily but serializes work and breaks independent review. Root owns followthrough; heads/executors own implementation and distinct acceptance.

## Recommendation and falsification

Use one request contract and one event-backed transition interface in maintained tools. Assign each missed transition to an existing accountable recovery owner with a due trigger and recorded action. Gate admission and completion on evidence; make failed refill a durable repair obligation. Prove installed writer/launcher/supervisor parity and run representative real-model cycles with the root and principal absent. If requests still require human reminders, stale owners can write, direct acceptance bypasses evidence, or unreceived review/refill obligations vanish, the process is not enforced.

The canonical process/enforcement plan records owners, current evidence, missing work and failure tests separately. No claim of automatic adoption follows from this research commit.
