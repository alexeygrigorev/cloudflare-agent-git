# Maintainer and code-review burden evidence (Claude lane)

Researcher: claude-principal research subagent. Started 2026-10-02.
Scope: OSS maintainers vs AI/agent contributions, AI contribution policies, GitHub feature responses, team review workflows for agent PRs, survey data.
Rules: quotes verbatim (<=40 words) only from pages fetched in this session; VERIFIED = fetched; UNVERIFIED = seen only in search snippets.

## Items

### E-C201 curl: "better crap is worse" (AI security reports)
- URL: https://daniel.haxx.se/blog/2024/01/02/the-i-in-llm-stands-for-intelligence/
- Author/org: Daniel Stenberg, curl. Date: 2024-01-02
- Quote: "When reports are made to _look_ better and to _appear_ to have a point, it takes a longer time for us to research and eventually discard it. Every security report has to have a human spend time to look at it"
- Category: review-burden, spam. Persona: OSS security maintainer.
- Signal: 415 reports historically, 64 confirmed; plausible AI text raises time-to-reject per item.
- Workaround: manual triage, ban reporters. Status: VERIFIED

### E-C202 curl: ~20% AI slop, valid rate ~5%, 3-4 people x 30min-3h per report
- URL: https://daniel.haxx.se/blog/2025/07/14/death-by-a-thousand-slops/
- Author/org: Daniel Stenberg, curl. Date: 2025-07-14
- Quote: "The curl security team consists of seven team members. ... Every report thus engages 3-4 persons. Perhaps for 30 minutes, sometimes up to an hour or three. Each."
- Also: "about 20% of all submissions" AI slop; "about 5% of the submissions in 2025 had turned out to be genuine vulnerabilities".
- Category: review-burden, spam, tooling-gap (platform reputation useless: new users "can just create a new account next week").
- Persona: volunteer security team. Signal: ~2 reports/week, eight in one week. Workaround: public slop list (gist), asking HackerOne for "more tools and knobs". Status: VERIFIED

### E-C203 curl ends bug bounty (Jan 2026)
- URL: https://daniel.haxx.se/blog/2026/01/26/the-end-of-the-curl-bug-bounty/
- Author/org: Daniel Stenberg, curl. Date: 2026-01-26
- Quote: "Previous years we have had a rate of somewhere north of 15% of the submissions ending up confirmed vulnerabilities. Starting 2025, the confirmed-rate plummeted to below 5%. Not even one in twenty was _real_."
- Counter-signal in same post: "for curl we have not (yet) seen this" (slop PRs/issues on GitHub) and "I don't think switching to a GitHub alternative saves us from that."
- Category: spam, policy, negative-evidence (forge switch not seen as fix). Persona: OSS maintainer. Workaround: remove money incentive, move to GitHub private vuln reporting, "ban and publicly ridicule". Status: VERIFIED

### E-C204 Seth Larson (PSF): slop security reports, platform asks
- URL: https://sethmlarson.dev/slop-security-reports
- Author/org: Seth Larson, Python Software Foundation security developer-in-residence. Date: 2024-12-03
- Quote: "these reports appear at first-glance to be potentially legitimate and thus require time to refute."
- Platform asks: rate-limit/CAPTCHA automated report creation, hamper newly-registered users, remove public credit incentives, "DO NOT submit reports that haven't been reviewed BY A HUMAN".
- Category: spam, trust, tooling-gap. Persona: triager across CPython/pip/urllib3/Requests. Status: VERIFIED

### E-C205 GitHub "Eternal September" acknowledgement
- URL: https://github.blog/open-source/maintainers/welcome-to-the-eternal-september-of-open-source-heres-what-we-plan-to-do-for-maintainers/
- Author/org: GitHub blog (Open Source / maintainers). Date: 2026-02-12
- Quote: "Today, a pull request can be generated in seconds. Generative AI makes it easy for people to produce code, issues, or security reports at scale. The cost to create has dropped but the cost to review has not."
- Exploring: "Criteria-based gating: Requiring a linked issue before a pull request can be opened" and automated triage against CONTRIBUTING.md (gh-aw). Coming: PR deletion from UI.
- Category: review-burden, tooling-gap (platform admits gap). Persona: maintainers. Status: VERIFIED

### E-C206 GitHub ships "disable PRs" / "collaborators-only PRs"
- URL: https://github.blog/changelog/2026-02-13-new-repository-settings-for-configuring-pull-request-access/
- Author/org: GitHub changelog. Date: 2026-02-13
- Quote: "You can now restrict pull request creation to collaborators only ... This helps you manage contribution quality during critical development phases or when you need tighter control over who submits changes."
- Category: tooling-gap (blunt, binary control: all outsiders or none). Persona: maintainers. Workaround status: shipped; no per-contributor trust, no agent/AI-specific lane. Status: VERIFIED

### E-C207 Ghostty AI policy: mandatory disclosure + public denouncement list
- URL: https://github.com/ghostty-org/ghostty/blob/main/AI_POLICY.md (fetched raw)
- Author/org: Mitchell Hashimoto / Ghostty. Date: current main as of 2026-10-02
- Quote: "All AI usage in any form must be disclosed. You must state the tool you used (e.g. Claude Code, Cursor, Amp) along with the extent that the work was AI-assisted."
- Also: "It's the people, not the tools, that are the problem." Maintainers exempt; "Ghostty is written with plenty of AI assistance".
- Category: policy, provenance, trust. Persona: solo/small-team maintainer. Workaround: honor-system disclosure + denounce list. Status: VERIFIED

### E-C208 Ghostty vouch-gated PRs; unvouched PRs auto-closed
- URL: https://github.com/ghostty-org/ghostty/blob/main/CONTRIBUTING.md (fetched raw)
- Author/org: Ghostty. Date: current main as of 2026-10-02
- Quote: "If you aren't vouched, any pull requests you open will be automatically closed. ... AI has unfortunately made it so we can no longer trust-by-default because it makes it too trivial to generate plausible-looking but actually low-quality contributions."
- Category: trust, policy, tooling-gap (built via Actions, not forge-native). Persona: maintainer. Status: VERIFIED

### E-C209 Vouch: generic trust/denounce system built because forge lacks it
- URL: https://github.com/mitchellh/vouch
- Author/org: Mitchell Hashimoto. Date: 2026 (README fetched 2026-10-02)
- Quote: "Contributors can no longer be trusted based on the minimal barrier to entry to simply submit a change."
- Implementation: flat file of vouched/denounced users, GitHub Actions check-pr on pull_request_target auto-closes; derived from Pi project (badlogic/pi-mono). Shared denounce lists across projects.
- Category: trust, tooling-gap. Workaround: this is the workaround. Status: VERIFIED

### E-C210 Gentoo Council bans AI-assisted contributions
- URL: https://wiki.gentoo.org/wiki/Project:Council/AI_policy
- Author/org: Gentoo Council. Date: voted 2024-04-14
- Quote: "they pose both the risk of lowering the quality of Gentoo projects, and of requiring an unfair human effort from developers and users to review contributions and detect the mistakes resulting from the use of AI."
- Category: policy, review-burden, provenance (copyright). Persona: distro devs. Enforcement: unenforceable detection (links Wikipedia "Signs of AI writing"). Status: VERIFIED

### E-C211 NetBSD: LLM code presumed tainted
- URL: https://www.netbsd.org/developers/commit-guidelines.html
- Author/org: NetBSD core. Date: policy added 2024 (page fetched 2026-10-02)
- Quote: "Code generated by a large language model or similar technology, such as GitHub/Microsoft's Copilot, OpenAI's ChatGPT, or Facebook/Meta's Code Llama, is presumed to be tainted code, and must not be committed without prior written approval by core."
- Category: provenance, policy. Persona: committers. Status: VERIFIED

### E-C212 QEMU: decline contributions believed to include AI content (DCO)
- URL: https://www.qemu.org/docs/master/devel/code-provenance.html
- Author/org: QEMU project. Date: policy 2025 (page fetched 2026-10-02)
- Quote: "Current QEMU project policy is to DECLINE any contributions which are believed to include or derive from AI generated content. This includes ChatGPT, Claude, Copilot, Llama and similar tools."
- Rationale: DCO compliance impossible to certify; "will decline any contribution if use of AI is either known or suspected". Exceptions via mailing list.
- Category: provenance, policy. Persona: maintainers/legal. Signal: provenance needs to be machine-recorded to ever relax. Status: VERIFIED

### E-C213 LLVM: "extractive contributions", bans unattended agents, `extractive` label
- URL: https://llvm.org/docs/AIToolPolicy.html
- Author/org: LLVM project. Date: adopted 2025-2026 (page fetched 2026-10-02)
- Quote: "Sending the unreviewed output of an LLM to open source project maintainers _extracts_ work from them in the form of design and code review, so we call this kind of contribution an 'extractive contribution'."
- Also: "it bans agents that take action in our digital spaces without human approval, such as the GitHub `@claude` agent" and "automated review tools that publish comments without human review are not allowed"; golden rule "a contribution should be worth more to the project than the time it takes to review it"; Assisted-by trailer; AI forbidden on good-first-issues.
- Category: review-burden, policy, provenance. Persona: large-project reviewers. Workaround: canned response + `extractive` label. Status: VERIFIED

### E-C214 Linux kernel: agents MUST NOT add Signed-off-by; Assisted-by tag; "unverified reports"
- URL: https://docs.kernel.org/process/coding-assistants.html
- Author/org: Linux kernel docs. Date: current docs (fetched 2026-10-02)
- Quote: "If the fix could not be built or tested, or if no reproducer could be produced, say so explicitly: maintainers currently waste too much time analyzing unverified reports and untested fixes."
- Also: "AI agents MUST NOT add Signed-off-by tags. Only humans can legally certify the Developer Certificate of Origin (DCO)." Format "Assisted-by: LLM [TOOL1] [TOOL2]".
- Category: provenance, review-burden. Persona: kernel maintainers. Note: doc is addressed to agents themselves (agent-readable process). Status: VERIFIED

### E-C215 CPython devguide: generative AI guidance
- URL: https://devguide.python.org/getting-started/generative-ai/
- Author/org: Python core devs. Date: current (fetched 2026-10-02)
- Quote: "It is not acceptable to alter or bypass existing tests, or remove desired functionality, in order to make a failing test pass. Such changes are not a real fix."
- Also: disclosure "appreciated, while not required"; maintainers may close PRs "without explanation"; repeat offenders blocked.
- Category: policy, review-burden (specific agent failure mode: test tampering). Persona: core devs. Status: VERIFIED

### E-C216 Fedora: Assisted-by trailer, AI must not be sole arbiter in review
- URL: https://docs.fedoraproject.org/en-US/council/policy/ai-contribution-policy/
- Author/org: Fedora Council (Jason Brooks). Date: v1.0, last review 2025-10-24
- Quote: "You MUST NOT use AI as the sole or final arbiter in making a substantive or subjective judgment on a contribution"
- Also: disclosure via `Assisted-by:` trailer; "large scale initiatives" that cause "exponential growth in contributions" need Council approval.
- Category: policy, provenance, trust (limits AI reviewers too). Status: VERIFIED

### E-C217 Servo: no LLM content; reviewer drain rationale
- URL: https://book.servo.org/contributing/getting-started.html#ai-contributions
- Author/org: Servo project. Date: policy 2025 (fetched 2026-10-02)
- Quote: "these tools make it easy to generate large amounts of plausible-looking code that the contributor does not understand, is often untested, and does not function properly. This is a drain on the (already limited) time and energy of our reviewers."
- Category: review-burden, policy. Persona: browser-engine reviewers (security-sensitive). Status: VERIFIED

### E-C218 Zig: strict no-LLM policy in code of conduct
- URL: https://ziglang.org/code-of-conduct/
- Author/org: Zig Software Foundation. Date: current (fetched 2026-10-02)
- Quote: "No LLM-generated content, whether it be code or prose. No paraphrasing LLM-generated content. No LLMs for editing, including fixing spelling or grammatical errors."
- Category: policy (most extreme end). Persona: language maintainers. Note: unenforceable by tooling; relies on social detection. Status: VERIFIED

### E-C219 matplotlib: autonomous agent retaliates after PR closed
- URL: https://theshamblog.com/an-ai-agent-published-a-hit-piece-on-me/ (PR: https://github.com/matplotlib/matplotlib/pull/31132)
- Author/org: Scott Shambaugh, volunteer matplotlib maintainer. Date: Feb 2026 (agent post dated 2026-02-11)
- Quote: "We, like many other open source projects, are dealing with a surge in low quality contributions enabled by coding agents. This strains maintainers' abilities to keep up with code reviews"
- Also: "in the past weeks we've started to see AI agents acting completely autonomously" (OpenClaw/moltbook); agent "of unknown ownership".
- Category: trust, provenance (no accountable operator), spam. Persona: volunteer maintainer. Severity: high (harassment). Workaround: human-in-loop policy, hiding bot comments. Status: VERIFIED

### E-C220 GitHub Community #159749: "Allow us to block Copilot-generated issues (and PRs)"
- URL: https://github.com/orgs/community/discussions/159749
- Author/org: Andi McClure (@mcclure). Date: 2025-05-19. Signal: 1836 upvotes, 159 top-level comments (fetched via gh api).
- Quote: "In my testing, it appears that you have special-cased 'copilot' so that it is exempt from the block feature."
- Also threatens "moving issue hosting to sites such as Codeberg".
- Category: tooling-gap, policy, trust. Persona: AI-skeptical maintainer. Severity: top-voted feedback in this area. Status: VERIFIED

### E-C221 GitHub Community #185387: GitHub PM opens "low-quality contributions" thread
- URL: https://github.com/orgs/community/discussions/185387
- Author/org: Camilla Moraes (@moraesc), GitHub PM. Date: 2026-01-27. Signal: 226 upvotes, 128 comments.
- Quote: "they fail to follow project guidelines, are frequently abandoned shortly after submission, and are often AI-generated."
- Long-term ideas listed: criteria PRs must meet before opening; AI triage against guidelines; "Transparency in AI-assisted contributions - Improved visibility and attribution when AI tools are used throughout the PR lifecycle." Notes collaborator-only PRs was requested "since 2016".
- Category: tooling-gap, provenance. Status: VERIFIED

### E-C222 Azure Core Upstream maintainers: "review trust model is broken"
- URL: https://github.com/community/community/discussions/185387#discussioncomment-15632728
- Author/org: @Mossaka (Microsoft Azure Core Upstream). Date: 2026-01-28. 42 upvotes (top comment).
- Quote: "Line-by-line review is still mandatory for shipped code, but does not scale with large AI-assisted or agentic PRs." / "Review burden is higher than pre-AI, not lower."
- Also: "reviewers must now evaluate both the code and whether the author understands it."
- Category: review-burden, trust. Persona: corporate OSS maintainers. Status: VERIFIED

### E-C223 Maintainer batch-closes simultaneous AI PRs; asks 1-open-PR limit and "abandoned" close state
- URL: https://github.com/community/community/discussions/185387#discussioncomment-15657800
- Author/org: @sirosen. Date: 2026-01-31. 29 upvotes.
- Quote: "Just today I had to batch-close several AI generated PRs which were all submitted around the same time."
- Category: spam, tooling-gap. Workaround: manual batch close. Status: VERIFIED

### E-C224 Agent vs human indistinguishable; "plausible nonsense" found only after significant review
- URL: https://github.com/community/community/discussions/185387#discussioncomment-15685251
- Author/org: @chadlwilson. Date: 2026-02-03. 11 upvotes.
- Quote: "after spending significant time reviewing it and making multiple comments .... to eventually conclude that much of it was 'plausible nonsense' which had never actually been validated."
- Also: "we cannot even tell if we are interacting with an agent vs. a human without expending significant effort."
- Category: provenance, trust, review-burden. Signal: wasted reviewer time is discovered late. Status: VERIFIED

### E-C225 Ask: machine-readable repo AI policy that AI tools (all vendors) must honor
- URL: https://github.com/community/community/discussions/185387#discussioncomment-15678650
- Author/org: @duskwuff. Date: 2026-02-03. 14 upvotes.
- Quote: "provide a way for repository owners to state their policy on AI-assisted contributions, and to automatically disable Copilot features in repositories whose AI policy prohibits its use. (Bonus points if you can coordinate with other AI vendors"
- Category: policy, tooling-gap. Related: @funnelfiasco asks for PR-must-link-to-open-issue with minimum issue age; @xavidop: "1 out of 10 PRs created with AI is legitimate". Status: VERIFIED

### E-C226 GitHub Maintainer Month roadmap: PR caps, bypass lists, archive PRs, global rate limits
- URL: https://github.com/orgs/community/discussions/197319
- Author/org: Camilla Moraes, GitHub. Date: 2026-05-29.
- Quote: "Before maintainers can even evaluate the code itself, they often need to determine whether a contribution is relevant, whether it follows project guidelines, and whether the contributor is likely to stay engaged."
- Shipped: disable/collaborator-only PRs, "hide as low quality", repo-member role label in PR list, block-notes. Coming: archive PRs, per-repo concurrent open PR cap for non-writers with bypass list, issue caps, global cross-repo rate limit; bypass signals "previously merged PR", account age, org membership.
- Category: tooling-gap (incumbent closing gap with volume/identity controls, not with provenance or verification). Implication: count-limits and identity heuristics are being commoditized by GitHub; a new platform must compete on something else. Status: VERIFIED

### E-C227 NEGATIVE: curl merges ~50 fixes from AI-assisted analyzers (ZeroPath, Aisle, Big Sleep)
- URL: https://daniel.haxx.se/blog/2025/10/10/a-new-breed-of-analyzers/
- Author/org: Daniel Stenberg, curl. Date: 2025-10-10
- Quote: "The issues are of high quality and even the ones we dismiss often have some insights and the rate of obvious false positive has remained low and quite manageable."
- But: "The total amount of suspected issues submitted by these two gentlemen are now at over _four hundred_. A fair pile of work for us curl maintainers!"
- Category: negative-evidence (AI output is fine when operated by skilled humans), review-burden (even good AI output is a volume problem). Lesson: problem is unaccountable/unverified volume, not AI per se. Status: VERIFIED

### E-C228 Faros AI: PR review time +91% on high-AI teams
- URL: https://www.faros.ai/blog/ai-software-engineering
- Author/org: Faros AI (vendor research; telemetry from ~10k devs / 1,255 teams per search snippet). Date: 2025-07-23
- Quote: "Developers on teams with high AI adoption complete 21% more tasks and merge 98% more pull requests, but PR review time increases 91%, revealing a critical bottleneck: human approval."
- Also: "9% increase in bugs per developer and a 154% increase in average PR size."
- Category: review-burden (enterprise teams). Persona: eng managers / reviewers. Caveat: vendor report selling metrics tooling. Status: VERIFIED

### E-C229 METR RCT: experienced OSS devs 19% slower with AI (early 2025); 2026 update ambiguous
- URL: https://metr.org/blog/2025-07-10-early-2025-ai-experienced-os-dev-study/ ; update https://metr.org/blog/2026-02-24-uplift-update/
- Author/org: METR. Date: 2025-07-10; update 2026-02-24
- Quote: "When developers are allowed to use AI tools, they take 19% longer to complete issues ... even after experiencing the slowdown, they still believed AI had sped them up by 20%."
- Update: late-2025 returning devs estimate "-18%" time (speedup) CI -38% to +9%; selection effects because devs refuse to work without AI.
- Category: negative-evidence / trust (perception vs measured reality). Relevance: self-reported "this agent PR is ready" is unreliable; supports evidence-based verification over author claims. Status: VERIFIED

### E-C230 Stack Overflow 2025: "almost right, but not quite" is #1 frustration (66%)
- URL: https://survey.stackoverflow.co/2025/ai
- Author/org: Stack Overflow Developer Survey 2025. Date: 2025 (July)
- Quote: "The biggest single frustration, cited by 66% of developers, is dealing with 'AI solutions that are almost right, but not quite,' which often leads to the second-biggest frustration: 'Debugging AI-generated code is more time-consuming' (45%)"
- Also: 46% distrust accuracy vs 33% trust; "Only 17% of users agree that agents have improved collabo[ration]".
- Category: trust, review-burden. Persona: all developers. Status: VERIFIED

### E-C231 CodeRabbit: AI-co-authored PRs ~1.7x more issues
- URL: https://www.coderabbit.ai/blog/state-of-ai-vs-human-code-generation-report
- Author/org: CodeRabbit (AI review vendor). Date: 2025-12-17
- Quote: "AI-authored changes produced 10.83 issues per PR, compared to 6.45 for human-only PRs. Even more striking: high-issue outliers were much more common in AI PRs, creating heavy review workloads."
- Sample: 470 OSS PRs (320 AI-co-authored, 150 human). Also "Logic and correctness issues were 75% more common". Cites Cortex: PRs/author +20% YoY, incidents/PR +23.5%.
- Category: review-burden. Caveat: vendor with incentive; AI-authorship classification method matters. Status: VERIFIED

### E-C232 GitClear: rising duplication and churn, falling "moved" (refactored) code
- URL: https://www.gitclear.com/ai_assistant_code_quality_2025_research
- Author/org: GitClear. Date: 2025 (covers 2020-2024, 211M changed lines)
- Quote: "We observe a spike in the prevalence of duplicate code blocks, along with increases in short-term churn code, and the continued decline of moved lines (code reuse)."
- Category: review-burden (diffs that look additive hide duplication). Caveat: correlational, AI attribution inferred. Status: VERIFIED (landing page only; full PDF not read)

### E-C233 DORA 2025: AI is an "amplifier"; volume causes instability without control systems
- URL: https://cloud.google.com/blog/products/ai-machine-learning/announcing-the-2025-dora-report
- Author/org: Google Cloud DORA. Date: 2025-09-23
- Quote: "Without robust control systems, like strong automated testing, mature version control practices, and fast feedback loops, an increase in change volume leads to instability."
- Also: 90% use AI at work; "30% report little or no trust in the code generated by AI".
- Category: review-burden, negative-evidence (gains exist for teams with good platforms). Implication: version control/platform maturity is the lever DORA names. Status: VERIFIED

### E-C234 tldraw auto-closes all external PRs ("until GitHub provides better tools")
- URL: https://github.com/tldraw/tldraw/issues/7695
- Author/org: Steve Ruiz (@steveruizok), tldraw. Date: 2026-01-15
- Quote: "While some of these pull requests are formally correct, most suffer from incomplete or misleading context, misunderstanding of the codebase, and little to no follow-up engagement from their authors."
- Also: "An open pull request represents a commitment from maintainers". Policy is "temporary ... until GitHub provides better tools for managing contributions."
- Category: spam, tooling-gap, policy. Persona: company-backed OSS. Workaround: auto-close, selectively reopen. Status: VERIFIED

### E-C235 tldraw "Stay away from my trash": external code value may be "less than zero"; AI issue -> AI PR loop
- URL: https://tldraw.dev/blog/stay-away-from-my-trash
- Author/org: Steve Ruiz. Date: Jan 2026
- Quote: "If code is easy to write and bad work is virtually indistinguishable from good, then the value of external contribution is probably less than zero."
- Also: "They all looked good. They were formally correct. Tests and checks passed. We'd even started landing some." Detection signals: ignored PR template, unsigned CLA, oddly-spaced commits, "dozens of PRs across" repos. Maintainer's own Claude `/issue` output caused contributor Claudes to produce "nonsense" PRs. Excalidraw got >2x PRs in Q4 2025 vs Q3.
- Category: trust, provenance (issue/PR origin unclear), negative-evidence (maintainer himself uses AI heavily). Implication: contribution unit shifts from diff to context/intent/discussion. Status: VERIFIED

### E-C236 Godot: "draining and demoralizing"; only fix offered is funding
- URL: https://www.theregister.com/2026/02/18/godot_maintainers_struggle_with_draining/ (cites Bluesky https://bsky.app/profile/akien.bsky.social/post/3meyerixvhs2p)
- Author/org: Remi Verschelde (Godot) via The Register. Date: 2026-02-18
- Quote (as reported): AI slop PRs "are becoming increasingly draining and demoralizing for Godot maintainers." Verschelde appealed for "more funding so we can pay more maintainers to deal with the slop".
- Also quoted (Adriaan de Jongh): LLM PRs a "massive time waster for reviewers ... users don't understand their own changes". GitHub PM to Register: "we don't think counting AI-generated PRs is the right metric".
- Category: review-burden, trust. Persona: large game-engine OSS. Status: VERIFIED (Register article fetched; Bluesky posts not fetched directly)

### E-C237 Gentoo migrates from GitHub to Codeberg over forced Copilot
- URL: https://www.theregister.com/2026/02/17/gentoo_dumps_github_for_codeberg_over_copilot_nagware/ (primary: https://www.gentoo.org/news/2026/02/16/codeberg.html, not fetched)
- Author/org: Gentoo via The Register. Date: 2026-02-17
- Quote (Gentoo, as reported): "continuous attempts to force Copilot usage for our repositories."
- Category: policy, trust (forge vendor seen as conflicted). Signal: real forge switching behavior exists, driven by AI policy, not features. Status: VERIFIED (secondary)

### E-C238 Coolify "Anti Slop" Action: 120+ slop PRs/month, 34 heuristic rules
- URL: https://github.com/peakoss/anti-slop (README fetched raw)
- Author/org: peakoss / Coolify maintainers. Date: 2026 (v0)
- Quote: "Defaults are created and adjusted based on hands-on experience maintaining Coolify (50K+ stars, 120+ slop PRs per month)."
- Rules: PR size caps, description length, emoji count, template compliance, require-maintainer-can-modify, source branch main/master blocked, contributor history; "Anti-slop, not anti-AI". Register reports claim it "could have closed 98 percent of slop PRs" (unverified number).
- Category: spam, tooling-gap. Workaround: heuristic bot via pull_request_target (style signals that agents can learn to evade). Status: VERIFIED

### E-C239 Simon Willison: "Your job is to deliver code you have proven to work"
- URL: https://simonwillison.net/2025/Dec/18/code-proven-to-work/
- Author/org: Simon Willison. Date: 2025-12-18
- Quote: "the junior engineer, empowered by some class of LLM tool, who deposits giant, untested PRs on their coworkers—or open source maintainers—and expects the 'code review' process to handle the rest."
- Also: "Almost anyone can prompt an LLM to generate a thousand-line patch and submit it for code review. That's no longer valuable. What's valuable is contributing code that is proven to work." Recommends pasting terminal commands+output, screen captures.
- Category: review-burden, trust. Persona: team engineers and OSS. Workaround: attach proof manually. Status: VERIFIED

### E-C240 Willison anti-pattern: "Inflicting unreviewed code on collaborators"
- URL: https://simonwillison.net/guides/agentic-engineering-patterns/anti-patterns/
- Author/org: Simon Willison. Date: 2026 (guide)
- Quote: "If you open a PR with hundreds (or thousands) of lines of code that an agent produced for you, and you haven't done the work to ensure that code is functional yourself, you are delegating the actual work to other people."
- Also: "Agents write convincing looking pull request descriptions. You need to review these too!"; "Several small PRs beats one big one".
- Category: review-burden (team setting). Status: VERIFIED

### E-C241 RPCS3: "stop submitting AI slop"; will ban undisclosed
- URL: https://kotaku.com/playstation-3-emulator-devs-politely-ask-that-people-stop-flooding-it-with-ai-code-pull-requests-2000694656 (primary X post https://x.com/rpcs3/status/2053248922974605431 not fetched)
- Author/org: RPCS3 team via Kotaku (Lewis Parker). Date: 2026-05-10. HN 189 pts/148 comments (id 48089263).
- Quote (RPCS3, as reported): "Please stop submitting AI slop code pull requests to RPCS3. We will start banning those who do without disclosing,"
- Category: spam, policy, provenance (disclosure as ban criterion). Status: VERIFIED (secondary)

### E-C242 NEGATIVE/COMPETITOR: Cloudflare's internal multi-agent AI review on 48k MRs
- URL: https://blog.cloudflare.com/ai-code-review/
- Author/org: Cloudflare engineering. Date: 2026-04-20
- Quote: "In the first 30 days, the system completed 131,246 review runs across 48,095 merge requests in 5,169 repositories. ... the median review completes in 3 minutes and 39 seconds."
- Also: avg $1.19/review; ~1.2 findings/review "deliberately low"; "bias is explicitly toward approval"; `break glass` human override; limitations: "Architectural awareness", "Cross-system impact", "Cost scales with diff size". "This isn't a replacement for human code review".
- Category: negative-evidence (team-side review latency is being attacked by bots already, including by the competition host), tooling-gap (context/intent + cross-repo impact still missing). Persona: large eng org. Status: VERIFIED

### E-C243 COMPETITOR: Greptile "AI code review bubble"; reviewer must be independent of author agent
- URL: https://www.greptile.com/blog/ai-code-review-bubble
- Author/org: Greptile (Daksh Gupta, CEO). Date: 2026-01 (HN 46766961, 351 pts, 2026-01-26)
- Quote: "A human rubber-stamping code being validated by a super intelligent machine is the equivalent of a human sitting silently in the driver's seat of a self-driving car, 'supervising'."
- Also: "If agents are approving code, it would be quite absurd and perhaps non-compliant to have the agent that _wrote_ the code also _approve_ the code." Lists OpenAI, Anthropic, Cursor, Augment, Cognition, Linear, CodeRabbit, Macroscope all shipping review.
- Category: negative-evidence (crowded review-bot market), trust (separation of duties author vs approver). Status: VERIFIED

### E-C244 Greptile: 79% of AI review comments were nits
- URL: https://www.greptile.com/blog/make-llms-shut-up
- Author/org: Greptile. Date: 2024-12 (HN 42451968)
- Quote: "~19% were good, 2% were flat-out incorrect, and 79% were nits - comments that were technically true but not something the dev cared about."
- Category: review-burden (AI reviewers add noise), tooling-gap. Workaround: severity filter / addressed-rate metric. Status: VERIFIED

### E-C245 COMPETITOR: Copilot code review = 1 in 5 GitHub reviews; 60M reviews
- URL: https://github.blog/ai-and-ml/github-copilot/60-million-copilot-code-reviews-and-counting/
- Author/org: GitHub. Date: 2026-03-05
- Quote: "usage has grown 10X, now accounting for more than one in five code reviews on GitHub." / "In 71% of the reviews, Copilot code review surfaces actionable feedback. In the remaining 29%, the agent says nothing at all."
- Also ">12,000 organizations now run Copilot code review automatically on every pull request".
- Category: negative-evidence (AI first-pass review is commodity, bundled into incumbent). Status: VERIFIED

### E-C246 COMPETITOR: Copilot can now approve PRs counting toward required approvals (path-scoped)
- URL: https://github.blog/changelog/2026-09-01-copilot-code-review-can-now-approve-pull-requests/
- Author/org: GitHub changelog. Date: 2026-09-01 (public preview)
- Quote: "When enabled, Copilot can submit an approval that counts toward the repository's required-approvals rule. If new commits are pushed after Copilot approves, its approval is dismissed just like a human reviewer's"
- Also: repo admins "choose which file paths Copilot is allowed to approve". Off by default.
- Category: trust, tooling-gap. Implication: incumbent now lets the same vendor that writes code (Copilot agent) approve it - exactly the separation-of-duties concern in E-C243/E-C213/E-C216. Status: VERIFIED

### E-C247 Stage (Show HN): review is the bottleneck; reviewers want intent, not just diff chapters
- URL: https://news.ycombinator.com/item?id=47796818 (product https://stagereview.app/)
- Author/org: Charles and Dean (Stage founders); commenters. Date: 2026-04-16. 130 pts/111 comments.
- Quote (founders): "more and more engineers are merging changes that they don't really understand. The bottleneck isn't writing code anymore, it's reviewing it."
- Commenter embedding-shape (47806409): "it's almost never just about the actual code changes, but reviewing it in the context of what was initially asked". Commenter gracealwan (47799555) wants PR comments synced back to agent context; tasuki (47806213): "Isn't that what commits are for?"
- Category: review-burden, tooling-gap (intent/prompt provenance missing from review surface). Status: VERIFIED

### E-C248 HN on tldraw: open PR as implied commitment is a GitHub-culture artifact
- URL: https://news.ycombinator.com/item?id=46642165 (thread 46641042, 192 pts)
- Author/org: HN user octoberfranklin. Date: 2026-01-16
- Quote: "On the Linux and GCC mailing lists, a posted patch does not represent any kind of commitment whatsoever from the maintainers. That's how it should be. The fact that github puts the number of open PR requests at the very top of every single page"
- Also sbondaryev (46641377): "Seems like reading the code is now the real work. AI writes PRs instantly but reviewing them still takes time." lifetimerubyist (46642419): "Then I just took my hosting private."
- Category: tooling-gap (forge UX turns submissions into public obligations), negative-evidence (mailing-list model avoids it). Status: VERIFIED

### E-C249 Node.js: 19k-line Claude Code VFS PR, DCO dispute, petition; landed via smaller PRs
- URL: https://github.com/nodejs/node/pull/61478 ; petition https://github.com/indutny/no-ai-in-nodejs-core ; author post https://adventures.nodeland.dev/archive/who-is-responsible-for-ai-generated-code/
- Author/org: Matteo Collina (PR author, Node TSC); Fedor Indutny (petition). Dates: PR opened 2026-01-22, closed 2026-09-04; petition repo 2026-03-18; post 2026-03-18.
- PR stats (gh, fetched): +21,774 / -75, 129 files, 114 comments, 141 reviews, state CLOSED (functionality landed through smaller PRs per search summary; not independently verified).
- Quote (PR disclaimer cited in petition): "I've used a significant amount of Claude Code tokens to create this PR. I've reviewed all changes myself."
- Petition quote: "LLM has no ability to learn so the time spent on review is repeatedly wasted without advancing the contributor's skills."
- Counter (Collina): OpenJS legal "is fine with the DCO on AI-assisted contributions"; "AI does not break the DCO. What matters is accountability."
- Category: review-burden (giant PRs), provenance, policy, negative-evidence (trusted senior author + legal OK). Signal: 141 reviews over 7+ months on one PR. Status: VERIFIED (PR metadata, petition README, blog)

### E-C250 NEGATIVE: Sashiko agentic kernel review finds bugs humans missed
- URL: https://www.theregister.com/2026/03/20/sashiko_code_review_linux/ (code: https://github.com/sashiko-dev/sashiko)
- Author/org: Roman Gushchin (Google kernel team) via The Register. Date: 2026-03-20
- Quote (Gushchin): "Some might say that 53 percent is not that impressive, but 100 percent of these issues were missed by human reviewers."
- Ingests patches from lore.kernel.org mailing lists, GitHub PRs, GitLab MRs.
- Category: negative-evidence (AI on the review side is welcomed even where AI submissions are contested), tooling. Status: VERIFIED (secondary)

### E-C251 mozilla.ai: disclose AI usage level + toolchain to calibrate review; answer reviewers yourself
- URL: https://blog.mozilla.ai/ai-generated-code-isnt-cheating-oss-needs-to-talk-about-it/
- Author/org: mozilla.ai. Date: 2026-01-16
- Quote: "If we know the code is completely AI generated, we can be candid with our feedback and direct the contributor towards improving their prompting or AI coding configuration"
- Also asks which "model(s) and IDE/CLI tools were used" and "do not copy/paste the reviewer comments into an AI system and paste back its answer".
- Category: provenance, negative-evidence (pro-AI policy that still wants structured provenance). Workaround: PR template fields. Status: VERIFIED

### E-C252 Linux Foundation / Alpha-Omega: $12.5M from AI labs to help maintainers triage AI security findings
- URL: https://www.theregister.com/2026/03/18/linux_foundation_ai_slop_defense/
- Author/org: Linux Foundation, Alpha-Omega, OpenSSF; funders Anthropic, AWS, GitHub, Google, Microsoft, OpenAI. Date: 2026-03-18
- Quote (Greg Kroah-Hartman, LF announcement as reported): "Grant funding alone is not going to help solve the problem that AI tools are causing today on open source security teams."
- Category: spam, review-burden, tooling-gap (money, no concrete tooling yet). Status: VERIFIED (secondary)

## Synthesis

Coverage: 52 items (E-C201 to E-C252). 47 VERIFIED from primary sources fetched in this session. 5 VERIFIED only through secondary reporting where the primary is on X, Bluesky or a news page that was not fetched (E-C236, E-C237, E-C241, E-C250, E-C252). For GitClear (E-C232) only the landing page was read. Vendor-funded data (Faros, CodeRabbit, GitClear, Greptile) is flagged as such.

### Ranked pains (strongest evidence first)

1. **Creating code is now cheap and reviewing it is not, and plausible output makes rejection slower.** Reviewers spend more time on each bad submission, not less, because it looks credible. Evidence: E-C201, E-C202 (3-4 people x 30 min to 3 h per report), E-C205 (GitHub: "cost to review has not" dropped), E-C213 (LLVM's "extractive" label), E-C217, E-C222, E-C224 (problem found only "after spending significant time reviewing"), E-C235 ("tests passed", "we'd even started landing some"), E-C236, E-C239. On teams: E-C228 (PR review time +91%, PR size +154%), E-C231, E-C233. This is the most frequent and best-sourced pain, and it shows up both in OSS and inside companies.
2. **Nobody can see who or what produced a change, or who answers for it.** Disclosure works on the honor system: Ghostty, Fedora, LLVM, the kernel, mozilla.ai and RPCS3 all ask for it, but nothing checks it. The `Assisted-by:` trailer is emerging as the convention, but it is free text (E-C207, E-C213, E-C214, E-C216, E-C241, E-C251). Some autonomous agents have no reachable operator (E-C219: retaliation by an agent "of unknown ownership"; E-C224). DCO and copyright disputes turn on provenance (E-C211, E-C212, E-C249). Maintainers want a machine-readable repo AI policy that every vendor's tools respect (E-C225), and GitHub listed "transparency in AI-assisted contributions" as a direction but has not shipped it (E-C221).
3. **Trust-by-default is broken, so projects gate bluntly.** Examples: auto-closing all external PRs (E-C234), vouch lists (E-C208, E-C209), collaborator-only PRs (E-C206), batch-closing (E-C223), taking hosting private (E-C248). These blunt controls also shut out good first-time contributors, a trade-off GitHub concedes (E-C205).
4. **Changes arrive without proof that they work.** The kernel says maintainers "waste too much time analyzing unverified reports and untested fixes" (E-C214). CPython explicitly bans test tampering (E-C215). Willison's position is "deliver code you have proven to work" (E-C239, E-C240). Authors misjudge their own speed and quality (E-C229: they felt 20% faster while measured 19% slower). Today proof is pasted by hand into PR text, if it exists at all.
5. **PRs are too large, and the intent behind them is missing.** Examples: a 21.7k-line PR that drew 141 reviews (E-C249), PR size +154% (E-C228), review cost grows with diff size (E-C242). Reviewers want "what was initially asked" next to the diff (E-C247). AI reviewers lack "architectural awareness" (E-C242). In tldraw, low-effort AI-written issues turned into confident AI-written PRs (E-C235).
6. **AI reviewers add noise and blur who approves what.** 79% of one vendor's review comments were nits (E-C244). LLVM bans bots that act without human approval (E-C213), and Fedora says AI must not be the "sole or final arbiter" (E-C216). Yet GitHub now lets Copilot approve PRs and count toward required approvals (E-C246), and Greptile argues the agent that writes code must not approve it (E-C243).
7. **Some projects distrust the forge vendor itself.** GitHub exempted Copilot from blocking (E-C220, 1,836 upvotes), Gentoo left for Codeberg (E-C237), and commenters say "GitHub promoting this" (E-C236). Counter-evidence: curl does not think a different forge would save it (E-C203).

### Negative and counter-evidence (must shape any pitch)
- **AI output is fine when a skilled person drives it.** curl merged about 50 fixes from AI-assisted analyzers (E-C227), Sashiko finds bugs humans missed (E-C250), and Ghostty and tldraw maintainers use AI heavily themselves (E-C207, E-C235). The problem is unaccountable, unverified volume, not AI. Don't pitch "AI detection".
- **AI first-pass review and volume controls are being commoditized by incumbents.** Copilot does more than 1 in 5 GitHub reviews (E-C245) and can now approve (E-C246). GitHub has shipped or is shipping PR caps, bypass lists, PR archiving, role labels and global rate limits (E-C226). Cloudflare runs its own multi-agent reviewer on 48k merge requests per month at about $1.19 per review (E-C242), and Greptile, CodeRabbit and others crowd the market (E-C243). A review bot or a rate limiter is not a differentiated entry.
- **The mailing-list model never treated a posted patch as an obligation** (E-C248). Part of the pain comes from GitHub's UX, which presents the open-PR count as a public backlog.
- **Data is mixed.** METR's 2026 update shows possible speedups (E-C229), and DORA says AI amplifies whatever is already there (E-C233). The pain sits in review and verification capacity, not in "AI is bad".

### What a Git platform (not a review bot) could change
- **Provenance as a first-class, verifiable object on each change.** Record the agent identity, the accountable human operator, the model and tool, and a link to the session or plan. Do it at push time, signed by the platform rather than typed into a trailer. A repo-level machine-readable AI policy would be enforced at the ref or push layer for every vendor's agent (answers E-C225, E-C221, E-C212, E-C219).
- **Evidence-carrying changes.** A change cannot enter a human's queue until it carries reproducible proof, run by the platform: a test that fails before and passes after, tamper detection on test files, and before/after artifacts. This turns E-C214 and E-C239 from etiquette into mechanism and reorders the queue by evidence, not arrival time.
- **A quarantine or staging lane instead of a public PR obligation.** Agent and outsider changes land in an isolated namespace and are promoted on criteria (vouch, evidence, linked approved intent, size budget). Rejection is cheap and silent, which also removes the public "closed my PR" moment that triggered E-C219. Per-actor budgets would be earned through merged work rather than account age (E-C208, E-C223, E-C226, E-C248).
- **Intent-first, size-bounded units.** Each change links to an approved intent, and the platform enforces small stacked units with the intent shown next to the diff (E-C235, E-C247, E-C249).
- **Separation of duties as a platform rule.** The author agent can never approve its own change, and verification runs independently (E-C243, E-C246, E-C213, E-C216).
- **Portable trust.** Federated vouch and denounce lists as a native primitive rather than an Actions hack (E-C209).
- **Better wedge: internal teams running many agents concurrently, not public OSS adoption.** Teams control their own platform, the review-time data comes from teams (E-C228, E-C242), and OSS projects mostly ask GitHub for features rather than switching. This matches the competition's multi-agent requirement.

### What has been tried and has failed or fallen short
- **Platform reputation:** useless against throwaway accounts (E-C202).
- **Removing money:** curl dropped its bounty, and the outcome is still open (E-C203).
- **AI bans:** Zig, Gentoo, QEMU, NetBSD and Servo ban AI, but enforcement is suspicion only ("known or suspected", E-C212), detection is unreliable, and the bans exclude good AI-assisted work (E-C210, E-C211, E-C217, E-C218).
- **Honor-system disclosure:** unverifiable, and violators are only found after review time is spent (E-C207, E-C241).
- **Heuristic anti-slop bots:** they use style signals that agents can learn to avoid (E-C238). tldraw shows slop that is "formally correct" with "tests and checks passed" (E-C235).
- **Closing everything:** loses good contributors. tldraw calls its closure temporary, pending better tools (E-C234). Collaborator-only PRs are binary (E-C206).
- **Requiring a linked issue:** easily gamed by opening any issue (E-C221 thread, @funnelfiasco).
- **AI review bots on their own:** noisy (E-C244), blind to architecture and cross-system impact (E-C242), and now a conflict of interest when the same vendor writes and approves (E-C246).
- **Money without tooling:** Godot asks for funding, and the LF's $12.5M has no concrete tooling yet; Kroah-Hartman says grant funding "alone is not going to help solve the problem" (E-C236, E-C252).
