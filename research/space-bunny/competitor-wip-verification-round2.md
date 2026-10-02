# Competitor verification round 2 — do anyone ship unfinished WIP-time integration warnings consumed by coding agents?

Author: `space-bunny-head`, aplexer session `0066a53b-3675-41da-b6f2-19cd40f5bc68` (interactive
resume of round-1 conversation `ses_f01ef9c54ffe86f5DrG7n8GCsY`; round 1 was sent from
`7564a895-6e3e-44e7-bfe2-1513d7992fec`). Round 2, interactive. Owned paths only, explicit-path commits,
single flock transaction. No installs, no clones, no cloud deploys, no token changes.

**Bottom line: yes. Collide ships exactly that, and A01's novelty *framing* is dead. A01's residual
novelty survives but is much narrower than `research/shortlist-6.md` claims, and it now has a specific,
cheap, executable falsification test (§5, Gate 3) that must be run before sign-off.**

---

## 0. Method: three separate categories, never merged

The instruction for this round was to separate claims from verified execution and source facts. I use
three labels throughout and never blur them:

| Label | Meaning | Standard applied |
|---|---|---|
| **SOURCE FACT** | Documented capability, quoted from a primary artifact I retrieved today | README/docs/marketing page text or repo API metadata, quoted verbatim |
| **VENDOR CLAIM** | A number or performance assertion made by the vendor | Recorded as asserted. **Not** treated as result unless independently reproduced |
| **REPRODUCED** | I or a third party actually ran it and observed the outcome | **Empty set in this document.** I ran no product and executed no competitor benchmark |

**REPRODUCED is empty everywhere below.** That is the most important single fact in this round, and it
applies to A01's own evidence as much to competitors'.

Retrieval date 2026-10-02. Artifacts fetched: `collidemcp.com` (+ Study 3 and Study 2 benchmark pages),
`api.github.com` metadata and `raw.githubusercontent.com` READMEs for `Ataraxy-Labs/weave` and
`switchman-dev/switchman`, plus repo-local fixtures for §6.

---

## 1. The direct answer

**Does any product ship unfinished-work, WIP-time, agent-consumed integration warnings? — Yes.**

**SOURCE FACT** (`collidemcp.com`, `schema.org` `SoftwareApplication` description, verbatim):
> "every agent on your team sees what the others are doing, so they stop colliding and stop re-reading.
> Collide briefs each agent on the exact code its prompt is about (a code graph plus embeddings),
> **tells it the moment a teammate changes what it depends on**, and lands every git push in one step."

**SOURCE FACT** (four MCP verbs "shipped to every agent in the MCP handshake, with zero setup"):
> `get_briefing` · `declare_intent` · `check_collisions` · `report_edit`

**SOURCE FACT** (`check_collisions`):
> "One call answers: has anyone changed what I am about to depend on? Exact symbols, the new
> signature, who did it, how fresh."

**SOURCE FACT** (real-time delivery into the running agent):
> "**It hears about teammates as it happens.** When a teammate's agent changes something yours uses,
> your agent is told on its next step. No re-reading to find out what moved."

**SOURCE FACT** (pre-code intent notification — *earlier* than A01's WIP-commit trigger):
> "Notices when a teammate **starts the file** an agent's task is about"
> `declare_intent`: "Before starting, the agent posts what it plans to touch. Intents expire on their own
> if the work stalls, so stale claims never pile up."

**SOURCE FACT** (automatic, per-write, not polled):
> "With hooks installed, this happens on **every single write**, automatically."

**SOURCE FACT** (colliding work is held rather than merely warned):
> "Work that would collide is held for the seconds it takes the other change to land, then released.
> **The collision never gets written.**"

**SOURCE FACT** (integration surface and licence — both permissive and inspectable):
> Remote MCP server `https://mcp.collidemcp.com`; "Claude Code, Codex, Cursor"; open-source Claude Code
> plugin, **MIT**, Shell, at `github.com/lithometric/collide-plugin`; free tier; listed in Smithery,
> MCP.so, Glama, PulseMCP, Awesome MCP Servers; "As seen on Y Combinator".

**SOURCE FACT** (Collide states A01's semantic-failure thesis in its own words):
> "Git finds conflicts at merge time. By then the damage is already written. One agent renames a
> function while another writes new code that calls the old name. **Both merge cleanly, and the project
> is broken anyway.** Four agents do an afternoon of work in ten minutes, so that blind window is no
> longer survivable."

### Consequence for A01 — stated precisely, because overstating it in either direction would be a disservice

**What is now occupied:** "tell the running coding agent, over MCP, that a teammate changed something
it depends on, while both are still working." Collide does this with intent-level notices, per-write
hooks, and zero-setup MCP. `research/shortlist-6.md` presents A01's novelty as "head-vector-specific
warning via agent endpoint/MCP + view" and as being "earlier than queue entry." **The agent-endpoint
timing half of that is no longer novel.** Any A01 demo whose headline is "the agent gets warned early"
will be met with "install Collide."

**What is not occupied:** Collide detects collisions and *dependency invalidation* at symbol/signature
granularity. I found **no evidence anywhere on its site, docs, or benchmark pages that Collide executes a
composed test suite against two unfinished trees.** It answers "did someone change what I depend on?"
It does not answer "do your change and theirs break *together* when neither touches the other's symbols?"
That is the residual, and §5 Gate 3 is how you kill it.

---

## 2. Collide — what its published evidence actually measures (the crux)

Collide markets heavily on numbers. **Every number it publishes is a token or context-discovery metric.
Not one reports collision-detection accuracy, false-positive rate, repair effort, or a comparison against a
merge queue.** That matters enormously, because those are precisely the metrics A01 must beat.

**SOURCE FACT** — Study 2 (`/benchmarks/study-2-ten-agents-one-repo`, Sep 26 2026): ten agents, one
task. "the ten on Collide used 240K tokens each and the ten searching the repository themselves used
1,262K." Totals 2,395K vs 12,623K tokens; $1.69 vs $4.91.
**The mechanism is amortised discovery, stated plainly by the vendor:** "Agent 1 on Collide pays for
discovery (545K); agents 2 to 10 inherit it."
**Critical limit:** "Every agent in both groups landed the change correctly." **No collision occurred.**
A benchmark in which nothing collides measures nothing about collision handling.

**SOURCE FACT** — Study 3 (`/benchmarks/study-3-teams-easy-to-hard`, Sep 28 2026): three tiers; hard
tier is 4 people / 12 agents / 654 files, "vague tickets." 47% fewer tokens, 12/12 correct.
**Methodological merits, stated for fairness:** "Tasks were graded by hidden tests on the final origin,
never by what the agents said they did"; "The same prompts ran without Collide, with no MCP server and
no hooks"; model Claude Sonnet 5.
**Two disclosures that undercut the headline:**
1. "**The first round of that tier was a tie and exposed defects in Collide**; later rounds added
   landing, which takes the push-rebase-retest loop out of the model, **and a notice when a teammate
   starts the file your task is about.**"
   → The 47% figure comes from the *final* round only. The capability that most directly pre-empts A01
   **did not exist during the first round**, where Collide tied the baseline. The published number is not
   evidence that the notice caused the win.
2. "The last round also ran with the Ponytail plugin, alone and alongside Collide" → the hard-tier round
   is confounded by a second plugin, and Collide separately reports "50% fewer tokens with Collide and
   the Ponytail plugin together."

**SOURCE FACT** — Collide's own medium-tier prompt is a semantic-interference fixture: "low stock alerts
arent going out when something actually runs out completely. fix it", where "one agent renames a
function two others depend on." So the demo Collide ships is *adjacent* to A01's demo — worth knowing,
and worth being honest about in our own narrative.

**SOURCE FACT** — an internal inconsistency on the Collide landing page worth noting for any comparison
we write: the same page displays "621×", then refers to "the way the 71.5× is computed", then states
"This is the number we publish. **5.3×**", and invokes an undefined "Graphify's arithmetic". Three
different multipliers on one page. Not disqualifying, but it is not the presentation of a settled result.

**VERDICT, stated in the categories this round demanded:**
- **SOURCE FACT:** Collide ships unfinished-work, agent-consumed, MCP+hook integration warnings, with
  intent-level notices. Confirmed.
- **VENDOR CLAIM (not reproduced by me or anyone I found):** 47%, 5.3×, 5.4 vs 10.4 searches, 14 vs 25
  turns, 4.0 vs 8.9 git calls, 12/12 correct. Vendor-run, vendor-selected repositories, vendor's own
  grader, no third-party reproduction located.
- **NOT MEASURED AT ALL:** collision-detection precision/recall, false-positive rate, time-to-repair,
  comparison against a merge queue, and behaviour when two unfinished trees interfere with **no symbol
  overlap**.
- **REPRODUCED:** nothing. Empty set.

The honest two-sided conclusion: **Collide's existence damages A01's framing, and Collide's evidence does
not damage A01's lane.** Anyone claiming Collide has already beaten us is over-reading a token benchmark;
anyone claiming we are still novel because of "warning agents early" is quoting a claim Collide's own
README now occupies.

---

## 3. Weave — real, substantial, and aimed at the *opposite* moment

**SOURCE FACT** (`github.com/Ataraxy-Labs/weave`, README):
> "**Entity-level semantic merge for Git.** Resolves merge conflicts that Git can't by parsing code into
> functions, classes, and keys with tree-sitter, then merging those entities instead of lines."

**SOURCE FACT** (workflow — this is the decisive timing fact):
> `weave setup` — "this repo now merges through weave; `git merge/rebase/cherry-pick` unchanged"

**SOURCE FACT** (agent surface exists): `weave-mcp` — "MCP server exposing weave to agent frameworks
(**22 tools**)"; plus `weave-github`, a "GitHub webhook service behind the hosted PR-comment
integration."

**SOURCE FACT** (GitHub API): 1,312 stars, 45 forks, 1 open issue, Rust, licence Apache-2.0 per API
(badge reads MIT OR Apache-2.0), created 2026-02-06, **last push 2026-09-30** — i.e. actively maintained
as of three days ago. Topics include `coding-agents`, `merge-driver`, `mcp`, `tree-sitter`.

**VENDOR CLAIM:** repo description "**~95% reduction** vs. line-based merge." Self-reported. Not
reproduced by me.

**Assessment: Weave does not threaten A01's timing, and it does threaten a different A01 novelty claim.**
- It operates at **merge time on committed branches** — the opposite of WIP-time. It also cannot help with
  an uncommitted tree.
- It resolves **textual/entity conflicts so the merge succeeds**. Its problem statement is Git inventing
  conflicts; A01's is two clean-merging changes jointly breaking behaviour. Complementary, not competing.
- **But:** "entity-level semantic merge" is now a shipped, well-funded-looking, actively-developed,
  permissively-licensed product. **A01 must not claim entity-level or tree-sitter-level novelty.** It
  never really did; this just makes it non-negotiable.

The 22-tool MCP server is the item to watch. I did not enumerate the tools; a future round should, because
if any of them operate on uncommitted state the timing analysis changes.

## 4. Switchman — real, but Pro-1 overstates it badly

**SOURCE FACT** (GitHub API): **6 stars**, 2 forks, JavaScript, MIT, created 2026-03-10, **last push
2026-06-18** — roughly 3.5 months stale as of today.
**SOURCE FACT** (README): "Merge confidence for parallel AI coding sessions." Verdict vocabulary:
> 🟢 GREEN — "Safe to merge. No agentic drift detected across 3 worktrees."
> 🟡 AMBER — "Review before merging. Interface mismatch on auth middleware."
> 🔴 RED — "Do not merge. Ownership conflicts and unclaimed changes detected."

**SOURCE FACT** (the honest bit, and genuinely good design):
> "When Switchman cannot make a trustworthy call, it reports `uncertain` instead of pretending the merge
> is safe."

**SOURCE FACT** (agent surface): "Switchman ships an MCP server that lets agents claim files, pull tasks
from a shared queue." Entry points are pull-based: `switchman review --all-worktrees`,
`switchman review --pr-ready`, `switchman gate install-ci`.

**Assessment:** Switchman *can* read in-progress worktrees and *does* ship an MCP server, so it is not
irrelevant. But the documented model is **a human runs it and gets a verdict**, plus optional CI gating.
I found **no documented per-write hook that pushes a finding into a running agent** — the mechanism
Collide has and the one A01's framing rests on. With 6 stars and a 3.5-month-stale last push, it is a
hobby-scale project.

**Correction for the record: Pro-1 listed Switchman alongside Weave and Collide as "direct competition."**
That overstates it by roughly an order of magnitude on adoption and overstates it on mechanism. It should
be recorded as *adjacent tooling*, not a primary competitive threat.

---

## 5. Gates I am proposing — exact, dated, with decision rules

These replace the shortlist's `median ≤60s / p95 ≤180s` latency bar, which I argued in round 1 is a
latency criterion standing in for an outcome criterion. I adopt Pro-1's and Pro-2's thresholds where they
exist so the gate is not invented by me.

### Gate 1 — Warning action rate (the replacement for the latency bar)

**Instrumentation requirement (this is the hard part, and it is why the metric is meaningful):** action
rate is only measurable with an **agent-side event log**, not a dashboard. A warning shown in a web view
cannot be scored. This forces A01 to actually build the agent endpoint — which is the right forcing
function.

- **Unit:** one *warning event* = a triple `(warned_agent, warned_about, implicated_head_sha)` delivered
  to the agent while the warned agent still has uncommitted or unpushed work.
- **Denominator:** warning events delivered during live work. Warnings raised after an agent finished go
  to the human path and are **excluded** from this denominator.
- **"Acted on"** = before the warned agent's next commit to its own fork, any of:
  (a) a write touching a file or symbol named in the warning;
  (b) a read of the implicated dependency at or after the new head (a re-read);
  (c) a machine-readable deferral citing the warning ID.
- **Unattributed** = no qualifying event before that next commit.
- **Decision rule:**
  - **Reject A01 as primary:** action rate **< 50%**.
  - **Indeterminate:** 50–70%.
  - **Conditional pass:** **> 70%**, *and* at least one conflicting pair shows a measurable outcome
    difference (Gate 2), *and* Gate 3 produces at least one interference case with no symbol overlap.
- **Minimum sample:** ≥10 warning events across ≥3 conflicting pairs, ≥2 real agents. **Below 10, report
  "indeterminate", never "pass".**
- **Anti-gaming rules, all mandatory:**
  1. The warning must carry the head SHA that was current when it fired. A warning naming a later head is
     invalid and must not count.
  2. A Durable Object must invalidate on new heads; a warning against a stale head scores as a **miss**,
     never as "not actionable".
  3. No retroactive scoring after the fact — the log is append-only and read at the end.
- **Why this beats latency:** delivery latency can be made small by shipping fast useless warnings.
  Action rate cannot be gamed by speed. It measures the thing A01 actually claims.

### Gate 2 — Repair effort

- **Design:** paired A/B, **same harness**. Identical task pairs, identical protected oracle, identical
  available test suite exposed to **both** arms. Pro-2's constraint is adopted verbatim because it closes
  the obvious cheat: *"Reject the standalone product if it only helps because it secretly receives better
  tests."*
  - **Arm A:** WIP warnings live.
  - **Arm B (baseline):** isolated worktrees + completion-time tests — the ordinary incumbent workflow.
- **Primary metric:** *agent-visible repair steps* = agent turns between the first combined-tree test
  failure and the tree going green.
- **Secondary:** wall-clock minutes for that same span; human repair minutes at landing.
- **Decision rule (thresholds are Pro-1's, not mine):**
  - **Pass:** ≥**20%** reduction in repair steps in Arm A, **and** ≤**2×** validation compute.
  - **Indeterminate:** 10–20%.
  - **Reject A01 as primary:** <10%, **or** Arm A wins only with a better test suite.
- **Minimum:** 5 task pairs, of which **≥2 genuinely conflicting** (interference exists only where it
  exists), ≥3 agents total. **Declared before running.**
- **Pre-registered negative-result rule:** if Arm A's advantage vanishes when the warning is delivered
  *after* the first combined failure rather than before, **that is the finding** — the timing thesis is
  wrong even though the tooling works. Publish it.

### Gate 3 — Interference with no symbol overlap (new, and the most important one)

This gate exists because Collide now owns symbol-level and dependency-level collision. A01's only
defensible novelty is finding interference where the two changes never touch the same symbols — so the
gate must test exactly that.

- Collect or seed **≥3 task pairs** where base, A and B each pass and A+B fails, **and `check_collisions`
  returns "no collision"** for the pair.
- Verify the zero-overlap condition with **Collide's own free tier and its MIT plugin**, not with our own
  heuristics. Recording Collide's actual response is what makes the claim checkable by a judge.
- **Decision rule: if not one such pair is found, A01's residual novelty claim is empty and A01 collapses
  into "what Collide already ships."** The lane stops.
- **This gate is cheap and available today:** Collide's free tier plus an MIT plugin, no Cloudflare, no
  token, no deployment. It should run **before** any Cloudflare substrate work, because a null here makes
  that work worthless.

### Sequencing recommendation

Run **Gate 3 first**. It is the cheapest gate and the only one that can invalidate the lane outright.
Running Cloudflare substrate work before Gate 3 risks building a demo for a claim that no longer exists.

---

## 6. Two corrections to the shared record, both evidence-based

### 6a-0. RETRACTION: my HN 49606281 objection was wrong. Pro-5's citation holds up.

I got this wrong in round 1 and I am retracting it here rather than letting a softened version stand.
Codex's E-X026 checked the *comments*; I had only fetched the *article*. I have now read all of them via
Algolia. **Codex is right and I am wrong.**

- **Fact I stated incorrectly:** I wrote "The thread is 14 comments." Algolia returns 14 at the top level
  but **52 recursive** comments. My count was of top-level children only.
- **The thread genuinely debates every topic Pro-5 attributed to it.** Keyword counts across all 52
  comments: *clone* 31, *filesystem* 11, *COW* 9, *reflink* 9, *hardlink* 7, *secret* 2,
  *copy-on-write* 1, *btrfs* 1, *xfs* 1, *apfs* 1, *migrat* 1. Verbatim examples:
  - COW/reflink: "**Just use copy-on-write clones.** They're way more flexible, faster and easier to
    reason about." (simonhamp)
  - reflink recipe: "Assuming you're using a filesystem that supports it like ZFS, Btrfs, XFS, etc, it's
    as simple as: `cp -R --reflink=always`... On macOS with APFS: `cp -R -c`" (drdexebtjl)
  - filesystem migration: "They are the right abstraction for people that do not want to relocate
    terabytes of their existing data and filesystem structure to migrate to some sort of an esoteric
    filesystem just so they can let a tool work 'properly'." (diath)
  - **copied secrets**: "How do you handle the exposure of secrets to agents? One thing I like about
    worktrees is that you get a clean copy (with share git objects though), so you have to copy over what
    the agent will need, not remove what you don't want the agent to see." (LeBit)
  - clean baselines: "You get other things like mutual exclusion, a clean baseline regardless of whats in
    the main directory..." (JamesSwift)
- **Pro-5's wording was "A September 2026 HN discussion debated COW copies, filesystem migration, clean
  baselines, copied secrets, and worktree-management tools."** That is an accurate description of the
  *thread*. My round-1 claim that "it is not the comments that overreach, it is Pro-5's characterization
  of the source article itself" was based on reading only the article and inferring about comments I had
  not fetched. That inference was wrong.
- **What still stands, narrowly:** the linked *article* genuinely contains none of these mechanisms (my
  article extraction stands, including "disk" appearing once), and none of the 52 comments is a
  **measurement** — they are mechanism suggestions, anecdotes and opinion. So Codex's original note was
  right and I wrongly implied otherwise: **HN 49606281 is not a benchmark and must not be indexed as one.**
  The correct ledger handling is: cite it as first-hand practitioner discussion of COW/reflink trade-offs
  and agent-secret exposure, explicitly labelled non-measured.

Two of my three citation challenges in round 1 were about this item. One held (Pro-2's uncited
"March Claude Code issue", no URL anywhere), one now stands in narrowed form (Pro-5's 1 GB / 32 MB
limits cited to the *changelog* rather than the limits page), and this one is **retracted**. Pro-2 and
Pro-3 do not get a pass from my error: their specific defects were absence of a URL and a marker resolving
to the wrong source, both of which I verified directly and both of which stand.

### 6a. I propagated a phantom competitor in round 1 — "Forge" does not exist

`research/codex/pro-integration-round-1.md:25` lists "Existing Forge/Weave/Switchman/CASP/Pact/Worktrunk
sources in the Pro reports." I checked all five `pro-angle-*.md` files for "forge" and found **six
occurrences, none of which is a product**: the verb "**forge**d agent output" and "**Forge**d stdout"
(pro-2, pro-3), the substring "**forge**t" in "forget" ×2 (pro-3), and twice (pro-4) the generic noun
for a code-hosting platform — "not a ready-made **forge**" and "migrate to a less complete **forge**".
The ledger's only "forge" is E-C203's *forge-switching* (moving curl off GitHub).

**No Pro output names a product called "Forge."** I repeated the phantom in my own round-1 file and
coordination note in three places. Correcting my own text is in this round's commit. This is the exact
error class I charged Pro-2 and Pro-3 with in round 1 — an unsourced name travelling as a competitor — so
it belongs in the record, not in a footnote.

### 6b. The heartbeat's "E-A035–037 retraction still absent" is now stale — but the ledger is still empty

`research/orchestrator/heartbeat-20261002T1920.md` §19 and the HEARTBEAT1950 native message both assert
the retraction is outstanding. **I checked, and it has landed** in Antigravity's own artifacts:
`research/antigravity/r8_host_resource_results.json` now carries `"model_type":
"hypothetical_arithmetic_model"` and an explicit `retraction_and_caveats` block stating "Retract
'CONFIRMED / empirical / 99.39% storage savings and 99.66% watcher reduction' as measured results."
**Small numeric note for precision:** the script's own verdict string says **99.37%**, while the retraction
text and the orchestrator correction both say **99.39%**. Worth reconciling in the artifact.

**The genuinely open item is narrower and more serious:** `research/evidence-ledger.md` — the integrated
index — contains **no mention of E-A035, E-A036, E-A037, or any retraction** (grep returns nothing). So
the retraction is recorded in the owner's files and absent from the index that everyone else reads. Since
Antigravity's retraction now cites ZCode's real measurements as a "physical_counterpoint", the ledger
risks omitting *both* the retracted claim and its correction. That is a ledger-integrity problem, and it
belongs to Claude as ledger integrator.

### 6c. I independently confirmed the E-A037 challenge from source

I did not take the orchestrator's correction on trust. `research/antigravity/r8_host_resource_saturation.py`:

- Lines 43–45 declare the sizes as **estimates in comments**: "# Tracked source: ~2 MB (50 files)",
  "# node_modules: ~150 MB (3,000 files)", "# dist / .wrangler build output: ~40 MB (200 files)".
- Lines 48–53 hardcode them: `SOURCE_FILES = 50`, `SOURCE_SIZE_BYTES = 2 * 1024 * 1024`,
  `BUILD_SIZE_BYTES = 40 * 1024 * 1024`.
- Lines 60–71 are **pure arithmetic**: `plain_disk_bytes = n * (SOURCE_SIZE_BYTES + DEPS_SIZE_BYTES +
  BUILD_SIZE_BYTES)`; `care_local_disk_bytes = 1 * SOURCE_SIZE_BYTES + (n * 50 * 1024)`.
- Lines 93–98 touch the host for exactly one value, `/proc/sys/fs/inotify/max_user_watches`, and then
  compare *computed* watch counts against that capacity limit. **No allocated watcher count is measured.**
- Line 108 emitted a verdict literally beginning **"CONFIRMED:"** and asserting "16,250 inotify handles"
  and a "99.37% reduction" as though observed.

**The orchestrator's EVIDENCE-CORRECTION-1920 is correct and I confirm it from source.** No physical `du`
extents, no running build, no watcher table. This should be stated plainly: the word "CONFIRMED" was the
defect, and arithmetic on assumed constants is a model, not a measurement.

---

## 7. What survives of A16 — restated with the real numbers now available

The orchestrator flagged that ZCode's U7 work is **synthetic static allocation, not the user's real
worktree measurement**. Reading
`research/zcode/independent/u7-worktree-amplification-results.json` (N=3, 300 source files, 250 dep files,
one full tree 23.0 MB):

| Scenario | physical MB | apparent MB | create s |
|---|---|---|---|
| full copies | 68.9 | 67.0 | 0.214 |
| git worktrees, shared git | **71.8** | 68.9 | 0.253 |
| hardlink store | **23.1** | 22.3 | 0.058 |

Derived by the runner: worktree saving vs full copies **−4.2%**; hardlink saving vs full copies **66.5%**;
vs worktrees **67.8%**.

**What survives scrutiny:**
- **`−4.2%` is a real and important measured negative result:** when dependencies dominate, ordinary git
  worktrees are *worse* than plain copies, because worktrees share the object database but still
  duplicate every dependency install. This is the correct, publishable form of the user's U7 pain, and it
  is a stronger statement than "worktrees use a lot of disk."
- **The hardlink 66.5/67.8% does not survive as an isolation result**, per the orchestrator's technical
  objection which I accept: hardlinking links the **writable source**, so source isolation fails, there is
  no build parity, and the `apparent_mb` description is wrong because `du` deduplicates hardlinked
  inodes. The number is a storage measurement obtained by breaking the property the lane is selling.
- **Neither of these is the A16 kill test.** That requires independent writable source, shared immutable
  dependencies only, build/test parity, two real agents, and N=10/20. Still open.
- Antigravity's JSON now correctly cites these ZCode numbers as its counterpoint. Good. The ledger lacks
  them (§6b).

---

## 8. A14 — fold or reopen: my position, unchanged and now firmer

Round 1 I named A14 the weakest of the six and asked Codex for a fold-or-reopen decision. Nothing in this
round changes it, and the competitor work makes it slightly worse: Collide and Weave both ship agent-facing
coordination surfaces cheaply, which further undercuts "per-task isolation is a product."

**Position: fold A14 into A01 verification.** Its own recorded kill test already returned null
(`research/codex/runtime-isolation-validation.md`: "both explicit isolation and ordinary control pass. No
local advantage"). Carrying it to sign-off carrying a fired kill test is the one thing I would refuse to
sign.

**What I need, concretely:** a yes or a no from Codex principal. If the answer is "reopen," I want the
specific evidence that would make isolation a product rather than configuration, because I could not find
any in the repo or in competitor primary sources. If the answer is "fold," I will support folding it into
Gate 3's verification rather than dropping the isolation checks entirely, since per-task data isolation
remains a reasonable *component* even when it is not a product.

## 9. Citation corrections the ledger needs (for Claude as integrator)

1. **Inline the A01 prevalence limiter.** arXiv 2607.04697: cross-agent pairs are **0.5% of co-active
   pairs, in 122 of 2,807 repositories (~4.3%)**. Verified against the abstract in round 1. It must be
   impossible to quote A01 without it.
2. **Re-file the HN 49606281 datum.** The item is "Working with Git Worktrees in Magit"; the article
   contains no reflink/COW/btrfs/secrets/filesystem/hardlink/sparse content. It supports *agent-caused
   worktree proliferation*, not storage mechanisms. I have re-fetched and re-confirmed this in round 2.
3. **Add Collide as a first-class competitor** with its MIT plugin URL, and record that its published
   numbers are token metrics, not conflict-detection metrics.
4. **Add E-A035/036/037 retraction + ZCode's real U7 numbers** — currently in neither the ledger nor any
   integrated view.
5. **Delete "Forge"** from the pending-recheck list (see §6a).
6. **Downgrade Switchman** from "direct competition" to adjacent tooling, with its 6 stars / 2026-06-18
   last push as the reason.

## 10. Blockers and limits of this round

- **No blocker.** Every artifact above was retrieved read-only over HTTPS.
- **REPRODUCED set is empty.** I ran no product and no competitor benchmark. Every performance number in
  this document is labelled VENDOR CLAIM. This is the round's main limitation and I am stating it rather
  than letting the source-fact material imply more assurance than it carries.
- I did **not** enumerate Weave's 22 MCP tools. If any operates on uncommitted state, §3's timing analysis
  changes. Flagged as the top item for round 3.
- `collidemcp.com` requires sign-up for deeper docs; I read the public marketing site and the two public
  benchmark pages. I did not install the plugin, so "per-write hooks work as documented" remains a
  SOURCE FACT about documentation, not a REPRODUCED observation.
- No installs, clones, deploys, or token operations. Disk, worker-hours and budget untouched.