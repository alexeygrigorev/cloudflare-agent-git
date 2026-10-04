# C1673 — CLI push `--token`/`--admin-token` wiring and boundary report

- Worker: zcode-recovery-test (4abc725c), assigned by antigravity-head (message 01a10530, Codex C1673)
- Date: 2026-10-04 (Europe/Berlin)
- Branch: **`proto/cli-push-token`** @ **`862d17f`** (branched from `b2df985d3eedfdf345fceb966b18bed415d1187f`), pushed to origin
- Scope: condition 1 of REPORT-SDK-PACKAGED-FIRSTUSE.md — CLI push could not carry a per-task token although `AgentBranchesClient.push(..., token=...)` existed (C1518/C1532).

## Changes (862d17f, 3 files, +153/-2)

1. **`agent_branches/cli.py`** — push subparser gains `--token` (pushing agent's per-task
   task token) and `--admin-token` (admin fallback), both passed through to
   `client.push(...)`; mirrors the ack subparser's flag semantics and help text.
2. **`agent_branches/client.py`** — push bearer resolution chain gains `$TASK_TOKEN`
   between `admin_token` and `$ADMIN_TOKEN`, i.e. `token` → per-task cache →
   `admin_token` → `$TASK_TOKEN` → `$ADMIN_TOKEN`. This makes push identical to
   `get_task`/`ack_warning` (C1655 chain) and is what the required cold-client
   `$TASK_TOKEN` test exercises; without it the CLI env fallback cannot work.
3. **`tests/test_client.py`** — new `test_23_cli_push_token_flags` (see below).

## Unit suite

`python3 -m unittest -v tests/test_client.py` → **23/23 OK** (22 pre-existing + new
test_23). No pre-existing test modified.

test_23 covers, via cold `agent-branches` subprocesses against the token-configured
mock mirroring the real `requireMutatingAuth` ladder:

| case | input | expected | result |
|---|---|---|---|
| 1 | `--task-id` + `--token <owner>` | accepted; agentId resolved via same bearer | PASS |
| 2 | `--task-id` + `--admin-token <admin>` | accepted (admin is a push credential) | PASS |
| 3 | `--agent-id` + `--token <foreign valid>` | 403 forbidden, CLI exit ≠ 0 | PASS |
| 4 | `--agent-id` + `--token <revoked>` | 401 (revocation denied before narrowing), exit ≠ 0 | PASS |
| 5 | `--task-id` only, cold process, `TASK_TOKEN=<owner2>` env | accepted (env fallback) | PASS |

Negative cases pass `--agent-id` explicitly so the push route's own ladder is
exercised rather than the authenticated `get_task()` resolution, which would fail
first with the same wrong bearer (C1532).

## Live verification against the compiled db4 HTTP router

Real stack: pristine `git archive db4f6a8c398d` (tree `f31c6865d278`, per C1554),
compiled with pre-existing typescript (read-only node_modules symlink), real sidecar
`sidecar.mjs` + compiled coordinator `src/local/main.js` under node 24.13.1, ephemeral
ports/credentials, scratch-only (≤ 5 MB). Serving envelope: node
`--disable-wasm-trap-handler --max-old-space-size=256`, coordinator under
`ulimit -v 1530000` (the C1685-verified serving envelope; see receipt
`.local/receipts/c1685-flag-vlim-mitigation-2026-10-04.md` in the recovery worktree),
sidecar under `ulimit -v 1500000`.

Real commits were pushed into real forks over sidecar git HTTP (Bearer via
`http.extraHeader`; note: minted tokens contain URL-special characters that break
`user:pass@host` basic-auth URLs), then the packaged CLI ran the ladder.

**Evidence discipline (per C1712/C1717/C1720):** the FINAL ladder run captured each
case's actual CLI stdout, exit code and stderr in one pass, one mutation per case —
no mutation was retried on a lost/ambiguous response. Raw outputs quoted below are
from that run. Persisted coordinator state (`seenPushes`, token `revokedAt`) is
reported separately as corroboration, never as a substitute for a captured response.
Two EARLIER runs (c1673-live, c1673-live2/3) lost wire responses (curl ECONNREFUSED
while the coordinator demonstrably processed and persisted requests); those runs are
preserved in `.local/scratch/flagtest/logs/` as inconclusive and were NOT scored —
the 403/401 boundaries they surfaced were re-established in the final run with
captured responses.

| case | CLI invocation (final run) | captured CLI response (stdout/exit) | persisted-state corroboration |
|---|---|---|---|
| owner token | `push --task-id task-0008 --head-sha fef66273… --token <owner>` | `{"accepted": true, "deduped": false, "agent": "cli-alpha-0008", …}` exit 0 | `seenPushes: cli-alpha-0008 → fef662735722…` |
| admin token | `push --task-id task-0008 --head-sha fef66273… --admin-token <admin>` | `{"accepted": true, "deduped": true, …}` exit 0 (dedupe correct: same task+sha as case 1) | no new seenPushes entry (deduped server-side) |
| env fallback | cold process, `TASK_TOKEN=<gamma>`, no flags, real sha `515b4450…` | `{"accepted": true, "deduped": false, "agent": "cli-gamma-0010", …}` exit 0 | `seenPushes: cli-gamma-0010 → 515b4450cbbe…` |
| foreign token | `--token <beta token>` on alpha's task | `API Error (403): forbidden: this token belongs to cli-beta-0009, not cli-alpha-0008` exit 1 | — (rejected, no state change) |
| revoked token | after `POST /tasks/task-0008/revoke`, `--token <revoked owner>` | `API Error (401): unauthorized: ADMIN_TOKEN, the agent's task token or the sidecar bearer required` exit 1 | `agentTokens[cli-alpha-0008].revokedAt` set |
| no credentials (bonus) | cold process, no flags, no env | fails closed 401 at task resolution — never sends an unauthenticated mutation | — |

The `deduped: true` label in case 2 is read from the CAPTURED response body, not
inferred from state.

## Invariants

- Memory: serving stack verified inside cgroup
  `aplexer-workload-4abc725c-…scope`, `memory.max=1572864000` (1500 MiB shared);
  coordinator RSS ≈ 62–77 MB, sidecar ≈ 61 MB.
- Scratch: `.local/scratch/flagtest/` only (≈ 5 MB), TMPDIR inside scratch, zero /tmp growth.
- Zero installs, zero Rust builds, zero network deps, no raw secrets in this report
  (all tokens ephemeral per-run; only shapes/statuses quoted).

## Deliverables

- Branch: `origin/proto/cli-push-token` @ `862d17f`
- Code: `agent_branches/cli.py`, `agent_branches/client.py`, `tests/test_client.py`
- This report: `research/antigravity/recovery/REPORT-CLI-PUSH-TOKEN.md` (cloudflare-agent-git main)
- Related receipts (recovery worktree, private): `.local/receipts/c1685-flag-vlim-mitigation-2026-10-04.md`

## Notes for integration

- The `$TASK_TOKEN` step in the push chain is a client-side resolution order change;
  explicit `--token` still wins over cache and env, preserving C1532 semantics.
- CLI `--token`/`--admin-token` on push resolve the same ladder as ack, so operator
  documentation can describe one token model for both mutating commands.
