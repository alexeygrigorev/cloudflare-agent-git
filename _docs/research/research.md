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

### 3.1 A01 fair pair: a null result

Question: does an agent that can see a peer's unfinished work do better than one that only meets it at completion? Grok ran one registered pair on 2 Oct (commits `7ef2269`, `2f4681c`): two arms (completion-time, live), each with two real `zcodex` writers on complementary reader and writer tasks (`research/grok/a01-fair-results.md`).

- Every role's first product commit already passed the task check and the composition oracle. Source repair was zero in all four roles; no warning notice was recorded (`research/grok/a01-fair-results.md`).
- The live arm did see the peer's later-committed bytes before its own commit. That changed nothing (`research/grok/a01-fair-results.md`).
- Codex replayed the live arm independently: all eight checks exit 0, including the combined tree, and nothing changed after the first source commit (`research/codex/a01-live-independent-replay.json`).
- Decision D-G25: "null separation" (`research/grok/a01-fair-results.md`). Claude proposed and Codex accepted dropping A01's primary status (`research/consensus.md`).

The earlier pilot, D-G23, does not count as evidence: its prompts differed between arms beyond the warning, and the notice arm "passed" by not doing the task (`research/debate/codex-a01-pilot-review.md`, `research/evidence-ledger.md`). The outside literature agrees the hazard is real but rare: one study found cross-agent pairs in only 0.5% of co-active pairs (`research/evidence-ledger.md`, theme T1).

### 3.2 G3: do capable agents break each other on disjoint files? Two negatives

Space Bunny gave two `zcodex` executors separate tasks on separate files, with no oracle and no hint that the other task existed (`research/space-bunny/g3-no-symbol-overlap/results-real-agents.md`).

- **Round 1 (shared cache contract):** base, A, B and A+B all pass. Swapping in a deliberately broken B made A+B fail, so the test could catch the bug; the agents simply did not write it. Agent B avoided it by explicitly modelling a memoizing cache, which it inferred from base files it had to read (`research/space-bunny/g3-no-symbol-overlap/results-real-agents.md`).
- **Round 2 (contract hidden in a third-party file):** again all four pass (`research/space-bunny/g3-non-discoverable/results-real-agents.md`).
- **The confound:** both rounds' briefs pointed at the behaviour that mattered, so neither tested whether agents find the coupling unaided. The author therefore refused to invoke his own pre-registered conclusion (`research/space-bunny/g3-non-discoverable/results-real-agents.md`). A neutral-brief rerun was planned but never launched (`research/space-bunny/g3-signposting-comparison-plan.md`, status "PLAN ONLY").

What it means: agents reason correctly about a contract when told it matters. Any demo that seeds such a conflict shows a capability, not a rate (`research/space-bunny/g3-no-symbol-overlap/results-real-agents.md`).

### 3.3 A06 review cards: no measured benefit

- **First real decision (N=1):** the reviewer approved the change at confidence 80 both before and after reading the change-story card. The card itself had a wrong number (3.0 s where the source says 1000 ms), and two of the reviewer's card findings were later corrected or withdrawn (`research/muse/a06-phase-b-record.md`).
- **Two-format pilot:** both arms reached REJECT, the known right answer. The "card is cheaper" reading (5 vs 14 tool calls) was withdrawn because the card arm was barred from raw sources the other arm used, and the packet changed mid-experiment. It was a calibration, not an efficacy test (`research/muse/a06-pilot-adoption/analysis.md`).
- **Grok's adoption decision** on a ZCode runner rejected its claim of "0 eligible warnings"; the corrected runner now reports "unknown" (`research/grok/a06-adoption-decision.md`). The same note found CodeRabbit already ships layered review and stale-snapshot refusal, and named the one difference left to test: a card that records what it does *not* guarantee (`research/grok/a06-adoption-decision.md`).
- **Antigravity's operational review** of the advisory stack scored it CONDITIONAL (6.8/10): useful for multi-agent pipelines, not to be mandated for ordinary maintenance (`research/antigravity/adoption/A06-ADVISORY-ADOPTION-DECISION.md`).

### 3.4 Storage (A16): real pain, ordinary tools nearly as good

- **The founder's host** (read-only scan): 472 linked worktrees, 111.7 GiB physical. Dependency and build directories are 62.1% of that; copied Python `.venv` folders alone are 57.3 GiB across 215 dirs. 264 worktrees (82.4 GiB summed) sit on commits already in `origin/main`, so cleanup is the bigger lever (`research/claude/u7-real-worktree-measurement.md`).
- **Ordinary pnpm** already shares installs: two trees sum to 458.984 MiB but occupy 229.617 MiB, about 49.97% less (`research/codex/package-storage-validation.md`).
- **The gate kept failing:** 42.37% and 36.05% (uv hardlink and symlink), 48.17% (clean state), and finally 47.76% against an ordinary-clone arm at 47.38%, all under the >50% bar (`research/evidence-ledger.md`, `research/antigravity/r8-worktree-d1-benchmark.md`).
- **A real hazard found:** an in-place write through a shared uv cache leaked into the other task (`research/antigravity/evidence.md`, E-A040). Three earlier "measurements" (E-A035 to E-A037) were hypothetical arithmetic and were retracted (`research/evidence-ledger.md`).

### 3.5 Duplicate execution and handoff

- **Inner duplicate:** the installed `zcodex` ran each shell call twice (count 2 per operation); the patched mode ran it once (`research/antigravity/r8-dupexec-count-verification.md`). A live append probe confirmed 2 marker lines before and 1 after (`research/antigravity/r9-runtime-single-effect-verification.md`).
- **Outer retries remain:** a separate trace under the patched mode showed the model re-issuing the same command about 16 s later, both runs exiting 0. Verdict of record: "no exactly-once claim" (`research/antigravity/r9-runtime-single-effect-verification.md`).
- **Cost of finding out:** one debug build grew the disk by about 12.26 GB, a resource violation; builds were frozen (`research/antigravity/r9-runtime-single-effect-verification.md`).
- **Incidence can't be read from logs:** inner duplicates never reach rollout logs. 159 quick identical re-issues across 147 rollouts were traced to tool-signature rejections, polling and ordinary re-runs (`research/antigravity/r11-real-duplicate-incidence.md`).
- **Handoff (A10):** a cold worker recovered the next action from plain Git in 27 s; a second applied a 2104-byte interrupted patch onto a moved base and passed 39/39 and 37/37 tests with no repair. Both are N=1 and the second's start time is unknown (`research/shortlist-6.md`).

## 4. Demand and competitor map

**Pain is documented, prevalence is not.** The evidence ledger indexes first-hand reports by theme: 70 Hacker News items, 52 maintainer items, 65 workflow and competitor items, 29 Codex items, among others. It warns that inclusion "does not establish prevalence" (`research/evidence-ledger.md`). The strongest themes were integrating parallel agent work (structural, but rare: see 3.1), review burden (most volume, most crowded remedies) and worktree disk use (first-hand founder pain, measured in 3.4) (`research/evidence-ledger.md`).

| Our idea | Who already does it | What is left |
|---|---|---|
| Warn agents early (A01) | Collide ships live, agent-consumed collision warnings over MCP (`declare_intent`, `check_collisions`). Its published numbers are vendor token metrics; nobody reproduced anything (`research/space-bunny/competitor-wip-verification-round2.md`) | Collide shows no evidence of running a combined test on two unfinished trees. "Warn early" alone is no longer novel (same file) |
| Catch combined breakage (A01) | GitHub PR merge refs, merge queues, GitLab merge trains and Bors run the same merge-then-test oracle before landing (`research/antigravity/demand/incumbent-premerge-and-buyer-workflow.md`) | Only the timing: a push-time warning can save a long agent run. Pairwise checks grow quadratically, 190 pairs at 20 agents (same file) |
| Pre-code intent claims (A02) | Foremerge: local-first, one SQLite store, self-declared scopes that can miss each other; no benchmark of its benefit (`research/antigravity/demand/foremerge-firsthand-verification.md`) | Multi-machine coordination is out of its scope (same file) |
| Review cards (A06) | CodeRabbit layered review and stale-snapshot refusal, Copilot review, Graphite (`research/evidence-ledger.md` T3, `research/grok/a06-adoption-decision.md`) | Recording what a review does not guarantee (`research/grok/a06-adoption-decision.md`) |
| Storage (A16) | pnpm shared store, ArtifactFS lazy hydration (`research/evidence-ledger.md` T7) | Remote workspaces, unmeasured (`research/shortlist-6.md`) |
| Best-of-N (A05), handoff (A10) | Cursor best-of-n, Agent HQ; Entire checkpoint refs and resume (`research/claude/workflows-competitors.md`) | Merging attempts back, which best-of-n "does not" do (same file) |
| Exactly-once side effects (A09) | At least 7 guard products launched Feb to Oct 2026, plus idempotency keys and durable execution; none is keyed to Git refs (`research/evidence-ledger.md` T11) | A narrow gap at Git-ref publication (same file) |

**Demand limits, from Antigravity's market reads.** Production agents mostly run in disposable containers and hand back a patch, with no Git credentials inside the sandbox; locked-down egress and token risk confine a remote agent-branch server to a narrow niche (`research/antigravity/demand/container-and-patch-workflows.md`). These are desk analyses: buyer willingness to pay "remains unproven" (`research/antigravity/demand/incumbent-premerge-and-buyer-workflow.md`). A hosted orchestrator, Terragon, shut down on 2026-02-09 (`research/claude/workflows-competitors.md`).

## 5. Architecture invariants

These held across every candidate and carried into the product (`research/shortlist-6.md`, "Shared implementation", unless noted):

1. One Artifacts fork per task. An agent's token writes only its own fork; a token's time limit is not path or ref enforcement.
2. One canonical publisher. It rechecks the exact head, uses non-force updates and rejects stale receipts.
3. Platform events arrive after the push, may repeat and may arrive out of order. Deduplicate them and treat them as observations, never as a pre-push guard (also `research/evidence-ledger.md` T9).
4. Merges and tests run in an external runner, because the Artifacts binding has no merge, diff or ref-write API (`research/claude/workflows-competitors.md`).
5. Changing the baseline tests needs independent approval. A candidate agent never approves its own tests.
6. A receipt names base, candidate, merged and deployed SHAs, tree, policy, environment and runner. It attests that a run happened, not that the code is correct.
7. An unchecked or inconclusive state is never shown as safe (`SUBMISSION.md`); missing data fails closed to "unknown" (`research/antigravity/reviews/REV-L3-ATTESTATION-CONTRACT.md`).
8. Mutations are idempotent: stable operation ids, check before acting, verify outcomes rather than trusting reported output (`research/evidence-ledger.md` T11).

Platform limits to design around: 1 GB per repo, 32 MB per blob, push over protocol v1 only (`research/evidence-ledger.md` T9).

## 6. Adoption and dogfood findings

- **Single agent: use plain Git.** Same task, same resulting tree hash, 16/16 tests in both: ordinary worktree 0.200 s over 7 commands, Agent Branches 1.143 s over 15 commands (5.7x). Verdict: DECLINE for single-actor work (`research/antigravity/adoption/REPORT-UNFAMILIAR-ADOPTER-T1.md`).
- **Concurrent refactor (scripted patches):** a baseline with only post-merge CI let 1 defect reach `main`; the radar flagged it before landing in 0.539 s. Total wall time 1.84 s vs 6.41 s, and about 155 MB of extra daemons (`research/antigravity/adoption/REPORT-UPRT-CONCURRENT-GATE.md`). Any standard pre-merge check would have caught the same failure (`research/antigravity/demand/incumbent-premerge-and-buyer-workflow.md`).
- **"Adoption confirmed" was an overclaim.** The first real fork run was relabelled "workflow transport confirmed": the work was two doc lines in separate files, and runner results are stored as claims (`research/antigravity/adoption/REAL-FORK-ADOPTION-REPORT.md`).
- **Real use found real gaps:** a newcomer requested changes to a `push_batch` patch because a mid-batch failure loses the accepted prefix (`research/antigravity/dogfood/NEWCOMER-ADOPTION-DECISION-7DE6836.md`); the packaged SDK was CONDITIONAL, missing a per-task token on the CLI (`research/antigravity/dogfood/REPORT-SDK-PACKAGED-FIRSTUSE.md`); Node needs about 1.46 GB of virtual address space, so limit memory by RSS or cgroup, not `ulimit -v` (`research/antigravity/adoption/REPORT-REALNODE-SIDECAR-PILOT.md`).
- **Scripted personas are not users.** Some dogfood reports say so explicitly (`research/antigravity/dogfood/CONSUMER-NEWCOMER-DECISION-OBSERVATION.md`).

## 7. Lessons

1. **Instrument the harness before trusting a result.** In G3 the first composition copied B's whole tree over A's work, so A+B "passed" for the wrong reason; only a liveness probe caught it (`research/space-bunny/g3-no-symbol-overlap/results-real-agents.md`).
2. **Give both arms the same information.** The A01 pilot gave the arms different prompts and oracle access (`research/debate/codex-a01-pilot-review.md`); the A06 pilot barred one arm from raw sources (`research/muse/a06-pilot-adoption/analysis.md`). Both had to be thrown out as comparisons.
3. **A brief can leak the answer.** Both G3 briefs named the behaviour that mattered, which voided the pre-registered conclusion (`research/space-bunny/g3-non-discoverable/results-real-agents.md`).
4. **Label models as models, and keep one denominator.** Three storage "measurements" were arithmetic and were retracted; an early "~80%" figure mixed per-directory sums with a physical union and became 62.1% (`research/evidence-ledger.md`, `research/claude/u7-real-worktree-measurement.md`).
5. **Do not move the bar after the result.** A16's 50% gate stayed at 50%, and a run at N=3 just to turn it green was refused (`research/shortlist-6.md`, `research/codex/retained-lanes-review-2324.md`).
6. **Preserve evidence before a rerun.** A second A01 feasibility attempt overwrote the first attempt's database rows, so the cause of its failure is unknown (`research/antigravity/r12-a01-loss-inventory-and-diagnosis.md`).
7. **Relabel an overclaim in the open.** "Adoption confirmed" became "workflow transport confirmed" (`research/antigravity/adoption/REAL-FORK-ADOPTION-REPORT.md`); "the card is cheaper" was withdrawn (`research/muse/a06-pilot-adoption/analysis.md`).
8. **Budget the machine.** One diagnostic build added about 12.26 GB (`research/antigravity/r9-runtime-single-effect-verification.md`).
9. **Agreement is an explicit act.** Read receipts, a third engine's vote or silence are not consent; only matching signoffs count (`research/consensus.md`, `research/debate/codex-open-disagreements.md`).
10. **Tests must be able to fail.** Most negative reviews in section 8 found tests that pass whatever the code does: surviving mutants, an empty-input "pass", a file with zero assertions.

## 8. Review verdicts by family, and the 22 negative verdicts

Antigravity ran most independent reviews and audits: 226 documents (222 in `research/antigravity/reviews/`, 1 in its `archive/`, 3 in `research/antigravity/audit/`), next to 10 reviewer launch prompts and 1 receipt file. Grouped by file name (our grouping; counts verified with `git ls-tree` at the tag):

| Family | Reviews | Negative |
|---|---|---|
| Agent bus, file bus, typed SSH, Windows client, fleet trials | 40 | 4 |
| Dashboard, hourly export, daily reports, review UI | 38 | 4 |
| Quota launcher and capacity | 34 | 2 |
| Supervision and continuation runtime | 32 | 4 |
| Product adoption, runbooks, demos | 27 | 3 |
| SDK, webhook auth, publication guard | 24 | 2 |
| Scale-to-50 task audits | 15 | 3 |
| Metrics collector and task tracker | 13 | 0 |
| Audits (repo sanitization, credential lineage, retry lineage) | 3 | 0 |

**The 22 reviews that opened with a negative verdict** (REJECT, REQUEST_CHANGES or a confirmed critical defect), each read in full at the verdict line. All paths are under `research/antigravity/reviews/`.

| Review | Why | Later |
|---|---|---|
| `REV-BUS-EXACTPIN-BB8DCAD.md` | Legacy pin lacks the successor's durability fixes | |
| `REV-BUS-TYPED-SSH-PORTABILITY.md` | POSIX-only imports and manifest gaps block Windows | |
| `REV-WINDOWS-DRIVER-2FD1BE4E.md` | Redaction regex can leak Base64 bearer tokens | |
| `REV-SYNTHESIS-AGENT-BRANCHES-4315-20261005.md` | Test file stubbed with `pass`, zero assertions | |
| `REV-L4-UI-3568780.md` | The named guard is dead code; a green "clean" badge shows during an outage | Accepted in `REV-L4-UI-99C3C97.md` |
| `REV-L4-DOM-NEGATIVE.md` | The fix double-escapes text; "zero clean badges" claim not literally true | |
| `REV-L6-CA16-REVIEW.md` | Worklog quarantine misses 2 of 3 files; no regression tests | |
| `REV-REPORT-ROLE-STRUCTURE-20261006.md` | Omits the rule that principals do not review code | |
| `REV-QL-FIRST-ACTION-BYPASS.md` | Any marker file bypasses the first-action check; schema whitelisting rejected as a pseudo-fix | |
| `REV-SYSTEMD-SCOPE-CONTAINMENT-C2087.md` | Direct-scope baseline fails the failure-pattern audit | Refactored adapter verified in the same review |
| `REV-SUPERVISION-C14B474.md` | Inverted premise: the "fallback" binary removes the fail-closed draft guard | |
| `REV-LIMITER-321FEB5.md` | Spoofable-header mutants survive all tests; a "window edge" test is 15 s off | |
| `REV-READINESS-CORRECTION.md` | Proposed producer fixes have serious failure modes | |
| `REV-READINESS-PRODUCER-REPAIR-SPEC.md` | Brittle engine-name coupling, PID-recycling risk, no draft protection | |
| `REV-DEMO-RUNBOOK-HARNESS.md` | Four validation defects; mutants survive | Re-review accepted in the same file |
| `REV-FORK-ADOPTION-FCD7985.md` | "Adoption" overclaimed; no stale-push case; plaintext tokens left in scratch | Report relabelled |
| `REV-RUNBOOK-SEED-LEASE-4C6FDD5.md` | README confuses the sidecar token with a write token; placeholders do not run | |
| `REV-SDK-PUSH-BATCH-7DE6836.md` | No proof of one effect per batch, no atomic batch | |
| `REV-WEBHOOK-AUTH-F3F06D2.md` | A replayed nonce returns 401 instead of 409 | |
| `REV-SCALE50-39-HOURLY-API-TESTS-20261006.md` | "Fake pass": asserts only list length on empty input | |
| `REV-SCALE50-41-INTEGRATION-PLAN-20261006.md` | No `127.0.0.1` binding, plus a proxy loophole | Accepted after remediation |
| `REV-SCALE50-53-MOBILE-QA-20261006.md` | Wrong query parameter, a pass the author's own log contradicts, 60+ tracked files modified | Accepted after remediation |

An earlier machine-made list of "22 negatives" (a cleanup draft, never committed) was wrong on 9 entries, mostly ACCEPT verdicts that mention "fail-closed" or a prior rejection, and missed 9 real ones; the list above replaces it. A separate negative finding sits in a capacity review: 50 concurrent task units on one host is "UNPROVEN and INFEASIBLE" (`research/antigravity/reviews/REV-SCALE50-RAM-PROOF-AND-CAPACITY-20261005.md`).

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
