# Agent Branches Conditional Deploy and Smoke Verification Checklist

## 1. Scope, Context, and Deployment Status

- **Context and Issue Scope**: Addresses Issue #111 (release documentation gap) and formalizes the conditional requirements, operational boundaries, and recovery runbook for deployment Issue #55.
- **Deployment Authorization, Executed Root Bounded Run, and Future Operational Authority**:
  - **Authorized Completed Bounded Run (Root Sole Operator)**: On 13 October 2026, founder Alexey authorized Root as the sole operator to execute exactly one bounded deployment smoke verification run. Root completed this bounded run per public completion receipt (GitHub issue #55 comment `6155150617`, script commit `898caf0`, doc commit `99f3fca5`, deployment endpoint `https://agent-branches.cloudflare-ai-agent-de9ca0.workers.dev`). All 14/14 verifications passed in 17.5s, consuming 60 Cloudflare Artifacts operations and bringing the daily counter to 138 of the 200 daily cap (`MAX_DAILY_OPS = 200`).
  - **No Further Cloud Run Authorization**: Root's sole-operator authorization was strictly limited to this single completed bounded run. Further cloud runs, deployments, or live test suites are **not authorized** here. Historical usage (138 of 200 ops on deploy day) does not establish ongoing or latest-day operational availability.
  - **Conditional Future Checklist (Non-Root No Further Deploy)**: For all non-Root actors, implementers, and harnesses, cloud actions remain strictly prohibited (zero `wrangler deploy`, zero `wrangler secret put`, zero cloud execution, zero spend, zero billing mutations). The completed deployment is live and not in a stale pre-run HELD state; however, any subsequent deployment, rollback, or cloud execution requires explicit Root and founder authorization. This checklist serves as the conditional future operational runbook and safety boundary while non-Root actors remain unauthorized for deployment.
- **Budget and Account Constraints**:
  - **Shared-Account Budget Unknown**: The Cloudflare account is shared with existing services (notably `agenthub`). Pre-existing resource usage, prior request volumes, and remaining monthly headroom on the shared account have not been independently audited.
  - **Total $5.00/Month Shared Ceiling**: The total account spending ceiling is strictly capped at $5.00/month, which includes the existing Workers Paid base subscription fee ($5.00/month). Because the subscription base consumes the full $5.00/month budget, zero financial margin exists for unmetered usage or paid overage fees.
  - **Unknown Actual Invoice Risk Not Erased by Smoke Run**: Cloudflare platform pricing does not provide automated hard spend cutoff limits for Workers or Durable Objects. Requests returning HTTP 429 still incur compute invocation costs. Cloudflare Artifacts pricing includes 10,000 operations/month and 1 GB-month storage before billing overages ($0.15/1,000 ops, $0.50/GB-month, with billing starting 14 October 2026), but Artifacts limits do not constrain overall account invoices. The successful 14/14 bounded smoke verification does not erase or mitigate this underlying account-level invoice risk.
- **Baseline and Video Freeze**:
  - Accepted source baseline commit `c73492ef62456b554b61861a925f9c08a7fadc92` and contest video SHA-256 `0e110c48c9b1083b18027d2649a115b68a57539edd61accd985fdec2e9a8ccc4` remain frozen and unchanged (no re-recording, no re-encoding).
  - **Location Disambiguation**: The canonical public contest video is tracked in the repository at `docs-submission/videos/agent-branches-demo-draft.mp4` (public GitHub blob: `https://github.com/alexeygrigorev/cloudflare-agent-git/blob/main/docs-submission/videos/agent-branches-demo-draft.mp4`; raw: `https://raw.githubusercontent.com/alexeygrigorev/cloudflare-agent-git/main/docs-submission/videos/agent-branches-demo-draft.mp4`). The local path `~/contest-submission/agent-branches-video-r2.mp4` is host-local only and not an externally accessible URL.

---

## 2. Software Budget Guardrails vs. Account Spending Caps

There is a fundamental architectural distinction between the prototype's internal software controls and Cloudflare account billing:

| Dimension | Prototype Software Guardrail (`prototype/wrangler.jsonc`) | Cloudflare Platform Account Billing |
| :--- | :--- | :--- |
| **Daily Operations** | `MAX_DAILY_OPS: 200` per UTC day | Uncapped by provider; billed per request/invocation |
| **Monthly Operations**| `MAX_MONTHLY_OPS: 6000` per calendar month | 10,000 free Artifacts ops included in Workers Paid; $0.15/1,000 thereafter |
| **Repository Count** | `MAX_REPOS: 4` application repositories | Dependent on Artifacts namespace quota |
| **Storage & Body** | `MAX_TOTAL_BYTES: 16777216` (16 MiB), `MAX_BODY_BYTES: 262144` (256 KiB) | 1 GB-month storage included; $0.50/GB-month overage |
| **Enforcement Seam** | Internal SQLite counter in `Coordinator` DO checks quota prior to binding calls; returns HTTP 429 when exhausted | Provider billing engine invoices all worker requests, including requests rejected with HTTP 429 |
| **Account Protection**| Application-level safeguard only; prevents self-induced runaway loops | **No hard cutoff**. Cloudflare will not cut off traffic at $5.00/month |

---

## 3. Credential Boundaries and Masking Requirements

All deployment, operations, and testing workflows must adhere to zero-credential leakage standards:

- **Strict Placeholder Nomenclature**:
  - `$CLOUDFLARE_API_TOKEN`: Cloudflare REST and Wrangler API token.
  - `$CLOUDFLARE_ACCOUNT_ID`: Cloudflare account identifier.
  - `$ADMIN_TOKEN`: Administrative bearer token for `/setup`, `/tasks`, and `/cloud/*`.
  - `$RUNNER_TOKEN`: Trusted radar runner bearer token for `/checks` and `/status`.
  - `$LOCAL_ARTIFACTS_TOKEN`: Webhook shared bearer token for `/events/artifacts`.
- **Credential Injection**:
  - Git smart HTTP interactions use Git environment variables: `GIT_TERMINAL_PROMPT=0`, `GIT_CONFIG_COUNT=1`, `GIT_CONFIG_KEY_0="http.extraHeader"`, and `GIT_CONFIG_VALUE_0="Authorization: Bearer <TOKEN>"`.
  - Credentials must never appear in command-line arguments (`argv`), process trees, URL query strings, or committed repository files.
  - Cloud secrets for Workers are provisioned via stdin using `wrangler secret put`, never committed to `wrangler.jsonc` or environment files.
  - No home directory paths or machine-specific identities may appear in commands or configuration.

---

## 4. Pre-Deployment Configuration and Offline Verification Checklist

All commands are relative to the repository root. Non-Root operators must not execute cloud deployment or secret provisioning commands.

### 4.1. Configuration Inspection
Verify that `prototype/wrangler.jsonc` contains the approved edge topology:
- Worker Name: `agent-branches`
- Main Script: `src/index.ts`
- Compatibility Date: `2025-06-01`
- Artifacts Binding: Namespace `agent-branches-dev`, binding name `ARTIFACTS`
- Durable Object Binding: Class `Coordinator`, binding name `COORDINATOR`
- SQLite Migration: Tag `v1`, `new_sqlite_classes: ["Coordinator"]`
- Guardrail Vars: `MAX_DAILY_OPS: 200`, `MAX_MONTHLY_OPS: 6000`, `MAX_REPOS: 4`, `MAX_TOTAL_BYTES: 16777216`, `MAX_BODY_BYTES: 262144`

### 4.2. Offline Test Verification
Execute offline validation suites to ensure code integrity without cloud calls:

```bash
# Typecheck TypeScript definitions
npm --prefix prototype run typecheck

# Execute all test suites (node:http router, sidecar, workerd unit tests)
npm --prefix prototype run test:all

# Verify executable protocol walkthrough locally
npm --prefix prototype run build:node
python3 prototype/demo/walkthrough.py
```

*Note on `walkthrough.py`*: In commit `2468e54a`, stale `.local` fallback logic was removed. When `BASE_URL` is set, `walkthrough.py` delegates strictly to `prototype/demo/cloud-smoke.py` in the same directory, failing closed with exit code 1 if the script is missing.

### 4.3. Conditional Deployment Commands (Root Sole Operator Reference Only — Non-Root No Further Deploy)
If and only if Root executes authorized edge deployment:

```bash
# Inspect bundle without deploying
npx --prefix prototype wrangler deploy --dry-run

# Provision secrets interactively via masked stdin
npx --prefix prototype wrangler secret put ADMIN_TOKEN
npx --prefix prototype wrangler secret put RUNNER_TOKEN

# Conditional production deployment
npx --prefix prototype wrangler deploy
```

---

## 5. Pre-Flight Endpoint and Auth Readback Checklist

Before initiating smoke tests, the operator must verify edge endpoints and authentication behaviors:

### 5.1. Public Status Readback (`GET /public/status`)
- Authentication: Unauthenticated (anonymous).
- Expected Response: HTTP 200 with `{ "status": "ok", "sanitizedSnapshot": true, ... }`.
- Accounting: Costs exactly 0 Cloudflare Artifacts operations (reads cached snapshot).
- Validation: Asserts that no private tokens, fork names, or unmasked credentials leak.

### 5.2. Authenticated Budget Readback (`GET /cloud/budget`)
- Authentication: Requires `Authorization: Bearer $ADMIN_TOKEN`.
- **Complete Live DO Stats Schema**: The real Worker/DO endpoint (`BudgetTracker.getStats()` in `prototype/src/cloudflare/budget.ts:179-235`) returns exactly 13 fields:
  1. `utcDayOps`: Current operations consumed in active UTC day (integer).
  2. `calendarMonthOps`: Current operations consumed in active calendar month (integer).
  3. `totalBytesUploaded`: Cumulative byte count across repositories (integer).
  4. `repoCount`: Active unique repositories tracked in Durable Object storage (integer).
  5. `dailyCap`: Configured daily quota limit (`MAX_DAILY_OPS`, default 200).
  6. `monthlyCap`: Configured monthly quota limit (`MAX_MONTHLY_OPS`, default 6000).
  7. `maxRepos`: Configured repository ceiling (`MAX_REPOS`, default 4).
  8. `maxTotalBytes`: Configured storage ceiling (`MAX_TOTAL_BYTES`, default 16,777,216).
  9. `maxBodyBytes`: Configured request payload ceiling (`MAX_BODY_BYTES`, default 262,144).
  10. `remainingDayOps`: Headroom remaining today (`dailyCap - utcDayOps`).
  11. `remainingMonthOps`: Headroom remaining this month (`monthlyCap - calendarMonthOps`).
  12. `remainingRepos`: Repository capacity remaining (`maxRepos - repoCount`).
  13. `remainingTotalBytes`: Byte headroom remaining (`maxTotalBytes - totalBytesUploaded`).
- **Pre-Condition Assertions**:
  - `repoCount == 0`: Confirms no foreign or stale demo repositories exist.
  - `remainingDayOps >= 90`: Asserts required operation headroom for smoke test (`MAX_BUDGET_DELTA_HARD = 90` in `prototype/demo/cloud-smoke.py:27` and `742-746`).
  - `remainingMonthOps >= 90`: Asserts required monthly quota headroom (`MAX_BUDGET_DELTA_HARD = 90`).
- **Negative Auth Check**: Anonymous request to `GET /cloud/budget` must return HTTP 401/403.

### 5.3. Coordinator and Task Read-Auth
- **Coordinator Read-Auth (`GET /status`)**:
  - Authentication: Requires bearer token (admin, runner, or valid agent token).
  - Negative Auth Check: Anonymous request must return HTTP 401 `{ "error": "unauthorized", ... }`.
- **Task Isolation Read-Auth (`GET /tasks/:id`)**:
  - Authentication: Requires owning agent token or admin token.
  - Negative Auth Check: Cross-agent request must return HTTP 403 Forbidden.

---

## 6. Finite Smoke Verification, Wire Alignment, and Op-Count Accounting

### 6.1. Smoke Script Invocation and Wire Alignment Status
The repository provides `prototype/demo/cloud-smoke.py` as the canonical verification suite. The script enforces finite timeouts (15s subprocess timeout, 15s HTTP timeout) and strict error handling.

- **Local Mock Mode (Fully Verified Offline)**:
  ```bash
  python3 prototype/demo/cloud-smoke.py --mock --actors 2 --output prototype/demo/report.json
  ```
  Verified offline against the internal loopback mock server with zero external network access.

- **Conditional Live Mode (Documented for Root Sole Operator Only)**:
  ```bash
  BASE_URL=https://<worker-domain> \
  ADMIN_TOKEN=<placeholder> \
  RUNNER_TOKEN=<placeholder> \
  python3 prototype/demo/cloud-smoke.py --actors 2 --output prototype/demo/report.json
  ```

- **Wire Alignment (Resolved on Current Main)**:
  All wire differences identified during initial development were resolved by Root in commits `951f4acc` and `898caf01` and validated in current source snapshot:
  1. **`POST /setup` Status Code**: `cloud-smoke.py:759` expects HTTP 201 (`expect_status=201`), matching `handleRoute` in `prototype/src/core/router.ts:471`. Resolved in commit `951f4acc`.
  2. **`POST /tasks` Parameter Naming**: `cloud-smoke.py:810` sends `"base_sha"` (snake_case), matching `router.ts:483`. Resolved in commit `898caf01`.
  3. **`POST /checks` Contract Version**: `cloud-smoke.py:951` and `987` supply `"contract": "0.0"`, matching contract validation in `prototype/src/checks-wire.ts:86` and `router.ts:596`. Resolved in commit `898caf01`.
  4. **Walkthrough Delegation**: `prototype/demo/walkthrough.py:59-66` removed legacy review fallbacks in commit `2468e54a` and delegates directly to `cloud-smoke.py`, failing closed with exit code 1 if missing.

### 6.2. Smoke Operation-Count Accounting (Observed Mock 24 ops vs. Live DO Accounting)

#### A. Observed Local Mock Execution Accounting (24 ops observed INCLUDING cleanup)
When executed with `python3 prototype/demo/cloud-smoke.py --mock --actors 2`, the internal `MockBackendHandler` records an exact delta of **24 operations** (`utcDayOpsDelta: 24`, `calendarMonthOpsDelta: 24`) measured at step `[8/8]` after step `[7/8]` cleanup:

| Step | Operation | Mock Route / Action | Mock Op Delta | Mock Cumulative | Notes |
| :--- | :--- | :--- | :---: | :---: | :--- |
| 1 | Baseline Preflight | `GET /cloud/budget` | 0 | 0 | Read-only budget query |
| 2 | Canonical Repo Setup | `POST /setup` | +1 | 1 | Mock creates bare repo on disk |
| 3 | Seed Push | `git push` (canonical) | +2 | 3 | Smart-HTTP: `GET info/refs` (+1) + `POST git-receive-pack` (+1) |
| 4 | Provision Actors | `POST /tasks` (x2) | +4 | 7 | Mock adds +2 ops per task (+1 fork + 1 mintToken) |
| 5 | Actor Clones | `git clone` (x2) | +4 | 11 | Smart-HTTP: `GET info/refs` (+1) + `POST git-upload-pack` (+1) x2 |
| 6 | Agent Pushes | `git push` (x2) | +4 | 15 | Smart-HTTP: `GET info/refs` (+1) + `POST git-receive-pack` (+1) x2 |
| 7 | Push Callbacks | `POST /events/push` (x2) | +2 | 17 | Mock adds +1 op per callback to advance head |
| 8 | Runner Clones/Fetches| `git fetch` (x2) | +4 | 21 | Smart-HTTP: `GET info/refs` (+1) + `POST git-upload-pack` (+1) x2 |
| 9 | Test Provenance | `POST /tasks/:id/tests` (1 pair for 2 actors) | +1 | 22 | Mock adds +1 op per pairwise test record (for 2 actors, there is exactly 1 pairwise check) |
| 10 | Radar Checks | `POST /checks` | +1 | 23 | Mock adds +1 op for check record |
| 11 | Negative Security Tests | 5 security checks | 0 | 23 | Rejected prior to state modification (see list below) |
| 12 | Teardown & Cleanup | `DELETE /cloud/demo-repos` | +1 | 24 | Mock adds +1 op upon cleanup; budget verification runs in step [8/8] after step [7/8] cleanup, so the observed 24-op delta includes the +1 cleanup op |

- **Negative Security Checks (0 ops added)**:
  1. `POST /public/status` -> HTTP 405 Method Not Allowed (0 ops)
  2. Stale vector submission in `POST /checks` -> HTTP 409 Conflict (0 ops)
  3. Cross-task test submission in `POST /tasks/:id/tests` -> HTTP 403 Forbidden (0 ops)
  4. Cross-repository push to unauthorized fork -> HTTP 403 Forbidden (0 ops)
  5. Unauthenticated request to `GET /cloud/budget` -> HTTP 401/403 Unauthorized/Forbidden (0 ops)

#### B. Mock Simulation vs. Live Worker / Durable Object / Artifacts Architecture
> [!IMPORTANT]
> The observed 24 operations in `--mock` mode are **simulation-only synthetic increments** within Python's `MockBackendHandler`. They do **not** represent or prove live Cloudflare Durable Object or Artifacts operations. There is no mathematical equation or 1:1 mapping between mock simulation counters and actual DO/RealArtifacts binding operations.

In the real Cloudflare edge deployment:
- **Per-Binding Operation Accounting (`RealArtifacts`)**:
  `RealArtifacts` (`prototype/src/artifacts/real.ts:150-188`) intercepts every Cloudflare Artifacts binding call (`create`, `get`, `fork`, `list`, `createToken`, `log`, `readCommit`, `delete`) and invokes `this.budgetTracker.reserveOp()` prior to dispatching the RPC.
- **`POST /setup`**: In the real Worker, setting up the canonical repository invokes multiple Artifacts binding calls (~3 ops), not the single synthetic op recorded by mock.
- **`POST /tasks`**: In the real Worker, creating a task executes 11 to 13 Artifacts binding calls (validating baseline, creating fork, reading commit tree, minting scoped gateway token), significantly higher than mock's synthetic +2 ops.
- **`POST /checks`**: In the real Worker, `CoordinatorCore.submitChecksNow` writes check status directly to Durable Object SQLite storage without calling Artifacts bindings; it consumes **0 Artifacts ops** (unlike mock's synthetic +1 op).
- **`DELETE /cloud/demo-repos`**: In the real Worker (`Coordinator.deleteDemoRepos`, `coordinator-do.ts:188-193`), the DO iterates over each tracked repository and invokes `await this.budgetTracker.reserveOp(); await gitHost.deleteRepo(name);`. For 1 canonical + 2 forks, this consumes **+3 ops**, whereas mock increments +1 op once.
- **Configured Hard Ceilings and Observed Operational Consumption**:
  In `prototype/demo/cloud-smoke.py:27`, the configured hard ceiling is `MAX_BUDGET_DELTA_HARD = 90`. Both preflight headroom checks (`remainingDayOps >= 90` and `remainingMonthOps >= 90` at lines 742-746) and post-run delta verification (`utcDayOpsDelta <= 90` and `calendarMonthOpsDelta <= 90` at lines 1105-1106) enforce this 90-operation threshold. During the sole authorized live smoke run completed on 13 October 2026, Root **observed exactly 60 actual Cloudflare Artifacts operations** (bringing the day counter to 138 of the 200 daily cap) while passing all 14/14 verifications. The 60-operation measurement is the observed outcome of that specific executed run, whereas 90 operations is the configured hard ceiling and preflight requirement.

---

## 7. Cleanup, Rollback, and Recovery Procedures

### 7.1. Ephemeral Resource Cleanup
Following smoke execution or in the event of an aborted test:
- **API Cleanup**: Invoke `DELETE /cloud/demo-repos` with `Authorization: Bearer $ADMIN_TOKEN`.
- **Inventory Audit**: Execute `GET /cloud/budget` with admin token; assert `repoCount == 0`.
- **Local Scratch Teardown**: Remove temporary directories created by test clients (`/tmp/smoke_*` or `.local/tmp/*`).

### 7.2. Cloudflare Worker Rollback Runbook (Root Sole Operator Reference)
If deployment anomalies, unexpected invocation spikes, or budget boundary warnings occur:

1. **Immediately Purge Repositories**:
   ```bash
   curl -X DELETE -H "Authorization: Bearer $ADMIN_TOKEN" https://<worker-domain>/cloud/demo-repos
   ```
2. **Roll Back Worker Deployment**:
   ```bash
   # Revert to previous deployment version
   npx --prefix prototype wrangler rollback
   ```
3. **Delete Worker Deployment (If rollback is insufficient)**:
   ```bash
   # Delete live worker and remove edge routes
   npx --prefix prototype wrangler delete --name agent-branches
   ```
4. **Credential Revocation**:
   Revoke administrative and runner tokens in Cloudflare Dashboard / Wrangler secrets.
5. **Incident Documentation and Operational Hold**:
   Record final `utcDayOps` and `calendarMonthOps` counters from `/cloud/budget` in post-mortem records. Post-rollback status holds and suspends any further conditional deployment pending Root and founder incident review.
