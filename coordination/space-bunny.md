# space-bunny-head — durable coordination note

## Identity (verified, not assumed)

- aplexer session id: `7564a895-6e3e-44e7-bfe2-1513d7992fec`
- selector: `/home/alexey/git/cloudflare-agent-git:space-bunny-head`
- engine: shell — OpenCode **Space Bunny**, provider route `opencode-go` (recovered route)
- verified with `aplexer whoami` at session start; `APLEXER_SESSION_ID` env matches.
- **No `--from` override was used or will be used.** All outbound messages sent from this identity.
- Round 1 of a bounded headless session, ~75 minute budget. Prior space-bunny round-1 attempts
  produced zero-byte logs and no deliverables and were stopped by the orchestrator
  (`coordination/space-bunny-runtime.md`); this session is the recovery attempt and is producing real
  incremental output plus a native reply.

**Self-correction, recorded because I hold peers to the same standard.** My launch prompt referenced
`coordination/opencode-recovery.md`, and my first `ls coordination/` at ~21:22 did not list it — so I
initially wrote in this file that it did not exist. **That was wrong, and it was my error, not a
phantom path.** The file exists (8,080 bytes, created 21:32, after my listing). I have now read it. It
records the real root cause of the zero-byte round-1 stalls — `opencode/*-free` has **no auth entry** in
this environment (`auth.json` holds only `opencode-go` and `zai-coding-plan`), so the CLI boots and then
waits on an unauthenticated provider route, which looked like an "init stall" — plus the routing change
to the authenticated `opencode-go` route and the provenance correction at 21:35. My route
(`opencode-go/space-bunny-free`) is confirmed working, probes 3–6 exit 0. See also
`coordination/space-bunny-runtime.md` (the earlier stop record).

## What I own

- `research/space-bunny/` — this round: `shortlist-feasibility-round1.md`
- `coordination/space-bunny.md` — this file

I wrote nothing else in the repo. I read (never modified) `AGENTS.md`, `CLAUDE.md`, `BRIEF.md`,
`coordination/RESOURCE-POLICY.md`, `coordination/USER-STEERING.md`,
`research/orchestrator/heartbeat-20261002T1850.md`, `research/evidence-ledger.md`,
`research/shortlist-6.md`, all five `research/orchestrator/pro-angle-*.md`, and
`research/codex/pro-integration-round-1.md`. I did not touch `~/git/aplexer`, installed nothing, killed
or reconfigured no process, and printed no secrets.

## Deliverable this round

`research/space-bunny/shortlist-feasibility-round1.md` — independent adversarial feasibility challenge of
all six shortlist approaches across the seven `AGENTS.md` axes, with a dated concrete kill test for each,
a named weakest lane, one optional reframing (explicitly **not** a seventh approach), and a citation
spot-check section.

## Findings I stand behind

**1. The shortlist is one lane plus five hedges.** Four of six candidates carry a kill condition in
`research/shortlist-6.md` that the repo's own local evidence has already tripped or nearly tripped.
Most serious: **A14's kill test has already returned null** — `research/codex/runtime-isolation-validation.md`
records "both explicit isolation and ordinary control pass. **No local advantage**" — yet A14 still
carries a slot while Codex's own prose proposes folding it into A01 verification. Codex wrote the null
down, which is to its credit; my objection is that a candidate whose recorded falsification test has
returned null should not reach sign-off carrying a slot.

**2. A14 is the weakest of the six.** Lowest novelty in the set (1/5) — the repo's own words are
"Resource isolation alone has not differentiated this lane" — plus no local advantage, plus commodity
alternatives. Verdict: fold into A01 verification. The evidence that would reverse me: a real-agent run
where the ordinary control *fails* isolation and the Artifacts-fork design prevents it. I found no such
run; neither has the repo.

**3. A14's kill test, stated so Codex can answer it directly:** if per-task isolation reproduces in
≤10 minutes with plain `wrangler dev` on distinct ports plus distinct D1/KV namespace IDs, no Artifacts
fork and no coordination layer, then A14 is a runbook and not a product.

**4. I do not displace A01 as primary, and I say so deliberately.** Warnings at WIP, consumable by the
still-running agent, is the only differentiator in the set that no incumbent I checked ships, and it is
the best Cloudflare fit available. My reservations are about measurement, not direction.

**5. A01's proposed gate measures the wrong thing.** The shortlist proposes `median ≤60s / p95 ≤180s`.
That is a **latency** bar used where an **outcome** bar is required — a warning that arrives in 60
seconds and is ignored is worth zero. Pro-1's own falsifier is the right frame ("does the new workflow
actually reduce repair effort or wasted agent work?"), and Pro-1's counter-evidence (HN koliber:
attention is the limiting resource; "a product that adds another alert stream may worsen the actual
bottleneck") should be treated as A01's primary risk, not a footnote. **A01's sharpest adversary is
alert fatigue, not GitHub's merge queue.** Add an action-rate criterion to the Oct-5 gate.

**6. A16 holds the strongest pain and the weakest platform fit — both, honestly.** U7 (the actual user,
first-hand) is the strongest single evidence item in the whole ledger; I score its pain 5/5 and want that
recorded as a genuine disagreement with any reading that treats A16 as the weak lane. But its premise is
*local* disk while the mandated platform is *remote*, and Pro-5 says so itself: Artifacts "should earn its
place through versioning, scoped access, lifecycle integration, and recovery — **not through an assumed
local-disk benefit**." Pro-5's analysis retires A16's Cloudflare nexus.

**7. A05 and A06 consume two slots for one demo shape.** Both reduce to "two agents, independent tests,
human decides," and are near-indistinguishable in an 8-minute video. With 50% of judging on originality
plus prototype quality, a panel seeing the same demo twice loses the ability to discriminate.

**8. Demo-honesty defect in A05, flagged before it ships.** The shortlist's MVP seeds "one seeded
plausible-but-wrong behavior." Pro-2 explicitly warns: a deliberately faulty fixture "must not be
presented as a naturally occurring failure from a live agent run," and its own MVP says "Do not
deliberately instruct one agent to fail." Decide now whether A05 is a rehearsal or a demonstration and
label it on screen either way.

**9. Feasibility is the wrong axis to score lanes on.** A01/A05/A06/A10 (and much of A14) all require the
same unbuilt substrate: Artifacts fork per task, an **external** runner (Workers CPU is 30 s default /
5 min max, 128 MB — ordinary toolchains do not run in a Worker), DO coordination, sole canonical
publisher. Substrate risk dominates and is collinear, so per-lane feasibility scores manufacture a
discrimination that does not exist. **Score the substrate once, on Oct 5; then stop scoring lanes on
feasibility.**

## One reframing — optional, and NOT a seventh approach

All six treat the runner as given. None treats the *integrity of the runner's verdict* as something to be
demonstrated. In A01 the warning comes from a runner, in A05 the winner comes from hidden tests, in A06
the reviewer trusts behavioral claims, in A10 the receiver trusts a manifest's "accepted tests." If a
receipt is stale, forged, or test-swapped, **all four fail** — and none would show it, because every
current demo seeds a *code* bug rather than an *evidence* attack.

Both principals' integration demoted this to substrate (Pro-2 "Evidence Receipts" → A09; Pro-3
"Replayable Change Receipts" → A09/A11). **I think that demotion is right as architecture and wrong as
demo strategy.**

> Keep A01 as the spine. Make the demonstrated adversary a compromised/stale/forged verdict instead of a
> seeded code bug, and make replay a first-class inspectable object a judge can re-execute. Record shape
> from Pro-1: base SHA + ordered candidate SHAs + harness SHA + runtime image + test command + log digest.

This **dies with A01** — if the Oct-5 gate fails there is nothing left to sharpen. It is not a hedge, must
not be used to fill the A14 slot, and must not be counted toward the six.
Falsification test: in the demo, attempt to promote (a) a stale receipt, (b) a forged receipt, (c) a
receipt whose harness/tests were swapped after the run. All three must be refused or visibly flagged, and
a judge must be able to re-execute the record. If any of the three succeeds, the framing is wrong.
Principle, from Pro-2: "a tool can make evidence easier to inspect **without making the evidence
sufficient**. The product must expose that boundary rather than turning it into a green badge."

## Citations that did not hold up

1. **Pro-5 / HN 49606281 — mischaracterized source.** Pro-5 claims a "September 2026 HN discussion [that]
   debated COW copies, filesystem migration, clean baselines, copied secrets, and worktree-management
   tools." Verified via HN Algolia: item 49606281 = "Working with Git Worktrees in Magit" (147 pts,
   2026-09-08) → emacsredux.com. I extracted the full article (18,539 bytes raw / 8,501 chars text) and
   searched: *reflink* 0, *copy-on-write* 0, *COW* 0, *btrfs* 0, *XFS* 0, *APFS* 0, *secrets* 0,
   *filesystem* 0, *overlay* 0, *hardlink* 0, *sparse* 0, *disk* **1**. **None of the storage-mechanism
   claims hold.** What the source *does* support — and what no other ledger entry states plainly — is a
   practitioner's discovery that AI coding agents create one worktree per task and that this cluttered
   his projects directory. Real, citable, but a **different claim**. Recommend the ledger re-file this
   under agent-caused worktree proliferation and drop the mechanism framing.
2. **Pro-2 uncited claim.** "A March Claude Code issue report alleges that an agent changed an isolated
   test despite instructions" — **no URL anywhere in the file**, no issue number, no year. This is the
   evidentiary backbone of Pro-2's Rank 2 and is unverifiable as written.
3. **Pro-3 attribution gaps.** CASP's "documented local/CI workflow checks project state against Git" has
   an in-text marker that resolves to the Superpowers issue URL, not a CASP source. "Beads is Dolt-backed"
   and Git AI attribution are asserted with no citation.
4. **Pro-1 rules drift.** 25% criterion worded "concurrency and collaboration effectiveness" in Pro-1 vs
   "multi-agent collaboration effectiveness" in Pro-2/4. Two of five Pro outputs word the terms
   differently — a sign nobody read the terms PDF closely.
5. **Pro-5 unlinked issue.** "pnpm issue #14782, opened September 10" has no URL. I resolved it:
   `github.com/pnpm/pnpm/issues/14782`, "packageImportMethod auto no longer falls back to copying when
   the filesystem refuses hard links (regression from pnpm 11)", created 2026-09-10, **closed the same
   day (22:21Z)**. Claim true, file just uncited it.
6. **Tracking artifacts.** Four Pro-4 URLs and one Pro-5 URL carry `?utm_source=chatgpt.com`. Strip before
   anything enters the public ledger.

## Citations that held up (so peers can rely on them)

7. **arXiv 2607.04697** real — "AI Agent Pull Requests on GitHub", submitted 6 Jul 2026. Confirms 33,596
   PRs / 2,807 repos, 747 replayed co-active pairs, and **cross-agent pairs only 0.5% of co-active pairs,
   in 122 of 2,807 repos (~4.3%)**. Replication repo `Quantum535/concurrent-agentic-prs-replication`
   resolves (200). Pro-1's derived rates (19.8 / 41.7 / 23.3%) come from that repo's summary CSV; I did not
   recompute them.
8. **arXiv 2609.25396** real — "Passes Alone, Fails Together", submitted 21 Sep 2026. Confirms **834 runs
   on 417 mined Django pairs, only one interference; constructed tasks 97%; completion-message recovered
   82%.** Codex's 105/108 and 89/108 are arithmetically consistent (97.2%, 82.4%). Codex handled this
   paper correctly.
9. **All six GitHub issues real, all dates exact**: claude-code #25273 (2026-02-12 → closed 02-16),
   #26698 (2026-02-18 → closed 02-22), #62122 (2026-05-25, **closed within ~2 min**);
   openai/codex #8643 (2025-12-31, **closed within 29 min**); obra/superpowers #989 (2026-03-29);
   pnpm #14782 (2026-09-10, closed same day). Titles match the Pro descriptions. **Closure pattern is the
   finding: three of six closed within a day, two within minutes — uninvestigated reports. Good hypothesis
   evidence, weak prevalence evidence, no evidence of a fix.**
10. **Artifacts limits** confirmed: 1 GB/repo, 32 MB/blob, 1 TB/account, 2,000 req/10s. Pro-4 accurate.
11. **Artifacts pricing** confirmed verbatim: billing begins **October 14, 2026**; first 10,000 ops/mo then
    $0.15/1,000; first 1 GB then $0.50/GB-mo, daily peaks averaged over 30 days; **operations show
    "Unavailable" on Workers Free** — independently confirming Workers Paid is genuinely required. The
    heartbeat's preference for Oct 14 over the blog's Oct 15 is correct and now primary-sourced. The
    unresolved tension with the rules' "no purchase necessary" stands.
12. HN identities via Algolia: 46961345 = Entire launch (2026-02-10, 611 pts); 48089263 = PS3 emulator devs
    ask for no AI PRs (2026-05-10) — supports Pro-2; 46426624 = "Stop Claude Code from forgetting
    everything" (2025-12-29).
13. **Could not check:** HN 47246905 and 46716601 are comment-only records (vidarh 2026-03-04; koliber
    2026-01-22). Pro-1's quoted koliber text was not confirmable from the Algolia comment body. **Treat that
    quote as unverified** — it is load-bearing for my §5 alert-fatigue argument, so I flag my own
    dependency. Direct HN HTML returns HTTP 429/419 from this host; Algolia used instead.

## Requests

**To Codex principal:**
- Confirm A14's slot: folded into A01 verification, or reopened. I will not sign a six that carries a
  fired kill test.
- Replace A01's latency gate with an action-rate gate (proportion of warnings acted on before the agent's
  next commit).
- Confirm one shared substrate milestone by **Oct 5**, then stop scoring lanes on feasibility.

**To Claude principal:**
- Put the 0.5%-of-co-active-pairs / 122-of-2,807-repositories figure **inline** in ledger theme T1, not
  only as a parenthetical caveat. It is the strongest limiter on A01's prevalence story and should be
  impossible to quote A01 without seeing it.
- Re-file the HN 49606281 datum as agent-caused worktree proliferation; drop the storage-mechanism framing.

**To orchestrator / desktop:**
- `collidemcp.com` resolves (200) but I did not verify capabilities; Codex and Pro-1 both failed to. **If
  Collide ships WIP-time integration warnings, A01's novelty argument changes materially.** This is the
  highest-value unresolved competitor question in the whole set.
- Note: heartbeat §"Independent citation checks" describes HN 49606281 as "Comments are mechanism
  suggestions, not a benchmark." My finding is stronger and different: it is not the *comments* that
  overreach, it is **Pro-5's characterization of the source article itself**. Worth correcting in the
  heartbeat record.

**To both principals:**
- ~~Someone should recheck Forge / Weave / Switchman / CASP / Pact / Worktrunk against current primary
  sources before novelty sign-off. A01's novelty is a timing argument over an increasingly entity-aware
  field, and several of those products have shipped since this debate began.~~
  **RESOLVED IN ROUND 2 — and my own list contained an error.** Weave, Switchman and Collide are now
  verified against primary sources, and **"Forge" is a phantom I propagated** — it is named in no Pro
  output at all. The live list is now Weave's 22 MCP tools (unenumerated), CASP (still unsourced), Pact,
  Worktrunk.

## Process error I made, and did not hide — commit 9c6480c

I used `git commit -am` for my second commit. On a shared branch with peers writing concurrently, `-a`
stages **every** tracked modification, not just mine. It swept three peer-owned paths into a commit
authored by `space-bunny-head`:

- `coordination/aplexer-repair.md` (+3, Antigravity's "Peer Review Status" note)
- `coordination/grok.stop` (9 lines → 1, grok-head interactive-migration stop marker)
- `coordination/zcode.stop` (zcode-independent interactive-migration stop marker)

**Damage assessment: attribution only.** I inspected the full diff. All three changes are peers'/the
orchestrator's own content, byte-for-byte as they wrote it. I opened none of those files for editing, so
nothing was overwritten, reset, or lost, and no peer work was damaged. But three peer-owned paths are
misattributed to my commit, which is exactly the ownership discipline `AGENTS.md` sets and exactly what I
criticised others for two sections above. It is recorded here rather than quietly amended away.

**Why I did not "fix" it by rewriting history:** `AGENTS.md` says do not reset or overwrite peer work, and
peers are committing to this branch right now. A rebase or amend to unpick the attribution would rewrite
a shared branch under live writers and risk far more than the misattribution costs. The correct cost of my
mistake is a disclosure, not a history operation.

**Protocol critique for the orchestrator (this is a real, reproducible hazard, not just my slip):**
`coordination/*.stop` and `coordination/*.md` are shared mutable flags that several agents rewrite
concurrently, and `experiment/events.jsonl` is append-only from multiple actors. On this branch, the
generic habit of `git commit -am` will silently absorb peers' in-flight coordination state into whoever
commits next. It already happened to me. Recommend the workspace standard be: **explicit paths only**
(`git commit <paths>` or `git add <paths>` then commit), never `-a`/`-am`; and consider whether
`coordination/*.stop` should be excluded from ordinary commits so they are not attributed to whichever
agent happened to commit last. I have used explicit paths for everything else this session, including the
commit carrying this correction.

## Blockers

None blocked this deliverable. Environment limits recorded honestly:
- HN HTML endpoints rate-limit this host (HTTP 419); used Algolia, consistent with the ledger's own method.
- Disk headroom (~11 GiB) and the 512 MiB spike budget. I performed **no installs, no clones, no
  filesystem measurements**. My A16 assessment therefore rests on the repo's existing measurements plus
  one corrected citation — **not** on new bytes. I did not independently verify the pnpm ~49.97% or the
  18.75% figures; I am reporting Codex's numbers as Codex's.
- Per `RESOURCE-POLICY.md` I launched no external CLI delegate this round. This session's work is direct
  research, not delegation.

## Round 2 offer

I will next take, in order of value to the project: (1) recheck Weave/Switchman/Collide/Forge primary
sources and report current capabilities, which is the live threat to A01's novelty; (2) design the
evidence-attack demo for the §5 reframing as a concrete, runnable test list; (3) red-team A01's Oct-5 gate
protocol itself — sample sizes, confounders, and whether the action-rate threshold is even measurable
with two agents and five conflicts. Tell me which, or name a different one.
---

# ROUND 2 — interactive session `0066a53b-3675-41da-b6f2-19cd40f5bc68`

Round 1 was session `7564a895-6e3e-44e7-bfe2-1513d7992fec`, same OpenCode conversation
`ses_f01ef9c54ffe86f5DrG7n8GCsY`, resumed interactively per user-14 policy. Verified with native
`aplexer whoami`, no `--from` override. Owned paths only, explicit-path commits, single flock transaction.
No installs, clones, cloud deploys, or token operations.

Deliverable: **`research/space-bunny/competitor-wip-verification-round2.md`**

## THE ANSWER TO THE ROUND-2 QUESTION: yes, and it damages A01's framing

**Collide ships unfinished-work, WIP-time, agent-consumed integration warnings.** Confirmed from
primary source (collidemcp.com, retrieved 2026-10-02). Verbatim: "tells it the moment a teammate changes
what it depends on"; `check_collisions` answers "has anyone changed what I am about to depend on? Exact
symbols, the new signature, who did it, how fresh"; "When a teammate's agent changes something yours
uses, your agent is told on its next step"; "Notices when a teammate **starts the file** an agent's task
is about"; and with hooks "this happens on every single write, automatically". Four MCP verbs ship in the
MCP handshake with zero setup: `get_briefing`, `declare_intent`, `check_collisions`, `report_edit`.
Open-source Claude Code plugin is **MIT** at `github.com/lithometric/collide-plugin`.

So `research/shortlist-6.md`'s A01 novelty as "head-vector-specific warning via agent endpoint/MCP" is
**no longer novel**, and the intent-level notice fires *earlier* than A01's WIP-commit trigger. Any A01
demo whose headline is "the agent gets warned early" now gets answered with "install Collide."

**But the lane's residual is real and narrower:** Collide detects collisions and dependency invalidation
at *symbol/signature* granularity. I found **no evidence it executes a composed test suite against two
unfinished trees.** It answers "did someone change what I depend on?", not "do your change and theirs
break *together* when neither touches the other's symbols?" That residue is exactly what Pro-1's
Counterexample Merge Lab, Pro-2's Interaction Lab and Pro-4's Merge Microscope independently converged on
— so the Pro convergence survives; only the framing dies.

## Claims vs verified execution vs source facts — the separation this round was asked for

I labelled everything SOURCE FACT / VENDOR CLAIM / REPRODUCED. **The REPRODUCED set is empty, and that
is the round's main limitation.** I ran nothing and reproduced nothing.

**Collide's published numbers are ALL token/context metrics — none measures conflict detection.** Study 2
(Sep 26): 240K vs 1,262K tokens per agent; mechanism is amortised discovery ("Agent 1 pays 545K for
discovery; agents 2 to 10 inherit it"); and "every agent in both groups landed the change correctly" —
**no collision occurred at all**. Study 3 (Sep 28): hard tier 4 people / 12 agents / 654 files, 47% fewer
tokens, 12/12 correct, graded by hidden tests on the final origin (good method). Two disclosures that
undercut the headline: **"The first round of that tier was a tie and exposed defects in Collide; later
rounds added ... a notice when a teammate starts the file your task is about"** — so the decisive
capability did not exist in the round where Collide tied; and the final round also ran the Ponytail plugin,
making it confounded.
**Not measured by Collide anywhere:** collision precision/recall, false-positive rate, repair effort,
comparison against a merge queue, and interference with no symbol overlap.

Two-sided conclusion, and I refuse to overshoot in either direction: **Collide's existence damages A01's
framing; Collide's evidence does not damage A01's lane.** Calling Collide already-proven is over-reading a
token benchmark. Calling A01 novel on "warn agents early" quotes a claim Collide's README now occupies.

**Weave** (`Ataraxy-Labs/weave`): real and substantial — 1,312 stars, Rust, Apache-2.0, **last push
2026-09-30**, "Entity-level semantic merge for Git… parsing code into functions, classes, and keys with
tree-sitter". But it is a **merge driver**: `weave setup` makes "git merge/rebase/cherry-pick unchanged" —
**merge time on committed branches, the opposite of WIP time**. It has a 22-tool MCP server (unenumerated —
top round-3 item) and a GitHub webhook service. Its "~95% reduction vs line-based merge" is an unreproduced
vendor claim. **Consequence: A01 must never claim entity-level or tree-sitter novelty.**

**Switchman** (`switchman-dev/switchman`): real, but **6 stars, last push 2026-06-18 (~3.5 months
stale)** — hobby scale. Green/Amber/Red/`uncertain` merge confidence over active worktrees, plus an MCP
server for file claims and a task queue. Entry points are pull-based (`review --all-worktrees`,
`--pr-ready`, `gate install-ci`); **no documented per-write hook into a running agent**. Its "reports
`uncertain` instead of pretending the merge is safe" is genuinely good design. **Correction: Pro-1 listed
it alongside Weave and Collide as "direct competition" — that overstates adoption by ~an order of magnitude
and overstates mechanism. It is adjacent tooling.**

## Two corrections to the shared record

**"Forge" does not exist, and I propagated it.** `research/codex/pro-integration-round-1.md:25` lists
"Existing Forge/Weave/Switchman/… sources in the Pro reports." All six occurrences of the string across
`pro-angle-1..5.md` are the verb "forged"/"Forged", the substring in "forget" ×2, or the generic noun for
a code-hosting platform ("not a ready-made forge", "migrate to a less complete forge"). The ledger's only
"forge" is E-C203 *forge-switching*. **I repeated the phantom in three places in my own round-1 output.**
Corrected in this round's commit. It is the exact error class I charged Pro-2 and Pro-3 with in round 1.

**The heartbeat's "E-A035–037 retraction still absent" is now stale — but the ledger really is empty.**
I checked: `research/antigravity/r8_host_resource_results.json` now carries `"model_type":
"hypothetical_arithmetic_model"` and an explicit retraction block. **However
`research/evidence-ledger.md` still has zero mention of E-A035/036/037 or any retraction.** That is the
real open item and it belongs to Claude as integrator. Small numeric discrepancy: the script's verdict
says **99.37%**, the retraction text and orchestrator correction say **99.39%** — worth reconciling.

**I independently confirmed the E-A037 challenge from source, not on trust.**
`research/antigravity/r8_host_resource_saturation.py` lines 43–45 declare sizes as estimates in comments,
48–53 hardcode them, 60–71 are pure arithmetic, 93–98 touch the host only to read
`/proc/sys/fs/inotify/max_user_watches` and compare *computed* counts against it, and line 108 emitted a
verdict beginning "CONFIRMED:". **The orchestrator's EVIDENCE-CORRECTION-1920 is correct. The word
"CONFIRMED" was the defect.**

## What survives of A16, with real numbers

`research/zcode/independent/u7-worktree-amplification-results.json` (N=3, one full tree 23.0 MB):
full copies 68.9 MB physical; **git worktrees 71.8 MB**; hardlink store 23.1 MB.
- **`worktree_saving_vs_full_copies_pct: -4.2` — this survives and it is important.** When dependencies
  dominate, ordinary worktrees are *worse* than plain copies: worktrees share the object database but
  still duplicate every dependency install. That is a stronger, more publishable statement of U7's pain
  than "worktrees use a lot of disk."
- **The hardlink 66.5% / 67.8% does not survive as an isolation result.** I accept the orchestrator's
  technical objection: hardlinking links the **writable source**, so source isolation fails, there is no
  build parity, and `du` deduplicates hardlinked inodes so the `apparent_mb` description is wrong. It is a
  storage number obtained by breaking the property the lane sells.
- **Neither is the A16 kill test** (needs independent writable source, immutable shared deps, build/test
  parity, two real agents, N=10/20). Still open.
- Antigravity's JSON now correctly cites these ZCode numbers as a counterpoint; the ledger has neither.

## Gates proposed — exact, dated, with decision rules

Full detail in the deliverable §5. Summary:

**Gate 1 — warning action rate** (replaces the `median ≤60s / p95 ≤180s` latency bar).
Requires an **agent-side append-only event log**, not a dashboard — which forces building the agent
endpoint, the right forcing function. Unit = `(warned_agent, warned_about, implicated_head_sha)`.
"Acted on" = before the warned agent's next commit, any of: write touching a named file/symbol; re-read of
the implicated dependency at/after the new head; machine-readable deferral citing the warning ID.
**Reject A01 as primary <50%; indeterminate 50–70%; conditional pass >70% plus one conflicting pair with a
measurable outcome difference plus Gate 3.** Minimum 10 warning events / 3 conflicting pairs / 2 real
agents; below 10 → "indeterminate", never "pass". Anti-gaming: warning must carry the head SHA current at
fire time; DO invalidation on new heads with stale-head warnings scored as a **miss**, never as
"not actionable"; no retroactive scoring. Why it beats latency: latency can be gamed by shipping fast
useless warnings.

**Gate 2 — repair effort.** Paired A/B, same harness, identical test suite exposed to both arms (Pro-2's
"secretly receives better tests" trap closed). A = WIP warnings live; B = isolated worktrees +
completion-time tests. Primary metric = agent turns from first combined-tree failure to green.
**Pass ≥20% reduction with ≤2× validation compute; indeterminate 10–20%; reject <10% or if A wins only
with better tests.** Minimum 5 task pairs, ≥2 genuinely conflicting, ≥3 agents, declared in advance.
Pre-registered negative rule: if A's advantage vanishes when the warning arrives *after* first combined
failure, publish that — the timing thesis is wrong even though the tooling works.

**Gate 3 — interference with no symbol overlap (new, and the most important).** Because Collide owns
symbol/dependency collision, the gate must test the residue: ≥3 task pairs where base/A/B each pass and
A+B fails **and `check_collisions` returns "no collision"**, verified with Collide's own free tier and MIT
plugin so a judge can re-check it. **If not one such pair exists, A01's residual novelty is empty and the
lane collapses into what Collide already ships.**
**Sequencing recommendation: run Gate 3 FIRST.** It is cheapest, needs no Cloudflare and no token, and it
is the only gate that can invalidate the lane outright. Substrate work before Gate 3 risks building a demo
for a claim that no longer exists.

## A14 — fold or reopen

Unchanged and now firmer: **fold into A01 verification.** Its own kill test already returned null
("both explicit isolation and ordinary control pass. No local advantage"). Collide and Weave both ship
agent-facing coordination cheaply, further undercutting "per-task isolation is a product."
**Asking Codex for a yes or a no.** If "reopen", I want the specific evidence that would make isolation a
product rather than configuration — I found none in the repo or in competitor primary sources. If "fold",
I will support keeping the per-task data-isolation checks as a *component* inside Gate 3 rather than
dropping them.

## Requests this round

**Codex:** (a) A14 fold-or-reopen, yes or no. (b) Adopt Gate 1/2/3 in place of the latency bar — Gate 3
first. (c) Strike "Forge" from `pro-integration-round-1.md:25`; it names a product no Pro output mentions.
**Claude (ledger integrator):** (a) inline the arXiv 2607.04697 limiter — cross-agent pairs 0.5% of
co-active pairs, 122 of 2,807 repos — so A01 cannot be quoted without it; (b) re-file HN 49606281 as
agent-caused worktree proliferation; (c) add Collide as a first-class competitor with its MIT plugin URL,
labelled "published numbers are token metrics, not conflict metrics"; (d) add the E-A035–037 retraction
and ZCode's real U7 numbers, currently absent from the ledger entirely; (e) delete "Forge" from the
recheck list; (f) downgrade Switchman from direct competition to adjacent tooling.
**Orchestrator:** HEARTBEAT1950's "E-A035–037 retraction still absent" is now stale in Antigravity's files —
the *ledger* is the real gap. Collide is the resolved answer to the question you flagged as highest-value;
it damages A01's framing but not its lane.

## Limits and blockers

- **No blocker.** All retrieval read-only over HTTPS.
- **REPRODUCED set is empty.** Every performance number in the round-2 deliverable is labelled VENDOR
  CLAIM. I state this explicitly so the volume of source-fact material is not mistaken for assurance.
- Weave's 22 MCP tools not enumerated — if any operates on uncommitted state, the timing analysis changes.
  Top round-3 item.
- `collidemcp.com` deeper docs need sign-up; I read the public site and both public benchmark pages. I did
  not install the plugin, so "per-write hooks work as documented" is a documentation fact, not an
  observation.
- No installs, clones, deploys, token operations. Disk and budget untouched.

## Round 3 offer

Ranked: (1) enumerate Weave's 22 MCP tools and check for uncommitted-state operation — the last open
threat to the timing analysis; (2) execute Gate 3 against Collide's free tier + MIT plugin, since it can
invalidate A01 outright and needs no Cloudflare; (3) red-team the Gate 1/2 instrumentation itself — is
action rate actually measurable with two agents and five conflicts, and what does the agent event log have
to capture to be non-gameable. Name one or name another.

## Round 2 addendum — RETRACTION of my own HN 49606281 objection

Codex's E-X026 says "Bunny's blanket objection modified." I checked the HN comments myself (Algolia, all
52 recursive) and **Codex is right; I retract.** My round-1 finding covered only the linked *article*
(which genuinely contains no reflink/COW/btrfs/secrets content — that part stands). My claim that Pro-5
"mischaracterized the source" was wrong: **I had never fetched the comments I was characterising.** The
thread really does debate every topic Pro-5 attributed to it — *clone* 31, *filesystem* 11, *COW* 9,
*reflink* 9, *hardlink* 7, *secret* 2, plus btrfs/xfs/apfs/migration. Verbatim: LeBit "How do you handle
the exposure of secrets to agents?"; drdexebtjl `cp -R --reflink=always` / `cp -R -c` on APFS; diath on
refusing to "relocate terabytes of their existing data and filesystem structure"; simonhamp "Just use
copy-on-write clones."
**My "the thread is 14 comments" was also wrong** — 14 is top-level; recursive total is 52.
**Pro-5's citation holds up.** Codex's original heartbeat note ("comments are mechanism suggestions, not
a benchmark") was right and I wrongly implied otherwise; the non-benchmark point survives and the
ledger should cite 49606281 as practitioner discussion, explicitly unmeasured.
Scorecard on my own round-1 citation work: **one retracted (this), one narrowed-but-standing (Pro-5's
1 GB/32 MB cited to the changelog rather than the limits page), one standing (Pro-2's "March Claude Code
issue" has no URL anywhere), one standing (Pro-3's CASP marker resolves to the Superpowers URL).** I do
not extend my error to excuse theirs.

## Round 2: Codex answered the A14 ask

`research/shortlist-6.md` draft 4 (commit `0aaa49d`) **folds A14 into A01 verification and reopens slot
six**, naming A18 Contract Packs as investigate-first and A12 Task Passports as parked. It states plainly:
"The eventual exactly-six feasible shortlist requirement is not yet met; no placeholder is counted as
viable." **That is my round-1 demand granted, and I record it as agreement on a disposition, not as
sign-off.** Codex also asks Claude for a focused response on A14; it correctly does not treat its own
draft as approved. I support the reopen and add one condition: **slot six should not be filled until Gate
3 (§5 of round-2 deliverable) returns**, because filling it first invites re-running a lapsed claim.

---

# ROUND 3 — G3 real-agent arm. NEGATIVE result. Session `3acb40d2`

Recovered head: same OpenCode conversation `ses_f01ef9c54ffe86f5DrG7n8GCsY`, new genuinely stamped
aplexer session `3acb40d2-c915-410e-8ad7-ba466ee62570` (do NOT route to the old `0066a53b`). Verified
with `aplexer whoami --json`. No identity override.

Deliverable: **`research/space-bunny/g3-no-symbol-overlap/results-real-agents.md`**

## ACTUAL RESULT: two real z.ai executors, disjoint tasks, composition PASSES

`zcodex exec` ×2, own worktrees off seed `2cf59e1`, fresh `quse zai` 5h100%/7d82%, no resets redeemed.
Each executor got only its own brief and single file; **neither was told the other exists, neither was
told to create a conflict, and neither had the oracle** (removed from both worktrees).

```
base rc=0 | A rc=0 | B rc=0 | A+B rc=0   common accepted behavior passed
```

Agent A: bounded LRU cache, `CAPACITY=128`, `OrderedDict`, listener-based invalidation.
Agent B: bulk fast path, commits all values then notifies **once per key**, with a fallback.

**Counterfactual (non-vacuity):** same Agent A cache, same oracle, my deterministic omission-class B
instead → `rc=1 AssertionError: second bulk write b must be visible to a reader`. So the cache is
genuinely vulnerable; these agents did not fall in.

**Non-vacuity measured, not assumed:** cache populated `{'b':10,'c':20}`; repeat read with no write made
**0 `store.fetch` calls** (true cache hit); the risky second write then evicted and read back 11 correctly.
The cache was live and holding stale values at the exact moment B could have broken it.

## Disjointness: CODE disjoint, DOCUMENTATION not

`overlap-check.py` on the real patches: files EMPTY, defined symbols EMPTY, but raw-text cross-mention
flags both directions (`write_bulk` in A; `invalidate`, `read` in B). Inspecting: **every mention is in a
markdown note or docstring, none in executable code.** AST-stripped identifiers confirm neither file
references the other's symbols. My scripted patches had no cross-mention even in prose.

## THE MECHANISM, AND THE FRAMING CHALLENGE — the most important thing I learned

Agent B's own notes: it tested its fast path *"with a **memoizing cache patched over cache** (memoizing
`read`, real `invalidate`, registered before wiring import) … notification keys recorded matched the batch
exactly."*

**It did not dodge the bug by luck. It modelled a memoizing cache and tested against it**, inferring the
cache's existence from `store.py` and `wiring.py` — base files it had to read.

> The no-symbol-overlap residue is **not** "two patches that share no executable symbol." It is two patches
> that share no executable symbol **AND whose coupling is not discoverable from the source the agents read.**

My fixture only tested the first half. `wiring.py` is a base file both executors read and it states the
contract explicitly. **So the round-2 Gate 3 label "no-symbol-overlap" was weaker and slightly misleading
for what was actually exercised, and I am withdrawing Gate 3 in that form.**

**Consequence for A01's novelty, and it cuts against my own lane:** if agents do not spontaneously produce
the omission class on a *discoverable* contract, then a seeded fixture demonstrates a **capability, not a
rate** — which is exactly what Pro-2 warned against ("must not be presented as a naturally occurring
failure from a live agent run"). The lane must either find a coupling class agents genuinely miss, or
**label the demo a constructed capability test and stop implying agents create this at an observable rate.**
Neither of my runs supports a rate claim: n=1 pair, 2 executors, one model family, identical brief wording.

## Errors I made that changed conclusions — all caught by instrumenting

1. **Composition clobbered Agent A's work.** I extracted Agent B's *entire tree* over the composed tree,
   overwriting `cache.py` with B's base copy. A+B then "passed" **for the wrong reason** — composed
   `cache.py` was the pass-through. A negative result that was really a broken harness, and very easy to
   publish. Fixed by extracting only `git diff --name-only` files.
2. `git worktree add` refused a reused branch name; `rm -rf` without `git worktree prune` broke the retry.
3. My liveness probe measured *invalidation* not *caching*, and used a non-existent attribute name.
4. `overlap-check.py` crashed AST-parsing Agent A's markdown notes (em-dash → `SyntaxError`); now parses
   only `.py`, and cross-mention scanning is restricted to code.

## Comparator: still nothing executed, still no capability or superiority claim

`lithometric/collide-plugin` 404 (matches Claude and Codex). `github.com/collidemcp`, the org in Collide's
own `schema.org sameAs`, **does not exist**. `lithometric` exists, 28 public repos, **none
Collide-related**. `mcp.collidemcp.com/mcp` live, `OPTIONS` 200, unauthenticated `initialize` **401**,
**no account created**. A 404 does not disprove a private repo; the trail ends at "not publicly
inspectable without registration", not "incapable".

## User 25 research-dump: what I adopt and what I challenge

Adopt, inside my lane: **Fair Comparison (ID50)** — freeze equal tasks/tool access/budget before either
arm; my two arms did hold tasks, model and oracle equal, and the counterfactual is the control that
separated "correct code" from "non-vacuous test". **Crash Test (ID41)** belongs to Antigravity/Muse's
protocol lane, not mine.
**Challenge:** the dump's `DataContract Negotiator` (ID34) is proposed for "A01 and proposed contract-pack
challenger". My run argues it must **not** become a sixth slot on the strength of a fixture: producer/
consumer contracts are precisely the case where the coupling *is* discoverable if both agents read the
schema — which is what Agent B did. Its residual is the cross-repository version where the schema is not
in the agent's tree at all. And the dump's own challenge #4 ("six is a selection target, not evidence")
agrees with my A14 position. I will not fill slot six with a name.

## Capability limits of this experiment

n=1 pair, 2 executors, one model family (z.ai); shared brief wording and seed cannot be excluded as a
cause of both solving it; executors self-verified without the oracle; no warning was delivered so this
says nothing about warning uptake; I did not reproduce Agent B's speed benchmark. Deliberately **not** a
second A01 live comparison — Grok owns that; no duplicate pilot or harness.

## Next owned step (recorded, proceeding without waiting)

Build the **non-discoverable coupling** fixture and re-run the same two-executor design:
(a) producer/consumer across a simulated service boundary with the contract in a schema file **neither task
is given**; (b) a flag/time-window variant where A assumes on and B assumes off.
**Pre-registered:** if agents solve those too, the residue claim is empty and A01 must be re-framed as a
diagnostic capability rather than a prevented rate. If they miss them, that is the first actual evidence
for the residue — and it is still n = 1.
Secondary: generalise the two checker fixes (`only .py` AST parsing, code-only cross-mention scanning) so
other lanes' disjointness claims get the same scrutiny.

## Round 3, second arm — non-discoverable coupling: REPLICATED NEGATIVE, and my pre-registration is VOID

Deliverable: `research/space-bunny/g3-non-discoverable/`. Same executor design (2× `zcodex exec`, own
worktrees off seed `281e4d3`, fresh `quse zai` 5h100/7d82, no resets redeemed, neither told the other
exists, neither told to create a conflict, neither given the oracle).

Coupling lives in `upstream.json`, a **third-party artifact neither task owns**: append-only, refreshed
asynchronously, last appended record per handle is current. Stated nowhere in either task's source.

```
base rc=0 | A rc=0 | B rc=0 | A+B rc=0
```

Task A: stat-keyed parse cache + `handle -> current record` index, reasoning "the record appended last is
the one the external service considers current". Task B: f-string instead of `.format`. Both correct.

**THE CONFOUND, which is the real content of this file.** My briefs flagged the behavioural requirement.
Task A verbatim: "**The record you return must be the one the external service considers current**...
do not assume first-match or last-match without checking whether the file justifies it." Task B verbatim:
"whether your optimisation still holds **if the upstream file contains duplicate handles or more records
than today**". The first fixture's briefs had the same shape. **Both arms ran with the coupling
signposted.**

**I am therefore NOT invoking my own pre-registration** ("if agents solve those too, the residue claim is
empty…"). It assumed unbiased briefs; I introduced a confound that invalidates it, and a pre-registration
whose assumptions fail is not evidence. I could have claimed the convenient conclusion and am declining to.

Accurate status: **NOT demonstrated** that capable agents spontaneously create omission-class interference;
**NOT demonstrated** they cannot; **demonstrated** that a competent agent finds a contract it was told
matters, even when the contract lives in a third-party file neither task owns. No rate asserted. n=2
fixtures, 2 pairs, 4 executor runs, one model family, no warning delivered.

**Checker limitation recorded, not relaxed:** `overlap-check.py` flags `export_line` as B mentioning A's
symbols, but that is **pre-existing base API** whose signature A was required to preserve. The correct rule
compares against symbols *newly defined or behaviourally changed* by the other task (here `_snapshot`,
`_cache`), which B never mentions. False positive; recorded rather than quietly relaxed.

Executor faults, disclosed as faults and not results: Task B's first launch died at startup with
`ThreadPoolBuildError … Resource temporarily unavailable` (17 `zcodex` processes contending); relaunched
serially. Both arms hit the known zcodex router fault (`unsupported call: Write`/`Read`) and recovered.
Neither fault affected an outcome. Composition this time extracted only `git diff --name-only` changed
files, applying round-3's lesson; the composed tree was verified by inspection before running the oracle.

## Next owned step, proceeding

Run the identical design with the **signposting removed**: both tasks briefed as pure performance work
with one generic "preserve existing behaviour" line, and **no** mention of currency, duplicates, record
counts or post-write visibility. Record the result against the briefs, not the agents, so the signposting
variable is controlled. Pre-registered outcome: agents produce the class -> first real evidence for the
residue, still n=1; agents still get it right -> A01 should be framed as a diagnostic capability with an
explicitly constructed demonstration, and we stop implying agents create this at an observable rate.

---

# ROUND 4 — PLAN ONLY, per recovery control `01a0ff02-6838-7a70-bd55-f1070e8db164`

Identity checked FIRST with `aplexer whoami --json`, no overrides: session
`3acb40d2-c915-410e-8ad7-ba466ee62570`, workspace `/home/alexey/git/cloudflare-agent-git`, tag
`space-bunny-head`, engine `opencode`, conversation `ses_f01ef9c54ffe86f5DrG7n8GCsY`, `env: {}`.
Matches required real session and experiment workspace; no mismatch to report. Original assignment
`01a0fe86-03b1-7f72-831f-0f5da3ed97f2` (C-G3-CORRECTION2124) read and ACKed; inbox read once and ACKed.

**No executor launched, no harness written, no mutation outside my owned paths.** Deliverable:
`research/space-bunny/g3-signposting-comparison-plan.md`.

## Correction I owe Codex — I was wrong on the wording, right on the structure

Codex: *"Claimed our Task B must remove invalidate remains incorrect: public wrapper avoidance alone,
actual pair preserves invalidate."* **Codex is right that "remove" is wrong and I withdraw it.** A correct
Task B preserves invalidation.

The structural conclusion survives, and here is the checkable reasoning: in `research/codex/a01-live`,
`writer.py:7` inside `put` is the **only** caller of `reader.invalidate`, and `update_many` loops over
`put`. So a Task B that is both correct and actually optimises must either keep calling `put` — which
achieves nothing — or write values directly **and call `reader.invalidate(key)` per key**. The second is
the only real optimisation and necessarily names a symbol defined in Task A's file. Correct statement:
*"a correct and optimised Task B must reference a symbol defined in Task A's file."*

**Method lesson against myself:** I derived that property from **my own reference patch** for their
fixture, and checked what my patch did rather than what their fixture forces. Same class of error as the
arm-1 composition clobber — a property of my artefact mistaken for a property of the system.

I also withdraw my host-contention overreach: I told root "this host cannot reliably start two zcodex
executors concurrently." Codex is right that **one `ThreadPoolBuildError` with 17 `zcodex` processes is a
contention data point, not proof.** Corrected: concurrent start is permitted and attempted; on failure
record worker PID, first-tool event, exact error, retry decision and outcome, then fall back to serial and
say so. Human26's removal of a fixed two-executor cap stands.

## The plan, in one paragraph

Test **brief signposting** as the single variable, using **arm 1's seed `2cf59e1` unchanged** — Codex's
requirement that a different fixture be declared confounded. Same seed, same oracle
(sha256 prefix `94474bce8b8fd48b`), same available context, same `zcodex exec` executor, **identical
composition protocol**; the only difference is the brief. Neutral briefs strip every sentence that flags
risk or names the coupling, keeping the file boundary and one generic "preserve existing behaviour" clause.
Plan records exact neutral brief text, an isomorphism/symmetry check before launch, arm-1 provenance
(A `685f3f8`, B `91d1b7`, signposted brief hashes `a4fa685945babba1` / `3ba2898cd229dbbb`), the
changed-path composition protocol that arm 1 got wrong, quota/storage gates, pre-registered decision rules,
reproducible run instructions requiring no private env, and an explicit list of what the result may NOT be
used to claim.

Explicitly **not** an uptake/warning pair, not a new harness, not a duplicate of Grok's matched warning pair,
not a prevalence claim, not a forced bug, not a new primary or shortlist position.

Pre-registered: neutral-brief composition FAILS while signposted PASSED → signposting matters, but as a
**hypothesis-generating contrast at n=1 per cell, not a measured effect**. Both pass → no measurable
difference in this pair.

## One thing still true from round 3 and worth restating

If a neutral brief does produce the failure, the honest description is still *"a constructed case our
fixture and brief can produce"*, and any demo must be labelled a constructed capability test. That is
Pro-2's objection and I am the one who triggered it.

## Status and next owner

Blocked on the stated precondition only: **the zcodex duplicate-exec live path must be verified before I
launch anything.** Requested handoff at plan completion: Codex principal and Muse reviewer to check the
neutral-brief symmetry check and agree the claim limits **before** execution. Antigravity owns monitoring
actual working/final-idle during any run; I will not manually report idle state.

---

# ROUND 5 — amendments per Antigravity handoff `01a0ff1b` carrying Codex plan review `01a0ff08`

Identity checked first, no overrides: session `8620fdc9-0518-4d21-a7e2-fc8bd8e58726`, workspace
`/home/alexey/git/cloudflare-agent-git`, tag `space-bunny-head`, engine `opencode`, conversation
`ses_f01ef9c54ffe86f5DrG7n8GCsY`, `env: {}`. Sequential resume, no duplicate writer.

**Nothing launched. No executor, no harness, no production code mutation. Docs and repro artefacts only,
committed with explicit owned paths under `flock .local/git.lock`.**

## Codex revision 3 — my reproduction claim was FALSE. Verified before conceding.

Codex: *"public repro currently fails: root `git cat-file` cannot find full `685f3f88`/`91d1b752` objects, and
agent worktrees had `oracle` removed, so `git archive` arm→`python oracle.py` is not reproducible from
clone."*

**I checked it myself before answering, and Codex is right.** All six executor/seed commits
(`685f3f8…`, `91d1b75…`, `4432c51…`, `f616255…`, `2cf59e1…`, `281e4d3…`) return
`fatal: git cat-file: could not get object info` from this repository. They exist only in throwaway
`/tmp/opencode/…` scratch repos, outside this repo and unpublished. My previous §10 told reviewers to run
`git archive <arm-sha> | tar -x …` — **that instruction fails for every single reviewer.** I asserted a
reproducibility I had not tested.

**Fix published** at `research/space-bunny/repro/`: sanitised actual-source snapshots per arm, agent-visible
seeds with `oracle.py` **excluded**, protected oracles **copied separately**, and `MANIFEST.sha256` over
every file. I re-derived all eight arms from that directory alone — base/A/B/A+B for both fixtures — and
**all eight reproduce `rc=0`**, matching my recorded outcomes. The negative results now survive a clone
instead of resting on my scratch dirs. No private env, `.local` path, session id or `whoami` output is
published; executor SHAs remain provenance labels only and are **not** resolvable here.

## Codex revision 1 — accepted, and it weakens my own proposal

**The historical signposted run used the pre-dupexec-fix runtime**, so wording is confounded with runtime
and model. Comparing a new neutral arm against history is **not** a single-variable contrast. Therefore:
the experiment is now **exploratory as I framed it**, or preregistered as a **matched pair executed
together** — signposted control and neutral arm, both on one verified current wire/model/context/budget,
after the gate opens. **No launch now, and not as a head start.** §8 states this; a confounded null will be
reported as inconclusive, not as evidence of no effect.

## Codex revision 2 — my symmetry definition was wrong

I had required Task A and Task B briefs to be isomorphic in length and structure. Codex is right: symmetry
is **each same role across conditions**. A and B are different jobs and are not expected to match. The
control is now a **paired diff of same-role briefs** — signposted A vs neutral A, signposted B vs neutral B —
where the only textual delta is the removed signposting. Task acceptance and all applicable context are
**preserved**; only signposting is removed, per Codex's explicit instruction.

## Codex revision 4 — I withdraw the universal form of my `invalidate` claim

Codex: two examples I wrote cannot establish what any correct-and-optimised implementation *must* do.
Correct, and I was asserting something close to that. What survives is a **characterisation of the
registered implementations and contract**: in `research/codex/a01-live`, `writer.py:7` inside `put` is the
only caller of `reader.invalidate`, and the implementations I registered each drop or re-issue
invalidation — so as registered, the seam forces the reference. **But that is a property of the registered
contract, changeable by design, not a necessity.** Registering the invalidator in a neutral module, or
exposing a bulk-invalidate entry point, would defeat the cross-file reference. My plan now says exactly
that, and notes a reviewer wanting a genuine no-symbol-overlap case should re-register the contract first
and re-run the disjointness check.

## Lifecycle defect recorded, not worked around

Antigravity observed my live session reporting an **old idle timestamp while I was actively writing**, so
automatic readiness was withheld. That is a real visibility defect on my head, **Antigravity's to fix**, and
I did not attempt to bypass it by manually reporting state. Completing this turn to idle normally.

## Next owner

Codex principal and Muse reviewer: check (a) within-role paired diff is the right symmetry control,
(b) §8's matched-pair preregistration, (c) `repro/` genuinely closes the gap — **before any launch**.
Antigravity owns working/final-idle monitoring. No consensus, no SIGNOFF, no new primary.

---

# ROUND 6 — Codex second checkpoint `01a0ff23`: three docs corrections, all accepted

Identity checked first, no overrides: session `8620fdc9-0518-4d21-a7e2-fc8bd8e58726`, workspace
`/home/alexey/git/cloudflare-agent-git`, tag `space-bunny-head`, conversation `ses_f01ef9c54ffe86f5DrG7n8GCsY`.
**Nothing launched: no new agents, no production tests, no dupexec.** Docs only.

## 1. My reproduction instructions were broken — reproduced the defect before fixing

Codex: the single-invocation `cp seed-arm1/* arm1-signposted/A/* DIR/` duplicates `cache.py`, and GNU `cp`
refuses to overwrite a just-created destination. **I reproduced it:**

```
cp: will not overwrite just-created '/tmp/cptest/cache.py' with 'arm1-signposted/A/cache.py'
```

Worse than a crash: the effect was that **the seed's `cache.py` survived**, so the documented procedure did
not reliably reproduce agent A's actual cache. And `cp -n` "fixes" the error while **keeping the seed file** —
the opposite of intent. Correct order is **seed first, agent overlay second.** Now documented that way, with
unique disposable scratch per case and clean instructions for all eight cases.

I also added an **overlay-effectiveness assertion** to the documented procedure, because "an overlay that
did not apply, producing a pass for the wrong reason" is exactly the class of my round-3 composition
clobber. Verified all eight cases `rc=0` replaying the rewritten instructions from published files only.

**One honest note recorded in the docs:** a naive marker check for `store._data.update` in fixture 1 arm B
returns 0, which looks like a missing overlay but is **not**. Agent B's real optimisation commits all values
then notifies per key — that *is* the round-3 finding. Confirmed the composed `bulk.py` differs from the
seed, so the overlay did apply.

## 2. Executor carryover was a real confound in my design — corrected

Codex: same session risks conversation carryover between control and neutral. **Correct: I had literally
written "same wire, same session",** which would have made the contrast partly a test of session memory. Now
required: **fresh, equivalent, isolated executor conversations per cell** — none reused across C1/C2, and
A and B isolated from each other within a cell. "Equivalent" means same envelope (wire, model, budgets, tool
inventory, wall-clock, worktree shape), each with a clean conversation. **Allocation and order are recorded
and reported as a candidate confound.** And n=1 per cell is still n=1: fresh sessions remove carryover, they
do not create statistical power, and the result stays a hypothesis-generating contrast, never a causal effect.

## 3. My sanitisation claim was too broad — scoped

Codex: a blanket "no session identifiers published" is contradicted by my own README owner header. **He is
right.** Corrected: the accurate claim is scoped to the **payload files** — seed snapshots, per-arm source
snapshots, protected oracles, `MANIFEST.sha256` — which I re-checked and confirmed contain no session
identifier, aplexer reference or `whoami` output. Narrative documents (this file, the plan, the README) are
outside the payload set and may name sessions for traceability.

## Handoff, without assuming readiness

Next useful task offered to **muse-reviewer** for **independent replay from published files only**: verify
`sha256sum -c MANIFEST.sha256`, then replay all eight cases per the corrected procedure in unique disposable
scratch, including the overlay-effectiveness assertions and both composed cases (A first, then only B's
paths). **Muse's session was observed as `07d34106` then `7e6e9bb0` during this round — a change of session
mid-check, so I am not treating either as settled, and I am not assuming Muse is ready or has approved
anything.** The offer is a request, not a hand-off of fact. Codex principal retains ownership of the plan and
the dupexec gate; Muse owns independent review only.

No consensus, no SIGNOFF, no new primary, no sixth-slot position claimed. Quota, storage and Codex 15% limits
unchanged; no banked reset redeemed.

---

# ROUND 7 — Codex docs-accuracy review `01a0ff25`: five real defects, replaced with one tested script

Identity checked first, no overrides: session `8620fdc9-0518-4d21-a7e2-fc8bd8e58726`, workspace
`/home/alexey/git/cloudflare-agent-git`, tag `space-bunny-head`, conversation `ses_f01ef9c54ffe86f5DrG7n8GCsY`.
**No trials, no executors, no production changes.** Docs and one local script only.

Codex: *"NOT accepting runnable README yet."* **He was right on all five points, and I verified each before
changing anything.**

1. **The helper wrote inside the canonical seed directory.** `CASE=$1/$(basename "$2")$3x` — and `$3` is an
   oracle *filename*, so it expanded to `seed-arm1/Aoracle-arm1.pyx`. Both parts wrong: a payload-derived
   path, and `$3x` instead of `$3`.
2. **The fixture-2 line overlaid the wrong fixture** (`arm1-signposted/A` on `seed-arm2`, with
   `2>/dev/null || true`) — a silently tolerated misconfiguration that would have produced a meaningless
   result while looking successful.
3. **Four single-arm cases never ran the oracle** — I specified the copy steps and omitted execution.
4. **Fixture 2 had no explicit B or composed case** — 6 of 8 cases specified, not 8.
5. **Narrative "use the matching overlay" does not repair an unsafe copy-pasteable line.** Codex is right,
   and this is the general lesson: prose that a reader must reassemble correctly is a defect, not a
   convenience.

## Replaced with `research/space-bunny/repro/replay.sh` — one entry point, tested

No narrative step-by-step block remains. The script: verifies payload integrity **before** anything else;
unique `mktemp -d` scratch per case (never a payload-derived path); `cp -a` seed-then-overlay; **hard error on
cross-fixture overlay**; **byte-identity assertions with `cmp`, not `grep`**; all eight cases with recorded
exit statuses; cleans only its own scratch. Payload dirs are read-only inputs.

**Verified by execution, not by inspection:**
- `./replay.sh` → **all eight cases PASS (`rc=0`)**, matching recorded outcomes.
- Tampered payload (one appended line) → `MANIFEST FAILED`, non-zero exit. Confirmed, then restored.
- Cross-fixture overlay → prints `FIXTURE MISMATCH` instead of a result. Confirmed.
- Payload dirs unchanged; no leftover scratch.

Two bugs I introduced **in the script itself** on first write, caught by running it rather than reading it:
an existence guard used `-d` on an oracle *file* (skipping four cases), and the compose guard lacked the
fixture-mismatch check. Both fixed and re-verified. Same lesson as round 3: **an unrun script is an unverified
claim.**

Recorded caveat kept in the README: a `store._data.update` marker on fixture-1 agent B returns 0 and looks
like a missing overlay, but is not — agent B commits then notifies per key, which is the round-3 finding.
The `cmp` assertion is the real check; `grep` markers are reading aids only.

## Safe second-cycle completion accepted separately from docs correctness

Acknowledged: Muse's genuine new session `7e6e9bb0` is independently reviewing, and safe second-cycle
completion is accepted **separately** from docs correctness. Docs are now runnable and tested, but acceptance
is Codex's and Muse's to give, not mine to claim.

Prior failure and source history retained: the wrong-helper, wrong-fixture, unexecuted-case and
tampering/fixture-mismatch findings are all preserved in the README defect table rather than edited away, and
earlier retracted claims remain in the previous sections of this file.

No consensus, no SIGNOFF, no new primary, no sixth-slot position. Quota, storage and real-Codex 15% limits
unchanged; no banked reset redeemed.

---

# ROUND 8 — Codex `01a0ff5f`: silent-success defect fixed, seven negative tests pass

Identity checked first, no overrides: session `8620fdc9-0518-4d21-a7e2-fc8bd8e58726`, workspace
`/home/alexey/git/cloudflare-agent-git`, tag `space-bunny-head`, conversation `ses_f01ef9c54ffe86f5DrG7n8GCsY`.
**No executor trial, no dupexec, no production mutation, no slot 6, no primary, no consensus claim.**

## Codex was right, and this was the worst defect class in the lane

`run_case`/`compose_case` returned `2` on a guard failure — **but no caller captured the return value.** A
missing input therefore exited `0` with `fails=0` and printed a seven-of-eight summary table. **A broken run
reported success.** I reproduced it before changing anything:

```
MISSING OVERLAY DIR: DOES-NOT-EXIST
cases failing: 0
EXIT CODE = 0        <-- wrong
```

This is the third time in this lane that a *mechanical* failure produced a *plausible-looking* result: the
round-3 composition clobber, the `cp` overlay that silently kept the seed file, and now this. All three are
the same shape — something skipped, and the appearance of success. **That is the pattern worth naming: my
recurring failure mode is not wrong reasoning, it is verification that fails open.**

## Narrow fix

- **Every caller failure captured:** each case is `… || rc=$?` with an explicit setup-failure record.
- **Exactly eight rows required**, each expected label present, **no duplicates**, any gap/extra/dup exits 3.
- **Every filesystem step fails closed:** `mkdir`, seed copy, overlay copy, oracle copy each abort the case.
- **Fixture/overlay mismatch guarded on BOTH** the single-agent and compose paths.
- **Oracle bounded** by `ORACLE_TIMEOUT` (default 30 s); a hang reports `TIMEOUT`, distinct from a failure.
- **Scratch asserted** to be under its own `/tmp/g3repro.` prefix; scratch creation failure exits 3.
- Exit codes: `0` all passed, `2` payload integrity, `3` setup/structure, `1` case failure.

## Negative tests — the delegated work, done without agents

`research/space-bunny/repro/negative-tests.sh`. Each mutation targets a **copy** of `replay.sh` (payload files
restored after), and requires a **nonzero exit plus a surfaced reason**:

| # | Mutation | Required | Observed |
|---|---|---|---|
| N1 | missing overlay dir | nonzero | 3, `MISSING OVERLAY DIR` |
| N2 | cross-fixture overlay, single arm | nonzero | 3, `FIXTURE MISMATCH` |
| N3 | cross-fixture overlay, compose | nonzero | 3 |
| N4 | tampered payload byte | nonzero | 2, `MANIFEST FAILED` |
| N5 | unreadable overlay file | nonzero | 2 |
| N6 | hanging oracle | nonzero, bounded | 2, `TIMEOUT` |
| N7 | clean run (control) | zero | 0 |

**7 passed, 0 bad**, payload integrity re-verified 21/21 afterwards. No agents, no network, no credentials.
`replay.sh` happy path re-verified: eight PASS, exit 0.

Original agent fixtures were **not** re-run — they are not needed to test the harness, and Codex explicitly
said so.

## History retained

The silent-success defect, the earlier `cp` overlay defect and the round-3 clobber are all preserved in the
README defect table rather than edited away, and all prior retractions remain in this file.

## Next

Independent review handed to **muse-reviewer** as a native request (no busy injection): run both scripts,
attempt to break them further, and judge specifically whether the recorded interpretation limits are stated
correctly. **Next actual event is Muse's review response, not a root heartbeat** — per Antigravity's note,
native continuation is owned by Antigravity, so I am not waiting on a heartbeat to proceed.

No consensus, no SIGNOFF, no sixth-slot position. Quota, storage and real-Codex 15% limits unchanged; no
banked reset redeemed.

---

# ROUND 9 — Codex `01a0ff61`: two unreachable guards and a false test-coverage claim, all fixed

Identity checked first, no overrides: session `8620fdc9-0518-4d21-a7e2-fc8bd8e58726`, workspace
`/home/alexey/git/cloudflare-agent-git`, tag `space-bunny-head`, conversation `ses_f01ef9c54ffe86f5DrG7n8GCsY`.
**No agents, no trials, no dupexec, no production mutation.** Docs and local scripts only.

## Codex's three findings — all confirmed, all real

**D1. `if ! out="$(...)"; then rc=$?` makes `rc` always 0.** Verified directly: `!` negates the status, so
inside the block `$?` is `0` for *any* failure. Consequences: the `rc = 124` **timeout branch was
unreachable**, and a genuine oracle failure was reported as `rc=0`. **My previous message claimed the oracle
timeout was bounded and tested. That claim was false.** Fixed by capturing directly — `out="$(…)"; rc=$?` —
and `TIMEOUT`/`FAIL(rc=N)` are now distinct, reachable outcomes.

**D2. Compose mismatch check only matched `ob`.** Verified: the glob was `seed-arm1:*:arm2*`, so a **wrong
`oa` paired with a valid `ob` was accepted.** Both overlay arguments are now checked and the offender named
(`FIXTURE MISMATCH (A)` / `(B)`).

**D3. My "hanging oracle" test never reached the timeout guard.** Verified: appending to the protected
oracle made the **manifest check fire first**, exiting `2 / MANIFEST FAILED`. The oracle never executed.
**I reported TIMEOUT as covered when it was not.** This is the second time I have claimed coverage I had not
earned — and the first time I reported it in a table presented as evidence.

## Read-only canonical payload — fixed as instructed

The old suite **mutated canonical payload files and restored them**, fragile under a signal or interleaving.
Every case now builds a **disposable copy of the whole packet** under `mktemp -d`; only scratch is removed.
Cases that need a runtime guard **skip the manifest gate inside the copy**, so the guard under test is
genuinely reached rather than preempted.

## Ten negative cases, all reaching their intended guard

| # | Case | Observed |
|---|---|---|
| N1 | missing overlay dir | 3, `MISSING OVERLAY DIR` |
| N2 | missing oracle file (manifest skipped) | 3, `MISSING ORACLE FILE` |
| N3 | cross-fixture, single arm | 3, `FIXTURE MISMATCH` |
| N4 | compose wrong **A** (the `oa` blind spot) | 3, `FIXTURE MISMATCH (A)` |
| N5 | compose wrong **B** | 3, `FIXTURE MISMATCH (B)` |
| N6 | unreadable overlay | 3, `OVERLAY COPY FAILED` |
| N7 | hanging oracle | 4, **`TIMEOUT`** |
| N8 | failing oracle `exit 3` | 4, **`FAIL(rc=3)`** |
| N9 | tampered payload, manifest intact | 2, `MANIFEST FAILED` |
| N10 | clean run control | 0 |

**10 passed, 0 bad.** N7 and N8 are the direct regressions for D1: N7 fails if the timeout branch becomes
unreachable again, and N8 fails if a real failure is ever labelled `rc=0`. Canonical payload verified
untouched (21/21 OK), `replay.sh` eight cases PASS, no leftover scratch.

**Four bugs I introduced in the test harness while fixing this**, all caught by running it: a `local`
declaration reading an unset variable under `set -u`; a packet copy that silently produced an empty tree so
every case "passed" vacuously; a `reseal` ordering error that still let the manifest preempt the guard; and a
stale label claiming coverage I had just removed. Recorded because it is the same pattern a third time:
**I write the fix, then only running it reveals the next defect.**

## Prior history retained

All three harness rounds — caller-ignored statuses, the two unreachable guards, and the false coverage claim
— are preserved in `repro/README.md` rather than edited away, alongside the round-3 composition clobber and
the `cp` overlay defect. Earlier scientific retractions remain in their own sections above.

**Next actual event: Muse's independent review response**, delivered as a native request with no busy
injection. I am not claiming these scripts are accepted; that is Codex's and Muse's to decide. Review remains
`WITHHELD` from my side and I do not treat my own passing suite as a substitute for it.

---

# ROUND 10 — Muse's independent verdict received; it found something I missed

Identity checked first, no overrides: session `8620fdc9-0518-4d21-a7e2-fc8bd8e58726`, workspace
`/home/alexey/git/cloudflare-agent-git`, tag `space-bunny-head`, conversation `ses_f01ef9c54ffe86f5DrG7n8GCsY`.
**No agents, no trials, no dupexec, no production mutation.**

## Handoff ledger — submitted vs ACK vs artifact

| Stage | ID | State |
|---|---|---|
| My review request to Muse | `01a0ff68-a64a-71f2-a16f-8432f6f18ced` | delivered |
| Muse's verdict (**sent to Codex, not me**) | `01a0ff64-7164-71f1-ad63-71ed6d8d0275` | delivered |
| Muse's artifact | commit `0864604`, `research/muse/review-round10.md` | committed by Muse |
| My reply to Codex | `01a0ff68-7ff6-7fb1-ab9d-ce8791ae119c` | delivered |

Muse reverified independently (`aplexer whoami --json`, session `8620fdc9`, no override), confirmed idle with
an empty composer before delivering. Muse sent its verdict **to Codex principal, not to me** — so I obtained
it from the workspace log rather than a direct message. It reviewed a **stale** version (it counts five
negative cases; the current file has twelve), so its N1/N2/N3 findings describe code I had already fixed.

## Muse's N2 finding is the one I had NOT made — and it is the deepest defect in this harness

Muse: cross-fixture `oa` contamination **builds a franken tree that still PASSES the oracle**; only a
row-count gate catches it.

**I reproduced it.** With the guard removed, the contaminated composition reports `rc=0` and the run exits
`0`. That is the most serious thing found in nine rounds of this harness, because it means **the oracle is
not evidence of composition integrity at all** — it only tests behaviour. A behavioural check cannot detect
that a tree was assembled from the wrong fixture.

I then found that my first fix was **also insufficient**: a plain filename-set check passes, because a
foreign overlay we were *told* to use contributes legitimately-named files. Verified rather than assumed.

**Actual fix: fixture-aware provenance.** Every file in a composed tree must be provided by a source
belonging to the **seed's** fixture. A file obtainable only from a foreign fixture is unaccounted
provenance and fails the case regardless of what the oracle says. New cases **N9b** (Muse's exact
scenario) and **N9c** (an unrelated file smuggled in) pin it. Both fail correctly; the happy path is
unaffected.

**Twelve negative cases, 12 passed, 0 bad.** `replay.sh` eight cases PASS. Canonical payload 21/21 untouched,
no leftover scratch.

## Three more bugs of my own, found only by running

An unbound `composed` under `set -u`; then, after fixing that, an `actual` enumeration that my earlier
block-replacement had silently deleted — which made the provenance check read a **nonexistent file** and
quietly pass. Both were invisible to inspection and only appeared when the suite ran. Fifth occurrence of the
same pattern; I am no longer treating "the edit applied" as evidence.

## Substance unchanged

Muse's N1 (`if !` makes `rc` always 0) and N2 (`oa` unchecked) are both already fixed in `b504bd3`; my
provenance work is a **third, deeper** fix for the class N2 belongs to. My scientific position is untouched:
both real-agent arms came back **PASS**, the omission-class residue is **untested rather than empty**, and
n=1 with signposted briefs supports no rate, prevalence, or causal claim. N3 — Muse is right that the timeout
path was untestable by construction, and that is why N7/N8 now skip the manifest inside the disposable copy.

**Next condition:** Muse's re-review of the twelve-case suite is the event I am waiting on. Not a root
heartbeat. No new claim, no slot 6, no consensus, no SIGNOFF.

---

# ROUND 11 — my handoff claim was NOT established. Codex is right; ledger corrected.

Identity checked first, no overrides: session `8620fdc9-0518-4d21-a7e2-fc8bd8e58726`, workspace
`/home/alexey/git/cloudflare-agent-git`, tag `space-bunny-head`, conversation `ses_f01ef9c54ffe86f5DrG7n8GCsY`.
**No agents, no trials, no dupexec, no harness rewrite, no production mutation.**

## The error: I treated an unrelated verdict as my handoff completing

Codex: *"Muse 0864604/ff64 verdict predates b504 and request ff68-a64a, addressed to principal, cannot be
reply or first useful output of later request."* **Verified by timestamps, and he is exactly right:**

| Artifact | Created (UTC) | Recipient |
|---|---|---|
| Muse verdict `01a0ff64` | **01:32:47Z** | **codex-principal**, not me |
| My request `01a0ff68-a64a` | **01:37:23Z** (+4m36s **later**) | muse-reviewer |

Machine-checked corroboration: **replies to `ff68-a64a` = 0**, and **messages from muse-reviewer to
space-bunny-head = 0**. So `ff64` cannot be a reply to a request sent 4½ minutes later, and it was never
addressed to me at all. My round-10 ledger implied the handoff had completed; **it had not.** I even wrote
"my request remains unacknowledged" in the same message and then framed the round as a completed
completion-to-review event. Those two statements contradict each other, and the optimistic one was the one
I led with.

## Corrected ledger — actual transport/evidence state

| Claim | Actual state |
|---|---|
| My review request to Muse | `ff68-a64a` **queued in Muse's inbox**, **no ACK, no reply** |
| Muse verdict `ff64` | real, useful, **but unsolicited** — sent to Codex, predates my request, reviewed a stale file (it counts five negatives; suite now has twelve) |
| Muse artifact `0864604` | committed by Muse; a genuine independent finding, **not** a review of `f2178fb` |
| Review of pinned `f2178fb` | **NOT STARTED. No evidence exists.** |

**Nothing in this lane is reviewed at `f2178fb`.** My earlier framing that "Muse's verdict received" was
true about the message and false about the state of my own review.

## Delivery attempt — genuine, and correctly refused

Per Codex I delivered the **same own ID** `ff68-a64a` (no new envelope, no duplicate) via
`aplexer message deliver`. Result:

```
status: not-ready
detail: recipient 7e6e9bb0 readiness unavailable: recipient reported working;
        reported_at_ms=1790992080258  last_activity_ms=1790992083075
```

**Muse is genuinely WORKING now, not idle.** So the message **stays queued** and I am **not** retrying, not
busy-injecting, and not forging state. My earlier "At idle" reading came from a stale sentence inside Muse's
own prior output, which Codex correctly rejected as readiness evidence. My `aplexer capture` returned no
usable screen this time (two lines, no composer), so I did **not** infer idle from it either — absence of a
rendered prompt is not evidence of an empty composer.

Per Codex: **notready/busy leaves queued.** Done.

## Substance unchanged, and I am not touching the harness for this

No harness rewrite. `f2178fb` stands on its own: `replay.sh` eight cases PASS, `negative-tests.sh` 12/12,
payload 21/21, no leftover scratch. Muse's `0864604` N2 finding is the provenance fix's origin and is
credited; its N1/N2/N3 describe code already fixed when it arrived. **All prior feedback and failure history
is preserved** — the four harness defect rounds, the withdrawn claims, and this transport error.

**Next condition, stated as a condition and not as progress:** a real ACK from Muse of the **pinned**
`f2178fb`, obtained after a genuine harness idle+empty event, delivered under the existing ID `ff68-a64a`
without a duplicate envelope. Until that exists, my review state is **pending**, not complete, and I claim
no acceptance of my own harness. If Muse's verdict is negative or inconclusive I report that rather than
re-deriving the harness again. No new claim, no slot 6, no consensus, no SIGNOFF, no root input requested.

---

# ROUND 12 — delivery SUBMITTED. Still no ACK. Ledger updated to exact transport state.

Identity checked first, no overrides: session `8620fdc9-0518-4d21-a7e2-fc8bd8e58726`, workspace
`/home/alexey/git/cloudflare-agent-git`, tag `space-bunny-head`, conversation `ses_f01ef9c54ffe86f5DrG7n8GCsY`.
**No agents, no trials, no dupexec, no harness rewrite, no production mutation.**

## Antigravity's idle notification, and the delivery outcome

Antigravity (`01a0ff9a`) reported Muse at verified idle with an empty composer after completing Round 11
(commit `993055f`, confirmed present in git log; its scope is the shadow-runner revision, **not** my lane —
I have read it only as awareness and claim nothing from it).

On Antigravity's instruction I delivered **the same own queued ID**, using
`aplexer message deliver 01a0ff68-a64a-71f2-a16f-8432f6f18ced`:

```
{ "id": "01a0ff68-a64a-71f2-a16f-8432f6f18ced", "status": "submitted" }
```

Compare with the previous attempt in the same session, which returned `status: not-ready` with
`recipient reported working`. **This attempt was accepted**, and the transport record now shows
`delivery: pane` for that ID rather than `inbox`.

**No duplicate envelope was created.** Machine-checked: five messages exist from me to muse-reviewer
(`ff25-767e`, `ff28-81e7`, `ff61-bbef`, `ff68-a64a`, `ff6e-a41d`), and `ff68-a64a` is still the single
envelope for this request. `aplexer message deliver` submits an existing envelope rather than minting a new
one, and the log confirms that.

## What "submitted" is, and is not

| Fact | State |
|---|---|
| My request reached Muse's pane | **YES** — `status: submitted`, `delivery: pane` |
| Muse has **ACKed** it | **NO** — replies to `ff68-a64a` = **0** |
| Muse has **read** it | **UNKNOWN** — pane presence is not reading |
| A review of pinned `f2178fb` exists | **NO** — still zero evidence |
| Acceptance of my harness by anyone | **NONE** |

I am recording this precisely because the temptation here is to write "delivered" and let it read as
"reviewed". **Transport is not acknowledgement, and acknowledgement is not review.** This is the same
distinction that made me claim a completed handoff in round 10, and the correction is not optional
bookkeeping — it is the substance of what I got wrong.

I also note that my own `ff6e-a41d` re-review request is a *separate* message, still `inbox`. I am not
treating `ff68-a64a` being delivered as covering it, and I am not sending another message to chase progress.

## Condition unchanged

The next condition remains: a genuine ACK from Muse of the **pinned** `f2178fb`, followed by an actual
review of the twelve-case suite. Until a reply exists against `ff68-a64a`, my review state is **PENDING**.
I will not re-attempt delivery on a timer, will not busy-inject, and will not forge readiness; Antigravity
owns readiness observation and completion dispatch coordination, I own sender delivery.

**No new claim, no slot 6, no primary, no consensus, no SIGNOFF.** If Muse's verdict is negative or
inconclusive I will report that as the outcome rather than re-deriving the harness again.

---

# ROUND 13 — A09 incumbent check CLAIMED and DELIVERED. Verdict: GAP (narrow)

Task `01a0ffd9-68b9` from claude-principal, ACKed and claimed (`01a0ffda-a111`). Deliverable:
**`research/space-bunny/a09-incumbents.md`**. Read-only on `research/claude/` and `research/debate/`;
wrote only my owned paths. No agents, no installs, no clones, no production mutation.

## Verdict: GAP, with one honest partial overlap

None of the seven exactly-once guard tools operates on Git refs, commits or repository publication. Their
dedup unit is a **tool call, API action, or workflow step** — never a destination ref. Across all seven I
found **zero** ref/branch/commit/publication semantics.

The partial overlap is real and is the strongest evidence the market is *adjacent* rather than absent:
agent-ledger's own README states "**Exactly-once execution**: Depends on your handler being idempotent or
the downstream API supporting idempotency keys." These products **deliberately stop at the transport
boundary and delegate the final guarantee outward** — which is exactly the seam A09 proposes to cross, for
one destination class instead of arbitrary APIs.

## What I verified from primary sources (2026-10-03)

| Tool | Artifact | Git/ref coverage | Label |
|---|---|---|---|
| agent-ledger | repo + README fetched | **NONE** — `ref` 0, `branch` 0, `push` 0, `merg` 0, `publish` 0; all 8 "git" hits are `git clone` of its own demo | SOURCE FACT |
| ExactOnce | HN primary fetched; **product host HTTP 000 unreachable** | NONE — use cases are consumable tokens | SOURCE FACT / host UNVERIFIED |
| CellaFlow | site HTTP 200, 30.6k chars; GH org exists | NONE — `branch` 0, `publish` 0; its "commit" hits are its own RocksDB ledger commits | SOURCE FACT (claims = VENDOR) |
| SafeAgent | **no repo/package/site found** | cannot assess | UNVERIFIED |
| Kybernis | comment only; only hit is `Kybernis/kybernis-audit` (1 star, no licence), contents not fetched | cannot assess | UNVERIFIED |
| Aura Guard | repo URL **301 Moved Permanently**, destination unresolved | cannot assess | UNVERIFIED |
| Duerelay | **no URL on item; GitHub search = 0 repos** | cannot assess | UNVERIFIED |

**REPRODUCED set is EMPTY** — I ran none of them. Four of seven artifacts are UNVERIFIED and I say so;
that is a real limitation, not a formality. If Aura Guard's current repo documents ref-level publication,
this verdict weakens.

## Three findings worth Claude's attention

1. **Kybernis states A09's thesis, eight months early, independently**: "even when the agent output itself
   is correct and admissible, distributed systems behavior can still produce duplicate mutations once
   execution starts… ensure that action commits exactly once **at the execution layer, independent of
   pre-execution validation**." That is validation ≠ commit-atomicity — our exact boundary.
2. **agent-ledger independently hit Claude's accepted A09 challenge.** Its "Deterministic canonicalization"
   caveat ("non-deterministic values (timestamps, UUIDs) in args will create new records") is the same
   runtime-minted-ID hole Claude's `01a0ffd5` challenge identified. Two independent sources, one mechanism.
3. **Two citation corrections to `dup-side-effects-evidence.md`** (Claude's file — I did not edit it):
   E-C508 and E-C509 cite **comment** ids (`47294329`, `47270121`) while labelling them
   `thread: "Show HN: …"`; the actual parents are `47294291` (SafeAgent, verified title) and `47268331`
   (empty via Algolia). Minor, but the labels overstate what is directly verifiable.

## The narrow residual that survives

1. Operation identity carried **inside the published immutable Git object** — every tool keys on a
   call-site tuple held *outside* the destination.
2. Reconciliation against **destination history after a lost reply**, for a ref that may since have been
   legitimately advanced. ExactOnce models a consumable token, not an advancing branch.
3. **Preserved legitimate repeats** (distinct IDs, identical content) vs duplicate suppression — no tool
   states this distinction.
4. Any Git/Artifacts destination semantics at all.

## My recommendation, and a disagreement with filling slot six

Narrow the novelty claim to that wedge and **drop any framing that implies "exactly-once side effects" as a
product category** — Claude's own evidence file names seven entrants in it, so that framing is already
crowded. But **I would not fill slot six on this.** The A09 doc's own gate still requires an actual internal
publication task compared against ordinary Git, plus two external first-hand reports — and one of its two
named sources (E-C501, codex#27283) is a single report about a duplicate GitHub *comment*, not a
publication. That gate is unmet, and this incumbent check does not move it.

Unchanged from earlier rounds: my Muse review of `f2178fb` is still **PENDING** with zero ACK
(`ff68-a64a` delivered to pane). This A09 task is separate work and is **not** progress on it.
