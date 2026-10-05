# Fleet Tasks Tracker, Usability Analytics, and Kanban Dashboard

**Document Tag:** `REPORT-DASHBOARD-TASKS-USABILITY`  
**Date:** 2026-10-05  
**Author / Implementer:** `dashboard-tasks-implementer` (`antigravity-head` delegate, session `64c2fff8`)  
**Parent Coordinator:** `antigravity-head` (`245c7bba-9a7b-45c1-87a7-4537f289f9a5`)  
**Context:** Codex Principal C2426 directives & direct human instruction `experiment/human-usable-task-tracker-20261005.txt` ("let's make sure we have a usable tracker")  
**Target Repository:** `agent-dashboard` (base commit: `249d086`)  
**Deliverable Patch:** `research/antigravity/recovery/dashboard-tasks-tracker-and-usability.patch`  

---

## 1. Executive Summary

This report records the complete design, implementation, and test verification of the **Private Fleet Task Tracker & Usability Analytics Suite** for `agent-dashboard`. The work directly fulfills the latest human instruction (*"let's make sure we have a usable tracker"*, October 5, 2026) and addresses the user's explicit preference for visual analytics (*"I want charts graphs etc"*).

All development was performed inside an isolated, disposable scratch testbed (`.local/scratch/dashboard-tasks-impl/`, mode `0700`, 1.2 MB). The canonical checkout `/home/alexey/git/agent-dashboard` remained **strictly read-only** throughout the entire prototyping cycle.

### Key Capabilities Delivered:
1. **Private Backend Endpoint (`/api/tasks`):**
   - Continuously ingests canonical task data from `coordination/TASKS.json` and human delivery requirements from `coordination/DELIVERY-BACKLOG.json`.
   - Exposes normalized, structured task objects across 11 core fields (`id`, `title`, `product`, `state`, `owner`, `priority`, `description`, `next_action`, `blocker`, `last_update`, `outcome_evidence`).
   - Accurately maps tasks onto the 5 canonical delivery workstreams: `agent-branches`, `agent-dashboard`, `quota-launcher`, `agent-coordination`, and `infrastructure`.
   - Implements disjoint fleet actor categorization separating **Persistent Coordinators**, **Active Task Workers**, **Ended/Completed Workers**, and **Idle/Blocked Sessions**.
   - Embeds the documented **Agent Update Workflow** enforcing the autonomous delivery contract.
   - Supports query filtering (`?product=...`, `?state=...`, `?owner=...`, `?as_of=...`).
2. **Interactive Frontend UI & Visual Analytics (`static/`):**
   - **Navigation Bar & Stable URL Hash Routing:** Prominent `#tasks` tab entry enabling direct linkability and bookmarking alongside `#overview` and `#actors`.
   - **Graphical Analytics (Native SVG, Zero External Assets):**
     * *Fleet Task State Breakdown:* Interactive SVG Donut chart displaying proportions of `Done` (green), `In Progress` (blue), `Review` (amber), `Blocked` (red), and `Ready/Backlog` (slate), with center completion percentage and legend.
     * *Product Stream Completion:* Horizontal SVG stacked progress bars displaying completion percentages across all 5 product streams.
     * *Priority & Queue Density:* Visual bar graph showing distribution of `Critical`, `High`, `Normal`, and `Low` priority tasks.
   - **Filter & Search Toolbar:** Real-time text search (querying ID, title, description, owner, next action), multi-dimensional dropdowns (Product, State, Owner, Priority), quick reset button, and live matching counter.
   - **Full Kanban Board:** 5 color-coded columns (`Ready/Backlog`, `In Progress`, `Review`, `Blocked`, `Done`) with accent borders, priority badges, blocker warning banners, next-action callouts, and evidence tags.
   - **Collapsible Details & JSON Modal:** Accessible dialog box exposing comprehensive metadata, next action steps, blocker dependencies, verified evidence paths, and collapsible raw JSON with a one-click copy button.
   - **Fleet Actors & Sessions View (`#actors`):** Transparent registry dividing fleet agents into their operational categories.
3. **Comprehensive Test Suite:**
   - 21 new tests added (`tests/test_tasks_endpoint.py` and `tests/test_tasks_ui.py`).
   - 100% test pass rate (69 of 69 tests pass in 1.76 seconds).
   - End-to-end live HTTP query verification against all server endpoints.

---

## 2. Architecture & Data Ingestion Engine

### 2.1 Task Normalization (`src/dashboard/tasks.py`)
The task tracking engine loads data from `coordination/TASKS.json` and cross-references it with `coordination/DELIVERY-BACKLOG.json`:

```
coordination/TASKS.json           coordination/DELIVERY-BACKLOG.json      coordination/TEAM-REGISTRY.json
        │                                         │                                      │
        ▼                                         ▼                                      ▼
   [Raw Tasks]                          [Human Sources Index]                    [Fleet Registry]
        │                                         │                                      │
        └───────────────────────┬─────────────────┘                                      │
                                ▼                                                        ▼
                    [Task Normalization Engine]                              [Actor Categorization]
                                │                                                        │
                                ├─ 11 Structured Task Fields                             ├─ Persistent Coordinators
                                ├─ 5 Canonical Products                                  ├─ Active Task Workers
                                ├─ 5 Normalized States                                   ├─ Ended/Completed Workers
                                ├─ Priority Normalization                                └─ Idle/Blocked Sessions
                                └─ Summary Rollups & Completion %
                                                │
                                                ▼
                                    JSON API: /api/tasks
```

### 2.2 Core Task Fields
Every structured task object exposes the following 11 canonical fields:
| Field | Type | Description / Derivation |
| :--- | :--- | :--- |
| `id` | `str` | Unique task identifier (e.g. `ab-safe-main-restore`, `dashboard-hourly24h`). |
| `title` | `str` | Derived human-readable title from backlog requirement summary / heading, or prettified ID. |
| `product` | `str` | Canonical stream: `agent-branches`, `agent-dashboard`, `quota-launcher`, `agent-coordination`, or `infrastructure`. |
| `state` | `str` | Normalized lifecycle state: `ready`, `in_progress`, `review`, `blocked`, or `done`. |
| `owner` | `str` | Assigned owner tag or worker identity (e.g. `antigravity-head`, `ab-worker-1`). |
| `priority` | `str` | Normalized priority: `critical`, `high`, `normal`, or `low`. |
| `description` | `str` | Detailed requirement summary or acceptance specification. |
| `next_action` | `str` | Concrete next action or continuation trigger. |
| `blocker` | `List[str]` | List of blocked dependencies, upstream gates, or reasons. |
| `last_update` | `str` | ISO8601 timestamp of last recorded change or acceptance. |
| `outcome_evidence` | `List[str]` | Paths to verified test reports, reviews, commits, or verification notes. |

### 2.3 Product Mapping & Canonical Streams
Tasks are mapped onto 5 canonical streams:
- `agent-branches`: Isolated worktree branches, safe main restore, dogfooding workflows.
- `agent-dashboard`: Utilization metrics, usage accounting, completed features, task tracker.
- `quota-launcher`: Quota-aware admission control, token budget tracking, multi-engine execution.
- `agent-coordination`: Cross-computer agent coordination, SSH typed RPC, offline retry.
- `infrastructure`: Shared harness protocols, publication pipeline, supervision, and runtime tooling.

### 2.4 Disjoint Fleet Actor Categorization
The engine categorizes all actors into four disjoint groups:
1. **Persistent Coordinators (Principals, Project Heads):**
   - Autonomous monitoring principals (`codex-principal`, `claude-principal`).
   - Project heads leading delivery workstreams (`antigravity-head`, `agent-dashboard-head`, `quota-launcher-head`, `agent-coordination-head`).
   - Remote coordinators (`desktop-orchestrator`, `public-journal-site`).
2. **Active Task Workers:**
   - Ephemeral workers currently running commands, workloads, or implementing tasks in `in_progress` or `review` states.
3. **Ended / Completed Workers:**
   - Workers that successfully delivered their task checkpoints or completed their execution runs.
4. **Idle / Blocked Sessions:**
   - Sessions awaiting dependencies, queued for execution, or blocked on rate limits.

---

## 3. Frontend Usability & Visual Analytics

### 3.1 Direct URL Hash Navigation (`#tasks`)
The top navigation bar provides stable routing:
- `#overview`: Rolling 24-hour utilization charts, usage accounting table, completed features list.
- `#tasks`: Full Tasks Tracker view with visual analytics, filter toolbar, and Kanban board.
- `#actors`: Fleet actors inventory and session status overview.

When a user visits `http://127.0.0.1:8765/#tasks`, the application immediately activates the Tasks view without reloading or losing state.

### 3.2 Visual Analytics & Charts (Native SVG)
In response to the human request for graphical charts, the Tasks section includes three responsive SVG visualizations:
1. **State Distribution Donut Chart:**
   - SVG circular ring with proportional colored segments for each state.
   - Center readout displaying overall fleet completion percentage (e.g. `68.2%`) and total task count (`148 tasks`).
   - Interactive legend with color dots, task counts, and percentage breakdowns.
2. **Product Stream Completion Stacked Bars:**
   - Horizontal stacked bar charts for all 5 product streams.
   - Shows Done, In Progress, Review, Blocked, and Ready segments.
   - Color-coded completion percentage badges (green >= 70%, blue >= 40%, amber < 40%).
3. **Priority & Queue Density Chart:**
   - Breakdown of tasks by priority level (`Critical`, `High`, `Normal`, `Low`).

### 3.3 Interactive Kanban Board
- 5 parallel columns: `Ready / Backlog`, `In Progress`, `Review`, `Blocked`, `Done`.
- Column headers include status dot indicators, titles, and live counter badges.
- Cards feature:
  * Top bar: Product badge, Priority badge (`Critical` in red, `High` in amber, `Normal` in slate), and monospace Task ID.
  * Title: Bold, readable task name.
  * Description: Truncated 2-line preview.
  * Callouts:
    - **Blocked:** Prominent alert box with red border and dependency list.
    - **In Progress:** Blue-accented next action box.
    - **Done:** Green-accented verification badge.
  * Footer: Owner tag with avatar dot, last update relative timestamp.
  * Click to inspect: Clicking any card opens the detailed modal dialog.

### 3.4 Collapsible Task Details & JSON Modal
- Accessible modal dialog accessible via click or keyboard navigation (`Enter`, `Escape`).
- Metadata summary grid: ID, Product, State, Priority, Owner, Last Updated.
- Full text views: Complete Requirement/Description, Next Action, Blockers & Dependencies, Outcome Evidence.
- **Collapsible Technical Payload:** Raw JSON payload is tucked into an expandable `<details>` element with a "Copy JSON" button, keeping the interface uncluttered for humans while remaining fully inspectable for engineers.

---

## 4. Test Suite & Verification Evidence

### 4.1 Unit & Integration Tests Added
Two dedicated test suites were implemented in `tests/`:

1. `tests/test_tasks_endpoint.py` (9 tests):
   - `test_canonical_task_product_mapping`: Validates mapping across all aliases and default to `infrastructure`.
   - `test_normalize_task_state`: Validates normalization of raw states (`running`, `integrated`, `held`, `done`, etc.).
   - `test_normalize_priority`: Validates critical/high/normal/low derivation.
   - `test_api_tasks_endpoint_success`: Validates HTTP 200, JSON schema, and summary fields.
   - `test_structured_task_fields`: Asserts all 11 required fields on every task object.
   - `test_actor_categories_separation`: Asserts that all 4 actor categories are disjoint.
   - `test_api_tasks_filtering`: Validates query filtering by `product`, `state`, and `owner`.
   - `test_missing_tasks_file_graceful_handling`: Validates coverage gaps and fallback when source is missing.
   - `test_documented_agent_workflow`: Asserts presence and integrity of agent update workflow documentation.

2. `tests/test_tasks_ui.py` (12 tests):
   - `test_html_navigation_tabs`: Asserts `#overview`, `#tasks`, `#actors` anchors and badges.
   - `test_html_tasks_view_structure`: Asserts tasks overview, donut chart, and product bar chart containers.
   - `test_html_filter_controls`: Asserts search input, dropdowns (product, state, owner, priority), and reset button.
   - `test_html_kanban_board_columns`: Asserts all 5 Kanban column wrappers.
   - `test_html_modal_dialog`: Asserts modal structure, `<details>` wrapper, and copy button.
   - `test_html_actors_inventory`: Asserts 4 category containers.
   - `test_html_agent_workflow_documentation`: Asserts workflow protocol documentation.
   - `test_js_routing_and_api_integration`: Asserts JS functions for routing, charts, modal, and filtering.
   - `test_css_styling_rules`: Asserts CSS styles for nav, kanban, cards, modal, and badges.
   - `test_server_serves_html_with_tasks_elements`: Integration test checking live HTTP serving of HTML with tasks.
   - `test_server_serves_js`: Integration test checking live HTTP serving of `dashboard.js`.
   - `test_server_serves_css`: Integration test checking live HTTP serving of `dashboard.css`.

### 4.2 Full Test Suite Execution
```text
PYTHONPATH=src python3 -m unittest discover -s tests -v
...
Ran 69 tests in 1.762s
OK
```

### 4.3 Live HTTP Server Receipt
A background server instance was launched on localhost and queried with live requests:
```text
Testing live server on http://127.0.0.1:33987:
  /api/health   -> 200 (application/json; charset=utf-8) len=117    [Status: ok]
  /api/hourly   -> 200 (application/json; charset=utf-8) len=26848  [24-hour buckets verified]
  /api/usage    -> 200 (application/json; charset=utf-8) len=939    [Usage aggregates verified]
  /api/features -> 200 (application/json; charset=utf-8) len=533    [Accepted features verified]
  /api/tasks    -> 200 (application/json; charset=utf-8) len=436614 [148 tasks, 4 actor categories, 68.2% completion]
  /             -> 200 (text/html)                       len=22826  [#tasks and kanban-board present]
All live queries verified successfully.
```

### 4.4 Patch Applicability Verification
The unified patch was applied to a clean clone pinned at commit `249d086`:
```bash
git apply --check research/antigravity/recovery/dashboard-tasks-tracker-and-usability.patch
# Exit code: 0 (clean application)
```

---

## 5. Strict Invariants Compliance Audit

| Requirement | Audit Result | Evidence |
| :--- | :--- | :--- |
| **Strict Read-Only Canonical Repo** | **COMPLIANT** | Zero edits to `/home/alexey/git/agent-dashboard`. Working tree clean, HEAD at `249d086`. |
| **Zero cargo / rustc invocations** | **COMPLIANT** | Only Python standard library used. Zero Rust invocations. |
| **Zero raw secrets or tokens** | **COMPLIANT** | Verified via `publication_guard.py` (exit 0). Zero bearer tokens, API keys, or private URLs. |
| **Scratch Budget <= 512 MB** | **COMPLIANT** | Scratch root usage: **1.2 MB** (mode `0700`). Zero net `/tmp` growth. |
| **Memory Budget <= 1500 MB** | **COMPLIANT** | Test server and test suite executed with peak memory < 85 MB. |
| **Clean Unified Patch** | **COMPLIANT** | `research/antigravity/recovery/dashboard-tasks-tracker-and-usability.patch` (131 KB). |

---

## 6. Documented Agent Update Workflow

As exposed in the UI and `/api/tasks` response, autonomous agents interact with the tracker through the standard delivery protocol:
1. **Live Read-Only Visibility:** The dashboard preview provides an honest, zero-drift window into canonical files. No fake UI write actions or manual overrides exist.
2. **Atomic File Transitions:** Agents update their owned task entries directly in `coordination/TASKS.json` using serialized file locking (`flock on .local/git.lock`).
3. **First Action Receipt:** A transition from `ready` to `in_progress` requires an authenticated `aplexer whoami` execution record with worker PID, session ID, and owned paths ACK.
4. **Delivery & Review Gate:** A transition to `review` requires passing test receipts and checkpoint commits; transition to `done` requires independent peer reviewer sign-off.
5. **Blockers & Continuation:** Stalled tasks must explicitly record `blocked_on` dependencies and a durable continuation trigger.

---

## 7. Conclusion & Next Actions

The Tasks Tracker & Usability Analytics prototype is complete, fully tested, and cleanly packaged into:
- Patch: `research/antigravity/recovery/dashboard-tasks-tracker-and-usability.patch`
- Verification Report: `research/antigravity/recovery/REPORT-DASHBOARD-TASKS-USABILITY.md`

The deliverable is ready for handoff to `agent-dashboard-head` and Codex Principal C2426 for review and canonical branch integration.
