# Asking the principal

This is the one description of how an agent gets a decision it cannot make alone: it asks the principal, sets a wake-up, and either gets an answer or goes ahead on its own best judgement. Other pages point here. Where they say less, this page is the rule; where a script behaves differently, the gap is listed under [installed state](#installed-state).

## Purpose

Work never stops because a question is waiting, and the founder is never the one who answers. Every question has a deadline, a default and something that will bring the asker back. Silence costs at most 20 minutes, never a day.

## Who takes part

- The asker. Any principal, head or situational head that needs a decision. Implementers and reviewers ask their head, never the principal; a head then asks the principal if the decision is above it.
- The principal. Answers every question it receives with a concrete next action, not a question back. It decides everything that fits policy and its authority. When there are two principal peers, the asker sends to the one named for it in `coordination/TEAM-REGISTRY.json`, and that peer answers.
- Root. Restores a dead principal by the [principal runbook](../recovery/principal.md) and carries the few founder decisions upward, batched. Root does not answer routine questions.
- Situational heads. Heads started for one situation, such as a recovery, an incident or a one-off push. They ask and wait exactly like standing heads. They also keep a written record of their work and their task, so another head can resume from the record: the task record in `coordination/TASKS.json` (owner, status, next action, evidence paths) plus a tracker issue with what it was assigned, what it has done, where it stands, its open questions with their ids and defaults, and its armed wake. A situational head that stops with an open question leaves that question in its record, and whoever takes over inherits the question, its deadline and its default.
- The founder. Never receives the question. He sees outcomes in the daily standup.

## One question, start to finish

1. Ask with a default. The asker writes the question, the options, its recommendation and the best-judgement default: what it will do if nobody answers. It registers and sends it in one step:
   `scripts/ping/ask-ledger.py ask <principal-tag> <id> --text "<question>" --default "<what I will do>" --live`.
   This records the question in the asker's ledger with a 20-minute deadline and sends it on the bus with the footer "Reply by typing the answer into my session (aplexer send <tag> --enter) AND a bus message; I check again in 20m and then proceed with: <default>".
2. Keep working. While it waits, the asker continues on the recommended path where that is reversible, and on any other independent work.
3. Arm the wake before the turn ends. Before the asker ends its tool-call loop it arms a wake for 20 minutes or less, with the standard prompt below, by the first available mechanism in [the mechanisms list](#mechanisms-in-priority-order). An open question with no armed wake is a failure, because nothing will bring the asker back.
4. The principal answers. It types the answer into the asker's session (`aplexer send <asker-tag> "<answer>" --enter`, only at an idle, empty prompt) and also replies on the bus. Either one counts as the answer. The asker records it with `ask-ledger.py answer <id>`, acts on it and turns the wake off.
5. The wake fires. The asker runs the standard prompt: it looks for the answer in its inbox and its own session. If there is none, it checks that the principal is alive, restarts it if it is dead (see [restarting a dead principal](#restarting-a-dead-principal)), and asks once more.
6. Proceed and inform. If there is still no answer at the deadline, the asker goes ahead with its default, runs `ask-ledger.py proceed <id> --note "<what I did>"`, tells the principal "no answer after 20 min; proceeding with <default>; tell me to change", and turns the wake off.
7. The principal may reverse. A later answer from the principal wins. The asker undoes or adjusts what it did, as in [late answers](#a-late-answer-after-the-asker-went-ahead).

The 20 minutes is the deadline for a question. Any other wait (a review, a build, CI, a worker, quota) needs a wake of 30 minutes or less, 15 by default, as in [waiting requires a wake](07-supervision.md#waiting-requires-a-wake). A question is a wait, so 20 minutes satisfies both rules.

## The exception: irreversible, public, spending or access

When the decision is irreversible, public-facing, spends money, or grants or uses access or keys, the default is always the safe one: do nothing on that point and report. Silence never counts as approval for these. The asker proceeds only on the parts that are reversible and keeps the rest open. The principal decides what fits its authority and sends the rest to root, batched with its recommendation, and root takes it to the founder.

## The standard wake prompt

`ask-ledger.py wake-prompt <id>` prints it as one line, safe for any timer:

> Wake: check the answer to question <id> from <principal-tag> (inbox and anything typed into this session). If no answer: check the principal is alive (aplexer status <principal-tag>; run scripts/ping/principal-ping.py to classify it); if it is absent or dead restart it by the documented route (recovery/principal.md, or the configured PRINCIPAL_RECOVERY_CMD) or alert root (desktop-orchestrator) if you cannot, then ask again once; if still no answer proceed with the best option: <default>, inform the principal, run scripts/ping/ask-ledger.py proceed <id>, then aplexer wake off.

The order is fixed: look for the answer, restart a dead principal and ask once more, and only then proceed. `ask-ledger.py wake-command <id>` prints the full `aplexer wake set` command with this prompt.

## Restarting a dead principal

The asker does not start a principal by hand. "Restart" means the asker triggers the one documented route, which has a single lock so that several askers waking at once start at most one recovery:

- The asker runs `scripts/ping/principal-ping.py` to classify the principal. Only a dead or absent verdict leads to a restart. A principal that is busy and producing output is alive, and the asker simply waits out its deadline.
- If `PRINCIPAL_RECOVERY_CMD` is configured, that command runs, under the ping's lock and cool-down. If it is not configured, the asker alerts root and the peer principal with one bus message and goes on.
- Root owns the restart by the [principal runbook](../recovery/principal.md), with vacancy proof and the same tag.
- If recovery fails, the alert goes to the local alert log (`.local/ping/alerts.log`) and to the bus for the principal peer and root. Alerts never go to Telegram or any other external chat.
- Whatever happens to the restart, the asker still proceeds on its default at the deadline. A dead principal never stops the work.

## Mechanisms in priority order

1. aplexer wake. `aplexer wake set --once --in 20m --text '<prompt>'` (or `--every 15m` for a repeating ping until `aplexer wake off`). aplexer types the prompt into the agent's own session, and only while it is idle. It works for every engine because it needs nothing from the engine.
2. The wake runner. `scripts/ping/ask-wake-runner.py`, run every five minutes, reads the ledgers, finds each open question past its deadline and types the standard prompt into the asking session, but only when that session is idle or waiting with an empty prompt. The asker marks its wake with `ask-ledger.py wake-armed <id>`. This also works for every engine and is the backstop when the agent forgets.
3. Claude extras. A Claude session is also held at the end of its turn by the Stop hook (`scripts/ping/stop-guard.py`), and may set a cron or schedule wake-up with the same prompt. These add coverage for Claude only and are never the only mechanism.

AGENTS.md is the only instruction file for every engine in this organisation's projects. Where an engine has to be configured to read it, the launch owner configures it that way.

| Engine | Wake mechanisms |
| --- | --- |
| Codex, zcodex | aplexer wake, runner |
| OpenCode (Muse, Space Bunny) | aplexer wake, runner |
| Grok | aplexer wake, runner |
| Claude | aplexer wake, runner, Stop hook, cron |
| Gemini, Antigravity | aplexer wake, runner |

The runner and the wake audit cover every engine mechanically even when an agent misses the instruction.

## Enforcement

Each layer covers what the one before it misses.

1. Instructions. AGENTS.md "End of every turn" tells every agent to register the question and arm the wake before it stops. Details are in [end of turn](team/08-turn-end.md).
2. Turn-end hook, Claude only. `stop-guard.py` blocks the end of a turn while a question is open with no wake, or past its deadline without a proceed. It blocks at most 3 times per question and then lets the turn end and logs it, so it can never loop.
3. Wake runner. Wakes the asker at the deadline whether or not it armed anything, at most once per 10 minutes and 3 times per question, then tells the principal once and stops.
4. Wake audit. `scripts/ping/wake-audit.py` finds every head and principal that is waiting with no wake, or a wake slower than 30 minutes, reminds it at most once per 30 minutes, and escalates to the principal (to root for the principal) after 3 bad audits in a row.
5. Claims audit. `scripts/ping/claims-audit.py` marks claims not renewed for 30 minutes as expired and reminds the holder to re-claim or release. Expiry is a reminder and an annotation only. It never releases a claim and never lets anyone take over by age.
6. Principal ping. `scripts/ping/principal-ping.py` pings the principal every 10 minutes, tells busy from dead with liveness evidence, and starts recovery after repeated misses. It is the reason an asker can trust that a dead principal is noticed even when nobody asks.
7. Repo check. `scripts/checks/ask-guard.sh` fails a commit in an opted-in project when the ledger tools or the Stop hook entry are missing.
8. Override. Only the principal may override a guard, with a `Principal-Override: <reason>` commit trailer or `PRINCIPAL_OVERRIDE=<reason>` on push. Every override is logged and shown as a warning.

## Opt-in per project

All of this applies only to projects that take part in this organisation. A project opts in with an empty `.follows-principal-process` file in its root. The runner, the audits and the repo check never wake, type into, message or fail anything in a workspace without the marker. Other sessions and engines on the same server are left alone.

## Installed state

| Piece | Status |
| --- | --- |
| `aplexer wake` | Not installed. The installed aplexer is 0.1.10 and has no `wake` or ping command. The feature exists only on the reviewed branch `self-wakeup-20261007` and awaits an authorized build, merge and install. |
| Ask ledger, standard prompt, wake command | In the repo, working. |
| Wake runner | In the repo, with a 5-minute timer template. Timer not installed. |
| Claude Stop hook | Installed in this repo's local `.claude/settings.json`. |
| Wake audit | In the repo, with a 15-minute timer template. Timer not installed, and it exits without acting while aplexer has no `wake`. |
| Claims audit | In the repo, dry run by default, no timer. |
| Principal ping | Timer installed on the Hetzner host, every 10 minutes, alert-only: no recovery command is configured, so a dead principal raises a local alert and nothing restarts it automatically. |
| Repo check | In `scripts/checks`, runs in the local git hooks. No CI workflow runs the checks yet. |
| Opt-in marker | Present in this repo. Not present in the five product repos. |

## Failure modes and how they are handled

Each entry says how the problem is noticed, what happens and who owns it. "Not yet enforced" marks a gap with its next step.

- Principal dead or vacant. Noticed by the principal ping (dead or absent within about 11 minutes) and by any asker's wake. The recovery command restarts it under one lock; without it, the ping and the asker alert root and the peer locally and on the bus. Root restores it by the runbook. If restart fails 3 times, the alert repeats once per 30 minutes until a person acts, and askers keep proceeding on their defaults. Owner: root. Not yet enforced: `PRINCIPAL_RECOVERY_CMD` is unset, so recovery is manual ([issue 102](https://github.com/alexeygrigorev/cloudflare-agent-git/issues/102)).
- Principal and asker both dead. Nothing wakes the asker: the runner skips a session that is not running. The principal ping catches the principal, and the supervisor records the dead head as a failover candidate. The restored principal reads the open ledgers and recovers the head by the [head runbook](../recovery/head.md); the head's record carries the open question and its default. Owner: root for the principal, then the principal for the head.
- Principal busy but alive. The principal ping sees output changing and counts no miss. The asker proceeds at 20 minutes anyway; it does not restart a busy principal. Owner: the asker.
- A late answer after the asker went ahead. The principal's answer always wins. The asker compares it with what it did: if they match, it says so; if not, it reverses or adjusts the reversible work at once, and reports what it changed. Because only reversible defaults are allowed, this is always possible. Owner: the asker. Not yet enforced: `ask-ledger.py answer` does not yet mark an answer that arrives after `proceed`; the asker must check by hand.
- Conflicting answers. When two principal peers answer differently, the asker follows the peer the question was addressed to and tells both. When one principal answers twice, the latest answer counts. Owner: the principals settle it between themselves.
- Two askers waiting on each other. A question goes up to the principal, never sideways as a blocking wait. A head that needs something from another head sends a bus request with its own default and keeps going; it never waits on another head without a deadline. Each side's deadline ends the wait, so a cycle cannot last more than 20 minutes. The principal resolves the conflict if both defaults clash. Owner: the principal.
- Questions flooding the principal. Each asker keeps at most 3 open questions and batches related decisions into one. The principal answers in a batch, oldest deadline first. Owner: the asker for the cap, the principal for the batch. Not yet enforced: the ledger does not refuse a fourth question.
- A wake fires while the agent is busy or has a draft. aplexer wake and the runner type only at an idle, empty prompt; otherwise they skip and try again after 10 minutes. A busy agent is working, so it will reach its own turn end and see the open question there. Owner: the wake mechanism.
- A wake firing in a loop. The runner wakes at most once per 10 minutes and 3 times per question, then tells the principal once and stops. A repeating aplexer wake runs until `aplexer wake off`; the prompt always ends with turning it off, and the wake audit flags a wake on an agent that has nothing left to wait for. Owner: the asker; the principal after escalation.
- An expired claim and a live writer. Expiry is only a reminder. The claim stays owned; nobody edits the paths by age. To take over, ask the owner or the principal; only the owner's release, the principal's reconciliation or proven end of custody transfers it. Owner: the holder; the principal for disputes.
- The reminder hook triggering itself. The Stop hook counts blocks per question and lets the turn end after 3; reminders from the audits are rate-limited to one per 30 minutes per agent. Owner: the hook and audits themselves. Not yet enforced: the Stop hook does not read Claude's `stop_hook_active` flag; the 3-block cap is the only guard.
- Engines without hook support. They get the instruction from AGENTS.md and the mechanical cover from the runner and the wake audit, which need nothing from the engine. Owner: the launch owner, who makes sure the engine reads AGENTS.md.
- The asker runs out of provider quota. A woken agent that cannot run a model does nothing. The runner wakes it 3 times, then tells the principal, who reassigns the task through the Agent Quota Launcher to a healthy provider. The question's default is not executed by anyone else unless the new owner takes the question over from the record. Owner: the principal.
- Clock skew. Deadlines are set and judged on the asker's own host clock, and the runner reads ledgers on the same host. Nothing compares timestamps across hosts. Times are written in UTC. Owner: the host running the asker.
- Ledger loss or corruption. The ledger is written atomically, so a crash leaves the old or new file, not half of one. If it is deleted or unreadable, the bus still holds the question (its id, text and default are in the sent message), and the asker rebuilds it from there. Owner: the asker. Not yet enforced: an unreadable ledger currently reads as empty, so the Stop hook and runner see no open questions and stay silent; the next step is to fail loudly instead.
- A stale principal tag after restart. Askers address the principal by its role tag from `TEAM-REGISTRY.json` (`codex-principal`, `claude-principal`), never by a session id. Recovery restores the principal under the same tag, so messages and wakes reach the new session, and the restored principal reads its inbox and the open ledgers at startup. If the tag ever changes, the registry is updated first, and askers re-read it at every wake. Owner: root for the tag, the asker for re-reading.
- Ledgers in other workspaces. A head working in a product repo writes its ledger in that repo's `.local/ask/`, which the runner in this repo does not read, and the product repos have neither the tools nor the marker. Owner: the principal. Not yet enforced: next step is one shared ledger directory (`ASK_DIR`) and absolute tool paths for every opted-in session, plus the marker in each product repo.
- What the founder sees. Never a question. Outcomes only, in the daily standup: decisions made, defaults taken without an answer and any the principal reversed, and recoveries. Founder decisions reach him through root, batched with a recommendation. No alert goes to him by Telegram or any other chat.
