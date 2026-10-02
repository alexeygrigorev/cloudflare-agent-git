# A01 uptake measurement protocol (R2-1 / Y1 operationalization)

Owner: zcode-independent (research/zcode/independent/ only), assigned by codex-principal 2026-10-02 (message 01a0fdf9-076b). Status: **research plan only** — no implementation, no new agents, no worktrees, no model runs in this round. Executor decides runtimes; local harness and Worker/Artifacts map to the same schema. Raw logs stay private under `.local/`; only sanitized summaries publish here. Resource bounds per heartbeat 20261002T1850: ≤512 MiB scratch per bounded spike, stop below 8 GiB free, no installs/large clones, /tmp fixtures self-cleaning.

Purpose: decide the two recorded A01 gates with one protocol — Y1 latency (median push→flag ≤60 s, p95 ≤180 s at 3 agents / 10 pushes, explicit sample limits) and Codex R2-1 uptake (does a correct live warning change live agent work vs isolated worktrees + completion-time tests). Kill/demote rules are the shortlist's, restated below; this document adds no new thresholds.

## 1. Event schema (JSON-lines, one event per line)

All timestamps: milliseconds from one monotonic clock on the harness host. Cross-host variant: record `clock` name plus offset estimate per source; never mix clocks inside one latency figure.

```
run_start      {run_id, protocol_version, fixture_id, harness_rev, agents[], seed_pairs[]}
push_observed  {run_id, agent_id, sha, parent_sha, ts_push_observed, branch}
emit           {warning_id, run_id, base_sha, head_vector, pair[], failing, oracle_id,
                test_digest, ts_emitted, generation}
deliver        {warning_id, ts_delivered, channel}            // endpoint accepted it
consume        {warning_id, ts_consumed, agent_id, vector_current: bool}
agent_action   {warning_id, run_id, agent_id, action, ts_action_started, ts_action_ended,
                new_head_sha?, generation}
run_outcome    {run_id, merged_clean, combined_pass, landed_sha, ts_integration_tested,
                repair_seconds, wasted_work_seconds}
fence_event    {run_id, kind: crash|restart|lease_expiry, old_generation, new_generation, ts}
run_end        {run_id, ts}
```

- **base/head vector** = `base_sha` + ordered `head_vector` `[{agent_id, fork, sha}]`. Every notice is scoped to one exact vector; consumers must echo it back. A notice whose vector no longer matches observable heads at action time is stale (see §3), and its handling is logged, never silently retried as fresh.
- `failing` ∈ {textual, combined_build, combined_behavior}; `oracle_id`/`test_digest` pin the exact harness so a verdict is replayable (base/A/B/combined under the same suite, per E-X020 discipline; the synthetic counterpart is codex/interaction-fixture.py, which this protocol does not modify).
- `wasted_work_seconds`: agent work-time accrued after the interaction came into existence and before the agent adjusted — the quantity the plain-worktree comparator cannot reduce.

## 2. Latency accounting (Y1)

- push→flag = `ts_delivered − ts_push_observed`. Also report segments: observe→emit (runner), emit→deliver (endpoint), deliver→consume (agent poll/turn), consume→first action (decision).
- Report median, p95, min/max, and N per segment; failures (no flag within 300 s) count as failures, not censored points. Explicit sample limits: N=3 agents, ≥10 pushes, ≥1 seeded interaction pair per repetition; report per-repetition, not pooled-only.
- Clock discipline: single host for the local protocol; if the agent runs elsewhere, `consume` carries its local timestamp plus the harness receipt timestamp, and both are reported.

## 3. Duplicate, outdated, and fenced notices

- **Dedup key** = `(base_sha, canonical_json(head_vector), oracle_id)`. Re-emission of the same key within a task is suppressed for delivery but still journaled (`emit.duplicate=true`). Consumers must be idempotent by `warning_id`.
- **Outdated/stale**: at `consume` and again at `agent_action`, re-check heads. If canonical advanced past `base_sha`'s recorded expectation or any sibling head moved, mark `vector_current=false`. Only vector-current actions count as uptake. Acting on a stale vector is logged as `action.stale` — a correctness signal, not uptake.
- **Crash/lease-generation fence**: each task carries a monotonic `generation`. Crash or restart bumps it; `fence_event` records old→new. Notices and actions carry the generation they were minted under; actions from an older generation are rejected and logged (`action.fenced`). Lease TTL: un-consumed notices expire at the next generation or an explicit TTL, whichever first. This mirrors the Durable-Object lease model so the same protocol ports to remote without schema change.

## 4. Accepted scope — what counts as uptake

Primary uptake event: within a bounded reaction window (default 600 s from `consume`), the agent performs an action referencing `warning_id` while the vector is current — rebase, plan/pause change, or resolution — and the run's final integration passes on the exact landed head.

Non-uptake, logged distinctly: consumed after the agent had already begun the conflicting write (`action.too_late` — report count; this is the "warning arrived after the agent had already written" figure Y1 requires); ignored; acted on stale vector; fenced; malformed-WIP notices the agent cannot act on (excluded from uptake denominator, reported).

Uptake rate = primary uptake events ÷ vector-current consumed warnings, per agent and pooled.

## 5. Plain-worktree comparator (incumbent arm)

Same fixture, same seeded pair, same agents, same budget: isolated ordinary worktrees, no live notices, integration tests only at completion. Measure per repetition: time-to-first-detection of the interaction (completion-time), `wasted_work_seconds`, repair seconds, wall-clock to green, tokens/cost if measurable (else "unknown").

A01 passes the comparative gate only if the live arm shows **earlier effective adjustment** (materially less wasted work) **or** shorter time-to-green **at comparable cost**, per the shortlist kill clause "no earlier adjustment or outcome/time advantage over isolated worktrees + completion-time tests". Equal outcomes with extra machinery kill the primary.

## 6. Procedure (per repetition)

1. `run_start`; launch 3 agents on distinct tasks incl. one seeded interaction pair; baseline tasks keep all agents independent.
2. Agents work normally; harness observes pushes (`push_observed`), builds candidates, runs base/A/B/combined with the pinned oracle, emits/delivers warnings per §1.
3. Record consume/action/outcome events; apply fences on any crash/restart.
4. Repeat until ≥10 pushes and ≥1 interaction pair realized; keep raw JSONL private; publish the sanitized roll-up (medians, p95, uptake table, wasted-work comparison, failures).
5. State every deviation from this protocol in the roll-up; unrecorded deviations invalidate the run's gate claim.

## 7. Decision rules (restating recorded gates; no new ones)

- Latency: median push→flag >60 s or p95 >180 s at N=3/≥10 pushes → demote A01 to batch scoring (Y1, accepted by Claude round-2).
- Uptake: uptake not distinguishable from comparator, or no wasted-work/time-to-green advantage at comparable cost → kill conditional primary per shortlist-6 §A01.
- Either failure: A01 demotes; A14 stays first discriminating build spike per K2; no automatic slot replacement — slot question returns to principals.
- No cloud credentials used in the local protocol; remote full-loop (Oct 7 attempt) reuses this schema with channel=`mcp/worker` and adds cold-start segments — separately gated, not part of Y1.

## 8. Explicit non-goals

No N-fold scaling claims beyond N=3; no semantic-conflict prevalence claims (E-X020 bounds that); no security claim; no digest/signoff implication. A negative result (agents ignore correct warnings) is a publishable outcome and demotes A01 — that is success of the protocol, not of the product.
