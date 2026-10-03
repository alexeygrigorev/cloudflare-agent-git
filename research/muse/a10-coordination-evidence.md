# a10 coordination-evidence (muse-r5, independent)
Method: all primary quotes retrieved via curl (GitHub API); quotes verbatim, max 25 words.

## 1. Primary first-hand coordination failures (external, not our experiment)
### A. Lost handoff / agent never woken — LiveKit Agents #5150
- URL: https://github.com/livekit/agents/issues/5150
- Date: 2026-03-18 (created_at via GitHub API)
- Quote: "the handoff never completes. The old agent stays active, `on_enter()` is never called"
### B. Duplicated handoff after retry/persist — OpenAI Agents SDK #1862
- URL: https://github.com/openai/openai-agents-python/issues/1862
- Date: 2025-10-07 (created_at via GitHub API)
- Quote: "this creates duplicate `function_call` entries in conversation history, causing API errors"
### C. Stale/wrong session identity + resume break — Vibe Kanban #2993
- URL: https://github.com/BloopAI/vibe-kanban/issues/2993
- Date: 2026-03-02 (created_at via GitHub API)
- Quote: "Renaming a workspace causes Claude Code to lose its session history"
- Extra verified case (sticky routing lost): https://github.com/openai/openai-agents-python/issues/1815 (2025-09-26): "The Main Agent treats this as a fresh query and replies itself"

## 2. Incumbent review (handoff delivery / receiver readiness / resume vs Git base)
- A2A: SOURCE FACT (https://github.com/a2aproject/A2A README via curl): open protocol for communication between opaque agentic apps. Delivery guarantee: UNVERIFIED. Receiver-ready check: UNVERIFIED. Git-base resume/head validation: UNVERIFIED.
- MCP: SOURCE FACT (https://github.com/modelcontextprotocol/specification README via curl): spec + schema + docs for tool/context. Session-handoff delivery: UNVERIFIED. Receiver readiness: UNVERIFIED. Git resume: UNVERIFIED.
- Conductor: no canonical repo/spec retrieved. All handoff/receiver/Git claims: UNVERIFIED.
- Vibe Kanban: SOURCE FACT (https://github.com/BloopAI/vibe-kanban README via curl): each workspace gives agent a branch, terminal, dev server; review diffs, PRs. Guaranteed delivery/wake: UNVERIFIED. Receiver-head validation: UNVERIFIED (see #2993 resume loop above).
- Claude Squad: SOURCE FACT (https://github.com/smtg-ai/claude-squad README via curl): terminal app, each task isolated git workspace, tmux sessions. Handoff delivery/receiver-ready: UNVERIFIED. Git-base resume validation: UNVERIFIED.
- Agent HQ: name collides across repos (e.g. MCP coordination, dashboards); no canonical spec retrieved. All guarantees: UNVERIFIED.
- LangGraph checkpoints: SOURCE FACT (https://github.com/langchain-ai/langgraph README via curl): durable execution persists through failures, resuming where left off; thread-scoped checkpoints. Cross-session handoff delivery: UNVERIFIED. Receiver readiness: UNVERIFIED. Git fork/base/head binding: UNVERIFIED.

## 3. Verdict
A Git-bound recovery handoff (explicit fork/base/task/policy carried in the handoff plus receiver-side head validation before resume) is uncovered by the above: A2A/MCP define messaging/context, Vibe Kanban/Claude Squad isolate work in branches/worktrees, and LangGraph restores thread state, but none retrieved here guarantees exactly-once handoff delivery tied to a Git base with receiver-head checking, which is precisely the gap the primary failures (silent handoff loss, duplicates, stale session identity) fall into.
