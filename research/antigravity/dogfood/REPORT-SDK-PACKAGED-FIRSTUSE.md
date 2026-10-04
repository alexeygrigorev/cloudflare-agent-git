# REPORT-SDK-PACKAGED-FIRSTUSE — C1625

Genuine first-use evaluation of the packaged SDK (`proto/sdk-distribution-complete`) on real development work.

- **Executor:** zcode-recovery-test (4abc725c), delegated by antigravity-head (46fdb644)
- **Date:** 2026-10-04 (Europe/Berlin), 05:43–06:00
- **Worktree:** /home/alexey/git/agent-branches-recovery on `proto/sdk-distribution-complete`, start pin **7692650578d275758615e28dd3e7de436de0b6db**
- **Infrastructure:** packaged offline coordinator `tests/mock_l1_server.py` on ephemeral port 59925 (127.0.0.1), admin/runner credentials generated fresh via `secrets.token_urlsafe`, stored mode 600 in `.local/scratch/zc-4abc725c-fu-141a75/`, never printed; `TMPDIR` pointed into scratch; every process under `ulimit -v 1500000`; zero /tmp growth; scratch ≈ 64 KB « 512 MB.

## Decision: CONDITIONAL ADOPT

The **Python client is production-usable today** for the create → push → status loop with correct credentials: the create-time per-task token cache makes subsequent `push()` calls authenticate automatically, and the radar raised genuine conflict warnings from real overlapping work. The **CLI is excellent against open/dev coordinators but not yet sufficient against a bearer-enforcing L1**: it cannot present a per-task token, so scripted multi-agent operation silently degrades to acting as admin via `$ADMIN_TOKEN`. Adoption is recommended for library-driven automation now; CLI-only hardened workflows and any ack-dependent flow should wait for the conditions below.

**Conditions (all small, all discovered in real use):**
1. Expose a per-task token credential on `push`/`status` (`--token` or a documented token-file/`AGENT_BRANCHES_TOKEN` convention) so CLI agents can act as themselves instead of admin.
2. Align naming: library kwarg `server_url`, CLI flag `--server`, env vars `AGENT_BRANCHES_SERVER` **and** `COORDINATOR_URL`. This exact inconsistency made this reviewer's own C1610 README example wrong (`server=` TypeError on first call) — fixed in commit 2623601.
3. Resolve the ack auth story: `ack_warning` sends no bearer and the mock's `POST /warnings/<id>/ack` accepts unauthenticated requests even when admin is configured. If proto L1 mirrors proto auth on ack, every CLI ack would 401 in production. Verify against proto and add the header.
4. Ship deployment guidance: the package includes no sidecar; the mock docstring explicitly simulates none, yet error strings reference a sidecar bearer. A consumer cannot assemble the documented auth model from the package alone.
5. Minor: mock `main()` exposes `--admin-token` only — a runner-token-gated `/checks` cannot be started from the CLI.

## What actually happened (authentic flow, real code)

| Step | Command (packaged surface) | Result |
| --- | --- | --- |
| Coordinator up | `python3 tests/mock_l1_server.py --port 59925 --admin-token <fresh>` | listening, `/status` serves canonical+tasks+warnings |
| Task create | `./agent-branches task create --intent "…" --json` | 201 `task-0002`/`alpha-0002`; **repo/base-sha/branch auto-filled from git** (correct values incl. base 7692650); token returned as `{scope, expiresAt, plaintext}` |
| Real work | README local-coordinator section (missing on first use) | commit **a63411a**, suite `22 tests OK` beforehand, pushed to origin |
| Push, no creds | `./agent-branches push --task-id task-0002 …` | fail-closed 401; error message actionable: *"Specify agent_id explicitly."* |
| Push, agent-id, no creds | `push --agent-id alpha-0002 …` | clean 401 `unauthorized: bearer token required`, exit 1 |
| Push, admin env | `ADMIN_TOKEN=… ./agent-branches push --task-id task-0002 --base-sha 7692650 --test-provenance "python3 -m unittest tests/test_client.py: 22 passed (OK)"` | accepted (deduped — see disclosure), registered files `[README.md]`, provenance stored |
| Peer task via library | `AgentBranchesClient(server_url=…)` → `create_task(...)` → `push(task_id, files_changed=["README.md"])` | token cached at create; push auto-authenticated; **radar: 3 pairwise checks, warn-002 raised (pair task-0004↔task-0002, README.md, textual)** — genuine conflict from real overlap |
| Status reads | `status` (open) · `status --task-id` (no creds → 401 · admin env → 200) | owner-or-admin narrowed read ladder behaves exactly as documented |
| Ack | `./agent-branches ack --task-id task-0002 --warning-id warn-002 --action "…"` | acknowledged; warning cleared from active list; unrelated pairs untouched |
| Follow-up fix | README `server=` → `server_url=` | commit **2623601** pushed |

Branch moved 7692650 → **a63411a** (docs section, +37 lines) → **2623601** (constructor fix); both verified on `origin/proto/sdk-distribution-complete`. Suite re-run: `Ran 22 tests … OK` (7.7s).

## Environment disclosure — concurrent duplicate execution

The same duplicate-executor pattern observed on C1580/C1588/C1610 ran this task in parallel: it bound my first reserved port 39899 at 05:48:39 (read from my scratch `port` file), then bound 59925 ahead of my process using my scratch token files, and mirrored every step (task-0001/task-0003 are its mirror records; its pushes deduped mine; commits a63411a and 2623601 landed under the duplicate first, byte-identical to my worktree edits, verified before acceptance). I did not touch its processes. Both listeners (39899 pid 2074547, 59925 pid 2125593) remain running and are left to their owner; my scratch is intentionally **not** deleted because the duplicate demonstrably reads it (< 64 KB, gitignored-by-absence: untracked, never committed). Recommend the head reap both listeners once C1625 is closed for all copies.

## Invariants

`ulimit -v 1500000` on server, CLI and Python client invocations; scratch usage ~64 KB in `.local/scratch/`; `TMPDIR` inside scratch; zero /tmp writes; zero raw secrets in this report (tokens generated at runtime, mode 600, never echoed); no Rust builds; no installs; no `rm -rf` (cleanup deferred, see disclosure).

## Verdict basis

No verdict was forced: ADOPT was reachable (the library loop is genuinely smooth) and DECLINE was reachable (the CLI credential gap is real for hardened use). CONDITIONAL reflects the measured split: library strong, CLI one small feature short, ack/sidecar stories unproven against proto. Falsification test for this verdict: run a two-agent flow on proto L1 with per-task tokens, CLI-only — if push/ack work without admin credentials, conditions 1 and 3 are obsolete and this should upgrade to ADOPT.
