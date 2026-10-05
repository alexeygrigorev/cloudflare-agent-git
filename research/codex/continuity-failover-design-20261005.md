# Continuity failover: custody, fencing and bounded recovery

Date: 5 October 2026. Actor: native helper `/root/two_hour_agent_counts`; parent `/root`; role: independently scoped design helper. Owned path: this document only. Read receipt: supplied AGENTS instructions, ROLE-CONTRACT, OPERATING-MODEL, RESOURCE-POLICY and scoped handoff; scheduler plan at `ec4f3bb` read before writing. No product mutation, runtime operation, inherited mailbox authority or acceptance claim. This complements `continuity-scheduler-design-20261005.md`; heads implement and appoint distinct reviewers.

## Decision and observed interfaces

Keep one authoritative queue on Hetzner and extend the maintained launcher/watch and receipt bridge. Principal absence must not prevent execution of previously acknowledged, independently owned work. A head heartbeat timeout must not grant permission to duplicate its still-live workers. Provider handover changes the execution attempt, not task dependencies or review requirements.

Read-only source pins: Agent Quota Launcher `6e6d683ae976b566c3b5a58f8bda7489af13f3d7`; Agent Coordination `eadeaaae91b5a9c3d46215705ed7ef4af047cdab`. These pins identify inspected source, not installed runtime revisions.

- `launcher/store.py` offers exclusive SQLite transactions, guarded task-state transitions, idempotency keys and leased paths. No custody epoch is present in the inspected task schema.
- `launcher/watch.py` reconciles only `launch-uncertain`/`stalled`, using native tag status; independent refill is currently subject to the global unreviewed-task gate described in the scheduler plan.
- `launcher/launch.py:native_status` treats any nonzero status-command return as dead. A transport/tool failure is not death evidence: classify those failures unknown unless a structured exact-identity result proves exit. Tag-only queries cannot replace task-unit evidence.
- `launcher/task_units.py` already compares systemd InvocationID before signaling an owned unit. Reuse that mechanism for orphan recovery, with host boot identity; never signal a reused unit name or PID.
- `scripts/supervision/terminal_consumer.py` validates artifact/review receipts and persists launcher cursors. `service.py` already has a singleton file lock and private durable notification records. Extend these owned mechanisms; do not deploy a competing broker.
- Coordination `NamespacedId`, `SshRelay` and `CursorStore` provide distinct origin/relay identities, offline outbox and idempotent-send metadata. Cursor JSON uses atomic replacement but the inspected implementation does not show a writer lock around read-modify-write: designate one consumer per namespace or add serialized mutation before using concurrent bridges.

## Smallest implementation split

| Owner | First bounded change | Acceptance responsibility |
|---|---|---|
| QL interactive head | Add custody and attempt records to store; fence watcher/controller state changes and recovery; persist admitted alternative routes and cooldown/recheck decisions | Separate reviewer pins source and loaded runtime, runs failure matrix below, verifies real next-task execution |
| Coordination interactive head | Add typed custody/READY/outcome bridge carrying exact task/epoch/attempt/hash; transactional ingest intent and cursor discipline | Separate bridge reviewer verifies replay, forgery rejection and concurrent consumer behavior |
| Each product head | Acknowledge fallback custodian and two existing independent ready tasks with review owner and immutable ownership/resource contracts | Verify first tool/output and integration; no new task invented to fill capacity |
| Principals | Resolve cross-team ownership and monitor successful continuation versus unresolved limits | Receive aggregate receipts; do not implement or personally review product code |

Suggested custody record: project/task, exact head identity, alternate acknowledged identity, monotonic `custody_epoch`, renewal/deadline, permitted scope, immutable task hash and handover reason. Attempt record: task/generation, custody epoch, exact enrolled actor/parent/provider/conversation, host/device ID, boot ID, unit name/InvocationID, process start identity where applicable, first tool, resource/path/provider reservation keys, terminal receipt and reconciliation status. Native helpers receive real child identity; they never inherit the parent's mailbox credentials.

QL uses one SQLite transaction to claim dispatch and write an outbox intent before spawn. Stable enqueue key is task plus generation; a retry must preserve the hash. Spawn outcome unknown retains the attempt and every reservation. Before another spawn, reconcile the exact native or unit identity, not merely a generic tag. A successful result remains awaiting distinct review. Head takeover uses compare-and-swap of custody epoch after explicit handover or verified head death with pre-acknowledged alternate custody. Timeout triggers investigation, not transfer. New controllers reject old epochs; old terminal receipts can be stored as evidence but cannot advance a successor generation or alter current ownership.

Epoch checking fences scheduler transitions; it does not stop an already-running arbitrary filesystem writer. Consequently never launch a successor with overlapping paths until predecessor exit/empty containment is proven. Use existing isolated branches/workspaces for recoverable attempts, checkpoint source, and have the head integrate only reviewed output. An old actor's newly arriving artifact cannot silently become canonical.

## Failure actions and resume paths

| Failure | Immediate bounded action and owner | Resume condition |
|---|---|---|
| Principal unavailable or protected draft | Existing remote watcher consumes acknowledged queue; project heads retain custody and existing review dispatch. Persist notification for principal return; no pane injections | Real next task first tool/output and independent review, without principal/desktop input |
| Head process dies, task worker remains alive | QL reconciliation records custody incident; acknowledged alternate head takes monitoring custody after exact death proof, preserving worker generation/reservations | Same worker completes or is independently proven dead; alternate never relaunches it based on heartbeat |
| Controller/watch dies, worker unit survives | QL reads durable intent plus exact unit invocation. Restore observation under current epoch; no duplicate spawn | Terminal evidence and empty containment reconcile once; next independent task dispatches |
| Worker dies or OOMs | QL records exact exit/cgroup evidence, retains artifacts privately, releases only proven-ended actor reservations; product head chooses bounded repair generation | Repair on verified eligible route, fresh admission, same ownership contract and distinct review |
| Provider quota, 429 or backend outage | QL records provider/account window and Retry-After, stops new admission to affected route; preserve productive running tasks | Fresh healthy alternative, actual supported model and task-compatible requirements, exact route receipt; otherwise durable queue plus timed recheck |
| SSH fails or Hetzner cannot be reached | Coordination records host-unreachable/unknown, persists outbox and cursors, preserves all possibly-live reservations. Continue only unrelated locally owned work | Host returns and reconciles exact attempts, or authenticated evidence proves old host cannot execute before transfer |

A full host outage is different from local process death. With an unreachable primary, automatic reassignment of its writer tasks to a laptop would risk split brain; single-host SQLite and file locks provide no cross-host fencing. The initial accepted scope is autonomous process/head/provider recovery on the existing host plus offline queue recovery, not automatic writable-host failover. Cross-host takeover needs confirmed power/process fencing or an acknowledged quiescence receipt; otherwise hold affected tasks and continue unrelated work. No new cloud coordinator or paid infrastructure is justified.

Provider fallback is limited to actually maintained adapters: inspected launcher supports ZAI GLM-5.3-Flash, Antigravity Gemini 3.1 Pro High and a Grok adapter subject to its freeze. Muse, Space Bunny, Codex Luna and Sonnet authorization alone is not proof of installed launcher support. Heads can use other maintained verified routes only after route-specific integration and review; never raw-provider bypass or silent substitution. Retain shared ZAI ceiling 26, Grok <=5%/unknown fail-closed and actual Codex 15% reserve. Provider account occupancy beyond observed host remains unknown; no inferred free slots from a local empty queue.

Before admission apply newest disk interpretation: projected free after aggregate outstanding and candidate growth >=20 GiB; below30 GiB launch eligible work and one durably deduplicated bounded cleanup actor in parallel. Unknown required growth/free space fails closed. Retain aggregate scratch <=512 MiB, separate worker <=1500M/100 Tasks, applicable scoped RAM policy and all privacy/Rust/spending constraints. Do not delete existing worktrees or histories.

Back up accepted canonical Git source to the existing private independent remote and verify disposable restore. For queue recovery capture SQLite through its consistent backup mechanism plus hash/version/custody cursor manifest, not copying a live DB alone; keep credentials/history machine-local. A restored queue is recovery evidence, not authority to replay all running tasks. Reconcile source host custody/attempts before release or dispatch. QL head owns queue backup/reconciliation; product heads own source backup/restore.

## Negative runtime acceptance

1. Remove principal/desktop input for a bounded trial using two real acknowledged tasks. Head/watcher continues completion -> distinct review -> next first tool and useful output. Do not count a timer, source test or queued status as success.
2. Kill watcher/controller only during a real worker invocation. Restart exactly one owner; preserved worker completes once and queued independent work refills. Inject duplicate terminal/acceptance/READY events across restart: one state advancement and one successor generation.
3. Expire head renewal while its worker is alive. Assert zero overlapping successor launches and retained reservations. After genuine head death, pre-acknowledged alternate custody increments epoch; stale head claim and stale controller mutations fail.
4. Reuse unit name/PID with a different InvocationID/boot/process-start identity. Assert no signal, no reclaimed lease and no false death. Make native status return nonzero or malformed JSON: remains unknown, not failed/released.
5. Simulate SSH partition while old host writer remains active. Assert affected queue is held and offline envelopes remain durable; unrelated eligible task proceeds. Reconnect and replay: original task remains single execution, cursors resume without skipped semantic outcome.
6. Exhaust one provider or return 429; fallback gets fresh account/resource admission and real model/tool receipt, with exact model requirements preserved. Unknown quota, unsupported requested model, ZAI occupancy >=26, Grok frozen or Codex reserve fail closed. Active productive workers are preserved.
7. Restore consistent queue backup; compare manifest and exact attempts, replay acceptance once, and quarantine unresolved old running entries. No automatic release from timestamp age. Check canonical source independently restores from private Git remote.
8. At projected29 GiB prove eligible dispatch plus one cleanup claim; at projected19 GiB prove no new dispatch. Duplicate pressure events/restarts cannot create duplicate cleanup actors or delete unknown-owned/dirty/history/worktree paths.

For every failure trial record exact loaded revision, actor/epoch/attempt IDs, first action and artifact hashes, command/exit evidence, independent verdict, outstanding unknowns, next owner/check and durable resume event. Tests must use isolated owned state and recoverable product branches, preserving healthy current sessions. Heads should report first implementation action and acceptance deadline after genuine ownership ACK; this document is a ready handoff, not an ACK or delivered implementation.
