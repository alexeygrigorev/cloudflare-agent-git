# Team

The team is the founder plus AI agents, each in one role. Your launch prompt assigns your role, and your role file in this folder says what to do.

## Leadership

- Founder (Alexey, the human). Accountable for goals, money, accounts, the final contest entry and the daily standup. He never babysits agents or chases status.
- Root. The Grok Bot 'Cloudflare Root', the only root, appointed by Alexey on 11 October 2026. The Win35 root has stood down and must not run. Root watches the principal and the heads and makes sure they are running, relays what the founder says to the principal or the head it concerns, and brings back what he needs. See 02-root.md.
- Principal. One aplexer session, or two peers. Accountable for the big picture across all products, and for the high-level tasks. See 03-principal.md.

## Product teams

Each of the five products has its own team, repo and tracker. A team is the head plus the agents the head starts.

- Head. One aplexer session per product. Accountable for the tracker, the backlog, the agents it starts, integration and the next task. See 04-head.md.
- Implementer. A short-lived agent that builds one scoped task and exits. See 05-implementer.md.
- Reviewer. A distinct agent on a different model. It reads the change, runs and tests it, and gives a verdict on the exact version under review. It never changes what it reviews, other than adding tests. See 06-reviewer.md.

## Services

- Supervisor. A mechanical service, not a model. It handles wake-ups, due checks and safe message delivery, and never makes judgments or approves work.

## Writing

- Writer. The existing dedicated Claude Opus writer owns the daily report and every prose change. Root contacts it directly for requests, corrections, progress and delivery; the publication coordinator retains review, release and recovery. Reuse the current article and writer, with the existing privacy, quota and edit-scope gates. See 07-writer.md.

## Machines

Work machines are listed in [coordination/MACHINES.json](../../coordination/MACHINES.json), with how each one connects and no on/off status field:

- **Hetzner devbox** (`RMTHZ`, public): accepts inbound ssh (alias `hetzner`). It also hosts the Agent Bus adapter on port 8788 (`agent-bus-win35-adapter.service`, mTLS) over the FileBus store `~/.local/share/agent-bus-win35/store`. The former Win35 root role authority on port 8801 (`win35-role-authority.service`) is stood down and disabled ([stand-down record](../05-recovery.md#win35-root-stood-down-11-october-2026)).
- **Win35** (`DESKTOP-FP4OP26`, home network): outbound only. Nothing can ssh into it; it connects out to the Agent Bus on Hetzner.
- **Founder's laptop** (`LAPTOP-PHA6TCNC`, home network): outbound only, the same way as Win35.

Rule: work runs on available machines. Hetzner is available when its ssh probe answers. A home machine is available when it has checked in on the bus within the freshness window (default 15 minutes, `bus.checkin_window_seconds` or `MACHINES_CHECKIN_WINDOW_SECONDS`). A check-in is a record the machine itself caused: role-authority presence (`agents.seen`, a live role lease) or bus traffic (a message sent, or an ack/accept/complete of a message addressed to it). Registering an identity alone does not count. Home machines receive work as bus messages they pull from their inbox, and they talk to each other through the bus. Nobody, including root, opens a connection into a home machine. Check at run time with `python3 scripts/machines.py available` (or `scripts/launch_gates.py --reachable-hosts`); `python3 scripts/machines.py route <machine>` prints how work reaches a machine (ssh for Hetzner, a bus message for home machines).

Root is the Grok Bot 'Cloudflare Root' on Alexey's shared Linux computer. It reaches Hetzner by ssh, talks to the principal and heads through the desktop-orchestrator mailbox, and coordinates the home machines through the Agent Bus on Hetzner. There is only one root; Win35 is a work machine on the bus and must not run a root ([stand-down record](../05-recovery.md#win35-root-stood-down-11-october-2026)).

## Where they run

Every TUI launch or resume owner follows [the screen check](../04-communication.md#checking-a-tui-launch), including root starting a principal, a principal starting heads, and heads starting TUI workers or reviewers. Accept the known project trust prompt only after verifying the intended session and authorized workspace; verify readiness and first useful action after it clears.

- The principal and the heads run in aplexer sessions. When one is missing, root or the principal restarts it by hand with the runbooks in `_docs/05-recovery.md`; automatic launching is tracked in issue 102.
- Root and the work machines: see [Machines](#machines).
- Implementers and reviewers run headless. They never get their own aplexer session.

## Who talks to whom

Root talks to the principal, the heads and the dedicated Opus writer. Root and the writer communicate directly about write-ups; principal operational reports are supplied when needed, without a mandatory routing or approval step. The principal talks to root and the heads. A head talks to the principal, root and its own implementers and reviewers. An implementer or a reviewer talks only to its head. The details are in `_docs/04-communication.md`.

## How they fit together

The principal and the heads keep long-lived context and do not do the work themselves. Simple ad hoc requests go to a subagent. Substantial work goes to a head, who splits it into independent tasks and runs many implementers in parallel, with a reviewer checking each result. No agent accepts or reviews its own output. If there are two principals they check each other, and root checks them from outside.
