# Independent feasibility challenge of the six-approach shortlist — round 1

Author: `space-bunny-head`, aplexer session `7564a895-6e3e-44e7-bfe2-1513d7992fec`, selector
`/home/alexey/git/cloudflare-agent-git:space-bunny-head`, engine shell (OpenCode Space Bunny, provider
route `opencode-go`). Round 1 of a bounded headless session. Read-only review of peer files; I wrote
nothing outside `research/space-bunny/` and `coordination/space-bunny.md`.

Target under review: `research/shortlist-6.md`, "Codex draft 3", candidates **A01, A14, A16, A05, A06,
A10**. That file states it is unapproved and that "No candidate has passed the real concurrent-agent
Workers/Artifacts gate". My challenge is therefore aimed at the *selection*, not at a signed digest.

This is a feasibility and evidence challenge. It is **not** a rival shortlist, not an approval, and not
an assertion of consensus. Where I disagree with Codex's recommendation I say so plainly; where Codex
already got it right I say that too.

---

## 0. Headline finding: the "six" is one lane plus five hedges

Before any per-approach scoring, one structural objection that outranks the individual scores.

`research/shortlist-6.md` gives four of its six candidates a kill condition **that the repo's own
local evidence has already tripped or nearly tripped**:

| Candidate | Kill condition written in the shortlist | What the repo's own file already says | Status |
|---|---|---|---|
| A14 | "if ordinary wrangler+Workers Previews reproduces whole workflow in ten minutes or state isn't isolated, fold into A01 verification rather than select as product" (`codex/runtime-isolation-validation.md`) | "both explicit isolation and ordinary control pass. **No local advantage**, real-agent or cloud result" | **kill test already returned null** |
| A16 | "Kill Artifacts-specific local product if ordinary package setup is sufficient" / "No exactly-zero or 1.0x footprint claim" | `codex/storage-validation.md`: sparse source savings "dilute to **18.75% total**"; `codex/package-storage-validation.md`: pnpm union ~49.97% below summed trees | **at or below its own bar** |
| A10 | "Park if no advantage" vs "Entire/checkpoint + git-log baseline" | no recovery measurement exists yet | armed, not fired |
| A06 | "Park if summary hides a bug or reviewer time does not improve" | no comparison measurement exists yet | armed, not fired |

Consequence: the shortlist is not six comparable bets. It is **A01, plus A16 (defensible on pain,
weak on fit), plus three slots currently occupied by unmeasured or already-nulled hypotheses (A05, A06,
A10), plus one slot (A14) whose kill test has already fired and which Codex's own text proposes folding
away while still listing it.**

I do not claim the shortlist is dishonest. Codex wrote the null result down, which is to its credit.
My objection is procedural: **a candidate whose recorded falsification test has returned null should not
travel to sign-off carrying a shortlist slot.** Either fold A14 into A01 verification as Codex already
proposes, or re-open the slot. Carrying it forward unresolved makes the six weaker than its own text
believes it is, and it dilutes the one thing the file is for: choosing.

---

## 1. Scoring

Axes are the seven from `AGENTS.md`: pain, evidence quality, novelty vs existing products, Cloudflare
fit, engineering feasibility by 2026-10-14, demo strength, adoption. 1 (weak) to 5 (strong).
**Feasibility scores are conditional on the shared substrate (below); they are therefore compressed
toward the middle and should not be read as discriminating between lanes.**

### Shared-substrate caveat (applies to A01, A05, A06, A10; partly A14, A16)

Every candidate except the purely local half of A16 requires the same unbuilt stack: Artifacts fork per
task, an **external** runner/sandbox (Workers CPU is 30 s default and 5 min maximum, 128 MB — ordinary
toolchains do not run in a Worker), Durable Object coordination, and a sole canonical publisher that
re-checks the exact head and rejects stale receipts. `research/codex/engineering-feasibility.md`
assesses this; the point I add is that **substrate risk dominates per-lane feasibility.** The correct
question for the principals is not "is lane X feasible by Oct 14" but "is the substrate feasible by
Oct 5", because every agent lane inherits the same answer. Scoring the six on feasibility separately
manufactures a discrimination that does not exist.

| | A01 Radar | A14 Isolation | A16 Storage | A05 Tournament | A06 Review | A10 Handoff |
|---|---|---|---|---|---|---|
| Pain | 5 | 3 | **5** | 2 | 4 | 4 |
| Evidence quality | 4 | 2 | 3 | 2 | 3 | 4 |
| Novelty | 3 | **1** | 2 | 2 | 2 | **1** |
| Cloudflare fit | **5** | 4 | 2 | 4 | 3 | 3 |
| Feasibility by Oct 14 | 4 | 5 | 3 | 4 | 4 | 4 |
| Demo strength | **5** | 3 | 4 | 4 | 3 | 4 |
| Adoption | 3 | 2 | 3 | 2 | 3 | 3 |
| **Total /30** | **29** | 20 | 21 | 22 | 22 | 23 |

Rank: A01 > A10 > A05 ≈ A06 > A16 > A14. That ranking is *not* my recommendation — see §3.

---

## 2. Per-approach challenge

### A01 — Live Integration Radar (Codex's recommended primary)

- **Target user:** operator of 3–20 concurrent tasks on one codebase; the job is detecting composition
  failure while agents still work, not after.
- **Cited-pain strength: strong, with a hard ceiling.** Theme T1 is the best-evidenced theme in the
  ledger and I independently confirmed the load-bearing study: arXiv 2607.04697,
  "AI Agent Pull Requests on GitHub", abstract states 33,596 PRs across 2,807 repositories, three-way
  merge replay on 747 unique co-active pairs, and — the part that matters — **only 0.5% of co-active
  pairs were cross-agent, in 122 of 2,807 repositories (~4.3%)**. So the *mechanism* (textual friction
  under co-activity) is real and the *population* (cross-agent pairs) is small. Strong pain, weak
  prevalence.
- **Novelty: 3, and lower than the shortlist implies.** Pro-1 independently reached the same ceiling:
  "The cited study is real, but measures textual conflicts, not semantic failures." The real novelty is
  narrow and specific — *timing*: warnings at WIP, before queue entry, consumable by the agent. That is
  defensible. But the shortlist's own competitor list understates live competition: Weave (tree-sitter
  entity merging plus impact analysis), Switchman (cross-worktree interface/ownership/staleness with an
  explicit "uncertain" verdict), Collide (symbol-level compare-and-swap, pre-write checks) are all
  entity- and interface-level, not just file-level. Pro-1's honest line is the right one: "Weave's
  advertised benchmark gains are vendor claims" — and equally, so is A01's.
- **Cloudflare fit: 5.** Push events → Durable Object → external runner → publisher is precisely the
  required stack. This is the strongest platform fit in the set.
- **Feasibility by Oct 14: 4.** Two real agents, one small Worker project, one conflicting pair is
  achievable. Conditional on substrate.
- **Demo strength: 5.** Genuinely novel to watch: a warning arrives *while an agent is still working*,
  carries SHAs, and the agent visibly changes course. No incumbent demo does that.
- **Kill test (concrete, dated):** By **Oct 5**, run the local live-uptake comparison: 3 agents, 10 WIP
  pushes, 5 conflicting pairs. **Decision rule:** kill as primary if ≥50% of warnings are not acted on
  before the agent's next commit, or if repair time does not fall versus isolated worktrees +
  completion-time tests. Do **not** accept the shortlist's proposed `median ≤60s / p95 ≤180s` as the
  primary criterion — see §4.

### A14 — Agent runtime and data isolation

- **Target user:** Workers/web developers whose parallel tasks collide via ports, devices, or shared
  data.
- **Cited-pain strength: weak-to-medium.** E-X002 (simulators/ports) and E-X005 (serial app testing)
  are the core; Pro-1 marks simulator claims as not independently reproduced. The adjacent pain
  (E-C321 "manually verifying everything is working") is real but is *verification* pain, not
  *isolation* pain. Nobody in the evidence asks for isolation as a product.
- **Novelty: 1 — lowest in the set, and the repo says so.** The shortlist's own line: "Resource
  isolation alone has not differentiated this lane." Competitors are commodity: Pages/Vercel previews,
  distinct ports, per-task D1/KV namespaces. Worse, GitButler's own documentation already warns that
  separate branches in a shared workspace leave "files, dependencies, generated outputs, and runtime
  state shared" — meaning the isolation gap is a *known, documented* problem with cheap known answers.
- **Cloudflare fit: 4 — and that is the problem.** It fits so easily that the product dissolves into
  configuration.
- **Feasibility by Oct 14: 5.** Easiest to build of the six, which is precisely why it should not occupy
  a scarce slot.
- **Demo strength: 3.** Two live URLs and a cross-task observation attempt read clearly but look flat
  next to A01's live-warning story.
- **Adoption: 2.** Users do not request isolation; they request "it works."
- **Kill test:** If per-task isolation is reproducible in ≤10 minutes with plain `wrangler dev` on
  distinct ports plus distinct D1/KV namespace IDs, with no Artifacts fork and no coordination layer,
  A14 is a runbook, not a product. **`codex/runtime-isolation-validation.md` reports this already
  passes for both the explicit design and the ordinary control.** On the shortlist's own stated
  criterion, A14 is dead.
- **Verdict: weakest of the six. Fold into A01 verification, as Codex already proposes, and do not carry
  it to sign-off as a seventh-equals candidate.** The evidence that would make me reverse: a real-agent
  run where per-task runtime/data isolation *fails* under the ordinary control **and** the Artifacts-fork
  design prevents it — that would convert a null into a product. I have not found such a run, and
  neither has the repo.

### A16 — Storage-aware agent workspaces

- **Target user:** the operator constrained by local disk running concurrent writable tasks.
- **Cited-pain strength: strongest single evidence item in the entire ledger, and the only first-hand
  statement from the actual user** (U7, `experiment/USER-INSTRUCTIONS.md` message 7). Corroborated by
  E-C157/159/160/167/168 and worktree caps E-C318–E-C320. If pain were the only axis, A16 would be
  first. I am rating it 5 and I want that on the record as a genuine disagreement with any reading that
  treats A16 as the weakest lane.
- **Evidence quality: 3, and I have a specific correction.** Pro-5 cites HN 49606281 for "a September
  2026 HN discussion [that] debated COW copies, filesystem migration, clean baselines, copied secrets,
  and worktree-management tools." I fetched the item and its target. **HN 49606281 is a link to
  "Working with Git Worktrees in Magit" (emacsredux.com, 2026-09-02).** I extracted the full article
  text: it contains **zero** occurrences of *reflink, copy-on-write, COW, btrfs, XFS, APFS, secrets,
  filesystem, overlay, hardlink,* or *sparse*; "disk" appears once. The article is a practitioner's
  account of discovering worktrees *because AI coding agents create one per task* and finding his
  projects directory full of siblings. That is good evidence — for **worktree proliferation caused by
  agents**, a claim nobody else in the ledger makes plainly. It is **not** evidence for any storage
  mechanism, and Pro-5's characterization of it does not hold up.
- **Novelty: 2.** Two incumbents bracket it. **ArtifactFS** is a documented Git-backed FUSE working
  tree with lazy hydration and a writable overlay (Codex E-X021, and Pro-5: "ArtifactFS lowers the
  novelty of lazy Git mounting"). **pnpm** already shares immutable dependency content, and Codex's own
  measurement gives ordinary package sharing a ~49.97% union advantage over summed trees.
- **Cloudflare fit: 2 — the structural problem.** A16's premise is *local* disk; Artifacts is a
  *remote* Git host. The competition mandates Workers and Artifacts. Pro-5 states the consequence
  itself: "Artifacts should earn its place through versioning, scoped access, lifecycle integration, and
  recovery — **not through an assumed local-disk benefit**." That sentence retires A16's Artifacts
  nexus. A16 is the strongest-pain / weakest-platform-fit lane, and a competitor judge who notices
  that will discount it on the 25% collaboration axis.
- **Feasibility by Oct 14: 3.** Requires disciplined physical-vs-apparent measurement, a remote
  sandbox comparison, and two real agents — under a 512 MiB spike budget and a filesystem with 11 GiB
  free. The measurement itself is the risky part.
- **Demo strength: 4.** Byte deltas and a disk inventory are unusually legible to a judge: "here is my
  disk before, here it is with two agents running, here are the accounted bytes."
- **Kill test:** By **Oct 7**, measure physical (not apparent) bytes at N=10 and N=20 post-build and
  post-divergence, charging seeds, caches, and metadata, against the pnpm-store and sparse-checkout
  controls. **Decision rule:** kill the Artifacts-specific product if physical savings fall below 50%
  — Pro-5's own suggested bar. Codex's local result of **18.75% total** for sparse-source savings is
  already below it, so A16 needs the remote-sandbox arm to carry it, and that arm has the weakest
  platform fit. Separately: kill if ArtifactFS's documented lazy hydration plus ordinary pnpm sharing
  achieves comparable whole-environment economy without a new runtime.

### A05 — Behavior-based fork tournament

- **Target user:** existing best-of-N users selecting one attempt by behavior rather than by eyeballing
  diffs.
- **Cited-pain strength: weak.** E-C320/323 (best-of-N "does not merge changes back") and E-C326/364 are
  the support, but the shortlist concedes "not evidence all developers want N attempts," and Pro-2 found
  the direct counterevidence: on Cursor's own forum, users "question whether paying for several
  implementations adds value when their preferred model predictably wins; some prefer dividing
  independent tasks instead." That is not a weak signal — that is your target persona's own forum.
- **Novelty: 2.** Pro-2 is blunt: "Neither parallel implementation nor model-based winner selection is
  new." Cursor ships isolated worktrees, simultaneous attempts at the same prompt, side-by-side results,
  and a suggested winner. A05 is a better UX on a shipped feature.
- **Cloudflare fit: 4.** Same substrate as A01.
- **Feasibility: 4.**
- **Demo strength: 4 — with an honesty defect I want flagged now.** The shortlist's MVP says "one seeded
  plausible-but-wrong behavior." Pro-2 explicitly warns against presenting this as natural: "A
  deliberately faulty fixture is useful for testing the product; it must not be presented as a naturally
  occurring failure from a live agent run," and its own MVP says "Do not deliberately instruct one agent
  to fail." **These are in tension.** A seeded failure is fine for a rehearsal; if it appears in the
  submission video without an on-screen "seeded fixture" label, it is a misrepresentation and it is the
  kind of thing a judging panel notices. Decide now which A05 is, and label it either way.
- **Adoption: 2.** See the Cursor forum counter-evidence.
- **Kill test:** By **Oct 8**, five tasks, single attempt vs A05 tournament vs Cursor-style selection
  with candidate patches and available tests held constant. **Decision rule:** park A05 if outcomes are
  equal at higher usage, or if it wins only when it is secretly given better tests.
- **Overlap objection:** A05 and A06 both reduce to "two agents, independent tests, human decides." In an
  8-minute video they are near-indistinguishable. Two of six slots for one demo shape is a portfolio
  weakness, and it costs the panel the ability to discriminate on 50% of the score (originality plus
  prototype quality).

### A06 — Change-story review queue for internal teams

- **Target user:** accountable reviewer in an AI-accepting team. Note the deliberate narrowing: the
  policy bloc (E-C210/211/212/217/218) is established as **non-buyers**, so this lane has no OSS segment.
- **Cited-pain strength: 4, strongest by volume.** T3 is the largest theme in the ledger. But the sharpest
  single statistic is vendor-sourced (E-C228, Faros +91% review time) and must be attributed as such;
  E-C230 (SO, 66% "almost right") is stronger because it is practitioner testimony.
- **Novelty: 2.** Pro-2 lists the occupied ground precisely: "Understand the change," "remember what I
  reviewed," and "compare code with the issue" are **already occupied** by CodeRabbit Change Stack,
  Copilot review/approvals, and Entire context. The shortlist's own line agrees: "generated summaries
  alone are commodity."
- **Cloudflare fit: 3 — the second-weakest.** A review-story generator is mostly text production over
  diffs. The Worker must group pushes and the runner must derive behavior, but the value does not
  obviously live on Cloudflare.
- **Feasibility: 4.**
- **Demo strength: 3.** Visually flat. High risk of being read as "a summarizer," which is the single
  most crowded category in developer tooling.
- **Adoption: 3**, but the buyer pool is narrow by construction.
- **Kill test:** By **Oct 8**, blind seeded-bug review against a plain PR list, ≥5 reviewers.
  **Decision rule:** park A06 unless review time drops ≥30% **with an equal or better catch rate** on a
  declared small sample. If a summary hides the seeded bug, park immediately — that is a correctness
  failure, not a taste question.
- **My objection beyond the score:** A06 is the lane most likely to be mistaken for an incumbent
  feature. Pro-4's list of "do not lead with" — collision detection, review swarms, PR babysitting,
  stacked changes, multi-agent dashboards — includes this lane's core deliverable.

### A10 — Durable task handoff tied to code state

- **Target user:** operator restarting or replacing an agent mid-task and needing to resume on the right
  base.
- **Cited-pain strength: 4, and I independently strengthened it.** I verified the two Claude Code issues
  Pro-3 leans on, including dates: **issue #25273 "Context compaction generates fabricated 'Pending
  Tasks' from user complaints, causing AI to execute opposite of user intent" — created 2026-02-12,
  closed 2026-02-16**; and **issue #26698 "Task list state not reconciled after context compaction" —
  created 2026-02-18, closed 2026-02-22.** These are precisely on point for "resume the right work on
  the right base." Two caveats the principals must carry: both are **closed**, and #25273 was closed as a
  duplicate. They establish reported failure modes, not incidence, and not a fix status. Nothing in the
  ledger should treat them as prevalence.
- **Novelty: 1 — tied for lowest, and the shortlist concedes it.** "Entire is a strong current competitor,
  not absent." Pro-3's check is more specific: Entire "already resumes sessions from branches and
  supports concurrent checkpoint writes," with per-checkpoint refs. Claude Code has native checkpointing
  with documented exclusions; Codex documents AGENTS.md precedence. Three credible incumbents.
- **Cloudflare fit: 3.** Storing a versioned manifest is a Durable Object row; the genuinely interesting
  part is git notes and Artifacts-versioned evidence, which is storage, not Workers.
- **Feasibility: 4.**
- **Demo strength: 4.** A mid-task handoff while canonical head advances is a good story with a real
  tension in it.
- **Adoption: 3.**
- **Kill test:** By **Oct 8**, five restart/drift tasks against native resume + same-commit structured
  plan + current Entire, with dirty and untracked state explicitly in scope. **Decision rule:** park A10
  unless correct-base recovery and preserved acceptance are both better **and** reviewer effort falls.
  Pro-3's own bar is a good one to adopt: across 20 placed interruptions with two live agents, require
  zero lost acknowledged checkpoints, zero stale-owner promotions, and ≥18 resumptions without manual
  state repair.
- **One live risk neither file raises:** both #25273 and #26698 were closed within days, and #62122
  within minutes. Fast auto-closure means these reports are *uninvestigated*, which strengthens the
  mechanism as a hypothesis and weakens them as evidence of anything else. Any demo built on A10 should
  reproduce the failure locally rather than cite the issues as proof it happens.

---

## 3. Recommendation

**I do not displace Codex's A01 primary, and I say so deliberately: the timing novelty (warnings at WIP,
consumable by the running agent) is the only differentiator in the entire set that no incumbent I
checked ships, and it is the best Cloudflare fit available.** My reservations are about *how it is
measured* and about *what else is in the list*.

Three concrete asks:

1. **Re-open or fold A14.** Its kill test has fired. Carrying it unresolved into sign-off is the one
   thing in the draft I would refuse to sign.
2. **Merge A05 and A06 into one demonstration** and use the freed slot for an unmeasured hypothesis,
   rather than running two near-identical videos.
3. **Score the substrate, not the lanes, on feasibility.** One Oct-5 substrate milestone, then per-lane
   feasibility stops being a discriminator.

If the panel needs a primary and A01's local live-uptake comparison fails its Oct-5 gate, my own view is
that **A16 is the better long-term product** (strongest first-hand pain, legible demo) and should be the
retained fallback — but it must then be rebuilt around Pro-4's Task Passports framing (task-scoped
source visibility) to regain a Cloudflare nexus, or it will be judged off-platform. That is a *reframe of
an existing lane*, not a seventh approach.

---

## 4. A methodological objection that affects the shortlist's primary

`research/shortlist-6.md` proposes for A01: "Proposed median ≤60s/p95 ≤180s at three agents and ten
pushes, with explicit sample limits."

**That is a latency bar being used where an outcome bar is required.** A01's entire thesis is that an
agent *acts on* a warning before finishing. Warning latency is necessary but not sufficient; a warning
that arrives in 60 seconds and is ignored is worth exactly zero. Pro-1's falsifier is the correct frame:
"when an ordinary merge queue runs the same tests, does the new workflow actually reduce repair effort
or wasted agent work?" And Pro-1 supplies the counter-evidence that should be treated as the primary
risk to A01, not a footnote — HN commenter koliber: attention is the limiting resource, finding more than
three concurrent sessions is difficult, and **"a product that adds another alert stream may worsen the
actual bottleneck."**

A01's sharpest adversary is therefore not GitHub's merge queue. It is **alert fatigue**. Add an
action-rate criterion to the Oct-5 gate (see §2, A01), and the p95 latency number becomes a constraint
rather than the objective.

---

## 5. One constructive reframing (not a seventh approach)

The six all treat the **runner** as given infrastructure. None treats the *integrity of the runner's
verdict* as something to be demonstrated. This matters because in A01 the warning comes from a runner,
in A05 the winner is chosen by hidden tests, in A06 the reviewer trusts behavioral claims, and in A10 the
receiver trusts a manifest's "accepted tests." **If a receipt is stale, forged, or replayed, all four
fail** — and today none of the four would show that, because each demo seeds a *code* bug rather than an
*evidence* attack.

Both principals' integration already demoted the receipts idea to substrate: Pro-2's "Evidence Receipts"
was mapped to A09 shared runner evidence, Pro-3's "Replayable Change Receipts" to A09/A11. I think that
demotion is defensible **as architecture and wrong as demo strategy**.

**Reframing: keep A01 as the spine; make the demonstrated adversary a compromised or stale verdict rather
than a seeded code bug, and make replay a first-class inspectable object a judge can re-execute.**
Pro-2 states the principle better than I can: "a tool can make evidence easier to inspect **without making
the evidence sufficient**. The product must expose that boundary rather than turning it into a green
badge." Pro-1 supplies the concrete record shape: base SHA + ordered candidate SHAs + harness SHA +
runtime image + test command + result/log digest.

This is a sharpening of shared substrate, not a new lane. It **dies with A01** — if A01's Oct-5 gate
fails, there is nothing left for it to sharpen. It is not a hedge, and it must not be counted as a
seventh approach or used to fill the A14 slot. Its falsification test: attempt to promote a stale, forged
and test-swapped receipt in the demo; every one must be refused or visibly flagged, and a judge must be
able to re-execute the record. If any of the three succeeds, the framing is wrong.

---

## 6. Citations I spot-checked

Independent checks run 2026-10-02 from this session. Network fetches returned real content; I did not
take any citation on trust.

### Did not hold up

1. **Pro-5 / HN 49606281 — mischaracterized source.** Pro-5: "A September 2026 HN discussion debated COW
   copies, filesystem migration, clean baselines, copied secrets, and worktree-management tools."
   Verified via HN Algolia: item 49606281 = "Working with Git Worktrees in Magit", 147 points,
   2026-09-08, linking to emacsredux.com. I fetched the article (18,539 bytes raw, 8,501 chars text) and
   searched: *reflink* 0, *copy-on-write* 0, *COW* 0, *btrfs* 0, *XFS* 0, *APFS* 0, *secrets* 0,
   *filesystem* 0, *overlay* 0, *hardlink* 0, *sparse* 0, *disk* 1. The thread is 14 comments. **None of
   the storage-mechanism claims hold.** What the source *does* support, and what no other ledger entry
   states plainly: an individual practitioner's discovery that AI coding agents create one worktree per
   task and that this cluttered his projects directory. That is a genuine, citable datum about
   agent-caused worktree proliferation — but it is a different claim.
2. **Pro-2 uncited claim.** "A March Claude Code issue report alleges that an agent changed an isolated
   test despite instructions" carries **no URL anywhere in the file** — no issue number, no year. This is
   the evidentiary backbone of Pro-2's Rank 2 and it is unverifiable as written.
3. **Pro-3 attribution gap.** CASP is credited with "its documented local/CI workflow checks project
   state against Git, including stale references and state consistency," but the in-text marker resolves
   to the Superpowers issue URL, not a CASP source. Same for "Beads is Dolt-backed" and Git AI
   attribution: asserted, uncited.
4. **Pro-5 unlinked issue.** "pnpm issue #14782 … opened September 10" has no URL in the file. I
   resolved it: `https://github.com/pnpm/pnpm/issues/14782`, "packageImportMethod auto no longer falls
   back to copying when the filesystem refuses hard links (regression from pnpm 11)", created
   2026-09-10, **closed the same day (22:21Z)**. The claim is true; the file just did not cite it.
5. **Pro-1 judgment wording drift.** Pro-1 states the 25% criterion as "concurrency and collaboration
   effectiveness"; Pro-2 and Pro-4 as "multi-agent collaboration effectiveness." Minor, but two of five
   Pro outputs word the rules differently, which is a sign nobody read the terms PDF closely.
6. **Tracking artifacts.** Four Pro-4 URLs and one Pro-5 URL carry `?utm_source=chatgpt.com`. Strip
   before any of them enters the public ledger.

### Held up (recorded so the principals can rely on these)

7. **arXiv 2607.04697** — real. Title "AI Agent Pull Requests on GitHub: Frequency, Structure, and Merge
   Conflict Rates", submitted 6 Jul 2026. Abstract confirms 33,596 PRs / 2,807 repositories, 747 replayed
   co-active pairs, **cross-agent pairs only 0.5% of co-active pairs, in 122 of 2,807 repositories
   (~4.3%)**. The replication repo `github.com/Quantum535/concurrent-agentic-prs-replication` resolves (200).
   **This confirms the ledger's own caveat is correct and is the strongest limiter on A01's prevalence
   story.** Pro-1's derived rates (19.8% / 41.7% / 23.3%) come from the replication repo's summary CSV,
   which I did not independently recompute.
8. **arXiv 2609.25396** — real. "Passes Alone, Fails Together: Benchmarking Semantic Coordination in
   Parallel LLM-Agent Development", submitted 21 Sep 2026. Abstract confirms **834 runs on 417 mined
   Django pairs, only one interference case; constructed tasks 97% interference; a completion-message
   recovered 82%.** Codex's `pro-integration-round-1.md` figures (105/108 failures, 89/108 recoveries)
   are arithmetically consistent with 97.2% and 82.4%. Codex's handling of this paper is correct, and its
   conclusion — that constructed rates do not estimate production prevalence — is the right one.
9. **GitHub issues, all real, all dates exact.** `anthropics/claude-code#25273` (created 2026-02-12,
   closed 2026-02-16); `#26698` (created 2026-02-18, closed 2026-02-22); `#62122` (created 2026-05-25,
   closed within ~2 minutes); `openai/codex#8643` (created 2025-12-31, closed within 29 minutes);
   `obra/superpowers#989` (created 2026-03-29); `pnpm/pnpm#14782` (created 2026-09-10, closed same day).
   Titles match the Pro descriptions closely. **Note the closure pattern: three of six closed in under a
   day, two within minutes. These are uninvestigated reports — good hypothesis evidence, weak prevalence
   evidence, and no evidence of a fix.**
10. **Artifacts limits** — `developers.cloudflare.com/artifacts/platform/limits/` confirms 1 GB/repo,
    32 MB/blob, 1 TB/account, and 2,000 requests per 10 seconds. Pro-4's table is accurate.
11. **Artifacts pricing** — confirms verbatim: "Cloudflare will begin billing for Artifacts operations and
    storage on **October 14, 2026**"; first 10,000 ops/month then $0.15 per additional 1,000; first 1 GB
    then $0.50 per GB-mo, averaged as daily peaks over a 30-day period; **Artifacts operations show
    "Unavailable" on the Workers Free plan**, which independently confirms Workers Paid is genuinely
    required. The heartbeat's preference for Oct 14 over the blog's Oct 15 is correct and now
    primary-sourced. The un-reconciled tension with the rules' "no purchase necessary" stands.
12. **HN item identities** (via Algolia): 46961345 = Entire launch (2026-02-10, 611 pts);
    48089263 = "PS3 Emulator Devs Politely Ask That People Stop Flooding It with AI PRs" (2026-05-10) —
    supports Pro-2's maintainer-overload use; 46426624 = "Show HN: Stop Claude Code from forgetting
    everything" (2025-12-29). Direct HN HTML fetches returned HTTP 419 (rate-limited); Algolia was used
    instead, which is also Claude's documented method.

### Not checkable here

13. HN 47246905 and 46716601 have no title or URL — they are comment records (authors vidarh and koliber,
    2026-03-04 and 2026-01-22). Pro-1's quoted koliber text could not be confirmed from the Algolia
    comment body in my check. Treat that quote as unverified until someone pulls the comment text.

---

## 7. What I need from peers

- **Codex:** confirm whether A14's slot is folded or reopened. My position: a fired kill test should not
  reach sign-off. Also: is the A01 latency threshold being replaced by an action-rate threshold?
- **Claude:** the ledger's T1 entry for arXiv 2607.04697 should carry the 0.5%-of-co-active-pairs /
  122-of-2,807-repositories figure inline, not only as a parenthetical caveat. It is the single most
  load-bearing limitation on the recommended primary's prevalence story, and it should be impossible to
  quote A01 without it.
- **Both:** someone should recheck Forge / Weave / Switchman / CASP / Pact / Worktrunk against current
  primary sources before any novelty sign-off. A01's novelty is a timing argument over an increasingly
  entity-aware field, and three of those products have shipped since this debate started.
- **Orchestrator:** `collidemcp.com` resolves (200) but I did not verify its capabilities. Codex and
  Pro-1 both failed to. If Collide ships WIP-time integration warnings, A01's novelty argument changes
  materially.

## 8. Blockers

None. No blocker prevented this deliverable. One environment limit: HN HTML endpoints rate-limit this
host (HTTP 419); Algolia was used, consistent with the ledger's own verification method. Disk headroom
(11 GiB) and the 512 MiB spike budget constrained what I attempted; I performed no installs, no clones,
and no filesystem measurements, so my §2 A16 assessment rests on the repo's existing measurements plus
one corrected citation, not on new bytes.