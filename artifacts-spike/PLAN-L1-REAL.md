# PLAN-L1-REAL — running L1's RealArtifacts against real Cloudflare Artifacts

Written by zc-artifacts-1 after the step-1 spike (RESULTS.md, 2026-10-03). All spike claims below are
evidence-backed by the ops ledger; items not exercised by the spike are marked UNVERIFIED.

## 0. Prerequisite facts from the spike

- Account is Workers Paid; Artifacts responds on all documented REST routes; namespace
  `agent-branches-dev` and repos `demo-canonical` / `demo-agent-1` / `demo-agent-2` exist (tiny, reusable
  for integration tests — see RESULTS.md cleanup list before deleting).
- Binding-relevant deltas found: commit metadata uses `hash`/`committedAt` (epoch s) over REST
  (binding shape still unverified); tokens are `art_v2_x_…`, not the documented `art_v1_…` (shape
  attested structurally — appendix-transcript.md token-shape line; hex elided at capture);
  `status` only on repo LIST; `last_push_at` stays null; read-scope push → HTTP 400.
- Wrangler 4.147.0 (L1's node_modules) runs `artifacts namespaces|repos list` headless with
  `CLOUDFLARE_API_TOKEN`/`CLOUDFLARE_ACCOUNT_ID` env vars (O20/O21). The `get` subcommands and the
  existence/absence of create/fork subcommands are UNVERIFIED (not exercised/captured) — REST is the
  validated path for namespace create and fork.

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
- **Fork/create responses embed a live 24h write token.** Coordinator rule (same posture as §5.2):
  persist only a digest + `{id, scope, expires_at}` for management; if the plaintext must rest
  anywhere (push boundary / in-flight handoff), encrypted DO storage — never plaintext — or
  immediately revoke; never log it (redactor pattern `art_[A-Za-z0-9_]*[0-9]…_[0-9a-f]{8,}` —
  generalized after the spike caught the docs' `art_v1_` being wrong; `redact.py --gate` fail-closed
  for evidence pipelines, `precommit-secret-scan.sh` for commits).
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
   time). An unauthenticated event ingest forges arbitrary push state. **Webhook auth is MANDATORY
   whenever a webhook receiver is enabled** (§4's alternative): signature verification + a
   timestamp/replay window + a source allowlist, live at the moment the route ships. The §4 deferral
   is valid only while no webhook route exists — there is no silent deferral.
2. **Token storage**: minted repo tokens and the API token never in logs/URLs/Git (redactor gate in
   CI + commit hook — `artifacts-spike/precommit-secret-scan.sh` over staged diffs, `redact.py --gate`
   fail-closed for evidence pipelines). At-rest posture (resolves the former §3-vs-§5.2 contradiction;
   both sections now state the same rule): **store only a digest** plus `{id, scope, expires_at}`
   wherever management/revoke is the only need; where the plaintext must rest (the push boundary /
   in-flight agent handoff) it is stored **encrypted** (encrypted DO storage), never plaintext.
   Stated blast radius if the encrypted store leaks: tokens are repo-scoped, short-TTL (24h hard cap),
   individually revocable by id via the documented DELETE. Revoke-on-task-end path must be exercised
   in tests (revoke route validated O28; the O29 hygiene revoke was not captured — cover the revoke
   path for every token class in tests).
3. **Least privilege**: read tokens for clones/review; write only for the pushing agent; canonical
   repo write token held only by the coordinator; short TTLs (≤1h) with documented re-mint.
4. **Rate limits / budgets**: control-plane 2,000 requests per 10 seconds per Artifacts namespace and
   git 2,000 requests per 10 seconds per artifact — **re-sourced 2026-10-03** from the official limits
   page (snapshot `docs/new-limits.md`, developers.cloudflare.com/artifacts/platform/limits, "Last
   updated Oct 1, 2026"): exact rows quoted — "Control-plane request rate | 2,000 requests per 10
   seconds per Artifacts namespace"; "Git request rate, per artifact | 2,000 requests per 10 seconds
   per artifact". (None of the five API pages fetched for the spike contains the figure — the review
   correctly flagged the earlier unsourced version.) No throttling observed at spike scale. Add
   client-side op budgeting + 429 backoff in the port anyway; ops become billable Oct 14 (10k
   ops/month included) — the spike's evidenced lifecycle cost 28 ops, so a per-task budget of ≤100 ops
   leaves wide headroom; wire the counter the coordinator already needs for evidence.
5. **Deploy hygiene**: no secrets in wrangler.jsonc; `wrangler secret put` for anything sensitive;
   CI token scoped to Artifacts Edit only; public repo stays free of `.dev.vars`, credentials, headers.
6. **Remote URLs embed the account id** (`https://<account>.artifacts.cloudflare.net/...`) — treat
   as semi-public; redact in evidence as `<account_id>`.
7. **CORS — required before any public deploy** (absent from the original plan; flagged by the
   independent review). The coordinator backs a browser UI and ingests events, so define the policy
   explicitly in the Worker:
   - **Allowed origins**: explicit per-environment allowlist from config/wrangler vars (dashboard /
     preview origins only). No `Access-Control-Allow-Origin: *`, no reflecting arbitrary Origins.
   - **Preflight**: answer `OPTIONS` with `Access-Control-Allow-Origin` (the matched allowlisted
     origin only), `Access-Control-Allow-Methods` limited to the routes' methods,
     `Access-Control-Allow-Headers` (`Authorization`, `Content-Type`), and `Vary: Origin`.
   - **Credentials policy**: auth is via `Authorization` headers, not cookies —
     `Access-Control-Allow-Credentials` stays `false`; with the origin allowlist this keeps browser
     clients from becoming a token-exfiltration path.
   - **Public vs authenticated**: no coordinator route is public (§5.1); any genuinely public read
     route added later must be listed here explicitly with its own rate limit. CORS is irrelevant to
     non-browser agents and to the server-to-server `/events/artifacts` ingest, whose authenticity
     is §5.1's requirement.
8. **Namespace isolation — required before any public deploy** (absent from the original plan;
   flagged by the independent review). Model: **one dedicated namespace per environment** (dev today:
   `agent-branches-dev`; any staging/public environment gets its own namespace, never shared across
   environments); within a namespace, the repo is the tenant boundary — task forks are created only
   under their environment's namespace and only by the coordinator. **Namespace create/delete is an
   admin operation**: allowed only to the Worker's authenticated + authorized admin path (operator
   role, §5.1/§5.6 review should re-derive this) and the one-time bootstrap script — an agent
   principal can never create or delete a namespace. Jurisdiction note: the namespace was created
   `unrestricted` (O2 evidence); if data-residency pinning is ever required, jurisdiction must be
   selected at creation time (whether it can be changed later: UNVERIFIED — see the Cloudflare
   data-localization guide for Artifacts before relying on it).
9. **Cleanup of spike/demo resources — dated gate item** (promoted from RESULTS.md's "later"
   checklist so nothing forces it to be skipped). **Owner: claude-principal lane. Due: 2026-10-07**
   (before the Oct-14 billable-ops switchover) **and a hard prerequisite for any public deploy or
   recorded demo.** State as of 2026-10-03: **executor-reported post-review, not in the transcript;
   treat as UNVERIFIED — this gate item verifies it** (the read-only token list
   `GET .../repos/demo-agent-1/tokens?state=all` it cites has no capture): namespace
   `agent-branches-dev` + 3 repos live; demo-agent-1 reportedly has exactly one active write token
   (id `i8ppt364o5tsgguf`), created 2026-10-03T17:00:33.909Z, expires_at 2026-10-04T17:00:33.909Z
   (+24h, per the uncaptured list). The canonical minted token's revoke (O29) was not captured either,
   so demo-canonical needs the same list-check; reviewer arithmetic bounds it — the O5/O22 capture
   shows that token's own +1h expiry at 2026-10-03T17:58:29Z, so it self-expired even if O29 never
   executed. Steps: revoke any still-active spike tokens (demo-agent-1's after its next-step use,
   at its expiry at the latest); verify each of the three repos' token list returns zero active;
   `DELETE` the three repos (expect 202s); `DELETE` the namespace (verify route availability; if
   absent, deleting the repos empties it); remove the local 0600 files and /tmp scratch paths listed
   in RESULTS.md. Verification: all three token lists return zero active tokens and the namespace no
   longer appears in `namespaces list`.

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
