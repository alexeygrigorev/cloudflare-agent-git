# WORKLOG — claude-exec-l1 (L1 scaffold)

Executor: claude-exec-l1, aplexer id d87c9657-3f68-4503-a096-9fd5f73dbab8,
model zai-coding-plan/glm-5.3 (per task assignment), parent claude-principal.

## 2026-10-03

### First tool

`a whoami --json` (recorded below, trimmed to identity fields):

```json
{
  "id": "d87c9657-3f68-4503-a096-9fd5f73dbab8",
  "workspace": "/home/alexey/git/cloudflare-agent-git",
  "tag": "claude-exec-l1",
  "engine": "shell",
  "parent_session": "b3a92dd0-a17e-4a62-940f-eb3b829393f6",
  "phase": "running"
}
```

Declared edit scope on the worktree workspace
(`a work join /home/alexey/git/agent-branches-l1 --paths prototype/**`).

### Commands and milestones

1. `git worktree add ../agent-branches-l1 -b proto/l1-scaffold`
   (from main @ 230f8a1, worktree at /home/alexey/git/agent-branches-l1).
2. Fetched the five official docs pages with curl into `prototype/docs/*.md`,
   extracted text to `docs/*.txt`, distilled `docs-notes.md` (cited URLs,
   documented API shapes, ASSUMED-A…E).
3. `npm install` iterations:
   - First install (wrangler 4.147 + @cloudflare/vitest-pool-workers) grew
     node_modules to **525 MiB** (three workerd copies: two binary stacks).
   - Aligned versions: wrangler 4.124.0 matched vitest-pool-workers 0.22 →
     321 MiB single stack, but that pool is the legacy API.
   - Final choice: **wrangler 4.147.0 + @cloudflare/vitest-plugin 1.3.6 +
     vitest ^4.1** (current documented testing API, same miniflare/workerd
     versions as wrangler → dedupe holds): **325 MiB ≤ 400 MiB budget**.
     No global installs; no `wrangler login`; no deploy.
4. `npx wrangler types` → generated `worker-configuration.d.ts`
   (global Env with `COORDINATOR: DurableObjectNamespace<Coordinator>`,
   `cloudflare:workers` module types incl. the `DurableObject` base class).
5. Build: `src/types.ts` (ArtifactsPort + documented push event envelope),
   `src/artifacts/local.ts` (in-memory fake; documented remote/token formats;
   `trustExternalHeads` flag), `src/artifacts/real.ts` (thin binding wrapper,
   `using` disposable handles), `src/radar.ts` (pluggable Radar + StubRadar +
   SilentRadar), `src/coordinator.ts` (Coordinator DO), `src/index.ts`
   (routes), `vitest.config.ts`, `test/local.test.ts`,
   `test/coordinator.test.ts`.

### Test results

- `npx tsc --noEmit`: clean.
- `npx vitest run`: **2 files, 18 tests, 18 passed**
  (unit: LocalArtifacts create/fork/log/refs/tokens + event parsing;
  integration through SELF: setup, 2 tasks, push → head vector + warning,
  dedup, sibling-advance invalidation + re-warn, task detail/404,
  `cf.artifacts.repo.pushed` envelope, error cases).
- `npx wrangler dev --local --port 8791`: boots ("Ready on http://…");
  curl-verified /status, POST /tasks (auto-setup), POST /events/push
  (accepted + warning), duplicate push (deduped), /status warnings.
  Process stopped afterwards.

### Open ASSUMED items (details in docs-notes.md)

- ASSUMED-A `listRefs` not in documented binding surface — refused in
  RealArtifacts, served by the fake.
- ASSUMED-B `ArtifactsCommitMetadata` field shape inferred from push event.
- ASSUMED-C `createToken().scope` field presence.
- ASSUMED-D Artifacts binding visible in DO env (not binding-page-explicit).
- ASSUMED-E event-subscription wiring not covered by fetched pages; envelope
  route implemented, subscription creation is a switch-to-real step.

### Notes / deviations

- Used `@cloudflare/vitest-plugin` (current docs) instead of the older
  `@cloudflare/vitest-pool-workers` (task said "if feasible, else plain
  vitest" — the plugin runs tests inside workerd, closest to production).
- LocalArtifacts is the in-memory-fake option (allowed by task); documented
  in README together with the sidecar alternative.

## 2026-10-03 (claude-exec-l1b follow-up)

Executor: claude-exec-l1b, aplexer id c3cd0e48-8338-4315-a1ef-f58b04b3d51c,
model zai-coding-plan/glm-5.3, parent claude-principal (b3a92dd0).

`a whoami --json` (trimmed to identity fields):

```json
{
  "id": "c3cd0e48-8338-4315-a1ef-f58b04b3d51c",
  "workspace": "/home/alexey/git/cloudflare-agent-git",
  "tag": "claude-exec-l1b",
  "engine": "shell",
  "parent_session": "b3a92dd0-a17e-4a62-940f-eb3b829393f6",
  "phase": "running"
}
```

Declared edit scope: `a work join /home/alexey/git/agent-branches-l1 --paths prototype/**`.

Previous executor state: working tree clean at 4837a78 (all prior work already
committed); "snapshot previous executor output" commit is a no-op.

Applying codex-principal review C-1305 (fixes 1-5), C-1306 (contract
additions), C-1309 (deployment boundary), each as a separate commit with
tests. Results appended below.

### Fix commits (codex C-1305 #1-5, C-1306, C-1309 #7-9), all with tests

1. `3e30d3f` radar result status contract (C-1305 #1):
   `{status: conflict|clean|unknown|not_checked, kind?, evidence?}`;
   StubRadar always `not_checked`; warnings only for runner-submitted
   conflict; /status per-pair views with stale/checkedAt; clean at same
   heads resolves a warning; POST /checks route added (auth came next).
2. `0201bb1` ArtifactsPort: `listRefs` -> `headCommit` (derived from
   documented `log({ref,limit:1})`); no invented merge/ref-enumeration APIs
   (C-1305 #2 + C-1309 #8); docs-notes ASSUMED-A rewritten.
3. `af054a6` auth (C-1305 #3): ADMIN_TOKEN on POST /setup + /tasks (incl.
   token minting), RUNNER_TOKEN on /checks; fail closed (503) when
   unconfigured; constant-time compare; tokens never logged/echoed;
   README documents wrangler-dev localhost-only + deploy auth review.
4. `bc797b7` L2/L4 contract additions (C-1306): base_sha (+ validation
   against canonical history) and intent on tasks; POST
   /warnings/:id/ack {agent, note?} records ack-at-head; POST
   /tasks/:id/tests {command, exit, head_sha} (verified against fork
   commits) -> testProvenance; GET /tasks/:id enriched.
5. `9925cc0` deployment boundary (C-1309 #7,#8,#9): local-artifacts Node
   sidecar (built-ins + system git ONLY, no new npm deps — node_modules
   still 325 MiB): real bare repos (init --bare + plumbing seed), fork =
   clone --bare (+ update-ref to baseSha), per-repo tokens, smart HTTP via
   `git http-backend` (read tokens cannot push), post-receive hook ->
   worker POST /events/push {fork, ref, sha}; SidecarArtifacts port client
   (Worker fetches sidecar in local mode; in-memory fake deleted; fail
   closed without backend); /checks now vector-gated (vector != current
   heads -> 409 + currentHeads) with lastRunnerReport in /status; radar
   runs only in the trusted L3 runner, never in the Worker.
6. `2bd0b95` persistence + concurrency (C-1305 #4): all mutating DO methods
   serialized through a per-instance mutex (workerd interleaves events
   during sidecar I/O awaits -> duplicate fork / lost update risk);
   restart-reconstruction test via `evictDurableObject` (memory torn down,
   DO storage + sidecar repos preserved) covering canonical/heads/tasks/
   warnings/acks/pairChecks/runnerReport + post-restart push; concurrency
   tests: 2 simultaneous + 4-burst createTask all distinct, no losses.
7. CONTRACT.md `version: 0.1` published (C-1305 #5): exact routes +
   request/response JSON, radar hook signature + status enum semantics,
   ArtifactsPort documented-vs-ASSUMED table, auth, sidecar API, webhook
   shape; README rewritten to match (worker-performs-no-git statement).

### Final test results (this executor's head)

- `npm run typecheck` (tsc --noEmit): clean.
- `npm test` (vitest, inside workerd, against the real-git sidecar booted
  by test/global-setup.ts): **8 files, 35 tests, 35 passed** —
  radar contract (4), envelope (2), auth (5), coordinator flow w/ real
  commits (9), vector-gated checks incl. 409 stale (6), C-1306 task
  contract (5), DO restart + concurrency (3), outbound-fetch canary (1).
- `npm run test:sidecar` (node --test): **11 tests, 11 passed** — admin
  API auth, seeded real repos, fork/pin-base, plumbing commits helper,
  REAL git clone/commit/push via git http-backend, post-receive ->
  worker webhook capture, invalid-token + read-token-cannot-push.
- `npm run test:all` = typecheck + both suites: all green.
- Fix #9 verified: `du -sh node_modules` = 325 MiB (unchanged; sidecar uses
  Node built-ins + system git 2.43 only; package.json deps untouched).

### Notes / deviations

- Fake DurableObjectState construction is rejected by the workerd
  DurableObject base class, so the restart test uses the real DO via
  `evictDurableObject` (cloudflare:test) instead of a hand-rolled fake.
- StaleVectorError was replaced by a `{stale: true, currentHeads}` return:
  custom error properties do not survive DO RPC marshalling.
- Canonical repo names get a per-model random 8-hex suffix so isolated
  per-test-file DO storage never collides in the shared sidecar repo root.
- POST /events/push, /events/artifacts, /tasks/:id/tests and /warnings/
   :id/ack stay unauthenticated in local mode (attestational/ingest
  routes); CONTRACT.md flags authenticating /events/* before any deploy.
