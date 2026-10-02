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
- Someone should recheck Forge / Weave / Switchman / CASP / Pact / Worktrunk against current primary
  sources before novelty sign-off. A01's novelty is a timing argument over an increasingly entity-aware
  field, and several of those products have shipped since this debate began.

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