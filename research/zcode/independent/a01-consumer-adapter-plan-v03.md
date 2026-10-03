# A01 consumer-adapter + registered next-test plan (v0.3, amended v0.4)

Owner: zcode-independent (aplexer session 7bd5b3c2-4399-4b2e-9797-e8e0014740ee;
the earlier d54c1e11 reference was stale — C-V03-REVIEW2124). Status:
**REGISTERED, not launched.** Launch of any writer pair additionally requires
the dupexec production gate to open (Codex 01a0ff25-eb60 via antigravity-head:
read-only docs/schema work unblocked; live trials gated). Shadow-consume of the
finished fair-pair heads is accepted (G-A01-SHADOW-CONSUME-20261003) and runs
after codex-principal accepts this adapter revision — no new writers, no seeded
bug. Basis: uptake protocol rev 2 + harness `skeleton-v0.4` (19/19 fixture
checks). Response to C-A01-UPTAKE-NEXT (01a0fe6e-a118); amendments per
C-V03-REVIEW2124 (+addendum). Separate from grok-head's frozen
publication-timing pair; no duplicate writers, no Grok-arm modification.

## Matched-arm design (the only differential is delivery)

- Both arms: identical task, identical discovery instructions, identical tools,
  identical model (glm-5.3-flash), identical time/compute budget, separate
  clones, two writers per arm. Prompts contain **no mention of warnings** —
  discovery must be autonomous (silent/optional uptake challenge, accepted by
  codex-principal and desktop HEARTBEAT2054).
- **Interface discoverability (C-V03-REVIEW2124):** although prompts never
  name warnings, the identical neutral tool inventory given to both arms must
  make the warning-inbox interface discoverable (an existing file/channel the
  agents' normal tools can read). Each observed discovery journals an
  `interface_observed` event (v0.4 schema, pre-declared) — file/tool
  discovery is recorded SEPARATELY from `consume`. Interpretation rule:
  empty consumption with zero `interface_observed` = invisible endpoint
  (harness/registration defect); empty consumption WITH observed interface =
  agent non-adoption. The two must never be conflated.
- Treatment arm: harness publishes verified warnings into the agents' real
  warning inbox (deliver + consume journaled).
- Comparator arm: same harness runs in shadow — warnings are emitted and
  journaled (availability recorded) but **not delivered**; no consume events
  can exist. Falsifier F2: any comparator "consume" proves broken isolation.

## Binding and evidence rules

- Every observed discovery/action journals a `discovery_action` event (v0.4:
  schema pre-declared in SCHEMA/SCHEMA_EXTENSIONS, no emitter until the
  adapter lands) bound to the immutable `(base_sha, canonical head_vector,
  wip_digest, warning_id)` from the emit event plus an explicit action
  `source` (agent_outbox | commit) — no free-floating claims.
- Before-first-commit reaction: watcher `ts_emitted` + `watcher_lag_ms` vs the
  first `push_observed` ref-update timestamp on the touched paths; both
  timestamps journaled so ordering is auditable, not asserted. When the
  capture is missing (commit beats the poll), the pre-commit flag stays
  `unresolved`/unknown — never inferred.
- Controlled repair: repair ordinal + source-diff refs from outbox actions and
  commits; `run_outcome` carries merged_clean/combined_pass/repair_seconds/
  wasted_work_seconds as already defined in the protocol.
- Eligibility exclusions: harness preflight/checker events are never agent
  evidence (F3); receipt-only commits (touching only journals/notices/logs)
  are excluded from repair counts and from push_observed reactions.

## Scoring semantics (binding)

- Funnel stages are SEPARATE counts — eligible_emitted, delivered, consumed,
  consumed_vector_current, effective_action_uptake, stale, fenced, ignored —
  never collapsed into one rate; no denominator overload.
- Zero eligible warnings in an arm → action rate `"undefined"`, not 0;
  a run with zero DELIVERED warnings can never render a 100 % rate.
- A clean run (no conflicts surfaced) is a **null benefit** result — recorded
  as feasible-null, not failure, not success.
- Funnel counts are the evidence card; no separate summary layer (reasoned
  rejection recorded with desktop, Human25 dump).

## First internal user/task (no manufactured bugs)

First real consumer remains the repo's own reader-cache/bulk-writer work.
The next genuinely conflict-prone task is to be *named* jointly with
grok-head (task owner) and codex-principal (reviewer) from actual upcoming
work — candidates: parallel edits to `research/grok/` scratch tooling or the
coordination-file concurrent-append path. A seeded synthetic bug does not
quality as the internal user; if no genuinely conflict-prone task exists,
the test waits rather than fabricates one.

## Crash/failure semantics (v0.4)

Oracle crash or timeout mid-scan journals `run_failure`, marks the run
`failed` (funnel `run_status`), aborts the scan — no verified claim, no
silent pass. Timeout classification (C-V03-REVIEW2124 addendum):
`subprocess.TimeoutExpired` is NOT a builtin `TimeoutError`; both are
explicitly labeled `oracle_timeout` (v0.4 fix — previously a subprocess
timeout would have been mislabeled `oracle_crash`). Thread coverage: the
DEFAULT oracle path is timeout-safe in ANY thread via the run_oracle
subprocess timeout, exercised by the fixture in an actual worker thread
(`watcher_thread_default_oracle_timeout_failclosed`). The SIGALRM whole-scan
deadline covers the main thread only and applies solely to CUSTOM
`oracle_fn` callables that bypass the subprocess: a custom fn in a watcher
thread is crash-covered but NOT timeout-covered — unsupported unless routed
through a bounded-timeout worker; the CrashTest timeout gate is claimed met
only for the default path.

## Shadow-consume of the finished fair-pair heads (accepted)

G-A01-SHADOW-CONSUME-20261003 accepted. After codex-principal accepts this
adapter revision, run the plan read-only against the finished fair-pair
heads listed in `research/grok/a01-live-provenance.md` (commit e81a0cb):
success is a `discovery_action` bound to those heads, or an explicit
zero-warning/undefined-rate result bound to those heads. No new writers, no
seeded bug, no Grok-arm modification. Pair result of record: grok-head
G-A01-FAIR-RESULT-20261002 — both arms pass, zero source repair, receipts
record no advisory notice → NOT uptake; codex live review still open.

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

## Resource bounds (per human26 / C-V03-REVIEW2124)

No fixed per-head executor cap — concurrency governed by actual independent
tasks, provider capacity and host resources, with coordination of shared
resources and no duplicate writers. Retained: 512 MiB incremental spike,
stop growth below 8 GiB free, fresh quota check before any launch, scratch +
candidate bundles retained until independent review release, no real-Codex
launch.
