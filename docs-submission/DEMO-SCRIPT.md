# Demo Script (8-Minute Practical Presentation)

## Scene 1 - Product Problem and Architecture (0:00 - 1:15)

The screen shows the title slide transitioning to a split view of multi-agent development dilemmas and the Agent Branches architecture diagram.

The voice-over introduces the product and architectural boundaries.

> "When multiple AI coding agents work concurrently on a single repository, two major problems arise. Clashes show up late, whether textual merge conflicts or silent combined test breakages. Nobody has a unified view of who is doing what from which base commit. We give every agent its own isolated fork of the canonical repository to solve this. We use a lightweight Node coordinator to track each agent's work-in-progress head on Hetzner servers without ever running Git or executing tests. Cloudflare Workers and Durable Objects adapter source exists solely as an architectural reference. The explicit contest execution runs entirely on Node and Git on Hetzner with no Cloudflare deployment steps. A separate, trusted runner performs the pairwise trial merges and test executions, posting typed results back to the coordinator. The review UI turns this into a real-time safety matrix where unknown is never rendered as safe."

## Scene 2 - Concurrent Source and History (1:15 - 2:30)

The screen shows the terminal and evidence logs demonstrating the concurrent multi-agent execution.

The voice-over explains the recorded concurrent run and evidence qualification.

> "Here we inspect the historical recorded run of three native agents. All three use Gemini 3.1 Pro for tasks a, b, and c, executing with a measured 113-second native active overlap window. We qualify this presentation as an evidence replay of the recorded run against the accepted baseline. We make no claim that new models launch on the fly. Each agent works in its own physical fork with path-scoped authentication and private 0600 token isolation. Git pushes to the coordinator occur sequentially, starting with Task B, then Task A, then Task C. These pushes trigger native post-receive hook notifications through system Node on PATH. By having every task record its explicit intent and base commit SHA, we guarantee verifiable provenance from canonical seed. Three original actors used the same Pro model, while repair used Flash from the same provider. We claim no three separate providers, no two-parent merges, and no physical proof."

## Scene 3 - Task Owner Warning Repair (2:30 - 4:00)

The screen shows terminal outputs and coordinator logs tracking Agent B's initial regression and CHANGES_REQUESTED warning. It then follows Agent B's owner repair session.

The voice-over details the warning detection and owner repair process.

> "A model's initial exit code 0 is never taken as acceptance. On the rehearsal launched from main commit `bbddb4f` — with accepted source changes integrated into `d215e9b7` after the run — an initial live run exited 0. It still exposed two owner-versus-owners test conflicts across 321 executions, with 319 passes and 2 failures. In this repair session, the owner of Task B operated with its own task credentials. It inspected the failure, acknowledged both active warnings on the record before its corrective push, and pushed single-parent commit `2dc07a1b` as a clean repair without fake events. Trusted checks on the same forks then verified 323 executions across tasks, with 108, 107, and 108 tests passing clean. This owner workflow clears the regression while retaining full audit history of prior acknowledgements."

## Scene 4 - Stale 409 and Current Checks in Review UI (4:00 - 5:30)

The screen displays a browser navigating the static Review UI in `prototype/ui/index.html` and `task.html`, with a split view showing runner terminal interactions.

The voice-over explains the safety matrix, stale probe rejection, and UI credential scoping.

> "In the Review UI, we see the live safety radar. When the runner attempts to submit a cached or stale check report against an older head vector, the coordinator rejects it with HTTP 409 Conflict. That leaves server state unchanged, ensuring we never mask new risk with outdated checks. When the runner submits evaluations against the current head vector, typed checks return HTTP 200. Across all three agent pairs, trusted checks execute 108, 107, and 108 tests, totaling 323 test executions, all passing clean alongside our historical 314-test proof. In the UI, authentication is scoped. We grant overview access with HTTP 200 using a runner token stored in localStorage. With the runner credential, a task-detail request returns HTTP 401; a foreign credential returns HTTP 403; the task's own credential returns HTTP 200."

## Scene 5 - Source Backup, Independent Restore and Checker Provenance (5:30 - 6:45)

The screen shows terminal verification of canonical source restore, git fsck validation, API cleanup verification, and checker artifacts.

The voice-over explains the verification and transparent error retention.

> "We anchor system integrity by focusing on independent source recovery. The canonical repository on main commit `d215e9b7` is verified through independent restore. We restore accepted source in a separate HTTPS checkout and verify all five hashes and Git integrity. Separately, 15 combined demo tests pass, and both owned API processes are stopped and verified absent. The original unborn repeat checker failure and missed finite cleanup stay preserved in the historical log. A fresh checker artifact on the exact same original forks and head vector verified complete success without launching new models. Scene 5 of the draft video was initially rejected for omitted error context, then repaired and accepted with explicit historical replay and UI fixture labels."

## Scene 6 - Limits, Unverified Gates and Video Draft Outcome (6:45 - 8:00)

The screen shows a summary slide of accepted components versus open gates.

The voice-over concludes with boundaries and next steps.

> "To summarize our current status, the same-host core, fork isolation, concurrent multi-agent Git push handling, radar safety interface, owner repair, and independent source recovery are accepted on main commit `d215e9b7`. Our draft video recording and reproduction package are accepted with an eight-minute duration of 480.002902 seconds in 1280x720 H264 AAC format, matching exact hash `0e110c48c9b1083b18027d2649a115b68a57539edd61accd985fdec2e9a8ccc4`. Watch the eight-minute evidence-replay draft: [video](videos/agent-branches-demo-draft.mp4). Public evidence in GitHub issue 53 comment 6115851621 supports this fresh milestone. We maintain gate discipline. Physical two-host transport across distinct machines under AC59 remains an open, pending gate, while the AgentBus consistency interface AC60 is accepted interface-only on main at `f389b716`. No physical deployment or final production approval is claimed."

## 8-Minute Shot Checklist

This checklist defines the 8-minute shot sequence aligned with verified baseline evidence:

- Scene 1 (0:00 - 1:15, Product Problem and Architecture). Title card, multi-agent clash diagram, and Hetzner Node HTTP coordinator architecture. Cloudflare Workers and Durable Objects are noted as an architectural reference adapter without executable deploy blocks.
- Scene 2 (1:15 - 2:30, Concurrent Source and History). Historical recorded run of three native agents using Gemini 3.1 Pro in a 113-second active overlap window. Sequential Git pushes from Task B, Task A, and Task C with path-scoped authentication. Labeled as an evidence replay of the recorded run against seeded fixtures without new model launches.
- Scene 3 (2:30 - 4:00, Task Owner Warning Repair). Rehearsal launched from main commit `bbddb4f` (with accepted source changes integrated into `d215e9b7` after the run), exposing two owner-versus-owners test conflicts across 321 executions with 2 failures. Task B owner acknowledges both warnings with its own credential before its corrective push, then pushes single-parent repair `2dc07a1b` to achieve clean status across 323 test executions.
- Scene 4 (4:00 - 5:30, Stale 409 and Current Checks UI). Static Review UI in `prototype/ui/`. Runner submits stale report returning HTTP 409 with state unchanged. Current heads check returns HTTP 200 with 323 test executions clean across three pairs. UI localStorage auth shows runner token returning HTTP 401 on task detail, foreign credential HTTP 403, versus own task credential returning HTTP 200.
- Scene 5 (5:30 - 6:45, Source Backup, Independent Restore and Checker Provenance). Canonical source restore on main commit `d215e9b7` with git fsck exit 0. Separately, 15 combined tests pass. Exact API cleanup with stopped processes absent. Retention of original unborn repeat checker failure and missed cleanup. Fresh checker artifact verifies success on same original forks without new models. Repaired Scene 5 video frame verified.
- Scene 6 (6:45 - 8:00, Limits, Unverified Gates and Video Draft Outcome). Explicit gate review. Draft video verified at 480.002902 seconds and hash `0e110c48c9b1083b18027d2649a115b68a57539edd61accd985fdec2e9a8ccc4`. Public relative link `videos/agent-branches-demo-draft.mp4`. Public milestone supported by issue 53 comment 6115851621. Physical two-host transport under AC59 remains pending. No physical deployment claimed.
