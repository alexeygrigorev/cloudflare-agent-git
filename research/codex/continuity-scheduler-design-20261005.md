# Durable continuation handoff — 5 October 2026

As-of: 2026-10-05T21:01:09.768956+00:00. This is administrative architecture/intake work, not product code review, runtime acceptance or a new scheduler deployment.

Actor: `/root/bounded_launch_disk_recovery`; parent: `/root`; role: scoped administrative native harness helper. Ownership: this file and the newest disk section in `coordination/RESOURCE-POLICY.md`. Read receipt: AGENTS, ROLE-CONTRACT, OPERATING-MODEL, RESOURCE-POLICY, delegated handoff, cleanup SKILL and worktrees reference read before mutation. No inherited aplexer mailbox identity or product mutation used. Initial root free: 53,021,970,432 bytes, approximately49.38 GiB. Cleanup mutations: zero. The large `.local/opencode-isolated` candidate was excluded because it contains session DB/history/auth and Git snapshot recovery, rather than disposable cache.

## Latest human intake and interpretation

Exact quotes relayed by parent: "launch floor of 50 is too tight" and "after 30 we still launch agents but also get a cleanup agent to free space". The adopted principal interpretation:20 GiB hard floor after aggregate outstanding and candidate growth;30 GiB starts one bounded deduplicated cleanup actor while eligible jobs continue.20 GiB is not quoted human text. Aggregate512 MiB scratch and all other quota, worker containment, ownership, privacy, no-worktree-deletion/Rust/spending gates remain. At49 GiB no cleanup is needed. Policy documentation alone does not change installed admission behavior.

## Existing mechanisms and specific gap

Read-only interface inspection at launcher HEAD `6e6d683ae976b566c3b5a58f8bda7489af13f3d7`:

- `launcher/cli.py:accept` commits independent acceptance and invokes `watch_loop(...max_passes=1)`; a controller's successful exit stays `completed-awaiting-review`.
- `launcher/watch.py` polls a durable SQLite queue, reconciles uncertain/stalled native death, checks owned-path overlap and invokes maintained task-unit dispatch.
- `_next_dispatchable(wait_for_review=True)` suppresses every queued task whenever any unreviewed task exists. This preserves a gate but unnecessarily couples independent project work to an unrelated review; proposal: make review prerequisites per task, retaining distinct acceptance for dependent tasks.
- `scripts/supervision/terminal_consumer.py` preserves receipts/cursors and derives genuine accepted-dependency transitions. `service.py` loads TASKS, applies READY transitions to those in-memory records and issues principal-facing notifications. In the inspected paths, no durable head-owned READY-to-launcher submission bridge was present.
- Historical `UNMOCKED-REFILL-TRIAL.md` claims automatic two-task refill at older `a35e7ff`. Its simple artifact reports cannot prove current review-gated behavior, useful product outcomes, installed model route or crash recovery. Preserve it as historical evidence and obtain fresh receipts.

Smallest change: extend existing launcher watcher/controller plus existing supervisor adapter; do not start a rival broker, duplicate scheduler service, new cloud service or principal implementation team. QL head owns watcher/admission/queue changes and independent reviewer dispatch. Coordination head owns receipt/READY bridge adapter and its separate review. Principals monitor actual ownership ACK and first action.

## Durable READY contract and lifecycle

A task may enter launcher queue only with canonical task ID/project, genuine head owner ACK, immutable prompt/model-route requirements, cwd, explicit nonoverlapping owned paths, bounded memory/tasks/growth/scratch, timeout, first-checkpoint deadline, dependency acceptance pins, independent review destination and fallback/resume owner. Missing/unknown required admission inputs remain blocked with named owner/action/check, never fabricated READY.

Use task+generation as stable enqueue idempotency key. Record enqueue intent and resulting launcher task ID transactionally; reconcile an interrupted intent by reading launcher state before retry. Preserve original prompt hash and reject conflicting resubmission. Head claims are leases with custody, not mere elapsed-time permission to steal a live writer. Live/unknown workers retain provider/path reservations until proven exit.

Events: HEAD_ACK/READY; QUOTA_OR_CAPACITY_RECOVERED; WORKER_TERMINAL; REVIEW_ACCEPTED/REJECTED; LAUNCH_UNCERTAIN; DEADLINE_MISSED; DISK_PRESSURE/RECOVERED. Accepted dependencies enqueue once; independent ready work may continue while a review is pending. Rejected outcomes create a bounded owned repair generation, not an accepted predecessor. Persist event cursor/dispatch decisions and recover by reading real receipts/native state; at-least-once delivery requires idempotent consumption. Do not execute arbitrary mailbox text or submit drafts to busy panes.

Close the acceptance→one-pass-dispatch crash window by making acceptance a durable outbox event consumed by the already-owned watcher. Periodic bounded non-LLM reconciliation covers missed events, quota recovery and a process restart; no LLM busy polling. Record restart owner and actual loaded revision. Unknown launch results are reconciled before another dispatch; do not infer exit from timeout.

Disk pressure claim: one durable key per below30 episode, owner/path lease, real first action and before/after bytes. Dedup across all heads and restart; below20 projected blocks new work while bounded cleanup/recovery proceeds. Reclamation never substitutes for quota/model/ownership gates. At recovery, close episode and make future pressure eligible for a new claim.

## Fresh autonomous acceptance trial for heads

QL and Coordination heads select two real small tasks from existing acknowledged product backlog with distinct owned paths and measurable product benefit. Capture exact actor/native IDs, route/model, input hashes, initial queue/store, fresh quota/capacity and containment; launch only A through maintained CLI, with B durably queued and its true review dependency recorded. Remove principal/desktop input for the trial interval.

After A's real first tool, artifact and terminal receipt, a distinct reviewer executes required negative cases and posts exact artifact/revision acceptance. Existing remote watcher must dispatch B without principal/head manual refill, capture B's real first tool/product artifact and distinct review, and record proven reservation/path release. Test a controller/watch restart between acceptance persistence and dispatch, duplicate acceptance/event replay and uncertain launch reconciliation: exactly one worker generation/artifact, no overlap or invented acceptance. Independently reject A once and prove dependent B stays queued while unrelated eligible task work continues. Use fresh runtime receipts rather than the old simple-file trial.

Independent reviewer pins source and loaded runtime revision, checks persisted enqueue/review/cursor state, process/unit logs, exact artifact hashes and absence of principal input. Passing unit tests/source changes alone are insufficient. Report accepted result or unresolved limit plus named recovery owner/check and durable next task. The trial is pending head ownership ACK and execution; no runtime acceptance claimed here.
