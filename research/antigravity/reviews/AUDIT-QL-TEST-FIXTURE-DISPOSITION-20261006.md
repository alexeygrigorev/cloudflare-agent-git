# Audit & Disposition: Attributable Unit-Test Fixtures in Launcher Databases

**Date**: 2026-10-06  
**Auditor**: Ant Head Custody (`ant-head-custody-resume-20261006`, `365d3033-e7f8-4962-98b1-869674578125`)  
**Challenge Reference**: `C2725` (codex-principal message `01a11014-c91f-7d43-b20d-2b7496e5c1a9`)  
**Status**: DISPOSITION DOCUMENTED & SOURCE REPAIRED

---

### 1. Attributable Test Fixtures Identified

During execution of `test_supervision_routing.py` (which runs `service.run()` under test harness conditions), the following five tasks were inserted into the `tasks` table of the live `agent-quota-launcher` databases:

1. `t-conflicted-ql` (origin: `tests/test_supervision_routing.py:564`)
2. `t-unconflicted-coord` (origin: `tests/test_supervision_routing.py:571`)
3. `t1` (origin: `tests/test_supervision_routing.py:126`)
4. `t-reconcile-1` (origin: `tests/test_supervision_routing.py:891`)
5. `t-recipient-change-1` (origin: `tests/test_supervision_routing.py:993`)

Affected SQLite database files:
- `/home/alexey/git/agent-quota-launcher/.local/launcher-config/state.db`
- `/home/alexey/git/agent-quota-launcher/.local/scale50/wt-gemini-head/.config/ql/state.db`
- `/home/alexey/git/agent-quota-launcher/.local/state.db`

### 2. Root Cause Analysis

In `scripts/supervision/service.py`:
- `ql_db_candidates` was statically hardcoded to point to the production database files in `/home/alexey/git/agent-quota-launcher/`.
- Although `service.ROOT` and `service.PRIVATE` were redirected to temporary directories during unit tests, `bridge_ready_task_to_launcher` still received the hardcoded production candidate paths and executed `INSERT INTO tasks ... VALUES (?, ?, ?, 'queued', ...)` into the live launcher databases.

### 3. Source Repair & Isolation Enforcement

1. Implemented `get_ql_db_candidates(root=None, private=None)` in `scripts/supervision/service.py`:
   - Checks `SUPERVISION_QL_DB_PATHS` environment variable override if present.
   - If `ROOT != /home/alexey/git/cloudflare-agent-git` (i.e. running in a test harness or temporary workspace), returns only isolated candidates within `private / 'launcher' / 'state.db'`, completely isolating live launcher databases from test runs.
   - Production launcher paths are only returned when running against the canonical repository root.
2. Updated `bridge_ready_task_to_launcher` and the supervision loop in `service.py` to use `get_ql_db_candidates(ROOT, PRIVATE)`.
3. Mirrored changes to `research/antigravity/tooling/supervision/service_candidate.py`.
4. Verified that test execution no longer alters or appends rows to live launcher databases.

### 4. Audit Disposition & State Cleanup

Per principal guidance, unknown tasks are never deleted, and attributable test fixtures must not be counted as executable reserve or launched on real models:
- The 5 tasks (`t-conflicted-ql`, `t-unconflicted-coord`, `t1`, `t-reconcile-1`, `t-recipient-change-1`) are formally marked with state `'audit-excluded-test-fixture'` (or terminal state `'failed'` with reviewer `'ant-head-custody-resume-20261006'`).
- Rows are **preserved** in SQLite with their full payload, timestamps, and an explicit reason:
  `"Attributable unit-test fixture from test_supervision_routing.py; excluded from useful model dispatch"`.
- This releases all path and resource reservations (`RESOURCE_HOLDING_STATES`, `LEASED_STATES`) without deleting audit history or corrupting SQLite integrity.
