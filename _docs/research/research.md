# Research: what we explored, what we measured, what we learned

This is the one research summary for the whole project, across every engine (Claude, Codex, Grok, Muse, Space Bunny, ZCode, Antigravity). It is written for someone who has just arrived and wants to know how the project decided what to build, and what turned out not to work.

## How to read the citations

Every path in parentheses is a file at the git tag `pre-cleanup-20261007` (commit `7a0b82c`, 7 Oct 2026). Read any of them with:

```
git show pre-cleanup-20261007:<path>
```

When a source names a commit or a message, it is quoted as it appears there. Numbers here were checked against the source file, not copied from summaries. Anything we could not check is marked **unverified**.

## The short version

The contest asked for an agent-native Git platform on Cloudflare Workers and Artifacts, with several coding agents working at once (`BRIEF.md`). We wrote 20 product approaches, scored them, and argued over a shortlist of six. Nobody ever signed a shortlist (`research/consensus.md`). The lead idea, a live radar that warns agents when their unfinished work stops fitting together (A01), lost its "primary" status after a fair live test with real agents showed no difference between warned and unwarned agents (`research/grok/a01-fair-results.md`). The storage idea (A16) missed its own pass mark (`research/antigravity/r8-worktree-d1-benchmark.md`). What survived became the product described in `SUBMISSION.md`: per-task forks, a live conflict radar, and a review view, built with honest limits on what they prove.

## 1. The 20 approaches and what happened to each

Claude wrote the 20 approaches on 2 Oct 2026 and scored each on a contest score out of 100 (half originality, a quarter visible concurrency, a quarter how easy it is to demo), plus separate pain, feasibility, Cloudflare-fit and long-term-value columns (`research/approaches-20.md`). The scores are Claude's alone; Codex scored independently in `research/codex/rankings-round-1.md`. The outcome column is the last recorded state.

| ID | Approach, in one line | Contest score | Outcome |
|---|---|---|---|
| A01 | Live Integration Radar: trial-merge every live agent head on each push and warn agents when their work stops composing | 85 | Kept as a conditional research hypothesis, **no longer primary** after the fair live pair showed no separation (`research/approaches-20.md` v3 log) |
| A02 | Lease-bound path claims, enforced when work lands | 70 | Not carried into any shortlist. Its own card notes Foremerge already specifies this protocol (`research/approaches-20.md`) |
| A03 | Merged-state gate that re-runs a failed task on the fresh base | 80 | Parked in v2 with a reopen test (the G5 fixture) (`research/approaches-20.md`) |
| A04 | Semantic contract sentinel for shared APIs | 75 | Parked in v2 with a reopen test (`research/approaches-20.md`) |
| A05 | Fork tournament: N attempts at one task, compare by behaviour, land one | 85 | Provisionally parked (`research/shortlist-6.md`). Independent adjudication of the one real task was a **TIE**, no winner (`research/zcode/independent/a05-adjudication/VERDICT.md`) |
| A06 | Change-story review queue: review intent and risk, not raw diffs | 65 | Kept as a research hypothesis; review pain is real but no comparative benefit was shown (`research/shortlist-6.md`) |
| A07 | Maintainer inbound quarantine: no human sees a contribution until a reproducer passes | 75 | Parked in v2 with a reopen test (`research/approaches-20.md`). The later demand scout collected evidence and gave no verdict (`research/zcode/independent/a07-demand-gate/findings-draft.md`) |
| A08 | Independent AI reviewer panel on every push | 50 | Kept "for completeness; likely feature of A06" (`research/approaches-20.md`) |
| A09 | Exact-SHA verification receipts | 60 | Re-scoped to "exactly-once publication receipts" for one Git-ref adapter as a slot-6 candidate, then parked with its kill test pending (`research/approaches-20.md`) |
| A10 | Durable handoff: plan, decisions and exact base travel with the task | 65 | Provisionally parked: two cold restarts recovered fine from plain Git (`research/shortlist-6.md`) |
| A11 | Merge decision ledger ("why this one won") | 70 | Not carried into any shortlist (`research/approaches-20.md`) |
| A12 | Quarantine forks and capability tokens | 65 | Its card calls it Cloudflare's own recommended practice, so low originality; the "Task Passports" refinement is parked (`research/approaches-20.md`) |
| A13 | Undo everything one agent session did | 75 | In the first six, then parked in v2 with a reopen test (`research/approaches-20.md`) |
| A14 | A live preview URL and private data per agent | 75 | **Folded into A01** as its runtime-verification part; an ordinary separate-resource control did just as well (`research/approaches-20.md`, `research/shortlist-6.md`) |
| A15 | Push-triggered fast test lane | 50 | Not carried into any shortlist; its card lists low originality (`research/approaches-20.md`) |
| A16 | Zero-checkout lazy agent workspaces (the founder's disk pain) | 70 | **Parked**: missed its own >50% storage gate three times (`research/approaches-20.md`) |
| A17 | Fork-is-the-task board | 65 | "Retained as UX shell candidate rather than product" (`research/approaches-20.md`) |
| A18 | Multi-repo change sets with recovery | 75 | Parked in v2. The "Contract Packs" refinement was scouted and **PARKED**: a configured Pact `can-i-deploy` setup already rejects the bad combination (`research/zcode/independent/a18-scout/findings.md`) |
| A19 | Maintenance swarm with batch landing | 75 | In the first six, then parked in v2 and folded into A01's batch mode (`research/approaches-20.md`) |
| A20 | Earned autonomy per agent configuration | 60 | Not carried into any shortlist (`research/approaches-20.md`) |

A02, A11, A15 and A20 have no disposition note of their own beyond never entering a shortlist.

## 2. Shortlist outcomes and kill criteria

**How the shortlist moved.** Claude's first six (A01, A05, A07, A14, A13, A19) were replaced by a v2 six (A01, A14, A16, A05, A06, A10) (`research/approaches-20.md`). Codex owned the shortlist file. Its last version, draft 10, keeps only **two research hypotheses, A01 (demoted) and A06**, leaves **four product places unfilled**, folds A14 into A01, and parks A16, A10 and A05 (`research/shortlist-6.md`).

**Nothing was ever signed.** The agreed procedure was: freeze the file, each lead engine hashes the exact bytes and sends `SIGNOFF <sha256>`, and any later edit voids it. No SIGNOFF was ever sent (`research/consensus.md`). Antigravity once declared "final consensus" on its own six; Codex rejected that because it lacked both leads' approval (`research/consensus.md`). The two leads also disagreed on the primary build: Claude favoured an A01-led six, Codex a provisional A14 build (`research/debate/codex-open-disagreements.md`).

**The gate every lane had to pass.** At least two real coding agents working at the same time, an Artifacts fork-and-push lifecycle, runnable open source, and a 5 to 10 minute demo. "Scripts pretending to be agents do not satisfy that gate" (`research/shortlist-6.md`). No candidate passed it during the research phase (`research/shortlist-6.md`).

**Kill criteria, per candidate.** Each candidate carried a written rule for when to drop it:

| ID | Kill or park rule | What happened |
|---|---|---|
| A01 | Original: kill if, on 10 replayed task pairs, the radar does not flag a real conflict earlier than PR time in at least half the conflicting pairs, or agents ignore warnings (`research/approaches-20.md`). Later: drop primary status if there is no earlier adjustment and no outcome or time advantage over isolated worktrees plus completion-time tests; proposed latency median ≤60 s, p95 ≤180 s at three agents and ten pushes (`research/shortlist-6.md`) | Primary withdrawn after the null fair pair (section 3.1). Reopen only with a pre-registered, neutral task family where the composition hazard occurs naturally (`research/approaches-20.md`) |
| A16 | The Artifacts mode must cut total physical bytes by more than 40% against sparse worktrees plus a shared pnpm store (`research/approaches-20.md`); the env-sharing gate was more than 50% whole-footprint savings for two concurrent tasks (`research/shortlist-6.md`) | Failed (section 3.4). The 50% bar was not moved and no N=3 extrapolation was allowed to rescue it (`research/shortlist-6.md`) |
| A05 | On five tasks, at least 3 of 5 outcome wins plus a review advantage over a single attempt and vendor-style selection; park if outcomes are equal at higher cost (`research/shortlist-6.md`) | One real task, adjudicated as a TIE (`research/zcode/independent/a05-adjudication/VERDICT.md`); parked as a portfolio decision, not a general falsification (`research/shortlist-6.md`) |
| A06 | Blind seeded-bug comparison: at least 30% shorter review with an equal catch rate (`research/shortlist-6.md`) | Never run as designed; the experiments that did run could not show a benefit (section 3.3) |
| A10 | On five restart or drift tasks, beat the strongest baseline (same-commit plan file, Entire checkpoint resume, git log) (`research/approaches-20.md`) | Parked after two single cold restarts worked from ordinary Git (section 3.5) |
| A14 | If ordinary `wrangler` plus Workers Previews reproduces the whole workflow in ten minutes, or state is not isolated, fold into A01 (`research/shortlist-6.md`) | Folded: the local shared-resource hazard was reproduced, and both explicit isolation and the ordinary control passed (`research/shortlist-6.md`) |
| A18 | If configured Pact `can-i-deploy` plus matrix CI and a merge queue rejects the bad combination and resumes cleanly after interruption, park (`research/shortlist-6.md`) | Parked by the scout; clean resume was documented by the vendor but not reproduced (`research/zcode/independent/a18-scout/findings.md`) |
| A09 | On a replay of the real duplicate-execution traces, exactly one publication per operation id with zero lost legitimate repeats (`research/approaches-20.md`) | Not run; parked. The demand evidence showed duplicated agent side effects exist as a category, not demand for Git-ref publication (`research/approaches-20.md`) |

## 3. Experiment results

(pending)

## 4. Demand and competitor map

(pending)

## 5. Architecture invariants

(pending)

## 6. Adoption and dogfood findings

(pending)

## 7. Lessons

(pending)

## 8. Review verdicts by family, and the 22 negative verdicts

(pending)

## 9. Where the raw evidence is

All raw material (harness code, fixtures, JSON results, transcripts of reviews, per-agent journals) stays readable in git. Nothing in this file replaces it.

- Now: tag `pre-cleanup-20261007` (commit `7a0b82c`). Use `git show pre-cleanup-20261007:<path>` for a file and `git ls-tree -r --name-only pre-cleanup-20261007 research/` for the list.
- Later: once the cleanup lands, the same files will also sit under the tag `research-archive-20261007`. Swap the tag name in the command; the paths stay the same.

Useful starting points inside the tag:

| What | Path |
|---|---|
| All 20 approaches with scores and the final disposition log | `research/approaches-20.md` |
| The unsigned shortlist with kill criteria | `research/shortlist-6.md` |
| Why nothing was signed | `research/consensus.md` |
| Evidence index by pain theme (E-C, E-X, E-A, E-G ids) | `research/evidence-ledger.md` |
| A01 fair pair, Codex replay | `research/grok/a01-fair-results.md`, `research/codex/a01-live-independent-replay.json` |
| G3 composition experiments with real agents | `research/space-bunny/g3-no-symbol-overlap/results-real-agents.md`, `research/space-bunny/g3-non-discoverable/results-real-agents.md` |
| A06 review-card experiments | `research/muse/a06-phase-b-record.md`, `research/muse/a06-pilot-adoption/analysis.md`, `research/grok/a06-adoption-decision.md` |
| Storage benchmarks | `research/claude/u7-real-worktree-measurement.md`, `research/codex/package-storage-validation.md`, `research/antigravity/r8-*.md` |
| Duplicate execution | `research/antigravity/r8-dupexec-count-verification.md`, `research/antigravity/r9-runtime-single-effect-verification.md`, `research/antigravity/r11-real-duplicate-incidence.md` |
| Demand research | `research/antigravity/demand/` |
| Adoption and dogfood trials | `research/antigravity/adoption/`, `research/antigravity/dogfood/` |
| Every independent review and audit | `research/antigravity/reviews/`, `research/antigravity/audit/` |
| Open disagreements between the two lead engines | `research/debate/codex-open-disagreements.md` |
