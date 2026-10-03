# Cloudflare Artifacts — documented API notes (fetched 2026-10-03)

Raw HTML fetched with curl into `docs/*.md`; extracted text in `docs/*.txt`.
Only shapes below are used in code. Anything not shown in these five pages is marked ASSUMED.

## Sources

1. Workers binding API — https://developers.cloudflare.com/artifacts/api/workers-binding/
2. Git protocol — https://developers.cloudflare.com/artifacts/api/git-protocol/
3. Event subscriptions guide — https://developers.cloudflare.com/artifacts/guides/event-subscriptions/
4. Limits — https://developers.cloudflare.com/artifacts/platform/limits/
5. Best practices — https://developers.cloudflare.com/artifacts/concepts/best-practices/

## Binding configuration (source 1)

Wrangler config (JSON):

```json
{
  "artifacts": [
    { "binding": "ARTIFACTS", "namespace": "default" }
  ]
}
```

TOML form adds optional `remote = true` to use the remote Artifacts service in
local dev. Wrangler ≥ 4.145.0 recommended for generated types / Blob methods.
`npx wrangler types` generates the authoritative `Artifacts` type into
`worker-configuration.d.ts`; `Env` then contains `ARTIFACTS: Artifacts`.

## Namespace methods on env.ARTIFACTS (source 1)

- `create(name, opts?)` → `Promise<ArtifactsCreateRepoResult>`
  - opts: `{ readOnly?: boolean; description?: string; setDefaultBranch?: string }`
  - result includes `name`, `remote`, `defaultBranch`, and an initial `token`.
- `get(name)` → `Promise<ArtifactsRepo>` — a **disposable repo capability**
  (implements Disposable; docs recommend `using repo = await artifacts.get(name)`).
  Metadata is NOT on the handle; call `repo.info()`.
- `list(opts?)` → `Promise<ArtifactsRepoListResult>` with `repos: [{name, status}]`
  (status: `ready | importing | forking`) and `cursor`.
- `import(params)` → source `{url, branch?, depth?}`, target `{name, opts?}` →
  `ArtifactsCreateRepoResult`.
- `delete(name)` → `Promise<boolean>`.

## Repository capability methods (source 1)

- `info()` → `Promise<ArtifactsRepoInfo>` (throws NOT_FOUND if deleted).
- `createToken(scope?, ttl?)` → `Promise<ArtifactsCreateTokenResult>` —
  scope `"read" | "write"` (default `"write"`), ttl seconds. Returns structured
  result with `plaintext` and `expiresAt`; `plaintext` is the Git token string.
- `listTokens()` → `{ total, tokens }`.
- `revokeToken(tokenOrId)` → `Promise<boolean>`.
- `fork(name, opts?)` on the repo handle → `Promise<ArtifactsCreateRepoResult>`;
  opts `{ description?, readOnly?, defaultBranchOnly? }`. New repo name is the
  first argument.
- `log(opts?)` → `Promise<ArtifactsCommitMetadata[]>` — opts `{ref = "HEAD",
  limit = 50 (max 1000), offset = 0}`; first-parent chain, newest first;
  unresolvable ref → empty array.
- `readCommit(hash)` → `ArtifactsCommitMetadata | null`.
- `readTree(hash)` → `ArtifactsTreeEntry[] | null` (immediate children only).
- `readBlob(hash)` → untyped `Blob | null`.
- `readFile({ref, path})` → MIME-typed `Blob | null` (throws INVALID_INPUT on
  empty ref/path).

## Git remote + auth (source 2)

- Smart HTTP remote: `https://<ACCOUNT_ID>.artifacts.cloudflare.net/git/<namespace>/<repo>.git`.
  Use the exact hostname from the returned `remote`.
- Auth: Bearer token via `git -c http.extraHeader="Authorization: Bearer $TOKEN"`,
  or Basic-auth URL `https://x:<token-secret>@<host>/...` (username ignored).
- Token format: `art_v1_<40 hex>?expires=<unix_seconds>`.
- Protocol: upload-pack v1+v2 (clone/fetch); receive-pack **v1 only** (push);
  some optional v1 capabilities (filter, include-tag) unsupported.

## Push event shape (source 3, repository-level `artifacts.repo` source)

```json
{
  "type": "cf.artifacts.repo.pushed",
  "source": { "type": "artifacts.repo", "namespace": "...", "repoName": "..." },
  "payload": {
    "ref": "refs/heads/main",
    "before": "<40-hex>",
    "after": "<40-hex>",
    "commits": [
      { "id": "<40-hex>", "message": "...", "messageTruncated": false,
        "timestamp": "ISO", "author": {"name","email"},
        "committer": {"name","email"}, "parents": ["<40-hex>"] }
    ],
    "totalCommitsCount": 1,
    "commitsTruncated": false
  },
  "metadata": { "accountId", "eventSubscriptionId", "eventSchemaVersion", "eventTimestamp" }
}
```

Other events (account-level `artifacts` source): `repo.created`, `repo.deleted`,
`repo.forked`, `repo.imported`; repo-level: `cloned`, `fetched`,
`token.created` (payload `{tokenId, scope, expiresAt}`), `token.revoked`.

## Limits (source 4)

- Control plane: 2,000 req / 10 s per namespace; Git: 2,000 req / 10 s per artifact.
- 1 GB per repository; 32 MB max blob; 1 TB per account; unlimited repos/namespaces.
- Names: 2–63 chars (`[A-Za-z0-9][A-Za-z0-9._-]*` pattern for namespace+repo names).

## Best practices (source 5)

- One repo per agent/session ("if you have 10,000 agents, create 10,000 repos");
  unique names like `${agentName}-${sessionId}-${repoName}`; do not share one
  repo as an agent queue.
- Fork from a stable reviewed baseline (`defaultBranchOnly: true`).
- Least-privilege tokens: `read` for clone/review, `write` only for the pusher,
  short TTLs, re-mint per session.
- Git notes (`refs/notes/*`) for prompts/harness metadata; push notes refs too.

## ASSUMED (not in the five fetched pages — flagged, avoided, or synthesized locally)

- **ASSUMED-A (listRefs)**: no documented binding method lists refs. Our port
  exposes `log()` (documented) plus a `listRefs()` convenience that
  `RealArtifacts` refuses (`UNSUPPORTED`) and only `LocalArtifacts` serves;
  ref state in real mode must be tracked from push events instead.
- **ASSUMED-B (ArtifactsCommitMetadata fields)**: the binding page names the
  type but not its fields. We assume the push-event commit shape
  (`id`, `message`, `timestamp`, `parents`, optional `author`/`committer`) —
  the event page documents exactly those fields. Verify with
  `npx wrangler types` when a binding exists.
- **ASSUMED-C (ArtifactsCreateTokenResult.scope)**: docs show `plaintext` and
  `expiresAt`; `scope` is assumed present (best-practices example reads
  `token.scope`, so this is well-grounded).
- **ASSUMED-D (DO visibility of the binding)**: the Artifacts binding is
  configured worker-wide; we assume a Durable Object in the same Worker can
  read `env.ARTIFACTS`. Generated `Env` typing applies to DO env the same way.
- **ASSUMED-E (event delivery)**: the guide shows event shapes but we did not
  verify how a subscription is created (dashboard/API). Our `/events/artifacts`
  route accepts the documented envelope; wiring the subscription is a
  switch-to-real step.
