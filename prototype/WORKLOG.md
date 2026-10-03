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
