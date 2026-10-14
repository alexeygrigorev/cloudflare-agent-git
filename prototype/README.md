# Agent Branches prototype

Shared base for the "Agent Branches" competition entry: several coding agents change code concurrently; each agent works in its own fork of a canonical repo; a lightweight coordinator tracks per-agent WIP heads and surfaces radar conflict warnings fed by a authenticated client.

The coordinator never runs Git commands or tests. The Cloudflare adapter uses a Worker, a SQLite-backed Durable Object, and the Artifacts Git binding. The historical live deployment passed its smoke run on 13 October; newer run-owned cleanup and planned-path APIs require the updated backend. A private Git gateway exposes task-scoped credentials; upstream Artifacts credentials stay private. The Node coordinator and Git sidecar support local reproduction.

An authenticated client executes trial merges and tests on a developer computer and submits authenticated results for the current head vector. The approved video records the earlier Node runtime; it doesn't prove the Cloudflare deployment.

Exact routes, request/response shapes, the radar hook contract, auth and the sidecar API are specified in [CONTRACT.md](CONTRACT.md) (version 0.1.5). Clients build against that file.

## Run

Explicit prerequisites:
- System `node` >= 22 (tested on Node 24) must be on `PATH` (required for sidecar post-receive hook execution).
- `git`, `npm`, `uv`, and Python >= 3.10 installed.
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

The self-contained executable script [`demo/walkthrough.py`](demo/walkthrough.py) implements the multi-agent coordination protocol. It starts its own bounded coordinator and sidecar servers automatically on dynamic loopback ports with temporary state; no manual server startup is needed. When `BASE_URL` is set, `walkthrough.py` delegates to [`demo/cloud-smoke.py`](demo/cloud-smoke.py).

```bash
npm run build:node
uv run python demo/walkthrough.py
```

### Cloud Smoke and Mock Verification

Deploy-config and smoke verification are handled by [`demo/cloud-smoke.py`](demo/cloud-smoke.py). Setting `BASE_URL` (strict HTTPS required) runs live verification against a deployed coordinator. The `--mock` flag on `cloud-smoke.py` (`uv run python demo/cloud-smoke.py --mock`) runs explicit source-only client tests against an in-memory loopback mock backend, not real Cloud Artifacts or native agents.

## Interactive demo and reusable CLI

From this directory:

```bash
npm install
npm run build:node
uv sync
uv run python demo/pair-example.py --backend local --interactive
```

For Cloudflare, use `--backend cloudflare` with private `BASE_URL`, `ADMIN_TOKEN` and `RUNNER_TOKEN` settings in `.env`. Both backends follow the same visible task/edit/push/status flow. Space executes a displayed block; another Space after output reveals the next one. `--plans` adds declared-file overlap warnings before edits. Cloudflare mode refuses an older backend without run-owned cleanup before any write.

The local dependency exposes `uv run branches`. Configure server/repository and private token files once with `branches configure`; create a task with `branches task create --agent agent-a --intent "Configure checkout" --files rate.py`. Explicit arguments override environment and private project settings.

Run `uv run branches watch --test-command 'python -m unittest discover -v'` on a user-owned computer. It checks independently pushed heads and records exact-commit results. Use `branches publish --task-id ...` from an agent checkout to push to its verified own fork, and `branches status` to see current evidence. The older `branches push` command only sends a notification; it does not perform a Git push. See the [complete example](../_docs/demo-recording-script.md).

The watcher needs each fork's scoped credentials in private configuration; the runner token only authorizes check submission. Checks run asynchronously: missing, stale or failed-to-run evidence remains unknown. `branches plan --task-id ... --files shared.txt` declares intended paths without a commit; overlaps are coordination warnings, not proof of a conflict.

Combined-test commands use unittest or pytest with structured reports. Arbitrary printed success messages, zero-test and entirely skipped runs cannot establish clean status. The client bounds command duration, output and expanded archive sizes.

## Auth

ALL mutating and sensitive read routes are authenticated (CONTRACT 0.1.1):

- `POST /setup` and `POST /tasks` require `Authorization: Bearer $ADMIN_TOKEN`.
- `POST /checks` (authenticated client check results) requires `Authorization: Bearer $RUNNER_TOKEN`.
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

Provider-neutral facade since CONTRACT 0.1.4 (details in [ARCHITECTURE.md](./ARCHITECTURE.md)): the coordination logic lives in `src/core/`. A zero-dependency `node:http` runtime (`src/local/main.ts`) serves routes. The Cloudflare adapter lives in `src/cloudflare/`; the historical deployment is documented in the submission evidence; new API changes need a new deployment.

## What is real vs deferred

| Piece | Local Fallback | Target Cloudflare Deploy |
| --- | --- | --- |
| Repo store | REAL bare git repos on disk via sidecar | Cloudflare Artifacts repos |
| Git remotes | Local sidecar retained | Gateway remote Worker `BASE_URL` with local tokens (upstream URLs NEVER exposed) |
| Trial merges/tests | Authenticated local client | Authenticated client on a user-owned computer |

The Cloudflare design limits operation attempts to 200 per UTC day and 6,000 per calendar month, reserves at most four repositories, and caps cumulative uploads at 16 MiB with a 256 KiB request body limit. Historical live operation measurements and the shared-account spending limitations are documented; see [costs and limits](../docs-submission/COST.md).

Evidence breakdown:
- Real-service evidence: `artifacts-spike/RESULTS.md` + `appendix-transcript.md` on `origin/proto/artifacts-spike` (29 ops against real service, 2026-10-03).
- **Stale In-Progress 11 Oct Status Update (Concise Historical Qualified)**: Scripted local source lanes are distinguished from historical 3 real model agent runs (113 sec). We make no fresh current main claim. Archival public evidence links for code contracts, API, and auth functional explanations remain truthful and useful.
