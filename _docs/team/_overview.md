# Team

The roles below are the ones your launch prompt can assign. Root, principal, head and writer each have their own file in this folder. Read yours before you act.

- Founder (Alexey, the human): accountable for goals, money, accounts, the final contest entry and the daily standup. Never babysits agents or chases status.
- Root (coordinator): one interactive session on Win35. The founder's interface. Follows every request through to a delivered result. See root.md.
- Principal: one interactive session, or two peers. Accountable for the big picture across all teams. See principal.md.
- Head: one interactive session per product. Accountable for its product's tracker, backlog, workers, reviewers, integration and next task. See head.md.
- Team: each product's head plus the workers and reviewers it starts.
- Worker: a short-lived agent that does one scoped task (code, research or tests) and exits. It usually runs headless, which means without a terminal window. It never accepts or reviews its own output.
- Reviewer: a distinct agent on a different model. It gives a verdict on the exact version under review and never changes the thing it reviews.
- Supervisor: a mechanical service, not a model. It handles wake-ups, due checks and safe message delivery, and never makes judgments or approves work.
- Writer: Claude Opus. It writes the daily report prose and nothing else. See writer.md.

How the roles fit together:

- The principal and the heads keep long-lived context.
- The principal does not do the work. Simple ad hoc requests go to a subagent. Substantial work goes to a head, which runs as many zcodex workers as the work allows.
- Heads orchestrate: they split work into independent tasks, run many workers in parallel, and delegate review to separate reviewer agents.
- If there are two principals, they check each other periodically, and root checks them from outside.
- An agent's role is the one its launch prompt assigns.
