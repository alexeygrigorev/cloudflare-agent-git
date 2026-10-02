# HN evidence: real problems when coding agents use Git/GitHub

Lane: Hacker News (Algolia API). Owner: Claude principal research subagent. Started 2026-10-02.
Method: HN Algolia search (stories + comments), item endpoint for comment trees. All quotes copied verbatim from API text (HTML entities decoded). VERIFIED = text fetched from API by this agent.

## Evidence items

### E-C101
- URL: https://news.ycombinator.com/item?id=45110721 (thread: "Parallel AI agents are a game changer", https://news.ycombinator.com/item?id=45110075)
- Author / date: tptacek / 2025-09-03
- Quote: "Concurrent execution is tricky, at least for tightly defined projects, because the PRs will step on each other, and (maybe this is just me) I would rather rewrite an entire project than try to pick through a complicated merge conflict."
- Category: conflicts
- Persona: solo dev / experienced practitioner (security engineer)
- Severity/frequency: High intensity; prominent HN user on 'Parallel AI agents are a game changer' thread
- Workaround mentioned: Prefers async over concurrent; rewrite rather than resolve
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C102
- URL: https://news.ycombinator.com/item?id=46429365 (thread: "Show HN: Superset – Terminal to run 10 parallel coding agents", https://news.ycombinator.com/item?id=46368739)
- Author / date: sathish316 / 2025-12-30
- Quote: "Most of these tools don’t make working with Git merges or conflicts to main simpler in their UX. Even in Cursor, it helps to be good at using git from the command line to use Parallel agents effectively"
- Category: tooling-gap / conflicts
- Persona: solo dev
- Severity/frequency: Medium; recurring complaint about orchestrator tools (Superset thread)
- Workaround mentioned: Manual diff, patch, cherry-pick from worktree to main; restrict parallel agents to non-overlapping work
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C103
- URL: https://news.ycombinator.com/item?id=48376181 (thread: "GitHub Copilot App", https://news.ycombinator.com/item?id=48373764)
- Author / date: mohamedkoubaa / 2026-06-02
- Quote: "I spend about a third of the time helping agents integrate and merge. I remember wishing the tooling would catch up"
- Category: conflicts / tooling-gap
- Persona: solo dev / team dev
- Severity/frequency: High: quantified ~1/3 of time on integration
- Workaround mentioned: agents.md instructions on how to merge branches; multiple worktrees in one VS Code workspace
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C104
- URL: https://news.ycombinator.com/item?id=47611627 (thread: "Show HN: Baton – A desktop app for developing with AI agents", https://news.ycombinator.com/item?id=47599771)
- Author / date: KurSix / 2026-04-02
- Quote: "when five parallel Claudes rewrite the exact same base class or interface for their own local needs, you're gonna end up with a merge conflict no neural net could ever untangle."
- Category: conflicts
- Persona: practitioner (skeptic)
- Severity/frequency: High intensity claim; calls worktree-per-agent an architectural dead end
- Workaround mentioned: None; manual rebasing
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C105
- URL: https://news.ycombinator.com/item?id=47253997 (thread: "Weave – A language aware merge algorithm based on entities", https://news.ycombinator.com/item?id=47241976)
- Author / date: laalshaitaan / 2026-03-04
- Quote: "The merge conflict is the symptom. The root problem is parallel agents have no coordination primitives before edits happen."
- Category: coordination
- Persona: tool builder / platform eng
- Severity/frequency: Medium; framing echoed by many Show HN tools (Clash, Foremerge, Weave)
- Workaround mentioned: Entity claiming via MCP server (Weave)
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C106
- URL: https://news.ycombinator.com/item?id=49383454 (thread: "There's no such thing as a small software team anymore", https://news.ycombinator.com/item?id=49382152)
- Author / date: ulrikrasmussen / 2026-08-21
- Quote: "You will also get these conflicts with a microservice architecture and hundreds of independent repos, but now it is not a merge conflict because you touched the same syntax, it is a semantic conflict."
- Category: conflicts (semantic)
- Persona: team engineer
- Severity/frequency: Medium; pushback on re-architecting for parallel agents
- Workaround mentioned: None; argues against microservices-for-agents
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C107
- URL: https://news.ycombinator.com/item?id=45749603 (thread: "Cursor 2.0", https://news.ycombinator.com/item?id=45749442)
- Author / date: billconan / 2025-10-29
- Quote: "If we do this in parallel, merging the changes, resolving merge conflicts will be a nightmare. Unless, the agents work on completely isolated modules, but that's rarely the case?"
- Category: conflicts / negative-evidence
- Persona: solo dev (skeptic)
- Severity/frequency: Medium; Cursor 2.0 launch thread
- Workaround mentioned: Only isolated modules
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C108
- URL: https://news.ycombinator.com/item?id=49415005 (thread: "Parallel development without the headaches using Git worktree", https://news.ycombinator.com/item?id=49413093)
- Author / date: pkghost / 2026-08-24
- Quote: "as soon as they needed to touch another repo, they would default to working in that repo directly"
- Category: coordination / tooling-gap (multi-repo)
- Persona: solo dev / homelab platform
- Severity/frequency: Medium; gave up on worktrees after a month
- Workaround mentioned: Multiple full checkouts instead of worktrees
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C109
- URL: https://news.ycombinator.com/item?id=48081696 (thread: "Bun's experimental Rust rewrite hits 99.8% test compatibility on Linux x64 glibc", https://news.ycombinator.com/item?id=48073680)
- Author / date: _flux / 2026-05-10
- Quote: "applied a simple protocol for locking the master repository during merges, so multiple agents wouldn't try to merge at the same time."
- Category: coordination
- Persona: solo dev
- Severity/frequency: Medium; home-grown merge lock + DB per worktree
- Workaround mentioned: Scripts: worktree setup/teardown, reflinked build artifacts, fresh DB instance, master-repo lock during merges
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C110
- URL: https://news.ycombinator.com/item?id=46731823 (thread: "Multiclaude – Lightweight Multiagent Orchestrator", https://news.ycombinator.com/item?id=46726307)
- Author / date: storystarling / 2026-01-23
- Quote: "I switched from a similar parallelized setup to LangGraph precisely because the merge conflicts and redundant reasoning steps were killing my margins."
- Category: cost / conflicts
- Persona: small business / agent operator
- Severity/frequency: High (economic): abandoned parallel setup
- Workaround mentioned: Switched to LangGraph with coordinator
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C111
- URL: https://news.ycombinator.com/item?id=49795653 (thread: "Show HN: Foremerge – Catch intent conflicts between parallel coding agents", https://news.ycombinator.com/item?id=49789356)
- Author / date: naw103 / 2026-09-22
- Quote: "Even if you can use AI to resolve the conflicts at PR time, you need the right context and you've already burned through tokens building and now even more fixing."
- Category: conflicts / cost
- Persona: tool builder / small team lead (GPTree)
- Severity/frequency: Medium; first-hand since Jan 2026
- Workaround mentioned: One worktree per task + lease/commit intent and scope into immutable log; drift verified at acceptance (Foremerge)
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C112
- URL: https://news.ycombinator.com/item?id=49795378 (thread: "Show HN: Foremerge – Catch intent conflicts between parallel coding agents", https://news.ycombinator.com/item?id=49789356)
- Author / date: ttoinou / 2026-09-22
- Quote: "But we don't know in advance what we will need to change in our current task. And even if we did, there are always side effects."
- Category: negative-evidence (against upfront intent/locks)
- Persona: developer
- Severity/frequency: Medium; objection to claim-based coordination
- Workaround mentioned: n/a
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C113
- URL: https://news.ycombinator.com/item?id=49811149 (thread: "Show HN: Foremerge – Catch intent conflicts between parallel coding agents", https://news.ycombinator.com/item?id=49789356)
- Author / date: gavmor / 2026-09-23
- Quote: "I've been using a combination of `weave` and ad hoc "blackboard pattern" skills—some self-made, some borrowed—but I haven't really felt they've earned their keep."
- Category: negative-evidence / coordination
- Persona: power user running up to ~25 worktree-isolated agents
- Severity/frequency: Medium; coordination tools not paying off
- Workaround mentioned: Coordinator agent that intrudes on sessions; aoe for spawning
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C114
- URL: https://news.ycombinator.com/item?id=49819493 (thread: "Show HN: Foremerge – Catch intent conflicts between parallel coding agents", https://news.ycombinator.com/item?id=49789356)
- Author / date: naw103 / 2026-09-23
- Quote: "The agents were aware of what was put into memory but still did their own thing and created conflicts."
- Category: coordination
- Persona: tool builder
- Severity/frequency: Medium; shared blackboard memory insufficient
- Workaround mentioned: Foremerge advisory intent claims with logged rationale
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C115
- URL: https://news.ycombinator.com/item?id=49795463 (thread: "Show HN: Foremerge – Catch intent conflicts between parallel coding agents", https://news.ycombinator.com/item?id=49789356)
- Author / date: wilsprouse / 2026-09-22
- Quote: "I think the current version control mechanisms are meant for humans, not agents. I'm still trying to think of a scenario where an agent needs to see a git diff."
- Category: tooling-gap
- Persona: developer
- Severity/frequency: Low-medium (opinion)
- Workaround mentioned: n/a
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C116
- URL: https://news.ycombinator.com/item?id=47801652 (thread: "Artifacts: Versioned storage that speaks Git", https://news.ycombinator.com/item?id=47792374)
- Author / date: gavinray / 2026-04-17
- Quote: "After reading the article, it still was not clear to me why I would need this over git, Github, and a bunch of branches/worktrees."
- Category: negative-evidence (Cloudflare Artifacts launch)
- Persona: developer
- Severity/frequency: Medium; judges market 'niche'
- Workaround mentioned: git + GitHub + branches/worktrees
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C117
- URL: https://news.ycombinator.com/item?id=47799165 (thread: "Artifacts: Versioned storage that speaks Git", https://news.ycombinator.com/item?id=47792374)
- Author / date: sudb / 2026-04-16
- Quote: "I suspect that the easy path is still one of the many sandbox providers + GitHub."
- Category: negative-evidence (Artifacts launch)
- Persona: agent platform builder
- Severity/frequency: Medium; questions target market of Artifacts
- Workaround mentioned: Sandbox providers + GitHub
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C118
- URL: https://news.ycombinator.com/item?id=47798459 (thread: "Artifacts: Versioned storage that speaks Git", https://news.ycombinator.com/item?id=47792374)
- Author / date: crabbone / 2026-04-16
- Quote: "I keep hearing this argument, but there's not even an attempt at explanation for why this should be true."
- Category: negative-evidence (scale claim)
- Persona: developer (skeptic)
- Severity/frequency: Medium; disputes '10x volume' premise of Artifacts blog
- Workaround mentioned: n/a
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C119
- URL: https://news.ycombinator.com/item?id=47804119 (thread: "Artifacts: Versioned storage that speaks Git", https://news.ycombinator.com/item?id=47792374)
- Author / date: mattzcarey / 2026-04-17
- Quote: "We started with exposing a git server interface from Artifacts but that is by no means the end goal or the best protocol for all situations."
- Category: tooling-gap (vendor statement)
- Persona: Cloudflare Artifacts author
- Severity/frequency: Signals openness to agent-first VCS layer on top
- Workaround mentioned: n/a
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C120
- URL: https://news.ycombinator.com/item?id=47797602 (thread: "Artifacts: Versioned storage that speaks Git", https://news.ycombinator.com/item?id=47792374)
- Author / date: tln / 2026-04-16
- Quote: "Missing features: list branches and tags list objects list commit history create new commits read raw git objects merge branches or repos read git object by path"
- Category: tooling-gap (Artifacts API, Apr 2026)
- Persona: developer
- Severity/frequency: Medium; Cloudflare replied these were 'coming soon' (47799296) - verify current docs
- Workaround mentioned: n/a
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C121
- URL: https://news.ycombinator.com/item?id=48089513 (thread: "PS3 Emulator Devs Politely Ask That People Stop Flooding It with AI PRs", https://news.ycombinator.com/item?id=48089263)
- Author / date: saagarjha / 2026-05-11
- Quote: "we would only accept PRs that reduced our work instead of increasing it."
- Category: review-burden
- Persona: OSS maintainer
- Severity/frequency: High; PS3 emulator AI PR flood thread (189 pts)
- Workaround mentioned: Policy: only accept PRs that reduce maintainer work
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C122
- URL: https://news.ycombinator.com/item?id=48090155 (thread: "PS3 Emulator Devs Politely Ask That People Stop Flooding It with AI PRs", https://news.ycombinator.com/item?id=48089263)
- Author / date: jonhohle / 2026-05-11
- Quote: "On a small utility I have I received a PR that was more lines than the project had."
- Category: review-burden
- Persona: OSS maintainer (small project)
- Severity/frequency: Medium; affects small projects too
- Workaround mentioned: Declined; cannot vet, cannot blindly accept
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C123
- URL: https://news.ycombinator.com/item?id=48089972 (thread: "PS3 Emulator Devs Politely Ask That People Stop Flooding It with AI PRs", https://news.ycombinator.com/item?id=48089263)
- Author / date: jcranmer / 2026-05-11
- Quote: "As a maintainer, discovering that a PR is AI-generated just absolutely saps any motivation I have to actually review it."
- Category: review-burden / provenance
- Persona: OSS maintainer
- Severity/frequency: High intensity
- Workaround mentioned: None
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C124
- URL: https://news.ycombinator.com/item?id=48090054 (thread: "PS3 Emulator Devs Politely Ask That People Stop Flooding It with AI PRs", https://news.ycombinator.com/item?id=48089263)
- Author / date: djtango / 2026-05-11
- Quote: "maintainers are flooded with low effort PRs that take more effort to review than author"
- Category: review-burden
- Persona: developer observing OSS
- Severity/frequency: High; effort-asymmetry framing recurs across threads
- Workaround mentioned: n/a
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C125
- URL: https://news.ycombinator.com/item?id=48089648 (thread: "PS3 Emulator Devs Politely Ask That People Stop Flooding It with AI PRs", https://news.ycombinator.com/item?id=48089263)
- Author / date: MBCook / 2026-05-11
- Quote: "It’s starting to feel like we may need to go back to the model where you need to be invited to be able to submit code or PRs."
- Category: review-burden / safety (trust)
- Persona: developer
- Severity/frequency: Medium; replies propose reputation / web-of-trust
- Workaround mentioned: Invite-only contributions, reputation score (proposed)
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C126
- URL: https://news.ycombinator.com/item?id=48089712 (thread: "PS3 Emulator Devs Politely Ask That People Stop Flooding It with AI PRs", https://news.ycombinator.com/item?id=48089263)
- Author / date: jamesu / 2026-05-11
- Quote: "the solution I liked the best was the linux "developers take full responsibility" approach. The "Assisted-by:" tag was a pretty nice touch too."
- Category: provenance
- Persona: developer
- Severity/frequency: Medium; existing provenance convention
- Workaround mentioned: Linux kernel Assisted-by: trailer + human responsibility
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C127
- URL: https://news.ycombinator.com/item?id=48089763 (thread: "PS3 Emulator Devs Politely Ask That People Stop Flooding It with AI PRs", https://news.ycombinator.com/item?id=48089263)
- Author / date: Panzer04 / 2026-05-11
- Quote: "If you're upfront about the provenance and amount of effort that went into it, is there really a problem?"
- Category: provenance
- Persona: developer
- Severity/frequency: Medium
- Workaround mentioned: Disclosure of provenance/effort
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C128
- URL: https://news.ycombinator.com/item?id=48089997 (thread: "PS3 Emulator Devs Politely Ask That People Stop Flooding It with AI PRs", https://news.ycombinator.com/item?id=48089263)
- Author / date: Aurornis / 2026-05-11
- Quote: "it’s funny how often they’ll come back with gigantic commits that just make everything worse or accomplish the goal but have 1000 lines of unnecessary complexity."
- Category: review-burden
- Persona: experienced dev running agents in parallel
- Severity/frequency: Medium-high; frequent ('how often')
- Workaround mentioned: Runs Claude Code/Codex in parallel as exploration, discards
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C129
- URL: https://news.ycombinator.com/item?id=48089735 (thread: "PS3 Emulator Devs Politely Ask That People Stop Flooding It with AI PRs", https://news.ycombinator.com/item?id=48089263)
- Author / date: nlh / 2026-05-11
- Quote: "I neither want to get attacked for submitting slop nor do I have the time to properly engineer it to be hand-coded, so the net result is that it lives on my machine alone."
- Category: provenance / tooling-gap (contribution path)
- Persona: solo dev / would-be contributor
- Severity/frequency: Medium; useful AI-built changes never shared upstream
- Workaround mentioned: Keep fork local; suggestions: open issue/discussion describing the change
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C130
- URL: https://news.ycombinator.com/item?id=46915049 (thread: "GitHub Ponders Kill Switch for Pull Requests to Stop AI Slop", https://news.ycombinator.com/item?id=46884471)
- Author / date: DavidYoussef / 2026-02-06
- Quote: "maintainers have no way to distinguish "AI-generated typo fix from a new contributor" from "AI-generated rewrite of my auth system by someone who doesn't understand it.""
- Category: review-burden / tooling-gap
- Persona: tool builder
- Severity/frequency: Medium
- Workaround mentioned: Risk-tiered GitHub Action (codeguard-action): zone classification, proportional AI review, hash-chained evidence bundle
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C131
- URL: https://news.ycombinator.com/item?id=46884497 (thread: "GitHub Ponders Kill Switch for Pull Requests to Stop AI Slop", https://news.ycombinator.com/item?id=46884471)
- Author / date: longtermop / 2026-02-04
- Quote: "A malicious contributor can embed prompt injection in comments, variable names, or even carefully crafted code patterns that manipulate how the reviewing AI interprets the change."
- Category: safety
- Persona: security tool builder
- Severity/frequency: Medium; AI reviewers ingest untrusted PR input
- Workaround mentioned: Prompt-injection detection (vendor)
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C132
- URL: https://news.ycombinator.com/item?id=47272069 (thread: "A standard protocol to handle and discard low-effort, AI-Generated pull requests", https://news.ycombinator.com/item?id=47267947)
- Author / date: lelanthran / 2026-03-06
- Quote: "If your PR took less time to create and submit than it takes the maintainer to read, then you didn't read your own PR!"
- Category: review-burden
- Persona: developer
- Severity/frequency: Medium-high; 'low-effort AI PR protocol' thread (305 pts)
- Workaround mentioned: n/a
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C133
- URL: https://news.ycombinator.com/item?id=47271528 (thread: "A standard protocol to handle and discard low-effort, AI-Generated pull requests", https://news.ycombinator.com/item?id=47267947)
- Author / date: danpalmer / 2026-03-06
- Quote: "I did not feel that I knew the codebase enough to be able to actually assess the correctness of the change."
- Category: review-burden / provenance
- Persona: team engineer
- Severity/frequency: Medium; first-hand at work ('1 min of prompting, 5 mins of tidying, and 30 mins of review')
- Workaround mentioned: Asked AI for more confidence; lost confidence after AI 'fixes' (see reply 47274125)
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C134
- URL: https://news.ycombinator.com/item?id=44036271 (thread: "GitHub Copilot Coding Agent", https://news.ycombinator.com/item?id=44031432)
- Author / date: timrogers / 2025-05-19
- Quote: "When Copilot pushes changes, your GitHub Actions workflows won't run by default, and you'll have to click the "Approve and run workflows" button in the merge box."
- Category: safety (competitor capability)
- Persona: GitHub product team (Copilot coding agent)
- Severity/frequency: Baseline: GitHub treats agent like first-time contributor; agent can only push own branch
- Workaround mentioned: Branch-only write, manual CI approval
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C135
- URL: https://news.ycombinator.com/item?id=48843951 (thread: "Rewriting Bun in Rust", https://news.ycombinator.com/item?id=48837877)
- Author / date: xyzsparetimexyz / 2026-07-09
- Quote: "one Claude ran git stash before committing. Another ran git stash pop. And then git reset HEAD --hard. They were stepping on each other!"
- Category: conflicts / safety (shared working tree)
- Persona: large OSS project (Bun Rust rewrite, quoted by commenter)
- Severity/frequency: High; repo too big for worktree-per-agent ('run out of disk space')
- Workaround mentioned: Instruct Claude never to run git stash/reset; commit specific files only
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C136
- URL: https://news.ycombinator.com/item?id=47569157 (thread: "Claude Code runs Git reset –hard origin/main against project repo every 10 mins", https://news.ycombinator.com/item?id=47567969)
- Author / date: jeswin / 2026-03-30
- Quote: "It has once even force pushed to github, which doesn't allow branch protection for private personal projects."
- Category: safety
- Persona: solo dev
- Severity/frequency: High; 'not a one off issue - it has happened to me a few times'
- Workaround mentioned: Rule at top of CLAUDE.md (partially followed)
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C137
- URL: https://news.ycombinator.com/item?id=47569446 (thread: "Claude Code runs Git reset –hard origin/main against project repo every 10 mins", https://news.ycombinator.com/item?id=47567969)
- Author / date: Jarred / 2026-03-30
- Quote: "Claude Code itself does not have code that spawns `git reset --hard origin/main`"
- Category: negative-evidence (safety incident misattributed)
- Persona: commenter "Jarred" who investigated the report (likely Bun author; identity not independently verified)
- Severity/frequency: Shows some incidents are user-config (cron/loop) not tool bugs
- Workaround mentioned: n/a
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C138
- URL: https://news.ycombinator.com/item?id=46787865 (thread: "I built a Git firewall because I'm terrified of my own AI agents", https://news.ycombinator.com/item?id=46787838)
- Author / date: cocabadger / 2026-01-27
- Quote: "I’d rely on them to 'fix' a merge conflict, click 'Apply', and then watch in horror as they force-pushed broken history."
- Category: safety / conflicts
- Persona: non-engineer vibe coder (PMM)
- Severity/frequency: High (emotional); built tool in response
- Workaround mentioned: SafeRun: git reference-transaction hook intercepting destructive ops
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C139
- URL: https://news.ycombinator.com/item?id=48550061 (thread: "Microsoft turns to AWS as GitHub faces AI capacity crunch", https://news.ycombinator.com/item?id=48549918)
- Author / date: nomel / 2026-06-16
- Quote: "I commit much more often, as checkpoints, with branch rules that prevent force pushes/deletions, so the agents can't delete anything."
- Category: safety / cost (commit volume)
- Persona: solo dev
- Severity/frequency: Medium; agent use increases commit volume on GitHub
- Workaround mentioned: Frequent checkpoint commits + branch protection rules, later squash
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C140
- URL: https://news.ycombinator.com/item?id=47914095 (thread: "An AI agent deleted our production database. The agent's confession is below", https://news.ycombinator.com/item?id=47911524)
- Author / date: noncoml / 2026-04-26
- Quote: "We all try to shout the exact same things to our agents, but they politely ignore us!"
- Category: safety
- Persona: developer
- Severity/frequency: Medium-high; prose rules in prompts unreliable for destructive git ops
- Workaround mentioned: System prompt rules (ineffective)
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C141
- URL: https://news.ycombinator.com/item?id=49213141 (thread: "GitHub Actions and Pages are experiencing degraded availability", https://news.ycombinator.com/item?id=49198302)
- Author / date: ModernMech / 2026-08-07
- Quote: "it ballooned a 3 minute CI workflow to 30 minutes per commit, and the number of commits it started making increased 10 fold. So we're looking at a 100x increase in usage just from myself."
- Category: cost
- Persona: solo dev / educator
- Severity/frequency: High; quantified 100x CI usage; GitHub Actions degradation thread
- Workaround mentioned: None mentioned
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C142
- URL: https://news.ycombinator.com/item?id=49125075 (thread: "Agent Sandbox: A Kubernetes CRD and controller for AI agent runtimes", https://news.ycombinator.com/item?id=49125061)
- Author / date: jhgaylor / 2026-07-31
- Quote: "I ended up using GitHub Actions as my trusted environment for testing untrusted code, which works but is miserable ergonomics for an agent: batch execution, a minutes-long feedback loop, and no way to poke at a failure interactively."
- Category: tooling-gap / cost (verification loop)
- Persona: platform eng running fleet of agents
- Severity/frequency: High; verification is 'the painful one'
- Workaround mentioned: GitHub Actions as trusted verifier; k8s agent sandbox
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C143
- URL: https://news.ycombinator.com/item?id=48200834 (thread: "Stop babysitting your AI agents", https://news.ycombinator.com/item?id=48200833)
- Author / date: railbuilder / 2026-05-19
- Quote: "Merge something whose tests are still red. And they're doing all of this with a personal access token that has full org access, no expiry, no audit trail."
- Category: safety / tooling-gap
- Persona: tool builder (AgentRail)
- Severity/frequency: Medium-high; recurring loop failure after push (miss CI failure, fix nonexistent commit)
- Workaround mentioned: AgentRail task lifecycle CLI (intake/route/claim/review/ship)
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C144
- URL: https://news.ycombinator.com/item?id=47715149 (thread: "We've raised $17M to build what comes after Git", https://news.ycombinator.com/item?id=47712656)
- Author / date: pu_pe / 2026-04-10
- Quote: "These days a 10k LOC commit might be triggered by a 100-word user prompt, there is a lot more signal in reading the prompt itself than the code changes."
- Category: provenance
- Persona: developer
- Severity/frequency: Medium; on '$17M to build what comes after Git' thread
- Workaround mentioned: Store prompts (proposed)
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C145
- URL: https://news.ycombinator.com/item?id=46970483 (thread: "Ex-GitHub CEO launches a new developer platform for AI agents", https://news.ycombinator.com/item?id=46961345)
- Author / date: tbrownaw / 2026-02-11
- Quote: "What actually works is putting a ticket (or project) number in the commit message, and making sure everything relevant gets written up and saved to that centralized repository."
- Category: negative-evidence (provenance)
- Persona: team engineer
- Severity/frequency: Medium; argues saving agent chats adds little
- Workaround mentioned: Ticket number in commit message
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C146
- URL: https://news.ycombinator.com/item?id=47213276 (thread: "If AI writes code, should the session be part of the commit?", https://news.ycombinator.com/item?id=47212355)
- Author / date: ehnto / 2026-03-02
- Quote: "An actual full context of a thinking agent is asinine, full of busy work, at best if you want to preserve the "reason" for the commits contents maybe you could summarise the context."
- Category: negative-evidence (provenance) / design hint
- Persona: developer
- Severity/frequency: Medium
- Workaround mentioned: Summarised context (proposed)
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C147
- URL: https://news.ycombinator.com/item?id=47214586 (thread: "If AI writes code, should the session be part of the commit?", https://news.ycombinator.com/item?id=47212355)
- Author / date: brainlounge / 2026-03-02
- Quote: "git history or the commit messages should focus on the outcome of the work, not on the process itself."
- Category: provenance (where to store)
- Persona: developer
- Severity/frequency: Medium; session logs valuable but not in git
- Workaround mentioned: Store sessions next to git, not in it
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C148
- URL: https://news.ycombinator.com/item?id=45055550 (thread: "Claude Code Checkpoints", https://news.ycombinator.com/item?id=45050090)
- Author / date: slavakurilyak / 2025-08-28
- Quote: "With jj, every file change is automatically captured (no manual commits needed), and you can create lightweight "sandbox" revisions for each Claude Code task."
- Category: negative-evidence (existing tool solves checkpointing)
- Persona: jj user
- Severity/frequency: Medium; jj recurrently proposed as answer
- Workaround mentioned: Jujutsu snapshots, jj undo, op log
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C149
- URL: https://news.ycombinator.com/item?id=47688462 (thread: "Git commands I run before reading any code", https://news.ycombinator.com/item?id=47687273)
- Author / date: Jenk / 2026-04-08
- Quote: "my workflow with agents that commit on my behalf but I'm not going to give agents my private key!"
- Category: provenance / safety (signing)
- Persona: solo dev (jj user)
- Severity/frequency: Low-medium; agent commits unsigned, human re-signs
- Workaround mentioned: jj log -r 'mine() & ~signed()' then jj sign
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C150
- URL: https://news.ycombinator.com/item?id=48846424 (thread: "How version control will evolve for the agent boom", https://news.ycombinator.com/item?id=48844709)
- Author / date: sdesol / 2026-07-09
- Quote: "With hooks, you can easy detect when 'git' is used and basically tell the agent "As stated earlier you must use jj"."
- Category: tooling-gap (agents default to git)
- Persona: tool builder
- Severity/frequency: Medium; models heavily trained on git forget alternative VCS
- Workaround mentioned: Hooks that block git and redirect to jj
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C151
- URL: https://news.ycombinator.com/item?id=46501159 (thread: "Claude Code On-the-Go", https://news.ycombinator.com/item?id=46491486)
- Author / date: philip1209 / 2026-01-05
- Quote: "I typically spend 30-60 minutes writing a spec, then the agent runs for 30-60 minutes, then I spend 30-60 minutes refining code/ui/etc before putting up a PR, then another 30-60 minutes waiting for CI"
- Category: negative-evidence (parallelism limited by human)
- Persona: solo founder
- Severity/frequency: Medium; 'does everybody have enough work for multiple agents in parallel?'
- Workaround mentioned: Sequential workflow
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C152
- URL: https://news.ycombinator.com/item?id=48845283 (thread: "How version control will evolve for the agent boom", https://news.ycombinator.com/item?id=48844709)
- Author / date: pornel / 2026-07-09
- Quote: "For popular projects agent-made pull requests become a DoS attack. I wouldn't be surprised if projects start refusing to accept unsolicited PRs and switch to "don't call us, we'll call you"."
- Category: review-burden / tooling-gap (contribution model)
- Persona: OSS maintainer (handle pornel; identity not independently verified)
- Severity/frequency: High; proposes agent scanning forks as roadmap instead of PRs
- Workaround mentioned: Maintainer's own agent reimplements idea; scan forks
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C153
- URL: https://news.ycombinator.com/item?id=48846415 (thread: "How version control will evolve for the agent boom", https://news.ycombinator.com/item?id=48844709)
- Author / date: wateralien / 2026-07-09
- Quote: "We need to store CHOICES with the commit or branch. Not the whole session. Conscious, summarized choices"
- Category: provenance
- Persona: developer
- Severity/frequency: Medium; recurring 'summarized decisions not transcripts' theme
- Workaround mentioned: Entire stores whole session with query tools (vendor reply)
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C154
- URL: https://news.ycombinator.com/item?id=48846817 (thread: "How version control will evolve for the agent boom", https://news.ycombinator.com/item?id=48844709)
- Author / date: jerf / 2026-07-09
- Quote: "Wasn't there an article on HN that went by in the last few weeks about someone actually implementing this, and it just made things worse on every metric?"
- Category: negative-evidence (session logs in repo)
- Persona: experienced developer
- Severity/frequency: Medium; skepticism of transcript-as-provenance
- Workaround mentioned: Prompt history at most
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C155
- URL: https://news.ycombinator.com/item?id=48846859 (thread: "How version control will evolve for the agent boom", https://news.ycombinator.com/item?id=48844709)
- Author / date: overgard / 2026-07-09
- Quote: "nobody wants to read someone else's conversation with it, and certainly nobody wants to read a multi-year old session log that's 20,000 words long."
- Category: negative-evidence (provenance via transcripts)
- Persona: developer
- Severity/frequency: Medium
- Workaround mentioned: Commit messages
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C156
- URL: https://news.ycombinator.com/item?id=48846245 (thread: "How version control will evolve for the agent boom", https://news.ycombinator.com/item?id=48844709)
- Author / date: mickeyp / 2026-07-09
- Quote: "No, the future is a complex "gate" that checks, weighs and measures everything before it gets committed"
- Category: tooling-gap (pre-commit gates) / negative-evidence on provenance
- Persona: developer
- Severity/frequency: Medium; distrusts vendor classifiers (48846489), wants project-specific gates; says session value 'practically nil'
- Workaround mentioned: Team-built gateway of subagents + linters + tests
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C157
- URL: https://news.ycombinator.com/item?id=47580465 (thread: "Ask HN: Is it actually possible to run multiple coding sessions in parallel?", https://news.ycombinator.com/item?id=47573483)
- Author / date: sprobertson / 2026-03-30
- Quote: "I lean heavily on hot-reloading of both backend and frontend (to actually see what I'm doing) so it's too annoying to deal with dependencies and ports when things are isolated."
- Category: negative-evidence (worktrees) / tooling-gap (env per branch)
- Persona: solo dev
- Severity/frequency: Medium; avoids worktrees entirely
- Workaround mentioned: Everyone on main; tasks kept separate in scope; agent commits its own work
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C158
- URL: https://news.ycombinator.com/item?id=47575576 (thread: "Ask HN: Is it actually possible to run multiple coding sessions in parallel?", https://news.ycombinator.com/item?id=47573483)
- Author / date: kevinsync / 2026-03-30
- Quote: "you run the risk of wasted time, tokens and effort having a bunch of parallel work running that may not end up compatible at the end."
- Category: negative-evidence (parallel) / conflicts
- Persona: solo dev using Claude + Codex
- Severity/frequency: Medium; rarely runs truly parallel tasks
- Workaround mentioned: Sequential: Claude plans, Codex validates, Claude implements, Codex reviews
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C159
- URL: https://news.ycombinator.com/item?id=47573568 (thread: "Ask HN: Is it actually possible to run multiple coding sessions in parallel?", https://news.ycombinator.com/item?id=47573483)
- Author / date: rox_kd / 2026-03-30
- Quote: "to many hanging worktrees can quickly also become a nightmare managing"
- Category: tooling-gap (branch/worktree lifecycle)
- Persona: solo dev running 5-10 sessions
- Severity/frequency: Medium
- Workaround mentioned: Small atomic tasks, merge often
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C160
- URL: https://news.ycombinator.com/item?id=47574025 (thread: "Ask HN: Is it actually possible to run multiple coding sessions in parallel?", https://news.ycombinator.com/item?id=47573483)
- Author / date: nathan_douglas / 2026-03-30
- Quote: "I've had some issues with Claude Code forgetting where it did things ("oh... it's not working because I'm not in the right directory")."
- Category: tooling-gap (worktree confusion)
- Persona: solo dev
- Severity/frequency: Low-medium
- Workaround mentioned: Superpowers plans + worktrees
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C161
- URL: https://news.ycombinator.com/item?id=46973881 (thread: "Ex-GitHub CEO launches a new developer platform for AI agents", https://news.ycombinator.com/item?id=46961345)
- Author / date: whh / 2026-02-11
- Quote: "I have a lot of concurrent agents working on things at the same time, so I'm not always sure why a piece of code is the way it is months later."
- Category: provenance
- Persona: developer running many concurrent agents
- Severity/frequency: Medium; direct first-hand provenance pain (Entire launch thread)
- Workaround mentioned: Trying Entire Checkpoints
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C162
- URL: https://news.ycombinator.com/item?id=46973388 (thread: "Ex-GitHub CEO launches a new developer platform for AI agents", https://news.ycombinator.com/item?id=46961345)
- Author / date: vidarh / 2026-02-11
- Quote: "You can trivially have Claude Code write a commit hook to do this for you if you find it useful."
- Category: negative-evidence (provenance product is thin)
- Persona: experienced developer
- Severity/frequency: Medium; transcript-to-branch is easy to DIY
- Workaround mentioned: Commit hook archiving Claude Code JSONL
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C163
- URL: https://news.ycombinator.com/item?id=46970704 (thread: "Ex-GitHub CEO launches a new developer platform for AI agents", https://news.ycombinator.com/item?id=46961345)
- Author / date: zhyder / 2026-02-11
- Quote: "wouldn't trying to pull N checkpoints into context of the N+1 task be MUCH more expensive? It's at odds with the current practice of clearing context regularly to save on input tokens."
- Category: cost / negative-evidence (provenance retrieval)
- Persona: developer
- Severity/frequency: Medium
- Workaround mentioned: Fresh context per task
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C164
- URL: https://news.ycombinator.com/item?id=47714451 (thread: "We've raised $17M to build what comes after Git", https://news.ycombinator.com/item?id=47712656)
- Author / date: hmontazeri / 2026-04-10
- Quote: "Just that works already pretty well with git and worktrees... and agent uses the tools anyway... dont know what they want to build with 17M"
- Category: negative-evidence (GitButler funding thread)
- Persona: developer
- Severity/frequency: Medium
- Workaround mentioned: git + worktrees
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C165
- URL: https://news.ycombinator.com/item?id=47716937 (thread: "We've raised $17M to build what comes after Git", https://news.ycombinator.com/item?id=47712656)
- Author / date: dirtbag__dad / 2026-04-10
- Quote: "As agents make it possible to do so much more code (even tens of files sucks to review, even if it’s broken into tiny PRs), I don’t want to be the gatekeeper at the code review lev"
- Category: review-burden
- Persona: developer / team lead
- Severity/frequency: Medium-high; rejects premise that humans will review all agent code
- Workaround mentioned: n/a
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C166
- URL: https://news.ycombinator.com/item?id=47720931 (thread: "We've raised $17M to build what comes after Git", https://news.ycombinator.com/item?id=47712656)
- Author / date: nickgreg / 2026-04-10
- Quote: "I find it less useful when agents code for me. The surgical changes GitButler made so easy became less relevant as agents touch so many files at once."
- Category: tooling-gap / negative-evidence (existing tool fit)
- Persona: long-time GitButler user
- Severity/frequency: Medium
- Workaround mentioned: n/a
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C167
- URL: https://news.ycombinator.com/item?id=47721667 (thread: "We've raised $17M to build what comes after Git", https://news.ycombinator.com/item?id=47712656)
- Author / date: ing33k / 2026-04-10
- Quote: "I lost interest the moment I was not able to commit using normal git commands."
- Category: tooling-gap (git compatibility requirement)
- Persona: developer (agent user; error shown is from agent session)
- Severity/frequency: Medium; agents/humans expect plain git to keep working
- Workaround mentioned: Exit GitButler mode
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C168
- URL: https://news.ycombinator.com/item?id=48636024 (thread: "Show HN: Oak – Git alternative designed for agents", https://news.ycombinator.com/item?id=48631726)
- Author / date: hanneshdc / 2026-06-22
- Quote: "git worktrees are a PITA."
- Category: tooling-gap (worktrees)
- Persona: developer
- Severity/frequency: Medium; Oak thread, likes 'lightning fast checkout for multi agent loads'
- Workaround mentioned: n/a
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C169
- URL: https://news.ycombinator.com/item?id=48633378 (thread: "Show HN: Oak – Git alternative designed for agents", https://news.ycombinator.com/item?id=48631726)
- Author / date: kjuulh / 2026-06-22
- Quote: "give agents the ability to have a workspace, that they pull repositories into, create branches as they want, commit on main it doesn't matter. the agents don't bother each other"
- Category: coordination (multi-repo workspaces)
- Persona: platform eng / solo dev
- Severity/frequency: Medium; cross-repo tasks
- Workaround mentioned: Own tool 'gitnow' (agent workspace pulling repos)
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

### E-C170
- URL: https://news.ycombinator.com/item?id=48633780 (thread: "Show HN: Oak – Git alternative designed for agents", https://news.ycombinator.com/item?id=48631726)
- Author / date: skydhash / 2026-06-22
- Quote: "Git has already all the features to make those happen, it’s the agent that is not integrated with git."
- Category: negative-evidence (git is fine)
- Persona: developer
- Severity/frequency: Medium; common rebuttal to 'git for agents'
- Workaround mentioned: git rebase, amend; fix architecture
- Status: VERIFIED (text fetched via HN Algolia items API 2026-10-02)

## Synthesis

Corpus: 70 VERIFIED items (E-C101 to E-C170) drawn from about 30 distinct HN threads, mostly 2025-09 to 2026-09. 21 items are negative or contrary evidence. Quotes were checked programmatically as exact substrings of the Algolia API text (whitespace normalized). Caveats: HN skews toward solo developers and tool builders. Many first-hand claims come from Show HN authors promoting their own tools (E-C105, E-C111, E-C114, E-C130, E-C143), so weight those as weaker evidence.

### Top 8 recurring pains (ranked by frequency x intensity)

1. **Integrating parallel agent work: merge conflicts, semantic conflicts and the human time they eat.** The most frequent pain. Worktrees isolate the filesystem but just move the pain to merge time. One quantified case: about 1/3 of time spent "helping agents integrate and merge". Some people rewrite instead of resolving. Items: E-C101, E-C102, E-C103, E-C104, E-C106, E-C107, E-C110, E-C111, E-C135, E-C158.
2. **No coordination layer before edits happen.** People build home-grown merge locks, intent/claim logs, blackboards and coordinator agents, and report that these often don't earn their keep. Items: E-C105, E-C109, E-C113, E-C114, E-C112 (objection: scope isn't knowable upfront), E-C169, E-C108 (multi-repo).
3. **Review burden from agent-generated PRs, both in OSS and at work.** The effort asymmetry is the core problem: a PR is cheaper to write than to review. Agent PRs are huge, sometimes larger than the whole project. Maintainers lose motivation to review, and some go invite-only or call it a "DoS". Items: E-C121, E-C122, E-C123, E-C124, E-C125, E-C128, E-C132, E-C133, E-C152, E-C165, E-C130.
4. **Destructive git operations by agents.** Examples: force-push, `reset --hard`, stash/pop races in a shared tree, and broad tokens. Rules written in prompts are ignored. People fall back on hooks, branch protection and wrappers. Items: E-C135, E-C136, E-C138, E-C139, E-C140, E-C143. E-C137 shows that some incidents are misattributed.
5. **Provenance: losing why code is the way it is.** This one is contested. People feel the pain (E-C161, E-C144, E-C129, E-C126/E-C127 on disclosure and Assisted-by, E-C149 on signing), but strongly reject raw transcripts (E-C154, E-C155, E-C146, E-C147, E-C145, E-C162, E-C163). The consensus pattern is short, summarized decisions/choices (E-C153) attached to commits, not session dumps.
6. **Slow verification loop and CI cost driven by agents.** Agents inflate commit counts and CI time (one self-report: 100x usage). GitHub Actions is batch-only and gives agents slow feedback. Agents miss red CI after pushing. Items: E-C141, E-C142, E-C143, E-C139, E-C151.
7. **Friction in managing worktrees and checkouts.** Problems reported: "PITA", stale worktrees piling up, agents confused about which directory they're in, disk space for big repos, port and dependency clashes for hot reload, and alternative VCS tools that break plain-git expectations. Items: E-C108, E-C135, E-C157, E-C159, E-C160, E-C167, E-C168, E-C166.
8. **Trust and safety of the review and contribution pipeline.** AI reviewers can be prompt-injected through PR content. People want gates they built themselves, not vendor classifiers. GitHub's baseline treats agents like first-time contributors (manual CI approval, own-branch-only pushes). Items: E-C131, E-C156, E-C134, E-C125.

### Negative or contrary evidence to respect

- **"git + worktrees already works; Artifacts and new VCSes are niche":** E-C116, E-C117, E-C118, E-C164, E-C170.
- **Parallelism is limited by human spec-writing and review, not by tooling:** E-C151, E-C158, E-C107.
- **Modular architecture prevents conflicts:** this claim appears in https://news.ycombinator.com/item?id=46729649 (BlueShrimpGames). It is not logged as an item. Counterpoint in E-C106.
- **jj is already offered as the answer for checkpointing and undo:** E-C148, E-C150. The catch is that agents default to git.
- **Coordination tooling exists but doesn't pay off:** E-C113.
- **Transcripts as provenance are rejected:** see pain 5.

### Gaps no current tool clearly fills (from evidence, for approach generation)

1. **A server-side merge/integration queue for many concurrent agent branches.** It would serialize merges, rebase and re-verify, and surface semantic conflicts. Today this is done with local scripts and locks (E-C109) or manual cherry-picks (E-C102, E-C103).
2. **Repo-native intent/claim signals visible across agents, harnesses and machines.** These need to be advisory, not locks, and enforced at acceptance time. Foremerge-style tools are local and per-tool (E-C105, E-C111, E-C114).
3. **Per-agent credentials and ref policy enforced by the git server itself.** Examples: agents can only push their own namespace, force-push and delete are impossible, there's an audit trail, and tokens are short-lived. This should work even for personal/private repos where hosted branch protection is limited (E-C136, E-C139, E-C143).
4. **Cheap ephemeral checkouts/forks per agent task.** These would avoid the disk and clone cost of worktrees for big repos (E-C135, E-C168) and enable cross-repo workspaces (E-C108, E-C169). This fits the Artifacts "repo per session" claim (E-C119 context, 47804133).
5. **A review-cost-aware contribution gate.** It would classify agent changes by risk and scope, demand evidence (tests, repro) and a short decision summary, and flip the effort asymmetry back onto the submitter. Alternatives to the PR, like pornel's "scan forks" model, are unaddressed (E-C121, E-C124, E-C130, E-C152).
6. **Summarized "choices" provenance attached to commits and queryable by later agents,** with no transcript dumps. This is wanted but contested, so it should be opt-in and compact (E-C153, E-C161 vs E-C155).
7. **A fast interactive verification sandbox tied to a branch,** in place of batch CI minutes (E-C141, E-C142).

### Data hygiene notes

- E-C120 (missing Artifacts APIs) dates from April 2026. Cloudflare replied "coming soon", so check it against current docs.
- E-C137 author identity is not independently verified.
- E-C152 is attributed to pornel by handle only.
