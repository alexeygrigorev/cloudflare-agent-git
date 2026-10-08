# Communication

Agents talk to each other over the agents bus, on one computer or across several, in headless and interactive sessions alike. Everything you need from another agent goes through it. Preserve busy screens, drafts and unknown prompts. Use only the supported, bounded exceptions below when controlling an owned session.

## Checking a TUI launch

After every TUI start or resume, the launch owner immediately inspects the actual screen and confirms the intended session and authorized task workspace. This applies to root launching a principal, a principal launching heads, and heads launching TUI workers or reviewers. If the known “Folder access” / “Trust and continue” prompt appears for that workspace, accept it through supported native control without asking for another confirmation. Inspect the screen again to verify the gate cleared, then verify readiness and a real first useful action; a running process alone does not complete startup. Check the screen even when no trust prompt appears. This is the launch owner's duty, with no extra user or root approval dependency. Preserve busy panes, drafts, unknown folders and other prompts, and all identity, election, quota and resource gates.

## Who talks to whom

- Root talks to the principal and the heads.
- The principal talks to root and the heads.
- A head talks to the principal, root and its own implementers and reviewers.
- An implementer or a reviewer talks only to its head.
- Between root and the others, most messages are status updates.
- Root restores an unavailable principal using [principal recovery](../recovery/principal.md); the principal restores heads using [head recovery](../recovery/head.md) and reports outcomes to root. Reuse scoped remote recovery agents for independent work. Delivery is not recovery: require custody, actual useful action and a next checkpoint. Check [installed recovery status](05-recovery.md) before assuming a helper exists.

## Sending and receiving

- Every agent has a tag, which is its name on the bus. `a whoami --json` shows yours.
- Send with `a message send --to TAG "text"`. Use `--all` for every other agent in the workspace and `--to-engine ENGINE` for one engine. The kind is a note, a handoff or a reply.
- Read your inbox at startup and every time a turn ends: `a message inbox`, then `a message show ID`. Read and act on every unread message.
- Answer with `a message reply ID "text"`, so the answer stays with the thread. A reply in the inbox does not wake an idle recipient; see [keeping heads moving](#keeping-heads-moving).
- When you have handled a message, acknowledge it with `a message ack ID`. An acknowledgement means the message was read and handled. It does not mean the work is done, and a delivered message is not a started task. Send a separate message when the work is finished.
- If an agent stops responding, send it a sync message and inspect its state before you decide it is gone.

## Keeping heads moving

A message alone sits in the inbox of an idle agent and moves nothing. Inbox delivery never wakes an idle agent. Every wait therefore needs a wake-up that actually works today.

- When a head or agent finishes a unit of work, it reports to its principal by bus message and asks for a synchronous reply.
- A synchronous reply is a bus message plus the same text typed into the head's session with `aplexer send <tag> --enter`, so the head wakes and continues. This is the one case where typing into another session is allowed, and only at an idle, empty prompt.
- The synchronous reply is the working mechanism today. `aplexer wake` is the intended self-wakeup for an agent that waits: one time with `--once --in 5m`, or repeating with `--every 2m` until `aplexer wake off`, stopped by `--until-message` when a message arrives, typing only while the session is idle. It is available only once it is merged and installed. Run `aplexer wake --help` first; if the command is missing, do not rely on it.
- Rule: no head goes idle waiting without a promised synchronous reply or, where `aplexer wake` is installed, a wake job, and it turns the wake off when the wait is over.
- The principal sends synchronous replies promptly. A head never ends a turn with an unresolved dependency and no promised reply or wake.
- Automatic recovery of missing sessions is not established by any of this. It is tracked in [issue 102](https://github.com/alexeygrigorev/cloudflare-agent-git/issues/102), whose acceptance gates are unattended productive cycles and a fenced test failover; see [recovery](05-recovery.md).

## Writing a message

- Make it self-contained. Say what you need, who owns it, when it is due and what has already been done, and link the issue.
- Keep it short. Long evidence goes into an issue comment or into git-ignored `.local/`, and the message carries the link or the path.
- Put no secrets, host addresses, quota balances or private evidence in a message. Keys reach a machine as a file with mode 600 on that machine, never in a message.

## Handoffs and claims

- A handoff names the new owner and the notes on the task. The new owner takes over only after acknowledging it on the bus, and then owns the work exclusively.
- Claim the files you will edit on the bus before you touch them, and release them when you finish. Claims are never written into documents.

## The founder

- Messages to the founder are rare, and every one costs us. Send one only for spending money, new accounts or keys, the contest entry, social media posts or his own product decisions. Come with concrete options and say what has already been done.
- Status, problems and results reach him through the daily standup and the report, without him asking.
- His messages are saved verbatim in that day's file in `_docs/founder-journal/` on the day they arrive.
