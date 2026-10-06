# Live integration log — first real end-to-end Agent Branches run

Session: zc-live-integration (ZCode executor for claude-principal)
- id: e64874cb-0013-4e7f-ac38-75c5129883db, engine shell, parent claude-principal (b3a92dd0)
- Started: 2026-10-03, Europe/Berlin
- Branch: proto/live (from origin/proto/l1-scaffold @ 4837a78), worktree /home/alexey/git/agent-branches-live

## Merge plan
Merge order: l4-review-ui (prototype/ui + prototype changes) -> l5-demo-target (demo-target/) -> l3-radar (radar/) -> l2-client (agent_branches/, agent-branches/).

## Merge log
(each conflict: file, lanes, resolution)

## 2026-10-03 — run 1 terminated; state preserved (zc-live-2)

Session: zc-live-2 (a03e9417), ZCode continuation of zc-live-integration for claude-principal.

**Termination.** The previous executor (zc-live-integration, e64874cb) ended with EXIT=143
(SIGTERM). Most likely cause: its own `pkill -f` pattern matched its zcodex wrapper process;
it had already self-killed once before. Its working tree was left UNCOMMITTED.

**Run 1 achieved (uncommitted work now preserved in ae9cdd4):**
- Prototype worker + git sidecar both came up (worker already up at 16:07:41; sidecar on :8799).
- Run 1 used its own bespoke sidecar (live/sidecar.mjs, prototype/src/artifacts/sidecar.ts)
  and was based on L1 @ 4837a78 — it predates L1's current local-artifacts sidecar.
- POST /setup created the canonical repo (live/evidence/setup.json).
- **Bug 1 (ADMIN_TOKEN export):** the token was defined but not exported to the seed/push
  environment, so git could not authenticate.
- **Bug 2 (seed push, canonical write token):** the seed push prompted for credentials —
  `fatal: could not read Username for 'http://127.0.0.1:8799'` — the canonical write token
  was never supplied; seedCommit stayed null. No agent pushes, radar run, or /checks ran.

**State preservation:** committed as `wip(live): run-1 state at termination` (ae9cdd4) and
pushed to origin/proto/live. Excluded: prototype/node_modules, __pycache__, *.log,
live/.dev.vars (run-1 tokens, untracked by design), live/work/ (runtime scratch: seed repo
fixture with embedded .git; regenerable from the L5 demo-target fixture).

## 2026-10-03 — zc-live-4 takeover, run 2

Session: zc-live-4 (608d319e), ZCode/zcodex warm-path continuation of zc-live-3 for
claude-principal.

**zc-live-3 termination.** EXIT=143. Cause UNKNOWN — the self-kill-by-broad-process-matching
theory (zc-live-integration's `pkill -f` matching its own zcodex wrapper) is a HYPOTHESIS
carried over from the earlier run, not an established cause for zc-live-3; the desktop
orchestrator's 120m session timeout is an equally plausible source of SIGTERM. Recorded as
unknown on purpose.

**zc-live-3 left behind (now preserved):** the three upstream merges already committed
(bfdfea8 = L1 762ff3d, 3469b4a = L4 40381f3, 33cb6ba = L5 47f5dbe) plus the run-1 summary
above; the rewritten live/run-demo.sh was UNCOMMITTED and is committed as-is in this state
(`wip(live): zc-live-2 state`). No services were left running: no live/state/*.pid existed,
and nothing listens on 8787/8788/8799 (8797/8798 are Antigravity's — untouched). Run 1 used
its own bespoke sidecar + L1 @ 4837a78; run 2 uses L1's local-artifacts sidecar per CONTRACT
v0.1. prototype/.wrangler does not exist, so the coordinator starts fresh; the L1 sidecar
root (live/artifacts) is likewise fresh — consistent state, no stale canonical.

**Process-safety rule for run 2 (dogfood gap G1).** No kills by pattern, cwd or exe — ever.
Only PIDs written by run-demo.sh itself to live/state/*.pid may be killed, and only after
verifying pid != shell pid, not an ancestor of the shell, cmdline matches the expected
server, and /proc starttime+exe+cwd match what was recorded at start (PID-reuse guard).
If any check is inconclusive: leave it running, use different ports.

## 2026-10-03 — RUN 2 GREEN: 15/15 assertions (zc-live-4)

Full flow executed against the merged tree (L1 sidecar + CONTRACT v0.1): services up →
/setup → canonical seeded at 2d03d63d (token-minted push) → 3 tasks/forks → 3 reference
pushes (t1 5438456, t2 bcab40d, t3 e4e6339; churn 0277ae3) → radar pass 1
(T1-T2 conflict/textual, T1-T3 conflict/textual, T2-T3 conflict/test) → POST /checks 200 →
stale replay 409 naming the moved agent → radar pass 2 → POST /checks 200 → headless
screenshot of the review UI rendering live data → 15/15 final assertions,
live/evidence/result.json allPassed=true. Idempotency proven across 5 invocations
(failures were fixed in place; markers kept completed data steps consistent).

Notable findings (full list in live/README.md GAP LIST):
- **G1 dogfood proof:** safe_stop refused a PID recycled by the script's own shell
  mid-run; wrangler CLI kills orphaned workerd twice (needs process-group kills).
- **G2:** sidecar 401s unauthenticated git CLONE/FETCH (token required on every git
  endpoint) — this was the real cause of run 1's seed failure symptoms.
- **G6:** worker had no CORS for the UI's documented cross-origin ?api= usage — fixed
  on proto/live (prototype/src/index.ts: CORS headers + OPTIONS preflight); L1 should
  adopt. First screenshot (size-only-asserted) had captured the UI error state.
- **G8 fixture drift:** demo-target SOLUTIONS.md says T1+T3 don't textually overlap;
  both patches insert routes at the same anchor in src/worker.js → real textual
  conflict, reproduced with git merge-tree. Radar honest; fixture docs stale.
- Process cleanup after run: sidecar/UI/trap-killed; two verified orphans (workerd
  :8787, ui :8788) killed after positive identity checks (exe+cwd), recorded here.
  All demo ports free at handoff.

## 2026-10-03 — zc-live-5 session start (warm path)

`a whoami --json` (full, logged per tasking):

```json
{
  "schema_version": 1,
  "id": "a96112ac-9493-4cff-a818-6b4b9964a59d",
  "workspace": "/home/alexey/git/cloudflare-agent-git",
  "tag": "zc-live-5",
  "engine": "shell",
  "parent_session": "b3a92dd0-a17e-4a62-940f-eb3b829393f6",
  "command": ["bash", "-lc", "cd /home/alexey/git/cloudflare-agent-git && ZCODE_WARM=1 timeout 90m zcodex exec --skip-git-repo-check \"$(cat .local/claude/ZC-LIVE5.md)\" > .local/claude/zc-live5.log 2>&1; echo \"RUN_EXIT=$?\" >> .local/claude/zc-live5.log"],
  "cwd": "/home/alexey/git/cloudflare-agent-git",
  "env": {},
  "env_unset": [],
  "limits": { "memory_bytes": 3145728000 },
  "history_bytes": 4194304,
  "created_at_ms": 1791044236292,
  "updated_at_ms": 1791044239381,
  "last_activity_ms": 1791044236481,
  "reported_state": "working",
  "reported_state_at_ms": 1791044239381,
  "phase": "running",
  "worker_pid": 3292998,
  "workload_pid": 3293005,
  "worker_cgroup": "/user.slice/user-1000.slice/session-8287.scope",
  "workload_cgroup": "/user.slice/user-1000.slice/user@1000.service/app.slice/aplexer-workload-a96112ac-9493-4cff-a818-6b4b9964a59d.scope",
  "containment_cgroup": "/sys/fs/cgroup/user.slice/user-1000.slice/user@1000.service/app.slice/aplexer-workload-a96112ac-9493-4cff-a818-6b4b9964a59d.scope",
  "containment_cgroup_identity": {
    "boot_id": "edbec548-453f-4111-b38e-e7c16d12aa93",
    "cgroup_namespace_device": 4,
    "cgroup_namespace_inode": 4026531835,
    "mount_namespace_device": 4,
    "mount_namespace_inode": 4026531841,
    "cgroup_mount_id": 33,
    "cgroup_root_device": 28,
    "cgroup_root_inode": 1
  },
  "containment_empty": false,
  "socket_path": "/run/user/1000/aplexer/sessions/a96112ac-9493-4cff-a818-6b4b9964a59d/control.sock",
  "history_path": "/home/alexey/.local/state/aplexer/sessions/a96112ac-9493-4cff-a818-6b4b9964a59d/history.bin"
}
```

Tasking: run 3 = green on CURRENT L1 contract (CONTRACT 0.1.2 @ 3e9983b) with the
run-2 gap list closed: typed /checks payload posted directly (delete the
down-conversion / *.posted.json shim, G4/G5), per-task intent + base_sha at setup
(UI "Not stated yet / not recorded"), T1-T3 real-textual-overlap labeling (G8),
per-pair active-warning counting across new+existing, T2-T3 tests_collected > 0 +
UI shows Conflict, G1 process groups (setsid + kill -PGID, orphaned workerd must
not keep ports), G2 authenticated git everywhere + GIT_TERMINAL_PROMPT=0, README G1
text fix (exact EXIT 143/137 records), evidence under live/evidence/run-3/.

## 2026-10-03 — run 3 prep (zc-live-5)

Merged origin/proto/l1-scaffold @ 3e9983b (CONTRACT 0.1.2) into proto/live
(merge commit ace104f; tree now carries the canonical typed /checks wire,
pair views keyed by agentId, and the C-1357 unprocessed-push guard).

Changes for run 3 (all on proto/live):
- G4/G5 CLOSED: run-demo.sh posts the radar's typed contract-"0.1" payload
  VERBATIM to POST /checks; the down-conversion `*.posted.json` shim deleted.
- Setup now sends each task's intent (distilled from demo-target/TASKS.md
  headings + tests-to-add lines) and base_sha (canonical seed commit).
- Worker (additive, proto/live for L1 to adopt): GET /status agents[] now carry
  the owning task's `intent` + `baseSha` — /status previously had neither, so
  the UI cards showed "Not stated yet / not recorded" even when tasks had
  them. UI task page reads task-level intent/base_sha.
- G8: T1-T3 is a REAL textual overlap (reproduced: `git merge-tree` → CONFLICT
  (content) in demo-target/src/worker.js). Assertions now REQUIRE
  conflict+textual for T1-T3 ("expected conflict (textual, real overlap)");
  SOLUTIONS.md corrected to "three designed conflicts: two textual + one
  test"; verify-overlap.sh gains FACT 4 — ALL 4 FACTS VERIFIED locally.
- Warnings assertion counts ACTIVE warnings per conflicting pair across new +
  existing (coordinator dedup by pair+headsAtIssue), not newly-created only.
- T2-T3 tests_collected: radar/engine.py now parses node:test summary lines
  ("ℹ tests 19" / "# tests 19" / TAP "1..19") and records `tests_collected`
  on the FAILING combined-test evidence too (it was dropped there); count is
  parsed from FULL output, not the 2KB snippet. /status per-pair
  coverage.tests_collected then comes from the 0.1 evidence per contract.
- G1: every demo server starts via setsid as its own process GROUP (pgid ==
  pid recorded); cleanup kills the recorded GROUP (-PGID) after cmdline +
  group-leader + not-my-own-group checks, with TERM→KILL escalation and a
  final port-held check (holders logged, never killed by pattern).
- Evidence dir per run: live/evidence/run-3/ (+ run-2 evidence moved to
  live/evidence/run-2/). Screenshots: index AND a task page; ui-pairs.json
  records the output of the UI's own pair-status logic on live /status so
  assertions can pin badge states (T2-T3 must be "Conflict").

Validation before the run: tsc clean; vitest 67/67; sidecar node --test pass;
ui pair-status node --test 13/13; pytest tests/test_radar_engine.py 16/16;
verify-overlap.sh ALL 4 FACTS VERIFIED.

## 2026-10-03 — RUN 3 GREEN: 36/36 assertions (zc-live-5)

End-to-end against CONTRACT 0.1.2 (L1 @ 3e9983b merged at ace104f), fully fresh
state (live/state + live/artifacts + prototype/.wrangler wiped; canonical
agent-branches-canonical-a4ebe005 seeded at f3c8351). Flow: setup → 3 tasks with
intent (from TASKS.md) + base_sha → 3 authenticated agent pushes → radar pass 1 →
POST /checks with the typed contract-"0.1" payload VERBATIM (200) → stale replay
409 naming the moved agent → radar pass 2 (200) → screenshots (index + task
page) + ui-pairs.json → 36/36 final assertions, result.json allPassed=true.

Head SHAs: t1 126ccee (2 pushes), t2 d49548c, t3 8335941. Radar verdicts both
passes: T1-T2 conflict/textual, T1-T3 conflict/textual (G8: REAL overlap,
asserted as designed conflict), T2-T3 conflict/test with per-pair
coverage.tests_collected=19 on /status (radar now records tests_collected on
failing combined runs + parses node:test summaries). Warnings: pass 2 created 2,
reused 1 (t2-t3 dedup) — the receipt assertion counts ACTIVE per pair across
new+existing. UI badges all three pairs "Conflict" (verified via the UI's own
pair-status.js on live /status AND visually on both screenshots: intents,
"Started from" SHAs, warning cards, no [object Object]).

First attempt failed honestly: the belt-and-braces POST /events/push was
anonymous → 401 (route token-gated since contract 0.1.1); fixed by
authenticating with the agent's own task token, plus idempotent re-apply of
already-pushed patches. Second attempt exposed my intent-parser bug (DOTALL
regex swallowed the rest of TASKS.md into T1/T2 intents — caught by LOOKING at
the screenshot, exactly the G7 lesson); fixed to a one-line capture and the
fresh run re-ran clean. All ports free after cleanup; process-group kills
verified (TERM → group, no orphaned workerd).

New OPEN item G14 (for L1): the canonical SEED push's post-receive callback
400s (no agent owns the canonical at seed time) and lands in the
unprocessed-pushes ledger with agentId null. Benign (no pair affected) but the
ledger shouldn't carry a permanent entry for the documented seed flow;
suggested fix recorded in live/README.md.

Run-2 gap list after run 3: G1-G10, G12, G13 CLOSED; G11 OPEN (tokens on the
wrangler argv; flagged for L1); G14 NEW/OPEN (seed-push ledger entry).
