# Research: what we explored, what we measured, what we learned

One research summary for the whole project, across every engine (Claude, Codex, Grok, Muse, Space Bunny, ZCode, Antigravity). It tells a newcomer how the project decided what to build and what did not work.

## How to read the citations

Every path in parentheses is a file at the git tag `pre-cleanup-20261007` (commit `7a0b82c`, 7 Oct 2026). Read any of them with:

```
git show pre-cleanup-20261007:<path>
```

Commits are quoted as the source gives them. Every number was checked against its source file. Anything we could not check is marked **unverified**.

## The short version

The contest asked for an agent-native Git platform on Cloudflare Workers and Artifacts (`BRIEF.md`). We wrote 20 approaches and argued over a shortlist of six. Nobody ever signed a shortlist (`research/consensus.md`). The lead idea, a live radar that warns agents when their unfinished work stops fitting together (A01), lost its "primary" status after a fair live test with real agents showed no difference between agents that could see each other's unfinished work and agents that could not (`research/grok/a01-fair-results.md`). The storage idea (A16) missed its own pass mark (`research/antigravity/r8-worktree-d1-benchmark.md`). The submitted product, Agent Branches, keeps per-task forks, a live conflict radar and a review view (`SUBMISSION.md`).

## 1. The 20 approaches and what happened to each

Claude wrote and scored the 20 approaches on 2 Oct 2026 (contest score out of 100: half originality, a quarter visible concurrency, a quarter demo clarity). The scores are Claude's alone. Unless noted, the source is `research/approaches-20.md`; the outcome is the last recorded state.

| ID | Approach, in one line | Contest score | Outcome |
|---|---|---|---|
| A01 | Live Integration Radar: trial-merge every live agent head on each push and warn agents when their work stops composing | 85 | Kept as a conditional research hypothesis, **no longer primary** after the fair live pair showed no separation |
| A02 | Lease-bound path claims, enforced when work lands | 70 | Never shortlisted; Foremerge already specifies this protocol |
| A03 | Merged-state gate that re-runs a failed task on the fresh base | 80 | Parked in v2 with a reopen test |
| A04 | Semantic contract sentinel for shared APIs | 75 | Parked in v2 with a reopen test |
| A05 | Fork tournament: N attempts at one task, compare by behaviour, land one | 85 | Provisionally parked (`research/shortlist-6.md`); the one real task was adjudicated a **TIE** (`research/zcode/independent/a05-adjudication/VERDICT.md`) |
| A06 | Change-story review queue: review intent and risk, not raw diffs | 65 | Kept as a hypothesis; real pain, no shown benefit (`research/shortlist-6.md`) |
| A07 | Maintainer inbound quarantine: no human sees a contribution until a reproducer passes | 75 | Parked in v2; a later demand scout gave no verdict (`research/zcode/independent/a07-demand-gate/findings-draft.md`) |
| A08 | Independent AI reviewer panel on every push | 50 | "Likely feature of A06" |
| A09 | Exact-SHA verification receipts | 60 | Re-scoped to exactly-once Git-ref publication receipts, then parked |
| A10 | Durable handoff: plan, decisions and exact base travel with the task | 65 | Provisionally parked: cold restarts worked from plain Git (`research/shortlist-6.md`) |
| A11 | Merge decision ledger ("why this one won") | 70 | Never shortlisted |
| A12 | Quarantine forks and capability tokens | 65 | Cloudflare's own recommended practice, so low originality; refinement parked |
| A13 | Undo everything one agent session did | 75 | In the first six, parked in v2 |
| A14 | A live preview URL and private data per agent | 75 | **Folded into A01**; an ordinary control did as well (`research/shortlist-6.md`) |
| A15 | Push-triggered fast test lane | 50 | Never shortlisted; low originality |
| A16 | Zero-checkout lazy agent workspaces (the founder's disk pain) | 70 | **Parked**: missed its >50% storage gate three times |
| A17 | Fork-is-the-task board | 65 | A possible UI shell, not a product |
| A18 | Multi-repo change sets with recovery | 75 | Parked; the scout found configured Pact `can-i-deploy` already covers it (`research/zcode/independent/a18-scout/findings.md`) |
| A19 | Maintenance swarm with batch landing | 75 | In the first six, then folded into A01 batch mode |
| A20 | Earned autonomy per agent configuration | 60 | Never shortlisted |

## 2. Shortlist outcomes and kill criteria

**How the shortlist moved.** Claude's first six (A01, A05, A07, A14, A13, A19) were replaced by a v2 six (A01, A14, A16, A05, A06, A10) (`research/approaches-20.md`). Codex owned the shortlist file. Its last version, draft 10, keeps only **two research hypotheses, A01 (demoted) and A06**, leaves **four product places unfilled**, folds A14 into A01, and parks A16, A10 and A05 (`research/shortlist-6.md`).

**Nothing was ever signed.** The agreed procedure was: freeze the file, each lead engine hashes the exact bytes and sends `SIGNOFF <sha256>`, and any later edit voids it. No SIGNOFF is recorded (`research/consensus.md`). Antigravity once declared "final consensus" on its own six; Codex rejected that because it lacked both leads' approval (`research/consensus.md`). In round 1 the two leads also disagreed on the primary build: Claude favoured an A01-led six, Codex a provisional A14 build (`research/debate/codex-open-disagreements.md`).

**The gate every lane had to pass.** At least two real coding agents working at the same time, an Artifacts fork-and-push lifecycle, runnable open source, and a 5 to 10 minute demo. "Scripts pretending to be agents do not satisfy that gate" (`research/shortlist-6.md`). No candidate passed it during the research phase (`research/shortlist-6.md`).

**Kill criteria, per candidate.** Each candidate carried a written rule for when to drop it:

| ID | Kill or park rule | What happened |
|---|---|---|
| A01 | Kill if, on 10 replayed pairs, it flags real conflicts earlier than PR time in under half, or agents ignore warnings (`research/approaches-20.md`). Drop primary status without an outcome or time advantage over worktrees plus completion-time tests (`research/shortlist-6.md`) | Primary withdrawn (3.1). Reopen only with a pre-registered neutral task family where the hazard occurs naturally (`research/approaches-20.md`) |
| A16 | >40% fewer physical bytes than sparse worktrees plus pnpm (`research/approaches-20.md`); env-sharing gate >50% whole-footprint savings at two tasks (`research/shortlist-6.md`) | Failed (3.4); the bar was not moved (`research/shortlist-6.md`) |
| A05 | At least 3 of 5 outcome wins plus a review advantage; park if equal at higher cost (`research/shortlist-6.md`) | One task, a TIE; parked as a portfolio decision, not a falsification (`research/shortlist-6.md`) |
| A06 | Blind seeded-bug test: ≥30% shorter review, equal catch rate (`research/shortlist-6.md`) | Never run as designed; other runs showed no benefit (3.3) |
| A10 | Beat plan file plus Entire resume plus git log on five restart tasks (`research/approaches-20.md`) | Parked after two cold restarts worked (3.5) |
| A14 | Fold into A01 if plain `wrangler` plus Workers Previews does the workflow in ten minutes (`research/shortlist-6.md`) | Folded: isolation and the ordinary control both passed (`research/shortlist-6.md`) |
| A18 | Park if configured Pact `can-i-deploy` rejects the bad combination and resumes after interruption (`research/shortlist-6.md`) | Parked; resume documented, not reproduced (`research/zcode/independent/a18-scout/findings.md`) |
| A09 | One publication per operation id on replayed duplicate traces (`research/approaches-20.md`) | Not run; demand was for side effects in general, not Git refs (`research/approaches-20.md`) |

## 3. Experiment results

### 3.1 A01 fair pair: a null result

Does an agent that sees a peer's unfinished work do better than one that meets it only at completion? Grok ran one registered pair on 2 Oct (commits `7ef2269`, `2f4681c`): a completion arm and a live arm, each with two real `zcodex` writers on complementary tasks (`research/grok/a01-fair-results.md`).

- Every first product commit already passed the task check and the composition oracle. Zero source repair, no warning notice. The live arm did see the peer's bytes before committing; it changed nothing (`research/grok/a01-fair-results.md`).
- Codex replayed the live arm independently: all eight checks exit 0, including the combined tree, and nothing changed after the first source commit (`research/codex/a01-live-independent-replay.json`).
- Decision D-G25: "null separation" (`research/grok/a01-fair-results.md`). Claude proposed and Codex accepted dropping A01's primary status (`research/consensus.md`).

The earlier pilot, D-G23, does not count: its arms had different prompts, and the notice arm "passed" by not doing the task (`research/debate/codex-a01-pilot-review.md`, `research/evidence-ledger.md`). Outside studies agree the hazard is real but rare: cross-agent pairs were 0.5% of co-active pairs in one (`research/evidence-ledger.md`, T1).

### 3.2 G3: do capable agents break each other on disjoint files? Two negatives

Space Bunny gave two `zcodex` executors separate tasks on separate files, no oracle, and no hint the other task existed (`research/space-bunny/g3-no-symbol-overlap/results-real-agents.md`).

- **Round 1 (shared cache contract):** base, A, B and A+B all pass. A deliberately broken B made A+B fail, so the test could catch the bug; the agents just did not write it. Agent B avoided it by modelling the cache it inferred from base files (`research/space-bunny/g3-no-symbol-overlap/results-real-agents.md`).
- **Round 2 (contract hidden in a third-party file):** again all four pass (`research/space-bunny/g3-non-discoverable/results-real-agents.md`).
- **The confound:** both briefs pointed at the behaviour that mattered, so neither tested unaided discovery; the author declined to invoke his pre-registered conclusion (`research/space-bunny/g3-non-discoverable/results-real-agents.md`). A neutral-brief rerun stayed "PLAN ONLY" (`research/space-bunny/g3-signposting-comparison-plan.md`).

Meaning: agents handle a contract when told it matters; a demo that seeds such a conflict shows a capability, not a rate (`research/space-bunny/g3-no-symbol-overlap/results-real-agents.md`).

### 3.3 A06 review cards: no measured benefit

- **First real decision (N=1):** APPROVE at confidence 80 before and after reading the card. The card had a wrong number (3.0 s; the source says 1000 ms), and two of the reviewer's card findings were later corrected or withdrawn (`research/muse/a06-phase-b-record.md`).
- **Two-format pilot:** both arms reached the known answer, REJECT. "Card is cheaper" (5 vs 14 tool calls) was withdrawn: the card arm was barred from raw sources and the packet changed mid-run. A calibration, not an efficacy test (`research/muse/a06-pilot-adoption/analysis.md`).
- **Grok's adoption decision** rejected a ZCode runner's "0 eligible warnings" claim; the corrected runner reports "unknown". It also found CodeRabbit already ships layered review, leaving one difference to test: a card that records what it does *not* guarantee (`research/grok/a06-adoption-decision.md`).
- **Antigravity's operational review** scored the advisory stack CONDITIONAL (6.8/10): not for ordinary maintenance (`research/antigravity/adoption/A06-ADVISORY-ADOPTION-DECISION.md`).

### 3.4 Storage (A16): real pain, ordinary tools nearly as good

- **The founder's host:** 472 linked worktrees, 111.7 GiB physical; dependency and build dirs are 62.1% of it, copied Python `.venv` dirs 57.3 GiB across 215. 264 worktrees (82.4 GiB summed) sit on commits already in `origin/main`: cleanup is the bigger lever (`research/claude/u7-real-worktree-measurement.md`).
- **Ordinary pnpm** already shares installs: two trees sum to 458.984 MiB but occupy 229.617 MiB, about 49.97% less (`research/codex/package-storage-validation.md`).
- **The gate kept failing:** 42.37% and 36.05% (uv hardlink and symlink), 48.17% (clean state), and finally 47.76% against an ordinary-clone arm at 47.38%, all under the >50% bar (`research/evidence-ledger.md`, `research/antigravity/r8-worktree-d1-benchmark.md`).
- **A real hazard:** an in-place write through a shared uv cache leaked into the other task (`research/antigravity/evidence.md`, E-A040).

### 3.5 Duplicate execution and handoff

- **Inner duplicate:** the installed `zcodex` ran each shell call twice; the patched mode once (`research/antigravity/r8-dupexec-count-verification.md`); a live probe wrote 2 marker lines before, 1 after (`research/antigravity/r9-runtime-single-effect-verification.md`).
- **Outer retries remain:** a separate trace under the patched mode showed the model re-issuing the same command about 16 s later, both runs exiting 0. Verdict of record: "no exactly-once claim" (`research/antigravity/r9-runtime-single-effect-verification.md`).
- **Incidence can't be read from logs:** inner duplicates never reach rollout logs; 159 quick re-issues in 147 rollouts were not caused by inner denials (`research/antigravity/r11-real-duplicate-incidence.md`).
- **Handoff (A10):** a cold worker recovered the next action from plain Git in 27 s; another applied a 2104-byte interrupted patch onto a moved base, 39/39 and 37/37 tests green, no repair. Both N=1 (`research/shortlist-6.md`).

## 4. Demand and competitor map

**Pain is documented, prevalence is not.** The evidence ledger indexes 70 Hacker News, 52 maintainer, 65 workflow and 29 Codex items, among others, and warns that inclusion "does not establish prevalence". Strongest themes: integrating parallel agent work (structural but rare), review burden (most volume, crowded remedies), worktree disk use (`research/evidence-ledger.md`).

| Our idea | Who already does it | What is left |
|---|---|---|
| Warn agents early (A01) | Collide ships live collision warnings to agents over MCP; its numbers are unreproduced vendor token metrics (`research/space-bunny/competitor-wip-verification-round2.md`) | No sign Collide tests two unfinished trees together; "warn early" alone is not novel (same file) |
| Catch combined breakage (A01) | PR merge refs, merge queues, merge trains and Bors run the same merge-then-test oracle (`research/antigravity/demand/incumbent-premerge-and-buyer-workflow.md`) | Timing only; pairwise checks grow quadratically, 190 pairs at 20 agents (same file) |
| Pre-code intent claims (A02) | Foremerge: local-first, self-declared scopes that can miss each other, no benefit benchmark (`research/antigravity/demand/foremerge-firsthand-verification.md`) | Multi-machine coordination (same file) |
| Review cards (A06) | CodeRabbit, Copilot review, Greptile (`research/evidence-ledger.md` T3) | Stating what a review does not guarantee (`research/grok/a06-adoption-decision.md`) |
| Storage (A16) | pnpm shared store, ArtifactFS lazy hydration (`research/evidence-ledger.md` T7) | Remote workspaces, unmeasured (`research/shortlist-6.md`) |
| Best-of-N (A05), handoff (A10) | Cursor best-of-n, Agent HQ; Entire checkpoint refs and resume (`research/claude/workflows-competitors.md`) | Merging attempts back, which best-of-n "does not" do (same file) |
| Exactly-once side effects (A09) | At least 7 guard products launched Feb to Oct 2026; none keyed to Git refs (`research/evidence-ledger.md` T11) | Narrow gap at Git-ref publication (same file) |

**Demand limits.** Production agents mostly run in disposable containers and hand back a patch with no Git credentials inside; egress lockdown confines a remote agent-branch server to a narrow niche (`research/antigravity/demand/container-and-patch-workflows.md`). These are desk analyses; willingness to pay "remains unproven" (`research/antigravity/demand/incumbent-premerge-and-buyer-workflow.md`). A hosted orchestrator, Terragon, shut down on 2026-02-09 (`research/claude/workflows-competitors.md`).

## 5. Architecture invariants

Every candidate shared these rules (`research/shortlist-6.md`, "Shared implementation", unless noted):

1. One Artifacts fork per task; an agent's token writes only its own fork. A token's time limit is not ref enforcement.
2. One canonical publisher: it rechecks the exact head, never force-pushes, rejects stale receipts.
3. Platform events come after the push and may repeat or reorder: deduplicate, treat as observations, never as a pre-push guard (also `research/evidence-ledger.md` T9).
4. Merges and tests run in an external runner; the Artifacts binding has no merge, diff or ref-write API (`research/claude/workflows-competitors.md`).
5. Changing baseline tests needs independent approval; an agent never approves its own tests.
6. A receipt names base, candidate, merged and deployed SHAs, policy, environment and runner. It attests a run, not correctness.
7. An unchecked or inconclusive state is never shown as safe (`SUBMISSION.md`); missing data fails closed to "unknown" (`research/antigravity/reviews/REV-L3-ATTESTATION-CONTRACT.md`).
8. Mutations are idempotent: stable operation ids, check before acting, verify outcomes (`research/evidence-ledger.md` T11).

Platform limits to design around: 1 GB per repo, 32 MB per blob, push over protocol v1 only (`research/evidence-ledger.md` T9).

## 6. Adoption and dogfood findings

- **Single agent: use plain Git.** Same tree hash, 16/16 tests in both; plain worktree 0.200 s and 7 commands, Agent Branches 1.143 s and 15 (5.7x). DECLINE for single-actor work (`research/antigravity/adoption/REPORT-UNFAMILIAR-ADOPTER-T1.md`).
- **Concurrent refactor (scripted patches):** a post-merge-CI baseline let 1 defect reach `main`; the radar flagged it before landing in 0.539 s, at 6.41 s vs 1.84 s wall time and about 155 MB of daemons (`research/antigravity/adoption/REPORT-UPRT-CONCURRENT-GATE.md`). Any pre-merge check would catch the same failure (`research/antigravity/demand/incumbent-premerge-and-buyer-workflow.md`).
- **"Adoption confirmed" was an overclaim,** relabelled "workflow transport confirmed": the work was two doc lines in separate files (`research/antigravity/adoption/REAL-FORK-ADOPTION-REPORT.md`).
- **Real use found real gaps:** a `push_batch` patch loses the accepted prefix on a mid-batch failure (`research/antigravity/dogfood/NEWCOMER-ADOPTION-DECISION-7DE6836.md`); the CLI lacked a per-task token (`research/antigravity/dogfood/REPORT-SDK-PACKAGED-FIRSTUSE.md`); Node needs about 1.46 GB of virtual address space, so cap RSS, not `ulimit -v` (`research/antigravity/adoption/REPORT-REALNODE-SIDECAR-PILOT.md`).
- **Scripted personas are not users,** as some reports say themselves (`research/antigravity/dogfood/CONSUMER-NEWCOMER-DECISION-OBSERVATION.md`).

## 7. Lessons

1. **Instrument the harness before trusting a result.** In G3 the first composition overwrote A's work, so A+B "passed" for the wrong reason (`research/space-bunny/g3-no-symbol-overlap/results-real-agents.md`).
2. **Give both arms the same information.** The A01 pilot (`research/debate/codex-a01-pilot-review.md`) and the A06 pilot (`research/muse/a06-pilot-adoption/analysis.md`) gave arms unequal access and were void as comparisons.
3. **A brief can leak the answer.** Both G3 briefs named the behaviour that mattered, which voided the pre-registered conclusion (`research/space-bunny/g3-non-discoverable/results-real-agents.md`).
4. **Label models as models, and keep one denominator.** Three storage "measurements" were arithmetic and were retracted; an early "~80%" figure mixed per-directory sums with a physical union and became 62.1% (`research/evidence-ledger.md`, `research/claude/u7-real-worktree-measurement.md`).
5. **Do not move the bar after the result.** A16's 50% gate stayed at 50%, and a run at N=3 just to turn it green was refused (`research/shortlist-6.md`, `research/codex/retained-lanes-review-2324.md`).
6. **Preserve evidence before a rerun.** A second A01 feasibility attempt overwrote the first one's database rows; its failure cause is now unknown (`research/antigravity/r12-a01-loss-inventory-and-diagnosis.md`).
7. **Relabel an overclaim in the open.** "Adoption confirmed" became "workflow transport confirmed" (`research/antigravity/adoption/REAL-FORK-ADOPTION-REPORT.md`); "the card is cheaper" was withdrawn (`research/muse/a06-pilot-adoption/analysis.md`).
8. **Budget the machine.** One diagnostic build added about 12.26 GB (`research/antigravity/r9-runtime-single-effect-verification.md`).
9. **Agreement is an explicit act.** Read receipts, third-party votes or silence are not consent (`research/consensus.md`, `research/debate/codex-open-disagreements.md`).
10. **Tests must be able to fail.** Many negative reviews in section 8 found tests that pass whatever the code does: surviving mutants, an empty-input "pass", zero assertions.

## 8. Review verdicts by family, and the 22 negative verdicts

The independent reviews and audits kept under `research/antigravity/` number 226 documents (222 in `research/antigravity/reviews/`, 1 in its `archive/`, 3 in `research/antigravity/audit/`), plus 10 launch prompts and 1 receipt. Grouped by file name (our grouping):

| Family | Reviews | Negative |
|---|---|---|
| Agent bus, file bus, typed SSH, Windows client, fleet trials | 40 | 4 |
| Dashboard, hourly export, daily reports, review UI | 38 | 4 |
| Quota launcher and capacity | 34 | 2 |
| Supervision, delivery readiness, continuation runtime | 31 | 3 |
| Product adoption, runbooks, demos | 27 | 3 |
| SDK, webhook auth, rate limiter, publication guard | 25 | 3 |
| Scale-to-50 task audits | 15 | 3 |
| Metrics collector and task tracker | 13 | 0 |
| Audits (repo sanitization, credential lineage, retry lineage) | 3 | 0 |

**The 22 reviews that opened with a negative verdict** (REJECT, REQUEST_CHANGES or a confirmed critical defect), each checked at its verdict line; paths under `research/antigravity/reviews/`:

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

All raw material (harness code, fixtures, JSON results, reviews, per-agent journals) stays readable in git.

- Now: tag `pre-cleanup-20261007` (commit `7a0b82c`). `git show pre-cleanup-20261007:<path>` reads a file; `git ls-tree -r --name-only pre-cleanup-20261007 research/` lists them.
- Later: the same files will also sit under the tag `research-archive-20261007`. Swap the tag name; paths stay the same.

Where to start inside the tag: `research/approaches-20.md` (all 20, scores, disposition log), `research/shortlist-6.md` (kill criteria), `research/evidence-ledger.md` (evidence ids by theme: E-C Claude, E-X Codex, E-A Antigravity, E-G Grok), `research/debate/` (the two leads' arguments), `research/antigravity/reviews/` (every review). Each section above names the files behind its claims.
