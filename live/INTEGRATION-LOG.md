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
