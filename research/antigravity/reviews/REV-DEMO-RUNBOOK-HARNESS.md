# REV-DEMO-RUNBOOK-HARNESS — Independent Negative & Provenance Review of Demo Harness

- **Document:** `REV-DEMO-RUNBOOK-HARNESS.md`
- **Reviewer:** Demo Provenance & Negative Reviewer (`demo-provenance-reviewer`)
- **Parent Authority:** `antigravity-head` (`46fdb644`), under Codex Principal C1639 / C1643 directives
- **As-of:** 2026-10-04, Europe/Berlin
- **Classification:** Comprehensive Independent Source Provenance, Negative Mutation, and Replay Truth Audit
- **Target Files Under Review:**
  - `scripts/demo-two-actor.sh` (uncommitted draft, mode `100755`)
  - `scripts/coordinator-local.mjs` (uncommitted draft, Node.js stdlib coordinator)
  - `research/antigravity/recovery/DEMO-RUNBOOK.md` (uncommitted draft)
- **Pinned Reference Points:**
  - `prototype/src/core/router.ts` and `prototype/src/local/main.ts` on `db4f6a8` (`proto/integration-auth-matrix`)
  - Base commit: `ec5030cf148b4207bde658a4fa1c0be7b2bf8e3e`
  - Actor Alpha commit: `9ec79dbcc5eb8be117a941c40e98deddc80e3c2f` (`inspect_token_metadata`)
  - Actor Beta commit: `d56689841b78ec0db77e66eb7934f042751c142b` (`calculate_jitter`)
  - Resolved merge commit: `eada0e44194359f5a9eb39d0d9b97724e5690aa7` (Tree `3f24dabadba1231b9e6dd97f8b5e3c26d8dff10f`)

---

## 1. Executive Summary & Verdict

### Verdict: REQUEST_CHANGES (Defects Noted & Critical Mutation Failures)

The demo script (`scripts/demo-two-actor.sh`) and accompanying local coordinator (`scripts/coordinator-local.mjs`) present an impressive zero-dependency, ephemeral-port demonstration of the two-actor conflict lifecycle. When executed on happy-path inputs, the end-to-end flow completes cleanly in ~9 seconds with zero system `/tmp` growth.

**However, negative mutation testing and code provenance audits reveal that the demo is currently operating as an unverified, handwritten contract replay fixture rather than a truthfully attested Radar protocol evaluation.** Specifically:

1. **Unverified Merge Conflict (Mutant 1):** Line 362 executes `git merge-tree` but never inspects the return code or diff. It unconditionally logs that Radar detected a collision and posts a handwritten conflict payload with hardcoded filenames. When mutated to push identical commits (zero conflict), the harness still claims a collision occurred.
2. **False-Positive Test Attestation (Mutant 2):** Line 447 executes `echo "${TEST_OUTPUT}" | grep -E "(Ran 22 tests|OK)"`. When mutated so that 0 unit tests run (or a single test runs), the regex matches `OK`, logs `22/22 unit tests collected and passed cleanly`, and submits a handwritten clean payload asserting 22 passed tests.
3. **Evidence Falsification in Coordinator (Mutant 3):** Line 506 in `scripts/coordinator-local.mjs` sets `testsCollected: result.evidence?.tests?.collected || 22`. In JavaScript, `0 || 22` evaluates to `22`. When a client submits a check with 0 tests collected or omitted test evidence, the coordinator falsifies the record to claim 22 collected tests.
4. **Source Provenance & Route Divergence:** `scripts/coordinator-local.mjs` was created because `prototype/src/local/main.ts` is written in TypeScript using `.js` ESM specifiers that fail under vanilla Node (`ERR_MODULE_NOT_FOUND`). However, `coordinator-local.mjs` diverges from `prototype/src/core/router.ts`: it lacks HMAC webhook verification (`WEBHOOK_SECRET` is unused), omits routes (`/events/artifacts`, `/tasks/:id/revoke`), introduces unauthenticated ACK access when `task_id` is supplied without a bearer token, and uses non-atomic file persistence.
5. **Actor Labeling & Replay Truth:** The script and runbook claim "Two autonomous actors" and "Simulating Autonomous Actor Beta/Alpha", whereas the system is actually executing a deterministic historical commit replay of static pins (`ec5030c`, `9ec79db`, `d566898`, `eada0e4`).
6. **Path & Credential Hygiene:** The script breaks on relative scratch paths, writes bearer credentials to `.git/config` on disk with mode `0664` rather than passing them via in-memory `-c` flags, and saves state files with mode `0664`.

Landing is **BLOCKED** until these negative validation gaps and labeling requirements are remediated.

---

## 2. Source Provenance Audit

### 2.1 Why `scripts/coordinator-local.mjs` was authored instead of running `prototype/src/local/main.ts`

The pinned Node runtime entry point exists on branch `proto/integration-auth-matrix` at commit `db4f6a8:prototype/src/local/main.ts`. An audit of why this file was not executed directly reveals two concrete barriers:

1. **Branch Isolation & Unmerged Tree:** `prototype/src/` exists only on branch `proto/integration-auth-matrix` and is not merged into `main`. The `main` worktree contains only `prototype/local-artifacts/`.
2. **ESM TypeScript Import Specifier Incompatibility with Vanilla Node:** Even when `prototype/` is extracted from `db4f6a8`, executing `node --experimental-strip-types prototype/src/local/main.ts` fails immediately:
   ```
   Error [ERR_MODULE_NOT_FOUND]: Cannot find module '.../prototype/src/core/coordinator.js' 
   imported from .../prototype/src/local/main.ts
   ```
   TypeScript source files in `src/` use relative imports pointing to `.js` extensions (e.g. `import { CoordinatorCore } from "../core/coordinator.js"`), in accordance with standard TypeScript ESM conventions. Node.js v24's native `--experimental-strip-types` does not perform extension-aliasing or resolve `.js` specifiers to `.ts` on disk. Running `main.ts` requires either a pre-build step (`tsc` / `esbuild`) or an external loader (`tsx` / `@swc/register`), which contradicts the project's requirement for zero npm packages and zero external build tooling.

To circumvent this, `scripts/coordinator-local.mjs` was created as a standalone, zero-dependency, pure JavaScript (ESM) file.

### 2.2 Route, Auth, and State Store Fidelity vs. `prototype/src/core/router.ts`

A line-by-line comparison of `scripts/coordinator-local.mjs` against `prototype/src/core/router.ts` (`db4f6a8`) reveals significant fidelity deviations:

| Feature / Invariant | Pinned Core (`prototype/src/core/router.ts`) | Standalone (`scripts/coordinator-local.mjs`) | Finding |
|---|---|---|---|
| **HMAC Webhook Ingestion** | Lines 86–105: Verifies `x-webhook-signature` using HMAC-SHA256, nonce replay guard, and timestamp freshness window. Fail-closed on missing secret. | Lines 326–392: Ingests `POST /events/push` without any HMAC verification or replay guard. Environment variable `WEBHOOK_SECRET` is defined (line 108) but completely unreferenced. | **DEFECT:** Insecure webhook ingestion. An attacker on localhost can spoof push events. |
| **Authentication Enforcement** | Lines 242–276 (`requireMutatingAuth`, `requireReadAuth`): Authenticates caller against bearer token ladder. Anonymous requests fail 401. | Lines 143–146 & 540: `authenticate(req, allowedAgents, allowTaskContext)` returns `{ ok: true, role: "agent" }` if `allowTaskContext` is provided, even if `Authorization` header is completely absent! | **CRITICAL DEFECT:** Calling `POST /warnings/:id/ack` with `{"agent": "actor-alpha", "task_id": "task-0002"}` bypasses authentication entirely without any bearer token. |
| **Check Validation & Test Counts** | `checks-wire.ts` / `coordinator.ts` line 722: Validates CONTRACT v0.1 schema; preserves verbatim `testsCollected: result.testsCollected` (`number | undefined`). | Line 506: `testsCollected: result.evidence?.tests?.collected || 22`. | **CRITICAL DEFECT:** Hardcodes default 22. If `collected` is 0 or omitted, it falsifies the record to 22. |
| **Push Agent Attribution** | Lines 360–375: Resolves agent strictly via fork ownership lookup or explicit authenticated task token. | Lines 349–351: If agent cannot be determined from body or fork suffix, falls back to `Object.keys(store.model.agents)[0] || "unknown-agent"`. | **DEFECT:** Arbitrary agent attribution fallback. |
| **Route Completeness** | Supports `/events/artifacts` and `/tasks/:id/revoke`. | Missing `/events/artifacts` and `/tasks/:id/revoke`. Adds `/health` and `/api/health`. | **DIVERGENCE:** Incomplete route surface. |
| **State Store Atomicity** | `FileCoordinationStore` (`prototype/src/local/store.ts`): Writes to `<path>.tmp` and executes atomic `rename` into place. | Lines 76–77: Synchronous `writeFileSync(this.path, ...)`. | **RISK:** Non-atomic store write; torn state on abrupt process termination. |

---

## 3. Negative Mutation Testing (Scratch Reproduction)

All mutation experiments were executed in isolated scratch directory `.local/scratch/demo-provenance-review/` with `ulimit -v 1500000` and `TMPDIR` redirected to scratch.

### 3.1 Mutant 1: No Conflict / Identical Actor Commits

**Objective:** Verify whether `scripts/demo-two-actor.sh` dynamically evaluates conflict evidence or blindly asserts collision.

**Mutation Applied:** In `mutant-1/demo-two-actor.sh`, Step 5 was modified so Actor Beta checks out commit `9ec79dbcc5eb8be117a941c40e98deddc80e3c2f` (the identical commit checked out by Actor Alpha, resulting in 0 merge conflicts):
```bash
git fetch local 9ec79dbcc5eb8be117a941c40e98deddc80e3c2f
git checkout -B main 9ec79dbcc5eb8be117a941c40e98deddc80e3c2f
```

**Observation:**
1. In Step 7 (lines 360–366), the script executed:
   ```bash
   CONFLICT_DIFF=$(git merge-tree "${BASE_SHA}" 9ec79dbcc5eb8be117a941c40e98deddc80e3c2f d56689841b78ec0db77e66eb7934f042751c142b)
   log_warn "Advisory Radar detected concurrent modification conflict in client.py & test_client.py"
   ```
   Notice that the commit SHAs passed to `git merge-tree` were hardcoded constants rather than referencing the actual branches or heads of the actors!
2. `$CONFLICT_DIFF` was never tested with `grep` or `[ -n "$CONFLICT_DIFF" ]`.
3. The script unconditionally printed `[WARN] Advisory Radar detected concurrent modification conflict in client.py & test_client.py`.
4. The script then submitted a hardcoded `CHECK_CONFLICT_PAYLOAD` with:
   ```json
   "vector": {
     "${ALPHA_AGENT_ID}": "9ec79dbcc5eb8be117a941c40e98deddc80e3c2f",
     "${BETA_AGENT_ID}": "d56689841b78ec0db77e66eb7934f042751c142b"
   }
   ```
5. Because Beta had actually pushed `9ec79db`, the coordinator correctly rejected the check with HTTP 409:
   `{"error": "stale vector: head for actor-beta-0001 moved to 9ec79db...; expected d566898..."}`.
6. The script crashed on python parsing: `KeyError: 'createdWarnings'`.

**Conclusion:** `demo-two-actor.sh` does **not** dynamically inspect merge results. It executes `git merge-tree` as an unverified cosmetic side-effect, unconditionally asserts that a conflict occurred, and sends a static pre-baked payload. If the actual git heads deviate, the script crashes.

---

### 3.2 Mutant 2: Test Suite Failure / Zero Tests Collected

**Objective:** Verify whether the demo harness detects test failures or collects real test execution metrics.

**Mutation Applied:** In `mutant-2/demo-two-actor.sh`, Step 9 (line 446) was mutated so that instead of running 22 tests, the command outputs 0 collected tests:
```bash
TEST_OUTPUT=$(python3 -c "print('Ran 0 tests in 0.000s\n\nOK')")
```

**Observation:**
1. Line 447 executed:
   ```bash
   echo "${TEST_OUTPUT}" | grep -E "(Ran 22 tests|OK)"
   ```
2. Because Python's `unittest` outputs `OK` even when 0 tests are selected, the regex matched `OK`.
3. Line 448 logged:
   ```
   [PASS] Test attestation passed: 22/22 unit tests collected and passed cleanly
   ```
4. Step 10 proceeded to submit `CHECK_CLEAN_PAYLOAD` containing handwritten evidence:
   ```json
   "coverage": {
     "pairs_checked": 1,
     "tests_collected": 22
   },
   "results": [{
     "status": "clean",
     "evidence": {
       "tests": {
         "collected": 22,
         "passed": 22,
         "failed": 0,
         "errors": 0,
         "exit_code": 0
       }
     }
   }]
   ```
5. The demo ran to completion with **Exit Code 0** and emitted `demo-receipt.json` certifying:
   `"unit_tests_passed": "22/22"`.

**Conclusion:** The test attestation is completely unparsed and bypassed by the permissive grep regex `(Ran 22 tests|OK)`. A broken, empty, or single-test run is falsely reported as 22/22 clean passing tests.

---

### 3.3 Mutant 3: Coordinator Fallback on Missing/Zero `testsCollected`

**Objective:** Verify behavior of `scripts/coordinator-local.mjs` line 506 when submitted with malformed or zero-count test evidence.

**Mutation Applied:** A Python harness sent two HTTP requests to a live instance of `scripts/coordinator-local.mjs`:
- Request A: `evidence.tests.collected = 0`
- Request B: `evidence = {}` (no tests object)

**Observation:**
```json
// Response to Request A (collected: 0):
{
  "pair": ["agent-a", "agent-b"],
  "status": "clean",
  "testsCollected": 22
}

// Response to Request B (evidence: {}):
{
  "pair": ["agent-c", "agent-d"],
  "status": "clean",
  "testsCollected": 22
}
```

**Cause Analysis:**
Line 506 in `scripts/coordinator-local.mjs`:
```javascript
testsCollected: result.evidence?.tests?.collected || 22,
```
In JavaScript, `0` is falsy. Therefore, `0 || 22` evaluates to `22`. When `result.evidence.tests` is omitted, `undefined || 22` also evaluates to `22`.

**Conclusion:** `scripts/coordinator-local.mjs` explicitly falsifies missing or zero-count test metrics to `22`, directly violating the CONTRACT v0.1 specification and the L3 Radar Engine contract (`radar/engine.py`), where 0 collected tests must result in `status: "unknown"`.

---

## 4. Actor Labeling & Replay Truth Audit

### 4.1 Audit of Script and Documentation Claims

In `scripts/demo-two-actor.sh`:
- Line 19: `# - Two autonomous actors: Actor Alpha (task-0002) and Actor Beta (task-0001)`
- Line 274: `log_step "Step 5: Simulating Autonomous Actor Beta (Task task-0001)"`
- Line 316: `log_step "Step 6: Simulating Autonomous Actor Alpha (Task task-0002)"`
- Line 435: `log_step "Step 9: Actor Alpha Resolves Collision via Merge (Commit eada0e4)"`
- Line 591: `DEMO COMPLETE: Two-Actor Concurrent Warning Lifecycle PASSED`

In `research/antigravity/recovery/DEMO-RUNBOOK.md`:
- Line 19: *"The demo showcases two autonomous actors—Actor Beta (actor-beta-0001) and Actor Alpha (actor-alpha-0002)—collaborating on the agent_branches client codebase."*
- Line 62: *"Phase 2: Pre-Merge Advisory Collision Detection — R detects textual collision in client.py & test_client.py"*

### 4.2 Replay Reality vs. Presentation

In reality:
1. No autonomous agent execution, reasoning, or tool-calling occurs.
2. The script executes sequential, deterministic git checkouts of historical commits:
   - `ec5030c` (historical base commit)
   - `d566898` (historical commit authored by human/agent during earlier spike)
   - `9ec79db` (historical commit authored by human/agent during earlier spike)
   - `eada0e4` (historical resolution merge commit)
3. The merge evaluation is hardcoded to output fixed JSON files.
4. Calling this "Simulating Autonomous Actors" without prominent upfront disclosure misrepresents a static contract fixture replay as dynamic agent behavior.

**Requirement:** The script header, stdout banner, and runbook must explicitly and prominently label the demonstration as:
> **Deterministic Historical Commit Replay & Protocol Contract Harness (Contract Replay Fixture)**
> Replaying historical commit trace `ec5030c -> {9ec79db, d566898} -> eada0e4`.

---

## 5. Credential & Environment Hygiene Audit

| Area | Observation | Status |
|---|---|---|
| **Stdout / Stderr Logging** | Dynamic bearer secrets minted via `secrets.token_hex(20)`. No raw secrets printed to terminal. | **PASS** |
| **Daemon Log Files** | `sidecar.log` and `coordinator.log` contain no bearer tokens or private key material. | **PASS** |
| **Git Credentials on Disk** | Lines 256, 302, 344 execute `git config http.extraHeader "Authorization: Bearer <token>"`. This writes plaintext bearer tokens into `.git/config` on disk with default permissions `0664`. | **DEFECT:** Should use per-command `git -c "http.extraHeader=..."` instead of writing secrets to disk. |
| **State File Permissions** | `coordinator-state.json` contains bearer tokens and is created with mode `0664` (governed by umask) instead of mode `0600`. | **DEFECT:** Must enforce `0600` on state files containing tokens. |
| **Scratch Root Relative Path Bug** | Line 56 sets `SCRATCH_ROOT="${1:-...}"`. If a caller passes a relative path (e.g. `./scratch`), subsequent `cd "${ALPHA_WT}"` causes relative references to fail with `cd: ... No such file or directory`. | **DEFECT:** Must canonicalize using `SCRATCH_ROOT="$(mkdir -p "$1" && cd "$1" && pwd)"`. |
| **Script Directory Portability** | Line 53 defines `REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"`, which fails if the script is copied or executed from another location. | **DEFECT:** Should use `git rev-parse --show-toplevel`. |
| **System `/tmp` Growth** | `TMPDIR` redirected to scratch root. Verified 0 bytes created in `/tmp`. | **PASS** |
| **Scratch Budget** | Scratch directory footprint measured at ~15 MB (well under 512 MB limit). | **PASS** |

---

## 6. Required Remediation Plan

To clear this review and achieve acceptance, the following concrete modifications must be made:

### Remediation 1: Verify Real Merge Conflicts in `scripts/demo-two-actor.sh`
Replace lines 360–403 with dynamic verification:
```bash
# 1. Dynamically retrieve current heads from coordinator or worktrees
ALPHA_HEAD=$(cd "${ALPHA_WT}" && git rev-parse HEAD)
BETA_HEAD=$(cd "${BETA_WT}" && git rev-parse HEAD)

# 2. Run git merge-tree using the dynamic heads and base
cd "${ALPHA_WT}"
MERGE_OUTPUT=$(git merge-tree "${BASE_SHA}" "${ALPHA_HEAD}" "${BETA_HEAD}" 2>&1 || true)

# 3. Fail if there is no conflict detected
if ! echo "${MERGE_OUTPUT}" | grep -q "<<<<<<<"; then
  log_error "Expected merge conflict between Alpha (${ALPHA_HEAD}) and Beta (${BETA_HEAD}), but merge-tree was clean!"
  exit 1
fi

# 4. Extract actual conflicting files from merge-tree output
CONFLICTING_FILES=$(echo "${MERGE_OUTPUT}" | grep -E "^\+\+\+ b/" | sed 's/+++ b\///' | sort -u | python3 -c "import sys, json; print(json.dumps([l.strip() for l in sys.stdin if l.strip()]))")
```

### Remediation 2: Parse Test Output & Reject Zero Counts in `scripts/demo-two-actor.sh`
Replace lines 446–495 with strict metric extraction:
```bash
# 1. Run unittest and capture exit code safely under set -e
set +e
TEST_RAW_OUTPUT=$(python3 -m unittest -v tests/test_client.py 2>&1)
TEST_EXIT_CODE=$?
set -e

# 2. Extract test count strictly using regex
TESTS_RAN=$(echo "${TEST_RAW_OUTPUT}" | grep -E "^Ran [0-9]+ test" | awk '{print $2}')
if [ -z "${TESTS_RAN}" ] || [ "${TESTS_RAN}" -eq 0 ] || [ ${TEST_EXIT_CODE} -ne 0 ]; then
  log_error "Test attestation failed! Exit code: ${TEST_EXIT_CODE}, tests ran: ${TESTS_RAN:-0}"
  echo "${TEST_RAW_OUTPUT}"
  exit 1
fi

log_success "Test attestation passed: ${TESTS_RAN}/${TESTS_RAN} unit tests collected and passed cleanly"
```
And in `CHECK_CLEAN_PAYLOAD`, dynamically interpolate `${TESTS_RAN}` instead of hardcoding `22`.

### Remediation 3: Fix Coordinator `testsCollected` Fallback in `scripts/coordinator-local.mjs`
Replace line 506 in `scripts/coordinator-local.mjs`:
```javascript
// BEFORE:
testsCollected: result.evidence?.tests?.collected || 22,

// AFTER:
testsCollected: typeof result.evidence?.tests?.collected === "number" 
  ? result.evidence.tests.collected 
  : (typeof result.testsCollected === "number" ? result.testsCollected : undefined),
```

### Remediation 4: Fix Authentication Bypass in `scripts/coordinator-local.mjs`
Remove lines 143–146 in `scripts/coordinator-local.mjs`. Do not allow requests to bypass bearer token authentication simply because `task_id` or `agent` is present in the request body. All mutating requests (`/warnings/:id/ack`, `/tasks/:id/tests`) must require a valid bearer token matching the agent or admin.

### Remediation 5: Accurate Replay Disclosure
Update `scripts/demo-two-actor.sh` and `DEMO-RUNBOOK.md` to state clearly:
- "Mode: Deterministic Historical Commit Replay & Protocol Contract Harness"
- Disclose that `9ec79db`, `d566898`, and `eada0e4` are historical commits rather than live agent reasoning runs.

### Remediation 6: Path and Credential Fixes
1. In `scripts/demo-two-actor.sh`, canonicalize `SCRATCH_ROOT`:
   ```bash
   SCRATCH_ARG="${1:-${REPO_ROOT}/.local/scratch/demo-runbook-harness}"
   mkdir -p "${SCRATCH_ARG}"
   SCRATCH_ROOT="$(cd "${SCRATCH_ARG}" && pwd)"
   ```
2. Pass git bearer tokens using `-c http.extraHeader="Authorization: Bearer ..."` on push commands, avoiding writing tokens to `.git/config` on disk.
3. In `scripts/coordinator-local.mjs`, write state files with mode `0600` (`writeFileSync(this.path, ..., { mode: 0o600 })`).

---

## 7. Compliance with Review Invariants

- **Memory Cap:** Process execution strictly contained within 1500 MB cooperative slice (`ulimit -v 1500000`).
- **Scratch Budget:** Maximum disk usage during review: 15 MB (limit: 512 MB). Scratch directory located strictly at `.local/scratch/demo-provenance-review/` (mode `0700`).
- **Zero `/tmp` Growth:** Verified 0 bytes created in system `/tmp`.
- **Git State:** Untouched working tree; zero git commits performed by subagent.

---
*End of Review Report REV-DEMO-RUNBOOK-HARNESS.md*
