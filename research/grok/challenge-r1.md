# Grok round-1 challenge

2026-10-02, Europe/Berlin. Author: grok-head, aplexer session `3b664830-1a4f-4f30-ba94-67828f32021c`. Owns only `research/grok/` and `coordination/grok.md`.

This is an independent challenge of the mission, the selection method, and the architecture. It is not a shortlist sign-off, not a lane assignment, and not evidence that any product is viable. Scores and file volume are not agreement.

User message 6 (experiment/USER-INSTRUCTIONS.md) sets the current goal: wide exploration, then zoom into the most interesting ideas. A US or Canada resident can be found later if something is worth entering. User message 7 is first-person pain: worktrees copy the workspace and disk fills quickly. Contest eligibility stays unresolved and is not a research stop. No submission is authorized.

## What I opened myself

Search discovery used `xai_search.py --tools web_search` once (4 tool calls, reported cost $0.0528). The model summary dated the Foremerge story as about ten days before 2026-10-02. Algolia says 2026-09-21. I cite only pages I opened. Raw search output stays in `.local/grok/` outside git.

| ID | Opened 2026-10-02 | What the page supports |
|---|---|---|
| E-G001 | [Git protocol](https://developers.cloudflare.com/artifacts/api/git-protocol/) (docs date Apr 25, 2026) | Clone/fetch speak protocol v1 and v2. Push is v1 `git-receive-pack` only. "Artifacts does not support v2 receive-pack." Optional v1 `filter` and `include-tag` are absent. Token scopes are `read` and `write` only. |
| E-G002 | [Best practices](https://developers.cloudflare.com/artifacts/concepts/best-practices/) (docs date Apr 25, 2026) | "Create one repo for each unit of autonomous work." "Do not use one shared repo as a queue for many autonomous agents." Tokens are repo-scoped read or write. Git notes are the documented place for prompts and model output. |
| E-G003 | [Event subscriptions](https://developers.cloudflare.com/artifacts/guides/event-subscriptions/) (docs date May 21, 2026) | `cf.artifacts.repo.pushed` fires with ref, before, after, and a commits array that can be truncated. The documented uses are post-push automation, including "trigger a review agent on every push". Nothing on the page rejects a push in flight. |
| E-G004 | [HN 49789356](https://news.ycombinator.com/item?id=49789356), naw103, created 2026-09-21T16:22:06Z | Foremerge author: parallel worktrees; the painful case is two plans that cannot both be true, for example one agent replacing a class while another extends it. Git sees that only when the same lines overlap. |
| E-G005 | [HN 47870607](https://news.ycombinator.com/item?id=47870607), ArielTM, created 2026-04-22T23:34:31Z | "The worktree part is the easy half." Two agents rename one type to different names in separate worktrees. Each checkout is locally coherent. The merge is not. |
| E-G006 | [HN 48534293](https://news.ycombinator.com/item?id=48534293), whh, created 2026-06-14T23:35:29Z | Separate worktrees still share one local Postgres. A migration on one branch changes the schema under the others. The author built Wtdb so each worktree gets its own database. |
| E-G007 | Synthetic fixture on this host, then removed | See G8. ext4 `/tmp`. `cp --reflink=always` returned "Operation not supported". |

Peer-fetched material I use only as their claims: Codex `research/codex/evidence.md` and `engineering-feasibility.md`; Claude `approach-seeds.md`, `workflows-competitors.md`, `maintainer-review-evidence.md`; Codex debate `research/debate/codex-round-1-challenge.md`. I did not re-open those URLs this round. Orchestrator `social-evidence.md` and the four ChatGPT Pro threads are pending or search-level. I have not read arXiv 2607.04697. Do not treat 33,596 pull requests as the merge-experiment denominator.

## G1. The mission is exploration with a later zoom, and the contest is a filter

The original brief optimizes for a judged Workers + Artifacts demo: originality and prototype quality 50%, concurrency 25%, ease of use 25%, deadline 2026-10-14 23:59 PDT, permissive license, human entry, no automated submission, no disparagement of a discernible product. Message 6 keeps ideas that are valuable beyond a 12-day contest MVP. Message 7 adds a user-specific storage pain that may never be a good contest entry.

Running both goals as one ranking will delete either the contest-shaped ideas or the user's actual pain, depending on who weights the spreadsheet. Keep two columns for every candidate: contest-shaped (Workers, Artifacts, visible concurrent agents, 5–10 minute demo, shippable by 14 Oct) and exploration-shaped (pain, existing workaround, what a later zoom would still want). A candidate may score in one column only.

Tradeoff: dual columns slow the shortlist and tempt people to "keep" everything. Cap the zoom set at six, and write an explicit disposition for every other survivor: merge, park with a named reopen test, or drop.

Kill test: a candidate with no named buyer and no falsification fixture is dropped even if its weighted score is high. A candidate that fails the contest column stays in the exploration notes when message 6 still applies. Reverse this split only if the user says to optimize for entry alone.

## G2. Selection is still a list of modules written ahead of the evidence

Claude's 22 seeds are labeled hypotheses and were written before the evidence lanes landed. That honesty is useful. Several seeds are one product described three times: an intent claim board, a live "I am editing X" channel, and an air-traffic dashboard share one buyer and one failure. A task board, a token proxy, and a reputation score do not become three approaches because they have three names.

The draft rubric gives novelty 20% and adoption 5%. The contest gives originality 50% and does not score adoption. The experiment cares whether an idea survives contact with worktrees, merge queues, and disk math. One weighted total hides that disagreement. Codex X1 already asks for a failure that plain worktrees cannot prevent. I agree with that gate. I do not agree that agreement is implied.

Required shape for anything that enters the six: one buyer, one job, one fixture, one existing product it must beat on that fixture. Two candidates that share a fixture are one product.

Tradeoff: this drops clever modules that would make a single demo feel complete. The demo can still show one product with one sharp failure, which matches the 5–10 minute limit better than six subsystems.

Kill test: if the only demonstrated failure is "two agents edited one checkout", the candidate loses to `git worktree` plus one integrator. Park it.

## G3. The architecture that fits the docs is a publication gate

From E-G001, E-G002, and E-G003, an Oct 14 design that needs any of the following is aimed at a platform Artifacts does not document:

- rejecting a push inside receive-pack
- path-scoped or branch-scoped tokens
- a binding method that merges, diffs, or creates commits
- using one shared repo as the agent queue
- treating a push event payload as the full commit

The boundary that does fit: each agent writes only to its own fork with a short-lived write token; the canonical repo's write token stays with a publisher Worker; a push event starts an idempotent job that fetches the exact before/after objects; a trusted runner builds a combined tree and runs checks owned by the baseline, so the candidate cannot pass by deleting tests; publication is a non-force fast-forward of the exact tested result, refused if the canonical head moved. Codex's feasibility note proposes this same boundary. I reached it from the three pages above. That is independent convergence, not a sign-off.

Agents can still fill their own fork with junk. The product, if it works, controls publication. It does not control editing.

Tradeoff: a gate is easier to demo and easier to dismiss as "CI on a fork". The contest originality score will punish a thin gate. The repair is a fixture with a specific failure (stale base, combined-tree break, or forged green receipt), not a second control plane.

Kill test: the day a spike requires a custom smart-HTTP proxy, path ACLs, or in-flight push rejection, stop that design. Also stop if two concurrent publishers can fast-forward the canonical ref without the stale-head check; that behavior has to be measured on a real Artifacts remote, which this round did not do.

## G4. The occupied neighborhood

E-G004 is the class-replaced-while-extended story, already attached to a product (Foremerge). E-G005 is the same architectural split without a product name: worktrees solved file stomping and left the decision conflict. E-G006 is runtime state, with Wtdb as an existing per-worktree database. Claude's competitor file, which I did not re-fetch, names Entire, git-ai, agent-trace, GitButler's pre-edit lock, Jujutsu snapshots, GitHub merge queue, and Cloudflare's own session-as-repo dogfood. Building those products again spends the originality half of the contest score.

The gaps still worth exploring, each unproven:

1. Combined-tree failure after each fork is green, with the baseline's tests as the authority.
2. Stale-base publication refusal when the canonical head moves after a passing receipt.
3. Per-attempt runtime and data identity (E-G006), including a receipt that names the commit the preview actually ran.
4. Local disk amplification (G8), which may be a workstation tool rather than a forge.

Tradeoff: focusing on these four ignores provenance and maintainer-shield stories that have more blog posts. Those stories already have Entire, git notes (E-G002), and project policies. More notes are not a product.

## G5. Bounded intent reapplication loses to merge-queue repair until a fixture says otherwise

Reply to Codex `C-R1-CONSULT-grok-head`. I object to adopting bounded intent reapplication as a differentiated product on the evidence we have.

The failure mode is real (E-G004, E-G005). The proposed behavior is: after the combined tree fails, keep the failed attempt, rerun a frozen task contract once on a fresh base in a new fork, and stop for a human if the path set or the intent changes. That is a retry policy. It is not deterministic replay. A second model call can widen scope, drop an acceptance detail, or pass by doing different work.

GitHub's merge queue already builds a temporary combined branch, runs required checks, and removes a failing group. The ordinary next step is an agent repair: give a coder the combined diff, the failing baseline tests, and the original path contract, and ask for one patch. Reapplication spends another full task run from the contract and throws away the partial work except as a link. Teams that already have a queue can script the repair arm without a new forge.

Falsification, same fixture for both arms, one attempt each:

- Setup: two agent branches, each green on its own tests; the merged tree fails a baseline test that neither author can edit; the task contract lists the allowed paths.
- Arm A, queue plus repair: one agent sees the red combined tree and the contract.
- Arm B, reapplication: one agent sees only the contract and the new base, in a fresh fork. The failed candidate is kept untouched.
- B is more viable only if tests pass, every changed path is inside the contract, and the changed-path set is smaller or equal to A's. A tie means B loses on cost and on novelty. Either arm fails if it edits outside the contract, deletes a baseline test, or needs a second repair call.
- Hidden-acceptance and flaky-test variants must fail closed. A green result with an unknown external dependency does not count.

Until that fixture exists, reapplication stays an exploration item inside the twenty. It must not become the spine that the other five "approaches" plug into. Codex X5 already limits the claim. I am pushing the adoption objection further: even the limited version is probably a prompt on top of a queue.

Tradeoff: the contest may still reward a visible "re-derive" moment more than a repair patch. That is a demo argument. It becomes a product argument only after Arm B wins the fixture. Reverse this objection if Arm B wins on one scripted conflict and one stale-base race without leaving the contract.

## G6. Heads, ZCode, and what counts as a round of work

Five engine names are not five lanes. Assign a head only after a candidate has a distinct buyer and a distinct kill test. Keep the sixth disposition in writing. Muse compares. I will not start a ZCode executor this round. Principal delegates already running stay theirs. `research/zcode/independent/` is not mine.

A round that only adds sources is inconclusive. Each later round of a lane should end in survive, fail, or inconclusive, plus the observation that would flip it. Two inconclusive note-rounds stall the lane.

Tradeoff: waiting for falsifiers serializes implementation. The alternative, spawning builders per seed now, multiplies worktrees on a host that is already at 96% disk (G8) and produces untested code.

## G7. Maintainer shield aims at the wrong buyer

Claude's maintainer file, as peer-fetched, includes curl's statement that a forge switch does not save them from AI bug-bounty slop (E-C203) and QEMU's policy of declining contributions believed to include AI content (E-C212). A quarantine forge for projects that refuse agent code has no buyer. The contest also forbids a submission that attacks a discernible product, so a "GitHub is drowning" demo is a rules problem as well as a weak story.

The buyer worth exploring is a team that already accepts agent diffs and is limited by review time. That claim still needs a first-hand thread I open myself; I am not using Claude's quotes as my verification.

Tradeoff: the honest buyer is smaller and less rhetorical. The workflow is a publication queue with a human approval, which is close to G3. If it cannot be distinguished from G3's fixture, merge them.

## G8. Worktree disk pain is first-person and unmeasured as a product

User message 7: worktrees have a copy of the entire workspace and space disappears quickly. That is the strongest pain statement in the project. It is qualitative. Repo size, file mix, and how agent tools populate new worktrees are unknown. I did not inspect or delete any existing user worktree.

Git linked worktrees share the object database. They do duplicate the checked-out files. They do not, by themselves, copy untracked dependencies. Agent bootstrap that reinstalls or copies `node_modules`, build outputs, or caches will dominate.

E-G007, disposable fixture under `/tmp/grok-wt-r1`, deleted afterward with a Python recursive remove. Host filesystem `ext4` (`findmnt` on `/tmp`). Volume at measurement time: 502,922,461,184 bytes, 453,441,794,048 used, 23,858,380,800 available, 96% full. Numbers are `du -s -B1` (allocated) and `du -s -b` (apparent):

| Tree | Allocated bytes | Apparent bytes |
|---|---:|---:|
| Tracked source, 200 files × 40 KiB | 8,196,096 | 8,192,000 |
| `.git` of that commit | 9,777,152 | 8,246,107 |
| Untracked fake `node_modules`, 120 files × 200 KiB | 24,584,192 | 24,576,000 |
| Three linked worktrees, no dependency copy | 24,612,864 | 24,576,156 |
| Same three after `cp -a` of `node_modules` into each | 98,365,440 | 98,304,156 |
| One later worktree with `node_modules` symlinked to the primary | 8,204,288 | 8,192,089 |

`cp -a --reflink=always` of the dependency directory failed immediately: `Operation not supported`. Copy-on-write clones are not available on this ext4 volume. The three clean worktrees cost about three checkouts of source (about 24.6 MB allocated) and did not triplicate `.git`. Adding a full dependency copy tripled about 24.6 MB of deps on top (98.4 − 24.6 ≈ 73.8 MB). A symlink avoided that multiplier and would be unsafe for any dependency tree an agent edits in place.

This fixture uses random bytes and a fake dependency tree. It does not measure the user's repositories. It does show that blaming "git worktree copies the whole repo" can mix three different piles: object database (shared), tracked checkout (duplicated), and untracked install/build (duplicated only if something copies it).

Artifacts forks (E-G002) reduce server-side copy cost for repo objects. They do not shrink the local checkout an agent still materializes, and E-G001's missing `filter` capability weakens a blobless-clone story until a spike proves partial fetch works some other way. A 1 GB per-repo cap, reported by Claude and not re-fetched by me, would also reject a plan that commits dependency trees into Artifacts.

Falsification, on a disposable copy, never on live worktrees:

- Attribute added bytes at 1, 5, and 10 workspaces to objects, tracked checkout, dependencies, build outputs, and agent-created copies. Record allocated and apparent size.
- If dependencies plus build outputs are the majority, compare a content-addressed or symlink install against full copies. The packaging arm wins, and a new forge loses, if allocated bytes drop by half or more and two workspaces still install, edit, and test without seeing each other's build outputs.
- If the tracked checkout itself is the majority, compare sparse checkout and a lazy/remote workspace against full worktrees on the same edit-and-test isolation check.
- Isolation failures (shared mutable `node_modules`, leaked build files, one workspace's migration touching another's database) fail the candidate even if the disk number looks good.
- Reverse the "packaging beats forge" lean if a real repo shows tracked checkout, not dependencies, as the majority, and sparse or remote materialization preserves concurrent edits and tests.

Tradeoff: prioritizing message 7 spends the next round on measurement that may conclude the fix is pnpm, Nix, or "stop copying node_modules", none of which need Cloudflare. That result is a successful exploration even when it kills a contest lane. Building an Artifacts-backed virtual filesystem before the byte split is known would spend the scarce disk and the calendar on an untested cause.

## Decisions

| ID | Decision | Alternatives | Outcome | What reverses it |
|---|---|---|---|---|
| D-G1 | Keep contest constraints and message 6/7 exploration in separate columns. | One rubric aimed only at winning the contest, or ignoring the contest entirely. | Both columns required before a zoom. No submission. | User instructs a single objective. |
| D-G2 | Publication gate is the only Artifacts-shaped control plane I will treat as feasible on current docs. | receive-pack proxy; path tokens; shared repo as queue. | Recorded as a hypothesis. No spike run. | A fetched API page documents the missing primitive, or a remote spike shows the gate cannot fast-forward safely. |
| D-G3 | Intent reapplication is not viable enough to lead. Queue plus one repair agent is the baseline it must beat. | Adopt Codex's bounded reapplication as the primary build now. | Objection sent to Codex. Stays inside the exploration list. | Arm B wins the G5 fixture. |
| D-G4 | No ZCode from me until a lane assignment names a distinct kill test. | Start an implementation delegate on storage or reapplication immediately. | No delegate launched. | Named assignment with ownership, worktree, and kill test. |
| D-G5 | Next grok work is the G8 byte split on a disposable copy, plus reading principal replies. | Another broad web survey. | Not started beyond the synthetic fixture above. | Measurement shows the cause, or the user ranks a different pain first. |

## Requests

Principals: reply to G1–G8 with accept, reject, or modify, and name the evidence you used. Do not treat this file as consensus. Claude integrates approaches only after that reply. Codex does not put reapplication into the six on my behalf.

I will read replies in a later round. Absence of a reply is not acceptance.
