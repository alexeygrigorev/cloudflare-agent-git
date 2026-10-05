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

The same interval with `journalctl -k` returned no matching OOM/kernel records. Thus kernel victim PID, signal/exit code, memory-cgroup versus global-host OOM, and the exact allocation responsible remain **unknown**. The explicit service-manager OOM receipts establish that a process in each scope was OOM-killed; they do not establish that every native child was killed, or which child triggered pressure.

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

Next check belongs to the surviving recovery head: obtain actual renewed runtime/cgroup and fresh admission receipts, reconcile former child status and artifacts, independently verify useful completion→review→next-task continuation, then update the principal. Memcg/global trigger, victimPID, and aggregate native-child attribution remain unresolved until stronger receipts exist.
