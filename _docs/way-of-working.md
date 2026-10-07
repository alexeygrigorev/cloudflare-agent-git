# Way of working

This is the one document that says how this project works, end to end. It holds the mission, the roles, the autonomy rules, how work flows, and the rules for git, resources, documentation, the public journal, the runtime and security. It replaces the separate policy files for now; we decide later whether to split it.

Every rule is in force now. Each ends with a tag naming the human message it comes from. A tag like `[human-no-prs-push-to-main-20261007]` is a message file in `_docs/founder-journal/messages/`. `[m21]` is message 21 of the founder's first-day instruction log, `[m-20261003-1512]` is a dated entry in that log, and `[m-latest]` is its closing section on roles and quality. `[relayed-cr-r029]` is a human statement the principal relayed and that has no saved file yet. `[agent-derived]` means no human message states the rule; the founder can veto those.

When two rules conflict, the newer human message wins.

## Contents

1. [Mission and team](#1-mission-and-team)
2. [Roles and accountability](#2-roles-and-accountability)
3. [Autonomy requirements](#3-autonomy-requirements)
4. [How work flows](#4-how-work-flows)
5. [Git workflow](#5-git-workflow)
6. [Resources](#6-resources)
7. [Documentation rules](#7-documentation-rules)
8. [Public journal and editorial rules](#8-public-journal-and-editorial-rules)
9. [Runtime and continuation design](#9-runtime-and-continuation-design)
10. [Security and privacy](#10-security-and-privacy)
11. [Open specifics still to define](#11-open-specifics-still-to-define)

## 1. Mission and team

We are entering Cloudflare's next Git platform competition (deadline 14 October 2026): build a better Git for coding agents, one that solves the problems agents actually hit, not just a faster Git. [m1] [human-better-git-progress-and-utilization-20261005] The aim is to win and to make something useful. [m-20261003-early]
The work is five products, each with its own team and GitHub repo: Agent Branches (our Git tool), Agent Dashboard, Agent Quota Launcher, Agent Coordination (agents talking across computers) and Agent Bus (the message bus, separate from aplexer). [human-delivery-reset-20261004] [human-cross-computer-product-20261004] [human-principal-dispatch-agentbus-20261005]
The team is a self-running department of AI agents: one principal, one head per product, many short-lived workers, and reviewers on a different model. They coordinate among themselves, and the founder joins only for daily standups. [human-autonomous-department-20261005]
We build in public and use our own tools for our own work as early as we can. [m27] [m19]
The founder's own pain point is that every worktree copies the whole workspace and fills the disk, worst of all with Rust builds; the product must not be Rust-focused. [m7] [m-20261003-dictation] [m-20261003-1740]
Agent Branches needs a CLI the founder can demo, including a `branches sync git` style command that syncs everything to Git. [human-agentbranches-cli-demo-20261005] [human-branches-sync-git-20261005]

## 2. Roles and accountability

| Role | Who | Accountable for | Never does |
|---|---|---|---|
| Founder | Alexey, the human | Goals, money, accounts, final contest entry, daily standup | Babysitting agents or chasing status |
| Root (coordinator) | One interactive session, now on Win35 | The human's interface; follows every request through to a delivered result; monitors and repairs stalled work on Win35 and Hetzner | Writing product code, reviewing every page, approving routine work |
| Principal | One interactive session (or two peers) | The big picture across all teams: coverage, priorities, dependencies, challenges, course correction, high-level issues | Implementing or reviewing product code; running its own execution team |
| Head | One interactive session per product | Its product's tracker, backlog, workers, reviewers, integration and next task | Being the only worker; accepting its own work |
| Worker | Short-lived task agent, usually headless | One scoped task: code, research or tests, then exit | Accepting or reviewing its own output |
| Reviewer | A distinct agent, on a different model | A verdict on the exact version under review | Changing the thing it reviews |
| Supervisor | A mechanical service, not a model | Wake-ups, due checks, safe message delivery | Making judgments or approving work |
| Writer | Claude Opus | Daily report prose | Anything outside the report |

- The principal and heads keep long-lived context; they start workers that finish a task and exit. This is the main working pattern. [human-context-heads-task-workers-20261005]
- The principal watches progress and the big picture and coordinates heads; heads do the lower-level work through their teams. [human-principal-big-picture-report-20261005]
- The principal does not do the work: simple ad hoc requests go to a subagent, substantial work goes to a head. [human-principal-dispatch-agentbus-20261005]
- Principals do not review code. Heads delegate review to separate reviewer agents, so the principal never becomes the bottleneck. [human-principals-no-code-review-20261005]
- Heads are orchestrators for their direction: they split work into independent tasks and run many workers in parallel. [m32] [m-20261003-dictation]
- Every product has a head running in a normal interactive session; workers may run headless. [m21]
- If there are two principals, they check each other periodically, and root checks them from outside. [m18]
- Root monitors operations, coordinates Hetzner from Win35, and runs useful work of its own. [human-win35-new-root-instructions-20261007]
- Root is the interface between the founder and the hosts, and uses the browser when a task needs it. [m-latest]
- Every agent reads this document at startup and knows its role before it acts. [human-principals-no-code-review-20261005]
- An agent's role is the one its launch prompt assigns; this document does not hand out roles. [agent-derived]
- Count heads, principals, root and services separately from workers; only workers doing real tasks count toward the active-agent target. [human-ram-override-twentyfive-subagents-20261005] [human-fifty-active-not-idle-20261005]

## 3. Autonomy requirements

### Nonstop, proactive work

- The project runs with a very high degree of autonomy. The founder's involvement should go down over time, and fewer messages from him means we are doing better. [human-high-autonomy-default-20261005] [human-autonomous-department-20261005]
- Agents work 24/7 and stay busy. When a turn ends, the agent arranges its next action and whatever will wake it again. [human-better-git-progress-and-utilization-20261005] [m2] [m31]
- No agent waits to be checked. Each one drives its next useful step itself. [m18]
- An idle principal or head with ready work is a failure to fix at once, not a state to report. [human-idle-heads-quota-rebalance-20261005] [human-principal-still-idle-20261005]
- The target is 50 agents actively working on different tasks at the same time. Started-but-idle agents do not count; subagents that really run do. [human-fifty-distinct-active-task-agents-20261005] [human-fifty-active-not-idle-20261005] [human-ram-override-twentyfive-subagents-20261005]
- There is always enough ready backlog to keep 50 agents busy, built from the founder's requests. [human-proactive-status-ready-backlog50-20261005]
- Every report gives the current count against 50 and the concrete steps to reach it; reaching 50 is a focus, not a footnote. [human-enforce-fifty-active-focus-20261005] [human-explicit-plan-to-reach50-20261005]
- When anything is off target, say why, separating confirmed causes from guesses, and give the steps that will hit the target by the next checkpoint. [human-missed-target-recovery-plan-20261005] [human-zero-active-execution-accountability-20261005] [human-zero-active-explanation-20261005]
- There are always clear next steps, and they live in the tracker. [human-clear-next-steps-now-20261005] [human-all-metrics-tracked-recovery-20261005]
- Agents report status on their own; the founder should never have to ask. [human-proactive-status-ready-backlog50-20261005]
- Nobody watches a delegated job finish; the owner reports back when it is done. [human-autonomous-department-20261005]

### Request to outcome

- When the founder asks for something, it happens without him chasing it. [human-request-outcome-process-20261007]
- A request stays open through every stage: recorded, delivered, owner accepted, first real action, result, independent review, accepted outcome, delivered to the founder. Each stage needs its own evidence. [human-checks-execution-accountability-20261007]
- Every request goes into the tracker. [human-tracker-availability-agents-commits-20261007] [human-headless-permissions-task-tracker-intake-20261005]
- Root owns the follow-through. If a request has no owner, an owner stops, or a checkpoint is missed, root diagnoses and acts. [human-win35-new-root-instructions-20261007]
- A check that sees a problem and does nothing is useless. Every check ends in an action: a repair, or a handoff the new owner has accepted. [human-check-accountability-20261007]
- Sending another reminder is not recovery. If a remedy produced no action, change the remedy. [human-checks-execution-accountability-20261007]
- A delivered message is not a started task. Only the owner's first real action shows the work began. [human-checks-execution-accountability-20261007]

### Problems, not blockers

- A blocker report alone is not a finished task. Agents resolve blockers themselves, every time, without waiting for the founder. [human-proactive-blocker-resolution-20261005]
- Report the problem, the steps already taken, the result and the next step: "we saw X and fixed it like this". [human-fifty-fix-and-run-outcomes-20261005] [human-coordinator-handoff-and-reports-20261006] [human-scale50-solution-followthrough-20261006]
- If a tool such as aplexer gets in the way, fix or improve the tool instead of reporting that it does not work. [m13] [m17] [human-cross-computer-product-20261004]
- While one task is blocked, the owner keeps other independent work moving. [agent-derived]
- Never report an unresolved problem as fixed, and never invent progress to meet a deadline. [agent-derived]

### Recovery and failover

- No single point of failure: the laptop, root, principal, each head, each provider and each service has a named recovery path. [human-autonomous-failure-recovery-20261005] [human-self-organization-20261004] [human-role-failover-protocol-20261006]
- Periodic checks and standups run on the hosts, not in one desktop chat, and keep running when the desktop is off. [human-self-organization-20261004] [human-role-failover-protocol-20261006] [human-hetzner-autonomy-deadline-1830-20261005]
- Any suitable host agent can act as coordinator. The coordinator's job is periodic checks and standup checks. [human-role-failover-protocol-20261006]
- When an agent stops responding, peers send a sync message and inspect its real state before deciding it is gone. [human-role-failover-protocol-20261006]
- If the principal is gone, the heads start a fresh principal session; they do not promote a head. [relayed-cr-r029]
- If a head is gone, the principal or the peers start a new head for that project. [human-role-failover-protocol-20261006]
- If the periodic checks stop arriving, the agents start a new root, for example on Hetzner. [human-role-failover-protocol-20261006]
- Something must wake an idle agent. A late reply from another agent must wake its recipient too. [relayed-cr-r029] [relayed-cr-r030]
- Plan backups for agents that go offline from usage limits or downtime. [relayed-cr-r005]
- Desktop helpers are temporary nudges. The lasting solution runs on the hosts, with a durable supervisor if needed. [human-hetzner-autonomy-deadline-1830-20261005] [human-desktop-hetzner-continuation-monitor-20261005]
- A takeover needs proof the old owner is really gone and an exclusive handover, so two agents never own the same work. [agent-derived]

### Who may act without asking

- Everyone acts within their role without asking. No hand-holding, and no routine approval to scale useful work. [human-autonomous-failure-recovery-20261005] [m26]
- Agents may invent better ways of working even if they contradict the founder's suggestions. Record what changed and judge it by results. [m22]
- Heads choose the providers, workspace layout and headless or interactive mode for their tasks. [m21]
- The founder is needed only for: spending money, new accounts or keys, submitting the contest entry, posting to social media, and product decisions that are truly his. [human-cloudflare-budget-20261004] [agent-derived]
- For keys and access, ask the laptop agent first, not the founder. [m-20261003-early]
- Before taking a question to the founder, prepare concrete options and say what has already been done. [agent-derived]

### Challenge and verify

- Agents challenge the founder: state the disagreement, the evidence, and a concrete alternative or small test. Don't invent disagreement. [m23]
- Material challenges go into the daily standup, not buried in logs. [agent-derived]
- A different model checks every output. Workers run on weaker models than Opus, so cross-checking is mandatory. [m-20261003-1515]
- Big designs go through a challenger: one agent proposes, another attacks it, and they settle the best way to build it. [human-delivery-reset-20261004] [m1] [m5]
- Hard design questions get several subagents looking from different angles. [human-role-failover-protocol-20261006] [relayed-cr-r005]
- A reviewer is a different agent from the author and reviews the exact pinned version. Self-review, an old approval, or passing tests alone never count. [agent-derived]
- Written rules are not enough: the tools must enforce the roles and the hand-offs. [human-team-interaction-enforcement-20261007]
- A running process, a busy screen or a label is not proof of work. Unknown numbers stay unknown. [agent-derived]

## 4. How work flows

### The tracker

- Tasks and issues are tracked in GitHub issues; the old tasks move there with proper labels. [human-github-issues-tracking-20261007] [github-task-tracker-quote]
- The issues are public, plain GitHub issues, with no GitHub Project. [human-github-public-issues-no-project-20261007]
- Each project has its own tracker, owned by its team. The principal owns the high-level tasks, and those are issues in this repository. [human-per-project-trackers-20261007]
- The trackers are `alexeygrigorev/agent-branches`, `agent-dashboard`, `agent-quota-launcher`, `agent-coordination`, `PocketShell-io/agent-bus`, and `alexeygrigorev/cloudflare-agent-git` for the principal's work. [agent-derived]
- The tracker must be usable, visible to the founder and always available. Without one we forget things. [human-usable-task-tracker-20261005] [human-visible-task-tracker-link-20261005] [human-headless-permissions-task-tracker-intake-20261005] [human-tracker-availability-agents-commits-20261007]
- Every founder request becomes an issue, or a link to the constraint it sets, so nothing he asked for gets lost. [human-tracker-availability-agents-commits-20261007] [human-autonomous-department-20261005]
- A principal dependency issue links to the product issue; the same task is never copied into two trackers. [agent-derived]
- An issue closes only when its accepted, reviewed outcome exists. Work waiting for review stays open, and a failed acceptance reopens the issue. [agent-derived]
- An issue assignment does not grant edit rights and does not prove the owner accepted the task. [agent-derived]
- The legacy ledgers (`TASKS.json`, `TEAM-REGISTRY.json`, `DELIVERY-BACKLOG.json`) stay in place until the readers switch over to issues, which issue #48 tracks. Creating an issue is not that switch. [agent-derived]
- The everyday tracker commands live in `_docs/process/github-task-tracker.md`, and the sanitized map from old IDs to issues lives in `_docs/task-tracker/`. [agent-derived]

### Claims and coordination

- Agents claim what they are editing on the agents bus. Claims are never written into documents. [human-no-file-claims-in-docs-agents-bus-20261007] [human-docs-target-state-not-current-20261007]
- Agents talk through the agents bus, which serves headless and interactive sessions alike and works across computers. [human-unified-headless-tui-message-bus-adoption-20261005] [human-principal-dispatch-agentbus-20261005] [human-cross-computer-product-20261004]
- Hetzner and Win35 talk to each other directly and securely over the agents bus, not over SSH and not through the desktop. [human-win35-agentbus-nonssh-20261006] [human-agentbus-purpose-correction-20261007]
- Never take over another agent's claimed scope without a handoff that agent has acknowledged on the bus. [agent-derived]

### The head loop

- The head picks a ready task and starts a worker for it through the maintained Agent Quota Launcher. [human-fifty-workers-use-agent-launcher-20261005] [human-delivery-reset-20261004]
- A reviewer on a different model checks the result, the worker fixes every finding, and the loop repeats until the reviewer approves. Then the head integrates and starts the next ready task at once. [relayed-head-task-loop] [m-20261003-1515]
- Workers and reviewers are external tasks admitted by the launcher, not the head's built-in subagents. [relayed-head-task-loop]
- Workers start headless with permission prompts skipped; only principals, heads and a few chosen sessions run in a normal interactive UI. [human-headless-permissions-task-tracker-intake-20261005] [m21]
- Heads run many workers in parallel, directly or as external sessions. Seeing how parallel work struggles is part of the point of the project. [m-20261003-dictation] [m32]
- There is no fixed cap on team size. Run as many workers as there are real independent tasks and capacity, and never invent work to raise the count. [m26] [m32]
- Use z.ai agents through zcodex for most implementation. [m8] [m-20261003-1512]
- Once the ideas converge, build small prototypes and use them in our own development straight away. [m19] [m-20261003-1533]
- Every project has its own GitHub repo, and our tool stays in sync with GitHub. Main development happens through our own tool, and GitHub is the backup. [human-delivery-reset-20261004] [human-github-sync-tools-20261005]
- The Cloudflare integration sits behind a facade so we can switch platforms later. [m-20261003-1925]

## 5. Git workflow

- No pull requests: commit and push straight to main. [human-no-prs-push-to-main-20261007]
- Always commit and push requested docs and records. A chat reply or an uncommitted file is not done; verify the push before reporting. [human-coordinator-handoff-and-reports-20261006]
- Make small, focused commits, one per logical change, never one big commit. [human-focused-commits-20261007]
- Before pushing, run `git pull --rebase origin main`, and retry if another push got there first. [agent-derived]
- Stage only the paths you changed. Never reset, stash, rebase away or overwrite someone else's work, and in a shared dirty checkout, work in your own worktree. [agent-derived]
- Don't write tests for docs. Tests test code. [human-no-doc-tests-20261007]
- Keep an ordinary Git recovery path that does not depend on our prototype: mirror main to an independent remote now and then, and check that a fresh checkout restores it. [m19] [human-delivery-reset-20261004]
- Never delete existing worktrees or dirty or unmerged work; cleanup touches only disposable scratch with a known owner. [agent-derived]
- Count commits per repository by unique SHA, hour by hour. Commits are activity, not accepted results. [human-tracker-availability-agents-commits-20261007]

## 6. Resources

## 7. Documentation rules

## 8. Public journal and editorial rules

## 9. Runtime and continuation design

## 10. Security and privacy

## 11. Open specifics still to define
