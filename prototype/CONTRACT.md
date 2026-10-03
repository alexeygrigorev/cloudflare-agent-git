# Agent Branches prototype — HTTP + integration contract

version: 0.1
(Pin this version when building against it: L2 review UI, L3 radar runner,
L4/L5 demo lanes. Any breaking change bumps the version.)

## Deployment boundary (codex C-1309)

The Worker and its Coordinator Durable Object **never run git and never run
tests**. They only coordinate state:

- **Local mode**: all repos are REAL bare git repos on disk, served by the
  Node sidecar (`prototype/local-artifacts/`). The Worker calls the sidecar
  over `fetch` (`LOCAL_ARTIFACTS_URL`). Agents use ordinary
  `git clone` / `git push` against the sidecar's smart-HTTP endpoints with
  per-repo tokens. The sidecar's post-receive hook notifies the Worker.
- **Real mode** (once a Cloudflare account exists): the same port is
  implemented over the documented Cloudflare Artifacts binding.
- The radar (trial merges / tests) runs in a **separate trusted local runner
  process** (L3), which submits results via `POST /checks`.

Sidecar (local mode, Node built-ins + system git only, binds 127.0.0.1):

```
npm run sidecar          # env: SIDECAR_ROOT, SIDECAR_HOST, SIDECAR_PORT,
                         #      SIDECAR_TOKEN (shared bearer for /api/*),
                         #      SIDECAR_NOTIFY_URL (default none)
```

Worker env (`.dev.vars` for wrangler dev, miniflare bindings in tests):

| Variable | Used by | Meaning |
| --- | --- | --- |
| `ADMIN_TOKEN` | POST /setup, POST /tasks | admin bearer; unset => 503 fail closed |
| `RUNNER_TOKEN` | POST /checks | trusted radar runner bearer |
| `LOCAL_ARTIFACTS_URL` | Coordinator | sidecar base URL (local mode) |
| `LOCAL_ARTIFACTS_TOKEN` | Coordinator | sidecar shared bearer (optional) |
| `ARTIFACTS` | Coordinator | real Cloudflare Artifacts binding (real mode) |
| `RADAR_IMPL` | Coordinator | `stub` (default) or `silent` |

Tokens are never logged or echoed in error bodies. `wrangler dev` binds
localhost only; deploying publicly requires an auth review first (token
rotation, TLS, authenticating `/events/*`).

## Routes

All bodies are JSON. Errors: `{ "error": string }` (+ extra fields where
noted). Statuses: 400 bad input, 401 bad/missing bearer, 404 unknown
task/warning, 409 stale vector, 503 auth secret unconfigured.

### POST /setup — admin

Creates the canonical repo (one per Coordinator). Idempotent once created.

```json
// response 201
{ "canonical": { "name": "agent-branches-canonical-<8hex>", "remote": "http://127.0.0.1:8790/git/agent-branches-canonical-<8hex>.git" },
  "created": true, "seedCommit": "<40-hex>" }
```

### POST /tasks — admin (codex C-1306)

```json
// request
{ "agent": "claude",          // required-ish; slugified into agentId-<seq>
  "intent": "fix login loop", // optional free text, shown on the review screen
  "base_sha": "<40-hex>",     // optional canonical commit to fork from
  "ttlSeconds": 3600 }        // optional fork token TTL
// response 201
{ "taskId": "task-0007",
  "agentId": "claude-0007",
  "fork": { "name": "agent-branches-canonical-<8hex>-claude-0007",
            "remote": "http://127.0.0.1:8790/git/<fork>.git" },
  "ref": "refs/heads/main",
  "base_sha": "<40-hex canonical commit the fork started from>",
  "intent": "fix login loop" | null,
  "token": { "scope": "write", "expiresAt": "ISO", "plaintext": "art_v1_<40hex>?expires=<unix>" },
  "head": "<40-hex fork head == base_sha at creation>" }
```

`base_sha` defaults to the canonical head; an explicit base must exist in
the canonical first-parent history (400 otherwise). In local mode the fork
starts exactly at `base_sha`. In real mode the binding can only fork the
default branch (docs-notes ASSUMED-F, muse-r46 D3): an explicit `base_sha`
that equals the canonical tip is honored exactly; an older one records the
fork's head at creation as `base_sha` instead. Agents then `git push`
to `fork.remote` with `git -c http.extraHeader="Authorization: Bearer
$plaintext"`; the sidecar hook reports the push automatically.

### POST /events/push — open (agent harness or sidecar webhook)

```json
// request: agent or fork identifies the pusher
{ "agent": "claude-0007", "sha": "<40-hex>" }
// or (sidecar post-receive webhook shape)
{ "fork": "<forkName>", "ref": "refs/heads/main", "sha": "<40-hex>", "before": "<40-hex>" }
// response 200
{ "accepted": true, "deduped": false, "agent": "claude-0007",
  "heads": { "claude-0007": "<sha>", ... },
  "invalidatedWarnings": ["warn-3"],   // warnings involving this agent
  "newWarnings": [],                   // only ever conflict-driven (see radar)
  "radarChecks": 3 }                   // pairs recorded as not_checked
```

`sha` must be a real commit in the agent's fork (400 otherwise). Repeated
(agent, sha) pushes are deduped (`"deduped": true`).

### POST /events/artifacts — open (Artifacts event subscription)

Accepts the documented `cf.artifacts.repo.pushed` envelope (see
docs-notes.md source 3); resolves the fork to an agent and behaves like
/events/push. Unknown forks => 202 `{accepted:false}`.

### POST /checks — RUNNER_TOKEN (trusted radar runner, L3)

```json
// request
{ "vector": { "claude-0007": "<sha>", "codex-0008": "<sha>", ... }, // ALL agents, exact current heads
  "policy": "merge-tree-v1",
  "coverage": ["claude-0007|codex-0008"],          // optional, recorded
  "results": [
    { "pair": ["claude-0007", "codex-0008"],
      "status": "conflict",                        // conflict|clean|unknown
      "kind": "merge-conflict",                    // optional classifier
      "evidence": "git merge-tree exit 1" } ] }
// response 200
{ "stale": false, "accepted": 2, "currentHeads": { ... },
  "pairs": [ /* PairStatusView[] as in /status */ ],
  "createdWarnings": [ /* WarningRecord[] */ ],
  "runnerReport": { "policy": "merge-tree-v1", "coverage": [...], "accepted": 2, "at": "ISO", "vector": { ... } } }
// response 409 (vector != current head vector — refetch /status and retry)
{ "error": "stale vector: heads have moved since the runner fetched them; re-fetch /status and retry",
  "currentHeads": { ... } }
```

### GET /status — open

```json
{ "canonical": { "name": "...", "remote": "..." },
  "agents": [ { "agentId": "claude-0007", "taskId": "task-0007", "forkName": "...",
                "forkRemote": "...", "ref": "refs/heads/main", "head": "<sha>|null",
                "pushes": 3, "createdAt": "ISO", "lastPushAt": "ISO|null" } ],
  "heads": { "claude-0007": "<sha>" },
  "pairs": [ { "pair": ["a","b"], "heads": { "a": "<sha>", "b": "<sha>" },
               "status": "conflict|clean|unknown|not_checked",
               "kind": "merge-conflict"?, "evidence": "..."?,
               "checkedAt": "ISO|null",       // last check time, even if stale
               "stale": false,                // stored check exists but heads moved
               "activeWarningIds": ["warn-3"] } ],
  "warnings": [ /* WarningRecord, newest first, capped 20 */ ],
  "radarLog": [ { "at": "ISO", "pair": ["a","b"], "heads": {...}, "status": "not_checked" } ],
  "lastRunnerReport": { ... } | null }
```

`not_checked` (never checked at these heads — includes stale) is always
visibly distinct from `clean`.

### GET /tasks/:id — open

```json
{ "taskId": "task-0007", "agentId": "claude-0007",
  "forkName": "...", "forkRemote": "...", "ref": "refs/heads/main",
  "createdAt": "ISO",
  "base_sha": "<40-hex>", "intent": "fix login loop" | null,
  "head": "<current sha>|null", "pushes": 3,
  "agent": { /* AgentRecord */ } | null,
  "warnings": [ { "id": "warn-3", "pair": ["a","b"],
                  "headsAtIssue": { "a": "<sha>", "b": "<sha>" },
                  "reason": "merge-conflict", "kind": "merge-conflict"?,
                  "evidence": "..."?, "status": "active"|"invalidated",
                  "createdAt": "ISO", "invalidatedAt": "ISO|null",
                  "resolvedBy": "clean check (policy)"?,
                  "acks": [ { "agent": "claude-0007", "head": "<sha at ack>",
                              "note": "rebase in progress"?, "at": "ISO" } ] } ],
  "testProvenance": { "command": "npm test", "exit": 0,
                      "head_sha": "<40-hex>", "at": "ISO" } | null }
```

### POST /tasks/:id/tests — open (agent harness posts proof)

```json
{ "command": "npm test", "exit": 0, "head_sha": "<40-hex in the fork>" }
// 201 { "testProvenance": { "command": "npm test", "exit": 0, "head_sha": "...", "at": "ISO" } }
```

`head_sha` must exist in the fork (400 otherwise). Last post wins.

### POST /warnings/:id/ack — open (attestational)

```json
{ "agent": "claude-0007", "note": "rebase in progress" }
// 200 { "warning": { /* WarningRecord with acks */ } }
```

Records which agent acknowledged which warning at which head (404 unknown
warning, 400 unknown agent).

## Radar hook contract (src/radar.ts)

```ts
type RadarStatus = "conflict" | "clean" | "unknown" | "not_checked";
interface RadarPairResult {
  pair: [string, string];
  heads: { a: string; b: string };
  status: RadarStatus;   // see semantics below
  kind?: string;         // conflict classifier, e.g. "merge-conflict"
  evidence?: string;     // how it was determined
}
interface Radar {
  onPush(change: HeadChange, heads: HeadVector, siblings: string[]): RadarPairResult[];
}
```

Semantics (codex C-1305 #1):

- **conflict** — checked at exactly these heads, real conflict found. The
  ONLY status that creates a warning.
- **clean** — checked at exactly these heads, no conflict. A clean result
  at the same heads auto-resolves that pair's active warning.
- **unknown** — checked but inconclusive. Recorded distinctly; never a
  warning, never clean.
- **not_checked** — no check covers the current heads. This is what the
  in-Worker `StubRadar` always reports (differing heads alone are NEVER an
  active warning) and what a pair reverts to after either head advances
  (`stale: true` flags the outdated stored check).
- Pushing invalidates active warnings whose pair includes the pushing
  agent; only a fresh runner `conflict` at the new heads opens a new one.

## ArtifactsPort (src/types.ts) — documented vs ASSUMED

| Port method | Real mode (binding) | Status |
| --- | --- | --- |
| `createRepo` | `create(name, opts)` | documented |
| `fork(source, target, opts)` | `repo.fork(name, opts)` | documented — **except** `opts.baseSha`: no documented API forks at a commit (ASSUMED-A/F). Since muse-r46 D3 real mode forks the default branch and records the **realized** base (fork head at creation) as the task's `base_sha`; local mode realizes it exactly with a real `git update-ref` after `git clone --bare` |
| `mintToken` | `repo.createToken(scope, ttl)` | documented (scope field: ASSUMED-C) |
| `log` | `repo.log(opts)` | documented |
| `headCommit` | `repo.log({ref, limit:1})` | derived from a documented op; the port deliberately offers NO ref enumeration (ASSUMED-A) |
| `hasCommit` | `repo.readCommit(sha)` | documented |
| `listRepos` / `deleteRepo` | `list` / `delete` | documented |

No merge or ref-enumeration APIs exist on the port (codex C-1309 #8): the
Worker cannot and does not perform trial merges. Full assumptions:
`docs-notes.md` ASSUMED-A…E.

## Sidecar API (local mode, 127.0.0.1)

Admin JSON API (bearer `SIDECAR_TOKEN` when configured):
`GET /api/health`, `POST /api/repos {name, defaultBranch?}`,
`GET /api/repos`, `POST /api/repos/:name/fork {target, baseSha?}`,
`POST /api/repos/:name/tokens {scope, ttlSeconds?}`,
`GET /api/repos/:name/head?ref=`, `GET /api/repos/:name/log?ref&limit&offset`,
`GET /api/repos/:name/hascommit?sha=`, `POST /api/repos/:name/commits
{message, ref?}` (test/dev helper), `DELETE /api/repos/:name`.

Git smart HTTP (per-repo token auth; `read` scope cannot push):
`GET /git/:name.git/info/refs?service=...`,
`POST /git/:name.git/git-upload-pack`,
`POST /git/:name.git/git-receive-pack`.

Push webhook: post-receive -> sidecar `/hooks/push` -> forwarded to
`SIDECAR_NOTIFY_URL` (point it at the Worker's `/events/push`) as
`{fork, ref, sha, before}`.
