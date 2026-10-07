# Research

## What we set out to learn

The contest asks for a Git platform for coding agents on Cloudflare Workers and Artifacts, with several agents changing code at the same time. We wanted to know which problem in that space is common, painful and not yet solved, and whether our tool would make a measurable difference. We wrote 20 candidate approaches, scored each on originality, visible concurrency and demo clarity, and gave each a written rule for when to drop it. Then we tested the strongest ones with live coding agents and kept only what survived.

## The 20 approaches

The approaches fall into six groups: early conflict warnings and merged-state checks between agents, review aids that show intent and risk instead of raw diffs, storage and workspace savings, parallel attempts at one task, durable handoff between agents, and safety features such as path claims, quarantine, undo and receipts that a side effect ran once.

What happened to the ones that mattered:

- A01, the live integration radar that trial-merges every agent's latest work, became the core of Agent Branches. It lost its place as the main research claim after the fair pair test showed no difference between agents.
- A14, a preview URL per agent, was folded into A01 because an ordinary control did as well.
- A06, review cards, stays a hypothesis. The pain is documented but no run showed a benefit, and existing review products already cover most of it.
- A16, lazy workspaces that save disk, was parked. Its bar was 50 percent savings for two tasks and the best run reached 47.76 percent. The bar was not moved.
- A05, several attempts at one task, was parked after its one task ended in a tie.
- A10, durable handoff, was parked because cold restarts worked from plain Git.
- A18, multi-repo change sets, was parked because Pact can-i-deploy already covers it.
- The rest were never shortlisted, mostly for low originality or because an existing product already does them.

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
