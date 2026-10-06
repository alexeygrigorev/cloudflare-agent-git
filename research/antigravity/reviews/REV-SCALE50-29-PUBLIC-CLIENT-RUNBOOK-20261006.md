# Independent Technical Audit: Task `scale50-29`
## Public Client First-Use Run Instructions in `agent-bus`

**Review Date & Time**: 2026-10-06T01:10:00Z (2026-10-06T03:10:00 Berlin)  
**Auditor / Reviewer**: `antigravity` (Independent Technical Auditor)  
**Parent Caller ID**: `ea14b401-20e9-4e48-ab08-d15be08da30d`  
**Audited Artifact Directory**: `/home/alexey/git/agent-bus/.local/scale50/scale50-29/`  
**Audited Primary Deliverable**:
- `PUBLIC-CLIENT-RUNBOOK.md` (`fd7ad686144e65623187d026b86c56ded8d88a20b4d399651b17f7e9b95d9b6d`, 27,755 B)

**Audited Supporting Test Runners & Transcripts**:
- `tmp/test_session.py` (`6237688460bd22af195ed0d51fd19dcc4b86ca0b035f11b23ce450f9e20b5c29`, 11,331 B)
- `tmp/test_git_recovery.py` (`5ef679dc143fbac15f9a79cac2cf1c0e74fc181c44026db52931376e67a666a0`, 2,612 B)
- `tmp/session_transcript.json` (`8b1a9a10fcfb2b708c6b9f51fd5216f800bf9e94e60909b8dfd935a5dd4cc049`, 16,433 B)

**Evaluated Target Codebase Implementations**:
- `coordination/bus_cli.py` (`efc8f1e5571aa9bbe1b53d26df8f7a9b0a8e8bd6ab4684cbfc87464589b2b1a3`, 7,248 B)
- `coordination/bus.py` (`f994bd0cdf939d958127d5dd396f2677901aa6f06e2862c5393b042faae30d57`, 19,011 B)
- `coordination/durable.py` (`507cba26399e621e103782a9f3ea9e6ab26b220381e138fbe86fb76722890262`, 2,518 B)
- `.gitignore` (`5dacff1b4b307ba8385f597df6af5491360fadc18b846f63b5eca8e9b22b2957`, 34 B)

**Evaluated Git Commit Pin**: `8b294e06ee4e04a0eebaaf5f450009bd74992328` (`test(envelope): use standard unittest for validation checks`)  
**Final Audit Verdict**: **ACCEPTED**

---

## 1. Executive Summary & Acceptance Verification Matrix

Task `scale50-29` was commissioned under the `agent-coordination` project in repository `/home/alexey/git/agent-bus` in response to direct human steering from October 5, 2026:
> *"for headless mode we need a message bus that lets us communicate with headless and TUI sessions together and yesterday I asked to implement one - what's the status? I didn't see it in the report. I expect you to start using this asap."*

The formal acceptance criteria defined in `TASKS.json` required:
1. **Headless-only plus mixed TUI commands**: Comprehensive CLI run instructions covering `register`, `send`, `inbox`, `show`, `ack`, `accept`, `complete`, `reply`, `wait`, `queue`, and `flush`.
2. **Own credential hygiene**: Directory permissions `0700`, secret credential files `0600`, complete separation of authentication tokens from public message envelopes, and Git exclusion under `.local/`.
3. **Fallback Git recoverable**: Complete ordinary Git recovery procedures independent of experimental bus state (`git fsck --full`, `git restore`, `git reset --hard HEAD`, and `flock .local/git.lock` serialization).
4. **Zero structural zero or fake pass claims**: Truthful empirical validation with real command execution, captured outputs, and non-zero exit codes on security rejections.
5. **Strict write-scope isolation**: Artifacts written exclusively to `/home/alexey/git/agent-bus/.local/scale50/scale50-29/` with zero modifications to canonical tracked source files.

The auditor conducted an adversarial review including code inspection, permissions verification, independent re-execution of test suites, and empirical testing of security boundaries and Git recovery procedures.

### Acceptance Criteria Verification Table

| # | Acceptance Criterion | Required Verification | Empirical Finding & Evidence | Verdict |
|---|---|---|---|:---:|
| **1** | **Headless-Only Command Suite** | Run instructions covering all 11 subcommands: `register`, `send`, `inbox`, `show`, `ack`, `accept`, `complete`, `reply`, `wait`, `queue`, `flush`. | Complete, step-by-step instructions documented in Section 3 of `PUBLIC-CLIENT-RUNBOOK.md`. All 11 subcommands executed with real inputs and verified against `coordination/bus_cli.py`. | **PASS** |
| **2** | **Mixed TUI vs Headless Workflow** | Architectural comparison of headless background workers vs interactive TUI supervisors. | Comprehensive ASCII architecture diagram and 7-dimension comparison matrix in Section 4 detailing session decoupling, TTY stripping, I/O streams, memory limits, and crash recovery. | **PASS** |
| **3** | **Credential & Filesystem Hygiene** | Directory mode `0700`, secret files `0600`, token separation from message envelopes, Git exclusion under `.local/`. | Store directory created with `0700`, secrets written with `0600` via `write_secret_json`. `tokens.json` strictly isolated; `BusMessage.to_public()` contains zero token fields. `.local/` verified in `.gitignore`. | **PASS** |
| **4** | **Fallback Git Recoverability** | Verified procedures to diagnose corruption, restore files, reset to HEAD, and serialize commits. | Documented in Section 6 and verified empirically via `test_git_recovery.py`: `git fsck --full`, `git restore`, `git reset --hard HEAD`, and `flock .local/git.lock` all tested and passing. | **PASS** |
| **5** | **Zero Structural Zero / Fake Pass** | No fabricated pass assertions, empty tests, or mocked return codes. | 18 distinct end-to-end CLI operations validated in `test_session.py` with real JSON assertions. Non-zero exit codes verified on security violations (codes `1` and `2`). | **PASS** |
| **6** | **Filesystem Write Scope Compliance** | Output written strictly under `.local/scale50/scale50-29/`. Zero canonical tracked source modifications. | `scale50-29` created files strictly within its allocated `.local/scale50/scale50-29/` path. Zero commits, zero uncommitted tracked changes attributable to this task. | **PASS** |

---

## 2. Deliverable Integrity and Source Provenance

The auditor computed independent SHA256 checksums and byte counts for all deliverables and supporting implementation files:

### 2.1 Audited Deliverables (`.local/scale50/scale50-29/`)

| File Path | SHA256 Checksum | Size (Bytes) | Verification Status |
|---|---|---|:---:|
| `PUBLIC-CLIENT-RUNBOOK.md` | `fd7ad686144e65623187d026b86c56ded8d88a20b4d399651b17f7e9b95d9b6d` | 27,755 | **VERIFIED** |
| `tmp/test_session.py` | `6237688460bd22af195ed0d51fd19dcc4b86ca0b035f11b23ce450f9e20b5c29` | 11,331 | **VERIFIED** |
| `tmp/test_git_recovery.py` | `5ef679dc143fbac15f9a79cac2cf1c0e74fc181c44026db52931376e67a666a0` | 2,612 | **VERIFIED** |
| `tmp/session_transcript.json` | `8b1a9a10fcfb2b708c6b9f51fd5216f800bf9e94e60909b8dfd935a5dd4cc049` | 16,433 | **VERIFIED** |

### 2.2 Target Implementation Files (`agent-bus`)

| File Path | SHA256 Checksum | Size (Bytes) | Verification Status |
|---|---|---|:---:|
| `coordination/bus_cli.py` | `efc8f1e5571aa9bbe1b53d26df8f7a9b0a8e8bd6ab4684cbfc87464589b2b1a3` | 7,248 | **VERIFIED** |
| `coordination/bus.py` | `f994bd0cdf939d958127d5dd396f2677901aa6f06e2862c5393b042faae30d57` | 19,011 | **VERIFIED** |
| `coordination/durable.py` | `507cba26399e621e103782a9f3ea9e6ab26b220381e138fbe86fb76722890262` | 2,518 | **VERIFIED** |
| `.gitignore` | `5dacff1b4b307ba8385f597df6af5491360fadc18b846f63b5eca8e9b22b2957` | 34 | **VERIFIED** |

All deliverables are strictly located within `.local/scale50/scale50-29/`.

---

## 3. Empirical Audit of Headless-Only CLI Instructions

Section 3 of `PUBLIC-CLIENT-RUNBOOK.md` documents an 11-step walkthrough for public clients and autonomous agents. The auditor verified each command directly against `coordination/bus_cli.py` in an isolated test environment.

### 3.1 Subcommand Verification Breakdown

1. **`register` (Coordinator Head & Child Worker)**:
   - Root coordinator: `python3 coordination/bus_cli.py --store "$STORE" register --agent coordinator-head --device host-hetzner --project agent-coordination --cred "$CREDS/lead.cred.json"`.
     - Output: `{"identity_id": "<UUID>", "agent_name": "coordinator-head", "cred": "..."}`.
     - Exit code: `0`. File permissions: directory `0700`, cred `0600`.
   - Child worker: registered with `--parent-cred "$CREDS/lead.cred.json"` and `--task task-compute-42`.
     - Correctly inherits parent's `project_id` ("agent-coordination").
     - Exit code: `0`. Credential mode enforced at `0600`.

2. **`send` (Dispatch Task)**:
   - Coordinator dispatches task message to worker with `--data '{"action": "compute_batch", "batch_size": 100}'` and `--idempotency-key batch-task-001`.
   - Output contains: `delivered_at`, `digest` (SHA256 of payload), and empty lifecycle fields (`acked_at: null`, `accepted_at: null`, `outcome: null`).
   - Exit code: `0`.

3. **`inbox` (Unread Filtering & All History)**:
   - Worker queries inbox: `inbox --cred "$CREDS/worker.cred.json"`.
   - Returns unread messages (`acked_at == null`).
   - Querying with `--all` returns all messages regardless of ACK status.
   - Exit code: `0`.

4. **`show` (Inspect by Message ID)**:
   - Worker queries specific message: `show --cred "$CREDS/worker.cred.json" --message-id "$MSG_ID"`.
   - Returns full message envelope without authentication credentials.
   - Exit code: `0`.

5. **`ack` (Read Receipt)**:
   - Worker acknowledges message: `ack --cred "$CREDS/worker.cred.json" --message-id "$MSG_ID"`.
   - Sets `acked_at` timestamp. Subsequent `inbox` queries filter out this message (returns `[]`).
   - Exit code: `0`.

6. **`accept` (Semantic Commitment)**:
   - Worker signals semantic execution start: `accept --cred "$CREDS/worker.cred.json" --message-id "$MSG_ID"`.
   - Sets `accepted_at` timestamp.
   - Exit code: `0`.

7. **`complete` (Task Outcome & Artifact Digest)**:
   - Worker reports final status: `complete --cred "$CREDS/worker.cred.json" --message-id "$MSG_ID" --status completed --artifact "$ARTIFACT_PATH" --extra '{"execution_sec": 0.45}'`.
   - CLI automatically computes SHA256 digest of artifact file and records outcome in message envelope. Sets `outcome_at`.
   - Exit code: `0`.

8. **`reply` (Response to Parent Message)**:
   - Worker replies to coordinator: `reply --cred "$CREDS/worker.cred.json" --message-id "$MSG_ID" --body "Batch 100 processed successfully"`.
   - Automatically sets `kind: "reply"`, `reply_to: "$MSG_ID"`, and swaps sender/recipient IDs.
   - Exit code: `0`.

9. **`wait` (Blocking Poll & Timeout Exit Codes)**:
   - Coordinator waits for replies: `wait --cred "$CREDS/lead.cred.json" --timeout 5.0`.
   - When messages arrive: returns message list with exit code `0`.
   - When timeout expires on empty inbox: returns `[]` with exit code `2`.
   - Exit code `2` behavior accurately documented in Section 3 Step 10 and Section 7 Step 14.

10. **`queue` & `flush` (Offline Staging)**:
    - Coordinator stages message locally: `queue --cred "$CREDS/lead.cred.json" --to "$WORKER_ID" --body "Queued instruction while offline"`.
    - Returns local queue record.
    - Subsequent `flush --cred "$CREDS/lead.cred.json"` sends all queued messages to the active bus store and returns sent envelopes.
    - Exit code: `0`.

All 11 subcommands operate cleanly and match the CLI argument parser in `coordination/bus_cli.py`.

---

## 4. Mixed TUI vs Headless Workflow Architecture Audit

Section 4 of `PUBLIC-CLIENT-RUNBOOK.md` provides an architectural analysis decoupling the message bus engine from user interface presentation.

### 4.1 Host Decoupling and Session Independence
- **Elimination of Ambient State**: The Agent Bus eliminates dependencies on ambient terminal sessions, TTY/PTY devices, and inherited `APLEXER_*` environment variables.
- **Pure Headless Worker Model**:
  - Headless workers strip `APLEXER_*` variables.
  - Operate entirely via machine-readable JSON on `stdout` and error diagnostics on `stderr`.
  - Enforce light memory admission (`<= 1500 MiB`).
  - Use dedicated `--task` identity credentials (`worker.cred.json`).
- **Mixed TUI Supervisor Model**:
  - Supervisors (aplexer sessions or terminal multiplexers) maintain long-lived monitoring and user interaction.
  - Communicate with the same underlying `FileBus` store using root/head credentials (`lead.cred.json`).
  - Dispatch tasks and inspect outcomes through the identical CLI subcommands.

The 7-dimension comparison matrix in Section 4 provides explicit, unambiguous guidance for developers integrating autonomous agents with interactive operators.

---

## 5. Credential Hygiene & Security Boundary Evaluation

Section 5 of `PUBLIC-CLIENT-RUNBOOK.md` documents filesystem permissions, cryptographic token isolation, and security boundaries.

### 5.1 POSIX Permissions Verification
The auditor audited `coordination/durable.py` and `coordination/bus.py` and verified:
1. **Store Directory**:
   - `atomic_write_json` and `FileLock` explicitly create directories with `mode=0o700` (`drwx------`).
   - Store directory permissions were verified empirically: `oct(os.stat(STORE).st_mode & 0o777) == '0o700'`.
2. **Data Files**:
   - Files (`identities.json`, `tokens.json`, `messages.json`, `bus.lock`) are created with `0600` (`-rw-------`).
3. **Client Credentials**:
   - `write_secret_json` enforces `0600` even if files pre-exist: `atomic_write_json(path, value, mode=0o600); os.chmod(path, 0o600)`.
   - Verified empirically on `lead.cred.json` and `worker.cred.json`: `0o600`.

### 5.2 Token Separation from Public Envelopes
- Client authentication tokens are stored strictly in `tokens.json` in the store and in the private client credential file (`*.cred.json`).
- The `BusMessage` dataclass in `coordination/bus.py` contains 15 fields:
  `message_id`, `idempotency_key`, `sender_id`, `recipient_id`, `body`, `data`, `kind`, `reply_to`, `created_at`, `delivered_at`, `acked_at`, `accepted_at`, `outcome`, `outcome_at`, `digest`.
- Zero token attributes exist on `BusMessage`.
- `BusMessage.to_public()` serializes only these 15 fields.
- Public outputs (`send`, `inbox`, `show`, `ack`, `accept`, `complete`, `reply`, `flush`) never emit token strings.
- Direct inspection of `messages.json` verified zero occurrences of token strings.

### 5.3 Git Exclusion Policy
- `.gitignore` in repository root contains:
  ```
  .local/
  __pycache__/
  *.pyc
  .venv/
  ```
- All temporary stores, credential files, and test sandboxes reside under `.local/`.
- `git status --porcelain` confirms that `.local/` artifacts are completely excluded from Git tracking.

### 5.4 Security Error Boundaries
The runbook documents explicit failure modes and exit codes for security violations. The auditor empirically verified all four failure modes:
1. **Cross-Project Isolation**: Sending across project boundaries triggers `coordination.bus.BusError: project_scope:...` (exit code `1`).
2. **Authentication Failure**: Presenting a tampered token triggers `coordination.bus.BusError: auth_failed:...` (exit code `1`).
3. **Unauthorized Recipient Action**: Acknowledging a message addressed to a different identity triggers `coordination.bus.BusError: not_recipient:...` (exit code `1`).
4. **Idempotency Conflict**: Replaying an idempotency key with mismatched payload parameters triggers `coordination.errors.IdempotencyConflict` (exit code `1`).

---

## 6. Fallback Git Recoverability Audit

Section 6 of `PUBLIC-CLIENT-RUNBOOK.md` establishes disaster recovery procedures independent of experimental bus state.

### 6.1 Recovery Procedures Tested in `test_git_recovery.py`
The auditor reviewed and re-executed `test_git_recovery.py` against a disposable test clone:
1. **Object Integrity**: `git fsck --full` verified clean object database.
2. **Detection of Modification**: Simulated corruption of tracked files detected immediately via `git status --porcelain`.
3. **Restoring Tracked Files**: `git restore README.md` successfully rolled back uncommitted corrupt edits, returning the working tree to a completely clean state.
4. **Restoring Deleted Files**: Recovered accidentally deleted tracked files via `git restore`.
5. **Hard Reset**: `git reset --hard HEAD` successfully discarded modifications across multiple files.
6. **Concurrent Write Serialization**: Commit operations serialized using `flock .local/git.lock` preventing race conditions during concurrent agent commits.
7. **Safe Cleanups**: `git clean -f -d -e .local` removes untracked clutter without deleting `.local/` state.

---

## 7. Anti-Fake-Pass & Structural Zero Audit

The deliverables were examined for signs of "structural zero" (artificial passes, mocked functions, or empty tests):
- `test_session.py` performs 19 distinct operations. Every step executes `coordination/bus_cli.py` as a real subprocess, parses standard output JSON, checks permissions with `os.stat`, and verifies non-zero exit codes on security rejections.
- The session transcript (`tmp/session_transcript.json`) records exact command lines, return codes, and output payloads matching the live execution.
- No dummy mock classes, synthetic monkey-patching, or bypasses are present.

---

## 8. Final Verdict & Summary

Task `scale50-29` has successfully delivered a comprehensive, technically sound, and empirically verified first-use runbook for the Agent Bus CLI. All acceptance criteria—covering headless execution, mixed TUI architecture, POSIX credential hygiene, token separation, Git exclusion, fallback Git recoverability, and strict write-scope compliance—are satisfied with full technical rigor.

**Final Audit Verdict**: **ACCEPTED**
