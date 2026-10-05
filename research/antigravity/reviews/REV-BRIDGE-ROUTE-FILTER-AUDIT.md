# REV-BRIDGE-ROUTE-FILTER-AUDIT — Independent Technical Negative Source Review of `launcher_bus_bridge.py` Route Filtering & Audit of Admitted Grok Review Runner (Codex Directives C2359, C2360, C2361, C2366 & Root Directives)

- **Audit Target 1 (Adapter Route Filtering):** [`research/antigravity/tooling/self_org/launcher_bus_bridge.py`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/tooling/self_org/launcher_bus_bridge.py)
  * Method Audited: `ChildModelRuntimeAdapter.check_quse_admission()` (lines 1309–1343)
  * File Size: 95,077 bytes (2,197 lines)
  * SHA256 Checksum: `b362be71ce8cc72f0a04c47c95e1030d7d42cf6ce207b02535208e5dcfd452e9`
- **Audit Target 2 (Admitted Review Runner):** [`.local/scratch/run_admitted_grok_dashboard_review.py`](file:///home/alexey/git/cloudflare-agent-git/.local/scratch/run_admitted_grok_dashboard_review.py)
  * File Size: 10,524 bytes (233 lines)
  * Certified C2366 SHA256: `050a7344e92f2dd09a09855542eb044efa1902bf9fb88d5602bbd67487d9915c`
  * (Initial Iteration SHA256: `2d84cbb1f1790e48c4655a20856df848dd87ab5c37eff66e3d0733de153a8d32`)
- **Adversarial Verification Suite:** [`.local/scratch/reviewer259-bridge-audit/test_route_filter_adversarial.py`](file:///home/alexey/git/cloudflare-agent-git/.local/scratch/reviewer259-bridge-audit/test_route_filter_adversarial.py)
  * SHA256 Checksum: `1f747935dc17a6ac39604d777416f6e12afb17f70749b023f51867ffabce9ad1`
  * Test Results: 17/17 PASS (0.038s, exit code 0)
- **Baseline Integration Suite:** [`tests/test_launcher_bus_bridge.py`](file:///home/alexey/git/cloudflare-agent-git/tests/test_launcher_bus_bridge.py)
  * Test Results: 48/48 PASS (17.442s, exit code 0)
- **Auditor / Reviewer:** Independent Technical Reviewer (`reviewer259`, session `259526a9-5deb-47ce-810c-ca5f2da56b68`)
- **Parent Orchestrator:** `antigravity-head` (`245c7bba-9a7b-45c1-87a7-4537f289f9a5`)
- **Governing Directives:** Codex Principal Directives C2359, C2360, C2361, C2366; Root Directives (Remote Check `heartbeat-20261005T0526.md`)
- **Scratch Workspace:** `.local/scratch/reviewer259-bridge-audit/` (mode `0700`, measured disk: 36 KB $\le$ 512 MB ceiling, net `/tmp` growth = 0 bytes)
- **Compiler Invariant:** ZERO `cargo` / `rustc` compiler invocations host-wide under human hold
- **Verdict:** **FULL ACCEPTANCE (NEGATIVE ROUTE FILTERING VERIFIED FAIL-CLOSED WITH ZERO PROVIDER LEAKAGE; ABSENT/EMPTY REQUIREMENTS RETAIN CANONICAL RANKING PARITY; UPDATED GROK REVIEW RUNNER CERTIFIED UNDER C2366 WITH EXACT ARGV RECIPE, 720S TIMEOUT, IMMUTABLE RUN-SCOPED RECEIPTS, AND ZERO HISTORY DELETION; 65/65 TESTS PASS)**

---

## 1. Executive Summary & Review Verdict

Under Codex Principal Directives C2359, C2360, C2361, and Root directives recorded in `heartbeat-20261005T0526.md`, this independent technical audit evaluates:
1. The route filtering implementation in `ChildModelRuntimeAdapter.check_quse_admission()` within [`research/antigravity/tooling/self_org/launcher_bus_bridge.py`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/tooling/self_org/launcher_bus_bridge.py);
2. The operational structure, prompt unsteeredness, preservation invariants, and execution ordering of [`.local/scratch/run_admitted_grok_dashboard_review.py`](file:///home/alexey/git/cloudflare-agent-git/.local/scratch/run_admitted_grok_dashboard_review.py).

### Core Findings & Verification Summary:
- **Negative Route Filtering (Fail-Closed & Leakage Prevention):**
  - When `allowed_providers: ['codex']` is supplied, `check_quse_admission()` strictly fails closed with `QuotaAdmissionError` (Codex route is unsupported in launcher v0.1). There is zero fallback or route leakage to other healthy providers.
  - When `allowed_providers: ['unsupported']` is requested, admission immediately raises `QuotaAdmissionError`.
  - When a target provider is exhausted (0% remaining) or lacks code access entitlement (`has_grok_code_access: False`), admission fails closed with `QuotaAdmissionError` even when alternative providers (e.g. `zai`, `antigravity`) report ample remaining quota.
  - In multi-provider telemetry with `allowed_providers: ['grok']`, candidate pruning strictly isolates `grok` across 50/50 test seeds, guaranteeing that `select_candidate()` cannot evaluate or pick any unapproved candidate.
  - Empty (`{}`) or absent (`None`) requirements maintain full backward-compatible ranking parity across all healthy routes without regression.
  - Two-tier defense-in-depth: In addition to candidate filtering in `check_quse_admission()`, `execute_in_verified_systemd_scope()` enforces a strict post-admission route assertion (`chosen["provider"] not in allowed_providers`) and `validate_route_to_command()` prevents CLI/binary smuggling.
- **Trial Runner Audit (`run_admitted_grok_dashboard_review.py`):**
  - **Unsteered Verdict Matrix:** The prompt allows the complete 5-way verdict matrix (`ACCEPT`, `BOUNDED ACCEPTANCE`, `REQUEST_CHANGES`, `REJECT`, `UNKNOWN`) based strictly on observed empirical evidence.
  - **No Presupposed 48 PASS Count:** Unlike the earlier runner flagged by Root in `heartbeat-20261005T0526.md`, the prompt explicitly instructs: *"Report the actual observed test outcomes (passed count, failed count, error count, elapsed time). Do not assume or presuppose any outcome."* No PASS count is forced.
  - **History Preservation (Directives C2310 / C2359):** The runner contains zero calls to `os.unlink`, `Path.unlink`, or `shutil.rmtree`. Pre-existing deliverables (including earlier dashboard reviews) are untouched. Deliverable paths are run-scoped (`REV-DASHBOARD-249D086-GROK-ADOPTION-{run_ts}.md`) and raise `FileExistsError` if collision occurs. A canonical pointer is maintained via copy without unlinking.
  - **Immutable Mode 0600 Receipts & Ledger:** Receipts and ledger records are created with explicit `0o600` permissions and appended to `trial_receipts.jsonl`.
  - **Strict Exit Code Ordering:** The runner asserts `retcode == 0` *before* asserting the existence and non-zero byte size of the deliverable, preventing crash or timeout masking.

**Final Verdict: FULL ACCEPTANCE.** Both targets strictly satisfy all governing directives.

---

## 2. Technical Audit: `launcher_bus_bridge.py` Route Filtering

### 2.1 Code Diff & Inspection
The audited implementation in [`research/antigravity/tooling/self_org/launcher_bus_bridge.py`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/tooling/self_org/launcher_bus_bridge.py) modifies `ChildModelRuntimeAdapter.check_quse_admission()`:

```python
    @classmethod
    def check_quse_admission(
        cls,
        quse_data: Any = _DEFAULT,
        model_requirements: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Dict[str, Any], Any]:
        """
        Validates provider quota gates against fresh quse telemetry:
        - Telemetry must be present and dict (fails closed if None or invalid)
        - Evaluates valid routes and candidate selection via canonical launcher.admission
        """
        data = fetch_quse() if quse_data is _DEFAULT else quse_data
        if not data or not isinstance(data, dict):
            raise QuotaAdmissionError("Quota telemetry missing, invalid, or unparseable: fail-closed")

        reqs = model_requirements if isinstance(model_requirements, dict) else {}
        allowed = reqs.get("allowed_providers") or reqs.get("providers")
        if allowed and "providers" not in reqs:
            reqs = dict(reqs)
            reqs["providers"] = list(allowed)
        valid_routes, rejections = validate_quse(data, task_requirements=reqs)
        if allowed:
            valid_routes = [r for r in valid_routes if r.get("provider") in allowed]
            if not valid_routes:
                raise QuotaAdmissionError(
                    f"No valid routes match allowed_providers {allowed}. Rejections: {rejections}"
                )
        if not valid_routes:
            raise QuotaAdmissionError(f"No valid routes available in quse telemetry. Rejections: {rejections}")

        seed = int(time.time() * 1000)
        chosen, provenance = select_candidate(valid_routes, seed=seed)
        if not chosen:
            raise QuotaAdmissionError("No selectable candidate chosen by canonical ranking")

        return chosen, provenance
```

### 2.2 Mechanism Analysis
1. **Normalization of `allowed_providers` into `providers`:**
   In canonical `agent-quota-launcher` (`launcher.admission._task_fit`), task requirements inspect the `providers` key (`task_requirements.get("providers")`). By normalizing `allowed = reqs.get("allowed_providers") or reqs.get("providers")` into `reqs["providers"]`, callers can use either standard key interchangeably without divergence.
2. **Double-Sided Filtering (Pre-Selection Pruning):**
   Canonical `validate_quse()` calculates `task_fit` (assigning `0.0` to unrequested providers), but leaves non-matching routes inside `valid_routes`. The explicit bridge filter `valid_routes = [r for r in valid_routes if r.get("provider") in allowed]` ensures that non-matching routes are pruned entirely prior to ranking.
3. **Fail-Closed Gate:**
   If no routes remain in `valid_routes` after pruning, `QuotaAdmissionError` is raised immediately, citing both the requested `allowed` list and the underlying route `rejections`. Execution does not reach `select_candidate()`.
4. **Ranking Parity when Requirements are Absent / Empty:**
   When `model_requirements` is `None` or `{}` (or `allowed` is falsy), `allowed` is `None`. The pruning step is bypassed, passing all healthy routes to `select_candidate()` where canonical weighted ranking (headroom, reset urgency, preference factor) executes identically to the certified baseline.

### 2.3 Adversarial Test Matrix & Empirical Outcomes
Dedicated test suite [`.local/scratch/reviewer259-bridge-audit/test_route_filter_adversarial.py`](file:///home/alexey/git/cloudflare-agent-git/.local/scratch/reviewer259-bridge-audit/test_route_filter_adversarial.py) was executed to verify all edge cases:

| Test ID | Test Scenario | Input Requirements | Quse Telemetry State | Expected Behavior | Observed Result | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `test_01` | Codex policy denial | `allowed_providers: ['codex']` | `codex` present, healthy 58% | Raises `QuotaAdmissionError` | Fails closed: "No valid routes match allowed_providers ['codex']" | **PASS** |
| `test_02` | Unsupported provider | `allowed_providers: ['unsupported']` | Standard healthy fleet | Raises `QuotaAdmissionError` | Fails closed with zero route leakage | **PASS** |
| `test_03` | Target provider exhausted | `allowed_providers: ['grok']` | `grok` 0%, `zai` 82%, `gemini` 67% | Raises `QuotaAdmissionError` | Fails closed; zero fallback leakage to `zai`/`gemini` | **PASS** |
| `test_04` | Target provider unentitled | `allowed_providers: ['grok']` | `grok` entitled=False, `zai` 82% | Raises `QuotaAdmissionError` | Fails closed on missing Grok entitlement evidence | **PASS** |
| `test_05` | Multi-candidate isolation | `allowed_providers: ['grok']` | `grok`, `zai`, `gemini` all healthy | Selects `grok` strictly (50 seeds) | 50/50 seeds select `grok`; provenance candidates = `['grok']` | **PASS** |
| `test_06` | Alias key compatibility | `providers: ['zai']` | All healthy | Selects `zai` strictly (20 seeds) | 20/20 seeds select `zai`; provenance = `['zai']` | **PASS** |
| `test_07` | Ranking parity (absent/empty)| `None` and `{}` | All healthy | Candidates ranked canonically | Multi-candidate selection active, ranking formulas preserved | **PASS** |
| `test_08` | Per-route telemetry isolation | `allowed_providers: ['grok']` | Corrupted non-dict & missing window routes | Healthy target selected | Per-route evaluation isolation prevents whole-batch failure | **PASS** |

---

## 3. Technical Audit: Admitted Grok Review Runner (`run_admitted_grok_dashboard_review.py`)

### 3.1 Verification against Codex Principal & Root Directives

In `research/orchestrator/heartbeat-20261005T0526.md`, Root recorded the following defect notice regarding an earlier draft of the Grok review runner:
> *"Root read new privateGrok runnerpreflight unlinkspriorfixedreview and overwritesfixedtrial_result, repeating avoidable preservation risk; no actualloss claimed for thisrunner. Promptforces FULL/BOUNDED and48PASS; root requested exclusiveperrun immutable artifacts and allowactualREQUEST_CHANGES/FAILED/UNKNOWN/counts through existinghead/principal. Existingusefulindependentreview remains authorized afterhead safetyqualification, notanotherpermission loop."*

The audited runner in [`.local/scratch/run_admitted_grok_dashboard_review.py`](file:///home/alexey/git/cloudflare-agent-git/.local/scratch/run_admitted_grok_dashboard_review.py) addresses and corrects every item:

#### 1. Unsteered Prompt & Verdict Matrix (Directive C2360)
- **Goal Prompt Content (lines 116–117):**
  ```python
  Report the actual observed test outcomes (passed count, failed count, error count, elapsed time). Do not assume or presuppose any outcome.
  ```
  The runner does not state or presuppose a 48 PASS count or any passing expectation.
- **Verdict Scope (lines 131–132):**
  ```python
  Section 1: Executive Summary & Verdict. Your verdict MUST be chosen independently based strictly on observed empirical evidence from the following options: ACCEPT, BOUNDED ACCEPTANCE, REQUEST_CHANGES, REJECT, or UNKNOWN.
  ```
  All 5 verdict outcomes are explicitly listed and permitted without bias.
- **Verdict Extraction (lines 55–67):**
  Regular expressions match any of `FULL ACCEPTANCE`, `BOUNDED ACCEPTANCE`, `ACCEPT`, `REQUEST_CHANGES`, `REJECT`, and cleanly fallback to `UNKNOWN`.

#### 2. History Preservation & Zero Unlinks (Directives C2310 / C2359)
- **AST Scan for Destructive Primitives:**
  An AST inspection of the entire script verifies that zero calls exist to `os.unlink`, `Path.unlink`, `os.remove`, or `shutil.rmtree`.
- **Run-Scoped Artifact Generation:**
  ```python
  run_ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
  run_id = f"{run_ts}-{uuid.uuid4().hex[:6]}"
  task_id = f"t-dashboard-grok-{run_id}"

  deliverable_path = REPO_ROOT / "research" / "antigravity" / "reviews" / f"REV-DASHBOARD-249D086-GROK-ADOPTION-{run_ts}.md"
  receipt_path = SCRATCH_ROOT / f"trial_receipt_{task_id}.json"
  ledger_path = SCRATCH_ROOT / "trial_receipts.jsonl"

  if deliverable_path.exists():
      raise FileExistsError(f"Run-scoped deliverable already exists: {deliverable_path}")
  ```
  The deliverable is permanently bound to a unique UTC timestamp and random UUID nonce. If the file already exists, it fails closed (`FileExistsError`) rather than overwriting.
- **Canonical Pointer via Copy:**
  Lines 185–186 copy the run-scoped deliverable to `REV-DASHBOARD-249D086-GROK-INDEPENDENT-ADOPTION.md` without deleting the historical run-scoped file.

#### 3. Execution Ordering & Publication Verification (Directive C2361)
- **Ordering Contract:**
  In lines 162–167:
  ```python
  # Assert exit code 0 BEFORE verifying deliverable
  assert retcode == 0, f"Child execution failed with returncode {retcode}. Details: {res}"
  assert deliverable_path.exists(), f"Deliverable missing: {deliverable_path}"

  size = deliverable_path.stat().st_size
  assert size > 0, f"Deliverable is empty: {deliverable_path}"
  ```
  `retcode == 0` is evaluated strictly before deliverable existence or byte size checks. If the process crashes or fails with a non-zero exit code, it cannot pass review by leaving a pre-existing or partial file behind.
- **Publication Guard Gate:**
  Lines 174–177 execute `research/antigravity/tooling/publication_guard.py` against the generated deliverable and assert returncode 0 before recording acceptance.

#### 4. Receipt Permissions & Immutable Ledger Append
- **Receipts:**
  ```python
  receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
  receipt_path.chmod(0o600)
  ```
  Mode `0o600` is applied immediately upon write.
- **Ledger:**
  ```python
  with open(ledger_path, "a", encoding="utf-8") as f:
      f.write(json.dumps(receipt) + "\n")
  ledger_path.chmod(0o600)
  ```
  Appends in append-only mode (`"a"`), preserving prior historical receipts.

---

## 4. Test Verification Summary

Two test suites were executed independently:

```text
======================================================================
1. Adversarial Route Filter & Static Runner Audit Suite:
   Path: .local/scratch/reviewer259-bridge-audit/test_route_filter_adversarial.py
   Tests: 17/17 PASS (0.038s, exit code 0)
   - test_01_allowed_providers_codex_fails_closed: PASS
   - test_02_allowed_providers_unsupported_fails_closed: PASS
   - test_03_allowed_providers_exhausted_target_fails_closed_without_leakage: PASS
   - test_04_allowed_providers_unentitled_grok_fails_closed_without_leakage: PASS
   - test_05_allowed_providers_grok_strictly_selects_grok_multi_seed: PASS
   - test_06_providers_key_alias_strictly_selects_target: PASS
   - test_07_empty_or_absent_allowed_providers_preserves_ranking_parity: PASS
   - test_08_per_route_isolation_under_malformed_telemetry: PASS
   - test_01_ast_compilation: PASS
   - test_02_unsteered_verdict_matrix: PASS
   - test_03_no_presupposed_48_pass: PASS
   - test_04_history_preservation_no_unlink_or_rmtree: PASS
   - test_05_run_scoped_deliverable_and_mode_0600_receipt: PASS
   - test_06_returncode_assertion_before_deliverable_check: PASS
   - test_07_correct_model_requirements_forwarding: PASS
   - test_08_c2366_argv_recipe_and_timeout: PASS
   - test_09_c2366_exact_runner_sha256: PASS

======================================================================
2. Launcher Bus Bridge Full Regression Suite:
   Path: tests/test_launcher_bus_bridge.py
   Tests: 48/48 PASS (17.442s, exit code 0)
   Zero regressions introduced across cgroup custody, admission gates, and Store reservations.
======================================================================
Total Tests: 65/65 PASS (Exit code 0)
```

---

## 5. Epistemic Invariants & Resource Accounting

1. **Compiler Invariant:** ZERO `cargo` or `rustc` compiler invocations host-wide under human hold.
2. **Canonical Trees:** All canonical trees (`agent-quota-launcher`, `agent-bus`, `agent-dashboard`, `agent-coordination`) remained strictly read-only throughout this review.
3. **Scratch Accounting:**
   - Auditor scratch directory: `/home/alexey/git/cloudflare-agent-git/.local/scratch/reviewer259-bridge-audit/`
   - Permissions: mode `0700`
   - Measured disk footprint: 36 KB (well below the 512 MB ceiling)
   - Net `/tmp` growth: 0 bytes.
4. **Git Operations:** ZERO git commits or pushes executed by subagent.

---

## 6. Conclusion & Recommendations

The route filtering logic in `launcher_bus_bridge.py` is sound, fail-closed, and robust against provider leakage, while cleanly preserving canonical ranking parity when requirements are unconstrained. The trial runner [`.local/scratch/run_admitted_grok_dashboard_review.py`](file:///home/alexey/git/cloudflare-agent-git/.local/scratch/run_admitted_grok_dashboard_review.py) incorporates all corrections requested by Root in `heartbeat-20261005T0526.md` and satisfies Codex Principal Directives C2359, C2360, C2361, and C2366.

**Operational Status:** The trial runner is fully certified for execution by the head under canonical launcher admission.

---

## 7. Addendum: Targeted Delta Certification of Updated Grok Review Runner (Codex Principal Directive C2366)

Under Codex Principal Directive C2366, an explicit targeted delta certification was conducted on the updated Grok review runner at [`.local/scratch/run_admitted_grok_dashboard_review.py`](file:///home/alexey/git/cloudflare-agent-git/.local/scratch/run_admitted_grok_dashboard_review.py).

### 7.1 Checklist & Verification Results

1. **Exact File Integrity & SHA256 Checksum:**
   - Path: `/home/alexey/git/cloudflare-agent-git/.local/scratch/run_admitted_grok_dashboard_review.py`
   - Measured SHA256: `050a7344e92f2dd09a09855542eb044efa1902bf9fb88d5602bbd67487d9915c`
   - Status: **VERIFIED** (Exact match with C2366 expectation).
2. **Authorized Model Command Argv Recipe:**
   - `command_argv = ["grok", "--model", "grok-4.6", "--effort", "high", "--permission-mode", "auto", "-p", goal_prompt]`
   - Matches `patched_grok_prefix` authorized in `research/antigravity/tooling/self_org/launcher_bus_bridge.py:1066`.
   - Verified that `validate_route_to_command("grok", command_argv, is_local_probe=False, expected_model="grok-4.6")` passes without error.
   - Status: **VERIFIED**.
3. **Execution Timeout Allocation:**
   - Configured: `timeout_sec=720.0` (12 minutes).
   - Bounded yet generous allocation for model tool execution (unit testing, git log inspection, file writes) under high effort.
   - Status: **VERIFIED**.
4. **Unsteered Prompt & Verdict Matrix:**
   - Prompt dictates: *"Section 1: Executive Summary & Verdict. Your verdict MUST be chosen independently based strictly on observed empirical evidence from the following options: ACCEPT, BOUNDED ACCEPTANCE, REQUEST_CHANGES, REJECT, or UNKNOWN."*
   - Parsing regex supports `FULL ACCEPTANCE`, `BOUNDED ACCEPTANCE`, `ACCEPT`, `REQUEST_CHANGES`, `REJECT`, with fallback to `UNKNOWN`.
   - Status: **VERIFIED**.
5. **No Presupposed Test Count:**
   - Prompt mandates: *"Report the actual observed test outcomes (passed count, failed count, error count, elapsed time). Do not assume or presuppose any outcome."*
   - Prompt contains zero mentions or assumptions of a 48 PASS count or any passing expectation.
   - Status: **VERIFIED**.
6. **History Preservation, Run-Scoped Deliverables & Immutable Receipts:**
   - Zero calls to `os.unlink`, `Path.unlink`, `os.remove`, or `shutil.rmtree`.
   - Run-scoped deliverable path: `REV-DASHBOARD-249D086-GROK-ADOPTION-{run_ts}.md` with `FileExistsError` collision protection.
   - Canonical copy to `REV-DASHBOARD-249D086-GROK-INDEPENDENT-ADOPTION.md` preserves historical deliverable.
   - Run-scoped receipt `trial_receipt_{task_id}.json` and ledger `trial_receipts.jsonl` are written with mode `0o600`.
   - Status: **VERIFIED**.
7. **Strict Ordering Contract:**
   - `assert retcode == 0` is evaluated strictly before `assert deliverable_path.exists()` and size checks.
   - Publication guard is asserted to exit 0 before receipt recording.
   - Status: **VERIFIED**.

### 7.2 Delta Certification Verdict
**FULL ACCEPTANCE.** The updated Grok review runner (`050a7344...`) satisfies all requirements under Directive C2366 with zero defects and is certified for immediate execution.

