# REV-FILEBUS-RUNNER-GUARDS — Independent Technical Audit & Adversarial Verification of Versioned Hardened FileBus Model Review Runner (Directives C2387, C2392, C2394, C2396 & C2398)

- **Target Versioned Runner:** [`research/antigravity/tooling/self_org/run_hardened_filebus_model_review.py`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/tooling/self_org/run_hardened_filebus_model_review.py)
  * Promoted Canonical Location: `research/antigravity/tooling/self_org/`
  * Staging Path: [`.local/scratch/run_hardened_filebus_model_review.py`](file:///home/alexey/git/cloudflare-agent-git/.local/scratch/run_hardened_filebus_model_review.py)
  * File Size: 29,378 bytes (704 LOC)
  * SHA256 Checksum: `72b50e4938a8b99bf17145c5611e18a736d97f277f851bae88042d19663e670a`
- **Target Canonical Test Suite:** [`tests/test_hardened_runner_guards.py`](file:///home/alexey/git/cloudflare-agent-git/tests/test_hardened_runner_guards.py)
  * Promoted Canonical Location: `tests/`
  * Staging Path: [`.local/scratch/test_hardened_runner_guards.py`](file:///home/alexey/git/cloudflare-agent-git/.local/scratch/test_hardened_runner_guards.py)
  * File Size: 21,487 bytes (467 LOC)
  * SHA256 Checksum: `ab486a192140689d4c5f5d1e3b3f2e316fa13e4705ea75ab2532e016513b0e6e`
- **Target Trial Ledger:** [`.local/scratch/filebus-hardened-model-review/trial_receipts.jsonl`](file:///home/alexey/git/cloudflare-agent-git/.local/scratch/filebus-hardened-model-review/trial_receipts.jsonl)
  * File Mode: `0600` (strictly restricted)
  * Format: Append-only JSON Lines with `fcntl.flock` exclusive locking
- **Independent Adversarial Test Suite:** [`.local/scratch/reviewer37-worker-audit/test_adversarial_runner_mutants.py`](file:///home/alexey/git/cloudflare-agent-git/.local/scratch/reviewer37-worker-audit/test_adversarial_runner_mutants.py)
- **Governing Directives:** Codex Directives C2387, C2392, C2394, C2396, and C2398; Operating Model Reset ([`coordination/OPERATING-MODEL.md`](file:///home/alexey/git/cloudflare-agent-git/coordination/OPERATING-MODEL.md)); User Messages 26, 31, 32, 34
- **Auditor / Challenger:** Independent Reviewer Subagent Reviewer 37 (`37aa1067-8bda-4dde-95b8-7b5bb927bd1f`)
- **Parent Orchestrator:** `antigravity-head` (`46fdb644`, ID `245c7bba-9a7b-45c1-87a7-4537f289f9a5`)
- **Audit Timestamp:** `2026-10-05T08:08:00Z` / `2026-10-05T10:08:00+02:00`
- **Scratch Workspace:** `.local/scratch/reviewer37-worker-audit/` (mode `0700`, disk: 80 KB $\le$ 512 MB ceiling, net `/tmp` growth = 0 bytes)
- **Compiler Invariant:** ZERO `cargo` / `rustc` compiler invocations host-wide under human hold
- **Telemetry Invariant:** Collector daemon PID `1608645` and Supervision daemon PID `3265459` undisturbed
- **Verdict:** **FULL ACCEPTANCE**

---

## 1. Executive Summary & Review Verdict

Under Codex Principal Directives C2387, C2392, C2394, C2396, and C2398, this independent technical audit evaluates the canonical promotion and defect hardening of `d698`'s hardened FileBus model review runner: [`research/antigravity/tooling/self_org/run_hardened_filebus_model_review.py`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/tooling/self_org/run_hardened_filebus_model_review.py) and its test suite [`tests/test_hardened_runner_guards.py`](file:///home/alexey/git/cloudflare-agent-git/tests/test_hardened_runner_guards.py).

The audit verified both the **4f974 frozen-runner invariants** and the **three critical defect repairs mandated by Directive C2396**:
1. **Defect 1 Repair (Body vs. Report Verdict Cross-Validation):** `parse_verdict()` cross-validates deliverable markdown text on disk, FileBus reply body text, and structured data payloads, strictly failing closed if any contradiction exists between sources.
2. **Defect 2 Repair (Multiple Replies Fencing):** `correlate_reply()` examines all matched replies for identical verdicts, artifact SHAs, bodies, and data payloads. If any difference is detected, it fails closed with `ValueError`, completely eliminating silent latest-reply fallback.
3. **Defect 3 Repair (Real Head ACK):** `run_hardened_filebus_review()` executes a genuine `bus_cli.py ack` command for the worker's reply message and records an affirmative `head_ack` block in the execution receipt.

Across the canonical test suite (`tests/test_hardened_runner_guards.py`) and our independent adversarial mutation test suite (`test_adversarial_runner_mutants.py`), **18 out of 18 automated tests passed cleanly** (11 unit tests in 0.970s + 7 adversarial tests in 1.215s).

**Verdict: FULL ACCEPTANCE.** The versioned runner provides robust, fail-closed, multi-agent protocol enforcement for autonomous reviews.

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
In `run_hardened_filebus_model_review.py` (lines 164–247), `parse_verdict()` extracts and validates the final verdict.
- **Audit Verification:**
  * Uses regex `(?:verdict|independent review verdict)\s*[:\-]?\s*[\*`_]*\s*(ACCEPT|BOUNDED ACCEPTANCE|REQUEST_CHANGES|REJECT)\b`.
  * **Missing Verdict Handling:** If no regex match is found, raises `ValueError("Fail-closed: No valid independent verdict found in deliverable or reply")`. Never defaults to `ACCEPT`.
  * **Unrecognized Verdicts:** Non-standard strings (e.g., `LGTM`, `PASS`, `APPROVED`, `ACCEPTED`) fail regex matching and trigger `ValueError`.
  * **Text Conflict Detection:** If multiple distinct verdicts appear in the deliverable text (e.g. an earlier draft stating `ACCEPT` and a later conclusion stating `REJECT`), `len(verdicts_found) > 1` triggers `ValueError("Fail-closed: Conflicting verdicts found within text")`.

### 2.3 Invariant 3: Exact Reply Correlation
In `run_hardened_filebus_model_review.py` (lines 252–321), `correlate_reply()` scans messages from the dispatcher's FileBus inbox.
- **Audit Verification:**
  * Rejects empty inboxes: `if not messages: raise ValueError(...)`.
  * Strictly filters messages: `if reply_to == task_msg_id and sender_id == reviewer_identity_id: matched_replies.append(m)`.
  * **No Substring Traps:** If an attacker message has `reply_to: "unrelated-task"` but puts `task_msg_id` in the message body, it is strictly ignored.
  * **No Prefix/Suffix Spoofing:** String equality `==` prevents imposter sender IDs (e.g. `reviewer_id + "-malicious"` or `"attacker-" + reviewer_id`).
  * If no exact match exists, raises `ValueError("Fail-closed: No reply found correlating to task_msg_id ...")`.

### 2.4 Invariant 4: Cryptographic Digest Verification
In `run_hardened_filebus_model_review.py` (lines 326–372), `extract_artifact_sha256()` and `verify_cryptographic_digest()` validate the output deliverable.
- **Audit Verification:**
  * **Hex Extraction:** Extracts `ARTIFACT_SHA256` from structured data (`reply["data"]["artifact_sha256"]`) or body text regex `ARTIFACT_SHA256:\s*([0-9a-fA-F]{64})\b`.
  * Rejects non-64-character hex strings (e.g. 63 or 65 characters) with `ValueError`.
  * Rejects non-hex characters with `ValueError`.
  * **On-Disk Check:** Verifies deliverable exists and `stat().st_size > 0` (rejects 0-byte touch files).
  * **In-Process Hash Recomputation:** Computes `compute_sha256(deliverable_path)` using 64 KB chunked reads.
  * **Bitflip Detection:** Strictly asserts `actual_sha == claimed_sha`. A single bit difference raises `ValueError("Fail-closed: Cryptographic digest mismatch!")`.

### 2.5 Invariant 5: Per-Run Exclusivity & Append-Only Ledger
In `run_hardened_filebus_model_review.py` (lines 377–442):
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

## 3. Audit of Codex Directive C2396 Defect Repairs

### 3.1 Defect 1: Body vs. Report Verdict Cross-Validation
- **Vulnerability Identified in Pilot:** Earlier implementations parsed the verdict from the report text or reply data, but did not guarantee that the reply body text agreed with the report text on disk. If a compromised or hallucinating model stated `VERDICT: ACCEPT` in the report but `VERDICT: REJECT` in the FileBus reply body, a discrepancy could slip through.
- **Repair in `parse_verdict()` (lines 200–247):**
  ```python
  deliv_verdict = extract_verdict_from_text(deliv_text)
  body_verdict = extract_verdict_from_text(reply_body if isinstance(reply_body, str) else None)
  data_verdict = extract_verdict_from_data(data_dict)

  sources: Dict[str, str] = {}
  if deliv_verdict is not None:
      sources["deliverable"] = deliv_verdict
  if body_verdict is not None:
      sources["reply_body"] = body_verdict
  if data_verdict is not None:
      sources["reply_data"] = data_verdict

  if not sources:
      raise ValueError("Fail-closed: No valid independent verdict found...")

  unique_verdicts = set(sources.values())
  if len(unique_verdicts) > 1:
      details = ", ".join(f"{k}='{v}'" for k, v in sources.items())
      raise ValueError(f"Fail-closed: Contradictory verdicts across sources: {details}")
  ```
- **Verification:**
  * Confirmed that any disagreement (e.g. `deliverable='ACCEPT'` vs. `reply_body='REJECT'`) immediately raises `ValueError`.
  * Verified in `tests/test_hardened_runner_guards.py` (`test_reply_body_vs_deliverable_verdict_mismatch_fails_closed`) and adversarial suite (`test_c2396_defect_1_cross_source_contradiction`).

### 3.2 Defect 2: Multiple Replies Fencing
- **Vulnerability Identified in Pilot:** If a reviewer or network glitch produced multiple replies correlating to the same `task_msg_id`, earlier implementations silently defaulted to `matched_replies[-1]` (the latest reply). This risked masking review tampering or desynchronized responses.
- **Repair in `correlate_reply()` (lines 288–319):**
  ```python
  if len(matched_replies) > 1:
      first_rep = matched_replies[0]
      first_verdict = extract_verdict_from_text(first_rep.get("body")) or extract_verdict_from_data(first_rep.get("data"))
      first_sha = extract_artifact_sha256(first_rep)

      for idx, other_rep in enumerate(matched_replies[1:], start=2):
          other_verdict = extract_verdict_from_text(other_rep.get("body")) or extract_verdict_from_data(other_rep.get("data"))
          other_sha = extract_artifact_sha256(other_rep)

          if first_verdict != other_verdict or first_sha != other_sha:
              raise ValueError(
                  f"Fail-closed: Multiple conflicting replies detected for task_msg_id '{task_msg_id}' "
                  f"(verdicts: {first_verdict} vs {other_verdict}, sha: {first_sha} vs {other_sha})"
              )

          if first_rep.get("body") != other_rep.get("body") or first_rep.get("data") != other_rep.get("data"):
              raise ValueError(
                  f"Fail-closed: Multiple conflicting replies detected for task_msg_id '{task_msg_id}' "
                  f"(non-identical reply contents/data)"
              )

      return matched_replies[0]
  ```
- **Verification:**
  * Confirmed that multiple replies with differing verdicts, different artifact hashes, or different body notes raise `ValueError`.
  * Only 100% identical idempotent duplicates are permitted to proceed.
  * Verified in `tests/test_hardened_runner_guards.py` (`test_multiple_conflicting_replies_fails_closed`) and adversarial suite (`test_c2396_defect_2_multiple_replies_fencing`).

### 3.3 Defect 3: Real Head ACK
- **Vulnerability Identified in Pilot:** The reviewer acknowledged the task message upon intake, but the dispatcher did not issue a protocol-level ACK for the reviewer's completion reply message.
- **Repair in `run_hardened_filebus_review()` (lines 637–644, 660):**
  ```python
  # 11. Real Head ACK for Worker Reply (Directive C2396)
  _run_bus(["ack", "--message-id", reply_msg_id, "--cred", str(dispatcher_cred)])
  head_ack_data = {
      "reply_msg_id": reply_msg_id,
      "acked": True,
      "acked_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
  }
  ```
  The execution receipt now includes the explicit `"head_ack"` object stamped with the acknowledged reply message ID and timestamp.
- **Verification:**
  * Verified in `tests/test_hardened_runner_guards.py` (`test_head_ack_emitted_on_completion`) and adversarial suite (`test_c2396_defect_3_head_ack_in_dry_run_workflow`).

---

## 4. Automated Test Execution & Empirical Results

### 4.1 Canonical Repository Test Suite (`tests/test_hardened_runner_guards.py`)
Executed via: `python3 -m unittest discover -s tests -p "test_hardened_runner_guards.py" -v`
Result: **11/11 PASSED** in 0.970s.

| Test Case | Directive / Invariant | Probes & Conditions Tested | Status |
| :--- | :--- | :--- | :---: |
| `test_unsteered_prompt_invariants` | Invariant 1 | Absence of hardcoded verdicts; presence of unsteered guidance | **PASS** |
| `test_fail_closed_verdict_extraction_mutants` | Invariant 2 | Missing verdict, invalid verdicts, text conflict | **PASS** |
| `test_reply_body_vs_deliverable_verdict_mismatch_fails_closed` | C2396 Defect 1 | Deliverable vs. reply body contradiction fails closed with `ValueError` | **PASS** |
| `test_exact_reply_correlation_mutants` | Invariant 3 | Wrong reply_to, wrong sender_id, body substring trap, empty inbox | **PASS** |
| `test_multiple_conflicting_replies_fails_closed` | C2396 Defect 2 | Multiple replies with conflicting verdicts/payloads fail closed | **PASS** |
| `test_cryptographic_digest_verification_mutants` | Invariant 4 | Missing SHA, malformed hex, hash mismatch, missing file, 0-byte file | **PASS** |
| `test_per_run_exclusivity_collision_deny` | Invariant 5 | Duplicate run_id collision deny raising `RuntimeError` | **PASS** |
| `test_append_only_ledger` | Invariant 5 | Multi-receipt append preservation, mode 0600 permissions | **PASS** |
| `test_loaded_source_manifest` | Invariant 6 | SHA256 digest computation of loaded `bus_cli.py` and `bus.py` | **PASS** |
| `test_accurate_terminology_invariant` | Invariant 7 | Verification of symmetric token labeling; zero asymmetric claims | **PASS** |
| `test_head_ack_emitted_on_completion` | C2396 Defect 3 | Real FileBus ACK dispatched and stamped in execution receipt | **PASS** |

### 4.2 Independent Adversarial Test Suite (`test_adversarial_runner_mutants.py`)
Executed via: `python3 .local/scratch/reviewer37-worker-audit/test_adversarial_runner_mutants.py -v`
Result: **7/7 PASSED** in 1.215s.

| Adversarial Test Case | Invariant Stressed | Adversarial Probes / Vectors | Status |
| :--- | :--- | :--- | :---: |
| `test_verdict_adversarial_boundary_and_injections` | Invariant 2 | Markdown styling variations, quotation injections, near-miss strings | **PASS** |
| `test_c2396_defect_1_cross_source_contradiction` | C2396 Defect 1 | Multi-source contradiction (deliverable vs body vs data) | **PASS** |
| `test_c2396_defect_2_multiple_replies_fencing` | C2396 Defect 2 | Differing verdicts, differing SHAs, differing notes, identical duplicates | **PASS** |
| `test_correlation_imposter_and_prefix_spoofing` | Invariant 3 | Prefix/suffix spoofing, corrupted non-dict objects in inbox | **PASS** |
| `test_digest_bitflip_and_format_strictness` | Invariant 4 | Bitflip in final SHA character, 63/65-char strings, non-hex characters | **PASS** |
| `test_concurrent_flock_ledger_durability` | Invariant 5 | 20 parallel threads appending concurrently under `flock(LOCK_EX)` | **PASS** |
| `test_c2396_defect_3_head_ack_in_dry_run_workflow` | C2396 Defect 3 | End-to-end dry run verifying real Head ACK emission and receipt stamping | **PASS** |

---

## 5. Live Trial Receipts Ledger Audit

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

## 6. Governance & Operational Guard Compliance

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
   - Canonical repositories strictly unmodified (except this review deliverable).

---

## 7. Final Verdict & Certification

**FULL ACCEPTANCE.**

The versioned hardened FileBus model review runner [`research/antigravity/tooling/self_org/run_hardened_filebus_model_review.py`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/tooling/self_org/run_hardened_filebus_model_review.py) (SHA256: `72b50e4938a8b99bf17145c5611e18a736d97f277f851bae88042d19663e670a`) and its test suite [`tests/test_hardened_runner_guards.py`](file:///home/alexey/git/cloudflare-agent-git/tests/test_hardened_runner_guards.py) (SHA256: `ab486a192140689d4c5f5d1e3b3f2e316fa13e4705ea75ab2532e016513b0e6e`) strictly satisfy all requirements of Codex Directives C2387, C2392, C2394, C2396, and C2398. All 3 C2396 defects have been successfully repaired, all 18 unit and adversarial mutation tests pass, and the system demonstrates complete fail-closed integrity against review spoofing, desynchronization, and tampering.
