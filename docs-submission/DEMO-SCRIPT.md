# Demo Script

## Scene 1 - The product (0:00-1:00)

The screen shows the title slide, transitioning to a split screen showing three independent agent forks on a Hetzner coordinator.

The voice-over introduces the product.

> "Agent Branches gives every agent its own fork of the canonical repo. A plain Node coordinator tracks every agent's work-in-progress head. A separate, trusted runner does the only thing the coordinator is never allowed to do - run git trial merges and budgeted combined tests - and posts results back. A review UI turns all of that into one picture. It shows who is doing what, from which base, and which pairs will collide. The coordinator itself never runs git and never runs tests."

## Scene 2 - Real agents, independent forks (1:00-3:00)

The screen shows a terminal showing tasks 0005, 0006, and 0007 running in their independently owned forks. We pause to look at the status with `curl` or `cat`.

The voice-over explains the setup.

> "Here we have three real model agents actively working on tasks 0005, 0006, and 0007. Each agent owns its own independent fork. There are no mocks here; these are actual models operating against real forks on a Hetzner deployment. Every task records its intent and the exact base commit it started from. The agents are driving this end-to-end."

## Scene 3 - Agents push and the radar evaluates (3:00-5:00)

The screen shows a terminal showing the head vectors updating. A script running `git merge-tree` locally and test validations is also visible.

The voice-over describes the evaluation process.

> "As the agents push their commits, the coordinator verifies the commit exists. Then, the local runner kicks in. It fetches the head vector, clones the forks, and runs pairwise checks. This includes a `git merge-tree` trial merge for textual overlap and combined-tree model tests bounded by a budget. The verdicts are real - textual conflicts and test failures are caught by the runner, not inferred."

## Scene 4 - The review UI (5:00-6:30)

The screen shows a browser showing the review UI, with accurate badges for conflicts based on live, physical evidence.

The voice-over highlights the review process.

> "This is the review UI. It shows the agents, their intent, and their base commits. The conflict badges you see - textual or test - are decided by the runner's live status endpoint against actual data. A reviewer can acknowledge a warning on the record. This tracks who acknowledged what, at which head."

## Scene 5 - Semantic ownership and the physical gate (6:30-8:00)

The screen shows a view of the pending physical gate requirements. 

The voice-over addresses the pending requirements.

> "AgentBus interface AC60 is currently rejected and under repair. We explicitly require a physical gate with native actor-local receipt and device-handled ACK plus semantic ownership of the result. Proxies, SSH, or raw JSON don't qualify here. The system demands verifiable, physical ownership, which remains a pending recording requirement for this demo. We don't claim actor code is accepted until this strict gate is passed."

## Scene 6 - Exact commits and unverified gates (8:00-10:00)

The screen shows a terminal showing the rejection of stale results and the current state of unresolved gates.

The voice-over concludes the demo.

> "Stale radar results are rejected. Unknown is never marked as safe. Silent failures can't masquerade as no conflicts. This is the scripted regression proof running against our accepted baseline. What's pending? The final two-host physical gate integration. But right now, we have real agents, on real forks, finding real conflicts before the merge."

## Shot checklist

This checklist outlines the required shots against the committed evidence.

- Tasks plus intents: Agent tasks 0005, 0006, 0007 from their respective physical forks
- Pushes plus head vector: Live telemetry JSON from Hetzner plainNode coordinator
- Conflict verdicts: Local runner `merge-tree` and model test outputs
- Physical gate: PENDING native actor-local receipt and device-handled ACK
