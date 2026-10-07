# Research

## What we set out to learn

The contest asks for a Git platform for coding agents on Cloudflare Workers and Artifacts, with several agents changing code at the same time. We wanted to know which problem in that space is common, painful and not yet solved, and whether our tool would make a measurable difference. We wrote 20 candidate approaches, scored each on originality, visible concurrency and demo clarity, and gave each a written rule for when to drop it. Then we tested the strongest ones with live coding agents and kept only what survived.

## The 20 directions

### A01 Live integration radar

A lead or a solo developer runs 3 to 20 coding agents on one codebase. Each agent's work passes on its own, but the combination can break, and nobody finds out until the end. One operator said a third of their time went into helping agents merge.

Each agent pushes unfinished work to its own fork. Every push triggers a trial merge of all live heads and a fast test run, and the affected agents get a warning while they still work. Merge queues run the same check, but only at landing time. Collide already warns running agents about collisions, so early warning alone is not new.

The fair pair test ran two writer agents with and without a view of each other's unfinished work. Both arms passed on the first commit with zero repairs, so the warning changed nothing. It became the core of Agent Branches but lost its place as the main research claim.

### A02 Lease-bound claims

Teams already give agents file ownership rules so that two agents do not do the same work twice. Those rules live in prompts, and agents ignore them.

An agent claims paths with a lease that expires. When work lands, the platform rejects any change outside the agent's claim or inside another agent's live lease unless a human approves. Some reports said claims do not pay off and that scope is not knowable in advance.

It was never shortlisted. Foremerge already specifies this protocol, and CODEOWNERS and GitButler locks cover nearby ground.

### A03 Merged-state gate with intent reapplication

Agents produce branches that pass alone and break when combined. One reported workflow had 60 branches on a stale base. Some developers would rather rewrite than resolve.

The platform tests the candidate on the fresh base. On failure an agent reruns the original task on the new base in a new fork, and the platform checks the result for scope drift. A merge queue with an AI conflict fixer is the incumbent.

It was parked. A repair agent that patches the combined failure is cheaper, because rerunning a whole task to change one caller line costs far more. It reopens only if reapplication wins on at least 3 of 5 seeded conflicts at no more than three times the repair agent's token cost.

### A04 Semantic contract sentinel

Teams with shared internal APIs see changes that merge cleanly and still break a caller. Modularity alone does not prevent this.

When an agent changes an exported function, the platform extracts its contract from the signature, tests and call sites. It then runs the other agents' new call sites against it. Type checkers, CI and merge drivers like Weave overlap.

It was parked. A 10-fixture benchmark caught every seeded case, but the sentinel called the same test oracle a merge queue would run, so it showed no extra detection power. Running the full tests on the merged state catches the same cases.

### A05 Fork tournament

Developers already run best-of-N attempts in Cursor or Agent HQ and then compare them by hand. Comparing is slow and differences show up late.

One task spawns several forks. Each candidate gets tests and a preview, a judge compares behaviour, a human picks, and the winner lands while the losers stay as evidence. A tie or neither is a valid outcome.

Two agents attempted one task, a task registry validator. An independent coverage check found no winner, and the two attempts tied on every requirement. One task showed no selection advantage, so it was parked. It reopens on a preregistered task where comparison changes which candidate is accepted.

### A06 Change-story review queue

A reviewer at work faces dozens of agent changes a day. Faros AI reported pull request review time up 91 percent on teams that use AI heavily. Reviewers want to see intent and risk, not raw diffs.

Each change arrives as a short story with its intent, a risk tier and test evidence. Low-risk changes land with a receipt and high-risk ones wait for review. CodeRabbit, Copilot review, Graphite and Stage already cover much of this.

In the first run on one change, the reviewer approved at confidence 80 with and without the story card, and the card itself had a wrong timeout. A second run was only a calibration against a known outcome, and its two arms did not get the same raw access. It stays a hypothesis with no shown benefit.

### A07 Maintainer inbound quarantine

Open source maintainers who accept AI contributions pay the review cost for low-quality ones. curl reported about 20 percent of reports as slop and 5 percent as valid. Yet curl merged about 50 fixes from AI analyzers, so verified AI work is welcome.

Contributions go to a quarantine fork instead of a pull request. The platform requires a reproducer and a test that fails before the patch and passes after it. Only verified submissions reach a maintainer. GitHub pull request controls and Vouch gate by volume or identity, not by running code.

It was parked. The test needed 20 historical slop and valid reports, each with a patch, a reproducer and a maintainer verdict. None of the 20 candidates met that bar, so the filter test could not run.

### A08 Independent reviewer panel on push

Teams want AI review that is independent of the agent that wrote the code. Prompt injection through pull request text is a known risk.

Every push goes to several read-only reviewers, each with one lens such as security or performance. Disagreements escalate to a human.

It was never shortlisted. Copilot review, CodeRabbit and Greptile already do this, and AI review comments are mostly nits. It scored 2 of 5 on originality.

### A09 Exact-SHA verification receipts

Reviewers need to trust a claim that tests passed. They want to know what ran, on which merged commit, under which policy and on whose runner, not the agent's word.

A trusted runner signs a receipt with the source, base and merged commits, the policy and the results. Anyone can verify it. SLSA and GitHub attestations exist, so it was later narrowed to one job. A retry finds its operation id in the published commit and adopts the recorded outcome instead of publishing twice.

Our own tooling ran shell calls twice, and 14 outside reporters described duplicated agent side effects. One Claude Code issue showed git commit repeating 30 to 50 times or more. Plain Git already refuses a double publication, and the reports prove the category, not demand for this tool. It is parked until its kill test runs.

### A10 Durable handoff

Long tasks span sessions and agents. The next agent needs the plan, the decisions and the exact base, and a stale base or a lost reason wastes the restart.

Each task gets a context branch bound to its code fork. A handoff check verifies the base and context version before the next agent starts. Entire and native session resume are strong incumbents.

Two cold restarts worked from plain Git. An easy handoff recovered in 27 seconds with no wrong action. A hard one applied a 2104-byte unfinished patch onto a moved base and passed its tests 39 of 39 and 37 of 37 with no repair. It was parked until a task shows plain Git failing.

### A11 Merge decision ledger

Future maintainers and agents ask why the code is the way it is and what was rejected. Blame shows who, not why.

Every landing records the chosen candidate, the rejected ones, conflict resolutions and the reviewer's decision as notes. A why command walks from blame to the ledger. Entire, Git AI and Agent Trace overlap.

It was never shortlisted. Its value shows up late and not in a short demo, and it depends on A05 or A01 producing decisions first.

### A12 Quarantine forks with capability tokens

Anyone who gives agents write access to a valuable repository has seen force pushes, resets and writes to the wrong checkout. Prompt rules do not stop them.

Agents get a short-lived write token for their own fork only. A single publisher lands work after rechecking the head, and every token is audited. GitHub forks with branch protection give the same result.

It was parked because this is Cloudflare's own recommended practice and has low originality. The pattern became a shared architecture rule. A refinement called Task Passports stays parked until first-hand demand and its leak tests pass.

### A13 Session undo across forks

After an agent run goes wrong, the operator wants to see and revert everything that session did across forks and landed commits. Locally people use the jj operation log for this.

The platform is the only publisher, so it records every ref change by agent identity. An undo computes reverts for one session and shows which later work depends on it.

It was parked. It could not show a dependency-aware undo that keeps later work from other agents intact. It reopens if a spike shows that.

### A14 Preview per agent

Web developers running parallel agents must check running behaviour, and agents collide on ports, databases and secrets. Checking by hand is a top complaint.

Each push builds a preview with its own URL and its own data, and the agent runs checks against it. Cloudflare Workers Previews already isolate resources per preview.

A local fixture reproduced the hazard. With a shared database one task read the other task's write. Separate databases fixed it, but an ordinary separate-resource setup did as well. With no advantage it was folded into A01 as runtime verification.

### A15 Push-triggered fast verification

Agents need feedback in seconds, but CI runs in batches and agents miss red builds.

Each push triggers test impact analysis, and a runner executes only the affected tests and reports to the agent. Nx, Bazel and Launchable already do this.

It was never shortlisted for low originality. Test impact analysis is also hard to get right.

### A16 Lazy agent workspaces that save disk

Developers running many agents locally watch worktrees eat their disk. This was the founder's own pain.

Each agent gets a fork on the server and a local workspace with a sparse checkout, a shared dependency store and private build outputs. Plain worktrees, pnpm, ArtifactFS and reflinks are the baselines.

The bar was 50 percent savings for two concurrent tasks. Earlier runs reached 36.05 to 48.17 percent. The corrected run reached 47.76 percent, while an ordinary clone reached 47.38. It was parked and the bar was not moved. The advice that remains is cleanup and shared dependency stores.

### A17 Fork-is-the-task board

Small teams dispatching agent tasks keep a separate tracker. Here claiming a task is forking, the fork state is the status and landing is done.

Tasks are repositories with metadata, and a board reads Artifacts events. Vibe Kanban, Conductor and Linear with agents fill this space.

It was never shortlisted. The pain evidence was weak and the idea was derivative.

### A18 Multi-repo change sets with recovery

Platform teams change an API across many services. Worktrees stop at the repository edge, so the remote becomes the only integration point.

One intent fans out to forks of several repositories. The platform tests consumers against the producer, lands in dependency order and recovers from a failure partway through.

A demand scout found that a configured Pact can-i-deploy stack with merge queue checks already rejects a bad version combination. It also documents a clean resume after interruption, though nobody reproduced that here. It was parked.

### A19 Maintenance swarm with batch landing

Teams have backlogs of upgrades, lint fixes and migrations. Many small pull requests cost CI time and clog the merge queue.

The platform splits a migration into items, gives 10 to 50 agents one item each, trial-merges batches and lands compatible ones together. Renovate, Dependabot and merge queues with batching are the incumbents.

It shares its machinery with A01, so it was parked and folded into A01 as a batch mode. It returns only if it beats a serial merge queue plus Renovate on wall time or CI runs by at least 40 percent.

### A20 Earned autonomy per agent

Engineering managers must decide how much to trust each agent setup. Copilot approvals already count toward required approvals, which shows demand.

The platform tracks land, revert and defect rates per agent configuration and lets low-risk changes from trusted setups land on their own. It needs a long history to mean anything and can be gamed.

It was never shortlisted. The pain evidence was weak.

## Experiments that changed our mind

The A01 fair pair ran two writer agents on complementary tasks in two arms. In one arm each agent could see the other's unfinished work. In the other it met that work only at completion. In both arms every first commit already passed the task check and the combined check. Seeing the peer's work changed nothing. An independent replay agreed. Outside studies say the same thing: clashes between agents happen but are rare, about 0.5 percent of co-active pull request pairs in one study.

A disjoint-files test gave two agents separate tasks with a hidden shared contract. Both rounds passed. The test could catch a broken change, so the agents avoided the bug on their own. Both briefs hinted at the behaviour that mattered, so this shows a capability and not a rate.

Storage on the founder's machine showed the pain is accumulation. 472 linked worktrees took 111.7 GiB, and 264 of them sat on commits already merged into main. Dependency and build folders were 62.1 percent of the space. Plain pnpm already saved about 50 percent across two trees, and an ordinary clone arm reached 47.38 percent against our 47.76. Cleanup beats a new storage layer.

For a single agent, plain Git won. Both paths produced the same tree. Plain worktrees took 0.200 seconds and 7 commands. Agent Branches took 1.143 seconds and 15 commands. We recommend plain Git for single-agent work.

## Demand and competitors

Pain is well documented in forums, issue trackers and maintainer posts, but prevalence is not. Combined breakage is structural but rare, review burden has the most volume and the most existing remedies, and worktree disk use is common. Merge queues, merge trains and pull request merge refs already run the same merge-then-test check. Our difference is timing, and pairwise checks grow fast, 190 pairs at 20 agents. Collide already warns agents early over MCP. CodeRabbit, Copilot review and Greptile cover review. pnpm covers storage. Most production agents run in disposable containers and hand back a patch, which narrows the market for a remote branch server. Willingness to pay is unproven, and one hosted orchestrator, Terragon, shut down in February 2026.

## Architecture rules we keep

- One Artifacts fork per task. An agent's token can write only its own fork.
- One publisher lands work. It rechecks the exact head, never force-pushes and rejects stale results.
- Platform events arrive after the push and may repeat or reorder. Deduplicate them and treat them as observations, never as a guard.
- Merges and tests run in a separate runner, because the Artifacts binding has no merge, diff or ref-write call.
- An agent never approves changes to its own tests.
- A receipt names the base, candidate and merged commits, the policy and the runner. It attests a run, not correctness.
- An unchecked or inconclusive state is shown as unknown, never as safe.
- Every change is idempotent, with stable operation ids, a check before acting and a check of the outcome.
- Design within the platform limits: 1 GB per repository and 32 MB per file.

## Lessons

- Check that the harness can fail before trusting a pass.
- Give both arms of a comparison the same information.
- Keep the brief from leaking the answer.
- Call a model a model, and use one denominator.
- Do not move the bar after seeing the result.
- Save the evidence before a rerun.
- Withdraw an overclaim in the open.
- Count the disk and memory a run will need before starting it.
- Agreement is an explicit act. Silence is not consent.
- A test that passes whatever the code does proves nothing.

The raw evidence is at the git tag research-archive-20261007.
