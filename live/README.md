# Live end-to-end demo — Agent Branches prototype

> **Status & Deployment Notice:**
> - **Current accepted implementation:** Plain Node + Git on existing Hetzner servers. There is **no Cloudflare deployment or Worker-serving plan**. Cloudflare Workers and Durable Objects adapter source (`prototype/src/cloudflare/`) is provided solely as an architectural reference implementation.
> - **Self-contained protocol walkthrough:** For the verified, self-contained protocol walkthrough (standard library Python only) and portable CLI options, see [`prototype/README.md`](../prototype/README.md).
> - **Historical run 3 evidence:** Run 3 evidence (`live/evidence/run-3/`, `run-3.log`, 2026-10-03) is historical and archival. Its execution commands (`bash live/run-demo.sh > live/run-3.log 2>&1`, `wrangler dev`, workerd serving, and headless Chrome screenshot override) are archival records of that past run, NOT current run instructions. Do not execute the legacy bare script.

## Current CLI Runner & Runtime Status (AB53 Split Runner)

The current demo entrypoint `live/run-demo.sh` is a thin POSIX wrapper delegating to `python3 -m live.demo_runtime "$@"`.
*(Note: Running `python3 live/demo_runtime.py` directly fails missing `live.demo_actors` under a clean systemd process unless `PYTHONPATH` is set to root).*

> **Important Gate Status (Do NOT imply full wrapper is accepted):**
> - The actual 15:25 run exited with code 1 (`exit 1`).
> - Submitted actors later completed only after runtime cleanup.
> - Runtime repair is ongoing.
> - Native push event propagation, current checks validation, owner acknowledgement (ACK), and the physical two-host transport gate (**AC59**) remain **unaccepted**.
> - AgentBus consistency interface (**AC60**) is **interface-only** accepted on main at `f389b716` with consumer three-case acceptance.
> - The dependent live CLI command gate (`--live` or full wrapper run) remains **OPEN / HELD** rather than claiming successful rehearsal.
> - Do not run old bare scripts or external APIs.

### Safe CLI Commands (Help & Preflight)

Safe offline inspection commands can be executed without launching models, mutating repository state, or invoking external APIs:

1. **Safe CLI Help (offline inspection):**

   ```sh
   python3 -m live.demo_runtime --help
   ```

2. **Safe Preflight Environment Check:**

   Validates system `node` and `git` binaries, sidecar source, compiled Node coordinator cache, and listener port status without model launch or state mutation:

   ```sh
   python3 -m live.demo_runtime --preflight --source-root . --cached-main prototype/.build/node/src/local/main.js
   ```

### Runtime Configuration & Required Options

The split runner CLI (`python3 -m live.demo_runtime`) accepts the following configuration options and environment variables:

- `--source-root <DIR>`: Path to repository source root (defaults to parent of `live/`).
- `--cached-main <PATH>`: Path to compiled Node coordinator (`prototype/.build/node/src/local/main.js`). Required for starting the local coordinator without recompilation.
- `--run-root <DIR>`: Path to runtime scratch directory for isolated session state (permissions 0700). Existing canonical wide root lease means this must be outside the protected canonical tree in its own isolated AgentBranches fork (not a new Git worktree).
- `--launcher-root <DIR>` (or `LAUNCHER_ROOT` env var): Path to `agent-quota-launcher` package directory containing the model launcher.
- `--launcher-config <DIR>` (or `LAUNCHER_CONFIG` env var): Path to launcher configuration directory.
- `--session <PATH>`: Path to private session JSON file (mode 0600) required for stage-specific execution (`--stage {models,checks,owner,cleanup}`).
- `--stage <STAGE>`: Executes an individual phase stage against an active session:
  - `models`: Runs parallel actor model tasks via the launcher.
  - `checks`: Evaluates radar mergeability and submits typed checks.
  - `owner`: Runs owner followup review and acknowledgement.
  - `cleanup`: Terminates owned process groups and releases allocated resources.
- `--live`: Full live setup, actor execution (models), checks, and cleanup. (*Gate notice: HELD / UNVERIFIED. Runtime repair is ongoing; do not run without verified environment and approved gate closure.*) Note: `--live` currently defaults to models/checks/cleanup; it does NOT complete owner/full video. To run `--stage owner`, you must have preserved own services/state resumed.

## Archival Run 3 Evidence (Historical Record, 2026-10-03)

**Run 3 result (2026-10-03, zc-live-5): 36/36 assertions passed** — archived in `live/evidence/run-3/`.

### Archival Evidence Inspection

The historical artifacts from Run 3 can be safely inspected using standard read-only commands:

```sh
cat live/evidence/run-3/result.json    # assertions, machine-readable
cat live/evidence/run-3/summary.txt    # same, human-readable
python3 -m json.tool live/evidence/run-3/status.json | head -40
```

### Archival Run 3 Headline (Historical Contract 0.1.2)

- **Typed wire end to end (G4/G5 closed).** The radar's contract-`"0.1"` payload (object `policy`, counts `coverage`, per-result `heads` + typed `evidence`) was POSTed to `/checks` verbatim. The down-conversion `*.posted.json` shim was deleted; no `[object Object]` anywhere in the UI.
- **Tasks carry intent + base_sha.** Intents were distilled at runtime from `demo-target/TASKS.md` (heading + tests-to-add line); `base_sha` pins the canonical seed commit. `GET /status` agents exposed `intent` + `baseSha`.
- **Designed matrix asserted honestly (G8 closed).** T1-T3 was a real textual overlap (both patches insert routes at the same anchor in `src/worker.js`; reproduced with `git merge-tree` and codified as FACT 4 in `demo-target/verify-overlap.sh`). The assertion required `conflict`+`textual` for T1-T3.
- **Warnings counted per pair, new + existing.** The receipt assertion verified every conflicting pair had an active warning.
- **T2-T3 coverage.** The test conflict surfaced per-pair `coverage.tests_collected = 19 > 0` in `/status`, and `pair-status.js` badged all three pairs "Conflict".

### Archival Execution Flow (Historical Reference Only)

The legacy run-3 procedure ran under `bash live/run-demo.sh > live/run-3.log 2>&1` using temporary `live/.dev.vars`, starting the L1 sidecar (:8799) and legacy `wrangler dev` (:8787). This flow is documented strictly for historical auditability of `live/evidence/run-3/` and has been superseded by the Hetzner Node architecture:

1. Started L1 sidecar (:8799) and legacy `wrangler dev` (:8787).
2. `POST /setup` (ADMIN_TOKEN) — initialized canonical repo.
3. `POST /tasks` x3 (admin) — created task forks with `intent` and `base_sha`.
4. Applied reference patches as agent pushes.
5. Radar pass 1 (`python3 -m radar --l1`) — posted typed payload to `/checks`.
6. Phase-1 assertions.
7. Stale probe: churn push on t1, replay of old radar payload → 409 Conflict.
8. Radar pass 2 at new vector; `POST /checks` verbatim.
9. Evidence collection: `/status` JSON, headless Chrome screenshots of review UI, `ui-pairs.json`.
10. Final assertions → `live/evidence/run-3/result.json`.

## GAP LIST — Historical Run-2/Run-3 Items & Current Status

**G1 · Process hygiene — CLOSED in historical script; adapted to AB53 runtime.** Prior executor terminations: zc-live-integration exited EXIT 143 (self-kill hypothesis); zc-live-2 ended RUN_EXIT 137 (OOM not excluded); zc-live-3 stopped intentionally. Run 3 introduced `setsid` process groups with group-leader checks and TERM→KILL escalation. The current `live/demo_runtime.py` tracks process groups and PIDs explicitly in private session files (mode 0600).

**G2 · Sidecar requires a per-repo token on EVERY git endpoint — CLOSED.** All clone/fetch/push calls authenticate with minted per-repo tokens, `GIT_TERMINAL_PROMPT=0` is exported, fresh read tokens per radar pass. `POST /events/push` is token-gated.

**G3 · Assertions/contract drift — CLOSED.** Assertions align with CONTRACT response shapes (typed receipt, `currentHeads` in 409, radar-kind reasons).

**G4 · radar `policy` object vs string — CLOSED.** Typed `{merge, tests}` policy object is posted and recorded verbatim (`contract: "0.1"` mandatory).

**G5 · radar evidence object vs string — CLOSED.** Typed evidence object is posted verbatim, stored as `evidenceDetail`, and rendered safely in UI.

**G6 · CORS for review UI — CLOSED on plain Node coordinator.** The plain Node coordinator (`src/local/main.ts`) serves CORS headers and handles OPTIONS preflights, enabling UI usage across origins.

**G7 · Screenshot assertion — ARCHIVAL.** Run 3 screenshots were visually inspected for intents, base SHAs, and badges. Current headless verification relies on machine assertions and `ui-pairs.json`.

**G8 · Fixture drift in demo-target — CLOSED.** T1-T3 real textual overlap codified in `demo-target/verify-overlap.sh` (ALL 4 FACTS VERIFIED).

**G9 · State/marker isolation — CLOSED in session model.** Replaced ad-hoc state markers with explicit isolated runtime directories (`--run-root`) and session JSON tracking.

**G10 · Small executor bugs — CLOSED.** Fixed in run 2 and maintained.

**G11 · Tokens on command line — CLOSED.** Path-scoped Git environment variables (`GIT_CONFIG_*`) and session files replace command-line token parameters.

**G12 · Empty-clone default branch — CLOSED.** Symbolic-ref guard maintained.

**G13 · Handoff state drift — CLOSED.** Handoffs carry commit SHAs and verified receipts.

**G14 · Canonical seed push unprocessed-pushes ledger entry — ARCHIVAL.** Observed in run 3 sidecar post-receive; addressed in plain Node event handling.

## Ownership & Supported Alternatives

- Owned files in this entrypoint documentation scope: `live/README.md` and `prototype/ui/README-UI.md` (with task evidence in `.local/entry-readme-repair-r3/`).
- For current, fully verified protocol execution, use the self-contained walkthrough in [`prototype/README.md`](../prototype/README.md).
- To test the coordinator core test suite on plain Node:
  ```sh
  cd prototype && npm run test:node
  ```
- To test the Git sidecar on plain Node:
  ```sh
  cd prototype && export GIT_TERMINAL_PROMPT=0 && npm run test:sidecar
  ```
