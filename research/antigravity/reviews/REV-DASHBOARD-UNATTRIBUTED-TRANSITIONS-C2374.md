# REV-DASHBOARD-UNATTRIBUTED-TRANSITIONS-C2374 — Independent Technical Audit of Updated Dashboard Patch (Directives C2374, C2379, C2381, C2385)

- **Auditor / Reviewer:** Independent dogfood model reviewer (`dogfood-model-reviewer`, FileBus identity `6a925c23-5f88-479b-88b4-3f880e98b1e9`)
- **FileBus task message:** `f5c30541-db73-4972-962d-5c4112871d75` (acked `2026-10-05T07:11:27Z`; sender `85fa0349-5ae8-414b-b736-a2f6dd6de9c7`; run `20261005T071104Z-b1a35f`; task `t-filebus-review-20261005T071104Z-b1a35f`)
- **Governing Directives:** Codex Principal Directives C2374, C2379, C2381, C2385; Operating Model (`coordination/OPERATING-MODEL.md`); four-product delivery contract
- **Audit Target Patch:** [`research/antigravity/recovery/dashboard-unattributed-and-as-of-c2372.patch`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/recovery/dashboard-unattributed-and-as-of-c2372.patch)
  - Size: 24,795 bytes / 617 lines
  - SHA256 (measured): `7a9322a9331aede2ab428f68176b96fdc08d266e10d765b416f842040eefb3d7` (exact match to dispatch digest)
- **Pinned Base Commit:** `249d086a007ee3d5d0381334a27d56771b959d11` (`main`) in `/home/alexey/git/agent-dashboard`
- **Scratch Testbed:** `/home/alexey/git/cloudflare-agent-git/.local/scratch/filebus-dogfood-model-review/testbed` (git clone `--local` of canonical at the pinned commit; measured `980K` ≪ 512 MiB ceiling)
- **Canonical Repository Access Mode:** **STRICTLY READ-ONLY** (zero writes, zero `git apply`, zero stage/commit in `/home/alexey/git/agent-dashboard`)
- **Compiler Invariant:** This reviewer launched **zero** `cargo` / `rustc` processes. Host snapshots before (`2026-10-05T07:12:01Z`) and after (`2026-10-05T07:14:16Z`) showed `pgrep -x cargo` and `pgrep -x rustc` empty.
- **Python / Node:** Python 3.12.3; Node v24.13.1
- **Audit Date:** 2026-10-05T07:14:16Z (Europe/Berlin 09:14 CEST)
- **Verdict:** **ACCEPT**

---

## 1. Executive Summary & Independent Verdict

**Final verdict: ACCEPT.**

This independent FileBus review re-audits the **updated** C2372/C2374 dashboard patch (`7a9322a9…`) atop `249d086`. The prior independent C2372 review (`REV-DASHBOARD-UNATTRIBUTED-AS-OF-C2372.md`) covered an earlier digest (`2a063916…`, 54 tests). Codex C2374 then identified two remaining frontend transition defects:

1. `renderUsage` returned early on empty `projects` **before** resetting `#events-unattributed` and `#tokens-unattributed`, leaving stale usage numbers on the unattributed card.
2. `renderHourly(null)` / HTTP 400 error paths did not defensively clear the new unattributed card (hourly cells, telemetry status, and chart).

This review independently cloned the canonical tree into scratch, applied the updated patch with **zero rejects and zero fuzz**, ran the full Python suite (**55/55 PASS in 0.125s**), and ran the Node DOM transition harness (**3/3 suites PASS**). Source inspection confirms both transition fixes, synchronized `as_of` dispatch to `/api/hourly`, `/api/usage`, and `/api/features`, and fail-closed HTTP 400 on invalid timestamps. Canonical `/home/alexey/git/agent-dashboard` remained clean at `249d086`.

This ACCEPT is an independent technical acceptance of the **scratch patch**. It is not canonical adoption, not a merge, and not a shortlist/product sign-off.

---

## 2. Scratch Replay & Patch Integrity

### 2.1 Artifact checksum

| Artifact | Path | Expected SHA256 | Measured SHA256 | Bytes | Status |
| :--- | :--- | :--- | :--- | ---: | :--- |
| Patch | `research/antigravity/recovery/dashboard-unattributed-and-as-of-c2372.patch` | `7a9322a9331aede2ab428f68176b96fdc08d266e10d765b416f842040eefb3d7` | `7a9322a9331aede2ab428f68176b96fdc08d266e10d765b416f842040eefb3d7` | 24,795 | **EXACT MATCH** |

This digest differs from the earlier C2372 review target `2a063916…` (12,312 bytes). The delta is the C2374 transition tests and the two JS reset/clearing fixes.

### 2.2 Clean application replay atop `249d086`

Commands:

```bash
git clone --local /home/alexey/git/agent-dashboard \
  /home/alexey/git/cloudflare-agent-git/.local/scratch/filebus-dogfood-model-review/testbed
git -C .../testbed checkout --detach 249d086a007ee3d5d0381334a27d56771b959d11
git apply --verbose --check .../dashboard-unattributed-and-as-of-c2372.patch
git apply --verbose .../dashboard-unattributed-and-as-of-c2372.patch
```

Observed `git apply --verbose` output:

```text
Checking patch src/dashboard/server.py...
Checking patch static/dashboard.css...
Checking patch static/dashboard.js...
Checking patch static/index.html...
Checking patch tests/test_dashboard_js_transitions.js...
Checking patch tests/test_server.py...
Applied patch src/dashboard/server.py cleanly.
Applied patch static/dashboard.css cleanly.
Applied patch static/dashboard.js cleanly.
Applied patch static/index.html cleanly.
Applied patch tests/test_dashboard_js_transitions.js cleanly.
Applied patch tests/test_server.py cleanly.
warning: 1 line adds whitespace errors.
```

Status: **clean apply, 0 rejects, 0 fuzz, exit 0**. The whitespace warning is a trailing blank line at `tests/test_server.py:244` (`git diff --check`: `new blank line at EOF`). Non-blocking.

Post-apply testbed porcelain (expected, uncommitted patch only):

```text
 M src/dashboard/server.py
 M static/dashboard.css
 M static/dashboard.js
 M static/index.html
 M tests/test_server.py
?? tests/test_dashboard_js_transitions.js
```

Diffstat of tracked files: **5 files, +172 / −4**. Plus new `tests/test_dashboard_js_transitions.js` (324 lines). Combined patch manifest: **6 files, +496 / −4**.

### 2.3 Canonical isolation

Measured after clone, apply, and both test runs:

| Check | Result |
| :--- | :--- |
| Canonical HEAD | `249d086a007ee3d5d0381334a27d56771b959d11` |
| `git status --porcelain` in `/home/alexey/git/agent-dashboard` | empty (working tree clean) |
| Canonical `tests/test_dashboard_js_transitions.js` | **absent** (exists only in scratch) |
| Canonical `tests/test_server.py` | original 7,045-byte file; not patched |
| Reviewer writes into canonical | **none** |

Requirement 4 is satisfied.

---

## 3. Test Execution Receipts

### 3.1 Python unit tests — 55/55 PASS

```bash
cd .../filebus-dogfood-model-review/testbed
PYTHONPATH=src python3 -m unittest discover -s tests/ -v
```

```text
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
test_features_honors_as_of (test_server.TestDashboardServer.test_features_honors_as_of) ... ok
test_features_invalid_as_of (test_server.TestDashboardServer.test_features_invalid_as_of) ... ok
test_health_endpoint (test_server.TestDashboardServer.test_health_endpoint) ... ok
test_hourly_endpoint (test_server.TestDashboardServer.test_hourly_endpoint) ... ok
test_hourly_honors_as_of (test_server.TestDashboardServer.test_hourly_honors_as_of) ... ok
test_hourly_invalid_as_of (test_server.TestDashboardServer.test_hourly_invalid_as_of) ... ok
test_html_root_contains_unattributed_card (test_server.TestDashboardServer.test_html_root_contains_unattributed_card) ... ok
test_html_root_endpoint (test_server.TestDashboardServer.test_html_root_endpoint) ... ok
test_js_dom_transitions (test_server.TestDashboardServer.test_js_dom_transitions) ... ok
test_missing_source_coverage_gap (test_server.TestDashboardServer.test_missing_source_coverage_gap) ... ok
test_static_css_if_present (test_server.TestDashboardServer.test_static_css_if_present) ... ok
test_unattributed_payload_key_exposed (test_server.TestDashboardServer.test_unattributed_payload_key_exposed) ... ok
test_usage_endpoint (test_server.TestDashboardServer.test_usage_endpoint) ... ok
test_usage_honors_as_of (test_server.TestDashboardServer.test_usage_honors_as_of) ... ok
test_usage_invalid_as_of (test_server.TestDashboardServer.test_usage_invalid_as_of) ... ok

----------------------------------------------------------------------
Ran 55 tests in 0.125s

OK
```

Loader recount: `unittest.defaultTestLoader.discover("tests").countTestCases() == 55`.

Breakdown: accounting 13/13, features 6/6, hourly 20/20, server 16/16 (9 baseline + 7 patch tests including `test_js_dom_transitions`). Baseline `249d086` was 48 tests; this patch adds 7.

### 3.2 JS DOM transition suites — 3/3 PASS

Independent of the Python subprocess wrapper:

```bash
node tests/test_dashboard_js_transitions.js
```

```text
Running Test 1: Transition from non-empty cutoff to empty cutoff resets usage counts...
  PASS: Transition 1 verified cleanly.
Running Test 2: Transition from success to HTTP 400 error clears all unattributed fields...
  PASS: Transition 2 verified cleanly.
Running Test 3: Direct renderHourly(null) and renderUsage(null)...
  PASS: Direct null fallbacks verified cleanly.

All 3 JS transition regression suites passed successfully.
```

Exit code **0**. The same file also ran inside `test_js_dom_transitions` (Python subprocess) and passed.

| Suite | Scenario | Assertions verified in this run |
| :--- | :--- | :--- |
| 1 | Non-empty usage → empty `projects: {}` | `#events-unattributed` and `#tokens-unattributed` reset to `n/a` with class `na` (were `85` and `12500 in / 3400 out`) |
| 2 | Successful `loadAll` → HTTP 400 on all JSON APIs | All six unattributed metric cells cleared (`n/a` / `unknown`); chart fallback paragraph `no bucket data (unknown)`; `#hourly-error` and `#usage-error` unhidden |
| 3 | Direct `renderHourly(null)` + `renderUsage(null)` | Same six-cell + chart clearing without going through `fetch` |

The harness loads **real** `static/dashboard.js` and `static/index.html` IDs via Node `vm`, not a reimplementation of the renderers.

---

## 4. Code Change Evaluation

### 4.1 Bugfix 1 — `renderUsage` empty-projects early return

**Defect:** `if (keys.length === 0) { ... return; }` ran before the unattributed card update, so a later empty cutoff left `#events-unattributed` / `#tokens-unattributed` showing the previous window.

**Fix** (patched `static/dashboard.js`):

```javascript
if (keys.length === 0) {
  setCell("events-unattributed", { text: "n/a", cls: "na" });
  setCell("tokens-unattributed", { text: "n/a", cls: "na" });
  // ... "no usage data (unknown)" row ...
  return;
}
```

The non-empty path still writes the unattributed card from `projects.unattributed` or `data.unattributed`, and the `else` branch writes `n/a` when that object is missing. `renderUsage(null)` takes the empty-keys path and therefore now clears those two cells. **Verified by JS suite 1 and suite 3.**

### 4.2 Bugfix 2 — unattributed card clearing on `data === null` / HTTP 400

`loadAll` already called `renderHourly(null)` and `renderUsage(null)` on fetch failure. The missing work was inside those renderers for the **new** `#unattributed` card, which is not in `PROJECT_IDS`.

Patched `renderHourly`:

```javascript
var u = (projects && projects.unattributed) || (data && data.unattributed) || null;
if (!u || data === null) {
  setCell("unique-unattributed", { text: "n/a", cls: "na" });
  setCell("hours-unattributed", (data !== null && topUnattrib !== null) ? fmtHours(topUnattrib) : { text: "n/a", cls: "na" });
  setCell("coverage-unattributed", { text: "unknown", cls: "na" });
  setCell("telemetry-status-unattributed", { text: "unknown", cls: "na" });
  renderChart("unattributed", []);
}
```

`renderChart(..., [])` writes a single `<p class="muted">no bucket data (unknown)</p>`.

**Architectural note (does not block ACCEPT):** `renderHourly` itself clears four hourly unattributed cells plus the chart. The two usage cells (`#events-unattributed`, `#tokens-unattributed`) are cleared by `renderUsage`. Combined `loadAll` HTTP-400 behavior (suite 2) and the explicit dual-null call (suite 3) clear all six fields. Splitting hourly vs usage ownership is the correct layering.

### 4.3 Synchronized `as_of` dispatch

Patched `loadAll`:

```javascript
var queryParam = asOfISO ? "?as_of=" + encodeURIComponent(asOfISO) : "";
var hourlyURL = "/api/hourly" + queryParam;
var usageURL = "/api/usage" + queryParam;
var featuresURL = "/api/features" + queryParam;
```

`/api/health` correctly remains unparameterized. `static/index.html` `#asof-help` now documents all three JSON APIs.

Backend: `_handle_hourly`, `_handle_usage`, and `_handle_features` all call `_parse_as_of` and return HTTP 400 `{"error": "invalid as_of"}` on parse failure. Python tests `test_*_honors_as_of` and `test_*_invalid_as_of` passed for hourly, usage, and features.

### 4.4 Unattributed card presence

`static/index.html` adds `<section class="card card-unattributed" id="unattributed">` with IDs `unique-unattributed`, `hours-unattributed`, `coverage-unattributed`, `telemetry-status-unattributed`, `events-unattributed`, `tokens-unattributed`, `chart-unattributed`, plus the non-productive warning copy. `test_html_root_contains_unattributed_card` passed.

### 4.5 Non-blocking observations

1. **Trailing newline** in `tests/test_server.py` (`git apply` whitespace warning). Cosmetic.
2. **Server synthesized zeros when `projects` lacks `unattributed`:** `_load_hourly_payload` / `_load_usage_payload` emit a top-level `unattributed` object with `unique_agents: 0` / `event_count: 0` and `unknown: True`. On a **non-empty** `projects` map that still lacks an `unattributed` key, the frontend would display `0` rather than `n/a`. On a fully empty `projects` map, the new early-return path now shows `n/a` and ignores that synthesized object. This is inherited C2372 payload shaping, outside the C2374 transition defect, and is recorded for the next owner rather than treated as a transition-test failure.
3. **JS harness uses a mock DOM**, not a browser. `MockElement.textContent` clears `children` only when the assigned string is empty, which matches `renderChart`'s `host.textContent = ""` then `appendChild`. Metric cells are text-only. Suites passed against real `dashboard.js`.
4. This ACCEPT does **not** apply the patch to canonical `agent-dashboard`. Integration remains with `agent-dashboard-head` under `.local/git.lock`.

---

## 5. Epistemic Invariants

| Invariant | Evidence |
| :--- | :--- |
| Unknown tokens render as `n/a`, never coerced to `0` in formatters | `fmtTokens` / `fmtInt` / `fmtHours` still return `{text:"n/a", cls:"na"}` on nullish; `test_unknown_cache_and_reasoning_stay_null` and `test_known_zero_preserved` still pass |
| Coverage null → `unknown` | `fmtCoverage`; suite 2/3 assert `#coverage-unattributed` == `unknown` |
| Empty chart → `no bucket data (unknown)` | `renderChart` empty path; suites 2 and 3 |
| Stale unattributed usage cannot survive empty cutoff | Suite 1 |
| HTTP 400 / null payload cannot leave unattributed card showing prior numbers or a prior chart | Suites 2 and 3 |
| Invalid `as_of` fail-closed HTTP 400 | `test_hourly_invalid_as_of`, `test_usage_invalid_as_of`, `test_features_invalid_as_of` |
| Canonical schema / accounting tests unchanged and green | 48 baseline tests still OK |
| No synthetic remapping of unattributed hours into product cards | `PROJECT_IDS` still the four products; unattributed is a separate card with explicit warning copy |

---

## 6. Host Safety

| Gate | Result |
| :--- | :--- |
| Canonical `/home/alexey/git/agent-dashboard` | Read-only; HEAD `249d086`; porcelain empty after all reviewer commands |
| Compiler hold | Reviewer invoked no `cargo`/`rustc`; `pgrep -x cargo` and `pgrep -x rustc` empty at 07:12:01Z and 07:14:16Z |
| Disk | Scratch testbed `980K` (clone `--local` hardlinks object store); parent store mode `0700` |
| Git commits / pushes by this reviewer | **none** |
| Secrets in this report | FileBus credential token is **not** copied here |

---

## 7. Requirement Trace

| # | Requirement | Result |
| :---: | :--- | :--- |
| 1 | Scratch clone replay atop `249d086` with zero rejects | **PASS** (`git apply --verbose`, 0 rejects / 0 fuzz) |
| 2 | 55/55 Python unittests | **PASS** (0.125s, OK) |
| 3 | 3/3 Node JS DOM transition suites (non-empty→empty, HTTP error clearing, null fallbacks) | **PASS** (direct `node` exit 0; also via `test_js_dom_transitions`) |
| 4 | Strict read-only canonical repository | **PASS** |
| 5 | Zero compiler invocations by this reviewer; none observed in snapshots | **PASS** |
| C2374-1 | `renderUsage` resets unattributed usage cells before empty return | **PASS** |
| C2374-2 | Null / HTTP 400 clears unattributed hourly cells + chart (usage cells via `renderUsage`) | **PASS** |
| C2372 | Synchronized `as_of` across `/api/hourly`, `/api/usage`, `/api/features` | **PASS** |

---

## 8. Final Sign-Off

Independent dogfood-model-reviewer (`6a925c23-5f88-479b-88b4-3f880e98b1e9`) **ACCEPTS** patch SHA256 `7a9322a9331aede2ab428f68176b96fdc08d266e10d765b416f842040eefb3d7` as a clean, tested C2374 transition repair atop `249d086a007ee3d5d0381334a27d56771b959d11`.

- 55/55 unit tests passed in the isolated testbed.
- 3/3 JS DOM transition suites passed against real `dashboard.js`.
- Canonical `agent-dashboard` was not mutated.
- Next product action (out of this reviewer's scope): `agent-dashboard-head` may apply the same patch under `.local/git.lock` after this FileBus reply.

**Verdict: ACCEPT.**
