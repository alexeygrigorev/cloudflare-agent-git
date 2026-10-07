# Projects

The work is five products. Each product has its own team, its own repo and its own tracker, which is the issues of that repo. The head of the product owns the tracker.

## Agent Branches

- Our Git tool. Folder ~/git/agent-branches, GitHub alexeygrigorev/agent-branches.
- It solves the founder's own pain: every worktree copies the whole workspace and fills the disk, worst of all with Rust builds. The product must not be Rust-focused.
- It needs a CLI the founder can demo, including a `branches sync git` style command that syncs everything to Git.
- Main development happens through this tool, which stays in sync with GitHub. GitHub is the backup.

## Agent Dashboard

- Folder ~/git/agent-dashboard, GitHub alexeygrigorev/agent-dashboard.
- It shows measured numbers only: agents run, tokens used, features done and tasks resolved, broken down by hour, per project and per team, next to active agents and commits.
- The public website shows these numbers as history by hour, with readable charts.

## Agent Quota Launcher

- Folder ~/git/agent-quota-launcher, GitHub alexeygrigorev/agent-quota-launcher.
- It starts workers and reviewers that run as separate sessions, checks quota before every launch, and routes work to a provider that has quota left. A fallback provider is a new launch through the launcher.
- It records usage statistics so its choices get smarter. It is built to be useful outside this project.

## Agent Coordination

- Agents talking across computers. Folder ~/git/agent-coordination, GitHub alexeygrigorev/agent-coordination.
- Hetzner and Win35 share one pool of provider quota and talk directly and securely over the agents bus, never over SSH or through the desktop. Both connect outbound, so neither needs inbound access. SSH is only for setup and recovery.
- During a network split, only work authorized in advance and isolated continues. Nothing integrates until the hosts reconnect and reconcile.

## Agent Bus

- The message bus, separate from aplexer. Folder ~/git/agent-bus, GitHub PocketShell-io/agent-bus.
- Agents use it to talk to each other, on one computer or across several, in headless and interactive sessions alike.
- Claims live on the bus. A claim is a note saying which files an agent is editing, so two agents do not edit the same thing.
- Messaging between agents costs close to nothing.

## This repo

- Folder ~/git/cloudflare-agent-git, GitHub alexeygrigorev/cloudflare-agent-git. It holds the portfolio-level docs and the principal's tasks, as issues.
