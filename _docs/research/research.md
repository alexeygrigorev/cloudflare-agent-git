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

(pending)

## 2. Shortlist outcomes and kill criteria

(pending)

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
