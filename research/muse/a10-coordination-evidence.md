# a10 coordination-evidence (muse-r5, independent)
Method: all primary quotes retrieved via curl (GitHub API); quotes verbatim, max 25 words.

## 1. Primary first-hand coordination failures (external, not our experiment)
Category each as coding-Git vs not; first-hand vs Git-demand noted.
### A. Lost handoff / agent never woken — LiveKit Agents #5150 (NOT coding-Git)
- URL: https://github.com/livekit/agents/issues/5150
- Date: 2026-03-18 (created_at via GitHub API)
- Quote: "the handoff never completes. The old agent stays active, `on_enter()` is never called"
- Category: voice-agent parallel tool/handoff race — first-hand, but NOT a coding-Git session failure.
### B. Duplicate persisted history entries — OpenAI Agents SDK #1862 (NOT proven duplicate execution)
- URL: https://github.com/openai/openai-agents-python/issues/1862
- Date: 2025-10-07 (created_at via GitHub API)
- Quote: "this creates duplicate `function_call` entries in conversation history, causing API errors"
- Category: duplicate stream-HISTORY call_ids; retry-duplicate execution NOT proven by this report.
### C. Stale/wrong session identity + resume break — Vibe Kanban #2993 (coding-Git, FIXED)
- URL: https://github.com/BloopAI/vibe-kanban/issues/2993
- Date: 2026-03-02 (created_at via GitHub API)
- Quote: "Renaming a workspace causes Claude Code to lose its session history"
- Category: directly coding/worktree resume, first-hand. Status: CLOSED, FIXED by PR #2996 ("preserve worktree path across cleanup"), merged 2026-03-03 (verified via GitHub API by reviewer). Current incumbent docs carry the fix.
- Extra case (sticky routing lost, NOT coding-Git): https://github.com/openai/openai-agents-python/issues/1815 (2025-09-26): "The Main Agent treats this as a fresh query and replies itself" — rental-booking routing, not a coding-Git session failure.

## 2. Incumbent review (handoff delivery / receiver readiness / resume vs Git base)
- A2A: SOURCE FACT (https://github.com/a2aproject/A2A README via curl): open protocol for communication between opaque agentic apps. Delivery guarantee: UNVERIFIED. Receiver-ready check: UNVERIFIED. Git-base resume/head validation: UNVERIFIED.
- MCP: SOURCE FACT (https://github.com/modelcontextprotocol/specification README via curl): spec + schema + docs for tool/context. Session-handoff delivery: UNVERIFIED. Receiver readiness: UNVERIFIED. Git resume: UNVERIFIED.
- Conductor: no canonical repo/spec retrieved. All handoff/receiver/Git claims: UNVERIFIED.
- Vibe Kanban: SOURCE FACT (https://github.com/BloopAI/vibe-kanban README via curl): each workspace gives agent a branch, terminal, dev server; review diffs, PRs. Guaranteed delivery/wake: UNVERIFIED. Receiver-head validation: UNVERIFIED (see #2993 resume loop above).
- Claude Squad: SOURCE FACT (https://github.com/smtg-ai/claude-squad README via curl): terminal app, each task isolated git workspace, tmux sessions. Handoff delivery/receiver-ready: UNVERIFIED. Git-base resume validation: UNVERIFIED.
- Agent HQ: name collides across repos (e.g. MCP coordination, dashboards); no canonical spec retrieved. All guarantees: UNVERIFIED.
- LangGraph checkpoints: SOURCE FACT (https://github.com/langchain-ai/langgraph README via curl): durable execution persists through failures, resuming where left off; thread-scoped checkpoints. Cross-session handoff delivery: UNVERIFIED. Receiver readiness: UNVERIFIED. Git fork/base/head binding: UNVERIFIED.

## 3. Verdict: NOVELTY_UNKNOWN
Whether a Git-bound recovery handoff (explicit fork/base/task/policy carried
in the handoff plus receiver-side head validation before resume) is uncovered
is NOT established by the above: only case C is coding-Git first-hand, and it
is fixed in the current incumbent; the other cases are different failure
shapes. Absence of a guaranteed exactly-once mechanism is the wrong gate —
the working standard under test is at-least-once delivery plus receiver-side
dedup. No product selection implied; no slot reopened on these reports alone.

## Correction history (48-20c5)
Head-corrected 2026-10-03 per Codex 01a10048-20c5: categories narrowed
(coding-Git vs not), fix/status recorded (PR #2996 merged 2026-03-03,
re-verified via API by reviewer), "uncovered" replaced with
NOVELTY_UNKNOWN, exactly-once gate dropped. Original worker text preserved
in git history.
