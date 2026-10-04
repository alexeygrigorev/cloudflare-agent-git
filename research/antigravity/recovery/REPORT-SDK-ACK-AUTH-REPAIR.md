# REPORT-SDK-ACK-AUTH-REPAIR — C1655

Narrow repair of the SDK ack-auth defect confirmed by REV-SDK-ACK-AUTH.md (commit 2960b89), assigned by antigravity-head (46fdb644) to zcode-recovery-test (4abc725c), 2026-10-04 Europe/Berlin.

- **Receipt:** `27a86fe` `fix(sdk): ack_warning sends bearer auth and agent body per proto contract (C1655)` — head of `origin/proto/sdk-distribution-complete` (verified via `git ls-remote`; local HEAD byte-identical, tree clean).
- **Base:** 2623601 (post-C1625 SDK branch state).
- **Verification:** client suite **22/22 OK** (`python3 -m unittest -v tests/test_client.py`, 7.9 s) and **11/11** boundary checks against an auth-enforcing coordinator.

## Defect (per 2960b89, all three legs confirmed independently before repair)

`ack_warning()` posted to `/warnings/:id/ack` with no `Authorization` header and no `body.agent`, while the real router (db4f6a8) answers 400 on missing `agent`, 401 without a bearer, 403 on a foreign agent's token, and accepts only the owner's task token or ADMIN_TOKEN (attestational route; sidecar bearer excluded). The mock double enforced neither, masking the defect in the suite (double mask).

## Repair (4 files, +110/−7)

1. **`agent_branches/client.py`** — `ack_warning()` / `branches_ack_warning()` accept optional `token`, `admin_token`, `agent`. Bearer ladder: explicit `token` → per-task token cached by `create_task` → explicit `admin_token` → `$TASK_TOKEN` → `$ADMIN_TOKEN`; token-less requests still go out unauthenticated so enforcing coordinators fail closed (401) rather than the client guessing. Agent resolves from the explicit argument, else the `task_to_agent` cache, else an authenticated `get_task` (same pattern as `push`), else fail-fast `ValueError` before any HTTP call (mirrors proto's 400 without a network round trip). Body now carries `agent` (plus existing `task_id`/`taskId`/`action`); bearer attached as `Authorization: Bearer <token>` only when a token resolves.
2. **`agent_branches/cli.py`** — `ack` gains `--agent`, `--token`, `--admin-token`, wired through `handle_ack`. (CLI `push` per-task-token remains dogfood condition 1 — explicitly out of scope here.)
3. **`tests/mock_l1_server.py`** — `/warnings/<id>/ack` now validates `body.agent` first (400 `agent is a required string`, mirroring router.ts order before auth), then enforces `check_mutating_auth` with agent narrowing when an admin token is configured (401 missing/runner/revoked/unknown → shared proto bodies; 403 foreign agent). Open-mode (no admin token) keeps validating `agent` but stays unauthenticated, consistent with the mock's other routes.
4. **`tests/test_client.py`** — one payload update: test_01's raw-urllib ack now sends `agent` (the old payload asserted the defective agent-less contract; disclosed scope widening beyond the three named files, declared via work join before editing).

## Boundary verification (auth-enforcing coordinator, fresh tokens, memory-only)

Started `MockL1Server` with `expected_admin_token` + `expected_runner_token` (both `secrets.token_urlsafe`, never printed or written to disk), two tasks/two owners created under admin auth:

| # | Case | Result |
| --- | --- | --- |
| 1 | missing `agent` → 400 `agent is a required string` | PASS |
| 2 | `agent`, no bearer → 401 `unauthorized: bearer token required` | PASS |
| 2b | runner token on ack → 401 (attestational route) | PASS |
| 3 | beta's task token acking as alpha → 403 `forbidden: this token belongs to beta-0002, not alpha-0001` | PASS |
| 4 | owner task token → 200 acknowledged | PASS |
| 5 | admin token → 200 acknowledged | PASS |
| 6 | cold client, `$TASK_TOKEN` env only → agent resolved via authenticated `get_task`, bearer sent, 200 | PASS |
| 7 | explicit `token=` + `agent=` args → 200 | PASS |
| 8 | no resolvable agent → client-side `ValueError`, no HTTP call | PASS |
| 9 | CLI `--token` flag end-to-end → rc 0, acknowledged | PASS |
| 10 | CLI `$ADMIN_TOKEN` env fallback → rc 0, acknowledged | PASS |

**Router-provenance note (honest scope):** verification used the auth-enforcing coordinator — the task's sanctioned alternative. The real compiled Node router was not exercised: this SDK branch carries no `prototype/` tree, and the router semantics (route order, status codes, error bodies, `decideMutatingAuth` ladder) were taken as pinned by REV-SDK-ACK-AUTH.md 2960b89, which quotes db4f6a8 verbatim. Real-L1 ack exercise remains the head's Ant18d follow-up; this repair does not claim proto runtime coverage.

## Anomaly disclosure (C1644 discipline)

During commit, an add/commit/push interleave occurred again: my first flock'd commit attempt reported "nothing added" while reflog/remote showed the intended commit `27a86fe` already landed and pushed, byte-identical SHA. Verified post-hoc: local HEAD == remote head == 27a86fe, tree clean, and the 22/22 + 11/11 results above were produced against exactly this tree. Cause recorded as UNKNOWN, no attribution; consistent with the unexplained same-session ancestry pattern documented in REPORT-SDK-PACKAGED-FIRSTUSE.md (C1644 correction). No other session's files or processes touched.

## Invariants

`ulimit -v 1500000` on suite and verification runs; scratch `.local/scratch/zc-4abc725c-ackauth/` (script + TMPDIR, < 64 KB, mode 700, removed after verification); zero /tmp growth; zero raw secrets in this report or on disk (tokens runtime-generated, memory-only); no Rust builds; no installs; report committed via `flock .local/git.lock` with explicit staged paths.

## Follow-ups (owner: antigravity-head)

- Exercise ack on the real L1 (Ant18d) — this repair makes the client send what proto requires; proto runtime confirmation is still outstanding.
- Dogfood condition 1 (CLI `push` per-task token) remains open and is the same pattern as `--token` added here.

## Addendum (C1657/C1664): verification against the actual compiled db4f6a8 Node router — 2026-10-04

The router-provenance note above is now closed. The boundary matrix was re-run against the **real compiled db4f6a8 router** — no substitute, no mock double.

**Source/process pin (private receipt: `.local/receipts/c1657-realnode-ack-verify-2026-10-04.md`, mode 600):**
commit `db4f6a8c398d69f0e19072c41cb4b453b7dd1b71`, tree `f31c6865d278e75ac6445717813c41d21210ccb5` (matches the C1554/C1559 pin), router blob `4c296c8a472c4ee6b90308f8a2c70747a25844e8`. Pristine `git archive db4f6a8 prototype` extraction; compiled with the pre-existing typescript from an existing node_modules tree (symlinked read-only — **zero installs, zero network**); served by `src/local/main.js` (node v24.13.1) with the real git sidecar (`local-artifacts/sidecar.mjs`); ephemeral ports, ephemeral openssl tokens (mode 600, destroyed with the scratch); the repaired SDK client (b2df985) drove the flow.

**Boundary matrix (every conclusion anchored in persisted coordinator state, not single response bodies):**

| Case | Result |
| --- | --- |
| missing `agent` with NO auth header → **400** `agent is a required string` | PASS — 400-before-401 ordering proven on the compiled router |
| missing / empty-string `agent` with valid admin auth → 400 | PASS |
| no bearer / garbage bearer → 401 | PASS |
| expired task token → 401 | PASS |
| revoked (cold) task token after admin revoke → 401 | PASS |
| sidecar bearer on ack → 401 (attestational, not accepted) | PASS |
| foreign **valid** agent token → 403 `forbidden: this token belongs to verify-delta-0023, not verify-gamma-0022` | PASS |
| owner task token → 200 (ack persisted in task view) | PASS |
| ADMIN_TOKEN → 200 | PASS |
| unknown warning id → 404 `unknown warning: nonexistent-warn` | PASS |

The warning itself was created through the real runner flow (RUNNER_TOKEN `POST /checks`, contract 0.0 → `warn-2`, pair of two live forked agents). **Zero acks persisted by any rejected credential** (state-verified negative evidence across sidecar/expired/garbage/foreign/revoked probes).

**C1669 action→note mapping (b2df985) verified on the same router:** the SDK client's ack (payload `note = action`) persisted ack note `verified-boundary`, visible on `GET /tasks/:id`; raw action-only requests (no `note` field) persist acks with **no** note — confirming the mapping is load-bearing, not cosmetic.

**Environment deviations (honest record; details in the private receipt):**
1. `ulimit -v 1500000` is infeasible for any Node 24 process using `fetch`: undici's WASM component needs a multi-GB *address-space reservation* (uncommitted). The sidecar (no fetch) ran under the cap; the coordinator ran heap-capped instead (`--max-old-space-size=256`), measured RSS 86.7 MB — cooperative intent (actual memory ≤ 1500 MB) met ~17× over. One-shot tsc build leg: `-v 3000000`, exit 0.
2. Duplicate request delivery: the sandbox network layer intermittently delivered requests twice with mismatched response bodies (sidecar request traces show two handler runs at identical milliseconds). All conclusions therefore anchored in persisted state (`GET /tasks/:id` ack lists); single-response statuses are labeled "seen by client" where quoted.
3. The workerd/Cloudflare adapter was not run; the local `node:http` runtime serves the same core router (`src/local/main.js` docstring states the parity intent).


Scope: report file only; SDK code untouched by this addendum (client state remains `27a86fe` + `b2df985` on `proto/sdk-distribution-complete`).

