# Real Fork Adoption & Verification Report — C1470/C1474

- **Executor**: zcode-fork-adoption (ZCode/z.ai, head: antigravity-head)
- **Date of run**: 2026-10-04 01:43–01:50 CEST (2026-10-03T23:43–23:50Z)
- **Checkout**: `/home/alexey/git/agent-branches-adopt`, branch `proto/ab-adoption`, HEAD `a2055e3` at run start
- **Wire**: prototype CONTRACT.md **0.1.4** (no wire drift; all statuses/shapes matched the contract)
- **Stack under test (this checkout, not the L6 stack)**: `local-artifacts/sidecar.mjs` on 127.0.0.1:8793 (repos in `/tmp/ab-adoption-c1474/repos`) + local node:http coordinator `.build/node/src/local/main.js` (src/local core) on 127.0.0.1:8792, fresh state file, `RADAR_IMPL` default.
- **Scratch/evidence dir**: migrated to `/home/alexey/git/cloudflare-agent-git/.local/scratch/zcode-fork-adoption/` per C1487 (run-time location was `/tmp/ab-adoption-c1474/`; tokens redacted throughout)

## Verdict

**ADOPTION CONFIRMED.** A real executor drove the full Agent Branches workflow end to end with plain `curl` and a plain `git` client: task creation → fork + per-task write token → real source edit → real push → automatic post-receive webhook → coordinator state → trusted-runner check → clean pair. Every step returned the contract-specified status and payload. The one friction found (409 full-vector stale gate) is documented behavior and has a clean recovery flow, which the run exercised.

## Workflow steps, outputs, timing

| # | Step | Status | Duration | Key output |
|---|------|--------|----------|------------|
| T0 | `GET /status` baseline | 200 | 14.1 ms | empty heads; canonical auto-init `agent-branches-canonical-ed14c7b6` |
| T1 | `POST /setup` (ADMIN) | 201 | 2.1 ms | `created:false` (idempotent — already auto-initialized at T0) |
| T2 | `POST /tasks` agent A (ADMIN) | 201 | 61.2 ms | `task-0003`, fork remote, write token, `base_sha` |
| T3 | `POST /tasks` agent B (ADMIN) | 201 | 62.3 ms | `task-0004` |
| T4/T5 | `git clone` fork A/B (Bearer via `http.extraHeader`) | ok | — | clone HEAD == `base_sha`; seed file `README.md` = `agent-branches baseline` |
| T6 | Agent A edit + commit + `git push` | ok | — | commit `aea84ba402f0bea1de71348a4d14fe722add577c` |
| T7 | Agent B edit + commit + `git push` | ok | — | commit `d5bd65fa8aa015c7d0f242b0a9ffe4ba8c904ed8` |
| T8/T9 | `GET /tasks/task-0003` / `task-0004` | 200 | 1.7 / 0.9 ms | `pushes: 1`, head advanced, `testProvenance: null` |
| T10 | Cross-agent push report (B token → A agent) | **403** | — | `forbidden: this token belongs to zcode-adoption-b-0004, not zcode-adoption-a-0003` |
| T11 | `POST /checks` wrong bearer | **401** | — | `unauthorized: valid bearer token required (RUNNER_TOKEN)` |
| R1 | Runner fetches both forks; `git merge-base` | ok | — | merge-base `5c5531bd863b5bd1edda54c1e0491e4504157398` (== base_sha) |
| R2 | `git merge-tree --write-tree` A×B | clean | 6.5 ms | merged tree `5decddaef78b9ca8fe30e943e5821d1363e9f3b9` |
| R3 | Content assertions in merged tree | 2/2 ok | 13.0 ms | `ok 1 - README carries adoption note A` / `ok 2 - NOTES-adoption-b.md carries adoption note B` |
| T12 | `POST /checks` with 2-agent vector | **409** | 2.1 ms | stale gate (see "Findings") + `currentHeads` in error body |
| T14 | `POST /checks` with FULL 4-agent vector | **200** | 3.1 ms | `accepted: 1`, pair `clean`, runnerReport persisted |

## Concrete identifiers and payloads

Task creation response (T2, token truncated — `expiresAt` 2026-10-04T00:43:47Z, TTL 3600):

```json
{ "taskId": "task-0003", "agentId": "zcode-adoption-a-0003",
  "fork": { "name": "agent-branches-canonical-ed14c7b6-zcode-adoption-a-0003",
            "remote": "http://127.0.0.1:8793/git/agent-branches-canonical-ed14c7b6-zcode-adoption-a-0003.git" },
  "ref": "refs/heads/main",
  "base_sha": "5c5531bd863b5bd1edda54c1e0491e4504157398",
  "intent": "C1474 adoption: add adopted-file note from agent A",
  "token": { "scope": "write", "expiresAt": "2026-10-04T00:43:47.000Z",
             "plaintext": "art_v1_0e51ef1b…REDACTED" },
  "head": "5c5531bd863b5bd1edda54c1e0491e4504157398" }
```

Agent commits pushed to the fork remotes (authors: `zcode-fork-adoption (agent A/B) <zcode-fork-adoption@agents.local>`):

```
aea84ba402f0bea1de71348a4d14fe722add577c docs: adoption note A — real fork adoption run (C1474)   [README.md +1 line]
d5bd65fa8aa015c7d0f242b0a9ffe4ba8c904ed8 docs: adoption note B — independent fork edit for pair check (C1474)   [NOTES-adoption-b.md new file]
```

Push method (exactly as CONTRACT.md documents): `git -c http.extraHeader="Authorization: Bearer $TASK_TOKEN" push origin HEAD:main`. Post-push idempotency probe: re-push returned `Everything up-to-date` (rc 0). Coordinator recorded both pushes via the sidecar post-receive webhook automatically:

```json
{ "zcode-adoption-a-0003": { "head": "aea84ba402f0bea1de71348a4d14fe722add577c", "pushes": 1, "lastPushAt": "2026-10-03T23:45:35.512Z" },
  "zcode-adoption-b-0004": { "head": "d5bd65fa8aa015c7d0f242b0a9ffe4ba8c904ed8", "pushes": 1, "lastPushAt": "2026-10-03T23:45:35.765Z" },
  "unprocessedPushes": [] }
```

`unprocessedPushes: []` proves the silent-callback guard saw **no** lost deliveries — every push the agents made reached the coordinator through the real webhook path.

Trusted-runner check submission (T14, `POST /checks` with RUNNER_TOKEN, canonical contract `0.1`):

```json
{ "contract": "0.1",
  "vector": { "zcode-adoption-a-0001": "5c5531bd…", "zcode-adoption-b-0002": "5c5531bd…",
              "zcode-adoption-a-0003": "aea84ba4…", "zcode-adoption-b-0004": "d5bd65fa…" },
  "policy": { "merge": "git-merge-tree",
              "tests": { "command": ["bash","-c","grep -qx 'adoption note A …' README.md && grep -q 'adoption note B …' NOTES-adoption-b.md"], "budget_s": 15.0 } },
  "coverage": { "pairs_checked": 1, "tests_collected": 2 },
  "results": [ { "pair": ["zcode-adoption-a-0003","zcode-adoption-b-0004"],
                 "heads": { "zcode-adoption-a-0003": "aea84ba4…", "zcode-adoption-b-0004": "d5bd65fa…" },
                 "status": "clean", "kind": "test",
                 "evidence": { "summary": "git merge-tree --write-tree clean (merged tree 5decddae…, merge-base 5c5531bd…); 2/2 content assertions passed",
                               "files": ["README.md","NOTES-adoption-b.md"],
                               "test_output_tail": "ok 1 - README carries adoption note A\nok 2 - NOTES-adoption-b.md carries adoption note B",
                               "tests_collected": 2 } } ] }
```

Response: `{"stale": false, "accepted": 1, …}` — the (a-0003, b-0004) pair flipped to `clean` with the evidence object and per-pair `coverage: {"tests_collected": 2}` echoed back, and `lastRunnerReport` persisted verbatim (`checkedAt 2026-10-03T23:48:55.147Z`). `createdWarnings: []` (clean pair, correctly no warning).

## Findings

1. **409 stale-vector gate is full-map, by design.** The first check submission used a 2-agent vector (just the checked pair) and got 409 with the exact documented message plus `currentHeads` for recovery. `src/core/coordinator.ts:645` requires the vector to equal the entire heads map. Recovery (re-fetch `/status`, resubmit full vector) worked on the first try. Useful guidance for L3 runner authors: always build the vector from a fresh `GET /status`, never from memory.
2. **Per-task token scoping holds.** Agent B's valid token was rejected for agent A's push with a precise 403 naming both agent ids; the DO-only-SHA-256 design means the plaintext never appeared in any response after minting.
3. **Push → webhook → status latency is effectively zero** (pushes at 23:45:35.512/.765Z were visible in the immediately following `GET /status`, `unprocessedPushes: []`).
4. **Execution-environment anomaly (not a prototype bug):** the ZCode shell harness double-executed several of this run's commands, creating stray tasks `task-0001`/`task-0002` (0 pushes, parked at base) and making the first clone invocations report "destination already exists" while genuine clones existed. The prototype behaved correctly throughout; the canonical run used `task-0003`/`task-0004`. Future executors on this harness should write idempotent, guard-checked step scripts.
5. **Idempotency of the workflow:** re-running push and setup steps is safe (`Everything up-to-date`, `created:false`); task creation always mints a new fork.

## Automated regression coverage

`prototype/test/adoption.test.ts` (this commit) automates the loop for CI within the workerd lane: setup → two tasks with payload-integrity assertions (fork remote shape, ref, base==head, `art_v1_` write token) → real sidecar git commits on both forks → cross-agent 403 → agent-token push reports → heads/pushes verification → full-vector 0.1 check → pair `clean` → runner-token 401. Run result: **1 passed (868 ms)**, `npm run typecheck` (real `tsc --noEmit` from `node_modules/typescript`) clean — re-verified 2026-10-04 after C1487 flagged that the original bare `npx tsc` invocation had resolved a stub. The ordinary-git-client leg itself (clone/push over smart HTTP with bearer headers) is covered by `local-artifacts/*.test.mjs` and by this live run.

## Reproduction

```bash
cd /home/alexey/git/agent-branches-adopt/prototype
npm run build:node
SIDECAR_PORT=8793 SIDECAR_TOKEN=$ADMIN SIDECAR_ROOT=$SCRATCH/repos \
  SIDECAR_NOTIFY_URL=http://127.0.0.1:8792/events/push node local-artifacts/sidecar.mjs &
LOCAL_ARTIFACTS_URL=http://127.0.0.1:8793 LOCAL_ARTIFACTS_TOKEN=$ADMIN \
  ADMIN_TOKEN=$ADMIN RUNNER_TOKEN=$RUNNER PORT=8792 \
  COORDINATOR_STATE_FILE=$SCRATCH/state.json node .build/node/src/local/main.js &
# SCRATCH: use the assigned session scratch, e.g.
#   /home/alexey/git/cloudflare-agent-git/.local/scratch/zcode-fork-adoption  (not /tmp)
# then: POST /setup, POST /tasks, git -c http.extraHeader=… clone/edit/push, POST /checks
npx vitest run test/adoption.test.ts   # automated equivalent
```

## C1487 correction — 2026-10-04

Applied after codex-principal/antigravity-head review (aplexer `01a1042c…`, `01a1042e…`):

1. **Scratch migrated out of `/tmp`.** `/tmp/ab-adoption-c1474` was copied to `/home/alexey/git/cloudflare-agent-git/.local/scratch/zcode-fork-adoption/` and verified identical with `diff -rq` (exit 0; only harness session files are dest-only) before the `/tmp` copy was removed. No new `/tmp` allocations. The migration did not touch any evidence content — all hashes, payloads and timings in this report are unchanged.
2. **Typecheck claim corrected.** The original `npx tsc --noEmit` invocation resolved a stub and its banner was mistaken for a pass. Re-ran the project script: `npm run typecheck` (`tsc --noEmit`, real TypeScript from `node_modules/typescript`) exits 0 with no errors. The claim stands; the invocation is now recorded accurately.
3. **No result relabeling.** The reported run outputs (including the one exercised 409 stale-gate recovery) are the same actually-tested pair/source tree as committed in `fcd7985`; nothing was rerun against a different head and relabeled.
4. **Ownership ACK (disjoint).** Commit `fcd7985` touched exactly `prototype/test/adoption.test.ts` and `research/antigravity/adoption/REAL-FORK-ADOPTION-REPORT.md` (verified via `git show --stat`), disjoint from zcode-limiter-fix's declared scope `prototype/test/node/router.test.ts` + `prototype/test/node/core.test.ts`; no contamination path between the two scopes.

Next owner/action: results handed back to antigravity-head (aplexer). Services from the live run were torn down after evidence capture; the durable private scratch (logs, raw payloads, tokens) lives under `/home/alexey/git/cloudflare-agent-git/.local/scratch/zcode-fork-adoption/` and is not published.
