# REV-DASHBOARD-ALIAS-AND-FOURTH-PROJECT — Independent Audit: Minimal Dashboard Alias & Fourth Product Patch

- **Review Target:** `/home/alexey/git/agent-dashboard` (STRICTLY READ-ONLY AUDIT)
- **Reviewer:** Independent Agent Dashboard Minimal Patch Reviewer (tag: `dashboard-adr2-reviewer`)
- **Dispatched By:** `antigravity-head` (`46fdb644-9b58-4e2f-aab3-9be5e1e33337`), under Codex Principal C2041 directives
- **As-of:** 2026-10-04 22:51 CEST (20:51 UTC)
- **Review Workspace:** `/home/alexey/git/cloudflare-agent-git`
- **Output Deliverable:** [`research/antigravity/reviews/REV-DASHBOARD-ALIAS-AND-FOURTH-PROJECT.md`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/reviews/REV-DASHBOARD-ALIAS-AND-FOURTH-PROJECT.md)
- **Scratch Workspace:** `/home/alexey/git/cloudflare-agent-git/.local/scratch/dashboard-minimal-patch-review/` (mode `0700`, measured disk: 460 KB $\le$ 512 MB, zero net `/tmp` growth)
- **Patch Under Audit:** [`research/antigravity/recovery/dashboard-alias-and-fourth-project-minimal.patch`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/recovery/dashboard-alias-and-fourth-project-minimal.patch) (137 lines, 6,817 bytes)
- **Integration Ownership:** Strictly reserved to `agent-dashboard-head`; **zero competitor writes or edits** made to `/home/alexey/git/agent-dashboard`
- **Compiler Hold:** Zero cargo/rustc invocations under human hold
- **Verdict:** **FULL ACCEPTANCE (CLEAN PATCH APPLICATION, 48/48 UNIT TESTS PASSING IN 0.63s, BIT-FOR-BIT HASH VERIFICATION ON ALL 3 TARGET FILES, AND PROVEN DRIFT REFUSAL)**

---

## 1. Executive Summary & Review Verdict

Under Codex Principal directive C2041, User messages 26/32, and the authoritative delivery reset (2026-10-04), this independent audit conducts an exact-pin verification of the minimal **Dashboard Alias & Fourth Project patch** (`dashboard-alias-and-fourth-project-minimal.patch`).

The patch addresses the two core consumer contract defects identified during the AD-R2 review:
1. **Defect 1 (`agent-quota-launcher` Unattributed Leakage):** Telemetry, working directory, and reports from Quota Launcher emit `"agent-quota-launcher"`, which previously fell back to `"unattributed"`. The patch introduces `PROJECT_ALIASES` mapping `"agent-quota-launcher"` and `"agent_quota_launcher"` to canonical `"quota-launcher"`.
2. **Defect 2 (Fourth Authorized Product `agent-coordination` Absent):** The newly authorized product—Cross-computer Agent Coordination—was previously absent from `CANONICAL_PROJECT_IDS`. The patch integrates `"agent-coordination"` into `CANONICAL_PROJECT_IDS` and wires corresponding accounting and hourly utilization tracking.

### Key Audit Findings:

1. **Strict Target Workspace Immutability:**
   - The primary workspace `/home/alexey/git/agent-dashboard` was audited in a strictly read-only mode.
   - **Zero file edits, staging operations, or git commits** were performed on `/home/alexey/git/agent-dashboard`. All patching, mutation testing, and test runs were isolated within `.local/scratch/dashboard-minimal-patch-review/`.

2. **Bit-for-Bit SHA256 Hash Verification:**
   - All 3 target files match their baseline hashes prior to patching:
     * `src/dashboard/__init__.py`: `5211df320cfac2cfc5c0e79a9eb00ce2135d99ccca55d57b5141ca2270cb6e4a`
     * `tests/test_accounting.py`: `bde672ecd0a3560f2aa4d7333dbf3dfa44972fcb218aa676a8ab3b05f110cb75`
     * `tests/test_hourly.py`: `17777a397648cef56c68d346afa44bdc68a27b8a93df573ddd6d6cb2d584e4c5`
   - Following patch application, all 3 patched files match their target expected SHA256 hashes bit-for-bit:
     * `src/dashboard/__init__.py`: `15a53aa140fb74ebc3fa6e045b476f5ab4f25f3443c837792615455f89c436c7`
     * `tests/test_accounting.py`: `ab29fc2d9edda6ca5487b0750987169e944dc88d6237132978d5240e6e11e396`
     * `tests/test_hourly.py`: `355056ffc5d5cfb7667b29746a6cebe723358232d21372a04584faf15dd0d446`

3. **Dry-Run & Clean Application:**
   - `patch -p1 --dry-run` checked cleanly with zero rejects and zero fuzz.
   - Patch application completed with exit code 0.

4. **Drift Refusal Tested & Confirmed:**
   - In an isolated drift testbed, synthetic drift was introduced into `src/dashboard/__init__.py`.
   - Applying the patch against the drifted baseline failed closed with `Hunk #1 FAILED at 8` (exit code 1), confirming strict drift protection.

5. **48-Test Suite Verification (100% Pass Rate):**
   - The test suite expands from 44 to **48 unit tests** (adding 2 tests in `test_accounting.py` and 2 tests in `test_hourly.py`).
   - Full suite execution via `PYTHONPATH=src python3 -m unittest discover -s tests/ -v`: **48/48 PASS in 0.633s**.

6. **Negative Mutation Testing in Scratch:**
   - **Mutant A (Dropping `agent-coordination`):** Resulted in 4 test failures and 1 test error (`KeyError`).
   - **Mutant B (Dropping `agent-quota-launcher` alias):** Resulted in 4 test failures (`AssertionError: 'unattributed' != 'quota-launcher'`).
   - **Mutant C (Failing open instead of closed to `unattributed`):** Resulted in 4 test failures.

### Review Verdict:
**FULL ACCEPTANCE.** The minimal patch is surgically precise (137 lines across 3 files), completely non-breaking, verified bit-for-bit against target hashes, and backed by comprehensive regression tests. It is recommended for immediate staging and commit by `agent-dashboard-head`.

---

## 2. Pinned Baseline and Target Hash Verification

### 2.1 Pre-Patch Baseline SHA256 Checksums

Computed on `/home/alexey/git/agent-dashboard` at commit `efed70d` (working tree dirty state):

```bash
sha256sum src/dashboard/__init__.py tests/test_accounting.py tests/test_hourly.py
```

| File Path | Baseline SHA256 Checksum | Verification Status |
| :--- | :--- | :---: |
| `src/dashboard/__init__.py` | `5211df320cfac2cfc5c0e79a9eb00ce2135d99ccca55d57b5141ca2270cb6e4a` | **MATCH** |
| `tests/test_accounting.py` | `bde672ecd0a3560f2aa4d7333dbf3dfa44972fcb218aa676a8ab3b05f110cb75` | **MATCH** |
| `tests/test_hourly.py` | `17777a397648cef56c68d346afa44bdc68a27b8a93df573ddd6d6cb2d584e4c5` | **MATCH** |

### 2.2 Post-Patch Target SHA256 Checksums

Computed on the patched files in `.local/scratch/dashboard-minimal-patch-review/testbed`:

```bash
sha256sum src/dashboard/__init__.py tests/test_accounting.py tests/test_hourly.py
```

| File Path | Expected Target SHA256 Checksum | Measured SHA256 Checksum | Verification Status |
| :--- | :--- | :--- | :---: |
| `src/dashboard/__init__.py` | `15a53aa140fb74ebc3fa6e045b476f5ab4f25f3443c837792615455f89c436c7` | `15a53aa140fb74ebc3fa6e045b476f5ab4f25f3443c837792615455f89c436c7` | **EXACT BIT-FOR-BIT** |
| `tests/test_accounting.py` | `ab29fc2d9edda6ca5487b0750987169e944dc88d6237132978d5240e6e11e396` | `ab29fc2d9edda6ca5487b0750987169e944dc88d6237132978d5240e6e11e396` | **EXACT BIT-FOR-BIT** |
| `tests/test_hourly.py` | `355056ffc5d5cfb7667b29746a6cebe723358232d21372a04584faf15dd0d446` | `355056ffc5d5cfb7667b29746a6cebe723358232d21372a04584faf15dd0d446` | **EXACT BIT-FOR-BIT** |

---

## 3. Patch Application, Dry-Run & Drift Refusal Verification

### 3.1 Dry-Run Execution Receipt

Executed within scratch testbed:
```bash
patch -p1 --dry-run < /home/alexey/git/cloudflare-agent-git/research/antigravity/recovery/dashboard-alias-and-fourth-project-minimal.patch
```

```
checking file src/dashboard/__init__.py
checking file tests/test_accounting.py
checking file tests/test_hourly.py
```
Exit code: `0` (clean dry-run; no rejects, no offsets).

### 3.2 Live Application Receipt

```bash
patch -p1 < /home/alexey/git/cloudflare-agent-git/research/antigravity/recovery/dashboard-alias-and-fourth-project-minimal.patch
```

```
patching file src/dashboard/__init__.py
patching file tests/test_accounting.py
patching file tests/test_hourly.py
```
Exit code: `0`.

### 3.3 Drift Refusal Audit

In `.local/scratch/dashboard-minimal-patch-review/drift_testbed`, `CANONICAL_PROJECT_IDS` in `src/dashboard/__init__.py` was intentionally drifted by mutating `"quota-launcher"` to `"quota-launcher-drifted"`.

Applying the patch against this drifted tree produced:
```
checking file src/dashboard/__init__.py
Hunk #1 FAILED at 8.
1 out of 1 hunk FAILED
checking file tests/test_accounting.py
checking file tests/test_hourly.py
Patch refused on drift as expected! Exit code: 1
```
The patch fails closed immediately on any context mismatch, guaranteeing that it will only apply to the exact expected baseline.

---

## 4. Full 48-Test Suite Verification

### 4.1 Unittest Suite Execution Receipt

Executed within `.local/scratch/dashboard-minimal-patch-review/testbed`:
```bash
PYTHONPATH=src python3 -m unittest discover -s tests/ -v
```

```
test_24h_usage_filter (test_accounting.TestUsageAccounting.test_24h_usage_filter) ... ok
test_boolean_and_negative_counts_invalid (test_accounting.TestUsageAccounting.test_boolean_and_negative_counts_invalid) ... ok
test_canonical_project_id_aliases_and_fourth_product (test_accounting.TestUsageAccounting.test_canonical_project_id_aliases_and_fourth_product) ... ok
test_deduplication_by_response_id (test_accounting.TestUsageAccounting.test_deduplication_by_response_id) ... ok
test_known_zero_preserved (test_accounting.TestUsageAccounting.test_known_zero_preserved) ... ok
test_missing_response_id_does_not_dedup_on_timestamp (test_accounting.TestUsageAccounting.test_missing_response_id_does_not_dedup_on_timestamp) ... ok
test_noncanonical_project_unattributed (test_accounting.TestUsageAccounting.test_noncanonical_project_unattributed) ... ok
test_nullability_and_types (test_accounting.TestUsageAccounting.test_nullability_and_types) ... ok
test_opencode_adapter_reasoning_not_folded (test_accounting.TestUsageAccounting.test_opencode_adapter_reasoning_not_folded) ... ok
test_quota_not_converted_to_cost_or_tokens (test_accounting.TestUsageAccounting.test_quota_not_converted_to_cost_or_tokens) ... ok
test_reasoning_token_subset_isolation (test_accounting.TestUsageAccounting.test_reasoning_token_subset_isolation) ... ok
test_unknown_cache_and_reasoning_stay_null (test_accounting.TestUsageAccounting.test_unknown_cache_and_reasoning_stay_null) ... ok
test_usage_accounting_alias_and_coordination_routing (test_accounting.TestUsageAccounting.test_usage_accounting_alias_and_coordination_routing) ... ok
test_24h_completed_feature_filter (test_features.TestFeaturesTracking.test_24h_completed_feature_filter) ... ok
test_feature_extraction_and_deduplication (test_features.TestFeaturesTracking.test_feature_extraction_and_deduplication) ... ok
test_missing_commit_or_tests_rejected (test_features.TestFeaturesTracking.test_missing_commit_or_tests_rejected) ... ok
test_missing_tasks_file_unknown (test_features.TestFeaturesTracking.test_missing_tasks_file_unknown) ... ok
test_unaccepted_substring_not_counted (test_features.TestFeaturesTracking.test_unaccepted_substring_not_counted) ... ok
test_updated_at_is_not_accepted_at (test_features.TestFeaturesTracking.test_updated_at_is_not_accepted_at) ... ok
test_agent_across_three_adjacent_buckets (test_hourly.TestHourlyUtilization.test_agent_across_three_adjacent_buckets) ... ok
test_bucket_generation (test_hourly.TestHourlyUtilization.test_bucket_generation) ... ok
test_canonical_project_id_aliases_and_fourth_product (test_hourly.TestHourlyUtilization.test_canonical_project_id_aliases_and_fourth_product) ... ok
test_duplicate_identical_spans_do_not_change_hours (test_hourly.TestHourlyUtilization.test_duplicate_identical_spans_do_not_change_hours) ... ok
test_ended_before_started_invalid_spans (test_hourly.TestHourlyUtilization.test_ended_before_started_invalid_spans) ... ok
test_future_ended_at_clamped_to_as_of (test_hourly.TestHourlyUtilization.test_future_ended_at_clamped_to_as_of) ... ok
test_hourly_utilization_aliases_and_fourth_product (test_hourly.TestHourlyUtilization.test_hourly_utilization_aliases_and_fourth_product) ... ok
test_identity_deduplication (test_hourly.TestHourlyUtilization.test_identity_deduplication) ... ok
test_invalid_ended_at_unknown_ended_not_alive (test_hourly.TestHourlyUtilization.test_invalid_ended_at_unknown_ended_not_alive) ... ok
test_missing_agent_id_unattributed_hours (test_hourly.TestHourlyUtilization.test_missing_agent_id_unattributed_hours) ... ok
test_missing_spans_unknown_not_zeros (test_hourly.TestHourlyUtilization.test_missing_spans_unknown_not_zeros) ... ok
test_non_hour_as_of_exact_window (test_hourly.TestHourlyUtilization.test_non_hour_as_of_exact_window) ... ok
test_noncanonical_project_goes_to_unattributed (test_hourly.TestHourlyUtilization.test_noncanonical_project_goes_to_unattributed) ... ok
test_overlapping_spans_union_once (test_hourly.TestHourlyUtilization.test_overlapping_spans_union_once) ... ok
test_partial_hour_calculation (test_hourly.TestHourlyUtilization.test_partial_hour_calculation) ... ok
test_registry_shape_rejects_members (test_hourly.TestHourlyUtilization.test_registry_shape_rejects_members) ... ok
test_shared_agent_ids_non_additive (test_hourly.TestHourlyUtilization.test_shared_agent_ids_non_additive) ... ok
test_single_agent_clipping (test_hourly.TestHourlyUtilization.test_single_agent_clipping) ... ok
test_span_entirely_outside_window (test_hourly.TestHourlyUtilization.test_span_entirely_outside_window) ... ok
test_union_seconds_helper (test_hourly.TestHourlyUtilization.test_union_seconds_helper) ... ok
test_features_endpoint (test_server.TestDashboardServer.test_features_endpoint) ... ok
test_health_endpoint (test_server.TestDashboardServer.test_health_endpoint) ... ok
test_hourly_endpoint (test_server.TestDashboardServer.test_hourly_endpoint) ... ok
test_hourly_honors_as_of (test_server.TestDashboardServer.test_hourly_honors_as_of) ... ok
test_hourly_invalid_as_of (test_server.TestDashboardServer.test_hourly_invalid_as_of) ... ok
test_html_root_endpoint (test_server.TestDashboardServer.test_html_root_endpoint) ... ok
test_missing_source_coverage_gap (test_server.TestDashboardServer.test_missing_source_coverage_gap) ... ok
test_static_css_if_present (test_server.TestDashboardServer.test_static_css_if_present) ... ok
test_usage_endpoint (test_server.TestDashboardServer.test_usage_endpoint) ... ok

----------------------------------------------------------------------
Ran 48 tests in 0.633s

OK
```

### 4.2 Module Breakdown (48 Tests)

| Module | Test File | Pre-Patch Count | Added by Patch | Post-Patch Total | Status |
| :--- | :--- | :---: | :---: | :---: | :---: |
| `dashboard.accounting` | `tests/test_accounting.py` | 11 | +2 | 13 | **PASS** |
| `dashboard.hourly` | `tests/test_hourly.py` | 18 | +2 | 20 | **PASS** |
| `dashboard.features` | `tests/test_features.py` | 6 | 0 | 6 | **PASS** |
| `dashboard.server` | `tests/test_server.py` | 9 | 0 | 9 | **PASS** |
| **Total** | **4 Test Files** | **44** | **+4** | **48** | **48/48 PASS in 0.633s** |

---

## 5. Canonical Routing & Alias Verification

The following assertions were verified directly against the patched module in Python:

```python
from dashboard import canonical_project_id, CANONICAL_PROJECT_IDS, UNATTRIBUTED_PROJECT_ID, PROJECT_ALIASES

# 1. Quota Launcher Aliases
assert canonical_project_id("agent-quota-launcher") == "quota-launcher"
assert canonical_project_id("agent_quota_launcher") == "quota-launcher"
assert canonical_project_id("quota-launcher") == "quota-launcher"

# 2. Fourth Product Routing
assert "agent-coordination" in CANONICAL_PROJECT_IDS
assert canonical_project_id("agent-coordination") == "agent-coordination"
assert canonical_project_id("agent_coordination") == "agent-coordination"

# 3. Other Existing Products & Underline Variants
assert canonical_project_id("agent-branches") == "agent-branches"
assert canonical_project_id("agent_branches") == "agent-branches"
assert canonical_project_id("agent-dashboard") == "agent-dashboard"
assert canonical_project_id("agent_dashboard") == "agent-dashboard"

# 4. Fail-Closed Fallback for Unknown Identifiers
assert canonical_project_id("unknown-xyz") == "unattributed"
assert canonical_project_id(None) == "unattributed"
assert canonical_project_id("") == "unattributed"
```

All assertions passed cleanly. Telemetry from `agent-quota-launcher` is now correctly routed to the canonical `quota-launcher` aggregation bucket, while `agent-coordination` is promoted to a primary canonical product.

---

## 6. Negative Mutation Testing in Scratch

To confirm that the updated test suite actively guards against regressions in aliasing and fourth-product handling, three targeted mutations were applied to `src/dashboard/__init__.py`:

### Mutant A: Omission of Fourth Product (`agent-coordination`)
- **Mutation:** Removed `"agent-coordination"` from `CANONICAL_PROJECT_IDS`.
- **Test Result:** **FAILED (4 failures, 1 error)**.
  * `KeyError: 'agent-coordination'` in `test_missing_spans_unknown_not_zeros`.
  * `AssertionError: 'agent-coordination' not in res['projects']` in hourly and accounting routing tests.

### Mutant B: Omission of `agent-quota-launcher` from `PROJECT_ALIASES`
- **Mutation:** Removed `"agent-quota-launcher": "quota-launcher"` from `PROJECT_ALIASES`.
- **Test Result:** **FAILED (4 failures)**.
  * `AssertionError: 'unattributed' != 'quota-launcher'` in `test_canonical_project_id_aliases_and_fourth_product`.
  * `AssertionError: 'quota-launcher' not found in agg['projects']` in `test_usage_accounting_alias_and_coordination_routing`.
  * `AssertionError: None != 1` in `test_hourly_utilization_aliases_and_fourth_product`.

### Mutant C: Fail-Open Fallback on Unknown Projects
- **Mutation:** Changed `return UNATTRIBUTED_PROJECT_ID` to `return project_id or UNATTRIBUTED_PROJECT_ID`.
- **Test Result:** **FAILED (4 failures)**.
  * Caught by both legacy noncanonical tests and new alias tests asserting that unknown strings must map strictly to `"unattributed"`.

---

## 7. Publication Credential Guard Receipt

The review deliverable was verified with `publication_guard.py`:

```bash
python3 /home/alexey/git/cloudflare-agent-git/research/antigravity/tooling/publication_guard.py /home/alexey/git/cloudflare-agent-git/research/antigravity/reviews/REV-DASHBOARD-ALIAS-AND-FOURTH-PROJECT.md
```

- **Scan Result:** Clean (0 violations).
- **Exit Code:** `0`.
- **Raw Credentials / Minted Tokens:** Zero detected.

---

## 8. Final Audit Sign-Off & Recommendation

| Audit Item | Verification Status | Notes |
| :--- | :---: | :--- |
| **Primary Target Workspace** | **PASS** | Strictly untouched; zero writes to `/home/alexey/git/agent-dashboard` |
| **Patch Clean Application** | **PASS** | `patch -p1 --dry-run` and live apply cleanly with exit code 0 |
| **Pre-Patch Baseline Hashes** | **PASS** | Matches AD-R2 baseline hashes |
| **Post-Patch Target Hashes** | **PASS** | Matches all 3 target SHA256 hashes bit-for-bit |
| **Drift Protection** | **PASS** | Rejects drifted baseline with exit code 1 |
| **48-Test Suite Execution** | **PASS** | 48/48 PASS in 0.633s |
| **Canonical Routing Contract** | **PASS** | Correctly maps Quota Launcher aliases and 4th product |
| **Negative Mutation Tests** | **PASS** | Mutants A, B, and C all caught with multiple test failures |
| **Resource & Compiler Bounds** | **PASS** | 460 KB disk ($\le 512$ MB); 0 cargo/rustc invocations |
| **Publication Guard** | **PASS** | Exit code 0 |

**Verdict:** **FULL ACCEPTANCE.** The minimal patch `dashboard-alias-and-fourth-project-minimal.patch` is certified and approved for immediate staging and commit by `agent-dashboard-head`.
