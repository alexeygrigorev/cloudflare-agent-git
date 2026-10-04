# Remote Checkpoint & Disposable Restore Verification: db4f6a8

- **Date**: 2026-10-04 (Europe/Berlin)
- **Target Branch**: `proto/integration-auth-matrix`
- **Target Commit**: `db4f6a8c398d69f0e19072c41cb4b453b7dd1b71`
- **Remote**: `git@github.com:alexeygrigorev/cloudflare-agent-git.git` (GitHub remote)
- **Executor**: `recovery-db4f6a8-executor` (antigravity subagent under directives C1554 / C1555 / C1558)
- **Verdict**: **`RESTORATION_VERIFIED_PASS`**

---

## 1. Remote Checkpoint Existence Verification

Direct query against GitHub remote repository `origin` via SSH:

```bash
$ git ls-remote origin proto/integration-auth-matrix
db4f6a8c398d69f0e19072c41cb4b453b7dd1b71	refs/heads/proto/integration-auth-matrix
```

- **Remote Ref**: `refs/heads/proto/integration-auth-matrix`
- **Reported Commit SHA**: `db4f6a8c398d69f0e19072c41cb4b453b7dd1b71`
- **Match Status**: **EXACT MATCH** (Verified authentic GitHub remote ref)

---

## 2. Disposable Isolated Clone & Tree Fidelity

- **Scratch Directory**: `/home/alexey/git/cloudflare-agent-git/.local/scratch/recovery-db4f6a8/` (mode `0700`)
- **Clone Command**:
  ```bash
  git clone --branch proto/integration-auth-matrix --single-branch \
    git@github.com:alexeygrigorev/cloudflare-agent-git.git \
    .local/scratch/recovery-db4f6a8/disposable-checkout
  ```
- **Clone Wall-Clock Timing**: `2.547s` (user `0.472s`, sys `0.140s`)
- **Disk Consumption**: `20 MB` (strictly under 512 MB scratch budget)
- **`/tmp` Growth**: `0 bytes` (strictly zero `/tmp` pollution)

### Checkpoint Fidelity

| Metric | Target / Expected | Observed in Disposable Clone | Match |
|---|---|---|---|
| Commit SHA (`git rev-parse HEAD`) | `db4f6a8c398d69f0e19072c41cb4b453b7dd1b71` | `db4f6a8c398d69f0e19072c41cb4b453b7dd1b71` | **EXACT** |
| Tree SHA (`git rev-parse HEAD^{tree}`) | `f31c6865d278e75ac6445717813c41d21210ccb5` | `f31c6865d278e75ac6445717813c41d21210ccb5` | **EXACT** |
| `git status --short` | clean | 0 modified / 0 untracked | **CLEAN** |

### Dependency Isolation

In accordance with resource constraints, no broad directory duplication or redundant external network package installations occurred. `node_modules` was cleanly symlinked from `/home/alexey/git/agent-branches-integration/prototype/node_modules` into `prototype/node_modules` within the disposable checkout.

---

## 3. Test Suite Execution on Restored Source

All test suites were executed directly against the restored disposable source code.

### A. Node Router & Neutral Core (`npm run test:node` & `node --test`)

Compiled via `tsc -p tsconfig.node.json` into `.build/node/` and executed using Node native test runner:

- **Isolated Router Suite** (`node --test .build/node/test/node/router.test.js`):
  - **11 / 11 tests passed** (0 fail, 0 skipped)
  - Wall-clock time: `0.13s`
  - Peak RSS: `58,468 KB` (~57.1 MB)
  - Receipt:
    - `routing: unknown routes and unauthenticated setup` (pass)
    - `fail-closed: unconfigured admin token refuses authenticated routes` (pass)
    - `/tasks and /status over the neutral router` (pass)
    - `/events/push: validation, auth ladder, cross-agent 403, dedup` (pass)
    - `/events/artifacts: envelope accepted, unknown fork 202, bad envelope 400` (pass)
    - `/checks: runner auth, parse errors, stale 409, success shape` (pass)
    - `/tasks/:id and /tasks/:id/tests: 404s and owner-only provenance` (pass)
    - `/warnings/:id/ack: body validated before auth, owner-only acks` (pass)
    - `malformed JSON bodies map to the contract 400` (pass)
    - `read auth: GET /status and GET /tasks/:id require a valid bearer (C1462 Task 1)` (pass)
    - `rejectionMessage helper stays honest (guards the suite itself)` (pass)

- **Complete Node Test Suite** (`npm run test:node`):
  - **50 / 50 tests passed** (0 fail, 0 skipped)
  - Wall-clock time: `1.25s`
  - Peak RSS: `192,748 KB` (~188.2 MB)

### B. Prototype Vitest Suite (`npm test` in `prototype/`)

Full integration suite covering Worker coordination, storage durability, sidecar integration, and radar checks:

- **Test Files**: `13 passed (13)`
- **Tests**: **`91 passed (91)`**, 0 fail, 0 skipped
- **Wall-clock time**: `30.81s` (test execution `21.07s`, total suite duration `29.59s`)
- **Peak RSS**: `474,932 KB` (~463.8 MB)
- **Suites Passed**:
  - `test/durable.test.ts` (3 tests)
  - `test/tasks.test.ts` (5 tests)
  - `test/unprocessed.test.ts` (1 test)
  - `test/real-artifacts.test.ts` (14 tests)
  - `test/checks-wire.test.ts` (8 tests)
  - `test/rest-client.test.ts` (10 tests)
  - `test/envelope.test.ts` (2 tests)
  - `test/radar.test.ts` (4 tests)
  - `test/spike-sidecar.test.ts` (1 test)
  - Additional worker/router integration files (43 tests)

### C. Python SDK Suite (`python3 -m unittest discover -v tests` in root)

Tested client API adapters, radar engine semantic collision logic, ack parser, and memory admission gates:

- **Tests**: **`65 passed (65)`**, 0 fail, 0 errors
- **Wall-clock time**: `10.91s` (execution time `10.729s`)
- **Peak RSS**: `35,120 KB` (~34.3 MB)
- Key verified cases:
  - C1494 / C1499 / C1509 / C1518 / C1532 Client Auth & Token cache normalization
  - TestRadarEngine: disjoint commits, clean positive collection, textual & semantic contract collision, missing commit fail-closed, zero-test fail-closed, safe archive traversal rejection, RAM/PSI admission gates
  - TestRun10AckParser: UUID matching, timestamp bounds, replay prevention

### Total Verification Volume

- **Total Tests Executed Across All Restored Suites**: **206 tests**
- **Passed**: **206**
- **Failed**: **0**

---

## 4. Resource Usage & Memory Accounting Truth

| Stage | Wall-Clock Time | Peak RSS | Disk Consumption |
|---|---|---|---|
| Git Clone (Remote GitHub) | 2.547 s | ~25 MB | 20 MB |
| Node Native Runner (`npm run test:node`) | 1.25 s | 188.2 MB | — |
| Vitest Full Suite (`npm test`) | 30.81 s | 463.8 MB | — |
| Python SDK Suite (`unittest discover`) | 10.91 s | 34.3 MB | — |
| Clean Teardown & Scratch Deletion | 0.05 s | — | 0 MB (reclaimed) |

### Memory Accounting Truth
- **Kernel Cgroup Reality**: Inspection of `/sys/fs/cgroup/user.slice/user-1000.slice/session-8309.scope/memory.max` reveals `max`. There is no active kernel-level cgroup hard cap at 1500M.
- **Process Convention**: The `1500M` ceiling is an agreed cooperative agent/process convention. Peak RSS across all restored verification executions remained strictly within this budget at `463.8 MB` max during the Vitest run.

---

## 5. Teardown & Recovery Verification

- No background tasks were left running (`lsof` confirmed 0 open descriptors).
- The scratch directory `.local/scratch/recovery-db4f6a8` and its disposable clone were completely removed.
- Canonical repo remains clean and unpolluted.

---

## 6. Final Verdict

```
=====================================================
VERDICT: RESTORATION_VERIFIED_PASS
Commit:  db4f6a8c398d69f0e19072c41cb4b453b7dd1b71
Ref:     refs/heads/proto/integration-auth-matrix
Tree:    f31c6865d278e75ac6445717813c41d21210ccb5
Status:  Clean independent remote recovery proven.
         206 / 206 tests passed on restored source.
=====================================================
```
