# REV-DASHBOARD-UNATTRIBUTED-AS-OF-C2372 — Independent Technical Audit of Dashboard Unattributed Visibility & as_of Window Alignment Patch (Directives C2371 & C2372)

- **Audit Target Deliverable 1 (Patch):** [`research/antigravity/recovery/dashboard-unattributed-and-as-of-c2372.patch`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/recovery/dashboard-unattributed-and-as-of-c2372.patch)
  * File Size: 12,312 bytes (252 lines)
  * SHA256 Checksum: `2a063916037a188ae93e4efe23e3b3b1db9f445a0efcc462075b8fb36d01cf51`
- **Audit Target Deliverable 2 (Report):** [`research/antigravity/recovery/REPORT-DASHBOARD-UNATTRIBUTED-AS-OF-C2372.md`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/recovery/REPORT-DASHBOARD-UNATTRIBUTED-AS-OF-C2372.md)
  * File Size: 10,978 bytes (137 lines)
  * SHA256 Checksum: `9aad6cdc30644cb84790994bd4877a3b010f25c5f1ce202ce0bdc2a96cc587c8`
- **Pinned Base Commit (HEAD):** `249d086a007ee3d5d0381334a27d56771b959d11` on branch `main` in `/home/alexey/git/agent-dashboard`
- **Auditor / Reviewer:** Independent Technical Reviewer (`reviewer259`, session `259526a9-5deb-47ce-810c-ca5f2da56b68`)
- **Patch Author / Reconciler:** `architect06` (Session UUID: `06ecf158-e51f-411c-89b8-083fc9fb3dd6`)
- **Parent Orchestrator:** `antigravity-head` (`245c7bba-9a7b-45c1-87a7-4537f289f9a5`)
- **Governing Directives:** Codex Principal Directives C2371, C2372, C2366, C2361; Operating Model ([`coordination/OPERATING-MODEL.md`](file:///home/alexey/git/cloudflare-agent-git/coordination/OPERATING-MODEL.md)); Authoritative Four-Product Delivery Reset
- **Scratch Testbed:** `/home/alexey/git/cloudflare-agent-git/.local/scratch/reviewer259-dashboard-c2372-audit/testbed/` (mode `0700`, measured disk footprint 972 KB $\le$ 512 MB ceiling, net `/tmp` growth = 0 bytes)
- **Canonical Repository Access Mode:** **STRICTLY READ-ONLY** (0 writes, 0 edits, 0 git stage/commit mutations in `/home/alexey/git/agent-dashboard`)
- **Compiler Invariant:** ZERO `cargo` / `rustc` compiler invocations host-wide under human hold
- **Verdict:** **ACCEPT (CLEAN SCRATCH REPLAY ATOP BASE 249d086 WITH ZERO REJECTS; 54/54 UNIT & SERVER ENDPOINT TESTS PASS IN 0.114S; EXPLICIT UNATTRIBUTED COHORT VISIBILITY RESTORED IN HTML/CSS/JS WITH PROMINENT NON-PRODUCTIVE WARNING; SYNCHRONIZED AS_OF WINDOW DISPATCH CERTIFIED ACROSS ALL THREE JSON APIS; HTTP 400 VALIDATION ON INVALID TIMESTAMPS VERIFIED; ZERO SYNTHETIC REMAPPING OR FAKE ZEROS; CANONICAL TREE UNTOUCHED)**

---

## 1. Executive Summary & Review Verdict

Under Codex Principal Directives C2371 and C2372, this independent technical audit evaluates the isolated patch and accompanying reconciliation report authored by `architect06` to resolve two key operational omissions originally identified by Grok independent model inspection ([`REV-DASHBOARD-249D086-GROK-ADOPTION-20261005T054222Z.md`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/reviews/REV-DASHBOARD-249D086-GROK-ADOPTION-20261005T054222Z.md), SHA256: `93c8f34b...`):
1. **Omission 1: Hidden Unattributed Cohort:** The prior dashboard UI rendered only the 4 canonical product cards (`agent-branches`, `agent-dashboard`, `quota-launcher`, `agent-coordination`), hiding the dominant unattributed infrastructure cohort (~96% of total observed hours: 317 agents / 5,276.0583 hours at the 04Z export) from visual inspection.
2. **Omission 2: Unsynchronized `as_of` Query Dispatch:** The frontend UI passed `?as_of=<ISO8601>` only to `/api/hourly`, leaving `/api/usage` and `/api/features` unbound and falling back to present server time `now()`, creating acute temporal inconsistency across dashboard panels when a historical cutoff was selected.

### Core Audit Outcomes:
- **Clean Scratch Replay:** The patch applied with zero rejects and zero fuzz against a clean scratch clone of `/home/alexey/git/agent-dashboard` at base commit `249d086a007ee3d5d0381334a27d56771b959d11`. Canonical repository `/home/alexey/git/agent-dashboard` remained completely untouched and strictly read-only.
- **Automated Test Suite Pass (54/54):** All 48 baseline tests plus 6 new server endpoint tests pass cleanly in 0.114 seconds (Exit Code 0).
- **Explicit Unattributed Card Architecture:** An explicit `<section class="card card-unattributed" id="unattributed">` was added to `static/index.html` with distinct slate border styling (`#475569`) and an amber warning: *"Unscoped/platform telemetry (unknown origin, never counted as productive agent work)."* Full metrics (unique agents, hours, coverage, usage events, tokens in/out, and 24-bucket timeline) are rendered dynamically.
- **Synchronized `as_of` Dispatch:** `loadAll(asOfISO)` in `static/dashboard.js` now uniformly passes `queryParam` (`?as_of=...`) to `/api/hourly`, `/api/usage`, and `/api/features`.
- **Fail-Closed HTTP 400 Validation:** In `src/dashboard/server.py`, `_handle_hourly`, `_handle_usage`, and `_handle_features` all parse `as_of` via `_parse_as_of` and return HTTP 400 `{"error": "invalid as_of"}` on malformed timestamps.
- **Epistemic Invariance:** Zero synthetic remappings or fake zeros were introduced. Unknown tokens remain `None` / `null` rendering as `"n/a"`, unknown coverage renders as `"unknown"`, and canonical schema keys in `src/dashboard/__init__.py` remain intact.

**Final Verdict: ACCEPT.** The patch cleanly and faithfully resolves both defects without regressions, preserving epistemic boundaries and repository safety.

---

## 2. Scratch Replay & Patch Integrity Verification

### 2.1 Artifact Checksum & Size Audit
| Artifact | Path | Expected SHA256 | Measured SHA256 | Bytes | Status |
| :--- | :--- | :--- | :--- | :---: | :---: |
| Patch | `research/antigravity/recovery/dashboard-unattributed-and-as-of-c2372.patch` | `2a063916037a188ae93e4efe23e3b3b1db9f445a0efcc462075b8fb36d01cf51` | `2a063916037a188ae93e4efe23e3b3b1db9f445a0efcc462075b8fb36d01cf51` | 12,312 | **EXACT MATCH** |
| Report | `research/antigravity/recovery/REPORT-DASHBOARD-UNATTRIBUTED-AS-OF-C2372.md` | `9aad6cdc30644cb84790994bd4877a3b010f25c5f1ce202ce0bdc2a96cc587c8` | `9aad6cdc30644cb84790994bd4877a3b010f25c5f1ce202ce0bdc2a96cc587c8` | 10,978 | **EXACT MATCH** |

### 2.2 Clean Application Replay atop Base `249d086`
A dedicated scratch clone was established in `.local/scratch/reviewer259-dashboard-c2372-audit/testbed/` and checked out at commit `249d086a007ee3d5d0381334a27d56771b959d11`:
```bash
git apply --verbose /home/alexey/git/cloudflare-agent-git/research/antigravity/recovery/dashboard-unattributed-and-as-of-c2372.patch
```
Observed output:
```text
Checking patch src/dashboard/server.py...
Checking patch static/dashboard.css...
Checking patch static/dashboard.js...
Checking patch static/index.html...
Checking patch tests/test_server.py...
Applied patch src/dashboard/server.py cleanly.
Applied patch static/dashboard.css cleanly.
Applied patch static/dashboard.js cleanly.
Applied patch static/index.html cleanly.
Applied patch tests/test_server.py cleanly.
```
Status: **100% clean application with 0 rejects and 0 fuzz**.

### 2.3 Canonical Repository Isolation
Canonical `/home/alexey/git/agent-dashboard` was checked with `git status --porcelain`:
- Uncommitted modifications: **0**
- Untracked files: **0**
- State: **Strictly Clean & Read-Only**.

---

## 3. Test Suite Execution & Regression Audit

The full test suite was executed in the patched testbed:
```bash
PYTHONPATH=src python3 -m unittest discover -s tests/ -v
```

### 3.1 Test Results Ledger (54/54 PASS)
```text
test_24h_usage_filter (test_accounting.TestUsageAccounting) ... ok
test_boolean_and_negative_counts_invalid (test_accounting.TestUsageAccounting) ... ok
test_canonical_project_id_aliases_and_fourth_product (test_accounting.TestUsageAccounting) ... ok
test_deduplication_by_response_id (test_accounting.TestUsageAccounting) ... ok
test_known_zero_preserved (test_accounting.TestUsageAccounting) ... ok
test_missing_response_id_does_not_dedup_on_timestamp (test_accounting.TestUsageAccounting) ... ok
test_noncanonical_project_unattributed (test_accounting.TestUsageAccounting) ... ok
test_nullability_and_types (test_accounting.TestUsageAccounting) ... ok
test_opencode_adapter_reasoning_not_folded (test_accounting.TestUsageAccounting) ... ok
test_quota_not_converted_to_cost_or_tokens (test_accounting.TestUsageAccounting) ... ok
test_reasoning_token_subset_isolation (test_accounting.TestUsageAccounting) ... ok
test_unknown_cache_and_reasoning_stay_null (test_accounting.TestUsageAccounting) ... ok
test_usage_accounting_alias_and_coordination_routing (test_accounting.TestUsageAccounting) ... ok
test_24h_completed_feature_filter (test_features.TestFeaturesTracking) ... ok
test_feature_extraction_and_deduplication (test_features.TestFeaturesTracking) ... ok
test_missing_commit_or_tests_rejected (test_features.TestFeaturesTracking) ... ok
test_missing_tasks_file_unknown (test_features.TestFeaturesTracking) ... ok
test_unaccepted_substring_not_counted (test_features.TestFeaturesTracking) ... ok
test_updated_at_is_not_accepted_at (test_features.TestFeaturesTracking) ... ok
test_agent_across_three_adjacent_buckets (test_hourly.TestHourlyUtilization) ... ok
test_bucket_generation (test_hourly.TestHourlyUtilization) ... ok
test_canonical_project_id_aliases_and_fourth_product (test_hourly.TestHourlyUtilization) ... ok
test_duplicate_identical_spans_do_not_change_hours (test_hourly.TestHourlyUtilization) ... ok
test_ended_before_started_invalid_spans (test_hourly.TestHourlyUtilization) ... ok
test_future_ended_at_clamped_to_as_of (test_hourly.TestHourlyUtilization) ... ok
test_hourly_utilization_aliases_and_fourth_product (test_hourly.TestHourlyUtilization) ... ok
test_identity_deduplication (test_hourly.TestHourlyUtilization) ... ok
test_invalid_ended_at_unknown_ended_not_alive (test_hourly.TestHourlyUtilization) ... ok
test_missing_agent_id_unattributed_hours (test_hourly.TestHourlyUtilization) ... ok
test_missing_spans_unknown_not_zeros (test_hourly.TestHourlyUtilization) ... ok
test_non_hour_as_of_exact_window (test_hourly.TestHourlyUtilization) ... ok
test_noncanonical_project_goes_to_unattributed (test_hourly.TestHourlyUtilization) ... ok
test_overlapping_spans_union_once (test_hourly.TestHourlyUtilization) ... ok
test_partial_hour_calculation (test_hourly.TestHourlyUtilization) ... ok
test_registry_shape_rejects_members (test_hourly.TestHourlyUtilization) ... ok
test_shared_agent_ids_non_additive (test_hourly.TestHourlyUtilization) ... ok
test_single_agent_clipping (test_hourly.TestHourlyUtilization) ... ok
test_span_entirely_outside_window (test_hourly.TestHourlyUtilization) ... ok
test_union_seconds_helper (test_hourly.TestHourlyUtilization) ... ok
test_features_endpoint (test_server.TestDashboardServer) ... ok
test_features_honors_as_of (test_server.TestDashboardServer) ... ok
test_features_invalid_as_of (test_server.TestDashboardServer) ... ok
test_health_endpoint (test_server.TestDashboardServer) ... ok
test_hourly_endpoint (test_server.TestDashboardServer) ... ok
test_hourly_honors_as_of (test_server.TestDashboardServer) ... ok
test_hourly_invalid_as_of (test_server.TestDashboardServer) ... ok
test_html_root_contains_unattributed_card (test_server.TestDashboardServer) ... ok
test_html_root_endpoint (test_server.TestDashboardServer) ... ok
test_missing_source_coverage_gap (test_server.TestDashboardServer) ... ok
test_static_css_if_present (test_server.TestDashboardServer) ... ok
test_unattributed_payload_key_exposed (test_server.TestDashboardServer) ... ok
test_usage_endpoint (test_server.TestDashboardServer) ... ok
test_usage_honors_as_of (test_server.TestDashboardServer) ... ok
test_usage_invalid_as_of (test_server.TestDashboardServer) ... ok

----------------------------------------------------------------------
Ran 54 tests in 0.114s

OK
```

### 3.2 Breakdown of New Tests Added in `tests/test_server.py`
1. `test_usage_honors_as_of`: Confirms `/api/usage?as_of=...` filters `window_start`/`window_end` correctly and excludes out-of-window events.
2. `test_usage_invalid_as_of`: Asserts HTTP 400 on malformed timestamp.
3. `test_features_honors_as_of`: Confirms `/api/features?as_of=...` filters accepted feature timestamps within `[as_of-24h, as_of)`.
4. `test_features_invalid_as_of`: Asserts HTTP 400 on malformed timestamp.
5. `test_html_root_contains_unattributed_card`: Asserts `#unattributed`, `#chart-unattributed`, `#unique-unattributed`, and warning labels exist in root HTML.
6. `test_unattributed_payload_key_exposed`: Asserts top-level or `projects.unattributed` key is present in `/api/hourly` and `/api/usage`.

---

## 4. Functional & Epistemic Audit Details

### 4.1 Unattributed Card Structure & Demarcation
- In `static/index.html`, lines 100–117:
  ```html
  <section class="card card-unattributed" id="unattributed" aria-label="Unattributed platform telemetry">
    <h2>Unattributed / Platform Telemetry</h2>
    <p class="proj-sub"><code>unattributed</code> <span id="status-unattributed" class="badge badge-unknown">unscoped/platform</span> <span id="unknown-unattributed" class="badge badge-unknown" hidden>unknown</span></p>
    <p class="unattrib-warning muted small">Unscoped/platform telemetry (unknown origin, never counted as productive agent work).</p>
    ...
  </section>
  ```
- **Epistemic Integrity:** The card prominently displays the warning that unattributed telemetry is never counted as productive agent work. It renders in slate styling (`#475569`) with amber warning text, visually segregating platform overhead from product lanes.
- **Metric Fidelity:** Renders `#unique-unattributed`, `#hours-unattributed`, `#coverage-unattributed`, `#telemetry-status-unattributed`, `#events-unattributed`, `#tokens-unattributed`, and full 24-bucket chart `#chart-unattributed`.

### 4.2 Synchronized `as_of` Window Dispatch
- In `static/dashboard.js`, lines 360–365:
  ```javascript
  function loadAll(asOfISO) {
    setRefreshStatus("loading…");
    var queryParam = asOfISO ? "?as_of=" + encodeURIComponent(asOfISO) : "";
    var hourlyURL = "/api/hourly" + queryParam;
    var usageURL = "/api/usage" + queryParam;
    var featuresURL = "/api/features" + queryParam;
  ```
- This resolves Grok Finding 2 completely: all three data endpoints now receive the identical `?as_of=` timestamp, preventing temporal skew between hourly presence, token usage, and feature completions.

### 4.3 Robust Fail-Closed Server Validation
- In `src/dashboard/server.py`:
  ```python
  def _handle_usage(self, query: Dict[str, List[str]]) -> None:
      as_of, err = _parse_as_of(query)
      if err:
          self._handle_json({"error": err}, status=400)
          return
      assert as_of is not None
      self._handle_json(_load_usage_payload(as_of))
  ```
  Identical fail-closed logic operates across `_handle_hourly`, `_handle_usage`, and `_handle_features`.

### 4.4 Preservation of Unknowns and Zero Fabrication
- `CANONICAL_PROJECT_IDS` in `src/dashboard/__init__.py` remains strictly:
  `("agent-branches", "agent-dashboard", "quota-launcher", "agent-coordination")`.
- Unknown project IDs continue to map to `unattributed`.
- Unknown tokens are preserved as `None` / `null` rendering as `"n/a"`, never coerced to fake 0s.
- Unknown coverage preserves `None` rendering as `"unknown"`.
- Zero synthetic remappings: `a16-runtime-protocol` and other infrastructure teams remain in `unattributed` until proven per-span mappings are established under task `ad-b2-unattributed-provenance`.

---

## 5. Epistemic Invariants & Safety Accounting

1. **Compiler Invariant:** ZERO `cargo` or `rustc` compiler invocations occurred host-wide.
2. **Canonical Trees:** `/home/alexey/git/agent-dashboard` remained completely read-only throughout the audit.
3. **Scratch Accounting:**
   - Scratch path: `/home/alexey/git/cloudflare-agent-git/.local/scratch/reviewer259-dashboard-c2372-audit/`
   - Permissions: mode `0700`
   - Measured disk footprint: 972 KB (well below 512 MB ceiling)
   - Net `/tmp` growth: 0 bytes.
4. **Git Operations:** ZERO git commits or pushes executed by subagent.
5. **Publication Guard:** Verified clean via `publication_guard.py` (Exit Code 0).

---

## 6. Conclusion & Handoff Recommendation

The C2372 deliverable ([`dashboard-unattributed-and-as-of-c2372.patch`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/recovery/dashboard-unattributed-and-as-of-c2372.patch)) is of exceptional engineering quality. It cleanly addresses the two deficiencies raised by Grok model review `93c8` without perturbing canonical project definitions, without introducing synthetic remappings, and with comprehensive test coverage.

**Recommendation:** The patch is fully certified for integration by `agent-dashboard-head` (`c7a75f76`) atop canonical `/home/alexey/git/agent-dashboard` under `.local/git.lock`.
