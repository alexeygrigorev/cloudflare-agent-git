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
| Cloned commit | `ae9d51354200533cd2b2ae588e97e7b5b3eee5ba` |
| Subject | `registry: record completion of muse-radar-bench (Task 8) and launch of muse-ui-auth (Task 6) per C1470` |
| Branch | `main` |
| Post-clone status | clean (0 modified/untracked entries) |
| Canonical GitHub remote | `git@github.com:alexeygrigorev/cloudflare-agent-git.git` (independent recovery target) |

Note: canonical `main` advanced from `6dbf8b1` to `ae9d513` while this check ran (peer commits landing concurrently); the clone is pinned at the hash above, which is what was verified.

## Clean-build evidence

- Command: `unshare -rn python3 website/build.py` (build is Python stdlib only — no dependency install step exists or is needed).
- Exit code 0, wall time 0.211 s.
- Output JSON: `{"output": ".../disposable-recovery-test/docs", "html_pages": 35, "published_daily": 1, "field_notes": 19, "projects": 5}`; `docs/` totals 3.0 MB.
- CI parity: `.github/workflows/publish-journal.yml` runs `python3 website/build.py --output docs` — the verified command is exactly the pipeline the repo's own CI uses.
- Environment: Python 3.12.3, pytest 9.1.1 (system-installed; no pip installs performed).

## Test-suite evidence (offline)

- Command: `unshare -rn python3 -m pytest tests/ -q`
- Result: **19 passed in 0.48s**, exit 0 (committed suites `tests/test_a01_runner.py`, `tests/test_run10_ack_parser.py`).

### How offline execution was proven

- Tests and build ran inside a Linux network namespace (`unshare -rn`); `unshare -rn ip -brief addr show` inside that namespace reports only `lo DOWN` — no routable interface exists, so no network access of any kind was possible during build or tests.
- Source scan: no `requests`/`urllib`/`http` usage in `tests/`.

## Dirty-state independence

The canonical worktree at clone time carried unrelated uncommitted changes (`coordination/TEAM-REGISTRY.json`, `research/muse/*`, `research/space-bunny/*`, untracked scratch files). None of it affected the clone: post-clone `git status --short` was empty and the cloned blob of `website/build.py` hashes identically to its committed version (sha256 prefix `e496b9999d11a232` for both working file and `git show HEAD:website/build.py`), proving restored source matches the commit, not the dirty worktree.

## Incident note (truthful log)

A leftover partial clone from an earlier attempt at this same task existed at the target path (created 01:28 today, reflog contained only the initial clone). One `git status` read on it transiently reported the whole tree staged for deletion; an immediate re-read showed clean. A `/proc/*/cwd` scan confirmed no process was working inside it, after which it was removed and re-cloned fresh; all evidence above comes from the fresh clone.

## Cleanup

The disposable clone was removed after this report was committed. Nothing under the canonical tree outside `research/antigravity/recovery/DISPOSABLE-RECOVERY-REPORT.md` was modified.

## Recovery-runbook summary (for operators)

1. `git clone` the canonical store (local path or the GitHub remote) into any scratch directory.
2. `git rev-parse HEAD` + `git status --short` to pin and confirm a clean checkout.
3. `python3 website/build.py` — expect exit 0 and a populated `docs/` (stdlib only, no installs).
4. `python3 -m pytest tests/ -q` — expect 19 passed (system Python + pytest required; no network required).
