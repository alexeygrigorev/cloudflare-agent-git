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
