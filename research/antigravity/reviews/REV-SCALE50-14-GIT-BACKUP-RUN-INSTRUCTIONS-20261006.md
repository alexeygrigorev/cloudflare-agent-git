# Independent Technical Audit: Task `scale50-14`
## Git Backup and Auth Fallback Run Instructions in `agent-quota-launcher`

**Review Date & Time**: 2026-10-06T01:05:00Z (2026-10-06T03:05:00 Berlin)  
**Auditor / Reviewer**: `antigravity` (Independent Technical Auditor)  
**Parent Caller ID**: `ea14b401-20e9-4e48-ab08-d15be08da30d`  
**Audited Directory**: `/home/alexey/git/agent-quota-launcher/.local/scale50/scale50-14/`  
**Audited Primary Deliverables**:
- `GIT-BACKUP-RUN-INSTRUCTIONS.md` (`56779294bb319aed27a4419251a1330c93dfd72e9637148ea3251a451d9fe60d`, 3,816 B)
- `RUN-GITHUB-SSH.md` (`3e76fa2664324bceccb1f225c0428fb2e1dc126071a0b0f14ccadb0f0b8c5d84`, 5,848 B)
- `PLATFORM-HTTP-UNAUTH.md` (`fd1fa28b6f848f9df6952f1d1e05712c2631449a853b76ae719e432819eb9fb1`, 3,293 B)
- `README.md` (`a2c5f580e08b6038b98cb2fa94d329894dc14bba91c69e457aaf401656127597`, 798 B)
- `evidence.json` (`a19506c26aca9c038aaad810f42438c30446376cf8aa66c2c0d4098aeea4e04e`, 3,162 B)
- `remotes-sanitized.json` (`be6b66740a5afb88db2acb81444b4af830db3be693578d3da8321650f252fc9b`, 981 B)
- `first-action.json` (`069d4c9ecbb594c3fd688c6e509ce60344663900c6bcc99b64ea886454f44428`, 591 B)
- `.local/launch-scale50-14.json` (`6964eb00aaa2b0f7ed71d0e3c266c0d1c024822c8066e1984dd682803e7371d7`, 1,376 B)

**Evaluated Commit Pin**: `31b41e68d50a33f39f532d096e20428a9a8cfd32` (`QL-CLI-001: public task-units backend, FileBus hold, grok argv, quse retry`)  
**Final Audit Verdict**: **ACCEPTED**

---

## 1. Executive Summary & Acceptance Verification Matrix

Task `scale50-14` was commissioned under the `agent-quota-launcher` project to deliver verified Git backup and authentication fallback run instructions. The task required evaluating concrete push and disposable restore receipts (`.local/launches/C2478-github-push.json` and `.local/launches/C2481-github-restore.json`), validating live launcher git remotes with sanitized URLs and zero leaked credentials, documenting the proven commit pin `31b41e68d50a33f39f532d096e20428a9a8cfd32` over private GitHub SSH, and separately analyzing the unresolved Agent Branches loopback HTTP `127.0.0.1:8848` authentication failure.

All five core acceptance criteria were subjected to adversarial technical inspection and verification:

### Acceptance Criteria Verification Table

| # | Acceptance Criterion | Required Verification | Empirical Finding & Evidence | Verdict |
|---|---|---|---|:---:|
| **1** | **Strict Filesystem Isolation (No-Write Boundary)** | Output written **ONLY** under `.local/scale50/scale50-14/`. Zero modifications to `launcher/`, `tests/`, `SPEC.md`, `git config`, or `website/`. | Verified. Scale50-14 created files strictly within `.local/scale50/scale50-14/`. Git working tree and history confirm zero changes to `launcher/`, `tests/`, `SPEC.md`, `.git/config`, or `website/` by this task. Local `.git/config` is unchanged since 2026-10-05T10:45:01Z. | **PASS** |
| **2** | **Evaluated Required Inputs** | Audit `.local/launches/C2478-github-push.json`, `.local/launches/C2481-github-restore.json`, and sanitized git remotes without leaked credentials/secrets. | Verified. Both receipts read, cited with bit-exact SHA256 hashes (`49dc7353...` and `0e4dcb4c...`), and validated against live repository state. Remotes audited and sanitized in `remotes-sanitized.json`. Zero secrets or credentials leaked. | **PASS** |
| **3** | **Proven Commit Pin 31b41e6 SSH Push & Restore** | Document proven commit pin `31b41e68d50a33f39f532d096e20428a9a8cfd32` private GitHub SSH push and disposable restore. | Verified. `RUN-GITHUB-SSH.md` and `GIT-BACKUP-RUN-INSTRUCTIONS.md` detail exact batch-mode SSH push, verification, disposable clone to `.local/tmp/restore-31b41e6`, `git fsck`, file verification, and literal-path cleanup. | **PASS** |
| **4** | **Separately Document Unresolved Platform HTTP Auth** | Document unresolved Agent Branches HTTP `127.0.0.1:8848` username-prompt failure as a separate, fail-closed track. | Verified. `PLATFORM-HTTP-UNAUTH.md` comprehensively diagnoses the HTTP 401 response missing `WWW-Authenticate` header, causing Git's fallback to interactive username prompts. Remotes and config left untouched; repair assigned to platform owner. | **PASS** |
| **5** | **Zero Structural Zero / Fake Pass Claims** | Truthful evidence reporting; no manufactured passes, fake counts, or fabricated successes. | Verified. The platform HTTP failure is honestly documented as `unresolved_username_prompt` (`repaired: false`, `claimed_platform_pushed: false`). Proven SSH backup is grounded in actual verifiable receipts. | **PASS** |

---

## 2. Execution Provenance and Deliverable Digests

### 2.1 Task Unit Execution Record
Task `scale50-14` was initially dispatched via the launcher's `task-units` backend on systemd user slice:
- **Unit Name**: `agent-task-scale50-14.service`
- **Invocation ID**: `96493d389ce94136926dcfbbdd7bac4d`
- **Execution Provider**: `grok`
- **Execution Window**: Started `2026-10-05T11:09:26.481108+00:00`, Finished `2026-10-05T11:15:58.617544+00:00`
- **Exit Code**: `0`
- **TasksMax / MemoryMax**: `100` / `768 MB`
- **Module SHA256**: `cf3255fca24f7bcd6479cd7bffc1860624018a875371a69bf96eb6eb59ebb148` (matches `launcher/task_units.py` at commit `31b41e68`)
- **Cleanup Verified**: `true` (`.local/tmp/scale50-14` purged upon exit)
- **First Action**: Recorded in `first-action.json` at `2026-10-05T11:13:32Z` ("read C2478-github-push.json and C2481-github-restore.json")

A subsequent coordination pass executed under `dispatch_ten.py` generated `GIT-BACKUP-RUN-INSTRUCTIONS.md` at `2026-10-05T13:23:25Z`, providing unified, step-by-step operator procedures adhering to the identical constraints.

### 2.2 Audited File Integrity & Digests

The auditor computed independent SHA256 checksums and byte counts for all artifacts located in `/home/alexey/git/agent-quota-launcher/.local/scale50/scale50-14/`:

| File Name | SHA256 Checksum | Size (Bytes) | Verification Status |
|---|---|---|:---:|
| `GIT-BACKUP-RUN-INSTRUCTIONS.md` | `56779294bb319aed27a4419251a1330c93dfd72e9637148ea3251a451d9fe60d` | 3,816 | **VERIFIED** |
| `RUN-GITHUB-SSH.md` | `3e76fa2664324bceccb1f225c0428fb2e1dc126071a0b0f14ccadb0f0b8c5d84` | 5,848 | **VERIFIED** |
| `PLATFORM-HTTP-UNAUTH.md` | `fd1fa28b6f848f9df6952f1d1e05712c2631449a853b76ae719e432819eb9fb1` | 3,293 | **VERIFIED** |
| `README.md` | `a2c5f580e08b6038b98cb2fa94d329894dc14bba91c69e457aaf401656127597` | 798 | **VERIFIED** |
| `evidence.json` | `a19506c26aca9c038aaad810f42438c30446376cf8aa66c2c0d4098aeea4e04e` | 3,162 | **VERIFIED** |
| `remotes-sanitized.json` | `be6b66740a5afb88db2acb81444b4af830db3be693578d3da8321650f252fc9b` | 981 | **VERIFIED** |
| `first-action.json` | `069d4c9ecbb594c3fd688c6e509ce60344663900c6bcc99b64ea886454f44428` | 591 | **VERIFIED** |
| `.local/launch-scale50-14.json` | `6964eb00aaa2b0f7ed71d0e3c266c0d1c024822c8066e1984dd682803e7371d7` | 1,376 | **VERIFIED** |

All files are strictly contained within `.local/scale50/scale50-14/`.

---

## 3. Filesystem & Git Isolation Audit (No-Write Boundary)

A critical mandate for task `scale50-14` was zero modifications outside `.local/scale50/scale50-14/`.

### 3.1 Status of Protected Paths
1. `launcher/`:
   - An inspection of `git diff` shows uncommitted modifications in `launcher/launch.py` and `launcher/store.py`.
   - File modification timestamps (`stat -c %y`) reveal these changes occurred on **2026-10-06 at 01:14:00 and 01:24:01 CEST**, more than 12 hours after `scale50-14` finished (`2026-10-05 13:15:58 CEST`).
   - Git log confirms zero commits or branches attributable to `scale50-14` touched `launcher/`.
2. `tests/`:
   - `git status --porcelain tests/` reports completely clean. No modifications.
3. `SPEC.md`:
   - `stat -c %y SPEC.md` indicates the file was last modified on **2026-10-04 13:07:31 CEST**. Completely untouched.
4. `.git/config`:
   - `stat -c %y .git/config` confirms the last modification occurred on **2026-10-05 12:45:01 CEST** (10:45:01 UTC, prior to `scale50-14` execution).
   - Content inspection shows standard config without temporary credentials, token injection, or altered remote specifications.
5. `website/`:
   - Directory does not exist in `agent-quota-launcher` (belongs to `cloudflare-agent-git`). No edits possible or made.
6. Temporary Directories:
   - `first-action.json` declared `tmpdir: "/home/alexey/git/agent-quota-launcher/.local/tmp/scale50-14"`.
   - Inspection verified that this directory does not exist; it was cleanly removed following task completion in compliance with the ephemeral disk cleanup rule.

---

## 4. Evaluation of Required Inputs & Proven Commit Pin 31b41e6

### 4.1 Evaluation of Launch Receipts
The auditor verified the two cited primary input receipts in `/home/alexey/git/agent-quota-launcher/.local/launches/`:

- **Push Receipt (`C2478-github-push.json`)**:
  - Independent SHA256: `49dc7353cdf21d811800b2c4cd4ae839a3931fd0024e427de6073f246d7e0ed5` (Exact match with `evidence.json`)
  - Recorded local SHA: `31b41e68d50a33f39f532d096e20428a9a8cfd32`
  - GitHub Main transition: `f982c8e13f6716e992977d4994f16e513022c1bd` -> `31b41e68d50a33f39f532d096e20428a9a8cfd32`
  - Fast-forward: `true`, Global config changed: `false`, New credentials: `false`
  - Platform status: `failed_username_prompt`, Claimed platform pushed: `false`
- **Restore Receipt (`C2481-github-restore.json`)**:
  - Independent SHA256: `0e4dcb4c6cb8664cf49cbb8fa0d87edcfdea1f1d844d3e854bf8d43df2f0f21a` (Exact match with `evidence.json`)
  - Restored SHA: `31b41e68d50a33f39f532d096e20428a9a8cfd32`
  - `fsck`: `passed`
  - Restore path: `.local/tmp/restore-31b41e6` (449,264 bytes)
  - Key owned files present: `launcher/cli.py`, `launcher/task_units.py`, `launcher/filebus_backend.py`
  - Dependencies copied: `false`, Disposable: `true`, Platform HTTP repaired: `false`

### 4.2 Run Instructions Quality & Operability
The run instructions provided across `GIT-BACKUP-RUN-INSTRUCTIONS.md` and `RUN-GITHUB-SSH.md` are comprehensive, technically sound, and guard against common operator pitfalls:
- **Environment Sanitation**: Explicitly mandates `export GIT_TERMINAL_PROMPT=0` and `export GIT_SSH_COMMAND='ssh -o BatchMode=yes'` to prevent blocking on interactive password or passphrase prompts in unattended environments.
- **Concurrency & Locking**: Mandates serialization via `flock .local/git.lock` and explicit refspecs (`HEAD:refs/heads/main`).
- **Resource Constraints**: Documents host prerequisites: root filesystem free space >= 50 GiB (+ 512 MiB spike floor) and available memory >= 10 GiB.
- **Integrity Checks**: Details post-restore verification with `git rev-parse HEAD`, `git fsck --no-reflogs`, file existence probes, and byte tallying.
- **Safe Teardown**: Enforces disposable checkout removal via two-stage command sequence (`realpath` followed by literal `rm -rf` without unbound shell variable expansion).
- **Automated Script Integration**: Section 1 of `GIT-BACKUP-RUN-INSTRUCTIONS.md` provides accurate usage of `python3 scripts/backup.py --repo <github-username>/agent-quota-launcher`, correctly describing its 50 GiB disk check, private repository verification via `gh`, temporary restore cloning under `.local/restore-*/`, and evidence recording.

---

## 5. Unresolved Platform HTTP Auth Evaluation

### 5.1 Protocol Diagnosis & Root Cause
In `PLATFORM-HTTP-UNAUTH.md`, the task provides an exemplary, root-cause diagnosis of the loopback HTTP failure (`http://127.0.0.1:8848/git/agent-branches-canonical-11ff2587.git`):
- **Observed Git Behavior**:
  ```bash
  $ GIT_TERMINAL_PROMPT=0 git -c credential.helper= ls-remote platform refs/heads/main
  fatal: could not read Username for 'http://127.0.0.1:8848': terminal prompts disabled
  ```
- **Underlying HTTP Interaction**:
  The auditor re-tested the live endpoint directly:
  ```http
  GET /git/agent-branches-canonical-11ff2587.git/info/refs?service=git-upload-pack HTTP/1.1
  Host: 127.0.0.1:8848
  
  HTTP/1.1 401 Unauthorized
  content-type: application/json; charset=utf-8
  Date: Tue, 06 Oct 2026 00:59:02 GMT
  Connection: keep-alive
  
  {"error":"git authentication required: valid per-repo token"}
  ```
- **Technical Insight**: The sidecar returns HTTP status `401 Unauthorized`, but **omits** the standard RFC 7235 `WWW-Authenticate` header (e.g. `WWW-Authenticate: Basic realm=...` or `Bearer realm=...`). Because Git receives a 401 without an authentication challenge mechanism, the Git client cannot select an authentication scheme and defaults to prompting for an HTTP Basic username on the terminal. With terminal prompts disabled (`GIT_TERMINAL_PROMPT=0`), Git immediately exits with returncode `128`.

### 5.2 Adherence to Fail-Closed Boundaries
`scale50-14` correctly maintained fail-closed discipline:
1. It did **not** attempt to bypass the failure by embedding plaintext tokens into the remote URL.
2. It did **not** edit `.git/config` to add insecure credential helpers.
3. It clearly documented that `scripts/platform.py` requires reminting per-repo tokens and injecting them process-locally via `http.<url>.extraHeader`.
4. It formally documented that repair ownership rests with the Agent Branches / platform design owner, separating the platform remote from canonical backup recovery.

---

## 6. Credential Sanitization and Anti-Fake-Pass Audit

### 6.1 Secret Sanitization Audit
The auditor executed automated pattern matching against all deliverables in `.local/scale50/scale50-14/` searching for tokens, passwords, private keys, and credential material:
- **Search Patterns**: `password`, `token`, `bearer`, `secret`, `key`, `ghp_`, `glpat-`, `xoxb-`, etc.
- **Findings**: All occurrences in `GIT-BACKUP-RUN-INSTRUCTIONS.md`, `PLATFORM-HTTP-UNAUTH.md`, and `evidence.json` were verified to be:
  - Synthetic parameter placeholders (e.g. `TOKEN=$(jq -r '.token.plaintext' ...)`).
  - Explicit prohibitions (e.g. "Do not provide private keys on the command line").
  - The literal error string emitted by the sidecar: `{"error":"git authentication required: valid per-repo token"}`.
  - Boolean assertion: `"secrets_included": false`.
- **Remote URLs**: Verified in `remotes-sanitized.json` and `.git/config`. Neither `git@github.com:...` nor `http://127.0.0.1:8848/...` contains userinfo or embedded secrets.

### 6.2 Truthfulness & Zero Structural Zero Claims
The deliverables are completely free of "structural zero" or manufactured pass claims:
- No artificial claims that platform push succeeded.
- No masking of the HTTP 401 status.
- Verification of the commit pin `31b41e6` is anchored in genuine git tree objects and verified against live GitHub remote state.

---

## 7. Recommendations & Concluding Verdict

### 7.1 Observation & Recommendation
- **Transport Alignment**: `scripts/backup.py` currently targets the HTTPS URL (`https://github.com/...`) relying on `gh auth`, whereas `RUN-GITHUB-SSH.md` documents SSH (`git@github.com:...`). While both routes are private and authenticated, operators running in non-interactive batch/systemd slices without `gh` keyring access should prefer the SSH transport (`git@github.com:...`) with `GIT_SSH_COMMAND='ssh -o BatchMode=yes'` as documented in `RUN-GITHUB-SSH.md`.

### 7.2 Final Conclusion
Task `scale50-14` has fulfilled all stated requirements and acceptance criteria with exceptional technical rigor, precise diagnostic analysis, and strict adherence to repository security boundaries.

**Final Audit Verdict**: **ACCEPTED**
