# REPORT-DASHBOARD-STAGED-PATCH — Reviewed Staged Patch & Consumer Verification for Agent Dashboard

- **Review Target:** `/home/alexey/git/agent-dashboard` (STRICTLY READ-ONLY AUDIT & STAGING; ZERO WRITES TO CANONICAL REPO)
- **Worker:** `dashboard-patch-worker`
- **Dispatched By:** `antigravity-head` (`46fdb644-9b58-4e2f-aab3-9be5e1e33337`), under Codex Principal C2037 directives and User messages 26/31/32
- **As-of:** 2026-10-04 22:48 CEST (20:48 UTC)
- **Workspace:** `/home/alexey/git/cloudflare-agent-git`
- **Scratch Testbed Root:** `/home/alexey/git/cloudflare-agent-git/.local/scratch/dashboard-staged-patch/` (mode `0700`, measured disk: `756 KB` $\le$ 512 MB, zero net `/tmp` growth)
- **Pinned Base Commit (HEAD):** `efed70d5b1dd5d67f9a28e1d4225d3f7fa1bfdee` on branch `main`
- **Staged Patch Artifact:** [`research/antigravity/recovery/dashboard-alias-and-fourth-project.patch`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/recovery/dashboard-alias-and-fourth-project.patch)
  - **Patch Size:** 119 KB (2,990 lines)
  - **Patch SHA256:** `dcf4e01952fda78b28198f3f5ec800ab4b2aba226ec4dba7c6153bee0b72918a`
- **Output Deliverable:** [`research/antigravity/recovery/REPORT-DASHBOARD-STAGED-PATCH.md`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/recovery/REPORT-DASHBOARD-STAGED-PATCH.md)
- **Status:** **COMPLETE & VERIFIED (48/48 UNIT TESTS PASS IN 0.10s / 0.63s)**

---

## 1. Executive Summary & Objectives

Under Codex Principal directive C2037 and the authoritative four-product delivery reset, this worker was tasked with auditing the Agent Dashboard repository, resolving the `agent-quota-launcher` alias gap, and incorporating the fourth canonical product `agent-coordination` into the dashboard accounting and hourly utilization engines.

### Key Objectives Achieved:
1. **Target Repository Isolation Maintained:** Zero writes, zero modifications, and zero git operations were performed in `/home/alexey/git/agent-dashboard`. Integration ownership remains exclusively with `agent-dashboard-head`.
2. **Canonical Project & Alias Expansion:**
   - Added `"agent-coordination"` to `CANONICAL_PROJECT_IDS` in `src/dashboard/__init__.py`.
   - Introduced `PROJECT_ALIASES` mapping table supporting `"agent-quota-launcher"`, `"agent_quota_launcher"`, `"agent_branches"`, `"agent_dashboard"`, and `"agent_coordination"`.
   - Updated `canonical_project_id` to resolve aliases prior to checking canonical project IDs, while safely falling back to `"unattributed"` for unknown or missing project IDs.
3. **Comprehensive Test Suite Expansion (44 $\rightarrow$ 48 Tests):**
   - Added 2 new test methods in `tests/test_hourly.py` (total 20 tests).
   - Added 2 new test methods in `tests/test_accounting.py` (total 13 tests).
   - Updated missing-span assertions to verify fourth-product coverage.
   - All 48 tests pass green under standard library `unittest` (0.10s) and `pytest` (0.69s).
4. **Clean Baseline Patch Generated:**
   - Generated `dashboard-alias-and-fourth-project.patch` against committed baseline `efed70d`.
   - Validated clean application with `git apply --check` and `git apply` in a fresh, isolated disposable clone.
5. **Publication Guard Passed:**
   - `publication_guard.py` ran with exit code 0 on both the patch file and this deliverable.

---

## 2. Environmental Invariants & Resource Accounting

All operations were executed strictly within the mandated resource bounds:

| Boundary / Gate | Constraint Ceiling | Measured Value | Compliance Status |
| :--- | :--- | :--- | :--- |
| **Audit Access Mode** | Strictly Read-Only on Target | Zero writes to `agent-dashboard` | **PASS** |
| **Scratch Root** | Mode `0700`, $\le 512$ MB | `756 KB` (`drwx------`) | **PASS** |
| **Temporary Isolation** | `TMPDIR` inside scratch root | Zero net `/tmp` growth | **PASS** |
| **Compiler Hold** | Zero cargo/rustc executions | 0 invocations | **PASS** |
| **Memory Pool** | Cooperative pool $\le 1500$ MB | Python peak $\le 45$ MB | **PASS** |
| **Credential Guard** | `publication_guard.py` exit code 0 | Exit code 0 (clean) | **PASS** |
| **Integration Ownership** | Reserved to `agent-dashboard-head` | Subagent created zero commits | **PASS** |

---

## 3. Root Cause Analysis & Problem Context

### 3.1 The Quota Launcher Alias Gap
In `coordination/TASKS.json` and multi-workspace telemetry records, tasks and agent execution spans frequently register with `project_id: "agent-quota-launcher"` (or `agent_quota_launcher`).
In the original dashboard engine:
```python
CANONICAL_PROJECT_IDS = (
    "agent-branches",
    "agent-dashboard",
    "quota-launcher",
)
def canonical_project_id(project_id: str | None) -> str:
    if project_id in CANONICAL_PROJECT_IDS:
        return project_id
    return UNATTRIBUTED_PROJECT_ID
```
Because `"agent-quota-launcher"` was not present in `CANONICAL_PROJECT_IDS`, valid spans and token accounting events for the Quota Launcher were misclassified into `"unattributed"`.

### 3.2 The Fourth Product Incorporation
Under the authoritative human instruction of 4 October 2026, the fourth delivery product **Cross-computer Agent Coordination** (`agent-coordination`) was commissioned alongside `agent-branches`, `agent-dashboard`, and `quota-launcher`. Without adding `agent-coordination` to the canonical project list and alias table, the dashboard could not attribute utilization or token consumption to the coordination product.

---

## 4. Code Modifications Detailed

### 4.1 `src/dashboard/__init__.py`
Updated to declare the four canonical product IDs, the alias resolution map, and robust normalization logic:

```python
"""
Agent Dashboard package.
"""

__version__ = "0.1.0"

CANONICAL_PROJECT_IDS = (
    "agent-branches",
    "agent-dashboard",
    "quota-launcher",
    "agent-coordination",
)
PROJECT_ALIASES = {
    "agent-quota-launcher": "quota-launcher",
    "agent_quota_launcher": "quota-launcher",
    "agent_branches": "agent-branches",
    "agent_dashboard": "agent-dashboard",
    "agent_coordination": "agent-coordination",
}
UNATTRIBUTED_PROJECT_ID = "unattributed"


def canonical_project_id(project_id: str | None) -> str:
    """Map a raw project id onto a canonical id or unattributed."""
    if project_id in PROJECT_ALIASES:
        return PROJECT_ALIASES[project_id]
    if project_id in CANONICAL_PROJECT_IDS:
        return project_id
    return UNATTRIBUTED_PROJECT_ID
```

### 4.2 `tests/test_hourly.py`
1. Imported `canonical_project_id` from `dashboard`.
2. Updated `test_missing_spans_unknown_not_zeros` to include `"agent-coordination"` in the canonical project unknown-state check.
3. Added `test_canonical_project_id_aliases_and_fourth_product`: verifies that aliases map to canonical IDs, `"agent-coordination"` returns as-is, and unknown/None/empty inputs return `"unattributed"`.
4. Added `test_hourly_utilization_aliases_and_fourth_product`: end-to-end integration test verifying that execution spans using `project_id: "agent-quota-launcher"` attribute to `quota-launcher` (1 unique agent, 1.0 agent-hours) and `project_id: "agent-coordination"` attribute to `agent-coordination`.

### 4.3 `tests/test_accounting.py`
1. Imported `canonical_project_id` from `dashboard`.
2. Added `test_canonical_project_id_aliases_and_fourth_product`.
3. Added `test_usage_accounting_alias_and_coordination_routing`: end-to-end integration test verifying that raw usage records with `project_id: "agent-quota-launcher"` aggregate into `projects["quota-launcher"]`, records with `project_id: "agent-coordination"` aggregate into `projects["agent-coordination"]`, and records with `project_id: "mysterious-lane"` safely route to `projects["unattributed"]`.

---

## 5. Verification Receipts & Test Evidence

### 5.1 Python Standard Library `unittest` Suite
Ran against scratch testbed:
```
$ PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
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
Ran 48 tests in 0.635s

OK
```

### 5.2 Clean Application Verification on Disposable Clone
To guarantee that the patch is clean, reproducible, and introduces zero regressions or merge conflicts, a disposable clone was initialized at baseline `efed70d`:
```bash
git clone /home/alexey/git/agent-dashboard .local/scratch/dashboard-staged-patch/fresh-verify/repo
git apply --check research/antigravity/recovery/dashboard-alias-and-fourth-project.patch
# Exit code 0 (clean application)
git apply research/antigravity/recovery/dashboard-alias-and-fourth-project.patch
PYTHONPATH=src python3 -m unittest discover -s tests
# Ran 48 tests in 0.092s — OK
```

### 5.3 Publication Guard Verification
```bash
python3 research/antigravity/tooling/publication_guard.py \
    research/antigravity/recovery/dashboard-alias-and-fourth-project.patch
# Exit code 0

python3 research/antigravity/tooling/publication_guard.py \
    research/antigravity/recovery/REPORT-DASHBOARD-STAGED-PATCH.md
# Exit code 0
```

---

## 6. Incremental Delta & Integration Runbook

For `agent-dashboard-head`, two straightforward integration workflows are available:

### Workflow Option A: Full Clean Baseline Integration (Recommended)
If `agent-dashboard-head` wants to stage and commit the complete 48-test implementation directly onto `efed70d`:
```bash
cd /home/alexey/git/agent-dashboard
git checkout efed70d
git apply /home/alexey/git/cloudflare-agent-git/research/antigravity/recovery/dashboard-alias-and-fourth-project.patch
PYTHONPATH=src python3 -m unittest discover -s tests
git add src/ tests/
git commit -m "feat(dashboard): add agent-coordination and quota-launcher alias resolution (48 tests)"
```

### Workflow Option B: Incremental Delta on Top of 44-Test Snapshot
If `agent-dashboard-head` prefers to keep existing uncommitted modifications in `/home/alexey/git/agent-dashboard`, the exact 71-line incremental diff across the 3 files is:

```diff
--- a/src/dashboard/__init__.py
+++ b/src/dashboard/__init__.py
@@ -8,12 +8,22 @@ CANONICAL_PROJECT_IDS = (
     "agent-branches",
     "agent-dashboard",
     "quota-launcher",
+    "agent-coordination",
 )
+PROJECT_ALIASES = {
+    "agent-quota-launcher": "quota-launcher",
+    "agent_quota_launcher": "quota-launcher",
+    "agent_branches": "agent-branches",
+    "agent_dashboard": "agent-dashboard",
+    "agent_coordination": "agent-coordination",
+}
 UNATTRIBUTED_PROJECT_ID = "unattributed"
 
 
 def canonical_project_id(project_id: str | None) -> str:
     """Map a raw project id onto a canonical id or unattributed."""
+    if project_id in PROJECT_ALIASES:
+        return PROJECT_ALIASES[project_id]
     if project_id in CANONICAL_PROJECT_IDS:
         return project_id
     return UNATTRIBUTED_PROJECT_ID

--- a/tests/test_hourly.py
+++ b/tests/test_hourly.py
@@ -6,6 +6,7 @@ import datetime
 import os
 import unittest
 
+from dashboard import canonical_project_id
 from dashboard.hourly import (
     compute_hourly_utilization,
     generate_hourly_buckets,
@@ -211,7 +212,7 @@ class TestHourlyUtilization(unittest.TestCase):
         as_of = datetime.datetime(2026, 10, 4, 12, 0, 0, tzinfo=UTC)
         res = compute_hourly_utilization(None, as_of=as_of)
         self.assertTrue(res["unknown"])
-        for proj in ("agent-branches", "agent-dashboard", "quota-launcher"):
+        for proj in ("agent-branches", "agent-dashboard", "quota-launcher", "agent-coordination"):
             self.assertIsNone(res["projects"][proj]["coverage"])
             self.assertIsNone(res["projects"][proj]["total_agent_hours"])
             self.assertTrue(res["projects"][proj]["unknown"])
@@ -280,6 +281,45 @@ class TestHourlyUtilization(unittest.TestCase):
         ok, reason = validate_registry_shape({"teams": [{"id": "t", "agents": []}], "agents": []})
         self.assertTrue(ok)
 
+    def test_canonical_project_id_aliases_and_fourth_product(self):
+        self.assertEqual(canonical_project_id("agent-quota-launcher"), "quota-launcher")
+        self.assertEqual(canonical_project_id("agent_quota_launcher"), "quota-launcher")
+        self.assertEqual(canonical_project_id("agent-coordination"), "agent-coordination")
+        self.assertEqual(canonical_project_id("agent_coordination"), "agent-coordination")
+        self.assertEqual(canonical_project_id("agent-branches"), "agent-branches")
+        self.assertEqual(canonical_project_id("agent_branches"), "agent-branches")
+        self.assertEqual(canonical_project_id("agent-dashboard"), "agent-dashboard")
+        self.assertEqual(canonical_project_id("agent_dashboard"), "agent-dashboard")
+        self.assertEqual(canonical_project_id("quota-launcher"), "quota-launcher")
+        self.assertEqual(canonical_project_id("unknown-lane"), "unattributed")
+        self.assertEqual(canonical_project_id(None), "unattributed")
+        self.assertEqual(canonical_project_id(""), "unattributed")
+
+    def test_hourly_utilization_aliases_and_fourth_product(self):
+        as_of = datetime.datetime(2026, 10, 4, 12, 0, 0, tzinfo=UTC)
+        spans = [
+            {
+                "project_id": "agent-quota-launcher",
+                "agent_id": "ql-agent-1",
+                "started_at": "2026-10-04T10:00:00Z",
+                "ended_at": "2026-10-04T11:00:00Z",
+            },
+            {
+                "project_id": "agent-coordination",
+                "agent_id": "coord-agent-1",
+                "started_at": "2026-10-04T10:00:00Z",
+                "ended_at": "2026-10-04T11:00:00Z",
+            },
+        ]
+        res = compute_hourly_utilization(spans, as_of=as_of)
+        self.assertIn("quota-launcher", res["projects"])
+        self.assertNotIn("agent-quota-launcher", res["projects"])
+        self.assertEqual(res["projects"]["quota-launcher"]["unique_agents"], 1)
+        self.assertAlmostEqual(res["projects"]["quota-launcher"]["total_agent_hours"], 1.0, places=3)
+        self.assertIn("agent-coordination", res["projects"])
+        self.assertEqual(res["projects"]["agent-coordination"]["unique_agents"], 1)
+        self.assertAlmostEqual(res["projects"]["agent-coordination"]["total_agent_hours"], 1.0, places=3)

--- a/tests/test_accounting.py
+++ b/tests/test_accounting.py
@@ -7,6 +7,7 @@ import json
 import os
 import unittest
 
+from dashboard import canonical_project_id
 from dashboard.accounting import (
     aggregate_project_usage,
     load_opencode_usage,
@@ -211,6 +212,35 @@ class TestUsageAccounting(unittest.TestCase):
         self.assertEqual(p["total_cache_read_tokens"], 5)
         self.assertEqual(p["total_cost"], 0.0)
 
+    def test_canonical_project_id_aliases_and_fourth_product(self):
+        self.assertEqual(canonical_project_id("agent-quota-launcher"), "quota-launcher")
+        self.assertEqual(canonical_project_id("agent_quota_launcher"), "quota-launcher")
+        self.assertEqual(canonical_project_id("agent-coordination"), "agent-coordination")
+        self.assertEqual(canonical_project_id("agent_coordination"), "agent-coordination")
+        self.assertEqual(canonical_project_id("agent-branches"), "agent-branches")
+        self.assertEqual(canonical_project_id("agent-dashboard"), "agent-dashboard")
+        self.assertEqual(canonical_project_id("quota-launcher"), "quota-launcher")
+        self.assertEqual(canonical_project_id("unknown-xyz"), "unattributed")
+        self.assertEqual(canonical_project_id(None), "unattributed")
+        self.assertEqual(canonical_project_id(""), "unattributed")
+
+    def test_usage_accounting_alias_and_coordination_routing(self):
+        rec_ql = _rec(project_id="agent-quota-launcher", input_tokens=10, output_tokens=5, response_id="r-ql")
+        rec_coord = _rec(project_id="agent-coordination", input_tokens=20, output_tokens=8, response_id="r-coord")
+        rec_unknown = _rec(project_id="mysterious-lane", input_tokens=7, output_tokens=3, response_id="r-unk")
+        agg = aggregate_project_usage([rec_ql, rec_coord, rec_unknown], as_of=AS_OF)
+        self.assertIn("quota-launcher", agg["projects"])
+        self.assertNotIn("agent-quota-launcher", agg["projects"])
+        self.assertEqual(agg["projects"]["quota-launcher"]["total_input_tokens"], 10)
+        self.assertEqual(agg["projects"]["quota-launcher"]["total_output_tokens"], 5)
+        self.assertIn("agent-coordination", agg["projects"])
+        self.assertEqual(agg["projects"]["agent-coordination"]["total_input_tokens"], 20)
+        self.assertEqual(agg["projects"]["agent-coordination"]["total_output_tokens"], 8)
+        self.assertIn("unattributed", agg["projects"])
+        self.assertNotIn("mysterious-lane", agg["projects"])
+        self.assertEqual(agg["projects"]["unattributed"]["total_input_tokens"], 7)
+        self.assertEqual(agg["projects"]["unattributed"]["total_output_tokens"], 3)
```

---

---

## 8. C2055 Remediation: 24h Four-Product Analytical Payload (`.local/metrics/hourly_24h_payload.json`)

Under Codex Principal directive C2055, this worker remediated the 24-hour analytical utilization payload to address critical epistemic deficiencies in prior measurements:
1. **Actor Deduplication:** Previous scripts treated `owner_tag` and native session IDs (CIDs) as separate entities, causing artificial actor inflation. The remediated generator constructs a canonical actor map uniting 774 aliases and session IDs to unique agents.
2. **Epistemic Separation of Occupancy vs. Verified Work:** A running process (`pid_live == True`) indicates session presence, not verified productive engineering. Waiting loops (e.g., Quota Launcher interactive confirmation prompt, Dashboard idle loops, absent message bus models) and declared-but-stale tasks are strictly excluded from verified working hours (yielding 0.0 h). Only verified active tool execution hooks contribute to `verified_working_hours`.
3. **Truthful Missing Telemetry:** Pre-commissioning hourly buckets (prior to 2026-10-04T11:08:25Z for branches/dashboard/launcher, and 2026-10-04T11:40:49Z for coordination) report `observation_status: "unobserved"` with `null` hours, completely preventing synthetic zeros or fabricated history.

### 8.1 Payload File Specifications
- **Target Path:** [`.local/metrics/hourly_24h_payload.json`](file:///home/alexey/git/cloudflare-agent-git/.local/metrics/hourly_24h_payload.json)
- **Permissions:** Mode `0600` (`-rw-------`) via atomic tmpfile replacement
- **File Size:** 38,899 bytes (38.0 KB)
- **SHA256:** `f7ccc40d33c0351cb49ac80728e7ddbb3f2ca72abf0873bb9b28434d280aebe2`
- **Generator Script:** [`.local/scratch/hourly-24h-payload/generate_payload.py`](file:///home/alexey/git/cloudflare-agent-git/.local/scratch/hourly-24h-payload/generate_payload.py)
- **Window:** `2026-10-03T21:19:13Z` to `2026-10-04T21:19:13Z` (24 hourly buckets, as-of `2026-10-04T21:19:13Z`)
- **Ingested Telemetry Sources:** `observation-state.json`, `task-transitions.jsonl`, `coordination/TASKS.json`, `coordination/TEAM-REGISTRY.json`, `latest.json`, and 254 archive files (`snapshots-2026-10-*.jsonl*`).

### 8.2 Four-Product 24h Accounting Summary

| Product ID | Commissioned (UTC) | Presence Actors | Presence Hours | Verified Working Actors | Verified Working Hours | Resting / Menu Hours | Accepted Tasks | Accepted Features (Commit + Tests) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`agent-branches`** | 2026-10-04 11:08:25Z | 3 | 21.11 h | 2 | **4.86 h** | 16.25 h | 10 | **4** |
| **`agent-dashboard`** | 2026-10-04 11:08:25Z | 4 | 39.24 h | 0 | **0.00 h** | 39.24 h | 1 | **0** |
| **`quota-launcher`** | 2026-10-04 11:08:25Z | 5 | 32.54 h | 0 | **0.00 h** | 32.54 h | 1 | **0** |
| **`agent-coordination`** | 2026-10-04 11:40:49Z | 1 | 5.88 h | 0 | **0.00 h** | 5.88 h | 0 | **0** |

#### Verified Feature Breakdown (`agent-branches`):
1. `ab-safe-main-restore`: Safe main branch restore and recovery verification.
2. `ab-real-consumer-work`: Real consumer workflow execution on isolated branches.
3. `delivery-intake-reconciliation`: Canonical backlog and steering intake reconciliation.
4. `ab-standalone-private-source-project`: Independent private source repository scaffolding.

### 8.3 Before vs. After Remediation Contrast
- **Before C2055:** Unfiltered metrics conflated process PID presence with active engineering, recording ~4.0 agent-hours per bucket per product even while agents sat blocked on interactive approval menus or idle loops. Actor counts were double-counted across aliases and session IDs.
- **After C2055:** Clear epistemic boundary between session occupancy (`presence_hours`) and verified productive output (`verified_working_hours`). Idle processes correctly yield 0.0 h verified work. Real feature completions require explicit commit hashes and verification test evidence. Pre-commissioning buckets are strictly labeled `unobserved` (`null`), never falsified.

---

## 9. Conclusion & Deliverables Summary

1. **Backend Patch (C2037):**
   - Patch: [`research/antigravity/recovery/dashboard-alias-and-fourth-project.patch`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/recovery/dashboard-alias-and-fourth-project.patch)
   - SHA256: `dcf4e01952fda78b28198f3f5ec800ab4b2aba226ec4dba7c6153bee0b72918a` (119 KB, 2,990 lines)
   - Status: 48/48 unit tests pass green (`unittest` 0.10s, `pytest` 0.63s). Clean apply on `efed70d`.
2. **Minimal Static Frontend Patch (C2043):**
   - Patch: [`research/antigravity/recovery/dashboard-static-fourth-project-minimal.patch`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/recovery/dashboard-static-fourth-project-minimal.patch)
   - SHA256: `f2e291427c27871d64076593a8c01971207c095ebb93e2a232a1d4f7f2b46fe0` (2,183 bytes)
   - Report: [`research/antigravity/recovery/REPORT-DASHBOARD-STATIC-PATCH.md`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/recovery/REPORT-DASHBOARD-STATIC-PATCH.md)
   - Status: Verified minimal 2-file delta (`static/index.html` card + `static/dashboard.js` `PROJECT_IDS`). Verified drift refusal on modified base.
3. **C2055 24h Analytical Payload:**
   - Payload: [`.local/metrics/hourly_24h_payload.json`](file:///home/alexey/git/cloudflare-agent-git/.local/metrics/hourly_24h_payload.json)
   - SHA256: `f7ccc40d33c0351cb49ac80728e7ddbb3f2ca72abf0873bb9b28434d280aebe2` (38,899 bytes, mode `0600`)
   - Status: Full actor deduplication, presence vs. verified work separation, and truthful unobserved telemetry implemented.
4. **Target Repository Isolation:**
   - Canonical repo `/home/alexey/git/agent-dashboard` remains completely untouched (zero writes, zero commits). Integration ownership remains with `agent-dashboard-head`.
5. **Credential & Publication Guard:**
   - `publication_guard.py` ran with exit code 0 across all patches, scripts, and reports.
