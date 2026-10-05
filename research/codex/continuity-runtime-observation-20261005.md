# Continuous-system runtime observation — 5 October 2026

Observation window: 21:40:49–21:42 UTC (23:40:49–23:42 Berlin). Actor `/root/two_hour_agent_counts`, parent `/root`, independent scoped native metadata helper. Owned path: this document only. AGENTS, ROLE-CONTRACT, OPERATING-MODEL, RESOURCE-POLICY and scoped handoff read. Read-only metadata/receipt audit; no product code review, tests, dispatch, mailbox actions, readiness override, signals or service changes. Existing healthy peer work preserved.

## Verified facts

| Claim | Actual private evidence | Bounded conclusion |
|---|---|---|
| Supervisor is running | `/proc/2535765`, command `python3 scripts/supervision/service.py`, cwd this repository, process start 21:26:01 UTC; parent PID2535754 is `aplexer worker --id 0a7d1367-93c2-42fb-8e3b-728c6de179d8` | Real supervisor process exists; supplied PID2535739 is absent and must be corrected |
| Supervisor has continuous ticks | `.local/supervision/status.json` tick21:40:21.896165 and next tick21:41:22.351773 UTC; fresh event/state file writes | Two consecutive cycles observed; both have `degraded:true`, `actions:[]`, `ingested_launcher_tasks:0` |
| systemd supervises the worker process | `systemctl --user show supervision.service`: MainPID0, active/exited; wrapper PID2535601 ran21:26:01–21:26:02 UTC, exit0 | Unit is a completed launcher wrapper, not a live systemd MainPID for the Python loop. Automatic recovery on worker death is unproven by this status |
| Source provenance | Commit `ae8dbd601a003578f57844bc69b446a94c43bedb` timestamp21:26:54 UTC; current `service.py` SHA256 `9811291c6ffacc902bde4fcd4c2b5122e6003e6978da367a48f58f25b6452011`, mtime21:21:56.962757 UTC | File existed before process start, but process started before the commit. Commit timestamp is not proof of loaded source |
| Startup provenance receipt | `events.jsonl` service-started21:26:02.557464 UTC records identity0a7d1367 and `binary_sha256:fd6fd0ce218f6256442193e0d078467ad74830615ce87435053d7450a41279bd` | Receipt does not identify this digest as loaded Python source/bytecode; it differs from current source hash. Exact loaded-source provenance remains unknown without a typed startup source/revision receipt |
| READY bridge queued work | 36 `task-ready-enqueued` events since21:26, with `launcher_submitted:true`; first event task`frozen-harness-consumer`, head`zcode-independent`, key`ql-enqueue-frozen-harness-consumer-0c20bc80b6ed` | Submission was real, not merely an event label: canonical launcher DB corroborates36 queued rows |
| Queue actually executes unattended work | Read-only SQLite samples at approximately21:41 and21:42: `/home/alexey/git/agent-quota-launcher/.local/launcher-config/state.db`: queued36, completed-awaiting-review19, failed10; no starting/running/accepted rows | Zero new executing task transitions observed in this canonical queue. No corresponding unattended first tool/result was established. This does not assert whole-host zero work |

The DB is in the **Agent Quota Launcher repository**, not this repository's `.local/launcher-config`; the latter path is absent. DB recent queued timestamps remain21:26:03 UTC across observations. The process query showed the supervisor Python loop but no command matching `launcher watch` or `launcher controller`; that bounded pattern check is not an exhaustive service/process census.

## Wake and response evidence

At second tick21:41:22 UTC the supervisor records:

- Codex principal session`93cf28f2-2872-411c-a5da-179e1b83b59f`: reported working but composer`menu-or-draft`; pending`01a10df8-934b-72b2-b893-03bfd2d98a11` blocked beyond300s, age725.78s. Preserve draft; a pending inbox envelope is not a successful wake.
- Coordination head`8d4c026c-b1f9-4cbf-83bf-4f5f82077cab`, QL head`750580e1-4089-4884-a04d-a5e85fbe1f1c` and publication`088a2387-89e4-468b-9ca5-20be7ffec202`: reported idle, composer unknown, zero ready snapshots; pending age907.88/907.57/907.67s respectively. No completed wake outcome demonstrated.
- Restored Ant head`36751672-c403-4ea8-9f53-9a0466434a37`: reported working, status ok, no pending. Message`01a10dfc-44c7-7541-b00b-cfcbbe856316` was recorded21:33:19.007822 UTC and exact consumer-cursor ACK21:34:19.490996 UTC. This confirms mailbox consumption by the exact recipient, not semantic ownership or a new worker first action. Recorded envelope digest`3a24467fd8039236d76a6b9596a6f9012ceb8e3dde68bd17b8f396322956b172`.

No mailbox identity was borrowed or mailbox operation performed by this auditor. The existing supervisor observations may have stale or incomplete readiness inputs; they are reported as observations, not permission to submit input.

## A/B trial scope and outstanding runtime gates

Trial DB `.local/scratch/fleet_work/trial_config/state.db` has exactly two accepted tasks. A accepted21:13:57 UTC; B accepted21:18:40 UTC. `REV-QL-TRIAL-TASK-B-20261005.md` explicitly records a parent/head command at21:13:53 UTC: `launcher accept --id ql-trial-task-A --reviewer reviewer-7f24768e-d40d`. Its embedded one-pass watcher dispatched B. Therefore real review-gated refill after an explicit head acceptance command is supported. An unattended reviewer receipt -> persistent watcher -> next useful task after head/principal absence is **not** established by that trial. Preserve the accepted bounded result and narrow the continuity claim.

The inspected runtime evidence establishes persistent supervision cycles, actual durable submission, one restored head's exact consumption and the earlier acceptance-triggered refill. It does not establish autonomous queue launch/review continuation during this observation, loaded-source fingerprint agreement, automatic service/process recovery, or quota/provider/host-downtime handover. Ninety source tests cannot substitute for those runtime outcomes; no tests were run by this helper.

Next owner/action: QL head and restored Ant head reconcile canonical queue/watch custody and perform one existing acknowledged task's unattended first tool -> useful artifact -> distinct review -> next-task trace. Publication/Coordination heads own their blocked wake/readiness diagnosis; principal owns cross-team follow-up while preserving drafts. Head team independently verifies exact runtime startup source digest, process recovery and one fresh quota/downtime fallback trace before claiming continuous-system acceptance. This is a handoff recommendation, not a claimed ACK, launch or fixed failure.
