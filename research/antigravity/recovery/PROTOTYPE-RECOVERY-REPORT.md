# Prototype recovery verification (C1478) — proto/live product branch

- Date: 2026-10-04 (Europe/Berlin)
- Executor: zcode-recovery-test (zcodex worker, antigravity-head team), per codex-principal C1484 guidance
- Verdict: **PASS** — the prototype product source is independently recoverable from the ordinary Git remote and its full test suite passes from a fresh restore.

## Pinned source

| Item | Value |
| --- | --- |
| Product branch | `proto/live` |
| Pinned commit | `f58227c7794751c26238b3988583d3c3e9273b47` (merge: proto/cred-expiry-gate, C-1430/C-1437) |
| Live worktree | `/home/alexey/git/agent-branches-live` — same commit `f58227c` |
| Independent remote | `git@github.com:alexeygrigorev/cloudflare-agent-git.git` — **reachable**; `git ls-remote` shows 22 heads including `refs/heads/proto/live` at exactly `f58227c` |

The remote is an independent ordinary recovery target: `ls-remote` was answered by GitHub over SSH, not by the local store.

## Restore (ordinary Git path)

```bash
git clone -b proto/live git@github.com:alexeygrigorev/cloudflare-agent-git.git <scratch-dir>
git rev-parse HEAD   # f58227c… — exact pin, clean status (0 entries)
```

Executed into a fresh atomic `mktemp -d` scratch dir (`.local/scratch/proto-verify-iu3pUj`, gitignored).

## Source fidelity

`diff -r` of the restored `prototype/` against the live worktree's `prototype/` reports no differences except `Only in live: .build, .wrangler` — gitignored build artifacts that a correct recovery must not carry. The restored source is the committed product source.

## Test evidence (from the restore, zero prior state)

- Python SDK suite: `python3 -m pytest tests/ -q` → **55 passed in 9.2s** (stdlib-only: `urllib`, `unittest`, mock L1 server; runs fully offline).
- Node prototype (`prototype/`, standard `npm ci` from `package-lock.json` — 87 packages, 4s; no global installs, no dependency copies from any worktree):
  - `tsc --noEmit` typecheck: pass
  - `vitest run`: **13 files, 91/91 tests passed**
  - sidecar tests: **16 pass, 0 fail**
  - node built tests (`test:node`): **29 pass, 0 fail**
- Total: **191 tests passing** from a pure remote restore; full `npm run test:all` exit 0.

Constraints honored per C1484: no cargo/global installs, no depscopy, no repeat of the main-branch website smoke (kept scoped in `DISPOSABLE-RECOVERY-REPORT.md`, commits `8ca77b3`+`7edd14c`).

## Incident / honesty note

Observation log (causality corrected per codex-principal C1493): two scratch paths this wire referenced were pre-populated seconds later — `proto-recovery-c1478` (born 01:49:43) and `proto-recovery-c1478-git` (born 01:50:20). Mid-run reads showed one path without a readable `.git` and one with an unborn HEAD; final inspection shows both are valid clones of `proto/live` at `f58227c`, consistent with in-progress clones caught mid-write. The actor and mechanism are **UNKNOWN** — "duplicate wire" and "mirror" remain unconfirmed hypotheses; no invocation lineage was captured, so no cause is asserted. Atomic `mktemp -d` naming avoids predictable-path collision; it does **not** prove non-preemption, and the pre-materialization pattern did not recur at the mktemp path. Both directories were left untouched as possible parallel-wire work and reported to the head. Measured preserved sizes (04:2x): 18,956,389 bytes each for the two `proto-recovery-c1478*` dirs and 19,737,520 bytes for `disposable-recovery-test` — ~56.6 MB total; no invented or extrapolated figures.

## Cleanup

The verified clone (including its `node_modules`) was removed after the report commit, following a `/proc` idle check. The two pre-populated directories remain in scratch, documented above with measured sizes.

Delivery note per C1493: two identical completion replies were delivered under different message IDs; they were acknowledged once semantically, with no second outcome produced.
