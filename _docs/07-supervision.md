# Supervision

The supervisor is the mechanical service from the team overview. It is a script, not a model. It watches the task list and the agent sessions, and sends short wake-up messages to principals and heads when ready work is not moving. It never does the work, never judges it and never approves it. This page says what it does, how to run it and how it maps to the rest of these docs. The source is `scripts/supervision/service.py`, and the detailed safety rules are in `coordination/SUPERVISION.md`.

## What it does

Every 60 seconds the supervisor takes one pass:

- It reads the task list and the team registry, and asks aplexer which sessions are alive and what state each is in.
- It finds ready work for each head. A head is idle with ready work when its session is idle, its prompt is empty and a task it owns is ready.
- It sends the head a message that names the ready tasks and asks it to start workers and report the first real output. It sends the principal a similar message when the task list changes, asking it to check that every ready task has an owner.
- It waits for a reply or a read acknowledgement. Until one arrives the request stays pending and is not sent again. When a request is acknowledged but the head is still idle with ready work after three minutes, it sends a fresh request.
- When a request has gone unanswered for five minutes (30 minutes for a Claude principal) it records the blocking reason, such as a dead process, a busy screen or an unsent draft. When the recipient is dead, or silent for twice that long, it records a failover candidate event. It does not recover anything itself.
- It records new ready tasks for the Agent Quota Launcher queue and imports the launcher's finished-task state, so that a task whose dependency has an accepted review becomes ready.
- It checks its own health: it halts if its own source or the aplexer binary it pinned at start changes, and it pauses all sending if its private storage reaches the hard limit.

It never types into a busy screen, a menu or a human draft. It sends only when two fresh observations show an idle session with an empty prompt, and it never sends Enter on its own. A message that was delivered is not a started task: only a reply from the recipient or a native read acknowledgement clears the request, and neither proves the work is done.

## How it works

- It runs as the aplexer shell session tagged `experiment-supervision` in this workspace, started with `aplexer start --workspace <repo> --tag experiment-supervision --engine shell -- python3 scripts/supervision/service.py`. A lock file allows only one copy. Never start a second one, and never start one with `--fresh` while the tag exists.
- Its inputs are `coordination/TEAM-REGISTRY.json` (who the principals and heads are), `coordination/TASKS.json` (the tasks and their status), the aplexer session list and the launcher databases.
- Its outputs are messages on the agents bus and private files in `.local/supervision/`: `status.json` (the latest pass, including every principal and head), `state.json`, `events.jsonl` and one receipt per message. Nothing in there goes into the repo, an issue or a message.
- Old receipts and logs are compressed into verified archives and never deleted. At 128 MiB of private storage it warns, and at 256 MiB it pauses sending until a person makes room.
- It sends each message with a key, so a crash cannot make it send twice. If a send may have started and its result is unknown, it freezes that request and never resends.

## How to use it

- To see what it is doing, read `.local/supervision/status.json`. Each principal and head has a state, a reason (idle and empty, busy, draft, missing process), the ready tasks, the pending request and its age. `errors` lists requests blocked past their limit. You can also run `aplexer status experiment-supervision` and `aplexer capture experiment-supervision`.
- To keep it useful, keep the task list true. Give every task an owner, a status and a next action. A head that is waiting on a running worker or a blocked dependency should say so on the task, so the supervisor does not call it idle.
- To answer a request, reply on the bus with task IDs, owners, first evidence and the next check, then acknowledge it. Reply text is never executed.
- To exclude an agent that is paused, mark it in the registry (`status: paused`, or `supervision_excluded: true`), or list it in `.local/supervision/excluded-heads.json`.
- To stop it, create `.local/supervision/stop` and let it finish its pass. Do not kill it, and do not delete an uncertain receipt. Remove the stop file before starting it again.
- To change it, treat it like product code: a head owns the change, a different agent on a different model reviews the exact version, and the service is restarted on purpose afterwards. Any edit to `service.py` makes the running copy exit at its next pass. Tests are in `scripts/supervision/`, for example `python3 scripts/supervision/test_service.py`.
- Who runs it: it runs by itself. The principal that owns recovery keeps it alive and acts on what it reports. Root checks that it is alive. A systemd unit and watcher in `scripts/supervision/systemd/` restart it, and the migration runbook next to them is the plan for that. Recovery status is in [recovery](05-recovery.md): a live supervisor is not proof that unattended recovery works.

## Waiting requires a wake

Whoever waits sets a wake, so nobody sleeps forever on something that already arrived. The wake is an aplexer timer that types a prompt into the agent's own session every 15 or 30 minutes. `scripts/ping/wake-audit.py` checks the rule, reminds, and escalates.

The rules, each one is checked by the audit:

- Who. Every head and principal session. Shell and service sessions are exempt, and so is the audit itself. An agent that is busy (any state other than idle or waiting) is exempt.
- Waiting means: the session has been idle or waiting for more than 5 minutes and is blocked on something outside itself: a reply, a review, a build, CI, another agent, quota, or a human.
- A waiting agent MUST have an active wake before it ends its turn: `aplexer wake set --every 15m --text '<what I wait for>'`, or for a one-off `aplexer wake set --once --in 30m`. The interval MUST be 30 minutes or less, and the wake must still be alive at the next audit (15 minutes from now).
- The wake prompt MUST make the agent check its inbox and the thing it waits for, then do exactly one of three things: continue the work, re-arm the wake, or run `aplexer wake off`.
- The agent MUST turn the wake off (`aplexer wake off`) when the wait is over, or when it has nothing left to wait for.
- Evidence the audit reads: `aplexer list --json` for the state and its age, and `aplexer wake list --all --json` for the wake (interval, active, expiry). The audit changes nothing in either.

Classes: `WAITING-WITH-WAKE` (fine), `WAITING-NO-WAKE` (violation), `WAKE-TOO-SLOW` (a wake exists but its interval is over 30 minutes; violation), `BUSY` (ignored), `UNKNOWN` (state or wake data unreadable; reported, never counted as a violation).

Consequences: the audit sends the agent a bus message quoting the rule and the exact command, and tells its principal. It sends at most one reminder per agent per 30 minutes. After 3 consecutive violating audits it escalates to the principal, and to root (`desktop-orchestrator`) when the violator is the principal. Everything is logged in `.local/ping/wake-audit.log`.

How to run it: `scripts/ping/wake-audit.py` is a dry-run that prints what it would send. `--live` sends and logs. `--read-only` prints only the line `wake coverage: N of M waiting agents covered`, which is also in `scripts/principal-metrics.sh`. A template for a 15-minute systemd timer is in the `wake-audit` unit files in `scripts/ping/` (not installed). If the installed aplexer has no `wake` command, the audit prints that the rule cannot be enforced, exits with code 3, and sends nothing: that is a standing unenforced state until aplexer wake is installed.

## Claims expire after 30 minutes

A claim says "I am editing these paths". It is a declaration made with `aplexer work join` (task, scopes, mode edit or read), plus any sessionless claim kept on the file bus. A claim is only worth something while someone is actually working under it, so every claim has a 30 minute lifetime.

- The rule. A claim not renewed for more than 30 minutes is EXPIRED. The clock is the declaration's `updated_at_ms`. The limit can be changed with `CLAIM_TTL_MINUTES`, and the default is 30.
- Renewing. The holder re-runs `aplexer work join` with the same scopes, which sets `updated_at_ms` to now. Nothing else renews a claim. For a file bus claim the equivalent is to write the claim again. A holder who is done runs `aplexer work leave`.
- What expired means. Expiry is a reminder, a stale-status annotation and a prompt for the holder to re-claim. It is never a release, and age never authorizes taking over unknown live product-writer edits, launcher leases, file bus claims or protected drafts. Four points:
  1. An expired peer claim that overlaps a staged file is a warning: `claim by <tag> expired N min ago: owner unconfirmed; ask the owner or the principal before editing; age never releases a claim`. It does not authorize the committer: a file outside the committer's own fresh claim fails exactly as an unclaimed path does.
  2. The committer's own expired claim fails with `claim expired N min ago: re-run aplexer work join to reclaim`. This is the only effect of expiry, and it falls on the holder.
  3. Read mode stays non-blocking.
  4. `scripts/ping/claims-audit.py` labels expired entries `EXPIRED (annotation only, not released)`.

  Expiry never transfers ownership; only the owner's release, the principal's reconciliation or authoritative terminal custody does.
- Who is reminded. `scripts/ping/claims-audit.py` lists every declaration with its age and marks the expired ones. With `--live` it sends each holder that is still running the message "your claim expired; reclaim with aplexer work join or release with aplexer work leave", at most once per holder per 30 minutes. The default is a dry-run that sends nothing and changes nothing.
- File bus claims. The audit reads them only when a local store is readable. Otherwise it prints `FileBus claims: no reader, expiry unenforced`, and those claims keep their old behaviour until the owners of aplexer add native expiry.
- Exceptions. A declaration in read mode never blocks anyone, so its age does not matter. `PRINCIPAL_OVERRIDE` still passes the commit check, with its reason logged.

Target state: aplexer itself expires claims (a native 30 minute lifetime, a `work renew` command, an EXPIRED state in `aplexer context`, and a refusal of overlapping scopes when the other claim is still live). Until then the claims check and the audit enforce the rule from outside.

## Asking the principal: answer or proceed after 20 minutes

The canonical description of this process, with its failure modes, is [asking the principal](08-asking-the-principal.md).

Target state. An agent that needs a decision asks its principal, never the founder. The process is the same everywhere:

- The question states the best-judgement default: what the asker will do if nobody answers. It goes to the principal on the bus with the footer "Reply by typing the answer into my session (aplexer send <tag> --enter) AND a bus message; I check again in 20 minutes and then proceed with: <default>".
- The principal answers directly in the asker's session (send keys) and also by bus message. The asker treats either as the answer.
- Before the asker ends its tool-call loop it arms a wake or timer for 20 minutes. An open question with no timer is a failure, because nobody will come back to it.
- The timer carries one standard prompt, printed by `scripts/ping/ask-ledger.py wake-prompt <id>` (a single line, safe for `aplexer wake set --text` and for cron prompts): "Wake: check the answer to question <id> from <to> (inbox and anything typed into this session). If no answer: check the principal is alive (aplexer status <to>; run scripts/ping/principal-ping.py to classify it); if it is absent or dead restart it by the documented route (recovery/principal.md, or the configured PRINCIPAL_RECOVERY_CMD) or alert root (desktop-orchestrator) if you cannot, then ask again once; if still no answer proceed with the best option: <default>, inform the principal, run scripts/ping/ask-ledger.py proceed <id>, then aplexer wake off." `ask-ledger.py wake-command <id> [--every 20m | --once --in 20m]` prints the full, shell-quoted `aplexer wake set` command with that prompt. The order is fixed: look for the answer, restart a dead principal and ask once more, and only then proceed on the default.
- Which timer. Installed aplexer 0.1.10 has no `wake` or ping subcommand. Until `aplexer wake` is installed, the asker uses the session's own scheduler (for example Claude Code's cron or schedule tool) with the same prompt. The reviewed branch `self-wakeup-20261007` provides `aplexer wake`; it awaits an authorized build, merge and install, so it does not exist yet and nothing here relies on it.
- At the deadline with no answer, the asker proceeds on its best judgement and tells the principal ("no answer after 20 min; proceeding with <default>; tell me to change"). The principal can reverse it.
- Reversible versus irreversible. The default must be reversible. For anything irreversible, public, spending money or granting access, the default is the safe one: do nothing and report. Silence never counts as approval for those.

How it is enforced. `scripts/ping/ask-ledger.py` records each question in a git-ignored ledger (`.local/ask/<session>.json`) with its deadline and default, and has `ask`, `answer`, `wake-prompt`, `wake-command`, `wake-armed`, `due`, `proceed` and `status`. Sending is a dry run unless `--live`. `scripts/ping/stop-guard.py` is a Claude Code Stop hook: it blocks the agent from stopping while a question is open with no timer armed, or while a deadline has passed unhandled, and gives up after 3 blocks per question so it can never loop forever.

Installing it in a project. Run `scripts/ping/install-ask-guard.sh <project-dir>`; it adds the Stop hook to `<project-dir>/.claude/settings.json` (project scope, existing keys kept, safe to repeat). A project that follows this process has an empty `.follows-principal-process` file at its root, and `scripts/checks/ask-guard.sh` then fails if the hook entry or the ledger tools are missing. Projects without the file are not checked. The settings file may stay local (not committed); CI then checks only the tools.

The end-of-turn wake that works on every engine is described in [end of turn](team/08-turn-end.md).

## How it maps to these docs

- Supervisor. It is the service in the [team overview](team/01-overview.md): wake-ups, due checks and safe delivery, with no judgment and no approvals. It is the one supervisor that [way of working](03-way-of-working.md) section 12 asks for.
- Principal. The supervisor wakes a principal when the task list changes or when a head is idle. The principal's job in [principal](team/03-principal.md) is the answer: coverage, an owner for every task, a head that is running. The supervisor treats `codex-principal` and `claude-principal` as the principal, or two peers.
- Head. A head is any agent named as a head tag in the registry. The supervisor wakes it when it is idle with ready work, as in [head](team/04-head.md): pick the ready task, start a worker through the launcher, keep the team busy. An idle head with ready work is the failure the supervisor exists to catch.
- Standing heads. These are the registered heads of the five products. The registry holds one head tag per product, and the supervisor tracks each head's session between passes in `state.json`.
- Situational heads. The supervisor has no such class. It treats any head tag the same way, and the head's kept state and task are the task record in `TASKS.json` (owner, status, next action, evidence paths). The supervisor's own `state.json` is its observation of the session, not the head's written record.
- Head loop. The supervisor starts it with a message and checks it by reading status. It does not run the loop. A worker or a reviewer is still started by the head through the launcher.
- Launcher. The supervisor queues ready tasks in the launcher database, and the launcher owns provider choice and quota.
- Agents bus. All of its messages go through the bus, and an acknowledgement means read and handled, as in [communication](04-communication.md). It sends to principals and heads only.
- Claims. The supervisor does not read or write claims. It edits no files except its own private ones. The word claim in its messages ("claim ready work") means a head takes ownership of a task. It is not a claim on files.
- Founder journal. It writes nothing there and sends the founder nothing. Its evidence stays private in `.local/supervision/`.
- Recovery. It detects and records a dead or silent head and emits a failover candidate event. Restoring the agent stays with [recovery](05-recovery.md).
- Metrics. Its idle episodes and pending-request ages are inputs to idle time in [metrics](06-metrics.md). It does not compute the metrics, and the target of 50 active agents is not something it counts.
