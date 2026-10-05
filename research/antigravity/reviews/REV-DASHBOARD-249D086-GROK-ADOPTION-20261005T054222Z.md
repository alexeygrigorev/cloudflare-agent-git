# Independent technical audit: Agent Dashboard canonical adoption commit `249d086`

- **Target commit:** `249d086a007ee3d5d0381334a27d56771b959d11`
- **Parent:** `efed70d5b1dd5d67f9a28e1d4225d3f7fa1bfdee`
- **Repository:** `/home/alexey/git/agent-dashboard` (`main`, working tree clean at inspection)
- **Audit timestamp (UTC):** `2026-10-05T05:45:31Z` environment capture; report written `2026-10-05T05:48:00Z`
- **Task ID:** `t-dashboard-grok-20261005T054222Z-2668db`
- **Governing directives:** Codex Principal Directives C2347, C2349, C2350, C2351, C2353, C2355, C2357, C2359, C2360, C2361; four-product operating contract in `coordination/OPERATING-MODEL.md`; AD-B2 provenance rules as recorded on `ad-b2-unattributed-provenance`
- **Reviewer execution environment / model identity as invoked:**
  - Invoked model: Grok 4.6 (xAI Grok Build)
  - Host: Linux 6.8.0-138-generic, Python 3.12.3
  - Native aplexer `whoami` at review start: `id=46fdb644-9b58-4e2f-aab3-9be5e1e33337`, `tag=antigravity-head`, `workspace=/home/alexey/git/cloudflare-agent-git`, `reported_state=working`
  - Identity note: the bound aplexer session tag is `antigravity-head`; this document is a Grok-authored independent audit of that session’s assigned review task. Session tag is routing provenance, not a claim that Antigravity authored the verdict.
- **Access mode:** read-only on `/home/alexey/git/agent-dashboard` (no edits, no `git` writes). Write is this review file under `research/antigravity/reviews/`.
- **Related payload pin:** `/home/alexey/git/agent-dashboard/.local/exports/oct5-hourly-24h-20261005T04Z.json` (`report.pin` = `249d086a007ee3d5d0381334a27d56771b959d11`, `as_of` = `2026-10-05T04:45:31.753369+00:00`)
- **Verdict:** **BOUNDED ACCEPTANCE**

---

## Section 1: Executive Summary & Verdict

**Verdict: BOUNDED ACCEPTANCE.**

The verdict is based on this review’s own measurements. It does not inherit the earlier `REV-DASHBOARD-249D086-ADOPTION.md` “FULL ADOPTION ACCEPTANCE” label. Card presence and a green unit suite establish a schema pin. They do not establish fourth-product utilization coverage.

Observed support for acceptance of the commit as a canonical pin:

1. HEAD of `/home/alexey/git/agent-dashboard` is exactly `249d086a007ee3d5d0381334a27d56771b959d11`. `git status --porcelain` was empty.
2. Independent unittest run: **48 tests, 0 failures, 0 errors, 0 skipped, 0.093s, OK**.
3. `CANONICAL_PROJECT_IDS` includes `agent-coordination`. `PROJECT_ALIASES` maps `agent_coordination` → `agent-coordination` and `agent-quota-launcher` / `agent_quota_launcher` → `quota-launcher`. Unknown ids map to `unattributed`.
4. `static/index.html` has a dedicated `#agent-coordination` card. `static/dashboard.js` `PROJECT_IDS` includes `"agent-coordination"`.
5. Server implements `GET /api/health`, `/api/hourly`, `/api/usage`, `/api/features` with `as_of` on the three metric endpoints.
6. Queued task `ad-b2-unattributed-provenance` states the correct epistemic rule: unattributed shrinks only through source-proven canonical mappings; unknown stays explicit.

Bounds that keep this from a full ACCEPT:

1. **Live cohort at the 04Z payload:** `agent-coordination` = 1 unique agent / 5.8817 h / coverage 0.245071. `unattributed` = 317 unique agents / 5276.0583 h / coverage 1.0. Canonical products together are 22 agents / 207.3016 h. The unlabeled bucket dominates the window.
2. **Observation labels:** at audit time, `observation-state.json` held 486 agent records, all with empty `project_id`. Labeling is entirely `team_id`. Canonical map of `(project_id or team_id)`: unattributed 464, agent-branches 11, agent-dashboard 8, quota-launcher 2, agent-coordination 1. Fourth-product hours in the dashboard are the single `team_id=agent-coordination` record. Larger teams that do fourth-product work (`a16-runtime-protocol` 229 records, plus `unregistered` 113) remain unattributed. That is fail-closed and correct; it is also incomplete coverage.
3. **Hourly UI hides the dominant cohort.** `PROJECT_IDS` is four canonical ids. `/api/hourly` emits a fifth `projects.unattributed` object when any non-canonical span is seen. The HTML grid has no card for it. Each canonical card’s “Unattributed hours” field is per-project missing-`agent_id` time (0.0 on the 04Z payload), with a fallback to a global rollup that this payload does not set at the top level. Operators can read a 4-card dashboard and miss 317 agents / 5276.1 h.
4. **Engine alignment gap.** Hourly maps `span.project_id or span.team_id`. Usage `normalize_usage_record` reads only `project_id`. OpenCode `by_team` records therefore land in `unattributed` even when `team_id` is a canonical product id. Features require exact `ACCEPTED` plus `accepted_at` plus commit/PR plus tests. All 14 `project_id=agent-coordination` TASKS.json rows have `accepted_at: null`; none have `status: ACCEPTED`. `/api/features` will omit fourth-product completions under this ledger.
5. **Client `as_of` is hourly-only.** `loadAll` appends `?as_of=` to `/api/hourly` and calls `/api/usage` and `/api/features` without the parameter. Server supports `as_of` on all three. A chosen cutoff is not a coherent three-surface window.
6. **Test pin is backend-heavy.** Hourly and accounting tests cover aliases and a synthetic fourth-product row. `tests/test_features.py` has no `agent-coordination` case. `test_html_root_endpoint` asserts the page title and forbids `"Status: Operational"`; it does not assert `#agent-coordination` or `PROJECT_IDS`.
7. **`ad-b2-unattributed-provenance` is queued, not started.** `first_action` is null, `executor_ids` is empty, `commit`/`tests`/`reviewer`/`accepted_at` are null. The 04Z unattributed bucket is still intact.

Challenge to the prior adoption review: treating HTML card presence plus 48 passing tests as “full adoption” overstates operational fourth-product coverage. The honest consumer statement at this pin is: the dashboard can *name* Cross-computer Agent Coordination and will *count* spans already labeled `agent-coordination` / `agent_coordination`; most observed hours remain in an explicit unattributed bucket that the hourly UI does not surface.

---

## Section 2: Unit Test Verification & Observed Counts

Command actually run from this review:

```bash
PYTHONPATH=/home/alexey/git/agent-dashboard/src python3 -m unittest discover -s /home/alexey/git/agent-dashboard/tests/ -v
```

**Observed summary (this run, not copied from the commit message or prior reviews):**

| Metric | Observed value |
| :--- | :--- |
| Result | `OK` |
| Tests run | 48 |
| Failures | 0 |
| Errors | 0 |
| Skipped | 0 (no skip lines in verbose output) |
| Elapsed | **0.093s** |
| Exit code | 0 |

Commit message claims “Tests: 48 passed”. A prior adoption review reported 48/48 in 0.600s. This run’s wall time is 0.093s on the same suite. Counts match; elapsed time is this host’s measurement.

Verbose outcomes, all `ok`:

**`test_accounting.TestUsageAccounting` (13)**

- `test_24h_usage_filter`
- `test_boolean_and_negative_counts_invalid`
- `test_canonical_project_id_aliases_and_fourth_product`
- `test_deduplication_by_response_id`
- `test_known_zero_preserved`
- `test_missing_response_id_does_not_dedup_on_timestamp`
- `test_noncanonical_project_unattributed`
- `test_nullability_and_types`
- `test_opencode_adapter_reasoning_not_folded`
- `test_quota_not_converted_to_cost_or_tokens`
- `test_reasoning_token_subset_isolation`
- `test_unknown_cache_and_reasoning_stay_null`
- `test_usage_accounting_alias_and_coordination_routing`

**`test_features.TestFeaturesTracking` (6)**

- `test_24h_completed_feature_filter`
- `test_feature_extraction_and_deduplication`
- `test_missing_commit_or_tests_rejected`
- `test_missing_tasks_file_unknown`
- `test_unaccepted_substring_not_counted`
- `test_updated_at_is_not_accepted_at`

**`test_hourly.TestHourlyUtilization` (20)**

- `test_agent_across_three_adjacent_buckets`
- `test_bucket_generation`
- `test_canonical_project_id_aliases_and_fourth_product`
- `test_duplicate_identical_spans_do_not_change_hours`
- `test_ended_before_started_invalid_spans`
- `test_future_ended_at_clamped_to_as_of`
- `test_hourly_utilization_aliases_and_fourth_product`
- `test_identity_deduplication`
- `test_invalid_ended_at_unknown_ended_not_alive`
- `test_missing_agent_id_unattributed_hours`
- `test_missing_spans_unknown_not_zeros`
- `test_non_hour_as_of_exact_window`
- `test_noncanonical_project_goes_to_unattributed`
- `test_overlapping_spans_union_once`
- `test_partial_hour_calculation`
- `test_registry_shape_rejects_members`
- `test_shared_agent_ids_non_additive`
- `test_single_agent_clipping`
- `test_span_entirely_outside_window`
- `test_union_seconds_helper`

**`test_server.TestDashboardServer` (9)**

- `test_features_endpoint`
- `test_health_endpoint`
- `test_hourly_endpoint`
- `test_hourly_honors_as_of`
- `test_hourly_invalid_as_of`
- `test_html_root_endpoint`
- `test_missing_source_coverage_gap`
- `test_static_css_if_present`
- `test_usage_endpoint`

Suite composition vs fourth-product claims:

- Hourly `test_missing_spans_unknown_not_zeros` asserts `agent-coordination` among the four keys with `coverage=None` / `unknown=True` on missing input (unknown stays explicit).
- Hourly `test_hourly_utilization_aliases_and_fourth_product` and accounting `test_usage_accounting_alias_and_coordination_routing` prove synthetic labeled rows route into `agent-coordination`.
- Features suite never names `agent-coordination`.
- Server HTML test never names `agent-coordination`.
- `test_opencode_adapter_reasoning_not_folded` proves `by_team: a16-runtime-protocol` aggregates under `unattributed`. That is the intended fail-closed path; it also documents that usage will not recover fourth-product hours from team labels alone.

This suite validates algorithms and aliases. It does not validate live observation labeling, UI rendering of the unattributed cohort, or client `as_of` fan-out.

---

## Section 3: Fourth-Product Integration Audit

### 3.1 Canonical schema

`src/dashboard/__init__.py` at this commit (SHA256 `15a53aa140fb74ebc3fa6e045b476f5ab4f25f3443c837792615455f89c436c7`):

```python
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
```

`canonical_project_id` returns an alias, a canonical id, or `unattributed`. Empty string and `None` become `unattributed`. That fail-closed default is the right default for AD-B2.

Stale docstring in `compute_hourly_utilization`: “across the three canonical projects.” Implementation iterates `CANONICAL_PROJECT_IDS` (four). Documentation drift only; still a signal that the fourth product was grafted onto a three-product design.

### 3.2 Server endpoints

`DashboardRequestHandler.do_GET` routes:

| Path | Handler | Fourth-product behavior |
| :--- | :--- | :--- |
| `/api/health` | liveness JSON: `status`, `service=agent-dashboard`, `static_index_readable`, `metrics_dir_readable` | No project list, no cohort, no coverage. Useful as process health, silent on fourth-product data. |
| `/api/hourly` | `_load_hourly_payload` + `compute_hourly_utilization` | Always emits the four canonical keys. Emits `unattributed` when any non-canonical span was seen. Registry is labeled `static-registration` and `used_for_hours=false`. |
| `/api/usage` | `_load_usage_payload` + `aggregate_project_usage` | Emits only projects that have kept records. Empty/missing input returns `unknown=true` and `projects={}`. Canonical keys are not pre-seeded. |
| `/api/features` | `_load_features_payload` + `load_accepted_features` | Groups exact-`ACCEPTED` tasks with `accepted_at` in `[as_of-24h, as_of)`. Canonical keys are not pre-seeded. |

`as_of` parsing: missing/blank → server UTC now; invalid → HTTP 400 `{error: invalid as_of}`. Confirmed by `test_hourly_honors_as_of` and `test_hourly_invalid_as_of`. Usage and features handlers share `_parse_as_of`. Client does not send it to those two.

Static serving: `/` and `/index.html` from `static/`, CSS/JS under the static root with realpath confinement. Fallback HTML lists the four JSON APIs and states that coverage/unknown live in JSON.

### 3.3 HTML card

`static/index.html` section `#agent-coordination`:

- Title: “Cross-computer Agent Coordination”
- Subcode: `agent-coordination`
- Unknown badge `#unknown-agent-coordination`
- Metrics: unique agents, total agent-hours, coverage, unattributed hours
- Chart host `#chart-agent-coordination`
- Same structure as the other three cards

Card markup is complete for the canonical id. Completeness of markup is not completeness of coverage.

### 3.4 Client JS `PROJECT_IDS`

```javascript
var PROJECT_IDS = ["agent-branches", "agent-dashboard", "quota-launcher", "agent-coordination"];
```

`renderHourly` iterates only this list. Missing project objects flip the unknown badge and render `n/a` / `unknown` / empty chart. Null numeric fields render as `n/a` or `unknown`, never coerced to 0. That rendering policy is sound.

`renderUsage` / `renderFeatures` iterate `Object.keys(data.projects)` after unwrap. They can show `unattributed` and `agent-coordination` when the API includes them. The hourly grid cannot.

`loadAll` URL construction:

- hourly: `/api/hourly` + optional `?as_of=`
- usage: `/api/usage`
- features: `/api/features`
- health: `/api/health`

A user-selected cutoff therefore binds hourly and leaves usage/features on server now. Schema alignment across the four endpoints is incomplete at the client.

### 3.5 Live 04Z payload vs current observation labels

Pinned export `oct5-hourly-24h-20261005T04Z.json` (`hourly_source_kind=observed-history`, `unknown=false`, `coverage_gaps=[]`, `shared_agent_ids=[]`):

| Project | unique_agents | total_agent_hours | coverage | unknown | unattributed_agent_hours |
| :--- | ---: | ---: | ---: | :--- | ---: |
| agent-branches | 11 | 85.4776 | 0.657336 | false | 0.0 |
| agent-dashboard | 8 | 100.1365 | 0.718626 | false | 0.0 |
| quota-launcher | 2 | 15.8058 | 0.657552 | false | 0.0 |
| **agent-coordination** | **1** | **5.8817** | **0.245071** | **false** | **0.0** |
| unattributed | 317 | 5276.0583 | 1.0 | false | 0.0 |

Fourth-product nonzero buckets in that window: seven consecutive hours from `2026-10-04T12:45:31Z` with a single active agent (partial first/last buckets 0.7813 h and 0.1004 h). Coverage 0.245071 = 5.8817 / 24 within rounding. One labeled agent filled ~24.5% of wall-clock; the rest of the fourth-product card is known-zero buckets, not unknown.

`coverage_gaps=[]` means source files were readable. It does not mean labels were canonical. Unattributed is a first-class known project (`unknown=false`), so the empty gap list is consistent and easy to misread as “full coverage.”

Current `observation-state.json` (486 records; **no session identifiers copied here**):

| team_id | record count |
| :--- | ---: |
| a16-runtime-protocol | 229 |
| unregistered | 113 |
| publication | 36 |
| independent-review | 31 |
| oversight | 31 |
| a01-harness | 11 |
| agent-branches | 11 |
| agent-dashboard | 8 |
| a06-a10 | 5 |
| a05 | 4 |
| product-integration | 4 |
| quota-launcher | 2 |
| agent-coordination | 1 |

`project_id` is empty on every record. Hourly therefore keys on `team_id`. Teams whose id equals a canonical product id are counted on that product. `a16-runtime-protocol` is the agent-coordination *team* in `TEAM-REGISTRY.json` (`project_id: agent-coordination` on that team object) and still maps to `unattributed` because the string `a16-runtime-protocol` is not in `CANONICAL_PROJECT_IDS` or `PROJECT_ALIASES`. Mapping the whole team string onto `agent-coordination` without per-span proof would mix other products’ work into the fourth-product card. That is exactly the remap AD-B2 is forbidden to invent.

### 3.6 Features ledger for the fourth product

`coordination/TASKS.json` at audit: 133 tasks, 14 with `project_id=agent-coordination`. Exact `status` or `acceptance_status` equal to `ACCEPTED` (strip/upper) exists on 12 tasks globally. Every coordination task inspected has `accepted_at: null`. Several have prose `acceptance_status` containing the substring “ACCEPTED” or “BOUNDED ACCEPTANCE”; `_exact_accepted` correctly rejects those. Result: the features engine will not emit a fourth-product group from the current ledger. Empty features for `agent-coordination` is missing evidence, not zero features.

### 3.7 Integration verdict for section 3

Fourth-product *wiring* at commit `249d086` is real: canonical id, alias, hourly always-key, usage/features routing when `project_id` is already canonical, HTML card, JS id list, synthetic tests.

Fourth-product *coverage* at the pinned 04Z consumer payload is one labeled agent and 5.8817 h, with 317 agents / 5276.0583 h sitting in `unattributed` and omitted from the hourly cards. Cohorts, gaps, and unknowns:

- **Covered:** spans whose `project_id` or `team_id` is already `agent-coordination` / `agent_coordination`.
- **Cohort leak:** observation uses team names (`a16-runtime-protocol`, `unregistered`, `publication`, `oversight`, …) that fail closed into `unattributed`.
- **Gap:** usage ignores `team_id`; features require fields the coordination tasks do not have; client `as_of` is hourly-only; unattributed project has no hourly card.
- **Unknowns kept explicit:** missing spans → `unknown=true` and null hours; null tokens → `n/a`; invalid `ended_at` → `unknown_ended`; registry not used for hours.

---

## Section 4: Provenance Backlog Audit (`ad-b2-unattributed-provenance`)

Record in `/home/alexey/git/cloudflare-agent-git/coordination/TASKS.json`:

| Field | Value |
| :--- | :--- |
| id | `ad-b2-unattributed-provenance` |
| project_id / team_id | `agent-dashboard` |
| owner_tag | `agent-dashboard-head` |
| status | `queued` |
| updated_at | `2026-10-05T04:48:10.880414+00:00` |
| executor_ids | `[]` |
| first_action | `null` |
| commit / pr_url / tests / reviewer / accepted_at / feature_id | `null` |
| blocked_on | `worker capacity after wind-down of AD-B1/F1/R1 sessions` |
| evidence_paths | `/home/alexey/git/agent-dashboard/.local/exports/oct5-hourly-24h-20261005T04Z.json` |
| owned_paths | dashboard `src/dashboard/` and `tests/` |

**Acceptance text (verbatim):** “Unattributed shrinks only via source-proven canonical mappings; every remap has provenance evidence; unknown stays explicit; full suite green; AD-R3 verdict”

**Next action (verbatim):** “Delegate provenance/attribution pass over the explicit unattributed bucket (317 agents / 5276.1h at 2026-10-05T04Z payload): map non-canonical project_ids to canonical or proven sources via owned executor; then AD-R3 independent review of the repair pin”

### 4.1 Epistemic rules vs the 04Z bucket

The numeric claim 317 / 5276.1 h matches the export: `unique_agents=317`, `total_agent_hours=5276.0583`. The task points at a real artifact pinned to `249d086`. No synthetic deletion of that bucket has occurred in the canonical dashboard code: non-canonical ids still become `unattributed`, and the 04Z object still contains the fifth project.

The acceptance rule is the right rule. Observation-state has **zero** `project_id` values. A bulk alias `a16-runtime-protocol` → `agent-coordination` would move 229 records in a later snapshot, including work that TEAM-REGISTRY also associates with other products. Proven mappings have to be per-agent or per-span (workspace, owned_paths, task_id, conversation/project field) with retained evidence. Team-string collapse is not provenance.

`unattributed_agent_hours=0.0` on the unattributed project itself: those 317 identities have `agent_id`s. The hours are unlabeled by canonical *project*, not missing identity. AD-B2 is a project-label problem. Treating it as missing-agent-id cleanup would leave the 5276 h untouched.

### 4.2 Unknowns remain explicit in current code

- Missing/empty spans → project `unknown=true`, hours/coverage null (tested).
- Non-canonical id → `unattributed` project, not dropped (tested).
- Invalid `ended_at` → `unknown_ended`, span excluded from live hours (tested).
- Unknown cache/reasoning → null, not 0 (tested).
- Features missing `accepted_at` / commit / tests → rejected and counted in `coverage_gaps` when status was exact ACCEPTED.
- Empty usage records → `unknown=true`, `projects={}`.

No code path in this commit deletes the unattributed bucket or fills canonical cards from TEAM-REGISTRY membership. Registry `used_for_hours=false` is labeled in `/api/hourly` sources.

### 4.3 Task-state honesty

The task is queued with no first action and no executor. `dashboard-canonical-integration-readiness` is `done` and names this task as `next_action`. That sequencing is consistent: adoption of the 4-id schema is separate from shrinking unattributed. Claiming AD-B2 complete at `249d086` would be false. Leaving the bucket visible in JSON while the hourly UI omits it is the remaining consumer defect AD-B2 / a follow-on UI task should address without fabricating remaps.

### 4.4 Provenance section verdict

**Rules: ACCEPT.** **Execution: not started.** **Data: unattributed remains 317 / 5276.0583 h at the cited 04Z pin.** No synthetic shrinkage observed.

---

## Section 5: Epistemic Invariants & Boundaries

### 5.1 Compiler hold

This review invoked no `cargo`, `rustc`, or C/C++ compiler. A process snapshot at `2026-10-05T05:45:31Z` showed **0** `cargo`/`rustc` processes host-wide. Dashboard tests used `python3 -m unittest` only.

### 5.2 Secrets / tokens

`git show 249d086a007ee3d5d0381334a27d56771b959d11` diff: 168236 bytes, 3966 lines. Pattern scan for `sk-…`, `api_key=`, `AKIA…`, `ghp_…`, `xai-…`, `Bearer …`, PEM private keys, `CLOUDFLARE_*` assignments: **no hits**. This report copies no credentials, proxy URLs, private mailbox bodies, or session UUIDs from metrics. TEAM-REGISTRY / TASKS.json identifiers used above are already in the public coordination tree.

### 5.3 Git / workspace boundary

- Target repo HEAD = target SHA; working tree clean.
- No writes under `/home/alexey/git/agent-dashboard`.
- Deliverable path is this file under `research/antigravity/reviews/`.
- File hashes at HEAD for the audited surfaces:

| File | SHA256 |
| :--- | :--- |
| `src/dashboard/__init__.py` | `15a53aa140fb74ebc3fa6e045b476f5ab4f25f3443c837792615455f89c436c7` |
| `src/dashboard/server.py` | `5576dbae9bbab3c1016156d3c2c24da475bf1013c006ea91d9960b8c4cbd25a6` |
| `src/dashboard/hourly.py` | `f80f591d5f593ff6bd2576017247da3615245e779f7ac640b5894dfb3cfabefb` |
| `src/dashboard/accounting.py` | `485d883127425d9d3d22bba7355e178bcffe3e2bb9e93f8735c48400ef6b9ff5` |
| `src/dashboard/features.py` | `b41f8026030f3c615d56d35065d4a1c9ad4757bcc630b8c9d9cdf2c6a9ffa49e` |
| `static/index.html` | `3938fc8eaa1c294aa71660dccc33450a0e6af6cf999f29bb865943412232eb82` |
| `static/dashboard.js` | `de35342571b4eda64150af797aa48a5115a2cc4900f44cce7ebb56a6b6013b21` |

### 5.4 What this review did not do

- No browser click-through of the live dashboard UI (no running server was started for this audit). HTML/JS were read as source; HTTP behavior was taken from unit tests plus code inspection.
- No remap of unattributed hours.
- No mutation of TASKS.json or TEAM-REGISTRY.json.
- No Cloudflare deploy, no new paid service, no quota bypass.

### 5.5 Recommended next owned work (not performed here)

Owner: `agent-dashboard-head` via `ad-b2-unattributed-provenance`, then independent AD-R3.

1. Keep the unattributed JSON object; add an hourly UI card or equivalent explicit rollup for `unattributed` so 317 / 5276.1 h cannot vanish behind four product cards.
2. Pass the same `as_of` to `/api/usage` and `/api/features`.
3. Provenance pass: map individual observation records using evidence (workspace, task, registry agent row), one mapping at a time, with a recorded source. Leave `a16-runtime-protocol` / `unregistered` / `oversight` in unattributed until that evidence exists.
4. Decide whether usage should consult `team_id` only when it is already a canonical id or alias — still fail closed for team names that are not products.
5. Pin HTML `#agent-coordination` and the unattributed surface in `test_server.py`.
6. Features: either populate `accepted_at` + exact `ACCEPTED` + commit/tests on genuine completions, or keep the empty group and document it as missing evidence.

---

## Verdict recap

**BOUNDED ACCEPTANCE** of commit `249d086a007ee3d5d0381334a27d56771b959d11` as the canonical four-product schema/UI/test pin.

- Tests observed: **48 passed, 0 failed, 0 errors, 0.093s**.
- Fourth-product card and APIs exist; live labeled coverage is 1 agent / 5.8817 h against 317 / 5276.0583 h unattributed at the 04Z pin.
- `ad-b2-unattributed-provenance` rules are sound and the task is still queued with no first action.
- Zero compiler invocations by this review; zero secret hits in the commit diff.

Independent reviewer: Grok 4.6, task `t-dashboard-grok-20261005T054222Z-2668db`.
