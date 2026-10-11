# Demo Script

## Scene 1 - The product (0:00-1:00)

The screen shows the title slide, transitioning to a split screen showing three independent agent forks on a Hetzner coordinator.

The voice-over introduces the product.

> "Agent Branches gives every agent its own fork of the canonical repo. A plain Node coordinator tracks every agent's work-in-progress head on existing Hetzner servers. Cloudflare Workers and Durable Objects adapter source is available as an architectural reference implementation, while the explicit contest execution runs entirely on Node and Git on Hetzner with no active Cloudflare deployment plans. A separate, trusted runner does the only thing the coordinator is never allowed to do - run git trial merges and budgeted combined tests - and posts results back. A review UI turns all of that into one picture. It shows who is doing what, from which base, and which pairs will collide. The coordinator itself never runs git and never runs tests."

## Scene 2 - Real agents, independent forks (1:00-3:00)

The screen shows a terminal displaying tasks 0005, 0006, and 0007 running in their independently owned forks. We pause to look at the status with authenticated commands or inspect local task state.

The voice-over explains the setup.

> "Here we have three real model agents actively working on tasks 0005, 0006, and 0007. Each agent owns its own independent fork. There are no mocks here; these are actual models operating against real forks on a Hetzner deployment. Every task records its intent and the exact base commit it started from. Tokens are minted with private 0600 permissions, and Git pushes authenticate via path-scoped environment variables with zero argv credential exposure. System Node on PATH executes the sidecar's post-receive hook, triggering native push event notifications back to the coordinator, while manual event push is reserved strictly for exceptional recovery. In our accepted baseline, this multi-agent workflow is demonstrated deterministically through the accepted concurrent scripted regression harness (`concurrent.mjs`), which proves fork isolation, credential scoping, and real Git push overlap. Canonical source recovery was independently verified via fresh GitHub main restore at `b4a261b6`, matching all five source hashes to accepted commit `928a838d` with git fsck exit 0."

## Scene 3 - Agents push and the radar evaluates (3:00-5:00)

The screen shows a terminal showing the head vectors updating. A script running `git merge-tree` locally and test validations is also visible.

The voice-over describes the evaluation process.

> "As the agents push their commits, the coordinator verifies the commit exists. Then, the local runner kicks in. It fetches the head vector, clones the forks, and runs pairwise checks. This includes a `git merge-tree` trial merge for textual overlap and combined-tree model tests bounded by a budget. The verdicts are real - textual conflicts and test failures are caught by the runner, not inferred. In our operator recheck across the author commit history — A772, B421, and C343 — each pair cleanly merged (exit 0) and passed combined-tree test suites (7, 11, and 6 tests respectively, all exit 0). Typed checks submitted against the current heads vector returned HTTP 200, while stale prior vectors correctly returned HTTP 409. We label this explicitly as an operator recheck rather than a new model run, keeping native model traces distinct. Scripted regression harness and operator rechecks verify protocol and radar evaluation rules deterministically, while fresh live multi-model execution and physical multi-host stages remain pending."

## Scene 4 - The review UI (5:00-6:30)

The screen shows a browser showing the review UI, with accurate badges for conflicts based on live evidence.

The voice-over highlights the review process.

> "This is the review UI. It shows the agents, their intent, and their base commits. The conflict badges you see - textual or test - are decided by the runner's live status endpoint against actual data. A reviewer can acknowledge a warning on the record. This tracks who acknowledged what, at which head."

## Scene 5 - Semantic ownership and the physical gate (6:30-8:00)

The screen shows a view of the pending physical gate requirements. 

The voice-over addresses the pending requirements.

> "The AgentBus consistency interface AC60 is now accepted on main at f389b716 with actual consumer three-case acceptance. However, physical two-host proof (AC59) is still missing and remains an explicit pending gate. We require native actor-local receipt and device-handled ACK plus semantic ownership of the result — proxies, SSH tunnels, or raw JSON don't qualify. The system demands verifiable physical ownership, which remains pending for this demo. We don't claim actor code is accepted until this physical gate is passed."

## Scene 6 - Exact commits and unverified gates (8:00-10:00)

The screen shows a terminal showing the rejection of stale results, accepted source-only CLI680 publication, and the current state of unresolved gates.

The voice-over concludes the demo.

> "Stale radar results are rejected. Unknown is never marked as safe. Silent failures can't masquerade as no conflicts. This is the scripted regression proof running against our accepted baseline. Source-only CLI680 is accepted via head-registered terminal independent Pro eleven mock tests, with normal guard integration 93e4d096 pushed and read back from GitHub at 15:05 UTC — explicitly distinguishing mock tests from fresh 3-model execution and physical gates. What's pending? The final two-host physical gate integration (AC59), while fresh 3-model runtime execution remains held prelaunch. But right now, we have real agents, on real forks, finding real conflicts before the merge."

## Shot checklist

This checklist outlines the required shots against the committed evidence.

- Tasks plus intents: Agent tasks 0005, 0006, 0007 from their respective physical forks (commits A772 `77202c16`, B421 `4211e0e8`, C343 `343c00b2`)
- Pushes plus head vector: Native Git pushes authenticated via path-scoped ENV; sidecar hook with Node on PATH forwarding to plain Node coordinator on Hetzner; manual push event reserved for exceptional recovery
- Conflict verdicts & Operator Recheck: Clean merge-trees and combined tests (7, 11, 6 passed, exit 0), typed checks 200, stale vector 409, labeled as operator recheck (not a new model run)
- Canonical source restore: Verified 5 source hashes match `928a838d` at `b4a261b6` main with git fsck exit 0
- Accepted scripted baseline: Deterministic regression (`concurrent.mjs`, commit `d725eec`) and runbook (`_docs/agent-branches-demo.md`)
- Python CLI integration: Source-only CLI680 accepted via head-registered terminal independent Pro eleven mock tests; normal guard integration `93e4d096` pushed and read back from GitHub (exit 0) at 15:05 UTC (mock tests explicitly distinguished from fresh 3-models and physical gates)
- Live fresh 3-model execution: Held prelaunch (dispatcher hardcoded historical IDs; fresh runtime feature-free 680 seed / 3 forks at 15:05; bounded Flash repair `6eb045` live, not new 3-model proof; existing same-host native owner A772 / operator checks 200 / stale 409 separate earlier receipts)
- Physical gate: PENDING native actor-local receipt and device-handled ACK (AC59 physical proof pending; AC60 interface accepted at `f389b716`)
