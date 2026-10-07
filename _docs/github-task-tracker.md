# GitHub task tracker

Tasks are plain public GitHub issues. Each product team owns the issues of its own repo. The principal's high-level and cross-project tasks live in this repo.

## Where issues live

- Agent Branches: alexeygrigorev/agent-branches
- Agent Dashboard: alexeygrigorev/agent-dashboard
- Agent Quota Launcher: alexeygrigorev/agent-quota-launcher
- Agent Coordination: alexeygrigorev/agent-coordination
- Agent Bus: PocketShell-io/agent-bus
- Principal, dependencies, research: alexeygrigorev/cloudflare-agent-git

## Labels

- project: one per product, for example project:agent-dashboard. This repo also uses project:portfolio, project:publication, project:continuation-runtime and project:infrastructure.
- type: feature, review, recovery, operations, documentation.
- status: queued, in-progress, review, blocked. Exactly one at a time.
- priority: p0, p1, unspecified.
- routing:needs-reconciliation means the project is not confirmed yet.
- migration:legacy-task, closure:legacy-record, evidence:needs-audit and status:legacy-closed mark older history. Keep them. Never add them to new issues.

## Everyday commands

Find your next task (add `--label priority:p0` to see urgent ones first):

```sh
gh issue list --repo OWNER/REPO --state open --label status:queued
```

Create a task:

```sh
gh issue create --repo OWNER/REPO --title 'Concrete outcome' --body-file task.md --label project:NAME,type:feature,status:queued,priority:unspecified
```

Comment and change status:

```sh
gh issue comment NUMBER --repo OWNER/REPO --body-file progress.md
gh issue edit NUMBER --repo OWNER/REPO --add-label status:in-progress --remove-label status:queued
```

Close with accepted evidence, or reopen:

```sh
gh issue close NUMBER --repo OWNER/REPO --reason completed --comment 'Accepted: commit SHA, reviewer, review verdict'
gh issue reopen NUMBER --repo OWNER/REPO --comment 'Why acceptance failed'
```

Link a dependency: put `Depends on OWNER/REPO#NUMBER` in the issue body and comment the link on the other issue. A dependency issue in this repo links to the product issue. Never copy one task into two trackers.

## Rules

- Close an issue only when a distinct reviewer approved the exact version and it is integrated. Work waiting for review stays open with status:review.
- Reopen a failed acceptance. Keep missed deadlines in the history.
- An assignee or a label is not ownership, admission or progress evidence.
- Issues are public. No secrets, host addresses, quota balances, transcripts or private evidence. Post a sanitized summary.
