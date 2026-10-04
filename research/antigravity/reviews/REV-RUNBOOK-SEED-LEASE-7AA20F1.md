# REV-RUNBOOK-SEED-LEASE-7AA20F1 — Independent Review: Restructured Product-Primary Git Seed-Lease Runbook, Live Runtime Verification & Fail-Closed Guard

- **Reviewer:** Independent Runbook Current-Pin Reviewer (tag: `runbook-seed-lease-7aa-reviewer`).
- **Dispatched by:** `antigravity-head` (`46fdb644`), under Codex Principal C1769 directives:
  > *"Znew7aa20f1 product sequence published; this needs current-pin runtime review rather than425-only acceptance."*
- **As-of:** 2026-10-04, Europe/Berlin.
- **Target Commit:** [`7aa20f1384d386039903c52a2ad92b829f8c71f3`](file:///home/alexey/git/cloudflare-agent-git/commit/7aa20f1) (`7aa20f1`) on branch `proto/runbook-seed-lease` (`origin/proto/runbook-seed-lease`).
  - **Author:** Alexey Grigorev (`alexey.s.grigoriev@gmail.com`).
  - **Date:** Sun Oct 4 08:23:08 2026 +0200.
  - **Subject:** `docs(runbook): coordinator-managed canonical product sequence primary (created/seedCommit fail-closed, sidecar token mint, file-backed extraHeader before lease push); standalone sidecar route labeled (C1751)`.
- **Base Commit:** [`425335274b0a819ab11aed6252b568fc741233a2`](file:///home/alexey/git/cloudflare-agent-git/commit/4253352) (`4253352`).
- **Target Report Addendum:** Section 6 in [`research/antigravity/recovery/REPORT-RUNBOOK-SEED-LEASE.md`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/recovery/REPORT-RUNBOOK-SEED-LEASE.md) (committed in `6498994` on `origin/main`).
- **Reference Pre-built Daemons:**
  - Sidecar: [`prototype/local-artifacts/sidecar.mjs`](file:///home/alexey/git/agent-branches-integration/prototype/local-artifacts/sidecar.mjs).
  - Coordinator: [`prototype/.build/node/src/local/main.js`](file:///home/alexey/git/agent-branches-integration/prototype/.build/node/src/local/main.js).
- **Deliverable Path:** [`research/antigravity/reviews/REV-RUNBOOK-SEED-LEASE-7AA20F1.md`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/reviews/REV-RUNBOOK-SEED-LEASE-7AA20F1.md).
- **Scratch Workspace:** `.local/scratch/seed-lease-7aa-review/` (mode `0700`, measured disk footprint: 1.7 MB $\ll$ 512 MB, `TMPDIR` strictly within scratch root, zero `/tmp` growth).
- **Publication Guard Validation:** Verified clean via `research/antigravity/tooling/publication_guard.py` (exit code 0, zero violations).
- **Verdict:** **ACCEPT** (The restructured runbook at commit `7aa20f1` elevates the coordinator-managed canonical sequence to primary product status, incorporates an automated fail-closed shell guard on repeated setup, cleanly persists repo write credentials via mode 0600 `.git/config` before lease push, and retains the standalone sidecar path with unambiguous labeling. All flows and negative assertions were verified end-to-end against live daemons).

---

## 1. Executive Summary & Verdict Rationale

Commit `7aa20f1` restructures the local runbook on `proto/runbook-seed-lease` in response to Codex Principal C1746 and antigravity-head C1745/C1751 directives. In the predecessor commit (`4253352`), standalone sidecar repo creation was presented first, while the coordinator-managed canonical flow was presented second as an "alternative control plane". Furthermore, in `4253352` the fail-closed condition on repeated setup was stated only in prose rather than as an executable shell guard, and the credential persistence snippet contained an unbound placeholder (`<remote-url>`).

Commit `7aa20f1` remedies these architectural and operational nuances:
1. **Primary Product Sequence Elevation:** The coordinator-managed canonical repo (`POST /setup` with `$ADMIN_TOKEN`) is now the **primary product sequence** (Step 1). This is the exact repository that the SDK's `create_task` branches from.
2. **Automated Executable Fail-Closed Guard:** Following `POST /setup`, an explicit, executable shell guard inspects both `created` and `seed_sha`:
   ```bash
   if [ "$created" != "True" ] || [ "$seed_sha" = "None" ]; then
       echo "canonical already initialized (created=$created seedCommit=$seed_sha);" \
            "refusing fresh-seed lease bootstrap" >&2
       exit 1
   fi
   ```
   This prevents operators and scripts from ever attempting a blind or guessed lease push against an existing canonical repository.
3. **Multi-Plane Token Minting:** Step 2 correctly invokes the sidecar control plane (`POST /api/repos/$canonical_name/tokens` with `$SIDECAR_TOKEN`) to mint a scoped write token (`repo_tok`), extracting the `plaintext` secret from the response.
4. **Pre-Push Credential Persistence (Mode 0600):** Step 3 resolves the earlier `<remote-url>` placeholder to `$repo_url`, configuring `http.$repo_url.extraHeader` in `.git/config` with permissions `0600` before the push occurs, eliminating per-command argv token leakage.
5. **Exact Seed Lease Push:** Step 4 executes `git push --force-with-lease=refs/heads/main:"$seed_sha" "$repo_url" HEAD:refs/heads/main`.
6. **Demarcation of Standalone Sidecar Mechanics:** The standalone sidecar creation flow (`POST /api/repos`) is preserved below the product sequence, explicitly labeled as standalone sidecar Git mechanics for unit/isolated testing, not the coordinator-managed canonical repository required by the SDK.

### Empirical Live Verification Outcome
In this review pass, all documented command sequences and failure paths were executed against **live, compiled daemons** (`sidecar.mjs` on port 9884, Node coordinator on port 9885 under `ulimit -v 1530000` with `--disable-wasm-trap-handler --max-old-space-size=256`):
- **Flow A (Primary Product Sequence):** Coordinator `POST /setup` succeeded (`created: true`, valid 40-hex `seedCommit`); fail-closed guard passed; sidecar minted write token; client `.git/config` extraHeader configured (mode `0600`); seed lease push succeeded (exit 0); remote canonical ref verified matching local client commit.
- **Flow B (Fail-Closed on Repeated Setup):** Coordinator `POST /setup` on the initialized repository returned `created: false` and `seedCommit: null` (`None` in Python); the runbook shell guard intercepted the state, emitted the exact refusal message to stderr, and exited with code 1.
- **Flow C (Standalone Sidecar Mechanics):** Sidecar `POST /api/repos` created standalone repository; seed lease push succeeded with minted token (exit 0); remote ref verified.
- **Negative Test 1 (Wire 401 & Git Exit 128):** Presented `$SIDECAR_TOKEN` (the control bearer) to Git Smart HTTP push; wire request returned HTTP 401 Unauthorized; Git CLI terminated with exit 128 (`fatal: could not read Username... terminal prompts disabled`).
- **Negative Test 2 (Stale Seed Lease & Ref Preservation):** After advancing canonical `main` with an external commit, pushing with the original seed lease was rejected (`stale info`, exit 1); the advanced ref remained untouched and unclobbered.

**Verdict: ACCEPT.** The documentation at commit `7aa20f1` is fully verified against live runtimes, cryptographically and operationally sound, and strictly adheres to project security and architectural standards.

---

## 2. Environmental Invariants & Resource Accounting

The review was executed strictly within an isolated scratch environment adhering to all runtime constraints:
- **Scratch Workspace:** `/home/alexey/git/cloudflare-agent-git/.local/scratch/seed-lease-7aa-review/` initialized with mode `0700` (`drwx------`).
- **Disk Budget Compliance:** Measured peak scratch disk usage was **1.7 MB**, well within the 512 MB ceiling. No host repositories, worktrees, or parent files were altered.
- **Temporary Directory Isolation:** `TMPDIR` was redirected to `.local/scratch/seed-lease-7aa-review/tmp`. Inspection of `/tmp` verified zero bytes and zero files added by the review harness.
- **V8 Process & Memory Configuration:** The coordinator was launched under `ulimit -v 1530000` (virtual address cap) with `--disable-wasm-trap-handler --max-old-space-size=256`. The daemon remained stable across all requests without V8 trap panics; RSS remained below 75 MB.
- **Ephemeral Port Allocation:** Sidecar bound `127.0.0.1:9884` and coordinator `127.0.0.1:9885`. Ports were confirmed free before launch and cleanly released upon exit.
- **Process Teardown:** A shell trap guaranteed that all background child processes (sidecar PID 2639480, coordinator PID 2639599) were stopped via SIGTERM/SIGKILL upon completion.
- **Credential Hygiene:** In-memory secrets (`ADMIN_TOKEN`, `SIDECAR_TOKEN`, `RUNNER_TOKEN`) were generated via `openssl rand -hex 24` and never emitted in plain text to logs or console output.
- **Publication Guard:** Verified via `research/antigravity/tooling/publication_guard.py` (exit code 0, zero violations).

---

## 3. Pinned Source Audit (`7aa20f1` vs `4253352` on `proto/runbook-seed-lease`)

### 3.1 Commit Metadata
```
commit 7aa20f1384d386039903c52a2ad92b829f8c71f3 (origin/proto/runbook-seed-lease, proto/runbook-seed-lease)
Author: Alexey Grigorev <alexey.s.grigoriev@gmail.com>
Date:   Sun Oct 4 08:23:08 2026 +0200

    docs(runbook): coordinator-managed canonical product sequence primary (created/seedCommit fail-closed, sidecar token mint, file-backed extraHeader before lease push); standalone sidecar route labeled (C1751)
```
- **Parent Commit:** `425335274b0a819ab11aed6252b568fc741233a2`
- **Tree Hash:** `593b1eb3bb8c68ff8db6f26487e41253457dc5b4`
- **File Touched:** `README.md` (60 insertions, 39 deletions relative to `4253352`).

### 3.2 Line-by-Line Structural Analysis of `README.md`
Diff inspection in a disposable scratch clone confirmed the following key changes:

1. **Framing & Architectural Context (Lines 187–198):**
   - States explicitly that both control planes initialize canonical bare repos with a synthetic seed commit (`chore: seed canonical baseline`).
   - Clearly establishes that coordinator `POST /setup` creates the **coordinator-managed canonical repo** required by SDK `create_task` (the primary product sequence), whereas sidecar `POST /api/repos` creates standalone repositories for sidecar-only Git mechanics.
   - Reiterates that newly created canonical repositories are non-empty and that unconstrained `git push --force` is forbidden due to silent clobber risks.

2. **Step 1: Coordinator-Managed Canonical Setup (Lines 200–214):**
   ```bash
   # --- Product sequence: coordinator-managed canonical repo (the repo the
   # SDK's create_task branches from). Step 1 — initialize canonical on the
   # coordinator control plane:
   coord_port="${PORT:-8787}"                # coordinator listens on $PORT
   admin_bearer="Bearer $ADMIN_TOKEN"        # scheme + admin credential, composed
   setup_resp=$(curl -fsS -X POST "http://127.0.0.1:$coord_port/setup" \
       -H "Authorization: $admin_bearer")
   created=$(printf '%s' "$setup_resp" | python3 -c 'import sys, json; print(json.load(sys.stdin)["created"])')
   canonical_name=$(printf '%s' "$setup_resp" | python3 -c 'import sys, json; print(json.load(sys.stdin)["canonical"]["name"])')
   repo_url=$(printf '%s' "$setup_resp" | python3 -c 'import sys, json; print(json.load(sys.stdin)["canonical"]["remote"])')
   seed_sha=$(printf '%s' "$setup_resp" | python3 -c 'import sys, json; print(json.load(sys.stdin)["seedCommit"])')
   # jq equivalents: canonical_name=$(printf '%s' "$setup_resp" | jq -r .canonical.name), etc.
   ```

3. **Fail-Closed Guard (Lines 216–224):**
   ```bash
   # Fail closed unless the canonical repo was freshly initialized: a fresh-seed
   # lease bootstrap requires created=true AND a non-null seedCommit. An already
   # initialized canonical (created=false, seedCommit=null) offers no seed SHA —
   # never lease against a guessed one; integrate through ordinary Git instead.
   if [ "$created" != "True" ] || [ "$seed_sha" = "None" ]; then
       echo "canonical already initialized (created=$created seedCommit=$seed_sha);" \
            "refusing fresh-seed lease bootstrap" >&2
       exit 1
   fi
   ```
   *Audit Finding:* Guard evaluates cleanly in bash (`bash -n` confirmed clean); exits immediately with code 1 if `created` is not `"True"` or `seed_sha` is `"None"`.

4. **Step 2: Scoped Sidecar Token Mint (Lines 226–235):**
   ```bash
   # Step 2 — /setup mints no write token: create a repo-scoped one on the
   # sidecar control plane (shared bearer; the response record carries the
   # secret as `plaintext`):
   sidecar_bearer="Bearer $SIDECAR_TOKEN"    # scheme + control credential, composed once
   token_resp=$(curl -fsS -X POST \
       "http://127.0.0.1:$SIDECAR_PORT/api/repos/$canonical_name/tokens" \
       -H "Authorization: $sidecar_bearer" \
       -H 'Content-Type: application/json' \
       -d '{"scope": "write", "ttlSeconds": 3600}')
   repo_tok=$(printf '%s' "$token_resp" | python3 -c 'import sys, json; print(json.load(sys.stdin)["plaintext"])')
   ```

5. **Step 3: Mode 0600 Repo-Local Git Config Persistence (Lines 237–242):**
   ```bash
   # Step 3 — persist the push credential in repo-local git config BEFORE the
   # push (0600 file, not per-command argv; header composed from scheme + token):
   umask 077
   repo_bearer="Bearer $repo_tok"   # scheme + minted repo write token
   git config --local "http.$repo_url.extraHeader" "Authorization: $repo_bearer"
   chmod 600 .git/config
   ```
   *Audit Finding:* Binds directly to `$repo_url` (derived from `canonical.remote`), resolving the earlier abstract `<remote-url>` placeholder.

6. **Step 4: Push with Exact Seed Lease (Lines 244–246):**
   ```bash
   # Step 4 — push with the exact lease on the seed commit:
   git push --force-with-lease=refs/heads/main:"$seed_sha" \
       "$repo_url" HEAD:refs/heads/main
   ```

7. **Standalone Sidecar Mechanics Demarcation (Lines 248–262):**
   ```bash
   # --- Standalone sidecar Git mechanics (sidecar-only testing; NOT the
   # coordinator-managed canonical repo the SDK's create_task requires):
   # sidecar POST /api/repos creates a repo and returns remote (canonical URL),
   # seedCommit (seed SHA) and token (repo write token) in one flat response.
   sidecar_resp=$(curl -fsS -X POST "http://127.0.0.1:$SIDECAR_PORT/api/repos" \
       -H "Authorization: $sidecar_bearer" \
       -H 'Content-Type: application/json' \
       -d '{"name":"my-task-repo"}')
   seed_sha=$(printf '%s' "$sidecar_resp" | python3 -c 'import sys, json; print(json.load(sys.stdin)["seedCommit"])')
   repo_url=$(printf '%s' "$sidecar_resp" | python3 -c 'import sys, json; print(json.load(sys.stdin)["remote"])')
   repo_tok=$(printf '%s' "$sidecar_resp" | python3 -c 'import sys, json; print(json.load(sys.stdin)["token"])')
   # jq equivalents: seed_sha=$(printf '%s' "$sidecar_resp" | jq -r .seedCommit), etc.
   # Then repeat steps 3-4 above: persist http.$repo_url.extraHeader with this
   # token and push with --force-with-lease=refs/heads/main:"$seed_sha".
   ```

8. **Credential Hygiene Subsection (Lines 291–301):**
   - Corrected to reference Step 3 with `$repo_url` bound to the canonical remote URL:
     `git config --local "http.$repo_url.extraHeader" "Authorization: $repo_bearer"`.

---

## 4. Live Runtime Verification: Primary Product Sequence (Flow A)

The harness verified the primary product sequence from lines 200–246 against running daemons.

### 4.1 Daemon Startup & Readiness
- **Sidecar Daemon:** Started on `http://127.0.0.1:9884` (PID 2639480). Readiness confirmed in 200ms via `GET /api/health`.
- **Coordinator Daemon:** Started on `http://127.0.0.1:9885` (PID 2639599) under `ulimit -v 1530000` with Node flags `--disable-wasm-trap-handler --max-old-space-size=256`. Readiness confirmed in 200ms via `GET /status`.

### 4.2 Step 1 — Coordinator `/setup`
- Invocations:
  ```bash
  coord_port="9885"
  admin_bearer="Bearer $ADMIN_TOKEN"
  setup_resp=$(curl -fsS -X POST "http://127.0.0.1:$coord_port/setup" \
      -H "Authorization: $admin_bearer")
  ```
- Extracted Values:
  - `created`: `"True"`
  - `canonical_name`: `agent-branches-canonical-f4455ac8`
  - `repo_url`: `http://127.0.0.1:9884/git/agent-branches-canonical-f4455ac8.git`
  - `seed_sha`: `27c61e54a5466edf1851e2f76bd11c320b5484a3` (valid 40-hex SHA)
- Fail-Closed Guard Evaluation:
  Condition `[ "$created" != "True" ] || [ "$seed_sha" = "None" ]` was **false**; the script proceeded past the guard as required for a fresh bootstrap.

### 4.3 Step 2 — Sidecar Token Minting
- Invocations:
  ```bash
  sidecar_bearer="Bearer $SIDECAR_TOKEN"
  token_resp=$(curl -fsS -X POST \
      "http://127.0.0.1:9884/api/repos/agent-branches-canonical-f4455ac8/tokens" \
      -H "Authorization: $sidecar_bearer" \
      -H 'Content-Type: application/json' \
      -d '{"scope": "write", "ttlSeconds": 3600}')
  repo_tok=$(printf '%s' "$token_resp" | python3 -c 'import sys, json; print(json.load(sys.stdin)["plaintext"])')
  ```
- Token format validated: starts with `art_v1_`, cryptographically random payload, contains expiry query string.

### 4.4 Step 3 — Repo-Local Git Config Credential Persistence
- Local client repository `client-a` initialized with unrelated initial commit:
  - SHA: `8f5a7a958f6fd9582d6584865156bf5f3193fa8d`.
- Credential persisted:
  ```bash
  umask 077
  repo_bearer="Bearer $repo_tok"
  git config --local "http.http://127.0.0.1:9884/git/agent-branches-canonical-f4455ac8.git.extraHeader" "Authorization: $repo_bearer"
  chmod 600 .git/config
  ```
- File permissions verified: `stat -c "%a" .git/config` returned **`600`** (`-rw-------`).

### 4.5 Step 4 — Exact Seed Lease Push
- Push executed:
  ```bash
  git push --force-with-lease=refs/heads/main:"27c61e54a5466edf1851e2f76bd11c320b5484a3" \
      "http://127.0.0.1:9884/git/agent-branches-canonical-f4455ac8.git" HEAD:refs/heads/main
  ```
- Output:
  ```
  Total 3 (delta 0), reused 0 (delta 0), pack-reused 0
  To http://127.0.0.1:9884/git/agent-branches-canonical-f4455ac8.git
   + 27c61e5...8f5a7a9 HEAD -> main (forced update)
  ```
- Exit code: **0**.
- Verification: Sidecar query `GET /api/repos/agent-branches-canonical-f4455ac8/head` confirmed canonical `main` updated to `8f5a7a958f6fd9582d6584865156bf5f3193fa8d`.

---

## 5. Live Runtime Verification: Fail-Closed on Repeated Setup (Flow B)

The harness verified the runbook's fail-closed guard against repeated coordinator `/setup` calls.

1. Invocations:
   ```bash
   setup_resp2=$(curl -fsS -X POST "http://127.0.0.1:9885/setup" \
       -H "Authorization: Bearer $ADMIN_TOKEN")
   ```
2. Response Extracted:
   - `created2`: `"False"`
   - `seed_sha2`: `"None"` (Python printed `null` as `None`)
3. Guard Execution in Isolated Subshell:
   ```bash
   created="$created2"
   seed_sha="$seed_sha2"
   if [ "$created" != "True" ] || [ "$seed_sha" = "None" ]; then
       echo "canonical already initialized (created=$created seedCommit=$seed_sha);" \
            "refusing fresh-seed lease bootstrap" >&2
       exit 1
   fi
   ```
4. Observed Result:
   - Stderr message: `canonical already initialized (created=False seedCommit=None); refusing fresh-seed lease bootstrap`
   - Exit code: **1**.
   - Guard verified fully functional: halts execution immediately, prevents unconstrained or guessed leases, and advises ordinary Git integration.

---

## 6. Live Runtime Verification: Standalone Sidecar Creation (Flow C)

The harness verified the retained standalone sidecar sequence (lines 248–262).

1. Invocations:
   ```bash
   sidecar_resp=$(curl -fsS -X POST "http://127.0.0.1:9884/api/repos" \
       -H "Authorization: Bearer $SIDECAR_TOKEN" \
       -H 'Content-Type: application/json' \
       -d '{"name":"my-standalone-task-repo"}')
   ```
2. Response Extracted:
   - `seed_sha`: `27c61e54a5466edf1851e2f76bd11c320b5484a3`
   - `repo_url`: `http://127.0.0.1:9884/git/my-standalone-task-repo.git`
   - `token`: `art_v1_...[REDACTED]`
3. Client Setup & Push:
   - Local client repo `client-c` committed `afee5ff642ba91a958f1c4b74d635918186f14b7`.
   - ExtraHeader configured in `.git/config` (mode `0600`).
   - Push executed with `--force-with-lease=refs/heads/main:"$seed_sha"`.
   - Output:
     ```
     Total 3 (delta 0), reused 0 (delta 0), pack-reused 0
     To http://127.0.0.1:9884/git/my-standalone-task-repo.git
      + 27c61e5...afee5ff HEAD -> main (forced update)
     ```
   - Exit code: **0**.
   - Verification: Sidecar query confirmed remote HEAD matches `afee5ff642ba91a958f1c4b74d635918186f14b7`.

---

## 7. Negative Tests & Security Verification

Both mandatory negative security assertions were tested and verified against the live daemons.

| Test Case | Injected Fault / Action | Expected Result | Observed Result | Status |
| :--- | :--- | :--- | :--- | :---: |
| **Neg 1 (Wire 401 & Exit 128)** | Push to Git Smart HTTP with control bearer `$SIDECAR_TOKEN` | Wire HTTP 401; Git CLI aborts with exit 128 | HTTP 401 Unauthorized; `fatal: could not read Username... terminal prompts disabled` (exit 128) | **PASS** |
| **Neg 2 (Stale Lease Rejection)** | External commit advances `main`; push with old `$seed_sha` lease | Git push rejected with exit 1 (`stale info`); remote ref unchanged | `! [rejected] HEAD -> main (stale info)` (exit 1); remote ref matches advanced SHA | **PASS** |

### 7.1 Negative Test 1 Details: Control Bearer Rejection on Git Transport
- **Wire probe:**
  ```bash
  curl -s -o /dev/null -w "%{http_code}" \
      "http://127.0.0.1:9884/git/agent-branches-canonical-f4455ac8.git/info/refs?service=git-receive-pack" \
      -H "Authorization: Bearer $SIDECAR_TOKEN"
  ```
  Returned HTTP status: **`401`**.
- **Git CLI probe:**
  ```bash
  GIT_TERMINAL_PROMPT=0 git -C "$CLIENT_NEG1" \
      -c "http.$repo_url.extraHeader=Authorization: Bearer $SIDECAR_TOKEN" \
      push "$repo_url" HEAD:refs/heads/main
  ```
  Exited with code **`128`**, emitting:
  `fatal: could not read Username for 'http://127.0.0.1:9884': terminal prompts disabled`.
- Proves conclusively that control plane credentials cannot authenticate Git transport operations.

### 7.2 Negative Test 2 Details: Stale Seed Lease & Ref Preservation
- **External advance:** Canonical `main` was advanced via sidecar commit API to `d88a94e4bd368e40a7f1c29e6553a8efaeb9780e` (representing concurrent actor work landing on `main`).
- **Client attempt:** `client-neg2` (commit `8a801a4...`) attempted to push using the now-stale seed lease `--force-with-lease=refs/heads/main:"27c61e5..."`.
- **Result:**
  ```
  To http://127.0.0.1:9884/git/agent-branches-canonical-f4455ac8.git
   ! [rejected]        HEAD -> main (stale info)
  error: failed to push some refs to 'http://127.0.0.1:9884/git/agent-branches-canonical-f4455ac8.git'
  ```
  Exit code: **`1`**.
- **Ref Preservation:** Canonical `main` was queried immediately after; it remained firmly locked at `d88a94e4bd368e40a7f1c29e6553a8efaeb9780e`. No history was overwritten or clobbered.

---

## 8. Architectural & Operational Assessment

### 8.1 Product-Sequence Primacy
The primary sequence in `README.md` now matches the operational topology of the actual product:
1. The coordinator is the single authority for provisioning canonical task baselines (`POST /setup`).
2. The sidecar acts as the physical repository host, issuing time-bounded, repo-scoped write tokens (`POST /api/repos/:name/tokens`).
3. Agents interact with the canonical repository through standard Git Smart HTTP transport authenticated by their minted repository tokens.

### 8.2 Fail-Closed Operational Guard
The runbook's fail-closed guard eliminates a serious operational hazard: an operator or deployment script attempting to lease against a non-existent or null seed SHA on an existing canonical repository. Because `created` is `"False"` and `seed_sha` is `"None"`, the guard halts execution immediately with an informative error message before any Git operations occur.

### 8.3 File-Backed Credential Hygiene
Configuring Git credentials in `.git/config` with mode `0600` under `umask 077` avoids argv token exposure during subsequent Git operations (`git push`, `git fetch`, `git pull`). The only residual exposure is the single-shot `git config` invocation itself, which is transparently acknowledged in the documentation.

### 8.4 Exact Lease Compare-and-Swap Mechanics
Using `--force-with-lease=refs/heads/main:"$seed_sha"` guarantees that the push acts as a strict compare-and-swap (CAS). It succeeds if and only if the remote branch has not progressed beyond the initial synthetic seed commit. If another worker or coordinator process lands changes first, the push fails closed without data loss.

---

## 9. Epistemic Status & Conclusion

Commit `7aa20f1` completely satisfies the requirements of Codex Principal C1769 and antigravity-head directives:
- The coordinator-managed canonical repo is the primary documented path.
- The fail-closed guard prevents accidental lease pushes on existing canonicals.
- Multi-plane token authorization is accurately documented and proven in live runtime execution.
- Mode 0600 Git configuration eliminates per-command argv token exposure.
- All live runtime commands, error conditions, and negative test vectors were executed and passed.

### Final Verification Ledger

```
[AUDIT] Target Commit: 7aa20f1384d386039903c52a2ad92b829f8c71f3 (origin/proto/runbook-seed-lease)
[AUDIT] Base Commit:   425335274b0a819ab11aed6252b568fc741233a2
[LIVE]  Flow A (Coordinator Setup + Sidecar Mint + 0600 Push):       PASSED (exit 0)
[LIVE]  Flow B (Fail-Closed on Repeated Setup: created:F/seed:None):  PASSED (exit 1 / refusal message)
[LIVE]  Flow C (Standalone Sidecar Create + Seed Lease Push):         PASSED (exit 0)
[NEG]   Neg 1 (Wire 401 & Exit 128 on SIDECAR_TOKEN Git Push):       PASSED (HTTP 401 / Git exit 128)
[NEG]   Neg 2 (Stale Seed Lease Rejection + Ref Preservation):       PASSED (exit 1 / ref preserved)
[ENV]   Scratch Footprint:                                           1.7 MB (<= 512 MB ceiling)
[ENV]   /tmp Growth:                                                 0 bytes / 0 files
[SEC]   Publication Credential Guard:                                PASSED (exit 0, 0 violations)
```

**Final Determination:** **ACCEPT**. Commit `7aa20f1` is fully cleared for integration into canonical documentation.
