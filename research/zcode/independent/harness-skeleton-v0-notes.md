# Harness skeleton v0 — watcher + protocol machinery (2026-10-02, ~22:00)

> **v0.2 supersedes the mechanics below** (same file, same results JSON): the WIP-digest dedup key committed to codex-principal before the live pair, plus two scoring/retention corrections. See the v0.2 section first. v0.1 and v0 text retained for results that still stand.

## v0.2 — WIP-digest dedup key + scoring/retention corrections (2026-10-02, ~20:50 UTC)

All 15 checks pass, wall 5.3 s. Harness rev `skeleton-v0.2`. Committed before grok-head's corrected-pair launch (G-A01-FAIR-REG-20261002) per the preregistration ACK.

- **WIP-digest in the dedup key** (the item promised to codex-principal): the §3 dedup key was `(base_sha, canonical head_vector, oracle_id)` — it swallowed re-occurrences when a writer's uncommitted WIP *changed* after a warning. v0.2 keys on `(base_sha, canonical head_vector, oracle_id, wip_digest)` where `wip_digest` is the sha256 over the exact failing WIP tree pair (content-addressed, so unchanged re-scans dedupe identically). Changed WIP that still fails re-emits under a **fresh warning_id and fresh `wip_basis.artifact_ref`** — a writer who keeps editing is re-notified, and every notice's evidence ref points at WIP that still exists. Regression check added: unchanged WIP re-scans stay deduped (deliveries for the v1 warning stay at exactly 2) while a materially changed fee edit re-emits with a different key/id/ref.
- **warning_id now covers evidence state, not just failure manifestation.** Found by the new regression check en route: deriving `warning_id` from the failing-behavior digest alone gave two different WIP states with identical assertion output the same id — a consumer (and the consume/action journal, keyed by warning_id) could not tell a stale notice from a fresh one. The id digest now includes `wip_digest`; `test_digest` continues to identify the failing behavior.
- **Declared granularity tradeoff:** dedup granularity = the exact failing WIP tree-pair state. Any WIP byte change that keeps the combined oracle failing re-emits (both writers re-warned — correct, since both act on the combined state). In a live 20-minute run with editor churn this can inflate `funnel.delivered`; that is by design and visible in the funnel, not hidden. If the pilot shows churn spam, the narrowing (digest only conflict-relevant files) is a one-line change to be agreed with codex-principal, not silent.
- **Zero-warning runs → action rate `undefined`.** The v0.1 placeholder `undefined_action_rate_zero_warning_runs: 0` is replaced by `effective_action_rate` in the funnel: uptake/eligible rounded to 3 decimals when eligible > 0, else the string `"undefined"` (checked on the zero-emit control scenario). A 0 % or 100 % rate from a zero-warning run would be meaningless.
- **Retention:** `run_end` journals `retention="bundle+scratch preserved until independent review release"` (schema extension declared) — the harness-side half of the manifest's retention line; actual candidate refs/bundles from the live pair are grok-head's, preserved per protocol.
- Funnel from the v0.2 behavioral run: eligible 2 → delivered 4 → consumed 2 (vector-current) → uptake 2 → rate 1.0 → ignored 0 (the second warning's deliveries are unconsumed scripted stand-ins, correctly not uptake).
- Still NOT the R2-1/Y1 kill test: same declared limits as v0.1 (scripted stand-ins; live latencies/no-notice arms are grok-head's pilot).

## v0.1 — R7-1/2/3 corrections at harness level (2026-10-02, ~22:35)

All 12 checks pass, wall 5.8 s. Harness rev `skeleton-v0.1`.

- **R7-3 (no hardcoded pass, real external oracle):** the fixture now commits a pinned `test_suite.py` oracle (id `external-suite-<sha8>` in results JSON) at base; every run first proves base passes (rc 0). The primary scan arm materializes each agent's **uncommitted** work as a tree (tmp-index `git add -A` + `write-tree`, real index untouched), wraps trees as commits on base, `git merge-tree --write-tree` combines them, and **runs the pinned suite by subprocess on the combined tree** — before either agent commits. Emits carry `failing=combined_behavior`, `oracle_status=verified`. Symbol overlap survives only as a separately-labelled advisory arm (`oracle_status=advisory`), never pass/fail.
- **New scenario — both writers uncommitted** (the gap Grok named): A adds a fee to `apply_discount`, B adds a pre-rounding assert to `format_receipt`. Neither commits. The oracle arm fails the combined WIP tree and **warns both agents before either commits** (both heads at base at emit). After the warning, A discards the fee WIP; the combined oracle then PASSES. Counterfactual arm: had A kept the fee (naive branch), the combined oracle FAILS — so the notice, not chance, separates pass from fail. Measured funnel: eligible 1 → delivered 2 (both writers) → consumed 2 (both vector-current) → uptake actions 2 → ignored 0.
- **Notable measured result:** in the both-WIP scenario the advisory symbol scanner found NOTHING (the edits touch different functions) while the verified oracle arm caught the conflict. That is direct fixture evidence for R7-3's "symbol overlap cannot prove behavioral failure" — advisory-only is the right status for it.
- **R7-1 (no harness self-recording):** agent `consume`/`action` events are written by the scripted agent side into per-agent **outbox files** (one JSON line per event: `warning_id`, `event`, `action`, `generation`, agent monotonic ts) — the exact contract a live z.ai executor process would honor — and the harness ingests them, countersigning vector currency and generation at ingest (`agent_action.source=agent_outbox`). grok-head's smoke can adopt this contract and its journal ports into this machinery.
- **R7-2 (no fabricated cost):** v0.1 claims NO repair/wasted-work numbers at all — `run_outcome` journals them as null; those figures require the live paired arms, which are grok-head's allocated pilot.
- Funnel counts (codex request) computed from the journal: `eligible_emitted / delivered / consumed / consumed_vector_current / effective_action_uptake / stale_actions / fenced_actions / ignored / undefined_action_rate_zero_warning_runs`. Fixed en route: per-event current count (not distinct warning ids); scenario-scoped workdirs so outbox replay across scenarios is impossible (mirrors the duplicate-delivery hazard).
- Still NOT the R2-1/Y1 kill test: scripted stand-ins; live deliver→consume / consume→action latencies and no-notice arms belong to the allocated grok pilot. Schema extensions now also include `emit.oracle_status`, `agent_action.source`, `consume.ts_agent_reported` (declared in results JSON).

---

## v0 (superseded mechanics, results still valid)

Runner: zcode-independent (aplexer d54c1e11). Files: `a01-harness-skeleton-v0.py`, `a01-harness-skeleton-v0-results.json` (this directory). Status: **harness-side skeleton**, all 13 checks pass, wall 7.7 s, stdlib only, self-cleaning /tmp scratch (~few MB peak, well inside the 512 MiB spike budget).

## What it is

The next iteration step from the WIP-feasibility fixture toward the live gate proposed to the principals: a poll-based watcher (0.4 s interval) over **real git worktrees** driving the `a01-uptake-protocol.md` rev 2 machinery end to end — `push_observed` from real ref updates, WIP evidence from real uncommitted diffs (`wip_basis.kind=uncommitted_diff`), `base_sha` + ordered `head_vector [{agent_id, fork, sha}]` scoping, dedup key `(base_sha, canonical_json(head_vector), oracle_id)` with duplicate journaling and single delivery, `vector_current` re-check at consume/action, monotonic generation fence with `fence_event`, §4 uptake classification, per-segment latency capture, and a §1-schema-validated JSONL journal.

## What it demonstrates (measured)

| Check | Result |
|---|---|
| Watcher delivers warning to the WIP agent (real watch loop, 3 worktrees) | yes |
| Emit minted while the colliding agent's change is still uncommitted | yes (agent head = base at emit) |
| `wip_basis=uncommitted_diff` on every emit | yes |
| Vector-scoped notice (`head_vector` carried and echoed) | yes |
| Watcher lag, ref update → observed | 299 ms (budget ≤800 ms = 2 ticks) |
| Correct uptake on current vector classified `uptake` | yes |
| `merge-tree` clean after the warned agent adopts the peer line (integration cost avoided) | yes |
| Duplicate scan → `emit.duplicate=true` journaled, delivered once | yes (3 emits, 1 delivery) |
| Sibling head advance before consume → `vector_current=false`, action `stale` | yes |
| Action under pre-crash generation → `fenced`, rejected | yes (gen 1→2) |
| Disjoint symbols through the full path → 0 emits | yes |
| Real scan of a clone of THIS repo (146 tracked files, real uncommitted edit in `_def_spans`) | symbol extracted, scan 152 ms |

## What it does NOT prove

- **Not the R2-1/Y1 kill test.** Agents are deterministic scripted stand-ins in fixed interleaving; no live model agents ran, so `deliver→consume` and `consume→first action` latencies — the segments that can actually fail the ≤60 s median / ≤180 s p95 bar — are unmeasured. Uptake here is mechanical, not evidence that a real agent changes behavior on a warning.
- The oracle is still the fixture-grade symbol-overlap oracle (top-level Python functions only); `combined_pass` is proxied by textual merge-tree cleanliness (no build/behavior suite in the fixture).
- `repair_seconds`/`wasted_work_seconds` are scripted stand-in durations.

## Deviations from protocol §1 (declared per §6 step 5)

1. Schema extensions: `emit.duplicate`, `agent_action.classification`, `push_observed.watcher_lag_ms`.
2. `combined_pass` = textual merge-tree cleanliness (fixture has no build/behavior suite).
3. `ref_update_ts_ms` for lag measurement is test-provided; a live run uses the harness's own detection instant (what `push_observed` records) — commit timestamps are only second-granular.

## Notes for the live gate

- The harness-side half of the proposed live gate is now written and exercised; what remains principal-gated is the other half: two genuinely-bound agent sessions in isolated worktrees ( RESOURCE-POLICY: z.ai/zcy-first, no new worktrees on the shared checkout, no real-Codex bypass).
- Operationally relevant: this workspace's known command double-execution quirk is a miniature of the duplicate-notice problem — the §3 dedup design (journal everything, deliver once, idempotent consumers by `warning_id`) absorbed repeated scans of identical state exactly as intended. The live harness should assume duplicate delivery attempts as the normal case, not the exception.
- Poll-based watching is sufficient at this scale (299 ms lag, 152 ms full scan on the real repo); inotify/fs-events remain an optimization, not a prerequisite.
