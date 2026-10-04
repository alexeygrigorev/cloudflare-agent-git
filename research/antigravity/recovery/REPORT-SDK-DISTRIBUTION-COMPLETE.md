# REPORT-SDK-DISTRIBUTION-COMPLETE — C1610 / C1609

- **Executor:** zcode-recovery-test (session 4abc725c), delegated by antigravity-head (46fdb644) under Codex Principal C1609
- **Date:** 2026-10-04 (Europe/Berlin), start 05:26:23 +02:00
- **Workspace:** /home/alexey/git/agent-branches-recovery
- **Deliverable branch:** `proto/sdk-distribution-complete` @ **7692650578d275758615e28dd3e7de436de0b6db**, pushed to origin (verified via fetch: `origin/proto/sdk-distribution-complete` = 7692650578d275758615e28dd3e7de436de0b6db)
- **Base:** `origin/proto/actor-warning-resolution` @ eada0e44194359f5a9eb39d0d9b97724e5690aa7 (verified `git cat-file -t` = commit; parent of the new commit)

## Result: COMPLETE — all packaging, verification and push steps pass

### 1. Worktree & branch setup

- Worktree verified clean on `proto/recovery-test` before starting; `git ls-remote` confirmed `proto/sdk-distribution-complete` did not exist on origin.
- Fetched `proto/actor-warning-resolution:refs/remotes/origin/proto/actor-warning-resolution`; base commit present locally.
- Branch `proto/sdk-distribution-complete` created from eada0e4 and checked out in this worktree (see §5 concurrent-execution note).
- origin/main and peer branches untouched; both parent branches preserved.

### 2. Packaging unification

| File | Mode | Blob | Required | Match |
| --- | --- | --- | --- | --- |
| `agent-branches` | 100755 | `b7efa8be78c9f3cc0cbe2ed00be64873e91dbe44` | same | ✅ exact (`git hash-object` re-verified) |
| `LICENSE` | 100644 | `f7531fe0b2d46fdd5a45de87558c477e340ca078` | `git rev-parse db4f6a8c398d69f0e19072c41cb4b453b7dd1b71:LICENSE` = same | ✅ exact (MIT, Copyright (c) 2026 Alexey Grigorev) |
| `README.md` | 100644 | `2ef4bb204a5d9ab9c89a75b7cd181245c63ddbce` | updated | ✅ SDK contract below |

README declares: install/run instructions (no build, no installs; `./agent-branches` adds repo root to `sys.path` and calls `agent_branches.cli.main`); usage examples matched against the real CLI surface (`task create`, `push --test-provenance`, `status --task-id`, `ack --warning-id --action`, `checks`) and the Python API (`agent_branches.client.AgentBranchesClient`, `AGENT_BRANCHES_SERVER`); and the explicit test contract:

- `python3 -m unittest -v tests/test_client.py` = **full SDK client test suite, 22/22 PASS (OK)**.
- `python3 -m unittest discover -s tests` = **FAILS with 4 known errors** — honestly disclosed, failing research tests left in place, not deleted or masked.

### 3. Verification suite (measured in this worktree, memory cap `ulimit -v 1500000`)

1. `./agent-branches --help` → usage printed, **exit code 0**.
2. `python3 -m unittest -v tests/test_client.py` → **`Ran 22 tests in 7.963s / OK`, exit 0** (includes test_21_inspect_token_metadata, test_22_calculate_jitter).
3. `python3 -m unittest discover -s tests` → **`Ran 26 tests ... FAILED (errors=4)`, exit 1** — reproduces the known 4 errors, all import failures from unbundled deps:
   - `test_a01_runner`, `test_admission`, `test_radar_engine`, `test_run10_ack_parser` (e.g. `ModuleNotFoundError: No module named 'research'` via `research.antigravity.continuation_trial_runner`).
4. `git status` after commit → **clean; only `agent-branches`, `LICENSE`, `README.md` were touched/added** (untracked `__pycache__` test-run byproducts removed with `shutil.rmtree`; no `rm -rf`).

### 4. Push & recovery path

- Pushed `HEAD:refs/heads/proto/sdk-distribution-complete`; `git fetch origin proto/sdk-distribution-complete` confirms `origin/proto/sdk-distribution-complete` = 7692650578d275758615e28dd3e7de436de0b6db.
- Fresh-clone reproduction: `git clone --branch proto/sdk-distribution-complete git@github.com:alexeygrigorev/cloudflare-agent-git.git && cd cloudflare-agent-git && ./agent-branches --help && python3 -m unittest -v tests/test_client.py` — expects exit 0 and `Ran 22 tests ... OK`.
- Ordinary Git recovery path independent of this branch remains main + the periodic independent mirrors per AGENTS.md.

### 5. Concurrent-execution disclosure

A concurrent duplicate execution of this same task created the branch in this shared worktree mid-task; my visible `git switch -c` failed with "branch already exists" (branch pointed at bare eada0e4, packaging not yet done), and the packaging commit `7692650` landed under the exact required message at 05:29:57 +0200 — authored while my README edits were in the worktree, so the commit contains **my final corrected README** (verified: committed blob content includes the corrected `task create`/`ack --warning-id` examples and the 4-error disclosure; `git diff HEAD -- README.md` empty). My own `git commit` then correctly reported "nothing added", and my first push was rejected ("reference already exists") because the identical tip was already pushed. All hashes, modes, test results and origin state above were re-verified from the committed tree after the race; content is exactly as specified.

### 6. Invariants

- Scratch: 0 bytes new scratch (all work in the existing worktree); zero /tmp growth. Memory capped at 1500M (`ulimit -v 1500000`) for every test invocation. No Rust builds, no global installs, no secrets in this report.

Report committed to cloudflare-agent-git main under `flock .local/git.lock` with explicit staged path.
