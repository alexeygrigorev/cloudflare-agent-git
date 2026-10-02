# Artifacts capabilities — fetched facts and feasibility notes (claude-zcode-redteam)

Fetched 2026-10-02 ~20:30-20:50 CEST by this delegate via WebFetch from official Cloudflare URLs. Facts = fetched from the named URL; proposals/unknowns labeled. Independent re-verification (does not rely on peer files). Evidence IDs E-RZ1xx.

## Workers binding — E-RZ101 (https://developers.cloudflare.com/artifacts/api/workers-binding/)
- Wrangler config `artifacts: [{binding, namespace}]`; non-inheritable per environment.
- Namespace methods: `create(name, opts?)`, `get(name)`, `list({limit,cursor})`, `import(params)`, `delete(name)`.
- Repo-handle methods: `createToken(scope?, ttl?)`, `listTokens()`, `revokeToken()`, `fork(name, opts?)`, `log({ref,limit,offset})`, `readCommit(hash)`, `readTree(hash)`.
- Repo `status` ∈ {ready, importing, forking}. Create/fork/import opts include `readOnly` (repo-wide), `description`, `setDefaultBranch`; fork has `defaultBranchOnly`; import takes external git source.

## REST API — E-RZ102 (https://developers.cloudflare.com/artifacts/api/rest-api/)
- Base: `https://api.cloudflare.com/client/v4/accounts/{account_id}/artifacts/namespaces/{ns}/...` (namespaces endpoints: POST create with immutable `jurisdiction: "eu"|"us"`, GET list/get).
- Repos: POST create (returns token), GET list (limit≤200, search, sort), GET/DELETE by name, POST `/fork`, POST `/import` (public HTTPS remote; 409 while importing/forking).
- Content: `/log`, `/commit/{hash}`, `/tree/{hash}`, `/blob/{hash}`, `/file?ref&path`, `/raw/{ref}/{path}` (octet-stream vs sniffed content-type).
- Tokens: GET list (state, per_page≤100), POST create (`repo` required, `scope` default **write**, `ttl` 60–31,536,000 s, default 86,400), DELETE revoke.
- REST auth = account Bearer token; repo tokens do NOT authenticate REST, only git operations.
- No REST rate limit stated on that page (see limits, E-RZ104).

## Git protocol — E-RZ103 (https://developers.cloudflare.com/artifacts/api/git-protocol/)
- Remote: `https://<ACCOUNT_ID>.artifacts.cloudflare.net/git/<namespace>/<repo>.git` (prefer the `remote` value returned by API).
- Auth: Bearer via `http.extraHeader`, or basic-auth with token in password slot (username ignored). Token format `art_v1_<40 hex>?expires=<unix>`; expiry embedded in token string.
- Scopes: `read` = clone/fetch/pull; `write` = + push. Push requires write.
- **Limitations: push is smart-HTTP v1 only ("Artifacts does not support v2 receive-pack"); v2 only for clone/fetch (ls-refs, fetch); v1 caps `filter`/`include-tag` unsupported → no partial clone.**
- Red-team note: standard git CLI negotiates v1 push fine, but wrappers on libgit2/isomorphic-git/JGit must be tested against v1 receive-pack before we standardize on them for agents.

## Events — E-RZ105 (https://developers.cloudflare.com/artifacts/guides/event-subscriptions/)
- Account-level (source `artifacts`): `repo.created`, `repo.deleted`, `repo.forked` (source+target identified), `repo.imported` (sourceUrl, branch).
- Repo-level (source `artifacts.repo`, scoped by namespace+repo_name): `pushed` (ref, before/after SHAs, commit list with author/committer/parents, `totalCommitsCount`, truncation flags `messageTruncated`/`commitsTruncated`), `cloned`, `fetched` (empty payload), `token.created` (tokenId, scope, expiresAt), `token.revoked`.
- Full names `cf.artifacts.repo.<event>`, e.g. `cf.artifacts.repo.pushed`. Delivery via Cloudflare Queues event subscriptions; consumed by a Worker. Schema version 1.
- Docs' own suggested use cases include "Trigger a review agent on each push" — native trigger for claim arbitration/review automation, no polling.
- UNKNOWN (not stated): delivery guarantees (at-least-once? ordering?), quotas — check Queues docs before relying.

## Platform model — E-RZ107 (https://developers.cloudflare.com/artifacts/concepts/how-artifacts-works/)
- Repo = "isolated Git service with its own remote URL, tokens, and durable state"; single logical instance routed globally (DO-like); synchronous cross-DC replication + async object-storage copies + snapshots.
- Namespace created implicitly on first repo; namespace+repo = stable address; responses include repo ID.
- Access control is repo-scoped read/write tokens only; "Token minting is left to the developer's Worker or API layer, keeping authz outside the repo." No visibility settings, no user/role management documented.
- No branch/merge/PR operations documented anywhere on concepts page.

## Limits — E-RZ104 (https://developers.cloudflare.com/artifacts/platform/limits/)
- Control-plane: 2,000 req/10 s/namespace. Git: 2,000 req/10 s per artifact.
- Max 1 GB storage/repo; 32 MB max file/blob; 1 TB/account (raisable); repos and namespaces unlimited.

## Pricing — E-RZ108 (https://developers.cloudflare.com/artifacts/platform/pricing/)
- Workers Paid plan **required**; free plan: unavailable.
- "Cloudflare will begin billing for Artifacts operations and storage on **October 14, 2026**." ⚠️ Blog post said Oct 15 (E-C008) — one-day discrepancy between marketing blog and pricing doc; assume docs authoritative; flag to principal.
- Operations: first 10,000/month included, then $0.15 per additional 1,000. Storage: first 1 GB-month included, then $0.50/GB-mo (peak-daily average). Ops counted per create/push/pull/clone. Replication free; repos persist until deleted.

## What the platform does NOT give us (negative space, cross-checked across fetched pages)
1. **No merge, branch-CRUD, diff, or PR object anywhere in the fetched surface.** Branches still work via git refs (push/fetch handle them), but merges must be performed by git clients or our own Worker/agent layer. Every "merge train"/"semantic merge"/"auto-integration" approach owns this cost.
2. **No path- or branch-scoped tokens** — only repo-level read/write. Path-level write policies (seed 11) need a proxy Worker; repo-per-agent isolation is the native primitive.
3. **No public/anonymous access model** — every consumer needs a token we mint. Public browsing/cloning for users requires us to mint+serve (or proxy). Impacts "ease of use" axis for reviewers trying the demo.
4. No webhook delivery except via Queues; no built-in CI/CD beyond the separate Workers Builds git-integration.

## Feasibility deltas vs codex-feasibility open questions (cross-check, read-only)
1. "Private/permission-scoped previews suspected public-by-default" → Artifacts has no URL-serving/preview concept at all in fetched docs; previews only via separate Workers Builds integration. Design-avoid: per-agent repos + short-TTL write tokens.
2. Stale-base detection: feasible natively (fork base commit vs upstream head via `/log`/`readCommit`; fork event).
3. Provenance receipts: no metadata store on repos → side repo (≤1 GB, ≤32 MB/file caps), KV, or DO.
4. Scale check for demo: 2,000 git req/10 s and unlimited repos comfortably cover N concurrent agents for a 5-10 min demo; cost within free tier of pricing.
