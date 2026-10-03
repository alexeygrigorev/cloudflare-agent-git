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

## 2026-10-03 (later) — muse-r46 review fixes (executor zc-l1-fix)

Cross-family review `.local/muse-r46/verdict.md` (Space Bunny) on pin
`762ff3d`. Four defect classes, each its own commit with a regression test
that fails before the fix (red observed and logged for every one):

- **D1** `b65643f` — canonical pair ordering. Reversed pair [b,a] at
  unchanged heads duplicated an active warning (review reproduced
  first=1/second_created=1); now canonicalPairHeads() sorts pair+heads
  before vector/headsAtIssue in applyCheckResultsNow, runRadar and
  warningForPairAtHeads. Red: duplicate warn created pre-fix.
- **D2** `8b6c54d` — seenPushes bounded per agent (ring of 16, exported
  SEEN_PUSHES_CAP_PER_AGENT; flat-array migration on load). Red:
  evicted-window redelivery was deduped=true pre-fix.
- **D3** commit 3 — real-mode createTask. RealArtifacts.fork no longer
  throws on baseSha: forks the default branch, reports realized base on
  ForkResult (types.ts); coordinator records the realized base as
  base_sha. ASSUMED-F documented. Red: UNSUPPORTED throw pre-fix.
- **AUTH** commit 4 — ALL mutating routes authenticated: agent per-task
  token (SHA-256 digest stored in DO at creation) / ADMIN_TOKEN /
  sidecar shared bearer on the two /events/* webhooks; cross-agent
  writes 403; tokensMatch now compares digests (length not observable).
  Sidecar forwardPush sends the shared bearer. CONTRACT.md bumped to
  0.1.1 with the change list; README auth + route table updated.
  Red: 4 new auth tests failed (200/201/202 from unauthenticated calls).

Supersedes the earlier WORKLOG note that /events/*, /tasks/:id/tests and
/warnings/:id/ack "stay unauthenticated in local mode".

Final suite (this executor): typecheck clean; vitest 9 files 44/44;
node --test sidecar 11/11. No new npm deps.

## 2026-10-03 (later) — canonical v0.1 wire alignment (executor zc-l1c-wire, codex C-1350)

Task: align POST /checks and the /status pair views to the CANONICAL v0.1
wire format that L3 emits (radar/engine.py `export_l1_payload`, branch
origin/proto/l3-radar @ 2b928fc), keep the legacy string shape behind an
explicit documented adapter, and expose per-pair coverage +
agentId-keyed heads in PairStatusView for the L4 clean gate.

`a whoami --json` (full result):

```json
{
  "schema_version": 1,
  "id": "a93fd86b-c006-4b3c-88e7-0a8960ea2141",
  "workspace": "/home/alexey/git/cloudflare-agent-git",
  "tag": "zc-l1c-wire",
  "engine": "shell",
  "parent_session": "b3a92dd0-a17e-4a62-940f-eb3b829393f6",
  "command": [
    "bash",
    "-lc",
    "cd /home/alexey/git/cloudflare-agent-git && ZCODE_WARM=1 timeout 60m zcodex exec --skip-git-repo-check \"$(cat .local/claude/ZC-L1C.md)\" > .local/claude/zc-l1c.log 2>&1; echo \"RUN_EXIT=$?\" >> .local/claude/zc-l1c.log"
  ],
  "cwd": "/home/alexey/git/cloudflare-agent-git",
  "env": {},
  "env_unset": [],
  "limits": {
    "memory_bytes": 1572864000
  },
  "history_bytes": 4194304,
  "created_at_ms": 1791038151627,
  "updated_at_ms": 1791038157119,
  "last_activity_ms": 1791038151783,
  "reported_state": "working",
  "reported_state_at_ms": 1791038157119,
  "phase": "running",
  "worker_pid": 384609,
  "workload_pid": 384641,
  "worker_cgroup": "/user.slice/user-1000.slice/user@1000.service/app.slice/aplexer-workload-a93fd86b-c006-4b3c-88e7-0a8960ea2141.scope",
  "workload_cgroup": "/user.slice/user@1000.service/app.slice/aplexer-workload-a93fd86b-c006-4b3c-88e7-0a8960ea2141.scope",
  "containment_cgroup": "/sys/fs/cgroup/user.slice/user@1000.service/app.slice/aplexer-workload-a93fd86b-c006-4b3c-88e7-0a8960ea2141.scope",
  "containment_cgroup_identity": {
    "boot_id": "edbec548-453f-4111-b38e-e7c16d12aa93",
    "cgroup_namespace_device": 4,
    "cgroup_namespace_inode": 4026531835,
    "mount_namespace_device": 4,
    "cgroup_mount_id": 33,
    "cgroup_root_device": 28,
    "cgroup_root_inode": 1
  },
  "containment_empty": false,
  "socket_path": "/run/user/1000/aplexer/sessions/a93fd86b-c006-4b3c-88e7-0a8960ea2141/control.sock",
  "history_path": "/home/alexey/.local/state/aplexer/sessions/a93fd86b-c006-4b3c-88e7-0a8960ea2141/history.bin"
}
```

Start state: proto/l1-scaffold pulled, head 3af4c08 (as assigned). L3
canonical source read at origin/proto/l3-radar 2b928fc
(`export_l1_payload` in radar/engine.py:1299): per-pair `tests_collected`
travels inside `results[i].evidence`, top-level `coverage.tests_collected`
is the sum; `pair` sorted, `heads` keyed by agentId, `kind` is
"textual"|"test"|null, `evidence` always carries `summary` (+ optional
`files`, `test_output_tail`, extra diagnostic fields preserved).

### Outcome — canonical wire integrated (C-1350 + C-1357), suite green

Deconflict: claude-principal dispatched C-1350 TWICE — message 01a10223-00eb
to zc-l1-fix ("do after the R46 fixes, same branch", explicit
contract:'0.0' legacy adapter) and my ZC-L1C launch ~30 min later. Both
executors wrote the same worktree concurrently until zc-l1-fix messaged a
deconflict split (it: src wire + CONTRACT; me: test/wire.test.ts + WORKLOG;
verified against both task messages). Recorded in aplexer 01a10240/01a10245
and reported to claude-principal (01a10246).

Mid-integration zc-l1-fix's COLD zcodex session hit its 60 m timeout
(EXIT=124, its Edit/Write tools had been erroring all along) and died with
the wire work UNCOMMITTED. I integrated it with attribution: committed as
the wire commit below, after review (spec-faithful: mandatory contract
dispatch per 01a10223, kind textual|test|null, L3 summary fallback chain,
heads required + value-checked only AFTER the stale gate so stale stays
409, verbatim typed evidence + per-pair tests_collected served on
PairStatusView, verbatim policy/coverage on the runner report).

Integration fixes by zc-l1c-wire:

- vitest `fileParallelism: false` — parallel test files OOM-killed the
  1.5 GiB sandbox (observed twice: zc-l1-fix "Killed", then me).
- 3 test bugs: my L3 mirror always synthesizes evidence (real exporter
  never omits it) so the no-evidence fixture is hand-built; warning
  assertions scoped to the test's pair (DO state is shared per file);
  checks-wire.test.ts string-evidence mutation lacked heads so the heads
  error pre-empted the evidence error.

C-1357 silent-callback guard (mine, red-first in
local-artifacts/notify.test.mjs + test/unprocessed.test.ts):

- Sidecar: forwardPush retries 3x (50/100/200 ms), then records the push in
  a durable NotifyLedger (notify-state.json) served at GET /api/notify-state;
  a later successful delivery for the repo+ref supersedes it; an
  unconfigured notify URL is the documented local mode, NOT a failure;
  repo delete purges; POST/DELETE /api/notify-state are bearer-gated
  dev/test helpers.
- Worker: optional ArtifactsPort.unprocessedPushes() (SidecarArtifacts ->
  /api/notify-state; RealArtifacts -> [], ASSUMED-G). GET /status adds
  top-level `unprocessedPushes` (agentId-resolved) and forces every pair
  with an affected agent to not_checked + unprocessedReason + stale — a
  stored clean never presents as current while the agent's true head is
  unknown.
- CONTRACT.md bumped to 0.1.2: exact v0.1 wire, contract dispatch rule,
  PairStatusView changes (heads keyed by agentId, per-pair coverage,
  typed evidence), C-1357(a) auth recap incl. the post-receive callback
  and 0600 token handling, and the C-1357(b) guard.

Suite (final, this executor): typecheck clean; vitest 12 files 67/67;
node --test sidecar 16/16 (11 pre-existing + 5 new). No new npm deps.
Commits: 67792d8 (sidecar guard), <wire commit> (C-1350 integration,
implementer zc-l1-fix + zc-l1c-wire), <docs commit> (CONTRACT 0.1.2 +
this entry).

## 2026-10-03 (later) — RealArtifacts matches REALITY from the artifacts-spike (executor zc-artifacts-2)

Task from claude-principal: fold the real-Artifacts spike results
(origin/proto/artifacts-spike @ c75faa1: RESULTS.md, appendix-transcript.md,
PLAN-L1-REAL.md) into L1's RealArtifacts adapter. OFFLINE only (no real API
calls, no deploy, no credentials, no new npm deps).

`a whoami --json` (full result):

```json
{
  "schema_version": 1,
  "id": "46880d0c-8d18-4bd1-974a-aead6277b9bd",
  "workspace": "/home/alexey/git/cloudflare-agent-git",
  "tag": "zc-artifacts-2",
  "engine": "shell",
  "parent_session": "b3a92dd0-a17e-4a62-940f-eb3b829393f6",
  "command": [
    "bash",
    "-lc",
    "cd /home/alexey/git/cloudflare-agent-git && ZCODE_WARM=1 timeout 60m zcodex exec --skip-git-repo-check \"$(cat .local/claude/ZC-ART2.md)\" > .local/claude/zc-art2.log 2>&1; echo \"RUN_EXIT=$?\" >> .local/claude/zc-art2.log"
  ],
  "cwd": "/home/alexey/git/cloudflare-agent-git",
  "env": {},
  "env_unset": [],
  "limits": {
    "memory_bytes": 1572864000
  },
  "history_bytes": 4194304,
  "created_at_ms": 1791047560282,
  "updated_at_ms": 1791047563313,
  "last_activity_ms": 1791047560464,
  "reported_state": "working",
  "reported_state_at_ms": 1791047563313,
  "phase": "running",
  "worker_pid": 619351,
  "workload_pid": 619408,
  "worker_cgroup": "/user.slice/user-1000.slice/session-8287.scope",
  "workload_cgroup": "/user.slice/user-1000.slice/user@1000.service/app.slice/aplexer-workload-46880d0c-8d18-4bd1-974a-aead6277b9bd.scope",
  "containment_cgroup": "/sys/fs/cgroup/user.slice/user-1000.slice/user@1000.service/app.slice/aplexer-workload-46880d0c-8d18-4bd1-974a-aead6277b9bd.scope",
  "containment_cgroup_identity": {
    "boot_id": "edbec548-453f-4111-b38e-e7c16d12aa93",
    "cgroup_namespace_device": 4,
    "cgroup_namespace_inode": 4026531835,
    "cgroup_mount_id": 33,
    "cgroup_root_device": 28,
    "cgroup_root_inode": 1
  },
  "containment_empty": false,
  "socket_path": "/run/user/1000/aplexer/sessions/46880d0c-8d18-4bd1-974a-aead6277b9bd/control.sock",
  "history_path": "/home/alexey/.local/state/aplexer/sessions/46880d0c-8d18-4bd1-974a-aead6277b9bd/history.bin"
}
```

Start state: proto/l1-scaffold pulled, head 3e9983b, working tree clean;
spike branch fetched at c75faa1.

### Outcome — adapter matches spike REALITY; suite green (13 files 88/88 + sidecar 16/16)

Evidence read via `git show origin/proto/artifacts-spike:…` (RESULTS.md,
PLAN-L1-REAL.md, appendix-transcript.md). All work OFFLINE: no real API
call, no deploy, no credentials, no new npm deps (`fetch` injectable in the
REST client; fakes for the binding).

1. **Finding B — commit fields (CONFIRMED over REST).** New seam: the
   binding capability now exposes the REAL raw shape (`hash`, `treeHash`,
   epoch-SECONDS `authoredAt`/`committedAt` — never `id`/ISO `timestamp`),
   and `src/artifacts/map.ts` maps raw→port `CommitMetadata` at exactly one
   boundary (`id` from `hash`, `timestamp` from epoch `committedAt`;
   missing fields throw). Red-first by construction: the old adapter read
   `commits[0]?.id`, which is `undefined` against the real shape — the new
   `headCommit`/`log` tests assert the mapped `hash`/ISO values the old
   code could neither produce nor typecheck.
2. **Finding 1 — tokens OPAQUE.** No prefix validation anywhere; mint and
   create/fork results pass `art_v2_x_<40hex>?expires=<unix>` through
   verbatim (docs' `art_v1_` is wrong). Tests assert verbatim passthrough
   and that the shape starts `art_v2_x_` — a prefix check would fail them.
3. **Findings 2+F — fork default-branch only + readiness via LIST.**
   `RealArtifacts.fork` (muse-r46 D3 behavior kept: baseSha stripped,
   realized base reported) now polls the LIST response's `status` — the
   only surface carrying it (single GET omits it; missing/unknown status
   maps to the conservative `importing`) — bounded via
   `RealArtifactsOptions.readiness` (default 20×500 ms, injectable sleep),
   then reads the realized head. Exhaustion → `ArtifactsForkNotReadyError
   (attempts)`. `last_push_at` (always null, finding 3) is never consulted;
   `info()` never used for status (asserted: 0 info calls in the readiness
   test).
4. **Findings 4/5 — typed errors.** New `src/artifacts/errors.ts`:
   `ArtifactsNotFoundError` (404 + code **10200**), `ArtifactsAuthScopeError`
   (read-scope push → HTTP **400**, NOT 401/403 — spike O27 — via
   `classifyGitHttpError`, where ANY 4xx on push is auth/scope),
   `ArtifactsRateLimitError` (429), `ArtifactsForkNotReadyError`, plus
   `mapRestError`/`normalizeArtifactsError` shared by the binding path
   (best-effort; unrecognized binding throws pass through untouched — the
   binding's thrown shape is UNVERIFIED) and the REST path (exact envelope).
5. **Finding 6 — REST seam for bootstrap.** New `src/artifacts/rest.ts`:
   thin REST client (namespace get/create/ensure, repo create/get/list/
   delete, fork, token mint/list/revoke, log) exactly as validated by the
   spike; Bearer header only (token never in URL); raw snake_case shapes
   kept internal. Per PLAN-L1-REAL §1 the Worker stays on the binding — the
   port is NOT ported to REST; scripts/bootstrap use this client. Both
   paths share errors+map. `wrangler.jsonc` untouched (binding add +
   `wrangler types` = PLAN §6 step 1, next spike step).
6. **Docs.** CONTRACT.md → **0.1.3**: spike fold-in changes 1–5 + the
   real-mode CONFIRMED vs ASSUMED/UNVERIFIED table (D binding-in-DO and E
   event subscriptions explicitly UNVERIFIED; binding-side commit TYPE
   unverified). README: real-mode table + spike-validated switch-to-real
   steps. docs-notes.md: ASSUMED-A/C/F CONFIRMED, B DIFFERENT, D/E/G status
   + new-findings addendum.
7. **Fixtures.** `test/fixtures/artifacts-spike.ts` built from the
   sanitized transcript (O1–O17 shapes verbatim, incl. the real base
   b4346112… and pushed c809475… commits with their epoch instants); the
   two redacted tokens replaced by an obviously-fake `art_v2_x_…` string.
   No secrets committed.

### Final test results (this executor's head)

- `npm run typecheck`: clean.
- `npm test` (vitest in workerd, real-git sidecar): **13 files, 88 tests,
  88 passed** (was 12/67; real-artifacts.test.ts rewritten 3→14 tests,
  rest-client.test.ts new 10 tests).
- `npm run test:sidecar` (node --test): **16/16**.
- `npm run test:all` EXIT=0. node_modules untouched (325 MiB; no new deps).

## 2026-10-03 (later) — Provider-neutral facade: ports + core + cloudflare/local adapters (executor zc-facade)

Task from claude-principal: make the Cloudflare integration swappable —
core logic (task registry, head vectors, dedup, warnings, checks validation,
stale-vector rule, auth decisions) depends ONLY on provider-neutral
interfaces; Cloudflare becomes one set of adapters. OFFLINE only (no deploy,
no new npm deps). Start gated on zc-artifacts-2 (waited, polled `a list`;
its commits aabcb92 + 2a0625e are on origin; CONTRACT now 0.1.3 → docs bump
to 0.1.4 per task).

`a whoami --json` (full result):

```json
{
  "schema_version": 1,
  "id": "52b589ff-0705-46df-b6f0-0c43add37106",
  "workspace": "/home/alexey/git/cloudflare-agent-git",
  "tag": "zc-facade",
  "engine": "shell",
  "parent_session": "b3a92dd0-a17e-4a62-940f-eb3b829393f6",
  "cwd": "/home/alexey/git/cloudflare-agent-git",
  "reported_state": "working",
  "phase": "running"
}
```

(truncated to the identity-relevant fields; full record in the session log)

Start state: proto/l1-scaffold pulled at 2a0625e, working tree clean,
zc-artifacts-2 exit verified via `a list` poll (7 × 60 s).

### Result (same session)

Commits on proto/l1-scaffold (all pushed at the end of the session):

- `48bbabf` ports — GitHost (ex-ArtifactsPort, alias kept),
  CoordinationStore, PushEvents (+ verbatim envelope parser move),
  Clock/Ids; SidecarArtifacts → src/local/githost.ts with injectable
  FetchLike; src/types.ts shim.
- `ba1861c` core — CoordinatorCore (all business rules verbatim, ports
  injected), pure auth decisions (core/auth.ts), THE one route
  implementation (core/router.ts) over neutral HttpRequest/HttpResponse;
  Cloudflare adapters (Coordinator DO wrapper with unchanged signatures,
  DO-storage store, gitHostFromEnv, push-event normalizers, Request
  mapping); src/index.ts + src/coordinator.ts compat shims. Typed-RPC
  tuple widening asserted through ONE documented boundary in worker.ts.
- `64a233c` local — Memory/File CoordinationStores (atomic tmp+rename),
  node:http runtime (serveCoordinator) + zero-dep entry (main.ts),
  minimal ambient Node typings; tsconfig.node.json (workerd-free build,
  no worker types — transitive CF deps cannot compile);
  test:node/typecheck:node scripts; vitest excludes test/node.
- `1f69274` node --test suite — 27 tests: core rules (registry, dedup
  ring, warnings lifecycle, checks validation, stale-vector rule, pair
  views + unprocessed suppression, restart, serialized concurrency),
  router wire parity (auth ladder 401/403/503, envelope 202/400, checks
  409), REAL node:http round trip, architecture gate (src/core +
  src/ports must import no cloudflare:* / @cloudflare/* /
  workers-types / wrangler; positive control included).

**Bug found by the new suite and fixed:** status()/recordPush() returned
the LIVE heads object — invisible over both HTTP wires (they serialize
immediately) but aliasing for direct core consumers. Snapshotted at the
core boundary (heads: { ...model.heads }); wire unchanged.

**Smoke test beyond the suite** (all localhost, offline): sidecar on
:18795 + node runtime main.js on :18796 → /setup 201, POST /tasks
(real fork via SidecarArtifacts), authenticated git clone/push with the
minted token, post-receive webhook (SIDECAR_NOTIFY_URL) → pushes: 1,
404 parity, dedup parity, state file on disk. Smoke processes killed by
exact PID; ports clean. (Also re-learned: never `pkill -f` a pattern
that matches your own shell's command line.)

**Final suite:** `npm run test:all` EXIT=0 — typecheck clean, vitest
13 files / 88 tests, sidecar 16/16, node 27/27.

Docs: ARCHITECTURE.md (ports/adapters/how-to-add-a-provider map),
README architecture + run sections updated, CONTRACT 0.1.4 DOCS-ONLY
bump (wire unchanged since 0.1.2; 0.1.3 was the spike fold-in).

Deliberately NOT done: no deploy, no new npm deps, no CONTRACT wire
change, src/artifacts/real.ts + errors/map/rest untouched (zc-artifacts-2
owns that seam; GitHost factory simply consumes the binding).
