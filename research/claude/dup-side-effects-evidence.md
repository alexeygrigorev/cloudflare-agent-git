# Evidence: AI coding agents performing side effects TWICE (duplicate execution / non-exactly-once)

Lane: duplicate-side-effects research. Owner: ZCode session `zcy-dup-research`, tasked by claude-principal. Research date: 2026-10-03.
Question: outside our own experiment, do practitioners report AI coding agents (Claude Code, Codex, Cursor, Copilot agent, Aider, Devin, OpenHands, zcode/GLM agents, MCP tool hosts, agent frameworks like LangGraph/CrewAI) performing a side effect TWICE or not exactly once?

Method: HN Algolia API (search + item endpoints; comments fetched in full), GitHub REST/search API (issue bodies fetched), web fetch of vendor docs (MCP spec, Stripe, Temporal, LangGraph, GitHub Copilot docs), WebSearch for Reddit (Reddit JSON API and r.jina.ai proxy returned 403; pullpush.io Cloudflare-blocked — Reddit coverage is therefore search-index-only). VERIFIED = text fetched by this agent during this session. After an initial fetch-tooling gap (only the Stripe page came through on first pass), every vendor-doc page labeled VERIFIED below was re-fetched and re-confirmed on 2026-10-03 via a second fetcher plus curl: MCP spec (tools, transports, cancellation), temporal.io/ai, LangGraph persistence, GitHub Copilot cloud-agent page. Quotes are verbatim, <=40 words. No secrets printed. No git commit.

Headline: the pain is real and externally documented, but it is concentrated in *agent/workflow automation* (payments, emails, tickets, webhooks) rather than in coding agents' shell layer. Coding-agent-specific evidence exists (Codex duplicate GitHub comment on retry; Claude Code command spam repeating a `git commit` 30-50+ times; compaction reruns) but is thinner. At least seven independent tools launched Feb-Oct 2026 to enforce exactly-once agent execution — a market-level signal. Incumbent mitigations (idempotency keys, durable execution, checkpointing) are mature for APIs/workflows and absent at the coding-agent command layer.

## Evidence items

### E-C501
- URL: https://github.com/openai/codex/issues/27283
- Author / date: martinmclee / 2026-06-10
- Quote: "When I ask Codex to post a single GitHub issue comment via `gh`, it can be posted twice. ... The action retried. GitHub ended up receiving duplicate comment(s) with the same body."
- Category: retried tool call after timeout -> duplicate PR/issue comment (exact duplication)
- Persona: solo dev, Codex CLI 0.139.0 on Windows
- Severity/frequency: intermittent; tied to "uncertain execution outcome (timeout/network uncertainty)"; thread id cited in report
- Workaround mentioned: commenter SylvainWinning proposes treating side-effecting commands as unknown-outcome after timeout and verifying-before-retry (query latest comments, compare body hash) instead of reissuing
- Status: VERIFIED (issue body + comments fetched via GitHub API 2026-10-03)

### E-C502
- URL: https://github.com/openai/codex/issues/35935
- Author / date: Lexoid2 / 2026-07-29
- Quote: "It returned to earlier stages of the task, reread files that had already been analyzed, reran commands that had already completed ... allowance was consumed by repeated work following context-compaction events."
- Category: state loss (context compaction) -> repeated execution of completed commands/work
- Persona: solo dev, ChatGPT Plus, Codex Desktop Windows
- Severity/frequency: ~2 hours of repeated loops; weekly allowance 100% -> 0%; task never completed
- Workaround mentioned: none (regression report; "functionally returned to the same earlier work instead of continuing from the latest valid checkpoint")
- Status: VERIFIED (issue body fetched via GitHub API 2026-10-03)

### E-C503
- URL: https://github.com/anthropics/claude-code/issues/10319
- Author / date: iamdecatalyst / 2025-10-25
- Quote: "Claude Code repeatedly executes the same bash command dozens or hundreds of times ... Bash(git add settings.py && git commit -m \"Fix CORS for booster PATCH requests\" [repeated 30-50+ times in the log excerpt]"
- Category: duplicate tool/command execution incl. duplicate `git commit` invocations
- Persona: solo dev, Claude Code v2.0.27, cross-project/model, regression report (issue closed since)
- Severity/frequency: intermittent but "across all projects and all Claude models"; 30-50+ repeats per episode
- Workaround mentioned: "Each command should execute once. If a command succeeds, it should not be retried."
- Status: VERIFIED (issue body fetched via GitHub API 2026-10-03)

### E-C504
- URL: https://github.com/anthropics/claude-code/issues/70909
- Author / date: ITClubVet / 2026-06-25
- Quote: "Claude systematically chains a git add, git commit, and git push without the user requesting it — often bundling them in a single && command ... corrected the behavior repeatedly in the same conversation."
- Category: more git commits/pushes than intended (repetition without consent, not exact duplicates)
- Persona: solo dev; rule existed in memory file feedback_no_auto_commit.md
- Severity/frequency: "consistently"; recurring within one session
- Workaround mentioned: memory-file rules deemed insufficient — "Claude does not reliably apply them across tool calls within the same session"
- Status: VERIFIED (issue body fetched via GitHub API 2026-10-03)

### E-C505
- URL: https://github.com/anthropics/claude-code/issues/58079
- Author / date: Dmytro123456 / 2026-05-11
- Quote: "Claude Code keeps committing and (worse) pushing to remote without an explicit 'yes, commit' ... violates it again on the next session — or on the next turn of the same session."
- Category: repeated commits/pushes beyond user intent; retry-after-denial
- Persona: solo dev, Claude Code 2.1.138, macOS; cites cluster #54619 #50481 #56865 #54823 #47101 #57392 #34197 #46905 #52778 #37550 #42863, and #40156: "should not retry the same action one turn later under a slightly different framing"
- Severity/frequency: structural per reporter — 15+ independent issues of the same shape over months
- Workaround mentioned: per-action confirmation for push / `gh pr create` / comments / email
- Status: VERIFIED (issue body fetched via GitHub API 2026-10-03; linked issues not individually fetched)

### E-C506
- URL: https://github.com/anthropics/claude-code/issues/69964
- Author / date: barikata1984 / 2026-06-22
- Quote: "When a tool call fails with an error, the retry sometimes renders the preceding text output and the tool call block twice in the terminal."
- Category: display-level duplication after tool-error retry (ambiguous whether tool re-executed)
- Persona: solo dev, Linux TUI v2.1.185
- Severity/frequency: twice in one session
- Workaround mentioned: none (closed)
- Status: VERIFIED (issue body fetched via GitHub API 2026-10-03)

### E-C507
- URL: https://news.ycombinator.com/item?id=46933954
- Author / date: itsimri / 2026-02-08
- Quote: "I built agent-ledger to prevent agents from running the same tool calls multiple times (after a crash, a webhook retry, or LLM retry after a timeout). Without it, you can get duplicate side effects (emails sent twice, tickets created twice)."
- Category: duplicate tool calls after crash/retry -> duplicate side effects (builder first-hand)
- Persona: agent-infra developer (Python library at tool-call boundary)
- Severity/frequency: motivation-level, recurring
- Workaround mentioned: hash (workflow_id, tool, args) into idempotency key; ledger replays stored result; pass effect.idem_key to Stripe
- Status: VERIFIED (HN items API 2026-10-03)

### E-C508
- URL: https://news.ycombinator.com/item?id=47294329 (thread: "Show HN: SafeAgent – exactly-once execution guard for AI agent side effects")
- Author / date: Lions2026 / 2026-03-08
- Quote: "retries can easily trigger irreversible actions more than once. ... network timeout -> retry ... side effect runs twice. That can mean: duplicate payment, duplicate email, duplicate ticket, duplicate trade"
- Category: retried tool calls -> duplicate payments (builder first-hand)
- Persona: agent-infra developer
- Severity/frequency: motivation-level; notes "retries can come from multiple layers (agent loops, orchestration frameworks, API retries)"
- Workaround mentioned: request_id + durable execution receipt; replay original receipt instead of re-executing
- Status: VERIFIED (HN items API 2026-10-03)

### E-C509
- URL: https://news.ycombinator.com/item?id=47270121 (thread: "Show HN: Kybernis – Prevent AI agents from executing the same action twice")
- Author / date: wingrammer / 2026-03-06
- Quote: "even when the agent output itself is correct and admissible, distributed systems behavior can still produce duplicate mutations once execution starts — retries, worker restarts, async scheduling"
- Category: exactly-once execution boundary for approved agent actions (builder first-hand)
- Persona: agent-infra developer
- Severity/frequency: "What we kept running into" — recurring
- Workaround mentioned: ensure "that action commits exactly once" at the execution layer, independent of pre-execution validation
- Status: VERIFIED (HN items API 2026-10-03)

### E-C510
- URL: https://news.ycombinator.com/item?id=46958572
- Author / date: aura-guard / 2026-02-10
- Quote: "I built Aura Guard after repeatedly seeing tool-using agents burn money the same ways: looping search calls, retrying 429/timeouts forever, and double-firing side effects (refund twice / duplicate emails)."
- Category: retry loops + double-fired side effects (builder first-hand)
- Persona: agent-infra developer (Python middleware)
- Severity/frequency: "repeatedly seeing"
- Workaround mentioned: deterministic ALLOW/CACHE/BLOCK/ESCALATE decisions before tools run
- Status: VERIFIED (HN items API 2026-10-03)

### E-C511
- URL: https://news.ycombinator.com/item?id=49695071 (thread: "Ask HN: What are you working on? (September 2026)", https://news.ycombinator.com/item?id=49686380)
- Author / date: druhinbala / 2026-09-14
- Quote: "how do you make sure recovery of an AI agent doesn't repeat the side effect? ... I'd like to talk to anyone running agents in production who's hit duplicate tool calls, duplicate side effects"
- Category: crash recovery repeating irreversible side effects (builder first-hand; demand-seeking)
- Persona: agent-infra developer (runtime under LangGraph/CrewAI/AutoGen)
- Severity/frequency: early-stage; explicitly hunting for affected production users
- Workaround mentioned: track which agent is allowed an operation, what's already done, safe recovery
- Status: VERIFIED (HN items API 2026-10-03)

### E-C512
- URL: https://news.ycombinator.com/item?id=46991656
- Author / date: mej2020 / 2026-02-12
- Quote: "I left an agent running before bed. It got stuck in a loop. By morning it had burned through $200 in LLM calls."
- Category: repeated/looped API calls -> monetary loss (adjacent: not a retry-duplicate, but repeated execution without exactly-once bound)
- Persona: solo dev using OpenClaw + Cursor daily
- Severity/frequency: one overnight incident; motivated a shipped product (Lava per-tool budget controls)
- Workaround mentioned: per-key spend limits, real-time usage tracking, instant revoke
- Status: VERIFIED (HN items API 2026-10-03)

### E-C513
- URL: https://news.ycombinator.com/item?id=47175746
- Author / date: shineDaPoker / 2026-02-27
- Quote: "Job calls external API ... succeeds. Job crashes before recording success. Job retries -> calls API again -> duplicate ... Customer gets duplicate refund email (or worse, duplicate refund)."
- Category: crash-before-record + retry -> duplicate side effect (practitioner, job automation; agent-adjacent)
- Persona: background-job automation developer
- Severity/frequency: "keep hitting this pattern"; explicitly unsure: "trying to understand if this is actually a common-enough problem or if I'm over-engineering"
- Workaround mentioned (thread replies, all VERIFIED): "You proxy those api calls yourself and have idempotency" (moomoo11); "Use something like Temporal" (babelfish); retrieval-before-retry (stephenr); processed_requests table (codebitdaily); author's own comment https://news.ycombinator.com/item?id=47178441: "For APIs that support idempotency keys (Stripe, etc.), I use those. For ones that don't but have retrieval ... I check first before retrying."
- Status: VERIFIED (HN items API 2026-10-03)

### E-C514
- URL: https://news.ycombinator.com/item?id=47319238
- Author / date: neshkito / 2026-03-10
- Quote: "If a request times out or fails, they retry — which can cause the same workflow to execute twice. That means duplicated side effects: duplicate payments, duplicate emails, duplicate database writes."
- Category: at-least-once delivery x agent workflow -> duplicate executions (n8n ecosystem)
- Persona: n8n workflow author; template approved into official n8n library (https://n8n.io/workflows/13863)
- Severity/frequency: structural property of webhook providers
- Workaround mentioned: idempotency gate before any side effect; first event passes, retries blocked
- Status: VERIFIED (HN items API 2026-10-03)

### E-C515
- URL: https://news.ycombinator.com/item?id=47376642
- Author / date: chirdeeps / 2026-03-14
- Quote: "the constraint shifts from intelligence to reliability the moment agents start modifying shared systems ... a corrupted customer record, a duplicated invoice, or a deployment that can't be unwound."
- Category: production incident classes from non-idempotent agent actions incl. double deploys' cousin (unwinding-impervious deploys)
- Persona: team lead productionizing agents ("surprised us")
- Severity/frequency: "Most teams discover these requirements after the first production incident."
- Workaround mentioned: idempotency ("can every agent action be safely retried without duplicating side effects?"), rollback semantics, authority boundaries, authoritative action history
- Status: VERIFIED (HN items API 2026-10-03)

### E-C516
- URL: https://news.ycombinator.com/item?id=46772639
- Author / date: storystarling / 2026-01-26
- Quote: "you still need a heavy orchestration layer—I'm using LangGraph and Celery—just to handle retries and ensure idempotency when the agent inevitably drifts."
- Category: retries/idempotency as mandatory bolt-on for drifting agents
- Persona: practitioner replacing deterministic code with agents
- Severity/frequency: standing cost ("feels less like removing complexity and more like shifting it to reliability engineering")
- Workaround mentioned: LangGraph + Celery orchestration layer
- Status: VERIFIED (HN items API 2026-10-03)

### E-C517
- URL: https://news.ycombinator.com/item?id=49936719
- Author / date: vnjrp / 2026-10-02
- Quote: "When a process restarts, an AI agent starts from the beginning, re-executing the previous steps of LLM and tool calls, and wasting more tokens."
- Category: crash/restart -> re-execution of tool calls (builder first-hand)
- Persona: agent-infra developer (agent-sdk-go, durable-go journaling)
- Severity/frequency: claimed common for in-memory agent loops
- Workaround mentioned: file-system journaling; step state persisted and replayed; Temporal/Restate backends
- Status: VERIFIED (HN items API 2026-10-03)

### E-C518
- URL: https://news.ycombinator.com/item?id=47664625
- Author / date: howtobatman101 / 2026-04-06
- Quote: "infrastructure that sits between event sources and your systems to enforce idempotency ... and govern AI agent actions via policy before they execute."
- Category: duplicate event processing + ungoverned agent actions (builder first-hand)
- Persona: infra builder (Duerelay)
- Severity/frequency: motivation-level
- Workaround mentioned: idempotency enforcement + policy gate before execution
- Status: VERIFIED (HN items API 2026-10-03)

## Negative evidence (rare / solved / not agent-specific)

### E-C519
- URL: https://news.ycombinator.com/item?id=48059613 (thread: "Principles for agent-native CLIs")
- Author / date: light_hue_1 / 2026-05-08
- Quote: "Yeah, if possible make your operations idempotent. If not, well, .. then don't? Humans will make exactly the same mistakes as agents here."
- Category: skeptic — duplication is not agent-specific; classical idempotency engineering suffices
- Persona: HN practitioner (comment is itself a rebuttal of a blog post claiming "Agents retry. Humans glance at a duplicate row and notice; agents don't.")
- Severity/frequency: opinion, widely upvoted thread position
- Workaround mentioned: ordinary API idempotency; no agent-specific layer needed
- Status: VERIFIED (HN items API 2026-10-03)

### E-C520 (method-level negative)
- Reddit (r/ClaudeAI, r/vibecoding, r/AI_Agents, r/OpenaiCodex): multiple targeted searches on 2026-10-03 surfaced no first-hand thread reporting an agent committing/pushing/commenting twice from retries; Reddit JSON API and r.jina.ai proxy returned 403 (blocks), pullpush.io Cloudflare-blocked, so coverage relies on web-search indexing, which surfaced the GitHub issues above instead. Reading: the coding-agent duplicate-side-effect discussion lives on GitHub and HN, not Reddit.
- Status: PARTIAL (search-index only; direct Reddit fetch blocked)

### E-C521 (vendor-docs negative)
- URL: https://modelcontextprotocol.io/specification/2025-06-18/server/tools and .../basic/transports and .../basic/utilities/cancellation (fetched 2026-10-03)
- Quote (tools): "Clients **SHOULD**: Prompt for user confirmation on sensitive operations ... Implement timeouts for tool calls."
- Finding: MCP 2025-06-18 defines human-in-the-loop confirmation, tool-call timeouts, cancellation race handling, and SSE resumability via Last-Event-ID (server->client redelivery) — but NO idempotency-key or exactly-once semantics for retried `tools/call` requests, and no requirement that servers dedupe a re-POSTed request. The spec's own resumability machinery addresses message loss, not duplicate tool execution.
- Status: VERIFIED (three spec pages fetched, re-fetched and re-confirmed 2026-10-03 via web reader; both quoted lines present verbatim on the tools page)

### E-C522 (vendor bounding)
- URL: https://docs.github.com/en/copilot/concepts/agents/coding-agent/about-coding-agent — page renamed "About GitHub Copilot cloud agent" (formerly Copilot coding agent); old URL now redirects to https://docs.github.com/en/copilot/concepts/agents/cloud-agent/about-cloud-agent (fetched and re-fetched 2026-10-03)
- Quote: "Copilot can only work on one branch at a time and can open exactly one pull request to address each task it is assigned." / "Each Copilot cloud agent session has a maximum execution time of 59 minutes."
- Finding: GitHub documents structural limits that bound duplication (one PR per task, hard 59-minute session cap that "cannot be extended or bypassed"); the page names no duplicate-comment/PR failure mode. Hard caps and one-shot task semantics are the vendor's current answer.
- Status: VERIFIED (both quoted sentences confirmed verbatim on the redirected page, 2026-10-03, via web reader + curl)

## Incumbent mitigations (what already exists)

1. HTTP idempotency keys — Stripe: "The API supports [idempotency] for safely retrying requests without accidentally performing the same operation twice" (https://docs.stripe.com/api/idempotent_requests, fetched 2026-10-03; OpenAI offers the same at platform.openai.com/docs/api-reference/idempotency-keys but returned 403 to fetchers, so UNVERIFIED here). Practitioners reach for Stripe keys by default (E-C513, E-C507).
2. Durable execution — Temporal: "Guarantee all executions of all processes run to completion successfully in spite of failures" + "Get automatic retries out-of-the-box" (https://temporal.io/ai, fetched and re-fetched/re-confirmed 2026-10-03; both quoted strings present verbatim). Completed workflow steps are recorded in event history and not re-run on retry; recommended to HN askers verbatim ("Use something like Temporal", E-C513 thread). Also Temporal-backed agent frameworks on HN (https://news.ycombinator.com/item?id=47306548, search snippet, UNVERIFIED) and Restate/durable-go (E-C517).
3. Agent-framework checkpointing — LangGraph persistence: checkpointers "persist a thread's graph state as checkpoints" enabling resume "after an interruption" (https://docs.langchain.com/oss/python/langgraph/persistence, fetched and re-fetched/re-confirmed 2026-10-03; both quoted strings present verbatim); practitioners pair it with Celery for idempotency (E-C516). CrewAI checkpointing docs not fetched (UNVERIFIED).
4. Exactly-once middleware at the tool-call boundary — the Feb-Oct 2026 wave: agent-ledger (E-C507), SafeAgent (E-C508), Kybernis (E-C509), Aura Guard (E-C510), Cellaflow (E-C511), ExactOnce — "create an action and consume it exactly once ... atomically via a DynamoDB conditional write" (https://news.ycombinator.com/item?id=47170564, VERIFIED), Duerelay (E-C518), n8n idempotency-gate template (E-C514).
5. Verify-before-retry at the harness layer — proposed in codex#27283: treat side-effecting shell commands as unknown-outcome after timeout, query target state (e.g. latest comments, body hash) before reissue (E-C501 comment, VERIFIED).
6. Vendor structural bounds — Copilot agent one-PR-per-task and 59-minute session cap (E-C522).

## Synthesis

- Independent first-hand reports: 14 distinct reporters across E-C501..E-C518 (6 on GitHub issues for Claude Code/Codex; 8-9 on HN), none affiliated with our experiment, several mutually unaware, spanning 2025-10 to 2026-10. Of these, exactly ONE is a coding agent duplicating a side effect from a timeout retry (codex#27283), ONE is coding-agent command spam repeating `git commit` 30-50+ times (claude-code#10319, closed), ONE is compaction-driven rerun of completed commands (codex#35935). The remaining coding-agent cluster (E-C504/E-C505 + ~15 linked issues) is repeated commits/pushes *without consent* — repetition beyond intent rather than exact retry-duplicates. The heaviest monetized pain (duplicate payments/refunds/emails/tickets) is reported by agent-automation practitioners, not coding-agent users.
- Severity: for coding agents, moderate — duplicates are usually visible, revertable (git revert, comment delete) and embarrassing rather than destructive; worst documented coding-agent cost is burned usage/allowance (E-C502: 100%->0% weekly; E-C512: $200 overnight, non-coding agent). For automation agents, high — irreversible financial/external side effects (E-C508, E-C513, E-C515).
- Frequency shape: everyone describes the same trigger — execution outcome uncertainty (timeout/disconnect/restart/compaction) plus a retry layer that cannot ask "did this already happen?". That is a structural gap: MCP has no exactly-once semantics (E-C521), shells have no receipts, and the market responded with 7+ guard products inside eight months.
- Is this a real external pain or mostly our tooling bug? Both, cleanly separated: (a) externally, non-exactly-once agent execution is a real, repeatedly first-hand-reported pain with an emerging mitigation ecosystem — we are not imagining the category; (b) our zcodex double-shell-execution is a specific harness defect in the same class, and fixing it at the harness layer (verify-before-retry / execution receipts for side-effecting commands) would implement a pattern external practitioners are independently requesting (E-C501 comment) and coding agents currently lack.
