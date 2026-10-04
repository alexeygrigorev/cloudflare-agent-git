# Shortlist gate evidence review — C1507 (independent, read-only)

Reviewer: zcode-shortlist-gate (session 5df4e39f), launched by antigravity-head under Codex Principal C1507/C1508. Date: 2026-10-04 Europe/Berlin. Method: read-only inspection of `research/evidence-ledger.md` (v3), `research/approaches-20.md` (v3 + addendum), `research/shortlist-6.md` (Codex draft 10), `research/consensus.md`, `research/debate/`, source evidence files (`research/claude/hn-evidence.md`, `workflows-competitors.md`), `prototype/README.md` (agent-branches-adopt worktree), and repo `LICENSE`. Direct file checks re-performed by this reviewer: MIT LICENSE present; `prototype/README.md` run commands present; E-C101/E-C102/E-C320 rows carry real URLs (HN Algolia format; Cursor docs fetched 2026-10-02). No research/source file was modified.

**Principal status (truthful):** Codex principal active (`codex-principal` in aplexer peers). Claude principal is currently stopped (absent from the live peers list). Claude's inputs are durable written artifacts (approaches-20 v3, evidence ledger v3, debate replies incl. `01a0fe3b-2151`, `01a0fffc-8221`, `01a1003c-0b2d`); they are treated as recorded history, not live agreement. **No Claude signoff of draft 10 exists and none is inferred.**

**Governing selection state (verified in consensus.md + shortlist-6.md):** Codex draft 10 is explicitly unapproved ("Neither principal has approved this file/digest"); consensus.md: "No final consensus. No SIGNOFF messages." Retained research hypotheses: A01 (conditional, demoted), A06. Parked, not occupying product places: A16, A05, A10, A14 (folded into A01), A09; A18 investigate-first. Slot 6 open. The "exactly 6 feasible shortlist approaches" requirement is **NOT met** — by design of the current drafts, not by reviewer judgment.

## Gate verdicts per candidate

Legend: PASS / PARTIAL / FAIL / UNKNOWN per the strict no-invention rule; every UNKNOWN is a real unverified item, not a soft pass.

### A01 — Live Integration Radar (retained hypothesis, conditional, no longer primary)

| Gate | Verdict | Evidence |
|---|---|---|
| a. Non-overlap/distinct | PARTIAL | Distinct vs landing-time merge queues (E-C341 GitHub merge queue; Graphite/Mergify/Trunk/Aviator E-C342/343). Collide (E-X027, fetch HTTP 200) is a live early-warning competitor; Codex rejects generic early-warning novelty; its MIT plugin repo 404'd twice — availability/license UNKNOWN. Weave owns entity-level merge (E-C346); A01 does not claim it. |
| b. Practitioner pain URLs | PASS (with mandatory prevalence limiter) | E-C101–110 etc.: 70 HN items exact-substring-verified vs Algolia (spot-checked E-C101/E-C102 rows carry real thread URLs). arXiv 2607.04697 + 2609.25396 re-verified by Claude. Limiter: cross-agent pairs only 0.5% of co-active pairs; mechanism real, population small — must be quoted with every A01 claim. |
| c. Concurrent-agent demo | FAIL (as product demo) | Draft 10: "No candidate has passed the real concurrent-agent Workers/Artifacts gate." D-G25 (registered fair pair, commits 7ef2269/2f4681c) ran two actual agents concurrently with Codex independent replay — but null separation: zero hazard, zero repair, zero live-warning consumption. Concurrent agents verified; product mechanism benefit UNKNOWN. |
| d. Permissive source | PASS | Repo LICENSE = MIT (verified by this reviewer 2026-10-04). |
| e. Local run instructions | PASS (prototype lane) | `prototype/README.md`: concrete npm/wrangler/node commands incl. plain-node no-Cloudflare mode; this reviewer's C1474 session executed the full loop live on 2026-10-04 (report: agent-branches-adopt `research/antigravity/adoption/REAL-FORK-ADOPTION-REPORT.md`). A01-specific remote Workers/Artifacts path: UNKNOWN (no cloud run claimed). |
| f. Video plan | PASS (plan only) | Concrete 4-beat plan in shortlist-6.md §1; plausible 5–10 min. No video recorded (UNKNOWN). |

### A06 — Change-story review queue (retained hypothesis)

| Gate | Verdict | Evidence |
|---|---|---|
| a. Distinct | PARTIAL | CodeRabbit Change Stack (E-X028, navigation verified) already documents grouping, per-snapshot progress, pinned links, stale-merge refusal; novelty lowered 3→2 (retained-lanes-review-2324.md). Surviving differentiator to test: cards recording **excluded guarantees** (Grok a06-adoption-decision.md). |
| b. Pain URLs | PASS | E-C201–252: 47/52 primary-fetched (4 secondary-press only, flagged in ledger). |
| c. Concurrent-agent demo | FAIL | N=1 real decision (Muse protocol, 57f8f8f/5000527): verdict unchanged with/without card; card contained a factual error; explicitly "not a controlled adoption gain." No concurrent-agent demo. |
| d. Permissive source | PASS | MIT. |
| e. Local run instructions | UNKNOWN | No A06-specific runnable product or instructions located; shared prototype stack only. |
| f. Video plan | PASS (plan only) | shortlist-6.md §4; not recorded. |

### A05 — Fork tournament (provisionally parked)

a: UNKNOWN — competitor refresh required before claiming a gap (Cursor best-of-N E-C320 VERIFIED-FETCHED: "does not merge changes back"; Agent HQ / Codex Cloud attempts not refreshed). b: PASS for indexed items (E-C320/323/326/364; note E-C344/348/350 UNVERIFIED per ledger). c: PARTIAL — real same-task attempts have source artifacts; head-owned adjudication pending; encoding-probe correction not yet in the public matrix; no winner. d: PASS. e: UNKNOWN (harness/task-schema mismatches challenged; no settled run instructions). f: PASS (plan only).

### A10 — Durable handoff (parked)

a: PARTIAL — Entire is a strong current competitor; Entire docs UNVERIFIED (E-X029 fetch failures, recorded as source limitation). b: WEAK/PARTIAL — E-X003 incidental tool issue, E-X008 stale-base; ledger itself says firsthand corroboration is lacking. c: PARTIAL — two N=1 cold recoveries via ordinary Git (27 s next-review; 2104-byte patch rebased, 39/39+37/37) — that is baseline sufficiency evidence, i.e. evidence *against* product need, not a product demo. d: PASS. e: UNKNOWN. f: PASS (plan only).

### A16 — Zero-checkout workspaces (parked)

a: PARTIAL — job distinct (U7 disk), but incumbent mechanisms give near-equal benefit: pnpm union ~49.97%/E-X019 229.6 vs 459.0 MiB; ArtifactFS FUSE+CoW verified (E-X021). b: MIXED — U7 is one first-hand user; HN 49606281 discussion date-pinned (E-X026); market breadth beyond U7 thin. c: PARTIAL — concurrent-thread code edits proved filesystem isolation only, "not coding-agent outcome efficacy"; benchmark results are fixture/synthetic (corrected labels). d: PASS. e: PARTIAL — benchmark scripts exist; product run instructions UNKNOWN. f: PASS (plan only). Gate data: 47.76% cache-inclusive N=2 < 50% gate (three failures: 42.37/36.05, 48.17, 47.76); 50% bar not moved.

### A14 — Preview-per-agent runtime isolation (folded into A01)

a: PARTIAL — Workers Previews baseline (E-X023 verified) already isolates DO/Containers per preview; distinct only for KV/D1/R2 shared-binding isolation. b: PASS-indexed (E-X002 promotional caveat, E-X005, E-C321/322/363). c: PARTIAL — local shared-resource hazard reproduced, but "both explicit isolation and ordinary control pass. No local advantage, real-agent or cloud result." d: PASS. e: PARTIAL (local fixture; no cloud run). f: PASS (plan only).

### Slot 6 area — A18 (investigate-first), A09 (parked), unfilled places

A18: Pact `can-i-deploy` incumbent verified (E-X025); park condition (incumbent stack rejects bad combination + resumes after interruption) outcome UNKNOWN pending the demand-first scout. A09: demand gate corrected — verified first-hand reports establish duplicated-side-effects-as-category, **not** Git-ref publication demand; Space Bunny incumbent check "GAP, narrow" with 4/7 artifacts UNVERIFIED (recorded unknown, not absent); kill test pending. No replacement selected for slot 6; "do not fill for count" stands.

## Bottom line

- **0 of 6 named candidates pass all six gates today.** Gate d (MIT) passes universally; gate f has plausible unrecorded plans for all; gate b passes for A01/A06/A14, mixed/partial for A16/A05/A10. The binding failures are gate c (no candidate has a real concurrent-agent product demo on Workers/Artifacts; A01's D-G25 was a null-separation fair pair) and, for A06/A05/A10, distinctness vs verified incumbents (CodeRabbit, unrefreshed best-of-N vendors, Entire).
- The exactly-six feasible shortlist with both principals approving one digest **does not exist yet**; current drafts truthfully record this. Any report claiming six approved approaches would contradict consensus.md and shortlist-6.md.
- Unknowns that materially block gates, as recorded (not invented): A01 live-warning uptake on a naturally recurring composition hazard; A06 controlled equal-access comparison; A05 adjudication + competitor refresh; A10 external Git-bound handoff gap; A16 remote-mode evidence; A14 comparative agent-workflow advantage; A18 scout outcome; A09 kill test.

Reviewer: zcode-shortlist-gate, 2026-10-04.
