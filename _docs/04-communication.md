# Communication

Agents talk to each other over the agents bus, on one computer or across several, in headless and interactive sessions alike. Everything you need from another agent goes through it. Never type into another agent's session, and never write to a busy screen, a menu or a draft.

## Who talks to whom

- Root talks to the principal and the heads.
- The principal talks to root and the heads.
- A head talks to the principal, root and its own implementers and reviewers.
- An implementer or a reviewer talks only to its head.
- Between root and the others, most messages are status updates.
- When root sees that something is absent, it tells the principal and resolves it. When the principal sees that something is absent, it tells root and resolves it. For an absent principal or head, resolving it means running `scripts/recover-agent <tag>`, described in `_docs/05-recovery.md`.

## Sending and receiving

- Every agent has a tag, which is its name on the bus. `a whoami --json` shows yours.
- Send with `a message send --to TAG "text"`. Use `--all` for every other agent in the workspace and `--to-engine ENGINE` for one engine. The kind is a note, a handoff or a reply.
- Read your inbox at startup and every time a turn ends: `a message inbox`, then `a message show ID`. Read and act on every unread message.
- Answer with `a message reply ID "text"`, so the answer stays with the thread. A late reply wakes its recipient.
- When you have handled a message, acknowledge it with `a message ack ID`. An acknowledgement means the message was read and handled. It does not mean the work is done, and a delivered message is not a started task. Send a separate message when the work is finished.
- If an agent stops responding, send it a sync message and inspect its state before you decide it is gone.

## Writing a message

- Make it self-contained. Say what you need, who owns it, when it is due and what has already been done, and link the issue.
- Keep it short. Long evidence goes into an issue comment or into git-ignored `.local/`, and the message carries the link or the path.
- Put no secrets, host addresses, quota balances or private evidence in a message. Keys reach a machine as a file with mode 600 on that machine, never in a message.

## Handoffs and claims

- A handoff names the new owner and the task packet. The new owner takes over only after acknowledging it on the bus, and then owns the work exclusively.
- Claim the files you will edit on the bus before you touch them, and release them when you finish. Claims are never written into documents.

## The founder

- Messages to the founder are rare, and every one costs us. Send one only for spending money, new accounts or keys, the contest entry, social media posts or his own product decisions. Come with concrete options and say what has already been done.
- Status, problems and results reach him through the daily standup and the report, without him asking.
- His messages are saved verbatim in that day's file in `_docs/founder-journal/` on the day they arrive.
