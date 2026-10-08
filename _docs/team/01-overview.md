# Team

The team is the founder plus AI agents, each in one role. Your launch prompt assigns your role, and your role file in this folder says what to do.

## Leadership

- Founder (Alexey, the human). Accountable for goals, money, accounts, the final contest entry and the daily standup. He never babysits agents or chases status.
- Root. One GUI session on the founder's laptop or on Win35. Watches the principal and the heads and makes sure they are running, relays what the founder says to the principal or the head it concerns, and brings back what he needs. See 02-root.md.
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

## Where they run

When Codex shows the known “Folder access” menu for this project, verify the actual owned session, current prompt and exact authorized workspace, then accept “Trust and continue” using supported native control without asking the human again. Do not leave startup blocked solely on this authorized menu. This permission covers that project trust prompt; preserve normal handling for unknown folders, drafts and busy panes, and all identity, election, quota and resource gates.

- The principal and the heads run in aplexer sessions. When one is missing, root or the principal restarts it by hand with the runbooks in `_docs/05-recovery.md`; automatic launching is tracked in issue 102.
- Root runs in a GUI session on the founder's laptop or on Win35. It never runs on Hetzner, which is a server without a GUI, and never headless. It reaches Hetzner and the other machine with ssh.
- Implementers and reviewers run headless. They never get their own aplexer session.

## Who talks to whom

Root talks to the principal, the heads and the dedicated Opus writer. Root and the writer communicate directly about write-ups; principal operational reports are supplied when needed, without a mandatory routing or approval step. The principal talks to root and the heads. A head talks to the principal, root and its own implementers and reviewers. An implementer or a reviewer talks only to its head. The details are in `_docs/04-communication.md`.

## How they fit together

The principal and the heads keep long-lived context and do not do the work themselves. Simple ad hoc requests go to a subagent. Substantial work goes to a head, who splits it into independent tasks and runs many implementers in parallel, with a reviewer checking each result. No agent accepts or reviews its own output. If there are two principals they check each other, and root checks them from outside.
