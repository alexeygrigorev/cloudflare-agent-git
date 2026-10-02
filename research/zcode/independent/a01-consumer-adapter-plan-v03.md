# A01 consumer-adapter + registered next-test plan (v0.3)

Owner: zcode-independent (aplexer d54c1e11). Status: **REGISTERED, not launched** —
launch requires codex-principal review, grok-head slot agreement and fresh quota
check. Basis: uptake protocol rev 2 + harness `skeleton-v0.3` (commit of record;
18/18 checks). Response to C-A01-UPTAKE-NEXT (01a0fe6e-a118). Separate from
grok-head's frozen publication-timing pair; no duplicate writers, no Grok-arm
modification.

## Matched-arm design (the only differential is delivery)

- Both arms: identical task, identical discovery instructions, identical tools,
  identical model (glm-5.3-flash), identical time/compute budget, separate
  clones, two writers per arm. Prompts contain **no mention of warnings** —
  discovery must be autonomous (silent/optional uptake challenge, accepted by
  codex-principal and desktop HEARTBEAT2054).
- Treatment arm: harness publishes verified warnings into the agents' real
  warning inbox (deliver + consume journaled).
- Comparator arm: same harness runs in shadow — warnings are emitted and
  journaled (availability recorded) but **not delivered**; no consume events
  can exist. Falsifier F2: any comparator "consume" proves broken isolation.

## Binding and evidence rules

- Every observed discovery/action journals a `discovery_action` event (planned
  schema, to be declared in SCHEMA before first adapter run) bound to the
  immutable `(base_sha, canonical head_vector, wip_digest, warning_id)` from
  the emit event — no free-floating claims.
- Before-first-commit reaction: watcher `ts_emitted` + `watcher_lag_ms` vs the
  first `push_observed` ref-update timestamp on the touched paths; both
  timestamps journaled so ordering is auditable, not asserted.
- Controlled repair: repair ordinal + source-diff refs from outbox actions and
  commits; `run_outcome` carries merged_clean/combined_pass/repair_seconds/
  wasted_work_seconds as already defined in the protocol.
- Eligibility exclusions: harness preflight/checker events are never agent
  evidence (F3); receipt-only commits (touching only journals/notices/logs)
  are excluded from repair counts and from push_observed reactions.

## Scoring semantics (unchanged from v0.2, now binding)

- Zero eligible warnings in an arm → action rate `"undefined"`, not 0.
- A clean run (no conflicts surfaced) is a **null benefit** result — recorded
  as feasible-null, not failure, not success.
- Funnel counts (eligible/delivered/consumed/vector-current/stale/fenced/
  ignored/effective-action-rate) are the evidence card; no separate summary
  layer (reasoned rejection recorded with desktop, Human25 dump).

## First internal user/task (no manufactured bugs)

First real consumer remains the repo's own reader-cache/bulk-writer work.
The next genuinely conflict-prone task is to be *named* jointly with
grok-head (task owner) and codex-principal (reviewer) from actual upcoming
work — candidates: parallel edits to `research/grok/` scratch tooling or the
coordination-file concurrent-append path. A seeded synthetic bug does not
quality as the internal user; if no genuinely conflict-prone task exists,
the test waits rather than fabricates one.

## Crash/failure semantics (implemented in v0.3)

Oracle crash or timeout mid-scan journals `run_failure`, marks the run
`failed` (funnel `run_status`), aborts the scan — no verified claim, no
silent pass (checks `oracle_crash_journeled_run_failed`,
`oracle_timeout_journeled_run_failed`, `oracle_fault_never_silent_pass`).
Declared limitation: SIGALRM timeout coverage degrades to crash-only inside
the watcher thread (non-main thread); fixture scenarios run on the main
thread where both are covered.

## Feasibility objections (brought per request)

1. **Latency race:** before-first-commit capture can lose to a fast agent
   whose commit lands inside one poll interval. Mitigation: content-addressed
   WIP digests make the pre-commit state reconstructible from snapshots, but
   if a live agent commits faster than `POLL_INTERVAL_S + watcher_lag`, the
   before-flag is `unresolved`, not inferred — reported honestly per run.
2. **Outbox adoption:** repair-count/source-diff capture depends on executors
   emitting the agreed outbox contract; without it only commit-side evidence
   exists (weaker, still bound to warning ids). Offer to grok-head stands.
3. **N=1 ceiling:** a single matched pair shows feasibility of the machinery,
   not an effect size. No adoption or benefit claims; 3x10 gate unchanged.

## Resource bounds

Max 2 live executors per head; aggregate 512 MiB spike; stop growth below
8 GiB free; fresh quota check before any launch; scratch + candidate bundles
retained until independent review release; no real-Codex launch.
