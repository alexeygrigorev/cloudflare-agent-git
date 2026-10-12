# Agent Branches prototype

Shared base for the "Agent Branches" competition entry: several coding agents change code concurrently; each agent works in its own fork of a canonical repo; a lightweight coordinator tracks per-agent WIP heads and surfaces radar conflict warnings fed by a trusted local runner.

The coordinator never runs Git commands or tests. The Cloudflare adapter uses a Worker, a SQLite-backed Durable Object, and the Artifacts Git binding. Deployment verification is pending. A private Git gateway exposes task-scoped credentials; upstream Artifacts credentials stay private. The Node coordinator and Git sidecar support local reproduction.

A trusted runner executes trial merges and tests on a developer computer and submits authenticated results for the current head vector. The approved video records the earlier Node runtime; it doesn't prove the Cloudflare deployment.

Exact routes, request/response shapes, the radar hook contract, auth and the sidecar API are specified in **[CONTRACT.md](CONTRACT.md) (version 0.1.4)** — L2/trusted runner/L4 build against that file, not against this README.

## Run

Explicit prerequisites:
- System `node` >= 22 (tested on Node 24) must be on `PATH` (required for sidecar post-receive hook execution).
- `git`, `npm`, and `python3` installed.
- Repository dependencies installed via `npm install` in `prototype/`.

### Quickstart: Build and Test Suites

```bash
cd prototype
npm install
npm run typecheck      # tsc --noEmit
npm test               # worker tests inside workerd: exit 0
npm run test:sidecar   # local Git server: 16 passed
npm run test:node      # core + router + local adapters: 64 passed
npm run build:node     # outputs .build/node/src/local/main.js
```

### Executable Protocol Walkthrough

The self-contained executable script [`demo/walkthrough.py`](demo/walkthrough.py) implements the multi-agent coordination protocol. It now starts its own bounded coordinator and sidecar servers automatically on dynamic loopback ports with temporary state; no manual server startup is needed. For remote smoke tests, setting `BASE_URL` delegates to a deployed coordinator . The `--mock` flag runs explicit source-only client tests, not real Cloud Artifacts or native agents.

```bash
npm run build:node
python3 demo/walkthrough.py
```

## Auth

ALL mutating and sensitive read routes are authenticated (CONTRACT 0.1.1):

- `POST /setup` and `POST /tasks` require `Authorization: Bearer $ADMIN_TOKEN`.
- `POST /checks` (trusted radar runner results) requires `Authorization: Bearer $RUNNER_TOKEN`.
- `POST /events/push`, `/events/artifacts`, `/tasks/:id/tests` and `/warnings/:id/ack` accept `ADMIN_TOKEN`, the relevant agent's per-task token, or the sidecar shared bearer. Cross-agent writes return `403`.
- `GET /status` requires an authorized token (anonymous `401`).
- `GET /tasks/:id` is owner-or-admin (`401`/`403` for others).

Per-agent workspaces must keep tokens in 0600 git-ignored files or environment variables (`GIT_CONFIG_*`), never in process `argv`, URLs, or published logs. The sidecar post-receive hook executes with system `node` on `PATH` to deliver push notifications.

## Routes

| Route | Auth | Meaning |
| --- | --- | --- |
| `POST /setup` | admin | create canonical repo (idempotent) |
| `POST /tasks` | admin | `{agent, intent?, base_sha?, ttlSeconds?}` — fork canonical, mint write token |
| `POST /events/push` | agent token \| admin \| sidecar | `{agent\|fork, ref?, sha}` — WIP head |
| `POST /events/artifacts` | sidecar \| admin | documented `cf.artifacts.repo.pushed` envelope |
| `POST /checks` | runner | `{contract:"0.1", vector, policy, coverage?, results:[...]}` |
| `GET /status` | admin \| runner \| agent token | canonical, agents, head vector, per-pair radar status, warnings |
| `GET /tasks/:id` | task's agent \| admin | base_sha, intent, head, pushes, warnings + acks, testProvenance |
| `POST /tasks/:id/tests` | task's agent \| admin | `{command, exit, head_sha}` — attach test provenance |
| `POST /warnings/:id/ack` | acking agent \| admin | `{agent, note?}` — record acknowledgements |

## Architecture

Provider-neutral facade since CONTRACT 0.1.4 (details in [ARCHITECTURE.md](./ARCHITECTURE.md)): the coordination logic lives in `src/core/`. A zero-dependency `node:http` runtime (`src/local/main.ts`) serves routes. The Cloudflare adapter lives in `src/cloudflare/`; deployment verification is pending.

## What is real vs deferred

| Piece | Local Fallback | Target Cloudflare Deploy |
| --- | --- | --- |
| Repo store | REAL bare git repos on disk via sidecar | Cloudflare Artifacts repos |
| Git remotes | Local sidecar retained | Gateway remote Worker `BASE_URL` with local tokens (upstream URLs NEVER exposed) |
| Trial merges/tests | Trusted local runner | Trusted remote runner |

The Cloudflare design limits operation attempts to 200 per UTC day and 6,000 per calendar month, reserves at most four repositories, and caps cumulative uploads at 16 MiB with a 256 KiB request body limit. Deployment and real operation measurements remain pending; see [costs and limits](../docs-submission/COST.md).

Evidence breakdown:
- Real-service evidence: `artifacts-spike/RESULTS.md` + `appendix-transcript.md` on `origin/proto/artifacts-spike` (29 ops against real service, 2026-10-03).
- **Stale In-Progress 11 Oct Status Update (Concise Historical Qualified)**: Scripted local source lanes are distinguished from historical 3 real model agent runs (113 sec). We make no fresh current main claim. Archival public evidence links for code contracts, API, and auth functional explanations remain truthful and useful.
