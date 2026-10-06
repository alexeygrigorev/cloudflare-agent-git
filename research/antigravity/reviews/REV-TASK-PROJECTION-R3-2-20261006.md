# Independent Technical Audit: Task `task-projection-r3-2` in `agent-quota-launcher`

**Date & Time**: 2026-10-06T00:47:00Z (02:47:00 Berlin)  
**Auditor / Reviewer**: `antigravity` (Independent Technical Auditor)  
**Parent Caller**: `ea14b401-20e9-4e48-ab08-d15be08da30d`  
**Target Repository**: `/home/alexey/git/agent-quota-launcher`  
**Audited Task**: `task-projection-r3-2` (`ql-core-3-projection-1`)  
**Target Artifacts**:
1. `/home/alexey/git/agent-quota-launcher/.local/first-action-task-projection-r3-2.json`
2. `/home/alexey/git/agent-quota-launcher/examples/dashboard-projection-schema.md`
3. `/home/alexey/git/agent-quota-launcher/.local/launcher-config/state.db`

**Verdict**: **ACCEPTED**

---

## 1. Executive Summary & Audit Matrix

This independent technical audit conducts an adversarial, rigorous evaluation of task `task-projection-r3-2` in `agent-quota-launcher`. The task specified two primary deliverables:
1. A strictly bounded first tool action receipt (`.local/first-action-task-projection-r3-2.json`) containing exactly four keys extracted from `aplexer whoami --json`.
2. A comprehensive dashboard projection contract (`examples/dashboard-projection-schema.md`) defining the newline-delimited JSONL format produced by `python3 -m launcher report --jsonl`.

Every acceptance criterion has been verified against raw files, git history (`b79ae70`, `c19c787`, `8af3684`), the SQLite task store, live CLI executions, and the test suite (`tests/test_report.py`).

| # | Acceptance Criterion | Required Specification | Measured Implementation & Evidence | Result |
|---|---|---|---|:---:|
| **1** | First Action Shape | Exactly 4 keys: `id`, `tag`, `workspace`, `timestamp`. No wrapper, engine, or excess keys. | Verified on disk: exactly `{id, tag, workspace, timestamp}` present; valid UTC ISO-8601 string. | **PASS** |
| **2** | Stream Shape & Line Distinction | Newline-delimited JSON objects; distinct bucket lines and coverage line; carries `project_id`. | Defined in § Stream shape; validated in `tests/test_report.py` and live CLI output. | **PASS** |
| **3** | Per-Line Fields | `bucket` (hourly label) and `tasks[]` (non-empty array with `id`, `state`, `reviewer`, `reason`, `usage`, `quota`). | Defined in § Bucket line: `bucket` and `tasks[]`. | **PASS** |
| **4** | Usage Object Policy | Null-unless-proven tokens; `source: "unproven"`; never zero-fabricated; no interpolation. | Defined in § Usage object & § Unknown rendering policy; enforced in `build_report()`. | **PASS** |
| **5** | Quota Object Isolation | Sibling object; never mixed with tokens or cost; normative disclaimer note. | Defined in § Quota object; separate `percent_delta`, `snapshots`, and `note`. | **PASS** |
| **6** | 24h Coverage Gaps & Timezone Policy | Explicit 24h gap enumeration; historical hours without tasks are gaps, not 0 activity; Europe/Berlin vs UTC evolution. | Originally implemented in Europe/Berlin (commit `b79ae70`), then matured via R1/R2 review to UTC `Z` half-open interval to resolve DST non-chronological sorting. | **PASS** (Matured) |
| **7** | Unknown-vs-Zero Policy | Complete mapping of unknowns to `null` or explicit badges, forbidding fake zeroes. | Summary matrix in § Unknown-vs-zero rendering policy. | **PASS** |
| **8** | Real CLI Example Lines | Includes real example lines from running `python3 -m launcher report --jsonl`. | Real bucket line and coverage line captured from live store in § Real example lines; replicated live. | **PASS** |
| **9** | Store State Integrity | Task transitioned to `completed-awaiting-review`, not self-accepted. Leases intact. | Confirmed in `.local/launcher-config/state.db`; reviewer `quota-launcher-core-3`; state `completed-awaiting-review`. | **PASS** |

---

## 2. Deep-Dive Criterion Verification

### 2.1 First Tool Action Receipt (`.local/first-action-task-projection-r3-2.json`)

**File Path**: `/home/alexey/git/agent-quota-launcher/.local/first-action-task-projection-r3-2.json`

**File Content**:
```json
{
  "id": "94452fdb-9ee1-496e-999d-f6ef69ee6926",
  "tag": "task-task-projection-r3-2",
  "workspace": "/home/alexey/git/agent-quota-launcher",
  "timestamp": "2026-10-04T12:33:11Z"
}
```

**Adversarial Checks**:
- **Key Whitelist**: Inspected with `set(json.load(...).keys())`. Returned exactly `{"id", "tag", "workspace", "timestamp"}`.
- **Engine Pollution Rejection**: No wrapper or aplexer internal session fields (`phase`, `worker_pid`, `cgroup`, `command`, `schema_version`, `parent_session`).
- **Identity & Correlation**:
  - `id`: Matches `session_id` `"94452fdb-9ee1-496e-999d-f6ef69ee6926"` in `.local/launch-task-projection-r3-2.json`.
  - `tag`: Matches `"task-task-projection-r3-2"`.
  - `workspace`: Matches `/home/alexey/git/agent-quota-launcher`.
  - `timestamp`: `"2026-10-04T12:33:11Z"` falls between `started_at` (`2026-10-04T12:31:51.232152+00:00`) and `first_action_validated_at` (`2026-10-04T12:33:13.127642+00:00`).

### 2.2 Deliverable Specification (`examples/dashboard-projection-schema.md`)

**File Path**: `/home/alexey/git/agent-quota-launcher/examples/dashboard-projection-schema.md`  
**Size**: 206 lines, 11,862 bytes.

#### A. Stream Shape and Attribution
- JSONL format: Exactly one valid JSON object per line, UTF-8, no outer array wrapper.
- Distinguishable line types: Bucket lines (`"bucket"` key present) vs Coverage line (`"coverage"` key present).
- Project attribution: Every line carries `"project_id"` (`string`, defaulting to repository root name or CLI argument `--project-id`).

#### B. Per-Line Bucket & Tasks Array
- `bucket`: Hourly label `%Y-%m-%dT%H:00:00Z` in UTC.
- `tasks[]`: Non-empty array of objects with schema:
  - `id` (`string`): Task ID.
  - `state` (`string`): Bounded lifecycle state (`queued`, `reserved`, `starting`, `running`, `completed-awaiting-review`, `accepted`, `failed`, `blocked`, `launch-uncertain`, `stalled`).
  - `reviewer` (`string | null`): Must render as "not yet" when null, never as empty reviewer.
  - `reason` (`string | null`): Rejection/failure reason or null.
  - `usage` (`object`): Mandatory usage metadata block.
  - `quota` (`object`): Mandatory quota metadata block.
- Attribution guarantees: Offset-aware timestamps are normalized to true UTC instants; malformed/missing timestamps are counted in `created_at_invalid` rather than fabricated into a fake bucket.

#### C. Usage Object & Quota Object Segregation
- `usage` object:
  ```json
  "usage": {
    "input_tokens": null,
    "output_tokens": null,
    "cached_tokens": null,
    "cost": null,
    "source": "unproven"
  }
  ```
  - Strictly normative: Token counts and costs are numeric **only** when natively proven. Otherwise `null`.
  - Zero-fabrication prohibited: `null` must render as unknown ("—"), never as `0`.
- `quota` object:
  ```json
  "quota": {
    "percent_delta": null,
    "snapshots": null,
    "note": "account percent delta is not token use or cost"
  }
  ```
  - Complete isolation from usage: Quota account percentages are never mixed into token counts or financial cost calculations.

#### D. The Europe/Berlin vs UTC Evolution Audit
- **Original Task Prompt**:
  `"...the coverage block with explicit 24h gaps in Europe/Berlin..."`
- **Initial Deliverable Analysis (Commit `b79ae70249d5c5e50b39ced9f9e858311dae5f06`)**:
  - The worker initially generated `examples/dashboard-projection-schema.md` using Europe/Berlin local time labels (`%Y-%m-%dT%H:00:00%z`, e.g. `2026-10-04T13:00:00+0200`) and `gaps_within_last_24h` in Berlin format, matching the CLI behavior at that exact commit.
- **Head Review Rounds R1 & R2 Refinement (Commits `c19c787` & `8af3684`)**:
  - During subsequent review rounds R1 (`QL-CORE-003 R1`) and R2 (`QL-CORE-003 R2`), a critical design defect in Berlin wall-clock labels was identified: during DST fall-back transitions (e.g., CEST to CET in late October), repeated wall-clock hours (`...T02:00:00+0200` vs `...T02:00:00+0100`) break lexicographical ordering, causing stream sorting desynchronization.
  - Furthermore, multi-host telemetry and dashboard federation required standard UTC ISO-8601 intervals `[as_of-24h, as_of)Z` with explicit tiling of the partial first hour and `created_at_invalid` tracking.
  - The schema documentation was updated synchronously with `launcher/cli.py` (`build_report()`).
- **Auditor Assessment**: The transition from Europe/Berlin wall time to UTC `Z` representations represents sound, rigorous engineering that eliminates DST ambiguity and respects the project-wide requirement for monotonic, deterministic telemetry while strictly fulfilling the requirement for explicit 24h gap enumeration (`gaps_within_window`).

#### E. Unknown-vs-Zero Rendering Matrix
The deliverable includes an explicit tabular policy dictating consumer behavior:
- `null` tokens/cost -> Render "unknown" / "—", never `0`.
- `source: "unproven"` -> Provenance badge "unproven".
- `percent_delta: null` -> Unknown headroom.
- `gaps_within_window` -> Explicit gap markers, not zero activity.
- `tasks_outside_window` -> Count badge; tasks omitted from stream.
- `created_at_invalid` -> Explicit count badge; never attributed to arbitrary hours.

### 2.3 Live Real Example Execution Verification

Section 9 of `examples/dashboard-projection-schema.md` contains real captured lines from running `python3 -m launcher report --jsonl`.

To verify live reproducibility, the command was executed directly during this audit:
```bash
python3 -m launcher --config-dir .local/launcher-config report --jsonl
```
Emitted output:
```json
{"project_id": "quota-launcher", "bucket": "2026-10-05T22:00:00Z", "tasks": [{"id": "coord-cross-host-audit-01", "state": "accepted", "reviewer": "reviewer-4e0af192-73e5", "reason": "head accepted reviewed artifacts", "usage": {"input_tokens": null, "output_tokens": null, "cached_tokens": null, "cost": null, "source": "unproven"}, "quota": {"percent_delta": null, "snapshots": null, "note": "account percent delta is not token use or cost"}}, ...]}
{"project_id": "quota-launcher", "coverage": {"window_hours": 24, "window_start": "2026-10-05T00:46:32Z", "window_end": "2026-10-06T00:46:32Z", "window_half_open": "[window_start, window_end)", "first_bucket": "2026-10-05T10:00:00Z", "last_bucket": "2026-10-05T23:00:00Z", "gaps_within_window": ["2026-10-05T01:00:00Z", ...], "tasks_outside_window": 2, "created_at_invalid": 0, "note": "historical hours without tasks are gaps, not simulated activity; tasks outside the window and tasks with malformed timestamps are counted, not emitted or attributed"}}
```

The live stream precisely matches the contract defined in `examples/dashboard-projection-schema.md`.

### 2.4 Test Suite Verification (`tests/test_report.py`)

Execution of `pytest tests/test_report.py`:
- Collected: 12 items.
- Result: **12 passed in 2.31s** (100% pass rate).
- Key contract tests verified:
  - `test_usage_null_and_quota_separate`: PASS
  - `test_utc_z_window_is_half_open_24h`: PASS
  - `test_default_project_id_is_quota_launcher`: PASS
  - `test_exact_24_buckets_on_hour_boundary`: PASS
  - `test_offset_timestamps_converted_not_relabelled`: PASS
  - `test_dst_offset_timestamp_lands_on_utc_instant`: PASS
  - `test_malformed_created_at_is_invalid_not_outside`: PASS
  - `test_task_outside_window_counted_not_emitted`: PASS
  - `test_first_partial_hour_task_placed_in_first_bucket_not_outside`: PASS
  - `test_task_before_window_start_counted_outside_window`: PASS
  - `test_jsonl_lines_carry_project_id_and_coverage_last`: PASS
  - `test_accept_on_queued_via_store_guard`: PASS

### 2.5 Task Database Record & Lifecycle Audit

Inspection of `/home/alexey/git/agent-quota-launcher/.local/launcher-config/state.db`:
- **Task Row**:
  - `id`: `"task-projection-r3-2"`
  - `idempotency_key`: `"ql-core-3-projection-1"`
  - `state`: `"completed-awaiting-review"`
  - `reviewer`: `"quota-launcher-core-3"`
  - `reason`: `"head marked complete; native death confirmed"`
  - `created_at`: `"2026-10-04 12:31:22"`
  - `updated_at`: `"2026-10-04 12:45:21"`
- **Path Leases**:
  - `/home/alexey/git/agent-quota-launcher/examples/dashboard-projection-schema.md`
  - `/home/alexey/git/agent-quota-launcher/.local/first-action-task-projection-r3-2.json`
- **Integrity**: Task lifecycle respects the peer review gate. The task was neither self-accepted by the worker nor prematurely finalized by the head.

---

## 3. Findings & Notes

1. **Strict First Action Compliance**: The JSON file `.local/first-action-task-projection-r3-2.json` contains strictly the 4 requested keys.
2. **Defensive Schema Design**: The schema contract in `examples/dashboard-projection-schema.md` rigorously enforces "unknown stays unknown" and forbids zero-backfilling.
3. **Sound Timezone Refinement**: The transition from Europe/Berlin wall-clock formatting to UTC `Z` representation resolved real ambiguities around DST autumn clock adjustments while preserving explicit gap enumeration.

---

## 4. Final Verdict

**FINAL VERDICT: ACCEPTED**

All acceptance criteria are satisfied. The deliverables are verified, fully documented, covered by passing regression tests, and properly recorded in the state database awaiting independent acceptance.
