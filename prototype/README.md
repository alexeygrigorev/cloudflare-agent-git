# Agent Branches — L1 scaffold prototype

Shared base for the "Agent Branches" competition entry: several coding agents
change code concurrently; each agent works in its own fork of a canonical
repo on Cloudflare Artifacts; a Durable Object coordinator tracks per-agent
WIP heads and raises radar warnings when heads diverge.

Runs **locally today, with no Cloudflare account**, by swapping the real
Artifacts binding for an in-memory fake. TypeScript, Wrangler 4, Vitest 4
(`@cloudflare/vitest-plugin`, tests execute inside workerd).

## Run

```bash
cd prototype
npm install          # ~325 MiB node_modules, single workerd stack
npm run typecheck    # tsc --noEmit
npm test             # 18 tests (unit + integration through the Worker)
npx wrangler dev --local
```

Then, against http://localhost:8787:

```bash
# optional: canonical repo is also auto-created on first /tasks call
curl -s -X POST localhost:8787/setup

# one task = one agent fork of the canonical repo
curl -s -X POST localhost:8787/tasks -H 'content-type: application/json' \
  -d '{"agent":"claude"}'
# => { taskId, agentId, fork:{name,remote}, token:{scope,expiresAt,plaintext}, head }

# agent pushed a WIP head
curl -s -X POST localhost:8787/events/push -H 'content-type: application/json' \
  -d '{"agent":"claude-0001","sha":"<40-hex>"}'

curl -s localhost:8787/status
curl -s localhost:8787/tasks/task-0001
```

## Routes

| Route | Meaning |
| --- | --- |
| `POST /setup` | create canonical repo (local fake seeds a root commit) |
| `POST /tasks` | fork canonical for one agent; returns agent id, fork remote, scoped write token |
| `POST /events/push` | `{agent, fork?, ref?, sha}` — agent pushed a WIP head; dedups per (agent, sha) |
| `POST /events/artifacts` | accepts the documented `cf.artifacts.repo.pushed` envelope |
| `GET /status` | canonical, agents, head vector, latest warnings + radar log |
| `GET /tasks/:id` | task detail incl. agent head |

## Architecture

```
                 ┌────────────────────────── Worker (src/index.ts) ─────────────────────┐
  agent/harness  │  POST /tasks   POST /events/push   POST /events/artifacts   GET ...  │
      ─────────► │        │               │                     │                     │
                 │        └───────────────┴──────────┬──────────┴─────────────────────│
                 │                          Durable Object RPC                       │
                 │                                      ▼                             │
                 │              ┌──── Coordinator DO (src/coordinator.ts) ────┐       │
                 │              │  agents · head vector · seen pushes         │       │
                 │              │  warnings (active/invalidated) · radar log  │       │
                 │              │  Radar hook (src/radar.ts, pluggable)       │       │
                 │              └───────────────┬─────────────────────────────┘       │
                 └──────────────────────────────┼─────────────────────────────────────┘
                                                ▼
                                   ArtifactsPort (src/types.ts)
                                   ├─ RealArtifacts   ← env.ARTIFACTS binding (real CF)
                                   └─ LocalArtifacts  ← in-memory fake (local dev/tests)
```

- **Coordinator DO** (single `"global"` instance): creates task forks, records
  pushes, maintains the head vector `{agentId → sha}`, dedups pushes per
  `(agent, sha)`, invalidates a warning whenever a sibling of the warned pair
  advances its head, then runs the Radar pass which may open fresh warnings.
- **Radar** (`src/radar.ts`): interface + `StubRadar` that records
  "would check pair (a,b) at heads (x,y)" and warns on `heads-diverged`.
  Swap via `RADAR_IMPL=silent` var (constructor picks the implementation).
  The real merge/test engine is a separate lane and plugs in here.
- State persists in DO storage (`model` key); fork/token plumbing goes through
  `ArtifactsPort`, so the DO is storage-authoritative for coordination state.

## What is mocked vs real

| Piece | Local (today) | Real (account) |
| --- | --- | --- |
| Repo store | `LocalArtifacts` in-memory fake (per-DO isolate; resets on restart) | Cloudflare Artifacts repos |
| Git remotes | `https://local.artifacts-stub.test/git/...` (fake URL) | `https://<ACCOUNT_ID>.artifacts.cloudflare.net/git/<ns>/<repo>.git` |
| Tokens | fake, same documented format `art_v1_<40hex>?expires=<unix>` | binding `createToken(scope, ttl)` |
| Push events | `POST /events/push` body `{agent, fork, ref, sha}` | real agents `git push` (receive-pack v1) + `cf.artifacts.repo.pushed` event → same handler |
| Commit verification | fake trusts any sha (`trustExternalHeads: true`) | `port.hasCommit` → binding `readCommit(sha)` |

`LocalArtifacts` is an in-memory fake, not a Node sidecar with bare git dirs:
chosen for zero moving parts in tests and `wrangler dev`. The interface keeps
the door open for a sidecar-backed implementation later; `applyPush()` exists
so a harness can also drive it like a real repo.

`RealArtifacts` (`src/artifacts/real.ts`) is a thin wrapper over the
documented binding surface (`create/get/fork/log/readToken...`, disposable
handles via `using`). It is compiled and typechecked but unused locally
because `wrangler.jsonc` declares no `artifacts` binding.

API shapes come only from the five official pages cited in
`docs-notes.md` (raw copies under `docs/`); anything beyond them is marked
ASSUMED there (`ASSUMED-A`…`ASSUMED-E`).

## Switch to real Artifacts (once an account exists)

1. `wrangler login` (or set `CLOUDFLARE_API_TOKEN`), create the namespace.
2. Add to `wrangler.jsonc` (documented shape):
   ```jsonc
   "artifacts": [{ "binding": "ARTIFACTS", "namespace": "agent-branches" }]
   ```
3. `npx wrangler types` — regenerate `worker-configuration.d.ts`; confirm the
   generated `Artifacts` type matches `ArtifactsNamespaceBinding` in
   `src/artifacts/real.ts` (resolves ASSUMED-B/D; ref enumeration remains
   deliberately absent per ASSUMED-A — use push events).
4. Seed the canonical repo: `POST /setup` creates it via the binding, then
   `git clone` its remote and push a real baseline commit
   (`git -c http.extraHeader="Authorization: Bearer $TOKEN" push`).
5. Point an Artifacts event subscription (`artifacts.repo` source) at the
   deployed `POST /events/artifacts` route so real pushes flow in
   (resolves ASSUMED-E).
6. `npx wrangler deploy` (not authorized yet — competition rules).
```
