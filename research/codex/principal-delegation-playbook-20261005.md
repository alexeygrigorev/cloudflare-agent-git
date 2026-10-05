# Principal delegation playbook — 5 October 2026

Authority: [latest exact human intake](../../experiment/human-principal-dispatch-agentbus-20261005.txt), [role contract](../../coordination/ROLE-CONTRACT.md), [operating model](../../coordination/OPERATING-MODEL.md), and [resource policy](../../coordination/RESOURCE-POLICY.md). This document proposes a precise addition for the canonical role-contract owner; it does not claim that startup enforcement is installed.

## Dispatch rule

The principal monitors the big picture, progress, capacity, dependencies and delivery evidence. The principal does not implement product code, personally review product code, or run product test harnesses.

For a simple ad hoc request, launch a scoped subagent with explicit paths, responsibility, evidence requirements and boundaries. For substantial product work, forward the outcome and acceptance contract to the existing interactive project head. The head decomposes work, launches independently owned implementers and separate reviewers, resolves failures, accepts results, integrates recoverably, and synchronizes GitHub. Do not build a competing implementation team under the principal.

When a request crosses teams, the principal coordinates interface ownership and sequencing. Confirm the receiver's actual ownership ACK and first useful action. An offer or inbox read is not an accepted handoff. If delivery or execution fails, arrange an owned bounded repair and independent ready work; do not take over the head's coding or wait for a desktop heartbeat.

## AgentBus application

The public repository [PocketShell-io/agent-bus](https://github.com/PocketShell-io/agent-bus) exists. Repository existence alone does not establish that aplexer's messaging functionality has been fully ported, that sessionless agents have adopted it, or that native cross-computer recovery has passed. The principal must obtain those outcomes from the head's pinned evidence.

1. Identify the existing responsible interactive head and obtain an explicit AgentBus ownership ACK. Record its genuine identity, workspace, source custody, integration owner, ready queue and next continuation event. Preserve previous owners and histories; do not invent a new head or silently transfer custody.
2. Ask the head to map the actual aplexer messaging surface to an extraction backlog: enrolled identities independent of UI sessions; durable send/inbox/read/reply/ACK; typed delivery versus read versus semantic outcome; idempotency, retries and cursor recovery; scoped access; transport adapters and cross-computer addressing. Identify preserved behavior, gaps and incompatible assumptions.
3. The head launches useful parallel zcy/zcodex lanes after fresh provider, route and host gates. Candidate lanes are sessionless identity/storage, CLI and API parity, aplexer compatibility adapter, authenticated transport/offline recovery, and independent negative-case review. These are proposed work partitions, not claims of running agents. Assign nonoverlapping files or isolated branches, explicit interface handoffs and exact reviewer pins. Do not launch duplicate writers merely to increase counts.
4. First adoption milestone: two genuine sessionless agents use independently enrolled identities to exchange an actual useful task and result, without requiring aplexer UI sessions or borrowing the principal/head mailbox. Retain exact message IDs, recipient ACK, first tool and changed artifact, and a separate reviewer verdict. Test duplicate send, missing recipient, receiver restart, replay and offline recovery narrowly. Keep ordinary Git and existing safe messaging fallback.
5. Integrate accepted changes through the head, push intended sanitized source, verify GitHub branch/main SHA, and document runnable commands. Then prove bidirectional communication and offline reconciliation on two distinct computers with a named integration owner. One-host mocks or SSH access to the old mailbox do not close this gate.
6. At each completion or failure, the head consumes the actual outcome, checkpoints, routes independent review, updates tasks, and starts the next ready task. Record a durable completion/dependency trigger and verify a subsequent useful cycle rather than relying on human reminders.

No fixed worker-count cap applies, but fresh quotas, actual supported model routes, memory/task limits, root disk floor, scratch budget, the Rust hold, privacy and no new purchases remain binding. Keep useful work moving on a verified alternative if ZCode is unhealthy; do not bypass admission. Count heads, workers and services separately. A PID, receiver ACK or passing fixture is not an adopted feature. Unknown usage remains unknown.

## Status and reusable reporting

For every substantial request report: named head and actual ACK; owned next milestone; verified first action; exact artifact/commit; independent reviewer result; integration and remote SHA; unresolved dependency with repair owner and check; next durable trigger. Publish meaningful outcomes and concrete failures, not repeated idle/status noise. Feed repeated coordination workarounds into a head-owned product intake with a falsification test.

Apply this same dispatch structure to other products. Require the role contract and scoped handoff to be read at startup, with actual actor/parent identity and owned-path receipt. A documented startup requirement is distinct from verified template rollout and a newly started worker's read receipt.

## Proposed canonical addendum for the role-contract owner

> Principals do not implement or personally review product code. Simple ad hoc requests are delegated to scoped subagents; substantial product work is routed to the responsible interactive project head. Heads own decomposition, implementer and independent-reviewer launches, acceptance, integration/recovery and verified GitHub synchronization. Principals confirm actual ownership ACK, useful first action, outcome evidence and the next durable continuation condition, coordinating cross-team dependencies without becoming a per-change approval bottleneck. Every startup reads this role contract and records the actual role, parent identity, scope and handoff read receipt. An inbox delivery, PID or repository's existence is not implementation or adoption acceptance.

Canonical publication and startup-template rollout remain the role-contract owner's task. This ad hoc documentation helper has no native inbox, ACK, delivery, inherited mailbox, service or process authority.
