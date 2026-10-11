# Demo Script (8-Minute Practical Presentation)

## Scene 1 - Product Problem & Architecture (0:00 - 1:15)

The screen shows the title slide transitioning to a split view of multi-agent development dilemmas and the Agent Branches architecture diagram.

The voice-over introduces the product and architectural boundaries.

> "When multiple AI coding agents work concurrently on a single repository, two major problems arise: clashes show up late — whether textual merge conflicts or silent combined test breakages — and nobody has a unified view of who is doing what from which base commit. Agent Branches solves this by giving every agent its own isolated fork of the canonical repository. A lightweight Node coordinator tracks each agent's work-in-progress head on Hetzner servers without ever running Git or executing tests. Cloudflare Workers and Durable Objects adapter source exists solely as an architectural reference implementation, while the explicit contest execution runs entirely on Node and Git on Hetzner with no Cloudflare deployment steps. A separate, trusted runner performs the pairwise trial merges and test executions, posting typed results back to the coordinator. The review UI turns this into an honest, real-time safety matrix where 'unknown' is never rendered as safe."

## Scene 2 - Genuine Actual Concurrent Source & History (1:15 - 2:30)

The screen shows the terminal and evidence logs demonstrating the genuine concurrent multi-agent execution.

The voice-over explains the recorded concurrent run and evidence qualification.

> "Here we inspect the recorded run of three native agents — all Gemini 3.1 Pro, handling tasks a, b, and c — executing with a measured 113-second native active overlap window. We qualify this presentation as an evidence replay of the recorded actual run against the accepted baseline, making no claim that new models are launched on the fly. Each agent works in its own physical fork with path-scoped authentication and private 0600 token isolation. Git pushes to the coordinator occur sequentially (Task B, then Task A, then Task C), triggering native post-receive hook notifications via system Node on PATH. Every task records its explicit intent and base commit SHA, guaranteeing verifiable provenance from canonical seed."

## Scene 3 - Authentic Owner Warning Repair (2:30 - 4:00)

The screen shows terminal outputs and coordinator logs tracking Agent B's empty-string contract regression, the resulting warning and CHANGES_REQUESTED status, followed by Agent B's owner repair session.

The voice-over details the warning detection and owner repair process.

> "A model's initial exit code 0 is never taken as acceptance. When Agent B first pushed, an empty-string contract regression triggered legitimate test conflicts in pairwise evaluation, causing the coordinator to issue CHANGES_REQUESTED and surface warnings. In this repair session, the authentic owner of Task B — operating with its own task credentials via the Launcher — inspected the failure, acknowledged both active warnings on the record, retracted its earlier flawed claim, and pushed single-parent commit `8fc` as a clean repair (not a native two-parent merge). This authentic owner workflow clears the regression cleanly while retaining full audit history of prior acknowledgements."

## Scene 4 - Actual Stale 409 & Current Checks in Review UI (4:00 - 5:30)

The screen displays a browser navigating the static Review UI (`prototype/ui/index.html` and `task.html`), with a split view showing runner terminal interactions.

The voice-over explains the safety matrix, stale probe rejection, and UI credential scoping.

> "In the Review UI, we see the live safety radar. When the runner attempts to submit a cached or stale check report against an older head vector, the coordinator strictly rejects it with HTTP 409 Conflict, leaving server state unchanged — ensuring outdated checks never mask new risk. When the runner submits evaluations against the current head vector, typed checks return HTTP 200. Across all three agent pairs, trusted checks execute 107, 102, and 105 tests — 314 test executions in total — all passing clean. In the UI, authentication is strictly scoped: bearer tokens stored in localStorage enable overview access (HTTP 200) with a runner token, while per-task private details correctly return HTTP 401 unless authorized with the task's own credential."

## Scene 5 - Source Backup, Independent Restore & Checker Provenance (5:30 - 6:45)

The screen shows terminal verification of canonical source restore, git fsck validation, API cleanup verification, and checker artifacts.

The voice-over explains the verification and transparent error retention.

> "System integrity is anchored by focused, independent source recovery. The canonical repository on main `76cc378` is verified via independent restore, matching source hashes with git fsck exit 0 and verified exact matched API cleanup. We practice radical transparency: the original unborn repeat checker failure and missed finite cleanup are preserved in the historical log. A fresh checker artifact executed against the exact same original forks and head vector — without launching new models — verified complete success, demonstrating that the failure was strictly an environmental artifact rather than a flaw in the core protocol."

## Scene 6 - Limits, Unverified Gates & Remaining Physical Proof (6:45 - 8:00)

The screen shows a summary slide of accepted components versus open gates.

The voice-over concludes with honest boundaries and next steps.

> "To summarize our current status: the same-host core, fork isolation, concurrent multi-agent Git push handling, radar safety contract, authentic owner repair, and independent source recovery are accepted on main at `76cc378`. However, we maintain strict gate discipline: no full contest acceptance is claimed. Physical two-host transport across distinct machines (AC59) remains an open, pending gate, while the AgentBus consistency interface AC60 is accepted interface-only on main at `f389b716`. Furthermore, final physical video recording is pending. Agent Branches proves that multi-agent Git collaboration can detect conflicts before merge — verified honestly on real code."

## 8-Minute Shot Checklist

This checklist defines the 8-minute shot sequence aligned with verified baseline evidence:

- **0:00 - 1:15 (Scene 1: Product Problem & Architecture)**: Title card; multi-agent clash diagram; Hetzner Node HTTP coordinator architecture; Cloudflare Workers/DO noted strictly as reference implementation (no executable deploy block).
- **1:15 - 2:30 (Scene 2: Genuine Actual Concurrent Source & History)**: Recorded run of 3 native agents (all Gemini 3.1 Pro, tasks a/b/c) in 113s active overlap window; sequential Git pushes (B -> A -> C); path-scoped ENV auth; qualified as evidence replay of recorded actual run vs seeded fixture (no new models launched).
- **2:30 - 4:00 (Scene 3: Authentic Owner Warning Repair)**: Agent B empty-string contract regression; runner catching failure; CHANGES_REQUESTED; Agent B authentic owner acknowledging both warnings with own task credential, retracting earlier claim, and pushing single-parent repair `8fc` (NOT a native 2-parent merge).
- **4:00 - 5:30 (Scene 4: Actual Stale 409 & Current Checks UI)**: Static Review UI (`prototype/ui/`); runner submitting stale report returning HTTP 409 (state unchanged); current heads check returning HTTP 200 with 107/102/105 = 314 test executions across 3 pairs clean; UI localStorage auth key showing runner 401 vs own task credential 200.
- **5:30 - 6:45 (Scene 5: Source Backup, Independent Restore & Checker Provenance)**: Canonical source restore on main `76cc378` with git fsck exit 0; exact matched API cleanup; retention of original unborn repeat checker failure and missed finite cleanup; fresh checker artifact verifying success on same original forks/vector (no new models).
- **6:45 - 8:00 (Scene 6: Limits & Remaining Physical Proof)**: Explicit gate review; AC59 physical two-host transport gate PENDING (AC60 interface accepted at `f389b716`); actual video recording PENDING; no claim of full contest acceptance or pre-recorded final video.
