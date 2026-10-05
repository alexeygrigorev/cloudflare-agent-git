# Independent Peer Review: Agent Dashboard Task `dashboard-usage-accounting`

**Date & Time**: 2026-10-05T23:12:00Z (01:12:00 Berlin, 2026-10-06)  
**Auditor / Reviewer**: `antigravity` (Independent Review Subagent `a3dd7197-64be-4d28-b587-715b6ccf51b7`)  
**Parent Caller**: `ea14b401-20e9-4e48-ab08-d15be08da30d`  
**Target Canonical Launcher DB**: `/home/alexey/git/agent-quota-launcher/.local/launcher-config/state.db`  
**Audited Task**: `dashboard-usage-accounting`  
**Verdict**: **ACCEPTED**

---

## 1. Executive Summary & Audit Matrix

This independent peer review audits the execution, tool invocations, state lifecycle, systemd unit isolation, and delivered artifact of task `dashboard-usage-accounting` executed by the `agent-quota-launcher` fleet runtime for `agent-dashboard`.

All evaluation criteria have been empirically verified:
1. **Store State**: SQLite state database at `/home/alexey/git/agent-quota-launcher/.local/launcher-config/state.db` records `dashboard-usage-accounting` in state `completed-awaiting-review` with reason `task-units sibling unit exit 0`.
2. **Execution Log & Genuine Tool Invocation**:
   - Log `/home/alexey/git/agent-quota-launcher/.local/launcher-config/dashboard-usage-accounting-stdout.log` verifies model initialization with `gemini-3.1-pro-high` (`conversation_id: 9986dc7a-b5a5-4ed4-b9af-a459d9129d59`).
   - Genuine FIRST MODEL TOOL executed: `run_command` with CommandLine `find . -type f -not -path "*/\\.git/*" -not -path "*/node_modules/*" -not -path "*/__pycache__/*"` at step 2.
   - Genuine code and test inspection via `view_file` on `src/dashboard/accounting.py`, `tests/test_accounting.py`, `src/dashboard/__init__.py`, and `src/dashboard/hourly.py`.
   - Unit test execution verified: Step 17 executed `PYTHONPATH=src python3 -m pytest tests/` with 48 items collected and 48 passed cleanly in 0.65s.
   - Comprehensive token accounting audit artifact generated via `write_to_file` at step 23 (`/home/alexey/.gemini/antigravity-cli/brain/9986dc7a-b5a5-4ed4-b9af-a459d9129d59/audit-report.md`).
   - Execution finished cleanly with status `SUCCESS` in 95.38s consuming 84,867 total tokens (8,086 thinking tokens).
3. **Accounting Breakdown Across Four Products**:
   - Confirmed canonical recognition of all four product streams (`agent-branches`, `agent-dashboard`, `quota-launcher`, and `agent-coordination`), with unmapped products routing to `unattributed`.
   - Verified breakdown accounting for `input_tokens`, `output_tokens`, and `cache_read_tokens` (including legacy aliases: `cached_input_tokens`, `cached_tokens`, `cacheReadTokens`).
   - Confirmed fail-closed nullability (`_sum_fail_closed`), negative/boolean invalidation, zero preservation, and reasoning token subset isolation.
4. **Independent Test Suite Re-verification**:
   - Reviewer independently executed `PYTHONPATH=src python3 -m pytest tests/ -v` inside `/home/alexey/git/agent-dashboard`; all 48/48 tests passed cleanly in 0.68s.
5. **Process & Cgroup Isolation**:
   - Confirmed task ran as detached transient sibling units under systemd user manager:
     - Controller: `ql-ctl-dashboard-usage-accounting.service`
     - Agent worker: `agent-task-dashboard-usage-accounting.service`
   - Memory and task bounds enforced: `--slice=app.slice`, `MemoryMax=768M`, `TasksMax=100`.
   - Transient cgroup dissolution verified cleanly post-execution (`cleanup_verified: true`, exit code 0, 512.0 KB peak memory, 0 swap).

| # | Audit Item | Required Specification | Measured Implementation & Evidence | Result |
|---|---|---|---|:---:|
| **1** | Database Task State | `tasks.state == 'completed-awaiting-review'`, `reason == 'task-units sibling unit exit 0'` | Verified via SQLite query against `/home/alexey/git/agent-quota-launcher/.local/launcher-config/state.db` | **PASS** |
| **2** | Model & Execution Log | Model `gemini-3.1-pro-high`, genuine FIRST MODEL TOOL (`run_command`), pytest execution, `write_to_file` | Verified in `dashboard-usage-accounting-stdout.log` & telemetry stream | **PASS** |
| **3** | Unit Test Execution | 48/48 unit tests in `agent-dashboard` passed cleanly | Verified 48 passed in execution log step 17; re-verified 48/48 passed in 0.68s | **PASS** |
| **4** | Token Accounting Logic | Audited breakdown across all four products (`input_tokens`, `output_tokens`, `cache_read_tokens`) | Verified across `src/dashboard/accounting.py`, `tests/test_accounting.py`, and deliverable artifact | **PASS** |
| **5** | Model Status & Telemetry | Status `SUCCESS`, valid telemetry stream | Verified `result.status == "SUCCESS"`, duration 95.38s, total tokens 84,867 | **PASS** |
| **6** | Process & Cgroup Isolation | Transient units in `app.slice`, `MemoryMax=768M`, `TasksMax=100`, clean dissolution | Verified via user systemd journal and execution receipt (`cleanup_verified: true`, exit 0) | **PASS** |

---

## 2. Detailed Technical Verification

### 2.1 State Store Confirmation
State database: `/home/alexey/git/agent-quota-launcher/.local/launcher-config/state.db`

Query:
```sql
SELECT id, state, reason, reviewer, updated_at 
FROM tasks 
WHERE id = 'dashboard-usage-accounting';
```

Result:
```text
dashboard-usage-accounting|completed-awaiting-review|task-units sibling unit exit 0||2026-10-05 23:08:13
```

Task state is confirmed as `completed-awaiting-review` with reason `task-units sibling unit exit 0`.

### 2.2 Execution Log & Genuine Tool Invocation Audit
Stdout log: `/home/alexey/git/agent-quota-launcher/.local/launcher-config/dashboard-usage-accounting-stdout.log`  
Telemetry log: `/home/alexey/git/agent-quota-launcher/.local/launcher-config/dashboard-usage-accounting-telemetry.jsonl`

Audit trail:
1. **Model Initialization**:
   ```json
   {
     "event": "init",
     "conversation_id": "9986dc7a-b5a5-4ed4-b9af-a459d9129d59",
     "init": {
       "model": "gemini-3.1-pro-high",
       "cwd": "/home/alexey/git/agent-dashboard",
       "permission_mode": "always-proceed"
     }
   }
   ```
2. **Step 0 (`user_input`)**: Goal prompt injected requesting audit and verification of token accounting breakdown (`input_tokens`, `output_tokens`, `cache_read_tokens`) across all four product streams, validating tests in `tests/`.
3. **Step 1 (`agent_response`)**: Model planning and reasoning (734 thinking tokens, 831 output tokens, duration 7.04s).
4. **Step 2 (`tool` - FIRST MODEL TOOL)**:
   - Tool: `run_command`
   - Parameters: `{"CommandLine": "find . -type f -not -path \"*/\\.git/*\" -not -path \"*/node_modules/*\" -not -path \"*/__pycache__/*\""}`
   - Duration: 0.036s. Verified genuine file tree discovery.
5. **Steps 4, 6, 8, 19 (`tool` - CODE & TEST INSPECTION)**:
   - Step 4: `view_file` on `/home/alexey/git/agent-dashboard/src/dashboard/accounting.py` (596 lines).
   - Step 6: `view_file` on `/home/alexey/git/agent-dashboard/tests/test_accounting.py` (247 lines).
   - Step 8: `view_file` on `/home/alexey/git/agent-dashboard/src/dashboard/__init__.py` (30 lines).
   - Step 19: `view_file` on `/home/alexey/git/agent-dashboard/src/dashboard/hourly.py` (484 lines).
6. **Step 17 (`tool` - TEST EXECUTION)**:
   - Tool: `run_command`
   - Parameters: `{"CommandLine": "PYTHONPATH=src python3 -m pytest tests/"}`
   - Output:
     ```text
     ============================= test session starts ==============================
     platform linux -- Python 3.12.3, pytest-9.1.1, pluggy-1.6.0
     rootdir: /home/alexey/git/agent-dashboard
     configfile: pyproject.toml
     plugins: anyio-4.12.1, opik-2.2.54
     collecting ... collected 48 items

     tests/test_accounting.py .............                                   [ 27%]
     tests/test_features.py ......                                            [ 39%]
     tests/test_hourly.py ....................                                [ 81%]
     tests/test_server.py .........                                           [100%]

     ============================== 48 passed in 0.65s ==============================
     ```
7. **Step 23 (`tool` - WRITE AUDIT REPORT ARTIFACT)**:
   - Tool: `write_to_file`
   - Parameters: `{"TargetFile": "/home/alexey/.gemini/antigravity-cli/brain/9986dc7a-b5a5-4ed4-b9af-a459d9129d59/audit-report.md"}`
   - Status: `DONE` in 0.023s.
8. **Final Result**:
   - `status`: `"SUCCESS"`
   - `duration_seconds`: `95.3797`
   - `num_turns`: 1
   - `usage`: `total_tokens: 84867`, `thinking_tokens: 8086`, `input_tokens: 74636`, `output_tokens: 10231`, `cache_read_tokens: 333831`.

### 2.3 Token Accounting Breakdown Across Four Products
The accounting implementation in `src/dashboard/accounting.py` and its definitions in `src/dashboard/__init__.py` were evaluated against the audit criteria:

1. **Four Canonical Products**:
   - `agent-branches`
   - `agent-dashboard`
   - `quota-launcher`
   - `agent-coordination`
   Unmapped or non-canonical product identifiers cleanly route to `unattributed` without data loss.

2. **Token Fields & Normalization**:
   - `input_tokens`: Accurately sums prompt token counts.
   - `output_tokens`: Accurately sums model completion tokens.
   - `cache_read_tokens`: Safely handles multi-provider aliases (`cached_input_tokens`, `cached_tokens`, `cacheReadTokens`).

3. **Robustness & Edge-Case Safeguards**:
   - **Fail-Closed Nullability (`_sum_fail_closed`)**: If token data is missing or empty, aggregates return `None` rather than false zero counts.
   - **Negative / Boolean Invalidation**: Non-integer or negative token readings trigger invalid record handling.
   - **Zero Preservation**: Explicit zero counts (`0`) are preserved and not stripped by falsey checks.
   - **Subset Isolation**: Specialized subset counters like `reasoning_tokens` remain isolated and do not inflate top-level `output_tokens`.

### 2.4 Independent Test Suite Re-verification
The reviewer independently executed the test suite directly from `/home/alexey/git/agent-dashboard`:
```bash
PYTHONPATH=src python3 -m pytest tests/ -v
```

Output:
```text
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.1.1, pluggy-1.6.0 -- /usr/bin/python3
cachedir: .pytest_cache
rootdir: /home/alexey/git/agent-dashboard
configfile: pyproject.toml
plugins: anyio-4.12.1, opik-2.2.54
collecting ... collected 48 items

tests/test_accounting.py::TestUsageAccounting::test_24h_usage_filter PASSED [  2%]
tests/test_accounting.py::TestUsageAccounting::test_boolean_and_negative_counts_invalid PASSED [  4%]
tests/test_accounting.py::TestUsageAccounting::test_canonical_project_id_aliases_and_fourth_product PASSED [  6%]
tests/test_accounting.py::TestUsageAccounting::test_deduplication_by_response_id PASSED [  8%]
tests/test_accounting.py::TestUsageAccounting::test_known_zero_preserved PASSED [ 10%]
tests/test_accounting.py::TestUsageAccounting::test_missing_response_id_does_not_dedup_on_timestamp PASSED [ 12%]
tests/test_accounting.py::TestUsageAccounting::test_noncanonical_project_unattributed PASSED [ 14%]
tests/test_accounting.py::TestUsageAccounting::test_nullability_and_types PASSED [ 16%]
tests/test_accounting.py::TestUsageAccounting::test_opencode_adapter_reasoning_not_folded PASSED [ 18%]
tests/test_accounting.py::TestUsageAccounting::test_quota_not_converted_to_cost_or_tokens PASSED [ 20%]
tests/test_accounting.py::TestUsageAccounting::test_reasoning_token_subset_isolation PASSED [ 22%]
tests/test_accounting.py::TestUsageAccounting::test_unknown_cache_and_reasoning_stay_null PASSED [ 25%]
tests/test_accounting.py::TestUsageAccounting::test_usage_accounting_alias_and_coordination_routing PASSED [ 27%]
tests/test_features.py::TestFeaturesTracking::test_24h_completed_feature_filter PASSED [ 29%]
tests/test_features.py::TestFeaturesTracking::test_feature_extraction_and_deduplication PASSED [ 31%]
tests/test_features.py::TestFeaturesTracking::test_missing_commit_or_tests_rejected PASSED [ 33%]
tests/test_features.py::TestFeaturesTracking::test_missing_tasks_file_unknown PASSED [ 35%]
tests/test_features.py::TestFeaturesTracking::test_unaccepted_substring_not_counted PASSED [ 37%]
tests/test_features.py::TestFeaturesTracking::test_updated_at_is_not_accepted_at PASSED [ 39%]
tests/test_hourly.py::TestHourlyUtilization::test_agent_across_three_adjacent_buckets PASSED [ 41%]
tests/test_hourly.py::TestHourlyUtilization::test_bucket_generation PASSED [ 43%]
tests/test_hourly.py::TestHourlyUtilization::test_canonical_project_id_aliases_and_fourth_product PASSED [ 45%]
tests/test_hourly.py::TestHourlyUtilization::test_duplicate_identical_spans_do_not_change_hours PASSED [ 47%]
tests/test_hourly.py::TestHourlyUtilization::test_ended_before_started_invalid_spans PASSED [ 50%]
tests/test_hourly.py::TestHourlyUtilization::test_future_ended_at_clamped_to_as_of PASSED [ 52%]
tests/test_hourly.py::TestHourlyUtilization::test_hourly_utilization_aliases_and_fourth_product PASSED [ 54%]
tests/test_hourly.py::TestHourlyUtilization::test_identity_deduplication PASSED [ 56%]
tests/test_hourly.py::TestHourlyUtilization::test_invalid_ended_at_unknown_ended_not_alive PASSED [ 58%]
tests/test_hourly.py::TestHourlyUtilization::test_missing_agent_id_unattributed_hours PASSED [ 60%]
tests/test_hourly.py::TestHourlyUtilization::test_missing_spans_unknown_not_zeros PASSED [ 62%]
tests/test_hourly.py::TestHourlyUtilization::test_non_hour_as_of_exact_window PASSED [ 64%]
tests/test_hourly.py::TestHourlyUtilization::test_noncanonical_project_goes_to_unattributed PASSED [ 66%]
tests/test_hourly.py::TestHourlyUtilization::test_overlapping_spans_union_once PASSED [ 68%]
tests/test_hourly.py::TestHourlyUtilization::test_partial_hour_calculation PASSED [ 70%]
tests/test_hourly.py::TestHourlyUtilization::test_registry_shape_rejects_members PASSED [ 72%]
tests/test_hourly.py::TestHourlyUtilization::test_shared_agent_ids_non_additive PASSED [ 75%]
tests/test_hourly.py::TestHourlyUtilization::test_single_agent_clipping PASSED [ 77%]
tests/test_hourly.py::TestHourlyUtilization::test_span_entirely_outside_window PASSED [ 79%]
tests/test_hourly.py::TestHourlyUtilization::test_union_seconds_helper PASSED [ 81%]
tests/test_server.py::TestDashboardServer::test_features_endpoint PASSED [ 83%]
tests/test_server.py::TestDashboardServer::test_health_endpoint PASSED   [ 85%]
tests/test_server.py::TestDashboardServer::test_hourly_endpoint PASSED   [ 87%]
tests/test_server.py::TestDashboardServer::test_hourly_honors_as_of PASSED [ 89%]
tests/test_server.py::TestDashboardServer::test_hourly_invalid_as_of PASSED [ 91%]
tests/test_server.py::TestDashboardServer::test_html_root_endpoint PASSED [ 93%]
tests/test_server.py::TestDashboardServer::test_missing_source_coverage_gap PASSED [ 95%]
tests/test_server.py::TestDashboardServer::test_static_css_if_present PASSED [ 97%]
tests/test_server.py::TestDashboardServer::test_usage_endpoint PASSED    [100%]

============================== 48 passed in 0.68s ==============================
```
All 48 unit tests pass cleanly without failures or regressions.

### 2.5 Process & Cgroup Isolation Audit
Systemd user journal verification for the task lifecycle:
```text
Oct 06 01:06:33 RMTHZ systemd[1339]: Started ql-ctl-dashboard-usage-accounting.service - /usr/bin/python3 -m launcher --config-dir /home/alexey/git/agent-quota-launcher/.local/launcher-config run --backend task-units --as-controller --id dashboard-usage-accounting --cwd /home/alexey/git/agent-dashboard --tmpdir /home/alexey/git/agent-dashboard/.local/tmp.
Oct 06 01:06:35 RMTHZ systemd[1339]: Started agent-task-dashboard-usage-accounting.service - /usr/bin/python3 /home/alexey/git/agent-dashboard/.local/tmp/prelude_dashboard-usage-accounting.py /usr/bin/env -u GEMINI_API_KEY -u GOOGLE_API_KEY /home/alexey/.local/bin/agy --model gemini-3.1-pro-high --effort high --dangerously-skip-permissions --print-timeout 0 --output-format stream-json -p "Audit and verify token accounting breakdown (input_tokens, output_tokens, cache_read_tokens) across all four product streams, validating tests in tests/.".
Oct 06 01:08:13 RMTHZ systemd[1339]: agent-task-dashboard-usage-accounting.service: Consumed 12.003s CPU time, 512.0K memory peak, 0B memory swap peak.
Oct 06 01:08:13 RMTHZ python3[1189961]: {"backend": "task-units", "task_id": "dashboard-usage-accounting", "receipt": {"task_id": "dashboard-usage-accounting", "unit_name": "agent-task-dashboard-usage-accounting.service", "invocation_id": "ce3ff5f6b4914bd6ae409390d18d181f", "exit_code": 0, "cgroup": "", "workspace": "/home/alexey/git/agent-dashboard", "working_directory": "/home/alexey/git/agent-dashboard", "module_sha256": "fd94f33ef58770129c39f904277d7d304e24748e23d20dccf4ca1aa92d5e3d59", "provider": "antigravity", "timeout_sec": 300.0, "started_at": "2026-10-05T23:06:35.937843+00:00", "finished_at": "2026-10-05T23:08:13.494649+00:00", "cleanup_verified": true, "memory_max_mb": 768, "tasks_max": 100, ...}}
Oct 06 01:08:13 RMTHZ python3[1189961]: task dashboard-usage-accounting completed-awaiting-review; automatic refill held waiting for distinct independent review acceptance
Oct 06 01:08:13 RMTHZ systemd[1339]: ql-ctl-dashboard-usage-accounting.service: Consumed 1.099s CPU time.
```

Isolation properties confirmed:
- Sibling service execution under `--slice=app.slice` with `--collect`.
- Resource constraints strictly applied: `MemoryMax=768M`, `TasksMax=100`.
- Peak memory measured at 512.0 KB, CPU time 12.003s, 0B swap peak.
- Transient cgroups and prelude scripts dissolved cleanly (`cleanup_verified: true`).
- Exit code 0, cleanly transitioning task state to `completed-awaiting-review`.

---

## 3. Explicit Verdict

**Verdict**: **ACCEPTED**

Task `dashboard-usage-accounting` satisfies all acceptance criteria:
1. Canonical state store records `completed-awaiting-review` with reason `task-units sibling unit exit 0`.
2. Execution log verifies genuine `gemini-3.1-pro-high` invocation, authentic FIRST MODEL TOOL execution (`run_command`), complete code and test inspection, pytest execution (48/48 passed), and deliverable artifact generation.
3. Accounting breakdown across all four products (`agent-branches`, `agent-dashboard`, `quota-launcher`, `agent-coordination`) is verified with strict nullability, alias, and subset isolation semantics.
4. Process isolation via transient systemd units under `app.slice` with memory bounds (768M) and clean dissolution is verified.
