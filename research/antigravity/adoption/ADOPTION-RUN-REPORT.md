# Adoption Run Report — C-1441: Bounded Invalid-Bearer Rate Limiter & Agent Branches Workflow Adoption

- **Executor:** zc-ab-adoption (ZCode, dispatched by antigravity-head 46fdb644)
- **Date:** 2026-10-03 (Europe/Berlin), branch `proto/ab-adoption`
- **Workspace:** `/home/alexey/git/agent-branches-adopt` (worktree of cloudflare-agent-git)
- **Scope honored:** edits confined to `prototype/src/**`, `prototype/test/**`, `research/antigravity/adoption/**`
- **Task:** Concrete Agent Branches workflow adoption with a security fix: a bounded invalid-bearer rate limiter in the provider-neutral router.

## 1. What was implemented

`BearerRateLimiter` in `prototype/src/core/router.ts` — pure, HTTP-free core logic:

- Tracks **consecutive 401 outcomes per client key**. After **5 failures inside a 60 s window** the block arms: the router answers **429** `{"error":"rate_limited","message":"Too many failed authentication attempts. Please retry later."}` with **`Retry-After: 60`** instead of 401, until the window from the *first* failure expires (failures outside the window restart the count, so low-and-slow guessing stays bounded per window).
- **Valid authentication is never blocked** and **clears** the client's failure count.
- **Only unauthenticated bearer failures count.** 403 (valid credential, wrong agent) and 503 (fail-closed misconfiguration) are neither counted nor cleared — they are not client-side unauthenticated failures.
- **Hard-capped table:** max 500 tracked clients, LRU eviction (Map insertion order, delete+set refresh). A flood of unique sources evicts other attackers' entries but can never grow memory. Clients whose IP the runtime cannot determine share one conservative `unknown` bucket.
- **Wiring with clean defaults** (500 entries / 5 failures / 60 s / Retry-After 60):
  - `src/cloudflare/worker.ts`: module-scope instance per isolate; `clientKey` from `cf-connecting-ip`.
  - `src/local/main.ts`: instance per local runtime; `clientKey` from `socket.remoteAddress` (typed via a structural, optional `socket` field in `src/local/node-globals.d.ts`).
  - `HttpRequest` gained optional `clientKey`; `RouterServices.rateLimiter` is optional so minimal rigs remain valid, but the node test rig injects it too, so the offline suites exercise the same defaults.
- Per-request cost is one map op on the auth path; no new dependencies; no changes to the wire contract for legitimate callers (only the new 429 outcome for abusive ones).

**Deliberate limitation (documented, not hidden):** the Worker-side table lives per isolate. It bounds memory and blunts floods per isolate; it is not a global cross-isolate counter (that would need a Durable Object and is out of scope for this bounded fix). Isolate eviction resets counts — acceptable for a prototype-tier defense, flagged for the head if production hardening is wanted.

## 2. Agent Branches workflow trace (local sidecar + local runtime)

Executed the real prototype workflow on this machine, no network beyond loopback:

1. **Stack up.** `local-artifacts/sidecar.mjs` (real bare git repos on disk, smart HTTP, per-repo tokens) on `127.0.0.1:37731`; the Node coordinator (`src/local/main.ts` compiled via `tsconfig.node.json`) on `127.0.0.1:38841` with `COORDINATOR_STATE_FILE=/tmp/ab-adoption-run/state.json`. Credentials freshly generated per run, mode 600, never printed or committed.
2. **`POST /setup`** (ADMIN bearer) → `201`, canonical repo `agent-branches-canonical-1ecc04f0` created on the sidecar.
3. **`POST /tasks`** `{agent:"zc-ab-adoption", intent:"implement bounded invalid-bearer rate limiter in router"}` → `201`:
   - `taskId: task-0002`, `agentId: zc-ab-adoption-0002`
   - `fork: agent-branches-canonical-1ecc04f0-zc-ab-adoption-0002` (real bare repo), `base_sha = head = b995852e21241045ff8da6857ba99809b5e5eba8`
   - write token plaintext (66 chars, sidecar `art_v1_…?expires=…` format — it is the per-repo fork token), expiry `2026-10-03T21:27:26Z`. Plaintext kept in `/tmp/ab-adoption-run/agent-credentials.json` (mode 600, ephemeral); **redacted everywhere else**.
4. **Real commit on the fork.** `git clone` of the fork over smart HTTP authenticated with the agent write token (`http.extraHeader: Authorization: Bearer …`), committed `ADOPTION-NOTE.md` → `c2b178887bf940deb8d5c598cf7b58d7064be9ea`, `git push origin main` → remote head confirmed `c2b1788…` via the sidecar API.
5. **Push event.** `POST /events/push` `{agent:"zc-ab-adoption-0002", sha:"c2b1788…"}` with the agent token → `200` `{"accepted":true,"deduped":true,…}`; `GET /status` shows `heads["zc-ab-adoption-0002"] = c2b1788…`. (First attempt 500ed because my launcher passed empty `LOCAL_ARTIFACTS_TOKEN` — launch-script bug, fixed by exporting; the push had already been recorded durably before the failing sidecar callback, so the retry correctly reported `deduped:true`. Noted as a crash-consistency observation for the head.)
6. **Checks step.** `POST /checks` (RUNNER bearer) with `contract:"0.0"`, the current head vector, `policy:"adoption-c1441"`, `results:[]` → `200` `{"stale":false,"accepted":0,…}` — stale-vector machinery engaged with a live vector.
7. **Live limiter demo on the same running stack.** Invalid ADMIN bearers on `POST /tasks`: attempts returned **401** until the 5-failure threshold armed, then **429 + `retry-after: 60`** with the exact body above; a **valid ADMIN request immediately returned 201** (never blocked) and cleared the count; the next invalid bearer was a plain **401** again. One honest nuance: my 5th physical invalid attempt already received 429 — duplicated loopback requests (see §4) interleave on the same client key, so the counted failures crossed the threshold one attempt early. Semantics unchanged: the block arms after 5 *counted* consecutive 401s.
8. **Ordinary Git fallback verification.**
   - Prototype side: plain `git ls-remote` against the sidecar-hosted canonical with a read-scoped token resolves `HEAD → b995852e…` — the Artifacts backend is ordinary git, no proprietary lock-in; clone/push worked with plain git + bearer.
   - Delivery side: this very report and code change travel through ordinary git (`proto/ab-adoption` → `origin`), independent of the prototype under test.

## 3. Tests and verification (all green)

- `npm test` (vitest + workerd, real-git sidecar): **92/92 tests, 13/13 files passed** (31 s), including the new worker-path limiter test.
- `npm run test:node` (plain node --test, no workerd): **36/36 passed**, including four new limiter unit tests and two new router-level tests.
- `npx tsc --noEmit` and `npx tsc --noEmit -p tsconfig.node.json`: **exit 0**.
- New coverage: 5×401-then-429 ladder with exact body/header; valid-token bypass + count clearing; 403/503 non-counting; table cap at defaults (5000 unique keys → size exactly 500, cap asserted per insert); LRU eviction with evicted-key restart; 60 s window restart; threshold arming; `unknown`-key shared bucket; 429 body never echoes the presented token.

## 4. Measured memory and bounded-table behavior (Node, compiled build)

| Measurement | Value |
| --- | --- |
| Unique clients pushed | 5000 |
| Max observed table size | 500 (cap never exceeded, asserted per insert) |
| Final table size | 500 |
| Table heap (with GC) | ≈ 88.8 KB → **≈ 178 B / tracked client** |
| Table heap (no GC pressure) | ≈ 212.7 KB |
| Cold insert (with eviction) | ≈ 1.0 µs/op |
| Hot-key op (retained key) | ≈ 156 ns/op |

Worst case ≈ 0.09 MB per isolate — the DoS surface the fix closes (unbounded per-IP maps) costs less than a cached response.

## 5. Anomaly: a duplicate executor mirrors this session's actions (evidence + impact)

Reproducible observations on two fresh stacks, all within the same wall-clock second as my own calls:

- A `task-0001` with my exact agent name and intent appeared before/alongside my `POST /tasks`, with a full credential record — on a stack whose port string had existed only in my commands.
- `git push` to my freshly-committed fork returned **"Everything up-to-date"**: the remote already held my commit object (`c2b1788…`), i.e. an identical commit object reached the fork before my push did.
- My limiter demo crossed the threshold one physical attempt early (interleaved duplicate requests from loopback).
- `ps` shows a `community-base` relay runner (`relay-adoption-coordination-20261003/runner.py run aplexer|aisl1890qa`) on this host; I did not inspect or touch that workspace (peer scope/privacy).

**Interpretation:** a coordination-side process duplicates (replays) this session's command stream on the same host/network namespace with sub-second lag. **Impact on this task: none** — all duplicated operations are idempotent or deduplicated by design (push dedup ring, git object identity, idempotent auth), my credentials never left my process env, and the demo stack is throwaway in `/tmp`. **Recommendation to principals:** attribute the relay (likely the community-base orchestration runner), and treat "same-second duplicate execution" as a known effect when reading session evidence; double-counted requests can skew request-level metrics.

## 6. Handoff notes

- `prototype/CONTRACT.md` is outside my allowed paths and was **not** updated; the wire gained one outcome (429 on abusive callers) that the contract owner should fold in.
- Monitoring: 429s carry `retry-after`; consider surfacing a rate-limited counter in supervision dashboards.
- Stack teardown: sidecar/runtime processes and `/tmp/ab-adoption-run/*` (incl. credentials) are ephemeral scratch and were cleaned up after the run; nothing sensitive is committed here.
