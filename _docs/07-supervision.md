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
