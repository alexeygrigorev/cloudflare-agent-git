# Candidate Engineering Report: Supervision Routing Repair (C1629 / C1630)

- **Worker:** supervision-routing-worker (launched by `antigravity-head` under Codex Principal C1629/C1630 directives)
- **Date:** 2026-10-04
- **Workspace:** `/home/alexey/git/cloudflare-agent-git`
- **Scratch Directory:** `/home/alexey/git/cloudflare-agent-git/.local/scratch/supervision-routing/` (mode 0700, strictly <= 512 MB, zero net `/tmp` growth)
- **Target Files:**
  - `research/antigravity/tooling/supervision/service_candidate.py`
  - `tests/test_supervision_routing.py`
  - `research/antigravity/recovery/REPORT-SUPERVISION-ROUTING-REPAIR.md`
- **Status:** **COMPLETE & VERIFIED (ALL TESTS PASS)**

---

## 1. Defect Analysis & Epistemic Boundary

### 1.1 Root Cause in `scripts/supervision/service.py`
Inspection of the canonical `scripts/supervision/service.py` revealed a critical architectural omission in entity extraction and task selection:

1. **Extraction Omission (Line 425):**
   ```python
   registry_full = json.loads((ROOT / 'coordination/TEAM-REGISTRY.json').read_text())
   teams = registry_full if isinstance(registry_full, list) else registry_full.get('teams', [])
   ```
   `service.py` only parsed `teams` from `TEAM-REGISTRY.json`. However, following the 4 October 2026 delivery reset, the active products are recorded under `projects`:
   - `agent-branches`
   - `agent-dashboard`
   - `quota-launcher`
   - `agent-coordination`
   
   None of these active products are members of the legacy research `teams` array in `TEAM-REGISTRY.json`.

2. **Matching Failure (Line 522):**
   ```python
   selected = [t for t in active if any(tag in team.get('principal_tags', []) and team['id'] == t.get('team_id') for team in teams)]
   ```
   Because `teams` only contained legacy research lanes (`a06-a10`, `a01-harness`, `a16-runtime-protocol`, `oversight`, etc.), tasks assigned to the 4 active products (such as `launcher-quota-resource-gates`, `launcher-native-lifecycle`, `coord-native-ssh-mvp`, `ad-b1-backend-repair`, `dashboard-hourly24h`) were **completely excluded** from principal task selection!

3. **Identifier & Alias Discrepancies:**
   Tasks in `coordination/TASKS.json` frequently specify:
   - `project_id` without matching `team_id` (e.g. `project_id: "agent-dashboard"`).
   - Project aliases such as `project_id: "agent-quota-launcher"` vs the canonical project identifier `id: "quota-launcher"`.
   The legacy check strictly required `team['id'] == t.get('team_id')`, causing valid product tasks to be ignored.

4. **Principal Oversight Mandate (C1444 / Human Steering 26, 31, 32):**
   Under the authoritative operating model, `codex-principal` is responsible for active operational oversight and monitoring across all four product teams, while `claude-principal` is excluded or quiet. By omitting product entities and project tasks, the watchdog was unable to send prompt envelopes alerting the monitoring principal to pending product tasks or recent completions.

---

## 2. Candidate Implementation Architecture

The candidate service is implemented in `research/antigravity/tooling/supervision/service_candidate.py`.

### 2.1 Unified Supervision Entity Extraction & Disambiguation
Function `extract_supervision_entities(registry_full)` extracts and normalizes both legacy `teams` and product `projects`:
- **ID Normalization:** Extracts `id` and `name`.
- **Truthful Principal Mapping (C1634: No Invented Fallback):**
  ```python
  principal_tags = project.get('principal_tags')
  if not principal_tags:
      owner = project.get('principal_owner')
      if isinstance(owner, dict) and owner.get('tag'):
          principal_tags = [owner['tag']]
      elif isinstance(owner, str) and owner.strip():
          principal_tags = [owner.strip()]
      elif isinstance(project.get('assignment_ack', {}).get('principal_owner'), dict):
          ack_owner = project['assignment_ack']['principal_owner'].get('tag')
          principal_tags = [ack_owner] if ack_owner else []
      else:
          principal_tags = []
  ```
  If no principal owner is registered, `principal_tags` remains strictly empty (`[]`) and the entity is marked `'unowned': True`. Projects are **never** silently defaulted to `codex-principal`.
- **Conflict Detection & Disambiguation:** Tracks seen normalized entity IDs across teams and projects. If a team and project share the same ID with conflicting `head_tag`, `workspace`, or `principal_tags`, a conflict is explicitly detected and recorded in `entity['conflict']` without silent overwriting.
- **Deterministic Alias Ordering:** Aliases are deterministically sorted (`sorted(aliases)`).

### 2.2 Robust Task Matching
Function `task_matches_entity(t, entity)` enforces:
```python
t.get('team_id') == entity['id'] or \
t.get('project_id') == entity['id'] or \
normalize_project_id(t.get('team_id')) == entity['id'] or \
normalize_project_id(t.get('project_id')) == entity['id']
```
It additionally checks normalized entity IDs and registered entity aliases, ensuring full symmetric resolution regardless of whether a task specifies `team_id`, `project_id`, or a variant alias.

### 2.3 Deterministic Head Completion & Queue Subscriptions
In `task_event(tasks)`:
- Active tasks (`status not in ('completed', 'done', 'cancelled', 'rejected', 'parked', 'on_hold')`) are tracked and categorized into:
  - Ready queue (`status in ('ready', 'queued')`).
  - Running queue (`status in ('running', 'in_progress', 'working')`).
- Recent completions (`status in ('completed', 'done')`) are captured, stably sorted by timestamp, and included in the event digest payload.
- **Deterministic Digest:**
  ```python
  digest_payload = {
      'active': active_meaningful,
      'completed': completed_meaningful,
  }
  digest = hashlib.sha256(json.dumps(digest_payload, sort_keys=True).encode()).hexdigest()[:20]
  ```
  This guarantees that completion transitions alter the revision digest deterministically, while remaining invariant to timestamp-only changes on running tasks.
- **Return Type:** Returns `TaskEventResult(tuple)`, preserving 100% backward compatibility with `active, digest, counts = task_event(tasks)` while exposing `.completed`, `.ready`, and `.running` attributes.

### 2.4 Structured Supervision Envelope Formatting & Epistemic Demarcation
Function `format_supervision_body(...)` structures task summaries clearly by project/team:
```
SUPERVISION-{event_key}: User requests autonomous useful execution and clear roles. ... Tasks: [quota-launcher] launcher-quota-resource-gates (queued, quota-launcher-head), launcher-native-lifecycle (queued, quota-launcher-head); [agent-coordination] coord-native-ssh-mvp (running, agent-coordination-head); Recent completions: ql-4c2bfec-independent-review (done)
```
- Groups active tasks under their canonical project identifier.
- Explicitly renders status (`queued`, `ready`, `running`) and owner tag.
- Appends recent completions for the supervised entity.
- **Epistemic Demarcation (C1634):** Formatting ready/running task queues and recent completions in the prompt envelope is an **informational watchdog notification** designed to prompt monitoring principals to review work and ask heads to claim ready work. It is **NOT** a native head queue subscription or automatic execution dispatcher. Heads retain sole authority to claim tasks and launch delegates.

### 2.5 Guarded Delivery & State Preservation
All existing watchdog safety invariants are preserved:
- Requires >= 2 consecutive clean `idle-empty` screen snapshots.
- Immediate 3rd screen check before delivery; aborts fail-closed on `busy` or `draft`.
- Preserves all durable memory fields in `state.json`: `sent_event`, `cooldown_until`, `last_request`, `pending`.
- Reconciles native ACKs via `exact_ack(...)`.

---

## 3. Test Suite Verification & Results

An offline test suite was created in `tests/test_supervision_routing.py` covering all twelve specification and negative test cases.

### 3.1 Offline Test Suite (`tests/test_supervision_routing.py`)

| Test # | Test Case Description | Result | Details |
|---|---|---|---|
| **Test 1** | Task with `team_id="quota-launcher"` and `project_id="quota-launcher"` matched for `codex-principal` | **PASS** | Verified entity extraction, principal tag binding, and task matching across active sets. |
| **Test 2** | Task with alias `project_id="agent-quota-launcher"` matched for `quota-launcher` | **PASS** | Verified alias normalization and symmetric matching across `project_id` and `team_id`. |
| **Test 3** | Product projects (`agent-coordination`, `agent-dashboard`, `agent-branches`, `quota-launcher`) all extracted | **PASS** | Loaded canonical `coordination/TEAM-REGISTRY.json`; verified all 4 active products present with truthful principal tags (dashboard codex+claude, coordination codex, branches/launcher unowned). |
| **Test 4** | Stopped or excluded principals (e.g. `claude-principal`) remain excluded | **PASS** | Validated exclusion via `excluded_principals`, agent `status: 'quiet'`, `supervision_excluded: True`, and `SUPERVISION_EXCLUDE_PRINCIPALS`. |
| **Test 5** | Deterministic head completion in digest and message body | **PASS** | Verified digest changes on completion, remains 100% deterministic across calls, and formats `Recent completions: ql-4c2bfec-independent-review (done)` in body. |
| **Test 6** | Ready tasks (`queued`) distinguished from `running` tasks | **PASS** | Verified queue separation in counts (`queued`: 1, `ready`: 1, `running`: 1), `active.ready` / `active.running`, and message body formatting. |
| **Test 7** | Full `service.run()` simulation verifying receipt and envelope body | **PASS** | End-to-end cycle in isolated scratch root; verified `[quota-launcher]`, `launcher-quota-resource-gates`, `Recent completions`, receipt JSON, and state tracking. |
| **Test 8** | Explicit empty ownership preserved (not defaulted to codex) | **PASS** | Project without principal owner preserves `principal_tags: []` and `'unowned': True`; task not assigned to codex. |
| **Test 9** | Unknown project task not matched | **PASS** | Task with unmapped project/team ID matches zero entities. |
| **Test 10** | Conflicting team and project registrations detected | **PASS** | Conflicting `head_tag`, `workspace`, or `principal_tags` recorded in `entity['conflict']` without silent overwrite. |
| **Test 11** | Deterministic alias ordering | **PASS** | Verified all entity `aliases` arrays match `sorted(aliases)`. |
| **Test 12** | Epistemic boundary: task body is notification only | **PASS** | Verified prompt envelope text serves as informational reminder, not execution dispatcher. |

Execution command:
```bash
TMPDIR=.local/scratch/supervision-routing python3 -m unittest -v tests/test_supervision_routing.py
Ran 12 tests in 0.009s
OK
```
OK
```

### 3.2 Canonical Test Suite Verification
All 47 canonical tests in `scripts/supervision/` continue to pass 100%:
- `test_ack_reconciliation.py`: 13/13 passed
- `test_retention.py`: 8/8 passed
- `test_service.py`: 26/26 passed

In addition, running `unittest discover` across all tests in `tests/` executed 107 test cases with 100% passing rate in 2.396s.

---

## 4. Environmental Invariants & Compliance

1. **Rust/Cargo Hold:** STRICTLY ZERO `cargo` or `rustc` invocations were executed.
2. **Scratch Budget:** Used dedicated scratch directory `.local/scratch/supervision-routing` (mode 0700). Measured disk usage: `4.0 KB` (limit: 512 MB).
3. **Zero Net `/tmp` Growth:** All temporary operations utilized `TMPDIR` pointing within `.local/scratch/supervision-routing/`.
4. **Memory Footprint:** Well within the cooperative process budget limit (<= 1500 MB).
5. **Publication Credential Guard:**
   ```bash
   python3 research/antigravity/tooling/publication_guard.py research/antigravity/recovery/REPORT-SUPERVISION-ROUTING-REPAIR.md
   ```
   Exit code: `0` (Zero credential leaks, unredacted tokens, or secrets detected).
6. **Subagent Protocol:** No git commit was performed by this subagent. All changes are staged in target files for parent inspection and integration.
