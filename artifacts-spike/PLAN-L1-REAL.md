# PLAN-L1-REAL — running L1's RealArtifacts against real Cloudflare Artifacts

Written by zc-artifacts-1 after the step-1 spike (RESULTS.md, 2026-10-03). All spike claims below are
evidence-backed by the ops ledger; items not exercised by the spike are marked UNVERIFIED.

## 0. Prerequisite facts from the spike

- Account is Workers Paid; Artifacts responds on all documented REST routes; namespace
  `agent-branches-dev` and repos `demo-canonical` / `demo-agent-1` / `demo-agent-2` exist (tiny, reusable
  for integration tests — see RESULTS.md cleanup list before deleting).
- Binding-relevant deltas found: commit metadata uses `hash`/`committedAt` (epoch s) over REST
  (binding shape still unverified); tokens are `art_v2_x_…`, not the documented `art_v1_…`;
  `status` only on repo LIST; `last_push_at` stays null; read-scope push → HTTP 400.
- Wrangler 4.147.0 (L1's node_modules) runs `artifacts namespaces|repos list/get` headless with
  `CLOUDFLARE_API_TOKEN`/`CLOUDFLARE_ACCOUNT_ID` env vars. No wrangler subcommand exists for
  namespace create or fork — those are REST-only.

## 1. Binding vs REST — which surface for what

| Concern | Surface | Why |
|---|---|---|
| Coordinator Worker (DO `Coordinator`, checks-wire, radar) | **Workers binding** `env.ARTIFACTS` | No token management, account-authenticated by the platform; RealArtifacts is already binding-shaped (`src/artifacts/real.ts`) |
| One-time bootstrap: namespace create, demo-canonical create, base push | **REST** (ns+repo create) + **git smart HTTP** (push) | Namespace create and fork have no wrangler command; git push is the only way to load commit objects |
| Forks for tasks | **REST** from scripts; **binding** (`repo.fork`) inside the Worker | Both documented; spike validated REST shape incl. `objects` count and returned token |
| Token mint/revoke/list | **Binding** (`createToken`/`revokeToken`/`listTokens`) in Worker; **REST** in scripts | Spike validated REST `POST/DELETE/GET .../tokens` incl. ttl and scopes |
| Head/log reads | **Binding** `log({ref, limit:1})` in Worker; REST `log` in scripts | Validated; no refs-enumeration API exists (ASSUMED-A CONFIRMED) — `git ls-remote` is the only full-ref listing |
| Agent-side clone/commit/push | **Git smart HTTP + repo-scoped Bearer token** | Validated end-to-end (clone 500ms, push 346ms); Basic-auth-in-URL documented but forbidden by our rules |

Decision: keep RealArtifacts on the binding; add a thin REST client ONLY for the bootstrap script
(`scripts/bootstrap-artifacts.*`: create-namespace-if-missing, create canonical if missing, mint
ops token with `ttl=3600`). Do not port the whole port to REST.

## 2. Wrangler config + types (concrete changes)

1. `prototype/wrangler.jsonc`: add
   ```jsonc
   "artifacts": [{ "binding": "ARTIFACTS", "namespace": "agent-branches-dev" }]
   ```
2. Run `npx wrangler types` (wrangler ≥ 4.145 in L1's node_modules = 4.147.0). This generates the
   authoritative `Artifacts` type into `worker-configuration.d.ts` and `Env.ARTIFACTS`.
3. Reconcile `RealArtifacts`' hand-declared `ArtifactsNamespaceBinding` with the generated type.
   First reconciliation targets (from REST evidence): commit field names (`id` vs `hash`,
   `timestamp` ISO vs epoch `authoredAt`/`committedAt`) and token result casing
   (`expiresAt` binding-style vs `expires_at` REST). Fix `headCommit`/`log` consumers accordingly;
   `CommitMetadata` in `src/types.ts` likely needs a mapping layer so the port stays
   provider-shape-free.
4. `compatibility_date`: docs example uses `2026-10-02`; current config `2025-06-01`. Bump only with
   the full test suite green; not itself required by the binding.
5. Local dev: TOML supports `remote = true` for remote-artifacts local dev; JSON-config support for
   that flag is UNVERIFIED — if `wrangler dev` needs it, test a scratch TOML config before
   converting wrangler.jsonc.

## 3. Credential handling

- **API token** (control plane): `CLOUDFLARE_API_TOKEN` from the orchestrator-provided
  `~/.config/cloudflare/agent-branches.env` (0600), loaded per-process via `set -a; . file; set +a`.
  For CI/deploys later: a separate token with ONLY Artifacts Edit, stored via `wrangler secret` /
  CI secret store — never in wrangler.jsonc, never in Git.
- **Repo tokens** (git data plane): mint per purpose with short TTL (spike: 3600s for ops, ≤600s
  would do for single pushes; fork/create defaults are 24h — revoke if unused, validated O23/O25/O28/O29).
  Delivery to git: Bearer via `http.extraHeader` persisted in a 0600 git-include file referenced by
  `-c include.path=<file>` (validated pattern — keeps tokens out of argv and URLs; include files must
  use proper `[http] extraHeader = …` INI syntax). `GIT_TERMINAL_PROMPT=0` always.
- **Fork/create responses embed a live 24h write token.** Coordinator rule: either persist it
  deliberately (encrypted DO storage) or immediately revoke; never log it (redactor pattern
  `art_[A-Za-z0-9_]*[0-9]…_[0-9a-f]{8,}` — generalized after the spike caught the docs' `art_v1_`
  being wrong; wire redact.py into the commit/test gates).
- **Plaintext visibility**: `createToken` returns plaintext exactly once; store `{id, scope, expires_at}`
  for management and the plaintext only where the push actually happens.

## 4. Post-push event path

- Target architecture (documented): **event subscriptions**. Repo-level source `artifacts.repo` emits
  `cf.artifacts.repo.pushed` with `{ref, before, after, commits[{id,message,timestamp,author,committer,parents}],
  totalCommitsCount, commitsTruncated}` — L1's `/events/artifacts` route already accepts this envelope.
- UNVERIFIED (ASSUMED-E stands): how the subscription is created (dashboard/API) and its delivery
  guarantees (at-least-once? ordering? retry/backoff?). Next spike step: create one subscription
  against the deployed Worker's `/events/artifacts`, push to demo-agent-1, capture the real event JSON.
- **Normalization**: event commits use `id`+ISO `timestamp`; REST log uses `hash`+epoch `committedAt`.
  Map both into the port's `CommitMetadata` at exactly one boundary.
- **Interim + permanent fallback**: bounded reconciliation poll — coordinator compares its recorded
  task head vs `log({limit:1})` per active repo on a slow cadence (validated cheap: ~130–170ms/read).
  Keep this loop even after subscriptions work, because event delivery semantics are unproven.
- Webhook alternative (custom HTTP receiver) is NOT needed while subscriptions exist; revisit only if
  subscription creation turns out to be dashboard-only.

## 5. Security review — required BEFORE any public deploy

1. **Auth on all routes** (muse-r48 flagged the auth review at 3af4c08 — close it): every coordinator
   route requires an authenticated principal; `/events/artifacts` must verify event authenticity
   (shared secret on the subscription, or signature if the guide documents one — verify at creation
   time). An unauthenticated event ingest forges arbitrary push state.
2. **Token storage**: minted repo tokens and the API token never in logs/URLs/Git (redactor gate in
   CI + commit hook); at-rest plaintext only in DO/KV with a documented blast radius; revoke-on-task-end
   path must be exercised in tests (routes validated O28/O29).
3. **Least privilege**: read tokens for clones/review; write only for the pushing agent; canonical
   repo write token held only by the coordinator; short TTLs (≤1h) with documented re-mint.
4. **Rate limits / budgets**: documented 2,000 req/10s per namespace (control plane) and per artifact
   (git) — no throttling observed at spike scale. Add client-side op budgeting + 429 backoff in the
   port anyway; ops become billable Oct 14 (10k ops/month included) — the spike's full lifecycle cost
   29 ops, so a per-task budget of ≤100 ops leaves wide headroom; wire the counter the coordinator
   already needs for evidence.
5. **Deploy hygiene**: no secrets in wrangler.jsonc; `wrangler secret put` for anything sensitive;
   CI token scoped to Artifacts Edit only; public repo stays free of `.dev.vars`, credentials, headers.
6. **Remote URLs embed the account id** (`https://<account>.artifacts.cloudflare.net/...`) — treat
   as semi-public; redact in evidence as `<account_id>`.

## 6. Ordered next steps (each independently verifiable)

1. Add the binding to wrangler.jsonc on a scratch branch; `npx wrangler types`; fix type reconciliation
   (`.hash`/epoch vs `.id`/ISO) with tests red→green. (No deploy needed; `wrangler types` is local.)
2. Bootstrap script (REST): idempotent namespace/repo creation + canonical base push, reusing
   `agent-branches-dev` (no new resources; delete-repo/re-create covered by the cleanup list).
3. `wrangler dev` smoke: DO reads `env.ARTIFACTS` (closes ASSUMED-D), lists repos, reads a log.
4. Event subscription spike: create subscription → real `cf.artifacts.repo.pushed` captured by
   `/events/artifacts` (closes ASSUMED-E); record delivery latency and retry semantics.
5. Independent review (per peer-review rule): another principal/reviewer re-derives the security list
   in §5 against the actual Worker code before any public deploy is even drafted.
