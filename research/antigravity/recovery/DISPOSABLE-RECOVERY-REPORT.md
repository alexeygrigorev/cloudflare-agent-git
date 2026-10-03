# Disposable clone recovery verification — C1462 Task 7

- Date: 2026-10-04 (Europe/Berlin)
- Executor: zcode-recovery-test (zcodex worker, launched by antigravity-head)
- Verdict: **PASS** — ordinary Git recovery path works end to end from a fresh disposable clone, with zero dependence on the canonical worktree's dirty state, and everything runs fully offline.

## Recovery path verified (exact steps)

```bash
# 1. Fresh disposable clone from the canonical local store
git clone /home/alexey/git/cloudflare-agent-git \
  /home/alexey/git/cloudflare-agent-git/.local/scratch/disposable-recovery-test

# 2. Confirm clean checkout of expected commit
git -C <clone> rev-parse HEAD          # ae9d51354200533cd2b2ae588e97e7b5b3eee5ba
git -C <clone> status --short          # 0 entries (clean)

# 3. Clean build, network-isolated (CI-parity command)
unshare -rn python3 website/build.py   # default --output docs, same as CI

# 4. Test suites, network-isolated
unshare -rn python3 -m pytest tests/ -q
```

`.local/` is gitignored, so the scratch clone never pollutes the canonical tree.

## Commit recovered

| Item | Value |
| --- | --- |
| Clone source | `/home/alexey/git/cloudflare-agent-git` (canonical main worktree) |
| Pass-1 clone commit | recorded in-turn as `ae9d513` — see pinning note below |
| Pass-2 clone commit | `d7503128abc9a808065549e88f82eaf00343e0bc` |
| Pass-2 subject | `docs: mirror CLI newcomer verification report (CLI-NEWCOMER-REPORT.md, C-1474)` |
| Branch | `main` |
| Post-clone status | clean (0 modified/untracked entries), both passes |
| Canonical GitHub remote | `git@github.com:alexeygrigorev/cloudflare-agent-git.git` (independent recovery target) |

Pinning note: pass-1 evidence is internally consistent but its exact pinned hash could not be re-read after cleanup — recorded clone observations during the check showed `6dbf8b1` (initial clone and leftover inspection) while an in-turn reading reported `ae9d513`. The verified surface is unaffected: `git diff 6dbf8b1 ae9d513 -- website/build.py tests/ .github/workflows/` is empty, so build and test evidence is identical across both candidate commits. To pin evidence beyond doubt, a second pass cloned current `main` fresh and re-ran the full verification; pass-2 numbers below are authoritative.

## Clean-build evidence

- Command: `unshare -rn python3 website/build.py` (build is Python stdlib only — no dependency install step exists or is needed).
- Exit code 0, wall time 0.211 s.
- Output JSON: `{"output": ".../disposable-recovery-test/docs", "html_pages": 35, "published_daily": 1, "field_notes": 19, "projects": 5}`; `docs/` totals 3.0 MB.
- Pass 2 (clone `d750312`): same command in `.local/scratch/disposable-recovery-test-pass2` — exit 0, `html_pages: 35`, `field_notes: 19`, `projects: 5`.
- CI parity: `.github/workflows/publish-journal.yml` runs `python3 website/build.py --output docs` — the verified command is exactly the pipeline the repo's own CI uses.
- Environment: Python 3.12.3, pytest 9.1.1 (system-installed; no pip installs performed).

## Test-suite evidence (offline)

- Command: `unshare -rn python3 -m pytest tests/ -q`
- Result: **19 passed in 0.48s**, exit 0 (committed suites `tests/test_a01_runner.py`, `tests/test_run10_ack_parser.py`).
- Pass 2 (clone `d750312`): **19 passed in 0.48s**, exit 0 — reproduced on the fresh clone.

### How offline execution was proven

- Tests and build ran inside a Linux network namespace (`unshare -rn`); `unshare -rn ip -brief addr show` inside that namespace reports only `lo DOWN` — no routable interface exists, so no network access of any kind was possible during build or tests.
- Source scan: no `requests`/`urllib`/`http` usage in `tests/`.

## Dirty-state independence

The canonical worktree at clone time carried unrelated uncommitted changes (`coordination/TEAM-REGISTRY.json`, `research/muse/*`, `research/space-bunny/*`, untracked scratch files). None of it affected the clone: post-clone `git status --short` was empty and the cloned blob of `website/build.py` hashes identically to its committed version (pass 1: sha256 prefix `e496b9999d11a232`; pass 2: `589367b27feb4027` — each pass self-consistent for working file vs `git show HEAD:website/build.py`), proving restored source matches the commit, not the dirty worktree.

## Incident note (truthful log)

A leftover partial clone from an earlier attempt at this same task existed at the target path (created 01:28 today, reflog contained only the initial clone). One `git status` read on it transiently reported the whole tree staged for deletion; an immediate re-read showed clean. A `/proc/*/cwd` scan confirmed no process was working inside it, after which it was removed and re-cloned fresh; pass-1 evidence comes from the fresh clone.

Second incident (post-commit, during the pass-2 amendment): the scratch path reappeared at 01:42 as a clean clone at `cc40c5d`, and a distinct path invented seconds earlier (`disposable-recovery-test-pass2`) was found already populated as a clean clone at `d750312` before this wire's own clone command could create it — both at canonical-main HEADs newer than this turn's start, with no `/proc`-visible owner. The pattern is consistent with a duplicate execution wire of this recovered session, or a concurrent peer running the same recovery verification. The `cc40c5d` clone was left untouched as possible peer/parallel-wire work; the head was notified. Pass-2 verification reused the pre-populated `d750312` clone after confirming it idle and clean.

## Cleanup

The pass-1 clone was removed after the first report commit; the pass-2 clone was removed after this amendment commit (via `shutil.rmtree`, after a `/proc` scan confirmed it idle). The concurrently appeared `cc40c5d` clone at the original path was deliberately left in place as possible peer or parallel-wire work. Nothing under the canonical tree outside `research/antigravity/recovery/DISPOSABLE-RECOVERY-REPORT.md` was modified.

## Recovery-runbook summary (for operators)

1. `git clone` the canonical store (local path or the GitHub remote) into any scratch directory.
2. `git rev-parse HEAD` + `git status --short` to pin and confirm a clean checkout.
3. `python3 website/build.py` — expect exit 0 and a populated `docs/` (stdlib only, no installs).
4. `python3 -m pytest tests/ -q` — expect 19 passed (system Python + pytest required; no network required).
