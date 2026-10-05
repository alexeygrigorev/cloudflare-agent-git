# Head runtime-loss observation — 5 October 2026

Sanitized metadata audit by native harness child `/root/head_runtime_loss_audit`, parent `/root`. Scoped read-only diagnosis; the sole authorized mutation is this file. No native mailbox authority, launch, signal, reload, build, install, product review, or registry modification. No commit.

## Startup receipt

First tool used `exec_command` with `login=false`, confirming `/home/alexey/git/cloudflare-agent-git`. Read AGENTS.md, ROLE-CONTRACT.md, RESOURCE-POLICY.md, OPERATING-MODEL.md and the parent scoped handoff; initial combined output was truncated and scoped rules were reread before this mutation. Ownership/read ACK sent to parent through native collaboration, not aplexer. Known parent gates: Codex seven-day 49%/status ok and root 53,844,668,416 bytes at 17:23 UTC; these are supplied observations, not this audit’s dispatch authorization. Output budget <=1 MiB; no copies or separate audit-file mutation.

## Exact loss receipts

The accessible **user service-manager journal**, rather than the kernel journal, provides these events. All are 2026-10-05 UTC, `_PID=1339`, `_SYSTEMD_USER_UNIT=init.scope`, `_TRANSPORT=journal`:

| Native session / workload scope | Timestamp / journal realtime microseconds | Receipt |
|---|---|---|
| Ant `5e1abcdb-44d3-44c9-ba20-eb21f6235672` | 17:21:03.463648 / 1791220863463648 | `aplexer-workload-5e1abcdb-44d3-44c9-ba20-eb21f6235672.scope: A process of this unit has been killed by the OOM killer.` |
| Ant same scope | 17:21:03.695258 / 1791220863695258 | Consumed 19min 41.226s CPU time, 1.4G memory peak, 0B memory swap peak. |
| QL `a86056b5-8b6b-403a-9b8f-6f0b49308959` | 17:21:59.653342 / 1791220919653342 | `aplexer-workload-a86056b5-8b6b-403a-9b8f-6f0b49308959.scope: A process of this unit has been killed by the OOM killer.` |
| QL same scope | 17:21:59.986099 / 1791220919986099 | Consumed 51min 6.084s CPU time, 1.4G memory peak, 0B memory swap peak. |

Reproduction: `journalctl --user --since '2026-10-05 17:19:00 UTC' --until '2026-10-05 17:24:00 UTC' -o json --no-pager`, selecting only MESSAGE entries containing the two exact scope UUIDs and emitting the fields above. Avoid broad historical MESSAGE dumps: unit start records can contain private prompts.

The initial unprivileged `journalctl -k` query returned no matching records. A subsequent authorized `sudo -n` kernel query independently confirmed the workload victims and memory-cgroup limit exhaustion; see the supplement below. The initial empty query was an access/coverage limit, not evidence of absent kernel events. It remains unknown which allocation or child activity created the pressure, and whether every native child was killed.

## Lifecycle and containment

At 17:25:55 UTC `/proc/1626757`, `/proc/1626781`, `/proc/1751879`, `/proc/1751920` were absent. Native retired-session metadata exists at `~/.local/state/aplexer/retired-sessions/<UUID>/tombstone.json`:

- QL: cause `finished`, finished_at_ms 1791220920019 (17:22:00.019 UTC).
- Ant: cause `finished`, finished_at_ms 1791220863740 (17:21:03.740 UTC).

`finished` is registry retirement metadata, not successful product completion. Preserve these former identities and prior history references.

Existing saved launch metadata `.local/codex/handoffs/quota-launcher-head-gemini-C2567-start.private.json` and `.local/codex/handoffs/ant-head-ui-recovery-C2568-start.private.json` independently record the exact worker/workload pairs above, `limits.memory_bytes=1572864000` (1500 MiB), `limits.pids=100`, worker cgroup `/user.slice/user-1000.slice/session-8544.scope`, and separate workload cgroups `/user.slice/user-1000.slice/user@1000.service/app.slice/aplexer-workload-<UUID>.scope`.

These are historical **aggregate workload-scope** ceilings. They are not evidence that each native harness child had its own 1500 MiB allocation. Child inheritance/shared containment at the loss instant needs a contemporaneous process/cgroup receipt; it was not reconstructed here. The old cgroup directories no longer exist. Current `systemctl --user show` reports both scopes not-found/inactive/dead, with default `Result=success` and `MemoryMax=infinity`; defaults of an unloaded unit do not override the saved launch limits or OOM journal receipts.

Supervisor `cd6383e6-5626-4b6a-9409-214e0f8bb899` worker3165603/workload3165652 remained present in independent `supervision.service`. Coordination `8d4c026c-b1f9-4cbf-83bf-4f5f82077cab` workload2156730 remained present in its own scope; current saved session metadata records1500MiB/100pids. Presence is survival evidence, not useful continuation acceptance.

## Historical checkpoint and recovery boundary

`.local/scale50/ROOT-25-TRANSCRIPT-EVIDENCE-20261005.json` records checked_at17:22:37.963270 UTC, roster_as_of17:21:24 UTC,25distinct IDs and25with real tool events,7–13calls per actor, first events17:21:11–14 and latest17:21:50–59. The QL scope loss17:21:59 follows that roster instant. Preserve this as the supplied historical25 checkpoint; it does not establish current25, accepted outcomes, or continued head coverage after loss. Ant loss occurred before that roster instant, so the roster is not evidence that the Ant head survived it.

Parent principal states repair will route through the surviving Coordination head, with saved-conversation recovery already authorized. This audit performs no recovery and does not create a competing writer.

Bounded existing-owner options: reconcile current live actors and leases first; preserve saved conversations/custody/cursors; recover the ordinary interactive head conversation under fresh disk/provider checks; delegate concrete tasks through the maintained launcher in separately bounded task scopes, or use limited measured native fanout that fits the aggregate head scope. Keep1500MiB/100Tasks ceilings; do not blindly raise limits, kill unknown work, or treat launched/running labels as progress. Recover one owner per scope and verify identity/ownership ACK, first tool/output, separate review and next useful task before claiming repair. Supervisor/Coord survival alone does not establish these acceptance steps.

Next check belongs to the surviving recovery head: obtain actual renewed runtime/cgroup and fresh admission receipts, reconcile former child status and artifacts, independently verify useful completion→review→next-task continuation, then update the principal. The privileged supplement below resolves the memory-cgroup constraint and victim PID. Aggregate native-child attribution and useful continuation acceptance still require stronger receipts.


## Independently verified kernel supplement — 17:35 UTC

A root-interface monitor report supplied candidate kernel evidence but copied the QL scope UUID tail incorrectly. This audit independently verified the genuine UUID, rather than accepting the reported string. The monitor message is not a recovery-owner ACK.

Exact source: `sudo -n journalctl -k --since '2026-10-05 17:20:00 UTC' --until '2026-10-05 17:23:00 UTC' -o json --no-pager`; narrow local JSON filtering selected only the exact session prefixes/workload PIDs and memory/OOM messages. All following entries have `_TRANSPORT=kernel`:

| Genuine workload scope | Exact event UTC / realtime microseconds | Confirmed fields |
|---|---|---|
| Ant `5e1abcdb-44d3-44c9-ba20-eb21f6235672` | 17:21:03.461991 /1791220863461991 | `memory: usage1536000kB, limit1536000kB, failcnt1144307` (journal spacing omitted here only for compactness). |
| Ant same scope | 17:21:03.463214 /1791220863463214 | `constraint=CONSTRAINT_MEMCG`; both `oom_memcg` and `task_memcg` equal its genuine full workload scope; task `agy`, pid1751920, uid1000. |
| Ant same scope | 17:21:03.463233 /1791220863463233 | `Memory cgroup out of memory: Killed process1751920 (agy)`; total-vm4384032kB, anon-rss1089752kB, file-rss130372kB, shmem-rss0kB, pgtables3368kB, oom_score_adj0. |
| QL `a86056b5-8b6b-403a-9b8f-6f0b49308959` | 17:21:59.639305 /1791220919639305 | memory usage1536000kB, limit1536000kB, failcnt9557664. |
| QL same scope | 17:21:59.653217 /1791220919653217 | `constraint=CONSTRAINT_MEMCG`; both `oom_memcg` and `task_memcg` equal its genuine full workload scope; task `agy`, pid1626781, uid1000. |
| QL same scope | 17:21:59.653248 /1791220919653248 | `Memory cgroup out of memory: Killed process1626781 (agy)`; total-vm5803332kB, anon-rss1035684kB, file-rss131904kB, shmem-rss0kB, pgtables3148kB, oom_score_adj0. |

Full common cgroup prefix: `/user.slice/user-1000.slice/user@1000.service/app.slice/aplexer-workload-`, followed by the genuine UUID and `.scope`. These receipts establish **memory-cgroup-constrained OOM kills of the actual former head workloads**, not global-host OOM.1536000kB matches1500MiB. `anon-rss` is a component, not total RSS; failcnt is not a count of separately killed workers. The aggregate native-child contribution and particular allocation responsible remain unknown. Do not raise the ceilings on this evidence alone.

### New QL generation observed

At17:35:58.593479 UTC, read-only native saved-session metadata and `/proc` independently confirmed:

- Native QL identity `750580e1-4089-4884-a04d-a5e85fbe1f1c`, tag `quota-launcher-head-gemini`, phase running.
- Parent `8d4c026c-b1f9-4cbf-83bf-4f5f82077cab` (surviving Coordination head).
- Worker113405 present **inside the Coordination workload scope**; workload113462 present inside the new QL own scope.
- New QL workload limits1572864000bytes/100pids, separate full scope `/user.slice/user-1000.slice/user@1000.service/app.slice/aplexer-workload-750580e1-4089-4884-a04d-a5e85fbe1f1c.scope`.

Parent reports this generation resumed saved conversation962ee79c-665f-43f2-a809-365701243ddf via Coordination; that conversation claim was not independently inspected here. Native worker custody remains coupled to Coordination containment despite separately bounded QL workload. Safe parent-loss recovery/independence, actual renewed owner ACK, first useful action, and completion→review→next-task continuation remain separate acceptance checks. No runtime or native messaging action was performed by this auditor.


### Installed recovery-tool capability boundary

Read-only `aplexer start --help` completed successfully after the supplement. It documents workload/session resource flags `--memory`, `--pids`, `--cpu-quota-us`, `--cpu-period-us`, plus engine/profile/workspace/cwd/history/timeout/attach options. It documents **no parent-detach, parent-session selection, worker-cgroup placement, or worker-custody independence flag**. `--fresh` chooses a free tag suffix; it does not establish custody independence and is not a recovery solution by itself. No environment/identity override or launch was attempted.

Therefore this CLI help does not provide a supported direct flag to repair the observed worker-inside-Coordination coupling. The existing recovery owner should retain the restored useful session and separately investigate a verified existing independent launch/custody path, or delegate a bounded tool-gap task. A future independent-custody claim needs actual worker/workload cgroup receipts plus tested parent-loss recovery. Choosing another assumed flag, duplicating the live owner, or raising memory limits is unsupported by this observation.


## Ant timer continuity metadata — 18:01 UTC

Parent assigned a separate read-only check of recovered Ant native identity `d78eeba5-7a0a-4b69-8a19-ca9d10b21371`, worker 579273/workload 579323. At 17:59:43 UTC both PIDs were present; workload had no child PIDs at that observation. Saved native metadata recorded running phase, separate own workload scope, worker in `session-8544.scope`, limits 1572864000 bytes/100 PIDs, parent principal `93cf28f2-2872-411c-a5da-179e1b83b59f`. This was liveness, not a continuation verdict.

Private source discovery used only process file-descriptor targets, scoped cache IDs and SQLite metadata. AGY process 579323 held `cli-20261005_194805.log`; its UUID references included supplied resume argument/historical context `245c7bba-9a7b-45c1-87a7-4537f289f9a5` and derived actual provider conversation `ea14b401-20e9-4e48-ab08-d15be08da30d`. Workspace last-conversation cache pointed to the latter. The old conversation DB's latest metadata was 10:51:49 UTC; it could not establish the evening timer. Do not label resumed historical context and actual new provider conversation as the same identity.

Read-only SQLite source: `~/.gemini/antigravity-cli/conversations/ea14b401-20e9-4e48-ab08-d15be08da30d.db`, 4292608 bytes when observed. Selected only recent step metadata and bounded payloads; one last-60-step batch was 345184 bytes. No private prompt/history/environment content was printed or retained. Protobuf metadata timestamps and numeric step types/statuses were decoded; schema enum names were not guessed.

| Step | Type/status | Actual metadata UTC | Safe receipt |
|---|---|---|---|
| 340 | 132/3 | created 17:55:57.192456; execution metadata 17:55:57.339995; completion 18:00:57.387962 | `DurationSeconds=300`, `TimerCondition=any`, task-340 identifier; timer/schedule terms present. Payload 2431 bytes; SHA-256 `57c56ecb46600c51920bd12741e28757c78e9452553d97278088ac07c4298380`. |
| 344 | 101/3 | created 18:00:57.841620; update 18:00:57.841987 | Notification step includes task-340 and timestamp 2026-10-05T18:00:57Z. Payload 895 bytes; SHA-256 `bc95b050f1411cf6b0774b42e6930c8cb0ba80092d49b7ed2f7fc1e85e78c7d2`. |
| 346 | 132/3 | created 18:01:01.961848; completion 18:01:02.070494 | Actual `run_command` tool payload; WaitMsBeforeAsync=5000, IsDaemon=false, RunPersistent=false. Payload SHA-256 `4a62f899aa00d61d0c096b0d1b9fae837d638c14431ef0880c8ddca70aab0fb3`. |
| 349,352,355,358,361 | 132/3 | tool metadata continues from 18:01:05.908853 through completion 18:01:27.147947 | Additional actual post-notification tool steps. |

At 18:01:50.251557 UTC the actual conversation had reached step 371. This is a **real five-minute timer and post-timer head tool continuation**, superseding a proposal-only interpretation. The timer is not an external shell `sleep` child; child absence at 17:59 does not invalidate it. The exact textual timer instruction/notification was intentionally withheld. Status number 3 alone was not interpreted as product acceptance.

Parent independently observed post-timer message show/ACK commands and working screen at 18:01:09 UTC, with original C2652 native NOTREADY preserved and no forced/manual redelivery afterward. That parent observation is separate provenance; this auditor used no native mailbox or ACK authority. This evidence establishes timer→notification→tools ordering, not absence of every other possible model input, useful product delivery, or independently accepted continuation cycles.

Head-owned next acceptance gap: link subsequent useful product tool/delegate first action to owned task, capture terminal outcome and distinct review, then prove the next useful continuation trigger. No timer repair is justified from this passing runtime observation. Preserve the existing head and avoid a duplicate recovery writer. No runtime mutation, launch, signal, build, installation, code review or commit was performed.
