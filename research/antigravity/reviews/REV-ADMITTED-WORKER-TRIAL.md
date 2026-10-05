# Independent Technical Audit: Admitted Bus Worker Trial Execution, Canonical Store State, Autonomous Tool Execution, Native FileBus Dogfood Cycle, Append-Only Storage & Output-Admission Adversarial Negative Verification

**Document ID:** `REV-ADMITTED-WORKER-TRIAL`  
**Directives:** Codex Principal Directives C2299, C2300, C2304, C2306, C2310, C2312, C2313  
**Reviewer:** `reviewer259` (Independent Model Reviewer, Session `259526a9-5deb-47ce-810c-ca5f2da56b68`)  
**Target Trial Receipt:** `/home/alexey/git/cloudflare-agent-git/.local/scratch/admitted-busworker-trial/trial_result.json`  
**Trial Receipt SHA256:** `2e7b2070d77ee0d654c875d7944ed9f1c80b8e7f4c83356afea67d25328a86da`  
**Audited Runner Script:** `.local/scratch/admitted-busworker-trial/run_admitted_busworker_trial.py`  
**Runner Script SHA256:** `4fab504ea57fa3abfcffc5279770dfef832965a76bdb8cbdb3ce6dd84fea37e3`  
**Negative Test Suite:** `.local/scratch/reviewer259-admitted-trial/test_output_admission_negatives.py`  
**Trial 1 Deliverable (Archived):** `research/antigravity/reviews/archive/REV-WINDOWS-DRIVER-2FD1BE4E-trial1-d93f3707.md`  
**Trial 1 SHA256:** `d93f3707d3aba5ff21b83da77a39e01136a99f049896ed2d98da3b9ff1832a31` (5,945 bytes, `BOUNDED ACCEPTANCE`)  
**Trial 2 Deliverable (Preserved):** `research/antigravity/reviews/REV-WINDOWS-DRIVER-2FD1BE4E.md`  
**Trial 2 SHA256:** `470a9ee6892fb8f5b452cca6c644151d5cd0dfd990ce5586891d4cee72188d2d` (3,560 bytes, `REQUEST_CHANGES`)  
**Target Driver Audited:** `research/antigravity/recovery/windows_rpc_diagnostic_driver.py`  
**Driver SHA256:** `2fd1be4ef2b9d0437ac47e3635f13212886f2e8c56d0dea94919f057a3205d44`  
**Canonical Store:** `/home/alexey/.config/agent-quota-launcher/state.db`  
**Audit Date:** 2026-10-05T05:40:00+02:00 (Europe/Berlin)  
**Formal Verdict:** **FULL ACCEPTANCE OF ADMISSION, NATIVE BUS DOGFOOD CYCLE & OUTPUT-ADMISSION ADVERSARIAL REPAIR; DRIVER VERDICT REQUEST_CHANGES RECORDED; PHYSICAL WINDOWS RUNTIME HELD**

---

## 1. Executive Summary & Verification Scope

Under Codex Principal Directives C2299, C2300, C2304, C2306, C2310, C2312, and C2313, an independent adversarial technical audit was conducted on the admitted FileBus worker trial execution (`admitted_busworker_gemini_pro_trial`), covering:
1. The append-only storage and locked lifecycle repair of the trial runner script (`run_admitted_busworker_trial.py`, SHA256: `4fab504e...`).
2. Adversarial negative testing of the output-admission path (`test_output_admission_negatives.py`), verifying strict isolation from pre-existing public artifacts, missing artifact rejection, two-sided thread correlation, and fail-closed verdict parsing.
3. Authentic model execution and autonomous tool actions under kernel systemd scope containment.
4. Dual evidence records preserving Trial 1 (`d93f3707...`) and Trial 2 (`470a9ee6...`) deliverables.
5. Canonical quota launcher store state, kernel resource enforcement, filesystem confinement, and native FileBus message exchanges.

### Verification Matrix Summary:
- **Output-Admission Adversarial Negatives (C2313) — ACCEPTED:** Verified via dedicated test suite (`test_output_admission_negatives.py`):
  * **Test A (Pre-existing public artifact):** Confirmed pre-existing files in canonical `research/` do NOT cause a new run with missing `run_deliverable` to count as `worker_tool_write` (`is_valid=False`, `worker_wrote_deliverable=False`).
  * **Test B (Missing new artifact):** Missing or 0-byte `run_dir / deliverable.md` is strictly rejected (`is_valid=False`).
  * **Test C (Wrong-thread reply rejection):** Messages with matching `sender_id` but wrong `reply_to`, or matching `reply_to` but wrong `sender_id`, return `None`.
  * **Test D (Conflicting verdict fail-closed):** Contradictory text matches and structured data vs text conflicts fail closed as `UNKNOWN_CONFLICT`. Zero prioritization of `BOUNDED ACCEPTANCE`.
- **Append-Only Runner Repair (C2310 & C2312) — ACCEPTED:** Verified that `run_admitted_busworker_trial.py` completely eliminated all raw SQLite mutations (`DELETE FROM tasks / task_resources / task_paths`) and destructive filesystem purges (`shutil.rmtree`, `unlink`). Independent AST analysis confirmed strictly 0 imports of `sqlite3` or `shutil`, 0 calls to `unlink` or `rmtree`, and 0 SQL delete statements. Verified run-scoped isolation (`run_id`, `task_id`, dedicated directories).
- **Autonomous Tool Execution (C2304) — ACCEPTED:** Verified that the worker in Trial 2 (`c6085104`) autonomously read-ACKed the assigned task on FileBus (`bus_cli.py ack`), directly authored the deliverable artifact via tool write (`worker_tool_write`), and autonomously dispatched the completion reply on FileBus (`bus_cli.py reply`). The outer controller executed strictly zero worker ACKs (`worker_ack_executed_by_controller: false`).
- **Review Deliverable Integrity (`470a9ee6...`) — ACCEPTED:** Verified `REV-WINDOWS-DRIVER-2FD1BE4E.md` (3,560 bytes) produced by `gemini-3.1-pro-high`. Validated an authentic, unprompted `REQUEST_CHANGES` verdict. Re-qualified security findings: Base64 padding regex truncation (`+`, `/`, `=`) verified as an active regex defect; `sys.stderr` spillage and native Windows `ssh.exe` resolution explicitly demarcated as architectural hypotheses / OS shell resolution questions under offline Linux evaluation.
- **Kernel Scope & Containment — ACCEPTED:** Verified systemd unit `agent-scope-t-busworker-c6085104.scope` executed under `TasksMax=100`, `MemoryMax=1500M`, with InvocationID `185ca9328b454142988a149886a5f55e`, confirmed dissolved post-exit with zero lingering PIDs and 466,366 bytes tmpdir growth (net `/tmp` growth = 0 bytes).
- **Physical Windows Boundary — HELD:** Native physical Windows execution remains held and untested (offline Linux component and model evaluation only).

---

## 2. Runner Script Audit, Append-Only Storage & Output-Admission Negative Testing (Directives C2310, C2312, C2313)

### 2.1. Initial Flaw Identification (Directive C2310)
In early revisions, `run_admitted_busworker_trial.py` contained destructive logic:
1. `shutil.rmtree(BUS_STORE)` and `shutil.rmtree(SCRATCH_TMP)` erased the initial trial's FileBus message history and cryptographic credentials.
2. Raw SQLite queries (`DELETE FROM tasks / task_resources / task_paths`) executed outside `launch_lock` and bypassed `Store` methods, colliding on static `task_id = "t-busworker-gemini-pro-trial"` and risking discarding active or uncertain task reservations.

Full runner lifecycle acceptance was therefore formally withheld pending verification of the append-only fix.

### 2.2. Independent Code Audit of Updated Runner (`4fab504ea57fa3abfcffc5279770dfef832965a76bdb8cbdb3ce6dd84fea37e3`)
The updated runner script at `.local/scratch/admitted-busworker-trial/run_admitted_busworker_trial.py` was subjected to comprehensive static and AST analysis:

1. **Elimination of Raw SQL Mutations:**
   - **AST Verification:** Confirmed strictly zero imports of `sqlite3`.
   - **Query Verification:** Confirmed strictly zero occurrences of `DELETE FROM`, `DROP`, or raw SQL mutations.
   - **Store Interaction:** All database interactions are strictly routed through canonical `Store` abstractions under `canonical_lock` (`launch_lock`).
2. **Elimination of Destructive Filesystem Purges:**
   - **AST Verification:** Confirmed strictly zero imports of `shutil`.
   - **Method Verification:** Confirmed strictly zero calls to `unlink` or `rmtree`.
3. **Run-Scoped Append-Only Isolation (Lines 161–171):**
   ```python
   run_id = f"run-{int(time.time())}-{uuid.uuid4().hex[:6]}"
   task_id = f"t-busworker-gemini-pro-{run_id}"

   # Run-scoped append-only directories (strictly no rmtree or unlinks)
   run_dir = ROOT_SCRATCH / run_id
   run_tmp = REPO_ROOT / ".local" / "tmp" / "admitted-busworker-trial" / run_id
   run_bus_store = run_dir / "bus_store"
   run_creds_dir = run_dir / "creds"
   run_deliverable = run_dir / "deliverable.md"
   run_trial_result = run_dir / "trial_result.json"
   ```
   Every execution generates a unique timestamped/UUID task identifier and writes into an isolated subfolder, preventing cross-run overwrites or state collisions.
4. **Append-Only Receipts & Canonical Preservation:**
   Receipts are written to the run-scoped `run_trial_result`, while the root `TRIAL_RESULT_PATH` is maintained purely as an updated latest pointer without deleting historical run directories.

### 2.3. Adversarial Negative Testing of Output-Admission Path (Directive C2313)
An independent adversarial test suite was authored and executed in scratch at `.local/scratch/reviewer259-admitted-trial/test_output_admission_negatives.py`. All four test cases passed cleanly (exit code 0):

```text
=== ADVERSARIAL NEGATIVE TEST SUITE: OUTPUT-ADMISSION PATH ===
--- [Test A] Pre-existing Public Artifact Isolation ---
  PASSED: Pre-existing canonical artifact did NOT credit new run. is_valid=False, worker_wrote_deliverable=False.
--- [Test B] Missing New Artifact Rejection ---
  PASSED: Missing or 0-byte run deliverable correctly rejected with is_valid=False.
--- [Test C] Wrong-Thread Reply Rejection ---
  PASSED: correlate_reply strictly rejected wrong-thread and mismatched-sender messages.
--- [Test D] Conflicting Verdict Fail-Closed Handling ---
  PASSED: parse_verdict fails closed as UNKNOWN_CONFLICT on all contradictory and conflicting inputs.

ALL 4 ADVERSARIAL OUTPUT-ADMISSION NEGATIVE TESTS PASSED CLEANLY (EXIT 0).
```

#### Detailed Test Case Evaluations:
- **Test A (Pre-existing public artifact):** Verified that `verify_run_deliverable` inspects exclusively `run_dir / deliverable.md`. A pre-existing file in `research/` has zero impact on output admission; if `run_deliverable` is missing, `is_valid` is `False`, `worker_wrote_deliverable` is `False`, and `deliverable_provenance` is `None`.
- **Test B (Missing new artifact):** Verified that absent or 0-byte deliverables return `is_valid=False`, preventing empty files from being admitted.
- **Test C (Wrong-thread reply rejection):** Verified that `correlate_reply` requires both `reply_to == task_msg_id` AND `sender_id == worker_id`. Messages with mismatched threads or impostor senders are rejected (`None`).
- **Test D (Conflicting verdict fail-closed):** Verified that `parse_verdict` fails closed as `UNKNOWN_CONFLICT` when:
  1. The deliverable text contains multiple conflicting verdicts (e.g. `BOUNDED ACCEPTANCE` and `REQUEST_CHANGES` in decision positions).
  2. The structured data payload contradicts the markdown text verdict (e.g. data specifies `BOUNDED ACCEPTANCE` while text specifies `REQUEST_CHANGES`).
  3. No verdict is prioritized over another; ambiguous or conflicting results cannot result in a default acceptance.

---

## 3. Dual Evidence Record & Deliverable Preservation

Under Directives C2310 and C2312, both trial deliverables have been explicitly preserved, cataloged, and cross-referenced:

| Deliverable Artifact | Scope Unit / Invocation | SHA256 Checksum | Size | Model Verdict | Status & Provenance |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `research/antigravity/reviews/archive/REV-WINDOWS-DRIVER-2FD1BE4E-trial1-d93f3707.md` | `agent-scope-t-busworker-a10e73fb.scope` | `d93f3707d3aba5ff21b83da77a39e01136a99f049896ed2d98da3b9ff1832a31` | 5,945 B | `BOUNDED ACCEPTANCE` | Archived baseline. Scope clean; FileBus ACK wrapped by controller. |
| `research/antigravity/reviews/REV-WINDOWS-DRIVER-2FD1BE4E.md` | `agent-scope-t-busworker-c6085104.scope` (`185ca932...`) | `470a9ee6892fb8f5b452cca6c644151d5cd0dfd990ce5586891d4cee72188d2d` | 3,560 B | `REQUEST_CHANGES` | Preserved current deliverable. Authored directly via `worker_tool_write` by `gemini-3.1-pro-high`. |

### Component Review Integrity:
Review deliverable `REV-WINDOWS-DRIVER-2FD1BE4E.md` (`470a9ee6...`) is confirmed as an authentic, high-quality, autonomous model review. With the append-only runner repair and output-admission negative tests verified, both the model component review and the outer execution runner are fully accepted.

---

## 4. Canonical Store State Audit (`state.db`)

Direct inspection of `/home/alexey/.config/agent-quota-launcher/state.db` confirmed the current state resulting from Trial 2:

### Task Record (`tasks` table):
- **Task ID:** `t-busworker-gemini-pro-trial`
- **State:** `completed-awaiting-review`
- **Created At:** `2026-10-05 03:15:30` (UTC)
- **Updated At:** `2026-10-05 03:16:46` (UTC)
- **Reviewer:** `systemd-scope-runner`
- **Reason:** `scope agent-scope-t-busworker-c6085104.scope exited 0; unit confirmed clean; awaiting independent review`

### Task Payload & Quota Ledger:
- **Owner:** `antigravity-head`
- **Provider:** `antigravity`
- **Model:** `gemini-3.1-pro-high`
- **Model Quota Claimed:** `true`
- **Timeout:** `180.0s`
- **Requirements:** `{"allowed_providers": ["antigravity"], "providers": ["antigravity"]}`

### Active Allocations (`task_resources` & `task_paths` tables):
- **Memory Allocation:** 1,500 MB
- **Disk Allocation:** 512 MB
- **Locked Path:** `/home/alexey/git/cloudflare-agent-git`

**Audit Assessment:** Canonical quota launcher contracts are satisfied. Future executions under the updated runner generate unique task IDs (`t-busworker-gemini-pro-run-...`), ensuring zero eviction of existing records.

---

## 5. Kernel Scope, Systemd Containment & Filesystem Confinement

### 5.1. Kernel Scope Telemetry (Trial 2)
Execution occurred inside systemd transient scope `agent-scope-t-busworker-c6085104.scope`:
- **Invocation ID:** `185ca9328b454142988a149886a5f55e`
- **ControlGroup:** `/user.slice/user-1000.slice/user@1000.service/app.slice/agent-scope-t-busworker-c6085104.scope`
- **TasksMax Limit:** `100` (verified against `systemctl --user show -p TasksMax`; exit 95 on mismatch)
- **MemoryMax Limit:** `1572864000` bytes (1,500 MB; exit 92 on mismatch)
- **Process Membership:** Self PID (`2823911`) confirmed in `/sys/fs/cgroup/.../cgroup.procs` (exit 97 on mismatch)
- **On-Disk Containment Receipt:** Verified at `.local/tmp/admitted-busworker-trial/containment_verified_agent-scope-t-busworker-c6085104.scope.json` (275 bytes).

### 5.2. Scope Dissolution & Teardown
Post-execution systemctl queries confirmed complete dissolution:
```text
ActiveState=inactive
SubState=dead
LoadState=not-found
TasksCurrent=[not set]
MemoryCurrent=[not set]
```
The scope was terminated cleanly with zero lingering background processes or orphaned cgroup nodes.

### 5.3. Filesystem Confinement & Tmpdir Growth
- **Tmpdir Contents:**
  - `containment_verified_agent-scope-t-busworker-c6085104.scope.json`: 275 bytes
  - `prelude_agent-scope-t-busworker-c6085104.scope.py`: 2,450 bytes
  - `unleash-repo-schema-v1-codeium-language-server.json` (agy artifact): 463,641 bytes
  - **Total Tmpdir Footprint:** Exactly **466,366 bytes** ($\approx 455.4\text{ KiB}$).
- **Ceiling Verification:** Well below the 512 MiB limit (`536,870,912` bytes).
- **Host Hygiene:** Net `/tmp` growth was strictly **0 bytes**.

---

## 6. Directive C2304 Autonomous Tool Execution & Native FileBus Dogfooding

Trial 2 (`c6085104`) resolved the earlier facade delegation from Trial 1:
- `worker_ack_executed_by_controller`: **`false`**
- `worker_ack_found_in_store`: **`true`**
- Assigned task message `a00877e2-7a3f-41d9-8b8e-eb41354a0ebb` was read-ACKed on FileBus by the worker at `2026-10-05T03:15:42Z`.
- Deliverable artifact `REV-WINDOWS-DRIVER-2FD1BE4E.md` was written directly by the worker:
  `written_by_worker_tool: true` (`provenance: worker_tool_write`).
- The worker autonomously formatted and dispatched reply message `e98f1f5a-8d48-4b80-b6c5-1ad37bbde393` at `2026-10-05T03:16:36Z`:
  > *"Review complete. The diagnostic driver contains critical regex token leakage vulnerabilities and lacks stderr sanitization. Verdict: REQUEST_CHANGES."*
- Head alone checked its inbox and read-ACKed the worker reply at `2026-10-05T03:16:46Z`.

### Deliverable Findings in `REV-WINDOWS-DRIVER-2FD1BE4E.md` (`470a9ee6...`) & Re-Qualified Epistemic Status:
1. **Adversarial Integrity:** The model independently rendered `REQUEST_CHANGES` (zero hardcoded approval).
2. **Base64 Padding Leak (Section 2 - FAIL):** Verified active regex defect. Pattern `r'(bearer\s+)[a-zA-Z0-9_\-\.]+'` fails to match `+`, `/`, and `=`, leaking trailing token remnants into output upon encountering Base64 padding.
3. **`sys.stderr` Spillage Consideration (Section 5 - Architectural Hypothesis):** Explicitly re-qualified as an **architectural hypothesis / threat model concern** rather than an empirically tested runtime leak on Linux. The reviewer correctly noted that while exceptions in `main()` emit sanitized JSON to `sys.stdout`, the script does not redirect or sanitize `sys.stderr`. If a child library or unexpected traceback writes raw unredacted data directly to stderr, it would bypass `sanitize_text()`. Under current controlled test execution, zero stderr leaks were observed.
4. **Windows OpenSSH Quoting & Detection (Section 3 - OS Shell Resolution Question):** Explicitly re-qualified as an **architectural portability hypothesis / OS shell resolution question**. The model flagged that `--ssh-binary` defaults to `"ssh"` rather than dynamically checking for `"ssh.exe"` on Windows. On the audited Linux desktop runtime, OpenSSH resolves natively as `ssh`. Whether path resolution or cmd.exe quoting requires `"ssh.exe"` is an untested hypothesis pending native Windows execution.

---

## 7. Constraint & Invariant Verification

1. **Compiler Invariant Under Human Hold:**
   - Strictly 0 `cargo` and 0 `rustc` compiler invocations host-wide across reviewer and audited subprocesses.
2. **Canonical Repository Immutability:**
   - Canonical `/home/alexey/git/agent-quota-launcher` was verified with `git diff --exit-code`: exit code 0, zero modified tracked files, zero staged changes, zero commits.
3. **Physical Scratch Footprint:**
   - Reviewer scratch `.local/scratch/reviewer259-admitted-trial/`: 24 KB ($\le 512\text{ MB}$).
   - Audited scratch `.local/scratch/admitted-busworker-trial/`: 60 KB ($\le 512\text{ MB}$).
4. **Filesystem Hygiene:**
   - Net `/tmp` growth = 0 bytes. All temporary files remained isolated in `.local/tmp/`.
5. **Subagent Git Commit Boundary:**
   - Strictly 0 git commits or git pushes executed by reviewer subagent.

---

## 8. Audit Conclusion & Formal Updated Verdict

1. **Autonomous Model Execution & Deliverable:** Fully accepted. Deliverable `REV-WINDOWS-DRIVER-2FD1BE4E.md` (`470a9ee6...`) is an authentic adversarial tool review with genuine `REQUEST_CHANGES` findings. Identified security risks are properly qualified between active regex bugs and architectural threat hypotheses.
2. **Systemd Containment & FileBus Messages:** Receipts and telemetry verified.
3. **Trial Runner Script (`run_admitted_busworker_trial.py`, `4fab504e...`):** **FULLY ACCEPTED.** The append-only architectural repair eliminated raw SQL mutations and destructive directory wiping.
4. **Output-Admission Negative Tests (`test_output_admission_negatives.py`):** **FULLY ACCEPTED.** All 4 adversarial tests (isolation from public artifacts, missing artifact rejection, two-sided thread correlation, and fail-closed conflicting verdict parsing) passed cleanly.
5. **Physical Windows Execution:** Formally held and unverified.

**Formal Updated Verdict:**  
**FULL ACCEPTANCE OF ADMISSION, NATIVE BUS DOGFOOD CYCLE & OUTPUT-ADMISSION ADVERSARIAL REPAIR; DRIVER VERDICT REQUEST_CHANGES RECORDED; PHYSICAL WINDOWS RUNTIME HELD**
