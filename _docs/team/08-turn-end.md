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

## Hook that checks the wake is armed

The instruction alone can be forgotten, so an end-of-turn hook checks it. `scripts/ping/turn-end-check.py` runs when the agent's turn ends. It finds the session (`--session`, ASK_SESSION, APLEXER_TAG, `aplexer whoami`) and reminds it when either an open question in `.local/ask/<session>.json` has no armed wake, or the hook is told the session is about to wait (`--waiting`) and no wake exists at all. A wake counts as armed when `aplexer wake list --json` is non-empty, or, where that subcommand does not exist, when the marker `.local/ask/<session>.wake` names the question. The reminder carries the exact `ask-ledger.py wake-command <id>` line and the fallback: use the engine's own scheduler with the same prompt. Output is `--format claude-stop` (a block reason), `plain` or `json`; `--also-bus` also sends the reminder to the session over the bus.

It acts only in a project that carries `.follows-principal-process` (the workspace or any parent up to its git root). Anywhere else it exits 0 and does nothing.

Loop guard, so a reminder can never become a loop:

- State per session in `.local/ask/<session>.reminders.json`, keyed by a hash of the unresolved condition (question ids and armed state).
- At most one reminder per condition every 10 minutes, and at most 3 per condition. After that it stays silent and logs once to `.local/ask/turn-end.log`.
- The entry is cleared when the wake is armed or the question is answered.
- A re-entrancy guard (env `TURN_END_CHECK_ACTIVE` and a lock file with a 60 second life) stops a turn that ends because of a reminder from re-firing at once. An invocation within 30 seconds of the previous one does nothing.
- Claude's Stop variant never blocks when the hook input says `stop_hook_active` is true, so it blocks at most once per stop sequence.
- It always exits 0 and swallows its own errors, so it cannot break the host hook.

Installation is per project, never in user-global config: `scripts/ping/install-turn-end-hooks.sh <project-dir> [--engine claude|codex|zcodex|gemini|opencode|all] [--check] [--join]`. It refuses a project without the marker unless `--join` is given, which creates the marker. `--check` reports each engine and exits 3 if one is missing. `scripts/checks/turn-end-hooks.sh` runs the check in marked projects: it fails for a missing Claude hook and only warns for the other engines.

| Engine | Project-scope mechanism | Status |
| --- | --- | --- |
| Claude | `.claude/settings.json` Stop hook | verified, in use |
| Codex, zcodex | `.codex/hooks.json` Stop hook (same schema as the user-level file) | schema verified, project-file loading and first-run trust not exercised |
| Gemini | `.gemini/settings.json` AfterAgent hook (project hooks need trust) | verified in the installed CLI code, not exercised |
| OpenCode | `.opencode/plugin/turn-end-check.js` on `session.idle` | plugin API verified from the installed global plugin, project path not exercised |

Where a hook is missing or does not fire, the wake runner and wake audit remain the backstop.

## Incoming-message hook

A session that has unread messages from peers must read and act on them, without asking first. The instruction alone is forgotten, so `scripts/ping/inbox-guard.py` checks for it.

What it does: it runs `aplexer message inbox --json` for the calling session. If there are unread messages it prints a prompt that lists, per message, the sender, the first eight characters of the id and a subject (the first line of the body, cut to 60 characters, long token-like strings masked). It never prints a full body. The prompt tells the agent to run `aplexer message inbox`, read the messages and act on them now, and acknowledge or reply when done.

Opt-in: it acts only in a project carrying `.follows-principal-process`. Anywhere else it prints nothing and writes nothing.

Loop guard: state per session and message id in `.local/inbox/<session>.json`. Each id is prompted at most 3 times, at least 10 minutes apart; after that it stays silent and logs once to `.local/inbox/guard.log`. An id is forgotten when it is no longer unread. In its Stop form it never blocks when the hook input says `stop_hook_active` is true. It fails open: a missing aplexer, a failing command, bad JSON or a 5 second timeout produces no output and exit 0.

Two ways to run it, so every engine is covered:

- Hook form: `inbox-guard.py --format claude-prompt` as a UserPromptSubmit hook, and `--format claude-stop` as a Stop hook, for Claude. Codex and zcodex take the Stop form from `.codex/hooks.json`. Register both with `scripts/ping/install-turn-end-hooks.sh <project-dir> --with-inbox`; this is off by default, idempotent, project scope only, and `--check --with-inbox` reports each engine.
- Engine-neutral form: `scripts/ping/ask-wake-runner.py --inbox` (add `--live` to act). For each running session in an opted-in workspace that is idle or waiting and shows an empty prompt, and that has unread messages, it types one line with `aplexer send <workspace>:<tag> ... --enter`. It uses the same loop guard and never types into a busy session or over a draft. It needs nothing from the engine.

| Engine | Incoming-message mechanism | Status |
| --- | --- | --- |
| Claude | UserPromptSubmit and Stop hooks, runner | tested with a fake aplexer; not yet installed in any live settings |
| Codex, zcodex | Stop hook in `.codex/hooks.json`, runner | tested with a fake aplexer; the real hook run is not exercised |
| Gemini, Antigravity, OpenCode, Grok | runner only (`--inbox`) | tested with a fake aplexer; no hook form |

Not verified: the `aplexer message inbox --json` shape was read from a live inbox (a list of objects with `id`, `from.tag`, `body`, `created_at`); behaviour of the real UserPromptSubmit hook in Claude Code is not exercised. The hook and runner are not installed in live settings or timers; installing them needs the principal.

To disable it: a principal removes the `inbox-guard.py` entries from the project's hook files (`.claude/settings.json`, `.codex/hooks.json`), stops running the runner with `--inbox`, or removes the `.follows-principal-process` marker to take the whole project out of scope. Deleting `.local/inbox/` resets the loop guard.
