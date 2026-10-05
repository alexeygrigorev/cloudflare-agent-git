# REV-FILEBUS-RUNNER-GUARDS — Independent Technical Audit & Adversarial Verification of Hardened FileBus Model Review Runner

- **Target Runner:** [`.local/scratch/run_hardened_filebus_model_review.py`](file:///home/alexey/git/cloudflare-agent-git/.local/scratch/run_hardened_filebus_model_review.py)
  * File Size: 26,103 bytes (630 LOC)
  * SHA256 Checksum: `9839db7a99ffacf0a83f4c1c929b8d43eb53f46270b5bbd7496fae6fae51dabd`
- **Target Author Test Suite:** [`.local/scratch/test_hardened_runner_guards.py`](file:///home/alexey/git/cloudflare-agent-git/.local/scratch/test_hardened_runner_guards.py)
  * File Size: 14,220 bytes (308 LOC)
  * SHA256 Checksum: `51465ab144d01243589313ae36ff09a4051c673a32b1a2d72728851bde523f4f`
- **Target Trial Ledger:** [`.local/scratch/filebus-hardened-model-review/trial_receipts.jsonl`](file:///home/alexey/git/cloudflare-agent-git/.local/scratch/filebus-hardened-model-review/trial_receipts.jsonl)
  * File Mode: `0600` (strictly restricted)
  * Format: Append-only JSON Lines with `fcntl.flock` exclusive locking
- **Independent Adversarial Test Suite:** [`.local/scratch/reviewer37-worker-audit/test_adversarial_runner_mutants.py`](file:///home/alexey/git/cloudflare-agent-git/.local/scratch/reviewer37-worker-audit/test_adversarial_runner_mutants.py)
- **Governing Directives:** Codex Directives C2387, C2392, and C2394; Operating Model Reset ([`coordination/OPERATING-MODEL.md`](file:///home/alexey/git/cloudflare-agent-git/coordination/OPERATING-MODEL.md)); User Messages 26, 31, 32, 34
- **Auditor / Challenger:** Independent Reviewer Subagent Reviewer 37 (`37aa1067-8bda-4dde-95b8-7b5bb927bd1f`)
- **Parent Orchestrator:** `antigravity-head` (`46fdb644`, ID `245c7bba-9a7b-45c1-87a7-4537f289f9a5`)
- **Audit Timestamp:** `2026-10-05T07:30:00Z` / `2026-10-05T09:30:00+02:00`
- **Scratch Workspace:** `.local/scratch/reviewer37-worker-audit/` (mode `0700`, disk: 80 KB $\le$ 512 MB ceiling, net `/tmp` growth = 0 bytes)
- **Compiler Invariant:** ZERO `cargo` / `rustc` compiler invocations host-wide under human hold
- **Telemetry Invariant:** Collector daemon PID `1608645` and Supervision daemon PID `3265459` undisturbed
- **Verdict:** **FULL ACCEPTANCE**

---

## 1. Executive Summary & Review Verdict

Under Codex Principal Directives C2387, C2392, and C2394, this independent technical audit evaluates `d698`'s hardened FileBus model review runner implementation: [`.local/scratch/run_hardened_filebus_model_review.py`](file:///home/alexey/git/cloudflare-agent-git/.local/scratch/run_hardened_filebus_model_review.py), the accompanying test suite [`.local/scratch/test_hardened_runner_guards.py`](file:///home/alexey/git/cloudflare-agent-git/.local/scratch/test_hardened_runner_guards.py), and the trial receipts ledger [`.local/scratch/filebus-hardened-model-review/trial_receipts.jsonl`](file:///home/alexey/git/cloudflare-agent-git/.local/scratch/filebus-hardened-model-review/trial_receipts.jsonl).

The mission evaluated whether the runner faithfully incorporates the **4f974 frozen-runner invariants** established during earlier pilot trials. In addition to verifying the author's 8-test unit suite (`Ran 8 tests in 0.023s, OK`), the reviewer designed and executed an independent adversarial mutation test suite ([`.local/scratch/reviewer37-worker-audit/test_adversarial_runner_mutants.py`](file:///home/alexey/git/cloudflare-agent-git/.local/scratch/reviewer37-worker-audit/test_adversarial_runner_mutants.py), `Ran 5 tests in 0.964s, OK`) probing edge-case fuzzing, prefix/suffix identity spoofing, bitflip SHA mutations, and high-concurrency `flock` contention.

### Key Audit Findings:
1. **Unsteered Review Prompting:** The runner completely eliminates signposted or hardcoded outcomes (e.g. `"VERDICT: ACCEPT"`). The dispatched worker instructions demand an independent verdict chosen from `ACCEPT`, `BOUNDED ACCEPTANCE`, `REQUEST_CHANGES`, or `REJECT` based strictly on empirical unit and transition tests.
2. **Fail-Closed Verdict Parsing:** The parser never defaults missing, unrecognized, or ambiguous verdicts to `ACCEPT`. It rejects contradictory verdicts in text, detects conflicts between text and structured data, and strictly enforces valid syntax.
3. **Exact Identity & Message Correlation:** FileBus inbox reply correlation strictly matches both `reply_to == task_msg_id` and `sender_id == reviewer_identity_id`. Substring matches on stdout/body are completely prevented, neutralizing imposter messages and spoofed sender prefixes.
4. **In-Process Cryptographic Deliverable Verification:** Replies must contain a valid 64-character hex `ARTIFACT_SHA256`. The runner computes the SHA256 of the deliverable directly on disk and fails closed on any mismatch, missing file, or empty (0-byte) deliverable.
5. **Collision Denial & Append-Only Ledger:** Execution directories are created with `mkdir(parents=False, exist_ok=False)` to deny collisions on duplicate `run_id`. All trial receipts are durably appended to `trial_receipts.jsonl` under `fcntl.flock(LOCK_EX)` serialization.
6. **Loaded Component Source Manifest:** In-process SHA256 hashes of loaded AgentBus components (`bus_cli.py` and `bus.py`) are captured directly into the execution receipt, preventing unpinned dependency drift.
7. **Accurate Authentication Labeling:** Authentication is explicitly designated as `symmetric_token_auth_per_identity` across code and receipts, completely eliminating inaccurate asymmetric claims.

**Verdict: FULL ACCEPTANCE.** The hardened runner and its guard mechanisms provide robust, fail-closed validation of multi-agent FileBus review workflows.

---

## 2. In-Depth Audit of the 4f974 Frozen-Runner Invariants

### 2.1 Invariant 1: Unsteered Prompt
In `run_hardened_filebus_model_review.py` (lines 109–159), `build_unsteered_worker_prompt()` constructs the task payload sent to the reviewer agent.
- **Audit Verification:**
  * Examined prompt string: strictly contains zero instances of `"VERDICT: ACCEPT"`, `"VERDICT: ACCEPTED"`, `"VERDICT: REJECT"`, or `"VERDICT: BOUNDED ACCEPTANCE"`.
  * Explicitly instructs worker: `"Determine your verdict STRICTLY INDEPENDENTLY based purely on empirical test evidence."`
  * Provides template placeholder: `"VERDICT: <YOUR_INDEPENDENT_VERDICT>"`.
  * Lists permissible verdict set: `ACCEPT, BOUNDED ACCEPTANCE, REQUEST_CHANGES, REJECT`.

### 2.2 Invariant 2: Fail-Closed Verdict Extraction
In `run_hardened_filebus_model_review.py` (lines 164–218), `parse_verdict()` extracts and validates the final verdict.
- **Audit Verification:**
  * Uses regex `(?:verdict|independent review verdict)\s*[:\-]?\s*[\*`_]*\s*(ACCEPT|BOUNDED ACCEPTANCE|REQUEST_CHANGES|REJECT)\b`.
  * **Missing Verdict Handling:** If no regex match is found, raises `ValueError("Fail-closed: No valid independent verdict found in deliverable or reply")`. Never defaults to `ACCEPT`.
  * **Unrecognized Verdicts:** Non-standard strings (e.g., `LGTM`, `PASS`, `APPROVED`, `ACCEPTED`) fail regex matching and trigger `ValueError`.
  * **Text Conflict Detection:** If multiple distinct verdicts appear in the deliverable text (e.g. an earlier draft stating `ACCEPT` and a later conclusion stating `REJECT`), `len(verdicts_found) > 1` triggers `ValueError("Fail-closed: Conflicting verdicts found in deliverable text")`.
  * **Structured Data Conflict Detection:** If structured data `{"verdict": "REQUEST_CHANGES"}` differs from text `VERDICT: ACCEPT`, `data_verdict != text_verdict` raises `ValueError`.

### 2.3 Invariant 3: Exact Reply Correlation
In `run_hardened_filebus_model_review.py` (lines 223–259), `correlate_reply()` scans messages from the dispatcher's FileBus inbox.
- **Audit Verification:**
  * Rejects empty inboxes: `if not messages: raise ValueError(...)`.
  * Strictly filters messages: `if reply_to == task_msg_id and sender_id == reviewer_identity_id: matched_replies.append(m)`.
  * **No Substring Traps:** If an attacker message has `reply_to: "unrelated-task"` but puts `task_msg_id` in the message body, it is strictly ignored.
  * **No Prefix/Suffix Spoofing:** String equality `==` prevents imposter sender IDs (e.g. `reviewer_id + "-malicious"` or `"attacker-" + reviewer_id`).
  * If no exact match exists, raises `ValueError("Fail-closed: No reply found correlating to task_msg_id ...")`.

### 2.4 Invariant 4: Cryptographic Digest Verification
In `run_hardened_filebus_model_review.py` (lines 264–310), `extract_artifact_sha256()` and `verify_cryptographic_digest()` validate the output deliverable.
- **Audit Verification:**
  * **Hex Extraction:** Extracts `ARTIFACT_SHA256` from structured data (`reply["data"]["artifact_sha256"]`) or body text regex `ARTIFACT_SHA256:\s*([0-9a-fA-F]{64})\b`.
  * Rejects non-64-character hex strings (e.g. 63 or 65 characters) with `ValueError`.
  * Rejects non-hex characters with `ValueError`.
  * **On-Disk Check:** Verifies deliverable exists and `stat().st_size > 0` (rejects 0-byte touch files).
  * **In-Process Hash Recomputation:** Computes `compute_sha256(deliverable_path)` using 64 KB chunked reads.
  * **Bitflip Detection:** Strictly asserts `actual_sha == claimed_sha`. A single bit difference raises `ValueError("Fail-closed: Cryptographic digest mismatch!")`.

### 2.5 Invariant 5: Per-Run Exclusivity & Append-Only Ledger
In `run_hardened_filebus_model_review.py` (lines 315–380):
- **Collision Denial:**
  * `run_dir = scratch_root / f"run_{run_id}"`
  * `run_dir.mkdir(parents=False, exist_ok=False)` raises `FileExistsError`, caught and converted to `RuntimeError("Exclusive create collision deny: run directory already exists")`.
- **Append-Only Ledger:**
  * `append_receipt_to_ledger()` opens `trial_receipts.jsonl` with mode `"a"`.
  * Serializes receipt as single-line sorted JSON.
  * Wraps file write in `fcntl.flock(f, fcntl.LOCK_EX)` followed by `f.flush()` and `os.fsync()`.
  * Protects ledger permissions at mode `0600`.

### 2.6 Invariant 6: Loaded Source Manifest
In `run_hardened_filebus_model_review.py` (lines 85–103), `build_loaded_source_manifest()` dynamically computes SHA256 digests and file sizes for the runtime components:
- `bus_cli.py`: `/home/alexey/git/agent-bus/coordination/bus_cli.py`
- `bus.py`: `/home/alexey/git/agent-bus/coordination/bus.py`
- Manifest is included directly in the execution receipt JSON, ensuring full supply-chain traceability.

### 2.7 Invariant 7: Accurate Terminology
- Across `run_hardened_filebus_model_review.py` and generated receipts:
  * Authentication is explicitly labeled: `"auth_mechanism": "symmetric_token_auth_per_identity"`.
  * Zero references to asymmetric signatures, public-key certificates, or "signed replies".
  * FileBus token verification is accurately documented as bearer-token verification over file system permissions (mode `0600`).

---

## 3. Automated Test Execution & Empirical Results

### 3.1 Author Test Suite (`test_hardened_runner_guards.py`)
Executed via: `python3 .local/scratch/test_hardened_runner_guards.py -v`
Result: **8/8 PASSED** in 0.023s.

| Test Case | Target Invariant | Mutants / Conditions Tested | Result |
| :--- | :--- | :--- | :---: |
| `test_unsteered_prompt_invariants` | Invariant 1 | Absence of hardcoded verdicts; presence of unsteered guidance | **PASS** |
| `test_fail_closed_verdict_extraction_mutants` | Invariant 2 | Missing verdict, invalid verdicts, text conflict, text-vs-data conflict | **PASS** |
| `test_exact_reply_correlation_mutants` | Invariant 3 | Wrong reply_to, wrong sender_id, body substring trap, empty inbox | **PASS** |
| `test_cryptographic_digest_verification_mutants` | Invariant 4 | Missing SHA, malformed hex, hash mismatch, missing file, 0-byte file | **PASS** |
| `test_per_run_exclusivity_collision_deny` | Invariant 5 | Duplicate run_id collision deny raising `RuntimeError` | **PASS** |
| `test_append_only_ledger` | Invariant 5 | Multi-receipt append preservation, mode 0600 permissions | **PASS** |
| `test_loaded_source_manifest` | Invariant 6 | SHA256 digest computation of loaded `bus_cli.py` and `bus.py` | **PASS** |
| `test_accurate_terminology_invariant` | Invariant 7 | Verification of symmetric token labeling; zero asymmetric claims | **PASS** |

### 3.2 Independent Adversarial Test Suite (`test_adversarial_runner_mutants.py`)
Executed via: `python3 .local/scratch/reviewer37-worker-audit/test_adversarial_runner_mutants.py -v`
Result: **5/5 PASSED** in 0.964s.

| Adversarial Test Case | Invariant Stressed | Adversarial Probes / Vectors | Result |
| :--- | :--- | :--- | :---: |
| `test_verdict_adversarial_boundary_and_injections` | Invariant 2 | Markdown styling variations, quotation injections, near-miss strings | **PASS** |
| `test_correlation_imposter_and_prefix_spoofing` | Invariant 3 | Prefix/suffix spoofing, corrupted non-dict objects in inbox, multi-reply ordering | **PASS** |
| `test_digest_bitflip_and_format_strictness` | Invariant 4 | Bitflip in final SHA character, 63/65-char strings, non-hex characters | **PASS** |
| `test_concurrent_flock_ledger_durability` | Invariant 5 | 20 parallel threads appending concurrently under `flock(LOCK_EX)` | **PASS** |
| `test_e2e_dry_run_workflow` | End-to-End | Complete execution lifecycle in dry-run mode with FileBus protocol | **PASS** |

---

## 4. Live Trial Receipts Ledger Audit

Inspection of `.local/scratch/filebus-hardened-model-review/trial_receipts.jsonl` confirmed 2 durable trial receipts from earlier pilot runs:
- **Receipt 1:**
  * `task_id`: `t-filebus-hardened-review-20261005T072627Z-a3970d5b`
  * `run_id`: `20261005T072627Z-a3970d5b`
  * `auth_mechanism`: `symmetric_token_auth_per_identity`
  * `verdict`: `ACCEPT`
  * `deliverable.sha256`: `26bcad23df970c196120aace486945083986f91beded49106bfea828c26d06a2`
  * `deliverable.publication_guard`: `PASS`
- **Receipt 2:**
  * `task_id`: `t-filebus-hardened-review-20261005T072701Z-617b24ec`
  * `run_id`: `20261005T072701Z-617b24ec`
  * `auth_mechanism`: `symmetric_token_auth_per_identity`
  * `verdict`: `ACCEPT`
  * `deliverable.sha256`: `26bcad23df970c196120aace486945083986f91beded49106bfea828c26d06a2`
  * `deliverable.publication_guard`: `PASS`

Both records conform strictly to schema, record valid source manifests, and reflect mode `0600` file permissions.

---

## 5. Governance & Operational Guard Compliance

1. **Publication Credential Guard:**
   - Executed: `python3 research/antigravity/tooling/publication_guard.py research/antigravity/reviews/REV-FILEBUS-RUNNER-GUARDS.md`
   - Result: **EXIT 0 (CLEAN)**.
2. **Compiler Invariant Under Human Hold:**
   - ZERO `cargo` or `rustc` compiler invocations host-wide during this entire audit.
3. **Telemetry Daemon Protection:**
   - Telemetry collector daemon (PID `1608645`, `scripts/metrics/collect.py`) verified active and undisturbed.
   - Supervision daemon (PID `3265459`, `scripts/supervision/service.py`) verified active and undisturbed.
4. **Scratch Storage Budget:**
   - Scratch usage: 80 KB, strictly within the 512 MB ceiling.
   - Net `/tmp` growth: 0 bytes.
   - Canonical repositories strictly unmodified.

---

## 6. Final Verdict & Certification

**FULL ACCEPTANCE.**

The hardened FileBus model review runner [`.local/scratch/run_hardened_filebus_model_review.py`](file:///home/alexey/git/cloudflare-agent-git/.local/scratch/run_hardened_filebus_model_review.py) and its test suite [`.local/scratch/test_hardened_runner_guards.py`](file:///home/alexey/git/cloudflare-agent-git/.local/scratch/test_hardened_runner_guards.py) strictly satisfy all requirements of Codex Directives C2387, C2392, and C2394. The 4f974 frozen-runner invariants are thoroughly enforced, all 13 unit and adversarial mutation tests pass, and the system demonstrates fail-closed resilience against unauthorized, unverified, or ambiguous review submissions.
