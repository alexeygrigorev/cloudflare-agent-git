# Demo diagram copy

## Cloudflare roles

Artifacts stores Git, Workers coordinates agents.

Two agents send Git requests to our Worker API. The API authorizes access to each agent's fork, coordinates tasks and records check reports. Cloudflare Artifacts stores the Git repositories.

## Coordination layer

A coordination layer on top of Git.

Git holds each agent's separate change. Agent Branches brings both current commits into one combined check and records a shared pair status. The authenticated client runs the check, and the coordinator records whether the pair is clean, conflicting or unknown.

Git already manages changes. The layer above it helps agents coordinate them. The same idea can use Artifacts forks or Git worktrees.

## Architecture

Git in the cloud, tests on your computer.

The authenticated client runs on a user-owned computer. It exchanges Git data and check reports through the Cloudflare Worker, which accesses Artifacts repositories and records state in a SQLite Durable Object.

Cloudflare hosts Git storage and coordination. Your authenticated client handles code checks on a user-owned computer. The coordinator records reports and never executes agent code.

- Runs merge and tests
- Git and check reports
- Canonical repo and forks

## Concurrent work

Separate forks, one combined check.

Agent A and Agent B push to separate forks at the same time. The authenticated client fetches both exact head commits to check their changes together. Separate forks alone don't prove that the combined changes are safe.

Each agent pushes to its own fork. The authenticated client checks both exact head commits together. In the smoke demo, it runs a Git merge-tree check and submits typed reports. Application test failures appear in the UI fixtures.

- Pushes its change
- Checks A + B together

## Safety states

Four reasons a pair isn't safe.

Compare a Git conflict with failing combined tests despite passing individual tests. A missing push leaves the current head unknown, while checks on older heads don't prove the current changes safe. These conceptual examples explain the fixture screens.

A clean merge alone can't establish safety. Tests can fail when changes are combined, a push can be missing, or checks can refer to older heads. These examples explain the local fixture screens.

## Gallery instructions

Use the arrow keys to change diagrams. These pictures explain the protocol, while the terminal report provides run evidence. On a narrow screen, scroll across the picture to read every label.

Open the diagram gallery in another browser tab. It works directly from the file. To serve it over HTTP, run this from the prototype directory in another terminal.

Use the arrow keys or buttons to switch pictures. These pictures explain the protocol, while the terminal report provides evidence from the current run.

Show the architecture picture while explaining where Git storage, coordination and the authenticated client run, then return to the README.

In the concurrent-work picture, highlight both separate forks feeding the authenticated client, then return to the terminal.

Show the safety-state picture and highlight the relevant card before opening each fixture screen.
