# artifacts-spike RESULTS — real Cloudflare Artifacts, 2026-10-03

Executor: zc-artifacts-1 (parent: claude-principal). Worktree proto/artifacts-spike.
Scope: artifacts-spike/ only. Docs read first: prototype/docs-notes.md + freshly fetched official
pages in docs/ (wrangler, REST API, authentication, git-protocol, workers-binding; fetched 2026-10-03).

## Verdict

**STEP 1: PASS** — all task items (a)–(f) completed against the real service using only documented
APIs. STEP 2 plan written (PLAN-L1-REAL.md). Total billable ops: **29** (budget < 100). Storage:
3 repos, 15 objects each (~KB scale). Nothing deployed; no resources beyond the listed ones.

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
| O25 | revoke unused | DELETE .../tokens/{demo-agent-2 initial} | 200 `{id}` | 218 |
| O26 | mint read token | POST .../tokens `{scope:read, ttl:600}` | id jni5lv…, +10min expiry | 197 |
| O27 | negative: push with read token | `git push` (read token) | **rejected: HTTP 400**, exit 128, 52ms — no objects landed | 52 |
| O28 | revoke read token | DELETE .../tokens/jni5lv… | 200 `{id}` | 218 |
| O29 | hygiene revoke | DELETE .../tokens/{canonical minted write token} | 200 `{id}` (canonical push done; least privilege) | 575 |

Two local-only failures never reached the network (bad git-include file syntax on first O6 attempt —
fixed by writing a proper `[http] extraHeader` INI include; not counted as ops).

## Assumption scorecard (docs-notes.md ASSUMED A–F)

| Assumption | Verdict | Evidence |
|---|---|---|
| A — no control-plane ref enumeration; head via log(limit:1); refs via git only | **CONFIRMED** | REST has no refs route (full REST page reviewed); O13/O16 log(limit:1) works; O18/O19 ls-remote is the only ref listing |
| B — CommitMetadata fields {id, message, timestamp(ISO), parents} | **DIFFERENT (REST)** | Real REST log returns `{hash, treeHash, message, author{name,email}, committer{name,email}, parents[], authoredAt, committedAt}` — `hash` not `id`, epoch-seconds `authoredAt`/`committedAt` not ISO `timestamp` (O13/O16). Binding type still unverified — must run `npx wrangler types` after adding the binding. RealArtifacts.log/headCommit read `.id` — will be wrong against REST shapes; pending binding-type check |
| C — createToken result carries scope | **CONFIRMED** | O5 mint returns `{id, plaintext, scope, expires_at}`; O22 list shows scope/state |
| D — DO in same Worker sees env.ARTIFACTS binding | **UNVERIFIED** | No Worker deployed (out of scope); requires binding config + deploy step |
| E — event subscription wiring unknown | **UNVERIFIED** | Not exercised (needs a Worker/webhook target); documented envelope unchanged |
| F — no fork-at-commit; fork default branch only | **CONFIRMED** | Fork body accepts only name/description/read_only/default_branch_only (REST page + O9/O10); fork head == source default-branch head (O13); `default_branch_only:true` worked, objects:15 copied |

## Additional findings (not in docs-notes)

1. **Token format DIFFERENT from docs**: real service issues `art_v2_x_<40 hex>?expires=<unix>`, not
   the documented `art_v1_<40 hex>`. Anything validating the `art_v1_` prefix will reject real tokens.
   The `?expires=` suffix convention is confirmed (create/fork tokens +24h; minted ttl honored: 3600→+1h, 600→+10min).
2. **`status` field only on LIST**: `GET /repos` (list) includes `"status":"ready"`; single `GET /repos/:name`
   omits it (docs' RepoInfo type has no status). Forks were immediately `ready`/GET-200 at ~2s after
   fork POST — no 409 "forking" window observed at this size. Port note: don't poll single-GET for status.
3. **`last_push_at` stays `null`** even after successful pushes (observed in O17/O21 after O7/O15).
   Don't rely on it for activity signals; use log(limit:1) or push events.
4. **Read-scope enforcement returns HTTP 400** (not 401/403) on receive-pack; fast fail (52ms), nothing written.
   Port error mapping should treat 4xx-on-push as auth/scope failure.
5. **Namespace-not-found error**: code `10200` "Namespace not found" with 404 — same numeric code family
   as the docs' "File not found" example; useful for NOT_FOUND mapping.
6. **Wrangler CLI**: `artifacts namespaces list/get` and `artifacts repos list/get` work headless with
   `CLOUDFLARE_API_TOKEN`/`CLOUDFLARE_ACCOUNT_ID` env (wrangler 4.147.0 from L1's node_modules, no install).
   No wrangler subcommands exist for namespace create or fork — those are REST-only.
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
- Active tokens remaining: demo-agent-1 write token (24h, needed for next step, stored 0600 outside git).
  All other tokens revoked (O23/O25/O28/O29).

### Later cleanup checklist (when the demo is torn down)

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
  re-redacted and re-scanned (0 live-token patterns), and the one still-useful exposed token was
  revoked (O29). Local /tmp scratch and throwaway clones removed at cleanup time.
- Commit gate before each commit: `git diff --cached | grep -iE 'token|secret|bearer'`.

## Full sanitized transcript

See appendix-transcript.md (redacted with the generalized redactor; zero live-token patterns).
