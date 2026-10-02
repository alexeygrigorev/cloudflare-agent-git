# Harness skeleton v0 — watcher + protocol machinery (2026-10-02, ~22:00)

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
