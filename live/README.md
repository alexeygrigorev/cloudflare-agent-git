# Live end-to-end demo — Agent Branches prototype (run 2)

Branch `proto/live` (integration of L1 @ 762ff3d, L4 @ 40381f3, L5 @ 47f5dbe).
One command reproduces the whole demo; all steps are idempotent via markers in
`live/state/` and leave evidence in `live/evidence/`.

**Run 2 result (2026-10-03, zc-live-4): 15/15 assertions passed** — see
`live/evidence/result.json` (machine-readable), `summary.txt`, `ui-index.png`
(review UI rendering live data), `radar1-l1.json` / `radar2-l1.json`,
`checks1-receipt.json` / `checks2-receipt.json`, `stale-409.json`.

## Prerequisites

- node + npx (wrangler dev), python3 (radar runner, assertions), git, rsync
- headless Chrome at
  `~/.cache/ms-playwright/chromium_headless_shell-1243/chrome-headless-shell-linux64/chrome-headless-shell`
  (only for the screenshot step; override the path in `run-demo.sh` if needed)

## Exact commands

1. Create the untracked token file `live/.dev.vars` (never committed; ignored by
   `live/.gitignore`). Tokens are arbitrary bearer strings you choose:

   ```sh
   # live/.dev.vars  (mode 600)
   export ADMIN_TOKEN='<random>'
   export RUNNER_TOKEN='<random>'
   export SIDECAR_TOKEN='<random>'
   export SIDECAR_PORT=8799
   export WORKER_PORT=8787
   export UI_PORT=8788
   ```

   Ports 8797/8798 belong to the Antigravity head — do not use them.

2. From the repo root (so `python3 -m radar` resolves):

   ```sh
   cd /home/alexey/git/agent-branches-live
   bash live/run-demo.sh > live/run-2.log 2>&1
   echo "exit=$?"   # 0 on success
   ```

   Never pipe the script's stdout into `tail -f` or similar: server processes
   inherit the pipe and hold it open. Read `live/run-2.log` and
   `live/evidence/result.json` instead.

3. Inspect results:

   ```sh
   cat live/evidence/result.json         # assertions, machine-readable
   cat live/evidence/summary.txt         # same, human-readable
   python3 -m json.tool live/evidence/status.json | head -40
   ```

## What the script does (in order)

1. Starts the L1 local-artifacts sidecar (:8799) and `wrangler dev` (:8787);
   both health-checked, started only if down, `</dev/null`, logs to files,
   PIDs recorded under `live/state/`, stopped by an identity-checked trap.
2. `POST /setup` (ADMIN_TOKEN) — creates the canonical repo
   (idempotent: returns the existing one), mints a canonical write token on
   the sidecar admin API, clones, seeds `demo-target/` (minus `.harness/`)
   and pushes the baseline.
3. `POST /tasks` x3 (admin) — forks with per-repo write tokens.
4. Applies the three reference patches as the three agents' pushes
   (authenticated clone + push; belt-and-braces `POST /events/push`).
5. Radar pass 1 (`python3 -m radar --l1`) at the 3-agent vector;
   `POST /checks` with RUNNER_TOKEN.
6. Phase-1 assertions.
7. Stale probe: churn push on t1, replay of the old radar payload → 409.
8. Radar pass 2 at the new vector; `POST /checks` again.
9. Evidence: `/status` JSON + headless-Chrome screenshot of the review UI
   (`prototype/ui`) served on :8788, pointed at the worker via `?api=`.
10. Final assertions → `live/evidence/result.json`.

To re-check a finished run without redoing data steps, just rerun step 2 —
markers skip everything except services + final assertions. To force a full
fresh run: `rm -rf live/state` (the runid/canonical guards keep partial state
consistent anyway).

## GAP LIST — every friction item hit while getting this green

**G1 · Process hygiene (dogfood, mandated).** "Executor killed itself twice via
broad process matching" (zc-live-integration; cause of its EXIT=143 remains
UNKNOWN — self-kill is the standing hypothesis, the 120m orchestrator timeout is
equally plausible). This run demonstrated both the failure mode and the fix:
- `safe_stop` REFUSED to kill a recorded PID that Linux had recycled for the
  script's own shell within the same run (cmdline check caught it).
- Killing the wrangler CLI PID orphans its `workerd` child, which keeps the
  port — happened twice. PID files must capture a process GROUP
  (`setsid` + kill `-PGID`), and "already up" checks cannot distinguish a
  healthy owned server from an orphaned child.
- `$!` of a compound `a && b &` is the subshell, not the workload — one of my
  own probe sidecars survived a "kill". Same lesson at executor scale: record
  workload identity, kill exactly that after verification.

**G2 · Sidecar requires a per-repo token on EVERY git endpoint** (clone and
fetch too, not only push). Unauthenticated git gets a 401 and then hangs on a
username prompt that becomes a confusing `exit 128`. Fix in script: authenticate
every clone/fetch/push, `GIT_TERMINAL_PROMPT=0`, mint fresh read tokens per
radar pass (TTL 3600 would otherwise break re-runs). The CONTRACT should say
this in bold.

**G3 · Assertions/contract drift.** `assertions.py` was written against field
names that don't exist: receipt is `{stale:false, accepted:<count>,
createdWarnings:[...]}` (not `accepted:true`/`warningsCreated`), the 409 body
carries `currentHeads` (not `staleHeads`), warning `reason` is the radar kind
("textual"/"test", not "radar-conflict:*"), and the script passed `--status`
which the parser didn't declare. All fixed on the assertions side; CONTRACT.md
should publish the exact response shapes.

**G4 · radar `--l1` payload `policy` is an object; `POST /checks` wants a
string.** The script posts a derived `*.posted.json` with
`policy="radar-l3 --l1 live-run-2"`. Align the two sides.

**G5 · radar evidence is an object; `/checks` types `evidence` as string.**
Accepted at runtime (TS type not enforced), but the UI can end up rendering
`[object Object]`. Pick one shape.

**G6 · No CORS for the documented UI usage (fixed on proto/live).**
`prototype/ui` is served from its own origin and fetches `?api=` cross-origin;
the worker sent no `access-control-allow-origin` and had no OPTIONS handling,
so the review UI could NEVER load live data (first screenshot shows the error
state — a size-only assertion had passed on it). Added CORS headers +
preflight to `prototype/src/index.ts` on this branch; L1 should adopt it.

**G7 · Screenshot assertion was vacuous.** `size > 10KB` passed on an
error-state PNG. Visual evidence needs to be looked at, not measured. (The
final `ui-index.png` now verifiably renders: 3 agent cards with head SHAs, all
three pair verdicts, the active-warnings table.)

**G8 · Fixture drift in demo-target (L5).** `SOLUTIONS.md` claims T1+T3 have no
textual overlap, but both patches insert routes at the same anchor in
`src/worker.js` → real git content conflict (reproduced with `git merge-tree`;
conflict hunk saved in the run log). The radar verdict `T1-T3 conflict/textual`
is honest; the fixture docs (and possibly `verify-overlap.sh`) are stale.
Either move one of the route insertions or update the designed matrix to
"three designed conflicts, two textual + one test".

**G9 · State/marker vs fresh-service combos.** Markers from an older run can
point at a canonical that no longer exists on a fresh sidecar, and tasks
created BEFORE the baseline push fork from the wrong head. Guards added:
canonical-exists check + runid marker that clears stale state; ordering
(seed before tasks) documented. Partial-state re-runs stayed consistent in
practice across four restarts.

**G10 · Small executor bugs the run caught:** `start_bg` had `shift 1` instead
of `shift 2` (executed the pidfile as the command); `wait_for` couldn't pass
auth headers (401 loop → false FATAL); a missing `declare -A FORK_NAME`
became `set -u` arithmetic on `t1`. All fixed.

**G11 · Tokens on the wrangler command line.** `--var ADMIN_TOKEN:…` is visible
in `/proc/<pid>/cmdline` to the whole host. Wrangler reads `.dev.vars` from the
project dir natively — a `prototype/.dev.vars` (untracked) would avoid the
exposure. Not fixed here (kept the single token source); flagged for L1.

**G12 · Empty-clone default branch.** An empty canonical clone follows local
`init.defaultBranch`; guarded with `symbolic-ref HEAD refs/heads/main`. Moot
in practice: the sidecar auto-seeds an initial commit on repo creation.

**G13 · Handoff state drift.** The tasking told this executor to redo merges
the predecessor had already committed, and the previous EXIT=143 cause was
unknowable post-hoc. Handoffs should carry: last known head SHA per branch,
what is committed vs WIP, and which processes were left running with their
PID files.

## Ownership / recovery

- Branch `proto/live`, worktree `/home/alexey/git/agent-branches-live`,
  pushed to `origin`. Evidence is committed. Tokens and runtime scratch
  (`live/.dev.vars`, `live/state/`, `live/work/`, `live/artifacts/`, logs)
  are gitignored.
- Recovery path: ordinary git (`git checkout proto/live`); the demo state is
  fully regenerable via the commands above.
