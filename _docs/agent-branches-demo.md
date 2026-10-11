# Agent Branches Prototype Demo Runbook

## Overview

This document provides reproducible technical run instructions and a timed 5-10 minute contest demo narrative for the Agent Branches prototype. The prototype demonstrates a concurrent regression harness where multiple simulated agents make overlapping, disjoint edits that resolve in conflicts. It securely verifies API boundaries and pair-status read authentication.

Note: This harness uses scripted regression actors. Model author output alone isn't full issue acceptance.

## Prerequisites

These are the prerequisites to run the demo:

- Node.js: Minimum Node environment (v18+) is required, which emits experimental warnings for global fetch. You must build `prototype/.build/node/src/local/main.js` before running. No extra global dependencies are required.
- Git: System git must be available in your PATH.

## Technical Run Instructions

Execute the following portable project-relative commands to run the local harness. Ensure you're at the repository root. You can reuse existing node_modules or run an optional clean install:

```bash
# Optional clean install: npm --prefix prototype ci
npm --prefix prototype run build:node

# The script requires the working directory to be the project root.
node prototype/demo/concurrent.mjs
```

## Credentials and Security Boundaries

The system enforces the following security boundaries:

- Credentials: Git uses the environment variables GIT_CONFIG_COUNT, GIT_CONFIG_KEY_0, and GIT_CONFIG_VALUE_0 to inject bearer tokens via http.extraHeader. Tokens aren't hardcoded in literals, argv, URLs, or published logs. No 0600 files are used.
- Boundaries: The git sidecar manages real git objects and push webhooks locally. The Coordinator runs as a plain Node HTTP server, strictly handling state coordination and authorization.
- Observable Evidence and Cleanup: The script generates ephemeral git repositories inside `.local/tmp/harness-*`, asserts 401/403/409 HTTP boundaries, and outputs a `result.json` on success. It uses signal traps and PID tracking to securely terminate sidecar and coordinator processes without leaking orphans.

## Demo Narrative and Shot List

The script executes in a few seconds. To make the 5-10 minute presentation actionable, you must pause to inspect post-run evidence in the terminal and `result.json` between these logical steps:

## Shot 1: Bootstrapping the Harness
- Action: Run the harness script.
- Observation: The sidecar and coordinator start on ephemeral ports.
- Check: The system returns 401 Unauthorized for an anonymous GET /status, proving the current 0.1.x read-authentication API is enforced. Also, anonymous GET /tasks/:id returns 401.

## Shot 2: Agent Task Creation and Local Forks
- Action: The system invokes POST /tasks using the admin token to create tasks for Agent A, Agent B, and Agent C.
- Observation: Three distinct agent identities are provisioned, returning scoped short-lived write tokens. Ephemeral clones are established via smart HTTP against the local sidecar.

## Shot 3: Concurrent Push and Conflict Generation
- Action: Agents commit to their clones concurrently and push to origin main using child_process.spawn for genuine overlap.
- Observation: The harness verifies positive millisecond overlap between pushes. The trusted runner fetches changes and verifies git merge-tree a b exits with 1 (textual conflict).

## Shot 4: API Declaration and Reviewer Result
- Action: The trusted runner submits POST /checks declaring contract: "0.1" explicitly. It submits both the textual conflict pair [a, b] and the clean disjoint pair [a, c].
- Observation: GET /status securely reflects both the conflict pair warning and the clean pair status.
- Check: The system attempts to ACK the warning as the wrong agent (using Agent C's token), correctly yielding 403 Forbidden. The true owner (Agent A) securely acknowledges it with 200 OK. Foreign POST /tasks/:id/tests correctly yields 403.

## Shot 5: State Invalidation and Owner Acknowledgement
- Action: Agent A pushes an updated, repaired commit.
- Observation: Submitting the old stale head vector to POST /checks correctly returns 409 Conflict. The active warning is properly invalidated by the new push, reverting the pair status to not_checked with stale: true.
- Result: Output hashes are verified, a final result.json is generated with true concurrency timestamps, and all child processes clean up gracefully.

## Pending Live Gates and Limitations

Here are the pending live gates and constraints:

- Genuine Simultaneous Launcher Actors: True concurrent AI model agents launching and communicating in real time remain pending.
- Physical Two-Host Identity and Custody: Physical separation requiring durable two-host identity receipts and device-handled ACKs is pending evidence. JSON consistency and SSH logs alone don't prove native cross-host ownership.
- Semantic Ownership Reply: The Agent Bus interface is owned by agent-coordination-head. Reviewed schema handoff is pending and CLI tooling is strictly constrained.
- Full Acceptance: Model author output isn't full issue acceptance. Missing live steps require verifications against independent flash reviews before source changes occur.
