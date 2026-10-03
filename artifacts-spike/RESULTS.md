# artifacts-spike RESULTS — real Cloudflare Artifacts, 2026-10-03

Executor: zc-artifacts-1 (parent: claude-principal). Worktree proto/artifacts-spike.
Scope: artifacts-spike/ only. Docs read first: prototype/docs-notes.md + freshly fetched official
pages in docs/ (wrangler, REST API, authentication, git-protocol, workers-binding; fetched 2026-10-03).

## Verdict

**STEP 1: PASS** — all task items (a)–(f) completed against the real service using only documented
APIs. STEP 2 plan written (PLAN-L1-REAL.md). Total billable ops: **28 evidenced** (budget < 100) — the
reported 29th op (the O29 hygiene revoke) was **not captured**; see ledger row O29. Storage: 3 repos
(~KB scale); `objects:15` is evidenced for the two forks only (O9/O10) — the canonical repo's object
count was never captured. Nothing deployed; no resources beyond the listed ones.

## Ops ledger (1 op = 1 REST call, 1 wrangler invocation, or 1 git network command)

| # | Op | Route / command | Result | Latency (ms) |
|---|----|-----------------|--------|--------------|
| O1 | ns get guard | GET namespaces/agent-branches-dev | 404 code 10200 (absent) | 1178 (cold) |
| O2 | create namespace | POST /artifacts/namespaces | 201 created | 1116 |
| O3 | verify namespace | GET namespaces/agent-branches-dev | 200, repo_count 0 | 181 |
| O4 | create repo | POST .../agent-branches-dev/repos `demo-canonical` | 200, id u7usp14xkllei2on, remote+token returned | 3046 |
| O5 | mint git credential | POST .../tokens `{repo, scope:write, ttl:3600}` | id e78473…, expires_at +1h exactly | 179 |
| O6 | refs of empty repo | `git ls-remote` demo-canonical | exit 0, empty output | 970 |
| O7 | push base commit | `git push` orphan commit (ff4decd:demo-target tree, no .harness) → main | `[new branch] main -> main` | 416 |
| O8 | verify head | `git ls-remote` | HEAD == refs/heads/main == b4346112… | 269 |
| O9 | fork 1 | POST .../repos/demo-canonical/fork `demo-agent-1` (default_branch_only) | 200, objects:15, remote+token | 4486 |
| O10 | fork 2 | POST .../repos/demo-canonical/fork `demo-agent-2` | 200, objects:15 | 3396 |
| O11 | fork status | GET repos/demo-agent-1 | 200 immediately, source provenance, no status field on single GET | 134 |
| O12 | fork status | GET repos/demo-agent-2 | 200 immediately | 118 |
| O13 | fork head | GET .../repos/demo-agent-1/log?ref=main&limit=1 | hash == base b4346112… | 172 |
| O14 | clone fork | `git clone` demo-agent-1 (write token via header) | exit 0, HEAD b4346112… | 500 |
| O15 | push 1-line change | commit + `git push origin main` | b434611..c809475 main -> main | 346 |
| O16 | read back head | GET .../repos/demo-agent-1/log?ref=main&limit=1 | hash == local HEAD c809475… (**MATCH**) | 130 |
| O17 | list repos | GET .../repos?limit=50&sort=name | 3 repos, all `"status":"ready"` | 450 |
| O18 | refs fork | `git ls-remote` demo-agent-1 | HEAD + refs/heads/main @ c809475… | 218 |
| O19 | refs canonical | `git ls-remote` demo-canonical | HEAD + refs/heads/main @ b4346112… | 348 |
| O20 | CLI cross-check | `wrangler artifacts namespaces list --json` (wrangler 4.147.0, env auth) | agent-branches-dev, repo_count 3 | 1092 |
| O21 | CLI cross-check | `wrangler artifacts repos list --namespace agent-branches-dev --json` | 3 repos, matches REST incl. status | 1082 |
| O22 | list tokens | GET .../repos/demo-canonical/tokens?state=all | 2 active (minted 1h + initial 24h), scope/state/expires_at | 207 |
| O23 | revoke unused | DELETE .../tokens/{initial canonical token} | 200 `{id}` | 267 |
| O24 | list tokens f2 | GET .../repos/demo-agent-2/tokens?state=all | 1 active | 238 |
| O25 | revoke unused | DELETE .../tokens/{demo-agent-2 initial} | 200 `{id}` | 217 |
| O26 | mint read token | POST .../tokens `{scope:read, ttl:600}` | id jni5lv… only — no `expires_at` captured; +10min honoring **UNVERIFIED** | 197 |
| O27 | negative: push with read token | `git push` (read token) | **rejected: HTTP 400**, exit 128, 52ms — no objects landed | 52 |
| O28 | revoke read token | DELETE .../tokens/jni5lv… | 200 `{id}` | 218 |
| O29 | hygiene revoke | DELETE .../tokens/{canonical minted write token} | **NOT CAPTURED** — executor-reported 200 `{id}`, but no transcript line or raw capture exists; treat as UNVERIFIED | (not captured) |

Two claims above were re-derived after independent review because they depended on the uncaptured O29:
"all unused tokens revoked" (see Resources section) and the revoke-route validation cited in
PLAN-L1-REAL.md §5.2 (only O28 is evidenced). One local-only failure never reached the network (the
transcript's `[O6 ls-remote-empty ms=4] fatal: bad config line 1` — bad git-include file syntax on the
first O6 attempt, fixed by writing a proper `[http] extraHeader` INI include; not counted as an op).

## Assumption scorecard (docs-notes.md ASSUMED A–F)

| Assumption | Verdict | Evidence |
|---|---|---|
| A — no control-plane ref enumeration; head via log(limit:1); refs via git only | **CONFIRMED** | REST has no refs route (full REST page reviewed); O13/O16 log(limit:1) works; O18/O19 ls-remote is the only ref listing |
| B — CommitMetadata fields {id, message, timestamp(ISO), parents} | **DIFFERENT (REST)** | Real REST log returns `{hash, treeHash, message, author{name,email}, committer{name,email}, parents[], authoredAt, committedAt}` — `hash` not `id`, epoch-seconds `authoredAt`/`committedAt` not ISO `timestamp` (O13/O16). Binding type still unverified — must run `npx wrangler types` after adding the binding. RealArtifacts.log/headCommit read `.id` — will be wrong against REST shapes; pending binding-type check |
| C — createToken result carries scope | **CONFIRMED** | O5 mint returns `{id, plaintext, scope, expires_at}`; O22 list shows scope/state |
| D — DO in same Worker sees env.ARTIFACTS binding | **UNVERIFIED** | No Worker deployed (out of scope); requires binding config + deploy step |
| E — event subscription wiring unknown | **UNVERIFIED** | Not exercised (needs a Worker/webhook target); documented envelope unchanged |
| F — no fork-at-commit; fork default branch only | **PARTIAL** | Fork body accepts only name/description/read_only/default_branch_only (REST page + O9/O10); fork head == source default-branch head (O13); `objects:15` copied (fork response). **UNVERIFIED:** the fork response never echoes `default_branch_only`, and no pre-push ref listing of demo-agent-1 was captured — "fork copies only the default branch" is inferred, not directly evidenced |

## Additional findings (not in docs-notes)

1. **Token format DIFFERENT from docs**: real service issues `art_v2_x_<40 hex>?expires=<unix>`, not
   the documented `art_v1_<40 hex>`. Anything validating the `art_v1_` prefix will reject real tokens.
   Token **shape** is recorded as a structural attestation line at the end of appendix-transcript.md
   (`art_v2_x_` + 40-hex elided + `?expires=<epoch seconds>`) — whole tokens were redacted at capture
   time, so the prefix is not recoverable from the transcript itself. The `?expires=` suffix convention
   is confirmed for captured cases (create/fork tokens +24h via O22/O24; minted ttl honored 3600→+1h
   via O5/O22); `ttl=600` honoring is **UNVERIFIED** (O26 captured only the token id, no `expires_at`).
2. **`status` field only on LIST**: `GET /repos` (list) includes `"status":"ready"`; single `GET /repos/:name`
   omits it (docs' RepoInfo type has no status). Forks were immediately `ready`/GET-200 at ~2s after
   fork POST — no 409 "forking" window observed at this size. Port note: don't poll single-GET for status.
3. **`last_push_at` stays `null`** even after successful pushes (observed in O17/O21 after O7/O15).
   Don't rely on it for activity signals; use log(limit:1) or push events.
4. **Read-scope enforcement returns HTTP 400** (not 401/403) on receive-pack; fast fail (52ms), nothing written.
   Port error mapping should treat 4xx-on-push as auth/scope failure.
5. **Namespace-not-found error**: code `10200` "Namespace not found" with 404 — same numeric code family
   as the docs' "File not found" example; useful for NOT_FOUND mapping.
6. **Wrangler CLI**: `artifacts namespaces list` and `artifacts repos list` work headless with
   `CLOUDFLARE_API_TOKEN`/`CLOUDFLARE_ACCOUNT_ID` env (wrangler 4.147.0 from L1's node_modules, no
   install) — that is all this spike exercised (O20/O21). **UNVERIFIED:** the `list`'s sibling `get`
   subcommands were never run, and no `--help` capture supports any claim about create/fork
   subcommands existing or not. Treat namespace create and fork as REST-only (the validated path)
   until a `--help`/`get` capture lands.
7. **Auth mechanics**: Bearer repo token via `http.extraHeader` works for clone/fetch/push. To keep tokens
   out of argv and URLs, this spike persisted the header in a 0600 git-include file referenced via
   `-c include.path=<file>` — viable pattern for L1's git-sidecar scripts. Basic-auth-in-URL (documented
   alternative) not used per task rules.
8. **Latencies**: control-plane reads 120–450ms; repo create 3.0s; forks 3.4–4.5s; git clone 500ms,
   push 350–420ms, ls-remote 220–970ms (first call includes TLS setup). Comfortably within the demo's
   5–10 min video budget.
9. **Fork response carries a full write token + remote** — convenient for agent handoff, but it means
   every fork creation mints a live 24h write secret; the coordinator side must store/revoke it deliberately
   (this spike revoked all unused ones; revocation is a single documented DELETE).

## Resources left in place (for the next step; tiny)

- Namespace `agent-branches-dev` (created 2026-10-03T16:57:42Z, unrestricted, repo_count 3)
- Repo `demo-canonical` (id u7usp14xkllei2on) — main @ b4346112… (orphan base commit; demo-target
  subtree of cloudflare-agent-git ff4decd; **no .harness**)
- Repo `demo-agent-1` (id z23vslwndyq9lz2b, fork of demo-canonical) — main @ c809475… (1-line README change)
- Repo `demo-agent-2` (id nzhkzbxleu7eyjds, fork of demo-canonical) — main @ b4346112…, untouched
- Active tokens remaining: demo-agent-1 write token (24h TTL — now **measured**, not assumed: read-only
  `GET .../repos/demo-agent-1/tokens?state=all` on 2026-10-03 returned exactly one active write token,
  id i8ppt364o5tsgguf, created 2026-10-03T17:00:33.909Z, expires_at 2026-10-04T17:00:33.909Z, i.e.
  +24h exactly; stored 0600 outside git). Needed for the next step; revoke at/after use — see the
  cleanup gate item (PLAN-L1-REAL.md §5.9).
- Token revocations evidenced in the transcript: O23/O25/O28. The O29 revoke (canonical minted write
  token) is executor-reported but **not captured** — treat that token as possibly live until the
  cleanup gate item verifies it (same read-only list call against demo-canonical).

### Later cleanup checklist — promoted to a dated gate item

Tracked as **PLAN-L1-REAL.md §5.9** (owner: claude-principal lane; due 2026-10-07, before the Oct-14
billable-ops switchover; hard prerequisite for any public deploy or recorded demo). Checklist retained
here for the concrete steps:

- DELETE repos demo-agent-1, demo-agent-2, demo-canonical (`DELETE .../repos/:name`, returns 202)
- DELETE namespace agent-branches-dev (verify route availability; if absent, deleting repos empties it)
- Revoke demo-agent-1 token (id in ~/.config/cloudflare/artifacts-spike-demo.env)
- Remove local 0600 files: ~/.config/cloudflare/artifacts-spike-demo.env,
  ~/.config/cloudflare/.artifacts-rest-header, ~/.config/cloudflare/.artifacts-git-header-f1
- Remove /tmp/artbase.h3nZeB, /tmp/artfork1.clone, /tmp/artifacts-spike-*.txt/path

## Security handling during this spike

- API token only ever passed via curl `--header @0600-file` (never argv/URL/env-dump); repo tokens only
  via 0600 git-include files. GIT_TERMINAL_PROMPT=0 everywhere.
- All evidence passed artifacts-spike/redact.py before persisting. First pass missed the real
  `art_v2_x_` prefix (docs said `art_v1_`) — caught in review, redactor generalized, transcript
  re-redacted and re-scanned (0 live-token patterns). The executor reports the one still-useful exposed
  token was revoked as hygiene (O29), but **that call was not captured** — the cleanup gate item
  (PLAN-L1-REAL.md §5.9) verifies it via the read-only token list and revokes if still live.
  Local /tmp scratch and throwaway clones removed at cleanup time.
- Commit gate before each commit: `git diff --cached | grep -iE 'token|secret|bearer'`.

## Full sanitized transcript

See appendix-transcript.md (redacted with the generalized redactor; zero live-token patterns).
