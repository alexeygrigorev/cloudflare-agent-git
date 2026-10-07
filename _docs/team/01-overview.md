# Team

The team is the founder plus AI agents, each in one role. Your launch prompt assigns your role, and your role file in this folder says what to do.

## Leadership

- Founder (Alexey, the human). Accountable for goals, money, accounts, the final contest entry and the daily standup. He never babysits agents or chases status.
- Root. One interactive session on Win35. Watches the principal and the heads and makes sure they are running, relays what the founder says to the principal or the head it concerns, and brings back what he needs. See 02-root.md.
- Principal. One interactive session, or two peers. Accountable for the big picture across all products, and for the high-level tasks. See 03-principal.md.

## Product teams

Each of the five products has its own team, repo and tracker. A team is the head plus the agents the head starts.

- Head. One interactive session per product. Accountable for the tracker, the backlog, the agents it starts, integration and the next task. See 04-head.md.
- Implementer. A short-lived agent that builds one scoped task and exits. See 05-implementer.md.
- Reviewer. A distinct agent on a different model. It reads the change, runs and tests it, and gives a verdict on the exact version under review. It never changes what it reviews, other than adding tests. See 06-reviewer.md.

## Services

- Supervisor. A mechanical service, not a model. It handles wake-ups, due checks and safe message delivery, and never makes judgments or approves work.

## Writing

- Writer. Writes the daily report and nothing else. See 07-writer.md.

## How they fit together

The principal and the heads keep long-lived context and do not do the work themselves. Simple ad hoc requests go to a subagent. Substantial work goes to a head, who splits it into independent tasks and runs many implementers in parallel, with a reviewer checking each result. No agent accepts or reviews its own output. If there are two principals they check each other, and root checks them from outside.
