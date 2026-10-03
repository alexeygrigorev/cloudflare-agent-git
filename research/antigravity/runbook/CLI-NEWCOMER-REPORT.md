# CLI Quickstart Runbook & Newcomer End-to-End Verification (C1470/C1474)

Executor: muse-cli-runbook · workspace `/home/alexey/git/ab-readme` · branch `proto/readme`
Date: 2026-10-04 (UTC) · CONTRACT v0.1.2 (`prototype/CONTRACT.md`)

Zero-assumptions premise: a newcomer with node/npx, python3, git, rsync —
nothing else pre-installed, no tokens, no running servers.

## 1. Commands tested (all from a clean terminal)

### 1.1 Offline / install path

| # | Command | Result | Time |
| --- | --- | --- | --- |
| 1 | `python3 agent-branches --help` (+ `task/push/status/ack/checks --help`) | PASS — all five subcommands render | <1 s |
| 2 | `python3 -m radar --help` | PASS — includes `--l1` (CONTRACT v0.1 payload export) | <1 s |
| 3 | `cd prototype && npm install` | PASS — 0 vulnerabilities (warm cache: 3.1 s) | 3.1 s |
| 4 | `npm run typecheck` (`tsc --noEmit`) | PASS, clean | 2.2 s |
| 5 | `npm test` (vitest worker suites, workerd + real-git sidecar) | PASS — **12 files, 67/67 tests** | 34.5 s |
| 6 | `npm run test:sidecar` | PASS — **16/16** | 1.7 s |
| 7 | `python3 -m pytest tests/test_client.py -q` (L2 client vs mock L1) | PASS — **10/10** | 7.9 s |
| 8 | `python3 -m pytest tests/test_radar_engine.py -q` | PASS — **16/16** | 8.6 s |
| 9 | `export_l1_payload(...)` shape check | PASS — keys `contract/vector/policy/coverage/results`, `contract == "0.1"` | <1 s |

### 1.2 Live smoke: sidecar + worker + full endpoint sequence

Fresh throwaway tokens, ports 8799/8787 (verified free first; peer ports
8797/8798 untouched). Servers started with `setsid … </dev/null`, killed
afterwards (TERM, then the orphaned `workerd` child by exact PID+cmdline —
killing only the wrangler parent leaves the port held; cf. live G1).

| # | Command | Result | Time |
| --- | --- | --- | --- |
| 10 | sidecar start + `GET /api/health` (bearer) | PASS — `{"ok":true,"repos":0}` | ~2 s boot |
| 11 | `wrangler dev --local --port 8787` (+4 `--var` tokens/URLs) | PASS — `Ready on http://localhost:8787` | ~12 s boot |
| 12 | `POST /setup` (admin bearer) | PASS — canonical `agent-branches-canonical-9b830c6f`, seedCommit returned | 0.06 s |
| 13 | `POST /tasks` `{"agent":"smoke","intent":"…"}` (admin) | PASS — task-0001/smoke-0001, fork remote, `base_sha`, 1 h `token.plaintext` | 0.08 s |
| 14 | `POST /events/push` **without** bearer | PASS (negative) — **401** `bearer token required` | — |
| 15 | anonymous `git clone` of fork | PASS (negative) — rejected (`No such device`, auth required on every git endpoint; cf. live G2) | — |
| 16 | authenticated clone + empty commit + `git push` with task token (`http.extraHeader`, `GIT_TERMINAL_PROMPT=0`) | PASS — push exit 0; head advances only after step 17 (hook has no `SIDECAR_NOTIFY_URL` → documented local no-worker mode, correctly *not* recorded as unprocessed) | — |
| 17 | manual `POST /events/push` `{"agent","sha"}` with **agent token** | PASS — `accepted:true, deduped:false`, head advanced, pushes=1 | 0.05 s |
| 18 | `POST /events/push` for agent A with agent B's token | PASS (negative) — **403** `token belongs to other-0002, not smoke-0001` | — |
| 19 | `POST /checks` canonical 0.1 payload (RUNNER_TOKEN) | PASS — `stale:false, accepted:1`, pair view keyed by agentId, `status:unknown` | — |
| 20 | `POST /checks` without `contract` | PASS (negative) — **400** names expected `"0.1"`/`"0.0"` | — |
| 21 | `POST /checks` with wrong runner token | PASS (negative) — **401** | — |
| 22 | `POST /checks` with stale vector (valid shape) | PASS (negative) — **409** + `currentHeads` | — |
| 23 | `POST /warnings/:id/ack` L2-client shape `{action,task_id}`, no `agent` | PASS (negative, documents L2 gap) — **400** `agent is a required string` | — |
| 24 | `GET /tasks/task-0001` | PASS — taskId/agentId/base_sha/intent/head/pushes all present | — |
| 25 | `GET /status` | PASS — agents, heads, pairs, warnings, radarLog, lastRunnerReport, unprocessedPushes | — |

Full `live/run-demo.sh` was **not** re-executed (run-3 evidence stands
committed at 36/36; a full re-run needs headless Chrome + ~10 min and would
collide with peer demo ports). Every primitive the script chains (setup,
tasks, authed pushes, verbatim 0.1 `/checks`, 409 replay, status/UI reads)
is covered above against the same CONTRACT.

## 2. Doc updates made in this pass

1. **`README.md`** — added the missing newcomer quickstart (was 11 lines with
   no run instructions): full demo path (`proto/live` + `live/run-demo.sh`),
   prototype dev/test loop with verified timings, L2 CLI + radar matrix
   commands, auth-token rules, and doc pointers including CONTRACT v0.1.2.
2. **`live/README.md`** — fixed stale hardcoded path
   `cd /home/alexey/git/agent-branches-live` → repo-root-relative `cd`
   (that worktree path does not exist for a newcomer; SUBMISSION.md already
   uses the portable form).
3. **`docs-submission/DEMO-SCRIPT.md`** — Scene 3 invocation ran the demo
   backgrounded (`… &`), contradicting the canonical foreground form in
   `live/README.md` and `SUBMISSION.md` (backgrounding also breaks the
   `echo "exit=$?"` beat). Now foreground.

## 3. Discrepancies found but NOT edited (out of scope — flagged)

1. **`prototype/README.md:16`** still cites CONTRACT **0.1.1** (actual 0.1.2),
   and its §Run `/checks` curl posts the legacy string-`policy` shape with no
   `contract` field → **400s** against the current worker (verified §1 #20).
   Owned by antigravity-head (`prototype/**`) — needs an L1-lane fix.
2. **`prototype/.dev.vars.example:8`** comment cites CONTRACT 0.1.1 (cosmetic).
3. **L2 client `agent_branches/` vs CONTRACT (functional, needs owner call):**
   - `push` sends **no `Authorization` header** (`client.py:244`) and the CLI
     has no `--token` flag → **401** against any secrets-configured worker
     (verified §1 #14). Extra fields (`agentId/head_sha/files_changed/…`)
     are tolerated (worker reads `body.agent`/`body.sha`), so auth is the
     only blocker.
   - `ack` sends `{action,task_id}` without required `agent` (`client.py:258`)
     and no auth; CLI has no `--agent`/`--note` flags → **400** (verified
     §1 #23), then 401 even if fixed.
   - `task create` sends undocumented `repo`/`branch` keys (ignored by worker,
     harmless) and only sends `agent` with `--agent`; auth path
     (`--admin-token`/`$ADMIN_TOKEN`) is correct.
   - `checks` is contract-correct (client-side `contract/vector/results`
     validation + `--runner-token`/`$RUNNER_TOKEN`).
   Suggested: add bearer auth to `push`/`ack` (+ `--token`/`$AGENT_TOKEN`
   plumbing) and `{agent,note}` to `ack`. Relevant to active zcode-l2-client
   lane — deconflict before touching.

## 4. Timing summary (newcomer budget)

Install 3 s (warm cache; cold ≈ wrangler/workerd download) · typecheck 2 s ·
worker suite 35 s · sidecar suite 2 s · L2 offline 8 s · radar engine 9 s ·
live smoke ≈ 3 min incl. server boots. Full `npm run test:all` green.

## 5. Reproduction notes

Throwaway tokens only (`t-*-smoke01`); never committed. Smoke state lived in
`/tmp` (sidecar root, clone, payloads) and was removed; demo ports verified
free before and after (orphaned workerd killed by exact PID after cmdline
check — peer `8797/8798` and `agent-branches-l1` processes untouched).
