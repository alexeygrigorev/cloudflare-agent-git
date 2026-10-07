# Team

The team is the founder plus AI agents, each in one role. Your launch prompt assigns your role, and your role file in this folder says what to do.

## Leadership

- Founder (Alexey, the human). Accountable for goals, money, accounts, the final contest entry and the daily standup. He never babysits agents or chases status.
- Root (coordinator). One interactive session on Win35. The founder's interface, who follows every request through to a delivered result. See 02-root.md.
- Principal. One interactive session, or two peers. Accountable for the big picture across all products, and for the high-level tasks. See 03-principal.md.

## Product teams

Each of the five products has its own team, repo and tracker. A team is the head plus the agents the head starts.

- Head. One interactive session per product. Accountable for the tracker, the backlog, the agents it starts, integration and the next task. See head.md.
- Implementer. A short-lived agent that builds one scoped task and exits. See implementer.md.
- Reviewer. A distinct agent on a different model. It reads the change, runs and tests it, and gives a verdict on the exact version under review. It never changes what it reviews, other than adding tests. See reviewer.md.

## Services

- Supervisor. A mechanical service, not a model. It handles wake-ups, due checks and safe message delivery, and never makes judgments or approves work.

## Writing

- Writer. Writes the daily report and nothing else. See writer.md.

## How they fit together

The principal and the heads keep long-lived context and do not do the work themselves. Simple ad hoc requests go to a subagent. Substantial work goes to a head, who splits it into independent tasks and runs many implementers in parallel, with a reviewer checking each result. No agent accepts or reviews its own output. If there are two principals they check each other, and root checks them from outside.
