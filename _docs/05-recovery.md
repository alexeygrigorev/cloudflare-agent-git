# Recovery

This says who watches whom and who restarts whom, so that nothing depends on a single agent staying up.

## The chain

- The founder starts root in a GUI session on his laptop or on Win35. Root never runs on Hetzner, which is a server without a GUI. It reaches Hetzner and the other machine with ssh.
- Periodic scripts launch the principal and the five heads in aplexer sessions. Each run calls `scripts/recover-agent <tag>` for the principal and for every head, so one that is missing comes back on the next run (issue 102).
- Root watches the principal and the heads. Every 30 minutes, and once a day for the standup, it checks that each one is running and not idle with ready work. Every check leaves a record on the agents bus.
- When root sees that the principal or a head is absent, it tells the principal and resolves it by running `scripts/recover-agent <tag>`. When the principal sees that a head is absent, it tells root and resolves it the same way.
- The principal is accountable that all five heads are running.
- A mechanical process restarts root and the principal when they cannot restart each other. The supervisor watches root's check records. When they stop for two checks, it restarts root through the Agent Quota Launcher. When the principal stops responding and root has not restarted it, the supervisor restarts the principal the same way.
- The supervisor runs as a system service that the host restarts. It never makes judgments and never approves work.
- If the supervisor is also down, the heads start a fresh root first and then a fresh principal. This is the last resort, and a head never promotes itself to principal or root.

## How a restart works

- Restarts go through one script, `scripts/recover-agent <tag>`. The periodic scripts run it, root and the principal run it, and the supervisor runs the same script when it detects inactivity or no response. It sends a sync message, inspects the agent's state, nudges an idle agent, and restarts a silent one through the launcher with `/goal`. An agent that answers is never replaced.
- Whoever starts a Claude or Codex agent sends it `/goal` as a direct session message.
- A replacement takes over only after proof the old agent is gone or an acknowledged handover. It takes exclusive ownership so the old agent cannot keep writing.
- A replacement rebuilds its context from the tracker, the agents bus and the founder journal, not from memory.
- If the old agent comes back, it looks on the bus for a newer one before doing anything. If there is one, it stops acting in that role, hands over what it was carrying and leaves. There is never more than one root and never more than one principal.
- Workers keep running when the head or principal that started them stops. Implementers and reviewers run headless, never in their own aplexer session.

## What root tells the founder

- When something has to be restarted, root says what stopped, what was restarted and what the new agent is doing, in the next report.
- Root brings back what the founder needs, such as the link to the published post and the summary he can share. Nothing is posted automatically.
