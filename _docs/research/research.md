# Research

## What we set out to learn

The contest asks for a Git platform for coding agents on Cloudflare Workers and Artifacts, with several agents changing code at the same time. We wanted to know which problem in that space is common, painful and not yet solved, and whether our tool would make a measurable difference. We wrote 20 candidate approaches, scored each on originality, visible concurrency and demo clarity, and gave each a written rule for when to drop it. Then we tested the strongest ones with live coding agents and kept only what survived.

## The 20 directions

- A01 Live integration radar. Know within seconds when two live agents' work stops composing. Became the core of Agent Branches. It lost its place as the main research claim after the fair pair test showed no difference between agents.
- A02 Lease-bound claims. Stop two agents from doing overlapping work by checking claims when work lands. Never shortlisted. Foremerge already specifies this protocol.
- A03 Merged-state gate with intent reapplication. When a candidate breaks the combined state, regenerate it on the fresh base. Parked until a fixture shows it beats a merge queue.
- A04 Semantic contract sentinel. Catch breakages that merge cleanly but break a caller. Parked. Running the full tests on the merged state would catch most of the same cases.
- A05 Fork tournament. Run several attempts at one task, compare by behaviour and land one. Parked after its one task ended in a tie.
- A06 Change-story review queue. Review intent and risk instead of raw diffs. Stays a hypothesis. The pain is documented but no run showed a benefit, and existing review products cover most of it.
- A07 Maintainer inbound quarantine. Accept agent contributions without paying review cost for low-quality ones. Parked.
- A08 Independent reviewer panel on push. Catch bugs before humans review. Never shortlisted for low originality.
- A09 Exact-SHA verification receipts. Show what was tested, on which exact commit and by whom. Narrowed to exactly-once publication receipts. Parked until its kill test runs.
- A10 Durable handoff. The next agent resumes with the plan, the decisions and the exact base. Parked because cold restarts worked from plain Git.
- A11 Merge decision ledger. Answer why the code is the way it is and what was rejected. Never shortlisted.
- A12 Quarantine forks with capability tokens. Make destructive agent Git operations impossible on canonical history. Parked.
- A13 Session undo across forks. See and revert everything one agent session did. Parked with a reopen test.
- A14 Preview per agent. Each agent change gets its own live URL and its own data. Folded into A01 because an ordinary control did as well.
- A15 Push-triggered fast verification. Run only the affected tests on every push. Never shortlisted for low originality.
- A16 Lazy agent workspaces that save disk. Give each agent a workspace whose cost follows what it changes. Parked. The bar was 50 percent savings for two tasks and the best run reached 47.76 percent. The bar was not moved.
- A17 Fork-is-the-task board. No separate tracker, because claiming a task is forking. Never shortlisted. The pain evidence was weak.
- A18 Multi-repo change sets with recovery. One intent changes several repos and lands in dependency order. Parked because Pact can-i-deploy already covers it.
- A19 Maintenance swarm with batch landing. Let 10 to 50 agents each take one maintenance item and land compatible ones together. Parked and folded into A01 as a batch mode.
- A20 Earned autonomy per agent. Let low-risk changes from agents with a good record land automatically. Never shortlisted. The pain evidence was weak.

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
