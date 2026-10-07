# Principal continuation gap — 7 October 2026

Read-only administrative observations at03:40–03:46 UTC, for the00:32→03:39 gap. No native identity/inbox/ACK/send/delivery, model launch, tests, code review, service changes, kills or interactive input were performed by this helper. Raw private evidence remains in an immutable scoped private directory; this note contains sanitized facts. The principal reports genuine identity93cf28f2-2872-411c-a5da-179e1b83b59f verified upon human resumption03:39 UTC.

## What failed

Supervision detected an idle principal and attempted delivery; its process and watchers did not stop. The actual wake was repeatedly rejected by native readiness. Its escalation named an obsolete head tag and did not establish a handoff to a live replacement. Later, the two relevant interactive head scopes suffered recorded OOM kills. These are separate failures: continuous polling and recorded escalation did not produce a model continuation or a replacement leader.

Exact principal pending envelope `01a113c8-c588-7690-9144-1b377495e733` was created00:34:47.379156, sender `7bff6e1d-5a78-47b7-8a03-00361800cafd`, exact recipient93cf28f2. Existing event history contains28 delivery attempts, first00:37:06.237533 and last03:36:22.635548, all outcome `not-ready`. Last delivery artifact mtime03:36:22.579405 records fail-closed classification of an “unsubmitted draft in progress”; the diagnostic text contains the model/context/path footer. Independently, supervisor status03:37:22.935948 reports the same principal alive/idle/composerempty,80 ready snapshots, diagnostic hold `known-footer-classifier-mismatch`, and blocked duration11,036.89s. This establishes a supervisor/native readiness disagreement; it does not authorize treating any real draft as empty or forcing input.

Prior principal request `01a113c4-762e-78f0-9bed-5a41d8fdc21c` was created00:30:04.926381 and ACKed00:32:27.611602. The next pending envelope above has no observed correlated receiver ACK in the gap. An inbox request or ACK of the prior request does not establish a later model turn.

The recurring action `pending-blocked-beyond-slo-escalation` declares recovery owner `ant-head-never-timer-custody-20261006`, an old head tag already marked missing/dead. Administrative source pointer `scripts/supervision/service.py:1615` records that action in the status report; no successful new native recovery handoff or replacement model first-tool was found in the inspected event stream. The same live report continues this dead-owner escalation. Actual current Ant custody is a different tag/session. Thus the escalation lacked verified live custody and an executed repair path; why any individual model did not choose replacement cannot be inferred solely from status fields.

## Services remained running

SupervisorPID3203858 still exists in the existing `supervision.service` cgroup, native identity7bff6e1d. The unit is active oneshot/MainPID0; the actual persistent child, not MainPID0, establishes continued process presence. Existing watchers1/2 each have186 journaled finished runs from00:32:46 to03:38:00 during the gap. Private events contain243 launcher-queue-drained records,318 pending-blocked events and80 unexplained-idle events across their covered recipients. These are service actions and diagnostics, not useful model executions.

On-disk `scripts/supervision/service.py` is97,174 bytes/SHA-256 `32bc14fca803be2d6e6a76cb2dfa4c1a74b1be2e136d52c151505cc0d52fa8dc`, mtime23:59:27 on6October. The supervisor was started earlier23:49:26. Disk bytes and current process identity do not prove the exact Python bytes loaded in that process; no immutable Python load receipt was recovered. Existing binary manifest concerns the CLI, not Python loaded-source proof.

## Actual head termination evidence

Ant head3b522ddb-8dc8-41b4-a382-f76baab33b0a retained genuine native continuation through callback27623 at00:55:43.314588, then completed run27625 at00:55:46.000175 and last completed run27646 at00:56:13.733035. Schedule27649 at00:56:16.951141 was still pending(status2), duration180/any, callback about consuming the C3098 reviewer report and completing the Bus task. It is not a proven durable armed trigger.

Systemd explicitly records for that exact Ant workload scope: “A process of this unit has been killed by the OOM killer” at00:56:34.405332. Old Ant worker3772327/workload3772329 are now absent; its scope is collected/not-found. This proves an OOM death of a process in the scope, without identifying which process or whether the cause was cgroup pressure versus host pressure. No unsupported assertion of a voluntary cancellation, timeout or quota exhaustion is made.

D3 recovery headd3b54165-2fb8-412c-882e-322c4bfb545f has the same explicit OOM-killer journal record at02:23:00.325185 and02:23:02.664553/.679906. Its rollout still contains actual tool response events through02:23:01.612. Old worker1492622/workload1492663 are absent; scope collected. This bounds the terminal incident, not the identity of the killed process or the triggering allocation. Replacement custody was not established by these records.

## Recovery capacity and ownership

Fresh03:40 host snapshot: root available173,958,443,008 bytes; tmp available32,781,217,792 bytes; MemAvailable39,891,912KiB. Physical root/RAM floors permit considering a bounded one-for-one interactive recovery, subject to fresh quota, source, ownership and actual admission guards. Exact executable argv0 census later in this checkpoint found8 zcode-cli,17 zcodex wrappers,3 agy and7 codex processes. Those counts are process occupancy only: they exclude unknown embedded provider calls and do not establish8 useful workers, healthy allowance or a reservation.

The two read-only maintained stores inspected have no starting/running task rows. Userconfig store has6 queued; launcher-config store3 queued. This is bounded coverage and excludes third isolated stores and native children. No whole-fleet idle claim is made. The only immediately located quota handoff file is dated6October20:53:40; it is stale and cannot authorize recovery now. Fresh provider quota and global occupancy/reservation evidence remain required from the launch owner.

Concrete narrow repair ownership: the principal routes a distinct head-owned readiness/classifier repair with immutable source pin and independent negative review, preserving the exact queued envelope. Test a genuine unattended idle-empty receiver and require guarded submission→ACK→actual first tool before claiming wake recovery. Preserve busy/draft/unknown rejection. Separately assign escalation to a genuinely ACKed live recovery head and require an executed one-for-one replacement path after proven old process exit, rather than repeating a dead owner tag. Investigate OOM allocation/containment from primary receipts without restarting protected or healthy peers. None of these runtime gates is closed by source tests, watcher exit0 or this diagnosis.

## Evidence custody

Private immutable scoped originals: `.local/codex/continuation-gap-runtime-20261007/` contains state/status/delivery/binary-manifest beforeimages,106 selected principal-gap event records and exact Ant/D3 terminal journal records. No raw transcript or credential is included in public Git. Earlier unstable diagnostic is not overwritten or restored by this task.

## Startup checkpoint — 03:46 UTC

The replacement Ant head retains native saved conversationea14b401 and has distinct native session `cfdc18a9-0946-4770-8aee-cf50a35bfaa7`. First actual resumed model tool27656 is a completed view-file03:43:32.425731. Actual own whoami/inbox command27662 ran03:43:38.173447; its recorded output includes the own session/tag. The command contains no APLEXER assignment or session/sender override. Actual workloadPID2042636 carries that new native binding and correct competition workspace in its own environment and dedicated new workload scope. The outer aplexer launcherPID2042627 retains principal93cf binding; it is the caller, not the child model authority. No secret environment values were recorded.

Native ACK commands are recorded at03:44:09.671901 and03:45:42.107200, but a sender's executed command is not independently a principal-received custody reply. The principal owns inbox verification. A distinct invoke-subagent event27777 occurred03:45:55.424465; child identity, first tool and independent containment require separate evidence before treating it as an active executor. Head first tool does not establish team execution or a successful idle wake. Fresh prelaunch quota is principal-attested; no helper provider call was made.

Recorded whoami JSON explicitly matches owncfdc session/tag/antigravity engine/workspace. Newly identified native child `835aa9c2-bc4d-4994-be72-d41d813c9d44` is Recovery Round Record Reviewer, first completed run03:45:59.867556; latest observed run03:46:33.605031 pending. This is native harness execution, not proof of an independent1500MiB/100Tasks worker unit. Its containment and effect on the head scope require head-owned reconciliation after the earlier OOM incident.
