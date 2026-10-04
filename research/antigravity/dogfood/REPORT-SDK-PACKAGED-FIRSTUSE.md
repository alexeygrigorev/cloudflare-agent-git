# REPORT-SDK-PACKAGED-FIRSTUSE — C1625

Genuine first-use evaluation of the packaged SDK (`proto/sdk-distribution-complete`) on real development work.

**Scope label (C1631, Codex Principal guidance):** the executed flow is **component mock double execution** — the coordinator was `tests/mock_l1_server.py`, a component test double, not the real L1 coordinator or deployment sidecar. The git work, code edits, and client/CLI behavior are real; coordinator responses come from the double. Mock-double limitations are recorded as double limitations and are **not** scored as real protocol adoption failures or sidecar packaging defects: an SDK legitimately requires an external service, and this report documents those external service/sidecar requirements honestly rather than penalizing their absence from the package.

**Correction (C1644, Codex Principal review 9ddda2d):** evidence wording revised — production/runtime usability claims withdrawn (component-double evidence only), and the concurrent-execution disclosure re-attributed: the listener process ancestry identifies this session's own process tree, so the actor/launch cause is recorded as UNKNOWN, not a duplicate executor. The CONDITIONAL decision and the README fixes (a63411a, 2623601) are unchanged.

- **Executor:** zcode-recovery-test (4abc725c), delegated by antigravity-head (46fdb644)
- **Date:** 2026-10-04 (Europe/Berlin), 05:43–06:00
- **Worktree:** /home/alexey/git/agent-branches-recovery on `proto/sdk-distribution-complete`, start pin **7692650578d275758615e28dd3e7de436de0b6db**
- **Infrastructure:** component test double `tests/mock_l1_server.py` on ephemeral port 59925 (127.0.0.1), admin/runner credentials generated fresh via `secrets.token_urlsafe`, stored mode 600 in `.local/scratch/zc-4abc725c-fu-141a75/`, never printed; `TMPDIR` pointed into scratch; every process under `ulimit -v 1500000`; zero /tmp growth; scratch ≈ 64 KB « 512 MB.

## Decision: CONDITIONAL ADOPT

What was **observed on the component double**: a create → push → status loop with correct credentials behaves correctly — the create-time per-task token cache makes subsequent `push()` calls authenticate automatically, and the double's radar raised conflict warnings from real overlapping work. **Production/runtime usability is unproven**: none of this exercised a real L1, real sidecar, or the real auth ladder, so no "production-usable" claim is made. The observed **CLI is convenient against open/dev-style coordinators but was not sufficient against a bearer-enforcing L1** (as implemented by the double's documented ladder): it cannot present a per-task token, so scripted multi-agent operation degrades to acting as admin via `$ADMIN_TOKEN`. Conditional adoption for library-driven automation is recommended pending the verification items below, which are the actual production gate.

**Conditions (all small, all discovered in real use):**
1. Expose a per-task token credential on `push`/`status` (`--token` or a documented token-file/`AGENT_BRANCHES_TOKEN` convention) so CLI agents can act as themselves instead of admin.
2. Align naming: library kwarg `server_url`, CLI flag `--server`, env vars `AGENT_BRANCHES_SERVER` **and** `COORDINATOR_URL`. This exact inconsistency made this reviewer's own C1610 README example wrong (`server=` TypeError on first call) — fixed in commit 2623601.
3. Verify ack auth against proto: `ack_warning` sends no bearer header — a client-side fact observed regardless of double. The double's unauthenticated `POST /warnings/<id>/ack` route is a double limitation and is not evidence about proto; if proto enforces auth on ack, CLI acks would 401 in production. Verify against proto and add the header if required.
4. Document external service/sidecar requirements explicitly (honesty item, not a defect): an SDK legitimately requires an external L1 service and sidecar; the package should state these dependencies and the expected bearer ladder in its docs (error strings already reference a sidecar bearer). This records what a consumer must supply — it is not scored as an adoption failure.
5. Mock-double limitation (not an SDK finding): the double's `main()` exposes `--admin-token` only, so a runner-token-gated `/checks` cannot be exercised from the double's CLI. Affects test-harness reach, not the SDK's protocol behavior.

## What actually happened (component mock double execution on real code)

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

## Environment disclosure — concurrent-execution anomaly, attribution corrected (C1644)

Observed anomalies, preserved as recorded: this session's first reserved port 39899 was already bound at 05:48:39; port 59925 was bound before this session's own listener start; the double's task list contained push records this session did not issue (task-0001/task-0003); and some pushes appeared deduplicated. Commits a63411a and 2623601 existed in this worktree and on origin before this session's acceptance step, byte-identical to its local edits.

The earlier attribution of these anomalies to a concurrent duplicate executor is **withdrawn**. The only identity evidence available points the other way: both mock listeners (pids 2074547 on 39899, 2125593 on 59925) had PPID 2937905 — this session's own zcodex process, child of aplexer worker `4abc725c` — i.e. they were launched inside this session's own process tree. No independent toolcall/identity evidence of another actor exists, and port-binding order, visible file ordering, or byte equality do not prove cause. Accordingly the actor/launch cause is recorded as **UNKNOWN**; the claims that another executor "read my scratch token files" or "mirrored every step" had no attributed invocation and are removed. The superficially similar patterns on C1580/C1588/C1610 are **not** re-attributed here; each would need its own evidence.

Disposition: both listeners are gone (verified; ports 39899/59925 free), and this session's scratch dirs (`zc-4abc725c-*`, < 64 KB, untracked, never committed) were removed by this session on C1644. No other session's processes or files were touched.

## Invariants

`ulimit -v 1500000` on server, CLI and Python client invocations; scratch usage ~64 KB in `.local/scratch/` (removed on C1644); `TMPDIR` inside scratch; zero /tmp writes; zero raw secrets in this report (tokens generated at runtime, mode 600, never echoed); no Rust builds; no installs; own-session listeners and scratch cleaned up during C1644 correction (see disclosure).

## Verdict basis

No verdict was forced: ADOPT was reachable (the library loop is genuinely smooth against the double) and DECLINE was reachable (the CLI per-task-token gap is real for hardened use). CONDITIONAL reflects the measured split from component mock double execution: library strong against the double, CLI one small feature short; ack-auth and sidecar behavior remain unproven against proto and are carried as verification items, not findings. Per C1631 the caller decision stays open; per C1644 the decision itself is unchanged by the evidence-wording corrections. Falsification test for this verdict: run a two-agent flow on proto L1 with per-task tokens, CLI-only — if push/ack work without admin credentials, conditions 1 and 3 are obsolete and this should upgrade to ADOPT.
