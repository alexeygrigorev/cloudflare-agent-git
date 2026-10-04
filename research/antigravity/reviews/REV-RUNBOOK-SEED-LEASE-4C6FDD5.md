# REV-RUNBOOK-SEED-LEASE-4C6FDD5 — Independent Review: Git Seed-Lease Runbook, Smart HTTP Auth Demarcation & Memory Boundaries

- **Reviewer:** Independent Runbook Seed-Lease Packaging Reviewer (tag: `runbook-seed-lease-reviewer`).
- **Dispatched by:** `antigravity-head` (`46fdb644`), under Codex Principal C1740 and C1741 directives:
  > *"C1740/C1741: independent currentpin reviewer inspect typedknownscope/actualGitsemantics and auth/placeholders/runbookgaps; ownerREADMErepairwithinexistingtasknot anotherseededproofoverclaim. Tests shouldverify actualsidecarSmartHTTP path/auth notjustlocalbarelease if runbook claimslivecompatibility."*
- **As-of:** 2026-10-04, Europe/Berlin.
- **Target Commit:** [`4c6fdd55131b454ed99dee5dbafb31a3c3dd251e`](file:///home/alexey/git/cloudflare-agent-git/commit/4c6fdd5) (`4c6fdd5`) on branch `proto/runbook-seed-lease` (`origin/proto/runbook-seed-lease`).
  - Tree SHA: `099256fd2db08a126675077c90649fff7800e01f` (Audit Note: caller prompt noted `099e048...`, verified empirically as `099256f...`).
  - Author: Alexey Grigorev (`alexey.s.grigoriev@gmail.com`).
  - Subject: `docs(runbook): seed-lease canonical push, INTEGRATION_DIR parameterization, 0600 .env.local and argv token hygiene notes (C1725/C1728)`.
- **Base Commit:** [`592a8ee7f18e578d716439dfb5cb672c9423793f`](file:///home/alexey/git/cloudflare-agent-git/commit/592a8ee) (`592a8ee`) on `origin/proto/pilot-realnode-maintenance`.
- **Target Report Audited:** [`research/antigravity/recovery/REPORT-RUNBOOK-SEED-LEASE.md`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/recovery/REPORT-RUNBOOK-SEED-LEASE.md) (commit `0f32239` on `origin/main`).
- **Deliverable Path:** [`research/antigravity/reviews/REV-RUNBOOK-SEED-LEASE-4C6FDD5.md`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/reviews/REV-RUNBOOK-SEED-LEASE-4C6FDD5.md).
- **Scratch Workspace:** `.local/scratch/seed-lease-review/` (mode `0700`, measured disk: 1.4 MB $\ll$ 512 MB, `TMPDIR` strictly within scratch root, zero `/tmp` growth).
- **Verdict:** **REQUEST_CHANGES** (Drop-in remediation patch provided; the underlying Git lease semantics and `INTEGRATION_DIR` parameterization are empirically verified, but the documentation in `4c6fdd5:README.md` contains critical defects that break live operation: confusing `$SIDECAR_TOKEN` with repository write tokens, non-executable schematic placeholders, and overgeneralized Wasm virtual memory claims).

---

## 1. Executive Summary & Verdict

This independent review evaluates commit `4c6fdd5` on `proto/runbook-seed-lease` and accompanying verification report `REPORT-RUNBOOK-SEED-LEASE.md` (`0f32239`). Commit `4c6fdd5` attempts to establish an operator runbook for running the compiled Node coordinator alongside the Git Smart HTTP sidecar, focusing on `INTEGRATION_DIR` parameterization, mode `0600` `.env.local` files, safe canonical repository pushing using Git seed leases, and token argv hygiene.

While the conceptual decision to employ exact Git commit leases (`--force-with-lease=refs/heads/main:<seed_sha>`) rather than blind force-pushes is sound and fully verified by our testbed, the runbook as packaged in `4c6fdd5:README.md` exhibits several critical documentation and operational gaps that prevent direct, reliable execution by operators and automated harnesses.

### Key Audit Findings

1. **Git Seed-Lease Semantics Verified Empirically (T0–T2 Ladder + Mutation Test):**
   - In an isolated scratch testbed replicating sidecar repository seeding (`hash-object` $\rightarrow$ `mktree` $\rightarrow$ `commit-tree` $\rightarrow$ `update-ref`), the 3-step ladder executed cleanly:
     - **T0 (Naive Push):** Plain push of unrelated history failed non-fast-forward with exit code 1; canonical ref was preserved.
     - **T1 (Positive Seed Lease):** `git push --force-with-lease=refs/heads/main:$seed_sha` succeeded with exit code 0; canonical ref matched local HEAD.
     - **T2 (Negative Stale Lease):** After canonical `main` advanced to an unexpected commit, pushing with the original seed lease failed closed (`stale info`, exit 1); advanced commit was preserved.
   - **Mutation Test:** Replacing `--force-with-lease` with unconstrained `--force` clobbered the advanced commit. The mutant was cleanly killed by the T2 negative assertion.

2. **Smart HTTP Authorization Path Failure in Runbook Line 199:**
   - Testing against the live `sidecar.mjs` daemon over HTTP revealed a severe flaw in the runbook's token advice.
   - Line 199 advises configuring Git with `Authorization: Bearer $SIDECAR_TOKEN`.
   - However, `sidecar.mjs` (`authorizeGit`) strictly checks tokens against minted repository tokens in `this.tokens.find(plaintext)`. It explicitly rejects `$SIDECAR_TOKEN` for Git Smart HTTP actions (`401 Unauthorized` / exit 128 when prompts are disabled).
   - Git Smart HTTP push requires a minted **repository write token** (`$REPO_WRITE_TOKEN`), not the administrative control bearer (`$SIDECAR_TOKEN`).

3. **Schematic Placeholders vs. Executable Shell:**
   - Lines 174–176 specify `seed_sha=<seedCommit from the createRepo response>` and `<remote-url-from-createRepo>`.
   - Pasting this into a POSIX shell yields syntax errors or invalid redirection.
   - The runbook omits the concrete API invocation (`POST /api/repos` on the sidecar or `POST /setup` on the coordinator) and lacks copy-pasteable JSON extraction commands (via standard Python `json.load`).

4. **Wasm Trap Handler & Memory Generalization:**
   - Lines 147–148 claim `--disable-wasm-trap-handler` and `--max-old-space-size=256` "prevent virtual address space reservation exhaustion under process memory limits (C1682)".
   - Empirical investigation (C1682, C1685) showed that the full compiled coordinator under strict virtual memory limit `ulimit -v 1500000` deterministically `SIGABRT`s on its first served request (`VmSize` reaches $\sim 1,517,240$ kB).
   - The minimal working envelope requires `ulimit -v 1530000` alongside `--disable-wasm-trap-handler` and `--max-old-space-size=256`. Furthermore, virtual address limits (`RLIMIT_AS`) must not be confused with physical memory (RSS $\sim 62$–$77$ MB) or the shared 1500 MiB cgroup budget.

5. **Epistemic Demarcation of Platform Claims:**
   - `REPORT-RUNBOOK-SEED-LEASE.md` claims "the sandbox duplicate-delivers commands; two early runs collided...".
   - The observed fact was an interleaving of executions colliding on a shared scratch path. Attributing this to harness/platform duplicate-delivery is an unproven causal hypothesis. The true cause must be labeled **CAUSE UNKNOWN**, with directory isolation acknowledged as the pragmatic mitigation.

**Verdict: REQUEST_CHANGES.** The runbook cannot be accepted in its current state (`4c6fdd5`). A verified, drop-in remediation unified diff that repairs all gaps and passes `git apply --check` is provided in Section 8 of this report.

---

## 2. Environmental Invariants & Resource Accounting

The review adhered strictly to repository resource and security directives:
- **Scratch Workspace:** `/home/alexey/git/cloudflare-agent-git/.local/scratch/seed-lease-review/` initialized with mode `0700` (`drwx------`).
- **Disk Budget:** Peak measured disk consumption was **1.4 MB**, well below the 512 MB ceiling. No pre-existing worktrees or caches were modified or deleted.
- **Process & Temporary Isolation:** `TMPDIR` was explicitly set to `.local/scratch/seed-lease-review/tmp`. Zero bytes and zero files were written to `/tmp`.
- **Memory Invariant:** Background test processes (`sidecar.mjs` and Git subprocesses) operated with RSS under 60 MB, strictly complying with the cooperative 1500 MB memory slice.
- **Credential Hygiene:** No raw secrets, minted bearer tokens (`art_v1_...`), or unredacted passwords exist in this report or repository commits. All examples use standard variable references (`$SIDECAR_TOKEN`, `$REPO_WRITE_TOKEN`).
- **Publication Guard Validation:** Verified clean via `research/antigravity/tooling/publication_guard.py` (exit code 0).

---

## 3. Pinned Source Audit (`4c6fdd5` on `proto/runbook-seed-lease`)

### 3.1 Commit Metadata & Scope
```
commit 4c6fdd55131b454ed99dee5dbafb31a3c3dd251e
parent 592a8ee7f18e578d716439dfb5cb672c9423793f
tree   099256fd2db08a126675077c90649fff7800e01f
author Alexey Grigorev <alexey.s.grigoriev@gmail.com> Sun Oct 4 07:55:25 2026 +0200
```

- **Tree SHA Discrepancy Note:** The assignment prompt referenced `tree SHA 099e048...`. Git inspection of `4c6fdd5` confirms the actual tree hash is `099256fd2db08a126675077c90649fff7800e01f`. This is a minor typographical deviation in the caller prompt; the commit object itself is verified authentic and intact.
- **Diff Scope:** Strictly scoped to a single file:
  ```
   README.md | 90 ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++-----
   1 file changed, 83 insertions(+), 7 deletions(-)
  ```
  No code, build artifacts, or unexpected repository files were touched.

### 3.2 Report Ingestion (`REPORT-RUNBOOK-SEED-LEASE.md`, commit `0f32239`)
The associated report was reviewed in full. It accurately documents:
1. Rewriting the runbook to use `INTEGRATION_DIR` parameterization.
2. Generating `.env.local` under `umask 077` (mode `0600`).
3. Introducing exact seed leases to prevent blind force-pushes.
4. Noting argv token exposure via `/proc/<pid>/cmdline`.
5. Local bare scratch tests (T0, T1, T2) using Git 2.43.0.

However, the report failed to identify the token scope mismatch in its own documentation and overclaimed platform behavior regarding command delivery.

---

## 4. Independent Empirical Verification: Git Seed-Lease Ladder & Mutation Testing

To independently verify the core Git lease claims, a dedicated test script (`test_seed_lease.sh`) was executed inside `.local/scratch/seed-lease-review/run-testbed/` (mode `0700`).

### 4.1 Testbed Initialization
The canonical bare repository was seeded using the exact sequence executed by `sidecar.mjs`:
```bash
git init --bare --initial-branch main canonical.git
blob=$(echo "agent-branches baseline" | git -C canonical.git hash-object -w --stdin)
tree=$(printf "100644 blob %s\tREADME.md\n" "$blob" | git -C canonical.git mktree)
seed_sha=$(git -C canonical.git commit-tree "$tree" -m "chore: seed canonical baseline")
git -C canonical.git update-ref refs/heads/main "$seed_sha"
```
A local work repository was initialized with an independent, unrelated commit history (`local_head`).

### 4.2 Ladder Execution Results

| Test Step | Command Executed | Expected Outcome | Observed Outcome | Exit Code | Status |
| :--- | :--- | :--- | :--- | :---: | :---: |
| **T0 (Naive Push)** | `git push origin main` | Push rejected non-fast-forward; seed preserved | `! [rejected] main -> main (fetch first)` | `1` | **PASS** |
| **T1 (Positive Lease)** | `git push --force-with-lease=refs/heads/main:$seed_sha origin HEAD:refs/heads/main` | Push succeeds; canonical ref matches `local_head` | `+ <seed_sha>...<local_head> HEAD -> main (forced update)` | `0` | **PASS** |
| **Ref Advance** | `git update-ref refs/heads/main $adv_sha` | Canonical advanced by external actor | Ref points to `$adv_sha` | `0` | **PASS** |
| **T2 (Stale Lease)** | `git push --force-with-lease=refs/heads/main:$seed_sha origin HEAD:refs/heads/main` | Push rejected (`stale info`); advanced ref preserved | `! [rejected] HEAD -> main (stale info)` | `1` | **PASS** |

Both ref preservation checks passed:
- In T0, canonical `refs/heads/main` remained locked at `$seed_sha`.
- In T2, canonical `refs/heads/main` remained locked at `$adv_sha`, preventing silent history destruction.

### 4.3 Mutation Testing (Mutant: Unconstrained `--force`)
The test was mutated to execute `git push --force` instead of `--force-with-lease`:
```bash
git push --force origin HEAD:refs/heads/main
```
- **Observed Result:** Push succeeded (exit code 0), and canonical `refs/heads/main` was forcibly updated from `$adv_sha` to `$local_head2`.
- **Conclusion:** Unconstrained `--force` destroys concurrent history without warning. The safety property verified by T2 killed the mutant completely, proving that `--force-with-lease` is essential.

---

## 5. Live Sidecar Smart HTTP Verification: Auth Demarcation Proof

Pursuant to Codex Principal directives C1740/C1741, testing was extended beyond local filesystem remotes to the **actual Git Smart HTTP sidecar daemon** (`prototype/local-artifacts/sidecar.mjs`).

### 5.1 Test Execution Architecture
1. `sidecar.mjs` was started in scratch with `SIDECAR_PORT=9872` and `SIDECAR_TOKEN="ctrl_token_dummy_12345"`.
2. A canonical repository `live-canonical` was provisioned via `POST /api/repos`:
   ```json
   {
     "name": "live-canonical",
     "remote": "http://127.0.0.1:9872/git/live-canonical.git",
     "defaultBranch": "main",
     "token": "art_v1_...[REDACTED]",
     "seedCommit": "4de918430aa92b39c1ffd1d5aa0bcbc9437a342f"
   }
   ```
3. A local work tree was prepared with unrelated history.

### 5.2 Smart HTTP Empirical Results

```
=== TEST A: Buggy README Line 199 - Push with SIDECAR_TOKEN instead of WRITE_TOKEN ===
Buggy push exit code: 128
fatal: could not read Username for 'http://127.0.0.1:9872': terminal prompts disabled
CONFIRMED: Smart HTTP rejects push with SIDECAR_TOKEN (exit 128)!

=== TEST B: Smart HTTP T0 - Naive push with WRITE_TOKEN (unrelated history) ===
Smart HTTP T0 exit code: 1
To http://127.0.0.1:9872/git/live-canonical.git
 ! [rejected]        HEAD -> main (fetch first)
CONFIRMED: Smart HTTP naive push fails non-fast-forward (exit 1)!

=== TEST C: Smart HTTP T1 - Push with WRITE_TOKEN and --force-with-lease against SEED_SHA ===
Smart HTTP T1 exit code: 0
To http://127.0.0.1:9872/git/live-canonical.git
 + 4de9184...58e0654 HEAD -> main (forced update)
CONFIRMED: Smart HTTP positive seed lease succeeds (exit 0)!

=== TEST D: Advance remote ref concurrently ===
Advanced remote canonical ref to: 7f9dbd4166c589cd21c2657edcc6fd9d590a9f1e

=== TEST E: Smart HTTP T2 - Negative push with stale SEED_SHA lease ===
Smart HTTP T2 exit code: 1
To http://127.0.0.1:9872/git/live-canonical.git
 ! [rejected]        HEAD -> main (stale info)
CONFIRMED: Smart HTTP stale seed lease fails closed (exit 1), advanced ref preserved!
```

### 5.3 Architectural Cause of the Line 199 Defect
In `sidecar.mjs`:
- The sidecar control bearer (`$SIDECAR_TOKEN`) is validated strictly for routes starting with `/api/` (lines 586–593):
  ```javascript
  if (path.startsWith("/api/")) {
    if (sidecar.sharedToken) {
      const header = req.headers.authorization ?? "";
      const presented = header.toLowerCase().startsWith("bearer ") ? header.slice(7).trim() : null;
      if (presented !== sidecar.sharedToken) {
        sendJson(res, 401, { error: "sidecar bearer token required" });
        return;
      }
    }
  ```
- Conversely, Git Smart HTTP requests (`/git/<repo>.git/...`) route to `handleGitCgi` $\rightarrow$ `authorizeGit` (lines 387–412):
  ```javascript
  authorizeGit(repoName, req, needsWrite) {
    ...
    let record = plaintext ? this.tokens.find(plaintext) : null;
    ...
    if (!record || record.repo !== repoName) {
      throw new HttpError(401, "git authentication required: valid per-repo token");
    }
    if (needsWrite && record.scope !== "write") {
      throw new HttpError(401, "write token required for push");
    }
  }
  ```
  `authorizeGit` queries `this.tokens`, which contains only minted repository tokens. Because `$SIDECAR_TOKEN` is a global control bearer and is never stored in `this.tokens`, passing `$SIDECAR_TOKEN` to Git Smart HTTP triggers a `401 Unauthorized` response. When non-interactive prompts are configured (`GIT_TERMINAL_PROMPT=0`), Git aborts with exit code 128.

**Conclusion:** The runbook's instruction to set `git config --local http.<remote-url>.extraHeader "Authorization: Bearer $SIDECAR_TOKEN"` is completely defective. It breaks the developer workflow and fails closed on the real sidecar.

---

## 6. Critical Runbook Gap Analysis in `4c6fdd5:README.md`

### 6.1 Schematic Placeholders vs. Executable Shell
- **Defect:** Lines 174–176 instruct the operator:
  ```bash
  seed_sha=<seedCommit from the createRepo response>
  git push --force-with-lease=refs/heads/main:"$seed_sha" \
      <remote-url-from-createRepo> HEAD:refs/heads/main
  ```
- **Consequences:** 
  - Un-interpolated angle brackets cause syntax errors or redirection failure in bash.
  - The text fails to specify *how* `createRepo` was invoked. An operator must know whether to call the sidecar HTTP API directly (`POST /api/repos` with `$SIDECAR_TOKEN`) or the coordinator setup endpoint (`POST /setup` with `$ADMIN_TOKEN`).
- **Remediation:** Provide complete, copy-pasteable bash commands using Python's standard `json` module to parse the response payload and store `SEED_SHA`, `REMOTE_URL`, and `REPO_WRITE_TOKEN`.

### 6.2 Token Authorization Demarcation
- **Defect:** Line 199 instructs:
  ```bash
  git config --local http.<remote-url>.extraHeader "Authorization: Bearer $SIDECAR_TOKEN"
  ```
- **Consequences:** Conflates the sidecar administrative bearer with the repository write token, resulting in HTTP 401 failures during push.
- **Remediation:** Explicitly delineate the two credential scopes:
  1. Administrative Control Bearer (`$SIDECAR_TOKEN`): for `/api/*` endpoints.
  2. Repository Write Bearer (`$REPO_WRITE_TOKEN`): for Git Smart HTTP push operations.

### 6.3 Wasm Trap Handler Flag Generalization & Memory Limits
- **Defect:** Lines 147–148 state:
  ```bash
  # Note: On Node 24+, --disable-wasm-trap-handler and --max-old-space-size=256
  # prevent virtual address space reservation exhaustion under process memory limits (C1682).
  ```
- **Consequences:** 
  - Overgeneralizes the mitigation. Empirical measurements in C1682 and C1685 proved that passing the flag alone does not permit running under strict virtual memory limits of `1500000` kB; the compiled coordinator `SIGABRT`s on its first request because serving requires `VmSize` $\approx 1,517,240$ kB.
  - Leaves operators unaware that `ulimit -v 1530000` is required.
  - Fails to distinguish between virtual address limits (`ulimit -v` / `RLIMIT_AS`) and actual physical resident memory (RSS $\sim 62$–$77$ MB) or the physical 1500 MiB cgroup budget.
- **Remediation:** Document the exact empirical envelope (`--disable-wasm-trap-handler --max-old-space-size=256` + `ulimit -v 1530000`) and clearly state the distinction between virtual address reservations and physical cgroup limits.

### 6.4 Token Argv Exposure & Mode `0600` Trade-Offs
- **Evaluation:** 
  - The documentation accurately notes that tokens in command-line arguments are visible in `/proc/<pid>/cmdline` and `ps aux`.
  - However, the example `git config --local http.<remote-url>.extraHeader "Authorization: Bearer $SIDECAR_TOKEN"` still suffers from:
    1. One-shot argv exposure during the `git config` call itself.
    2. Syntax parsing defects if `<remote-url>` contains unquoted dots or slashes (Git requires subsection quoting: `http."$REMOTE_URL".extraHeader`).
    3. The wrong token value (noted above).
  - The `curl` example using `printf 'header = ...' > .curl-scratch` similarly exposes the token in argv to `printf`.
- **Remediation:** Recommend using standard input (`cat <<EOF`) to write mode `0600` configuration files without argv exposure, and correctly quote the git configuration subsection.

---

## 7. Epistemic Demarcation & Hypothesis Evaluation

### 7.1 "Sandbox Duplicate-Delivery" Hypothesis (REPORT-RUNBOOK-SEED-LEASE.md §2)
- **Report Claim:**
  > *"Environment quirk, disclosed: the sandbox duplicate-delivers commands; two early runs collided on a shared scratch directory... Remote ref confirmed at 4c6fdd5 via git ls-remote (first delivery succeeded; the duplicate-delivered second attempt was rejected with 'reference already exists')."*
- **Epistemic Evaluation:**
  - **Empirical Observation:** Two commands executed in the same scratch directory, and a git push was attempted twice against the same ref.
  - **Causal Leap:** Attributing this behavior to the platform/sandbox "duplicate-delivering commands".
  - **Demarcation:** There is no evidence of platform-level message duplication. The observed duplicate execution is consistent with known causes such as agent sub-shell retries, overlapping asynchronous task execution, or script re-invocation without directory cleanup.
  - **Classification:** **CAUSE UNKNOWN (UNPROVEN PLATFORM HYPOTHESIS)**. The isolation fix (`run-<ns>-<pid>`) is an effective software defense against concurrent execution collisions, regardless of cause.

### 7.2 Memory Limits: Virtual Address Space vs. Physical cgroups
- **Report Claim:**
  > *"Memory cap: ulimit -v 1500000 inside the test shell. Cooperative 1500M convention respected; no coordinator/sidecar processes launched."*
- **Epistemic Evaluation:**
  - `ulimit -v 1500000` sets the virtual memory limit (`RLIMIT_AS`) to $1,500,000$ kB ($\sim 1.43$ GiB).
  - Virtual address space allocation does not consume physical RAM. V8 reserves 4 GiB of virtual address space by default for WebAssembly trap handlers and heap sandboxing.
  - A process can consume $1.4$ GiB of virtual address space while its physical resident set size (RSS) is only $40$ MB.
  - Conversely, `ulimit -v` does not prevent multiple concurrent processes from exhausting physical host memory.
  - **Demarcation:** Virtual memory ceilings (`ulimit -v`) must be explicitly distinguished from physical memory enforcement (`cgroups v2 memory.max` or cooperative RSS monitoring).

---

## 8. Complete Remediation Unified Diff

The following clean unified diff remediates all identified gaps in `README.md` against commit `4c6fdd55131b454ed99dee5dbafb31a3c3dd251e`.

### 8.1 Verification of Remediation Patch
The patch was tested in the scratch checkout detached at `4c6fdd5`:
```bash
git apply --check remediation.patch
# Exit code: 0 (clean application)
```

### 8.2 Remediated Patch Content

> **Publication Guard Note:** In the diff below, line 204 reflects `<sidecar_token>` in place of `%s` to comply with publication credential rules. The bit-identical raw patch is preserved at `.local/scratch/seed-lease-review/remediation.patch` and passes `git apply --check` with exit code 0.

````diff
diff --git a/README.md b/README.md
index 8ba78d4..3d3b8f3 100644
--- a/README.md
+++ b/README.md
@@ -145,7 +145,11 @@ node "$INTEGRATION_DIR/prototype/local-artifacts/sidecar.mjs"
 
 # Terminal 2 — Launch the compiled Node coordinator daemon
 # Note: On Node 24+, --disable-wasm-trap-handler and --max-old-space-size=256
-# prevent virtual address space reservation exhaustion under process memory limits (C1682).
+# provide an observed empirical mitigation against V8 virtual address reservation
+# exhaustion (C1682, C1685). Under virtual address space limits, serving requests
+# requires `ulimit -v 1530000` (at strict `-v 1500000` VmSize reaches ~1,517,240 kB
+# and aborts on the first served request); physical RSS remains compact (~62–77 MB,
+# well within the shared 1500 MiB cgroup budget).
 set -a; . ./.env.local; set +a
 export PORT=8787
 export HOST=127.0.0.1
@@ -159,24 +163,49 @@ node --disable-wasm-trap-handler --max-old-space-size=256 \
 `.env.local` is scratch-local: keep it out of Git and regenerate it per stack
 session instead of reusing stale tokens.
 
-#### Pushing work to a canonical repo: exact seed lease
+#### Provisioning and pushing: exact seed lease & token demarcation
 
-The sidecar's `createRepo()` initializes every canonical bare repo with a
-synthetic seed commit (`chore: seed canonical baseline` on `main`) and returns
-its SHA as `seedCommit` next to the remote URL and a minted write token. A
-freshly created canonical repo is therefore **not** empty: pushing your
-unrelated local history (e.g. a branch based on `b2df985`) is a
-non-fast-forward. Do **not** recover with an unconstrained `git push --force`
-— that silently clobbers anything any other actor lands on `main`. Push with
-an exact lease on the seed commit instead:
+Every canonical repository is initialized by the sidecar with a synthetic
+seed commit (`chore: seed canonical baseline` on `main`) and is **not** empty:
+pushing unrelated local history is non-fast-forward. Do **not** recover with
+an unconstrained `git push --force` — that silently clobbers any concurrent
+updates. Push with an exact lease on the seed commit instead.
+
+##### Token Scope Demarcation
+- **Sidecar Control Bearer (`$SIDECAR_TOKEN`):** Grants access to administrative
+  HTTP endpoints (`POST /api/repos`, `/api/repos/:name/tokens`). It is **rejected**
+  by Git Smart HTTP (exit 128 / 401 Unauthorized).
+- **Repository Write Bearer (`$REPO_WRITE_TOKEN`):** Minted per-repository token
+  (returned directly by `POST /api/repos` or minted via `POST /api/repos/:name/tokens`).
+  Required for Git Smart HTTP push (`git-receive-pack`).
+
+##### Executable Provisioning & Lease Push Workflow
 
 ```bash
-seed_sha=<seedCommit from the createRepo response>
-git push --force-with-lease=refs/heads/main:"$seed_sha" \
-    <remote-url-from-createRepo> HEAD:refs/heads/main
+# 1. Provision canonical repo on sidecar using the control bearer ($SIDECAR_TOKEN)
+REPO_JSON=$(curl -s -f -X POST "http://127.0.0.1:$SIDECAR_PORT/api/repos" \
+    -H "Authorization: Bearer $SIDECAR_TOKEN" \
+    -H "Content-Type: application/json" \
+    -d '{"name":"canonical"}')
+
+# 2. Extract seed commit SHA, Smart HTTP remote URL, and repository write token
+SEED_SHA=$(python3 -c 'import sys, json; print(json.load(sys.stdin)["seedCommit"])' <<< "$REPO_JSON")
+REMOTE_URL=$(python3 -c 'import sys, json; print(json.load(sys.stdin)["remote"])' <<< "$REPO_JSON")
+REPO_WRITE_TOKEN=$(python3 -c 'import sys, json; print(json.load(sys.stdin)["token"])' <<< "$REPO_JSON")
+
+# (Alternative lifecycle: if provisioned via coordinator POST /setup with $ADMIN_TOKEN,
+# fetch canonical name from setup response and mint REPO_WRITE_TOKEN via:
+# curl -s -f -X POST "http://127.0.0.1:$SIDECAR_PORT/api/repos/$CANON_NAME/tokens" \
+#   -H "Authorization: Bearer $SIDECAR_TOKEN" -H "Content-Type: application/json" \
+#   -d '{"scope":"write","ttlSeconds":3600}')
+
+# 3. Push unrelated local history safely using exact seed lease and repo write token
+git -c http.extraHeader="Authorization: Bearer $REPO_WRITE_TOKEN" push \
+    --force-with-lease=refs/heads/main:"$SEED_SHA" \
+    "$REMOTE_URL" HEAD:refs/heads/main
 ```
 
-This succeeds only while canonical `main` still points at `seed_sha`. If
+This succeeds only while canonical `main` still points at `SEED_SHA`. If
 another actor advanced it, git rejects the push (`stale info`) and the
 canonical ref is preserved untouched — the failure is closed, not a clobber.
 On rejection: fetch the canonical ref, inspect what landed, and re-run with a
@@ -194,20 +223,29 @@ process runs, via `ps aux` and `/proc/<pid>/cmdline`. This applies to
 this; on multi-user hosts prefer mode `0600` files over argv:
 
 ```bash
-# Git: persist the header in the repo config once (file-backed, not per-command argv)
+# Git: persist the repo write token header in local repo config (file-backed, mode 0600)
+# Note: Smart HTTP requires the repository write token ($REPO_WRITE_TOKEN),
+# NOT the administrative control bearer ($SIDECAR_TOKEN).
 umask 077
-git config --local http.<remote-url>.extraHeader "Authorization: Bearer $SIDECAR_TOKEN"
+git config --local http."$REMOTE_URL".extraHeader "Authorization: Bearer $REPO_WRITE_TOKEN"
 chmod 600 .git/config
 
-# curl: read options from a 0600 config file instead of -H
+# Subsequent pushes use file-backed credentials without exposing tokens in argv:
+git push --force-with-lease=refs/heads/main:"$SEED_SHA" "$REMOTE_URL" HEAD:refs/heads/main
+
+# curl: write control bearer to a 0600 config file via stdin (avoids argv exposure)
 umask 077
-printf 'header = "Authorization: Bearer <sidecar_token>"\n' "$SIDECAR_TOKEN" > .curl-scratch
-curl -K .curl-scratch https://sidecar.example.invalid/...
+cat <<EOF > .curl-control
+header = "Authorization: Bearer $SIDECAR_TOKEN"
+EOF
+chmod 600 .curl-control
+curl -K .curl-control "http://127.0.0.1:$SIDECAR_PORT/api/health"
 ```
 
-Residual gap, stated honestly: the single `git config` / `printf` invocation
-itself carries the token in argv for its brief runtime. For strict zero-argv
-setups, write the config file in an editor instead.
+Residual gap, stated honestly: writing `git config --local http."...".extraHeader "..."`
+still briefly exposes `$REPO_WRITE_TOKEN` in argv during the single configuration command.
+For strict zero-argv setups, append the section to `.git/config` via stdin (`cat <<EOF`)
+or edit `.git/config` directly.
 
 ## License
 
````

---

## 9. Review Summary & Next Actions

1. **Summary Verdict:** **REQUEST_CHANGES**.
   - Git seed-lease semantics (`--force-with-lease=refs/heads/main:<seed_sha>`) are fully verified on local bare repos and over Git Smart HTTP.
   - The runbook in `4c6fdd5:README.md` cannot be shipped to operators or users as-is because it advises passing `$SIDECAR_TOKEN` to Git Smart HTTP (guaranteed 401 failure), provides non-executable placeholders, and overclaims Node 24 memory behavior.
2. **Next Action for Branch Owner / `antigravity-head`:**
   - Apply the clean drop-in patch provided in Section 8.2 (or `.local/scratch/seed-lease-review/remediation.patch`) to `README.md` on branch `proto/runbook-seed-lease`.
   - Re-verify publication guard (`python3 research/antigravity/tooling/publication_guard.py README.md`).
   - Create a clean repair commit on `proto/runbook-seed-lease` and push to origin.
   - Upon publication of the repaired commit, the runbook will satisfy all criteria for final peer acceptance.
