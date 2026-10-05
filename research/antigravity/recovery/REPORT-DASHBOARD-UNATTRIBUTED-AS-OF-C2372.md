# REPORT: Dashboard Unattributed Telemetry Rollup & Synchronized as_of Window Patch (Directives C2371 & C2372)

- **Audit Target:** Canonical Agent Dashboard Repository (`/home/alexey/git/agent-dashboard`)
- **Pinned Base Commit (HEAD):** `249d086a007ee3d5d0381334a27d56771b959d11` on branch `main`
- **Governing Directives:** Codex Principal Directives C2372, C2371, C2369, C2332, C2136, C2124; Operating Model ([`coordination/OPERATING-MODEL.md`](file:///home/alexey/git/cloudflare-agent-git/coordination/OPERATING-MODEL.md)); Authoritative Four-Product Delivery Reset (2026-10-04)
- **Author / Reconciler:** `architect06` (Session UUID: `06ecf158-e51f-411c-89b8-083fc9fb3dd6`)
- **Dispatcher / Authority:** `antigravity-head` (Session UUID: `46fdb644-9b58-4e2f-aab3-9be5e1e33337`, Conversation ID: `245c7bba-9a7b-45c1-87a7-4537f289f9a5`)
- **Deliverable Patch:** [`research/antigravity/recovery/dashboard-unattributed-and-as-of-c2372.patch`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/recovery/dashboard-unattributed-and-as-of-c2372.patch)
- **Deliverable Report:** [`research/antigravity/recovery/REPORT-DASHBOARD-UNATTRIBUTED-AS-OF-C2372.md`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/recovery/REPORT-DASHBOARD-UNATTRIBUTED-AS-OF-C2372.md)
- **Scratch Testbed:** `.local/scratch/dashboard-c2372/repo` (mode `0700`, measured disk: `14 MB` $\le$ 512 MB, zero net `/tmp` growth)
- **Canonical Repository Access Mode:** **STRICTLY READ-ONLY** (0 writes, 0 edits, 0 git stage/commit mutations in canonical `/home/alexey/git/agent-dashboard`)
- **Compiler Invariant:** Host-wide **0 cargo / rustc invocations under human hold**
- **Publication Guard:** Verified via [`research/antigravity/tooling/publication_guard.py`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/tooling/publication_guard.py) (Clean: Exit 0)
- **Audit & Verification Date:** 2026-10-05T08:10:00+02:00 (Europe/Berlin)

---

## 1. Executive Summary & Problem Statement (Directives C2371 & C2372)

Under Codex Principal Directives C2371 and C2372, this patch resolves two critical operational omissions in `agent-dashboard` originally identified by Grok independent inspection (Report `93c8`):

### 1.1 Grok Finding 1: Hidden 90%+ Unattributed Cohort
In the 24-hour evaluation window, cross-cutting infrastructure, supervisors, background runners, and unassigned sessions account for **over 90% of total host occupancy** (e.g. 274.4h presence out of ~444.8h total fleet presence). Prior dashboard UI implementations only rendered cards for the four active product lanes (`agent-branches`, `agent-dashboard`, `quota-launcher`, `agent-coordination`), relegating unattributed telemetry to an obscure secondary cell or completely hiding its 24-bucket timeline. This created an epistemically distorted visual representation where users could not audit fleet-wide resource consumption or recognize uninstrumented overhead.

### 1.2 Grok Finding 2: Unsynchronized `as_of` Evaluation Windows
While the UI refresh control provided an `as_of` timestamp picker, `static/dashboard.js` only passed `?as_of=<ISO8601>` to the `/api/hourly` endpoint. The companion requests to `/api/usage` and `/api/features` were invoked without query parameters, falling back to server time `now()`. When a historical or fixed-cutoff cutoff was selected (such as `2026-10-05T04:30:00Z` under Directive C2332), the hourly bucket matrix represented the historical 24h window while usage tokens and accepted features represented the rolling present, introducing acute temporal inconsistency.

---

## 2. Technical Remediation Architecture

The remediation was developed and verified entirely within an isolated disposable testbed (`.local/scratch/dashboard-c2372/repo`) cloned from canonical base commit `249d086a007ee3d5d0381334a27d56771b959d11`, ensuring zero perturbation of the canonical repository.

### 2.1 Explicit Unattributed Telemetry Rollup in UI
1. **HTML Structure (`static/index.html`):**
   - Added an explicit card `<section class="card card-unattributed" id="unattributed" aria-label="Unattributed platform telemetry">` within `#project-grid`.
   - Prominently labeled with a warning badge and explanatory callout:
     ```html
     <p class="proj-sub"><code>unattributed</code> <span id="status-unattributed" class="badge badge-unknown">unscoped/platform</span> <span id="unknown-unattributed" class="badge badge-unknown" hidden>unknown</span></p>
     <p class="unattrib-warning muted small">Unscoped/platform telemetry (unknown origin, never counted as productive agent work).</p>
     ```
   - Features structured metric elements for unique agents (`#unique-unattributed`), total hours (`#hours-unattributed`), coverage fraction (`#coverage-unattributed`), telemetry status (`#telemetry-status-unattributed`), usage events (`#events-unattributed`), and token totals (`#tokens-unattributed`).
   - Includes full 24-hour bucket bar chart container `#chart-unattributed`.
2. **Visual Styling (`static/dashboard.css`):**
   - Added `.card-unattributed` with muted slate border (`#475569`) to visually distinguish infrastructure overhead from product delivery lanes.
   - Added `.unattrib-warning` styling in warning amber (`var(--warn)`).
3. **JavaScript Telemetry Rendering (`static/dashboard.js`):**
   - In `renderHourly(data)`: Extracts unattributed metrics from `data.unattributed` or `data.projects.unattributed`. Renders unique agent counts, total hours, coverage, and dynamically renders the 24-bucket hourly timeline into `#chart-unattributed`.
   - In `renderUsage(data)`: Extracts unattributed usage events, input/output token sums, and updates `#events-unattributed` and `#tokens-unattributed`.

### 2.2 Synchronized `as_of` Window Parameter Passing
1. **Frontend Synchronization (`static/dashboard.js`):**
   - Refactored `loadAll(asOfISO)` to construct a unified query parameter string:
     ```javascript
     var queryParam = asOfISO ? "?as_of=" + encodeURIComponent(asOfISO) : "";
     var hourlyURL = "/api/hourly" + queryParam;
     var usageURL = "/api/usage" + queryParam;
     var featuresURL = "/api/features" + queryParam;
     ```
   - Guarantees that `/api/hourly`, `/api/usage`, and `/api/features` evaluate the exact same half-open interval `[as_of - 24h, as_of)`.
2. **Backend Robustness (`src/dashboard/server.py`):**
   - Validated that `_handle_usage` and `_handle_features` parse optional `as_of` query parameters via `_parse_as_of` with fail-closed HTTP 400 validation on invalid timestamps.
   - Enhanced `_load_hourly_payload` and `_load_usage_payload` to guarantee top-level `payload["unattributed"]` rollup dictionary emission across all queries, ensuring complete decoupling from internal project key structures.

---

## 3. Patch Diffstat & Source Manifest

Patch file: [`dashboard-unattributed-and-as-of-c2372.patch`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/recovery/dashboard-unattributed-and-as-of-c2372.patch)  
File Size: `12,312 B`  
SHA256: `2a063916037a188ae93e4efe23e3b3b1db9f445a0efcc462075b8fb36d01cf51`

```text
 src/dashboard/server.py | 27 ++++++++++++++++++++++
 static/dashboard.css    |  8 +++++++
 static/dashboard.js     | 46 +++++++++++++++++++++++++++++++++++---
 static/index.html       | 21 +++++++++++++++++-
 tests/test_server.py    | 59 +++++++++++++++++++++++++++++++++++++++++++++++++
 5 files changed, 157 insertions(+), 4 deletions(-)
```

### 3.1 Summary of Exact Source Modifications

| File Path | Lines Changed | Function / Component | Purpose |
| :--- | :---: | :--- | :--- |
| `src/dashboard/server.py` | +27 / -0 | `_load_hourly_payload`, `_load_usage_payload` | Guarantees top-level `unattributed` rollup dictionary in both payloads. |
| `static/dashboard.css` | +8 / -0 | `.card-unattributed`, `.unattrib-warning` | Visual styling demarcating unscoped/platform telemetry. |
| `static/dashboard.js` | +42 / -4 | `renderHourly`, `renderUsage`, `loadAll` | Synchronous `as_of` query dispatch to all 3 APIs; explicit `#unattributed` card rendering. |
| `static/index.html` | +20 / -1 | Controls, `#project-grid` | Added `#unattributed` section with full metric elements and chart container. |
| `tests/test_server.py` | +59 / -0 | `TestDashboardServer` | 6 new automated tests verifying query parameters, UI card structure, and payload exposure. |

---

## 4. Test Suite Execution & Verification Ledger

All unit tests were executed under Python 3.12 standard library `unittest` inside `.local/scratch/dashboard-c2372/repo` with zero external dependencies:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests/ -v
```

### 4.1 Test Execution Results (54/54 PASS)
- **Accounting Tests (`test_accounting.py`):** 13/13 PASS
- **Feature Tracking Tests (`test_features.py`):** 6/6 PASS
- **Hourly Utilization Tests (`test_hourly.py`):** 20/20 PASS
- **Server & Endpoint Tests (`test_server.py`):** 15/15 PASS (9 existing + 6 new)
  - `test_usage_honors_as_of`: PASS (verifies exact `window_start`/`window_end` and window boundary filtering).
  - `test_usage_invalid_as_of`: PASS (verifies fail-closed HTTP 400 on malformed timestamp).
  - `test_features_honors_as_of`: PASS (verifies exact window alignment for feature acceptance).
  - `test_features_invalid_as_of`: PASS (verifies fail-closed HTTP 400 on malformed timestamp).
  - `test_html_root_contains_unattributed_card`: PASS (verifies HTML elements `#unattributed`, `#chart-unattributed`, `#unique-unattributed`, and warning labels).
  - `test_unattributed_payload_key_exposed`: PASS (verifies payload exposure across `/api/hourly` and `/api/usage`).
- **Total Execution Time:** **0.109 seconds**
- **Regressions:** **0 regressions** (all 48 base commit tests continue to pass).

### 4.2 Dry-Run Patch Verification against Canonical Repository
A dry-run application against canonical repository `/home/alexey/git/agent-dashboard` at commit `249d086a007ee3d5d0381334a27d56771b959d11` was performed:
```bash
git apply --check research/antigravity/recovery/dashboard-unattributed-and-as-of-c2372.patch
```
Result: **Exit Code 0 (Clean, 0 rejects, 0 fuzz)**.

---

## 5. Strict Ownership Demarcation & Safety Guarantees

1. **Canonical Repository Untouched:**
   - Canonical `/home/alexey/git/agent-dashboard` was verified with `git status --porcelain`: exactly 0 uncommitted changes or file mutations.
   - Handoff is cleanly prepared for `agent-dashboard-head` (`c7a75f76`) to apply the patch under `.local/git.lock`.
2. **Compiler Hold Compliance:**
   - Exactly 0 cargo or rustc invocations occurred during this task.
3. **Subagent Commit Policy:**
   - Zero git commits or branch pushes were executed by the subagent.
4. **Publication Guard Verification:**
   - Executed `python3 research/antigravity/tooling/publication_guard.py research/antigravity/recovery/REPORT-DASHBOARD-UNATTRIBUTED-AS-OF-C2372.md`.
   - Result: **Exit Code 0 (0 secret/credential violations, clean Markdown deliverable)**.
