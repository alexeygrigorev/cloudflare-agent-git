# Independent Git-only checkpoint & disposable restore verification — proto/integration-auth-matrix @ db4f6a8 (C1554/C1559)

- Date: 2026-10-04 (Europe/Berlin)
- Executor: zcode-recovery-test (zcodex worker, antigravity-head team)
- Verdict: **PASS** — the integration branch is independently recoverable from the ordinary GitHub remote; restored checkout is byte-exact (tree-hash equality), repository-consistent (fsck), and its unit suites pass cleanly.
- Report filename note: this file satisfies the assignment delivered 04:3x (name `ZCODE-RECOVERY-AUTH-MATRIX-DB4F6A8.md`); the earlier C1554 message named `RECOVERY-AUTH-MATRIX-DB4F6A8.md` — same single report, no duplicate written.

## Pinned source

| Item | Value |
| --- | --- |
| Branch | `proto/integration-auth-matrix` |
| Commit | `db4f6a8c398d69f0e19072c41cb4b453b7dd1b71` |
| Tree | `f31c6865d278e75ac6445717813c41d21210ccb5` |
| Subject | `merge: combine proto/sdk-get-task-auth (cbf72e2) into proto/integration-auth-matrix` |
| Integration worktree | `/home/alexey/git/agent-branches-integration` — `git rev-parse db4f6a8` and `db4f6a8^{tree}` return exactly the hashes above |

## Remote & checkpoint (independent, Git-only)

1. `git ls-remote origin proto/integration-auth-matrix` (GitHub over SSH) → `db4f6a8c398d69f0e19072c41cb4b453b7dd1b71  refs/heads/proto/integration-auth-matrix` — the independent ordinary remote already carries the branch at the exact pin.
2. Additional Git-only checkpoint created and verified (no dependency/cache copies):
   `git bundle create .local/checkpoints/proto-integration-auth-matrix-db4f6a8.bundle proto/integration-auth-matrix`
   `git bundle verify` → "records a complete history", sha1; **6,879,109 bytes** (measured), retained.

## Disposable restore (GitHub → scratch)

```bash
git clone --no-checkout --branch proto/integration-auth-matrix --single-branch \
  git@github.com:alexeygrigorev/cloudflare-agent-git.git .local/scratch/zcode-recovery-db4/clone
git -C .local/scratch/zcode-recovery-db4/clone checkout db4f6a8c398d
```

Provenance observation (recorded per C1493 discipline): the destination pre-existed at 04:31:53 with exactly the assigned command's configuration (origin URL `git@github.com:alexeygrigorev/cloudflare-agent-git.git`, single-branch refspec `+refs/heads/proto/integration-auth-matrix:...`, no-checkout, `origin` ref at the exact pin, empty worktree) before this wire's clone executed. A `/proc` scan showed no active process inside. The actor/cause is **unknown** (no invocation lineage captured). Every receipt below was produced by this wire's own commands against the artifact, so the evidence stands regardless of which wire materialized the bytes.

## Verification receipts (this wire's commands)

| Check | Expected | Observed | Result |
| --- | --- | --- | --- |
| `git rev-parse HEAD` | `db4f6a8c398d69f0e19072c41cb4b453b7dd1b71` | same | PASS |
| `git rev-parse HEAD^{tree}` | `f31c6865d278e75ac6445717813c41d21210ccb5` | same (also equals worktree `db4f6a8^{tree}`) | PASS |
| `git status --short` | clean | 0 entries | PASS |
| `git fsck --full` | no corruption | exit 0, no output | PASS |

Source fidelity: the restored checkout's tree hash equals the pinned tree hash exactly — under Git's content addressing this asserts byte-for-byte tree fidelity, stronger than a file diff.

## Unit tests in the restored checkout

- Python SDK suite (`tests/`): **65 passed, exit 0** (12.5 s), run on host loopback.
  Honest isolation note: an attempt inside `unshare -rn` (loopback DOWN) failed 18/65 with `URLError('no host given')` — this branch's auth-era client tests require a live loopback listener (mock L1 server), unlike the earlier f58227c suite that passed fully offline. So: tests are localhost-only (no external network touched), but the hard netns-offline proof does not apply to this suite version.
- Node prototype (`prototype/`): `npm ci` from `package-lock.json` (87 packages, 3 s; no global installs, no dependency copies) → `tsc --noEmit` exit 0; `vitest run` **13 files, 91/91 tests passed**, exit 0.

## Invariants

Zero Rust builds; zero global binary installs; memory well under 1500M (Python/Node test processes only); scratch: task clone removed after verification (measured before removal as part of a ~353 MB shared scratch total, dominated by unrelated peer scratch — within the 512 MB cap); bundle checkpoint retained at 6.9 MB.

## Cleanup

`.local/scratch/zcode-recovery-db4/` removed via `shutil.rmtree` after a `/proc` idle check. Bundle checkpoint retained. Nothing in the canonical tree was modified except this report (and the separate C1493 amendment commit to `PROTOTYPE-RECOVERY-REPORT.md`).
