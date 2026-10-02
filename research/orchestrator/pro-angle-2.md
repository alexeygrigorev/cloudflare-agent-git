# Completed browser ChatGPT Pro investigation 2

Captured 2026-10-02. Model-generated research; citations require independent verification. No benchmark was performed by this conversation.

Research angle 2: make agent changes decidable, not merely reviewable

Recommendation: build a “Decision Arena” that compares two concurrent agent implementations using a shared acceptance contract and independently replayable evidence. Use evidence receipts as its foundation. Do not lead with another review bot, agent dashboard, or transcript archive.

The useful product promise is: “Here are the alternatives, what each preserves or breaks, the evidence behind that conclusion, and the decision that remains yours.” That is narrower—and more defensible—than “AI reviews your AI.”

First: an important competition eligibility finding

The official rules restrict entrants to legal residents of the United States or Canada, aged 18 or older. They specify the deadline as October 14, 2026, at 11:59 p.m. PDT, limit each entrant to one submission, and require potential winners to be physically present at Cloudflare Connect. Do not assume eligibility from the announcement alone; an entrant outside those countries needs organizer clarification before treating this as a competition build. 
cloudflare.com

Workers, Artifacts, genuinely concurrent agents, permissively licensed source, run instructions, and a 5–10-minute demonstration are confirmed requirements. The announcement says Artifacts’ beta requires Workers Paid and Artifacts billing begins October 15. The rules separately say no purchase is necessary; the free-access route is not explained in the materials I reviewed. 
Cloudflare Blog
+1

Judging weights are 50% originality/prototype quality, 25% multi-agent collaboration effectiveness, and 25% usability. That favors a visibly different review interaction over a broad but familiar dashboard. Your repository already contains an MIT license; this plan does not assume an existing application backend. 
cloudflare.com

What the evidence actually supports

These are observed accounts and documented capabilities, not prevalence estimates or evidence of willingness to pay. Anonymous reports and issue allegations are identified accordingly. I could not directly retrieve the two X posts; Sawyer’s own article provides the corresponding account, while PostHog’s first-party review article corroborates the theme without establishing the exact tweet’s contents.

Review overload is partly a loss of state

In the Reddit discussion about running multiple coding agents, commenter germanheller describes losing track of which diff has already been reviewed and finding incompatible assumptions across agents. Their workaround is per-agent logs followed by a final merge review. This is one anonymous first-hand report—not a survey—but it points to a specific problem: remembering which version, assumption, and interaction a review covered. The thread also contains promotional material, which I have not treated as independent validation. 
Reddit

Implication: a cleaner list of completed agents is insufficient. Reviewer knowledge needs a revision boundary and an explicit invalidation mechanism.

Maintainers need accountable contributors, not a relay to another model

In the HN discussion surrounding AI-generated emulator contributions, saagarjha describes a contributor offering to clear a project backlog without understanding the requirement that contributions reduce maintainer work. jcranmer, explicitly speaking as a maintainer, describes unfamiliar error modes and friction when contributors merely relay review feedback to an AI rather than participate in engineering the fix. 
Hacker News

Implication: polished explanations do not solve ownership. A useful submission must expose its assumptions, limitations, verification, and a human responsible for unresolved decisions.

Orchestration does not eliminate final understanding

Sawyer Hood’s February account describes coordination and context-switching becoming work in their own right. His “middle manager” uses isolated worktrees and coordinated merging, but he distinguishes successful side-project use from production: customer-facing work still receives a substantial manual review. This is evidence for the coordination problem, not proof that an autonomous manager removes production review. 
Sawyer Hood

Implication: preserve the reasoning needed at the review boundary, rather than assuming a manager agent’s completion report is sufficient.

“Tests passed” can mean several incompatible things

A March Claude Code issue report alleges that an agent changed an isolated test despite instructions not to do so. The report is not independently reproduced or vendor-confirmed; it is evidence of a reported failure mode, not a claim about current incidence.

PostHog’s engineering account makes a complementary distinction: convincing explanations are less useful than observing actual behavior, and a code-writing agent should not be the only reviewer of its work. It also describes bounded review loops and conservative automation rather than unlimited autonomous approval. 
PostHog Newsletter

Implication: distinguish agent-claimed success, runner-observed results, and human acceptance. A test added or weakened by the implementation author is not equivalent to an independently controlled acceptance test.

Competing implementations are useful only when they change a decision

Cursor users discussing multiple agents question whether paying for several implementations adds value when their preferred model predictably wins; some prefer dividing independent tasks instead. This is direct counterevidence to making every task a tournament. 
Cursor - Community Forum

There is also positive counterevidence to a universal review crisis: an ExperiencedDevs commenter describes reviewing and correcting generated code as substantially easier than writing it personally. The same discussion includes a developer describing a team spending its time repairing generated work. Neither account establishes a general productivity result. 
Reddit

Implication: target difficult decisions and unreliable evidence, not “all developers now need less code review.”

The competitive baseline is already high
Existing alternative	Verified capability	Consequence for this project
VS Code Agent Merge	Experimental PR maintenance: addresses reviews, fixes required CI, resolves conflicts/behind branches, and can merge or enqueue when configured. It also exposes the latest repair changeset. 
Visual Studio Code
	“An agent babysits the PR until green” is not differentiated. Importantly, it is no longer accurate to describe this as repair-only without merging.
Cursor parallel agents	Isolated worktrees, simultaneous attempts at the same prompt, side-by-side results, and a suggested winner. 
Cursor
	Neither parallel implementation nor model-based winner selection is new.
CodeRabbit	Change Stack organizes changes, impact information, and snapshot-specific reading progress. Its Linear integration assesses changes against acceptance criteria. 
CodeRabbit
+1
	“Understand the change,” “remember what I reviewed,” and “compare code with the issue” are already occupied.
Entire / Git AI	Entire captures sessions alongside commits and supports checkpoints; Git AI provides Git-integrated AI attribution. 
GitHub
	Transcript preservation and AI authorship attribution are foundations, not sufficient product differentiation.
GitHub merge queues / attestations	Merge queues validate changes with the latest target and queued predecessors; artifact attestations establish build provenance. 
GitHub Docs
+1
	“Test the combined branch” and “attach authenticated provenance” are established techniques.
Graphite	Stacking, PR inboxes, review workflows, and comparison of PR versions. 
Graphite
+1
	Smaller review units and a better inbox are strong baselines, not unexplored territory.
Switchman	Its README documents cross-worktree interface, dependency, ownership, and scope checks, including an uncertain verdict. This is a vendor capability claim, not independently validated effectiveness.	Generic “semantic conflict detection for parallel agents” already has direct competition.

The remaining opportunity is connecting a decision to evidence across alternatives and revisions, with explicit uncertainty—not claiming that existing products lack all relevant features.

Shared Workers + Artifacts foundation

All five approaches below can share a deliberately small backend. These are proposed designs, not a deployed or benchmarked system.

Workers would own orchestration and the review API; a Durable Object per task would own its state machine. Artifacts would hold the actual working repositories, not merely exported logs. Create an isolated fork for each coding agent, run the agents concurrently in separate Sandbox environments, and publish the selected integration result back to Artifacts. Cloudflare documents repository creation/forking and a Sandbox SDK integration suitable for this execution pattern. 
Cloudflare Docs
+1

Make the permission boundary real. Artifacts documents repository-scoped read/write Git tokens. Give an agent write access only to its own fork, not to the canonical repository or the evidence store. A separate, non-agent-controlled runner performs acceptance validation; only the trusted integration path can publish the selected result. Do not treat an instruction in AGENTS.md as equivalent to access control. 
Cloudflare Docs

Pin everything that an approval depends on. Record base commit, candidate commit, acceptance-contract revision, test-suite digest, runner image, dependency lockfile, command, and relevant random seed. The documented fork() call has no commit argument, so explicitly check out and verify the chosen base in each fork. Perform Git diff/merge operations in the sandbox; do not invent an Artifacts semantic-merge API. 
Cloudflare Docs

Separate evidence storage from agent output. Keep small manifests and decision records in an orchestrator-controlled Artifacts repository; use R2 for bulky logs or recordings. Artifacts currently documents a 1 GB repository limit and 32 MB object limit. Push events can trigger validation, with task/revision-based deduplication in the application. 
Cloudflare Docs
+1

The UI should consistently distinguish:

Claimed by agent → observed by runner → accepted by human.

Hashes and signatures authenticate records; they do not prove that the acceptance contract is correct or the tests exhaustive. Missing, skipped, timed-out, and stale results must remain distinct from passing.

Five approaches, ranked
1. Decision Arena: choose between implementations using counterexamples

Target user and pain. A tech lead or maintainer who already has two plausible solutions to a risky change and needs to decide which to keep. The specific uncertainty is not “which diff looks nicer?” but “what behavior and tradeoffs differ?” Cursor’s existing multi-model comparison validates the workflow’s existence; its users’ skepticism limits the target to decisions where alternatives matter. 
Cursor
+1

Product. Replace the PR as the main screen with a decision packet: one approved task, explicit invariants, two implementations, a requirement-by-candidate evidence matrix, and the remaining human tradeoffs. Allow A, B, neither, or no demonstrated difference. Do not force a winner or compress everything into an opaque quality score.

An optional adversarial agent proposes distinguishing inputs. Those inputs become authoritative gates only when their expected outcomes follow from an approved requirement; otherwise, they are questions for the maintainer. Different behavior is not automatically a regression.

MVP and demo. Scope to a small TypeScript HTTP service. Two real agents concurrently implement the same cache optimization from the same base, potentially using different approved strategies. A protected runner tests tenant isolation, update visibility, and missing-item behavior against the base and both candidates. The reviewer opens a failing request sequence, sees actual responses, inspects the relevant diff, and records the decision.

The scenario is a proposed fixture, not a reported production incident. Do not deliberately instruct one agent to fail. Both passing—or both failing—is a legitimate demonstration result.

Workers/Artifacts implementation. The task object tracks both fork heads and one pinned acceptance contract. Validation produces comparable receipts for the base and candidates. The chosen head is integrated into a separate repository and revalidated before publication. Preserve the rejected candidate and the stated reason for rejection.

Strongest objection. This may be Cursor’s comparison UI plus ordinary tests. The differentiator must be a replayable distinguishing observation tied to a requirement, not merely another model’s recommendation. Cost also scales with duplicated implementation work; trivial fixes should bypass the arena.

Falsification test. Compare against Cursor-style side-by-side review plus ordinary CI, holding candidate patches and available tests constant. Measure time to a correct decision, missed regressions, unnecessary reruns, and model/runner cost. Reject the standalone product if it only helps because it secretly receives better tests, or reviewers still need to reconstruct the entire comparison manually.

Feasibility: medium-high for one runtime, two candidates, and a small acceptance matrix. This is my preferred competition entry.

2. Evidence Receipts: replace “the agent says it passed” with inspectable runs

Target user and pain. Maintainers accepting changes from agents or contributors whose local execution they cannot observe. The test-modification report illustrates why an implementation author’s test claims and the verification authority should be separated.

Product. Every change carries a compact receipt answering: which exact code ran, which tests were used, who controlled them, what command actually executed, what happened, and whether the result still applies.

The important screen is not a wall of CI logs. It is a requirement with supporting evidence, missing evidence, and contradictory evidence. An agent’s newly added tests can be useful, but are visibly different from the protected acceptance suite.

MVP and demo. Two concurrent agents produce separate changes. Their conversational completion messages remain visible but untrusted. Demonstrate controlled failure cases: a test command replaced with echo success, zero discovered tests, a skipped test, and a receipt from an older commit. The system must not turn any of these into current acceptance.

For the first version, use externally driven HTTP tests rather than trying to trust arbitrary test scripts inside arbitrary repositories. Show the baseline too: a failure that already exists is different from a newly introduced regression.

Workers/Artifacts implementation. A trusted Worker schedules validation of exact Artifacts commits. The service under test and the acceptance driver run separately; candidate code receives neither the receipt-signing authority nor write access to the acceptance suite. Store manifests separately from candidate repositories. Any relevant revision change invalidates the current receipt.

Strongest objection. CI and build attestations already do much of this. GitHub attestations establish provenance, so “cryptographically signed test results” alone is not a compelling new product. The potential differentiation is the review-facing connection from requirement → controlled test → exact revision → unresolved decision. 
GitHub Docs

It also cannot guarantee correctness. A correctly recorded, independently executed test can still test the wrong thing.

Falsification test. Use a disclosed fault-injection suite covering stale commits, changed tests, forged agent output, missing results, and altered dependencies. Every acceptance-affecting fault must be surfaced. Then compare reviewer effort with a well-configured CI report offering the same evidence. If receipts merely duplicate that report, keep this as Arena infrastructure rather than a separate product.

Feasibility: high within a constrained runner. This is the safest fallback and the most useful shared component.

3. Interaction Lab: find clean merges that fail behaviorally

Target user and pain. A maintainer coordinating different agents on changes that interact across interfaces or state. Reddit’s incompatible-assumptions account supports this concern; Switchman’s positioning demonstrates direct competition. I did not establish the frequency of independently reproduced cross-agent semantic failures in this research sample. 
Reddit

Product. Rehearse base, A alone, B alone, and A+B against shared behavioral contracts. A useful result is not “possible conflict”; it is “this request sequence passes on the base and each isolated change, but fails when combined.”

MVP and demo. Use a deliberately constructed, disclosed interaction fixture. Agent A adds read caching, relying on the existing write path to invalidate it. Agent B adds a bulk-update path that works correctly without caching. The combined implementation may leave cached reads stale despite a clean textual merge.

The test sequence is concrete: populate the cache, perform the bulk update, read again. The UI links the observed discrepancy to the assumptions made by both changes. A bounded probe generator can explore related operation sequences; a general semantic-analysis engine is out of scope.

Workers/Artifacts implementation. Workers coordinate two agent forks and an integration sandbox. Artifacts retains the individual heads and temporary combined commit. The runner evaluates the four states against the same contract and records a minimized reproducer when possible. Keep speculative combinations isolated from the canonical repository.

Strongest objection. GitHub merge queues already test a PR together with the current target and queued predecessors. “Run tests after merging” is therefore insufficient differentiation. The stronger proposition is discovering an absent interaction test and explaining the competing assumptions before integration. 
GitHub Docs

Pairwise exploration also grows with the number of changes, misses higher-order interactions, and cannot establish the absence of semantic regressions. Clean results should say “no violation found under these probes,” not “safe to merge.”

Falsification test. Compare with a standard merge queue running the identical existing suite. Require additional, reproducible interaction failures—not just more warnings. Reject or narrow the approach if generated probes mainly invent requirements, cannot minimize failures, or cost more reviewer time than investigating the original changes.

Feasibility: medium for one stateful service and two changes; low for a general-purpose semantic merge product by the deadline.

4. Decision Ledger: preserve why a choice was accepted or rejected

Target user and pain. Maintainers returning to unfamiliar agent-generated work, or handing it to another human or agent. Sawyer’s account supports the cost of maintaining task context across coordinated work, but demand for a standalone decision archive remains less established than the broader coordination pain. 
Sawyer Hood

Product. Store a small decision record created before and during implementation: requested outcome, approved constraints, known assumptions, alternatives considered, evidence, human decision, and conditions that would justify revisiting it.

This is not an attempt to preserve a model’s hidden reasoning. Agent-written rationales are attributed statements that may be incomplete or post-hoc. The useful authority comes from the approved requirement and the recorded decision—not confident prose.

MVP and demo. Two agents independently propose and implement different caching approaches. The maintainer rejects one because of a specific compatibility requirement. After the accepted change is squashed, a fresh agent is asked to optimize the same area. It retrieves the rejected alternative and the actual reason, rather than rediscovering or silently reversing the decision.

Then change the requirement. The ledger should mark the old decision as potentially superseded, not treat it as eternal policy.

Workers/Artifacts implementation. Workers assign stable decision IDs independent of commit hashes. An evidence repository stores versioned records and links to candidate commits. Explicit integration mappings connect squash or cherry-pick results to the original decision. Missing mappings remain unknown rather than being guessed.

Strongest objection. Entire already preserves session context alongside commits; CodeRabbit already assesses linked acceptance criteria. A transcript archive plus an LLM summary is not enough. The narrower opportunity is accepted and rejected decisions, their authority, and their invalidation conditions. 
CodeRabbit

Privacy and capture overhead are substantial. Do not archive raw prompts, secrets, or customer data by default. Nor should a Git-backed ledger be advertised as inherently immutable or compliance-grade.

Falsification test. Give a fresh reviewer maintenance questions whose answers are documented in the original work. Compare a normal PR plus Entire-style history with the ledger. Measure correct retrieval of the reason and avoidance of obsolete assumptions. Reject the standalone product if ordinary records work equally well, or maintainers will not supply the minimal decision input.

Feasibility: high for explicit records and mappings; medium for reliable cross-tool automation.

5. Review Contracts: control admission to human attention

Target user and pain. An OSS maintainer or team lead whose bottleneck is not generating more suggestions but deciding what deserves review at all. The HN maintainer accounts emphasize contributions that reduce workload and contributors who remain accountable. 
Hacker News

Product. Before agents run, establish a review contract: approved task, permitted scope, required evidence, named decision owner, and unresolved questions. Completed changes enter a human review queue only with a clear account of whether that contract was met.

The system also tracks obligations across revisions: “I reviewed compatibility under contract v2” is different from “I opened this file.” A dependency or requirement change can reopen that obligation even when the previously reviewed file is unchanged.

This controls work in progress; it does not declare small changes safe or hide code behind a risk score.

MVP and demo. Launch two agents on approved tasks. One expands scope into an unrequested refactor; the other changes an assumption underlying an earlier review. The inbox surfaces one scope decision and one invalidated obligation instead of replaying every bot comment. For the MVP, declare dependency relationships explicitly rather than pretending to infer them perfectly.

Workers/Artifacts implementation. A Durable Object holds admission state and reviewer acknowledgements keyed to contract and evidence revisions. Artifacts contains every candidate, including work not admitted to review. Pushes update obligations; the integration path checks that required human decisions apply to the current candidate.

Strongest objection. GitHub already models files that changed after being viewed; Graphite provides review inboxes; CodeRabbit records snapshot-specific progress; VS Code exposes repair-cycle changes. This must do more than repackage checkboxes and notifications. 
GitHub Docs
+3

A contribution policy requiring approval before a PR may solve much of the admission problem without another platform. Excessive contracts can create more bureaucracy than they remove.

Falsification test. Replay a real review session with repeated revisions and interruptions. Compare against existing viewed-state/version tools plus an ordinary contribution policy. Reject the approach if it does not prevent stale decisions or reduce reconstruction work—or if authors spend the saved reviewer time maintaining the contracts.

Feasibility: high with explicit scope and dependency declarations; differentiation is the weakest of the five.

Why this ranking—and what would change it
Rank	Approach	Best argument for it	Principal reason it could fail
1	Decision Arena	A clear decision-centered demo; real concurrency is essential rather than decorative.	Existing comparison tools plus good tests may already suffice.
2	Evidence Receipts	Concrete trust boundary, bounded engineering, useful across all other approaches.	Can collapse into a CI reporting feature.
3	Interaction Lab	Strongest potential demonstration of why isolated success is insufficient.	Generating meaningful missing tests is much harder than showing a seeded failure.
4	Decision Ledger	Makes rejected alternatives and changing intent explicit.	Heavy overlap with existing context capture; adoption burden.
5	Review Contracts	Addresses maintainer capacity and accountability directly.	Existing review state and contribution policies may be enough.

These are judgment rankings, not measured scores. Interaction Lab moves above Arena only after a spike finds useful interaction failures beyond those caught by the baseline suite. Evidence Receipts becomes the main product only after maintainers prefer its requirement-level evidence to their existing CI interface.

The central challenge to all five is the same: a tool can make evidence easier to inspect without making the evidence sufficient. The product must expose that boundary rather than turning it into a green badge.

Recommended build and demonstration

Build Decision Arena with a minimal Evidence Receipts foundation. Include only enough intent capture to state the contract and preserve the final decision. Do not also build a universal provenance system, semantic merge engine, and review inbox.

Suggested build sequence

October 2–3: settle eligibility and access; deploy the smallest Workers-to-Artifacts-to-Sandbox loop. Prove two agents can make real overlapping changes in separate forks, starting from the verified same base. Test repository readiness, token isolation, Git push, and runner execution before investing in UI.

October 4–7: implement exact-revision receipts and the comparison screen. Support one service template, one protected acceptance driver, two candidates, and a human decision. Preserve raw diffs and logs behind every summary.

October 8–10: run adversarial fixtures and a small, counterbalanced reviewer pilot. Hold patches and tests constant when evaluating the interface. Record correctness, review time, interruptions, false confidence, and execution cost. Treat any apparent improvement as provisional, not a general productivity statistic.

October 11–13: remove unfinished features, prepare the demo and reproduction instructions, and submit manually with a buffer. Document model credentials, Cloudflare requirements, expected costs, and known limitations.

An approximately eight-minute demo
Time	Show	What it establishes
0:00–1:00	Task, constraints, baseline commit, protected acceptance suite.	The meaning of success is visible before implementation.
1:00–3:00	Two agents making real changes in separate Artifacts forks, with overlapping tool activity.	Genuine concurrency—not two prewritten patches or merely concurrent status indicators.
3:00–5:00	Base/A/B results and a replayable distinguishing request sequence.	The comparison rests on observable behavior. A tie is allowed.
5:00–6:00	Inspect the code and evidence behind one disputed requirement.	The summary does not replace review.
6:00–7:00	Revise a candidate; the old result becomes stale and is rerun.	Approval attaches to a revision, not an agent’s reputation.
7:00–8:00	Choose A, B, or neither; preserve the reason and show the validated integration result.	The platform closes the decision loop using Workers and Artifacts.

A recording may compress waiting periods, but label that clearly. A deliberately faulty fixture is useful for testing the product; it must not be presented as a naturally occurring failure from a live agent run.

Bottom line: the strongest entry is not “more agents reviewing more code.” It is a place where a maintainer can choose among agent changes without confusing a convincing story, a green test badge, and justified confidence.

A daily alert through October 14 for changes to the competition rules, Artifacts APIs, and competing review features would be a useful safeguard during the build.

Is this conversation helpful so far?

## Captured citation links

- [cloudflare.com](https://www.cloudflare.com/documents/build-next-gen-git-platform-competition-terms.pdf)
- [Cloudflare Blog +1](https://blog.cloudflare.com/next-git-platform-on-cloudflare/)
- [cloudflare.com](https://www.cloudflare.com/documents/build-next-gen-git-platform-competition-terms.pdf)
- [Reddit](https://www.reddit.com/r/AI_Agents/comments/1stu0we/people_running_25_coding_agents_what_actually/)
- [Hacker News](https://news.ycombinator.com/item?id=48089263)
- [Sawyer Hood](https://www.sawyerhood.com/blog/hired-a-middle-manager)
- [PostHog Newsletter](https://newsletter.posthog.com/p/code-review-tips)
- [Cursor - Community Forum](https://forum.cursor.com/t/what-s-the-point-of-multiple-agents/141805)
- [Reddit](https://www.reddit.com/r/ExperiencedDevs/comments/1uh8uts/the_ai_burns_the_toast_i_scrape_it/)
- [Visual Studio Code](https://code.visualstudio.com/docs/agents/run/agents-window)
- [Cursor](https://cursor.com/blog/agent-best-practices)
- [CodeRabbit +1](https://docs.coderabbit.ai/change-stack/navigation)
- [GitHub](https://github.com/git-ai-project/git-ai)
- [GitHub Docs +1](https://docs.github.com/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue)
- [Graphite +1](https://graphite.com/docs/key-features)
- [Cloudflare Docs +1](https://developers.cloudflare.com/artifacts/api/workers-binding/)
- [Cloudflare Docs](https://developers.cloudflare.com/artifacts/guides/authentication/)
- [Cloudflare Docs](https://developers.cloudflare.com/artifacts/api/workers-binding/)
- [Cloudflare Docs +1](https://developers.cloudflare.com/artifacts/platform/limits/)
- [Cursor +1](https://cursor.com/blog/agent-best-practices)
- [GitHub Docs](https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations)
- [Reddit](https://www.reddit.com/r/AI_Agents/comments/1stu0we/people_running_25_coding_agents_what_actually/)
- [GitHub Docs](https://docs.github.com/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue)
- [Sawyer Hood](https://www.sawyerhood.com/blog/hired-a-middle-manager)
- [CodeRabbit](https://docs.coderabbit.ai/connections/linear)
- [Hacker News](https://news.ycombinator.com/item?id=48089263)
- [GitHub Docs +3](https://docs.github.com/en/graphql/reference/pulls)
