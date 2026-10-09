# End of turn

The whole ask-wake-proceed process, with its failure modes, is in [asking the principal](../08-asking-the-principal.md).

## End-of-turn wake is universal

Every agent in this organisation ends its turn the same way, whatever engine it runs on. If it asked the principal something, or waits on anything, it registers the question and arms a wake before it stops. A turn never ends with an open question and nothing that will bring the agent back.

This is opt-in per project. It applies only to projects that take part in this organisation, marked by an empty file named `.follows-principal-process` in the workspace root. Sessions in any other workspace on the same server are never woken, typed into or messaged, and the runner ignores them.

The instruction lives in AGENTS.md, so the agent sets the wake up itself at the end of the turn. No engine needs a special hook for this to work.

## Three mechanisms, in priority order

1. The aplexer wake. The agent registers the question with `scripts/ping/ask-ledger.py ask`, then runs the command printed by `scripts/ping/ask-ledger.py wake-command <id>`. aplexer brings the session back when the timer fires. This works on every engine once aplexer wake is installed.
2. The wake runner. Until then, and as a backstop, the agent runs `scripts/ping/ask-ledger.py wake-armed <id>`. `scripts/ping/ask-wake-runner.py` runs every five minutes, reads the ledgers of this repository, and for each open question past its deadline finds the asking session. If that session is idle or waiting, and its screen shows an empty prompt, the runner types the standard wake prompt. It never types into a busy session or over a draft. It wakes at most once per ten minutes and at most three times per question; after that it tells the principal and stops. It types through aplexer, so it works for every engine.
3. Claude's Stop hook and cron, as extras. Claude sessions can also be held at the end of a turn by the Stop guard, or woken by cron. These add coverage for Claude only and are never the only mechanism.

## What happens on wake

The agent checks whether the answer came. If not, it checks that the principal is alive and restarts it as in `recovery/principal.md` if it is not. If there is still no answer, it proceeds on the best option, tells the principal what it chose, and marks the question done with `scripts/ping/ask-ledger.py proceed`.

## What each engine does

| Engine | Instruction file it reads | Wake |
| --- | --- | --- |
| Claude | AGENTS.md | aplexer wake, runner, Stop guard |
| Codex, zcodex | AGENTS.md | aplexer wake, runner |
| OpenCode | AGENTS.md | aplexer wake, runner |
| Grok | AGENTS.md | aplexer wake, runner |
| Gemini, Antigravity | AGENTS.md (configure it to read AGENTS.md) | aplexer wake, runner |

AGENTS.md is the only instruction file in this organization's projects, for every engine. If an engine needs configuration to read it, configure it to read AGENTS.md. The runner wakes any engine that forgets, because it needs nothing from the engine.
