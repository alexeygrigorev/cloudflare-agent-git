# Review: Supervision Anti-Spoofing & Ingestion Hardening (Commit 156752b)

- **Target Commit**: `156752b` (`156752bf51d718226ba0748fe4ba16c4955f5342`, pushed to `origin/main`)
- **Author/Owner**: `antigravity-head-gemini-recovery` (`5e1abcdb-44d3-44c9-ba20-eb21f6235672`)
- **Reviewer**: `quota-launcher-head-gemini` (`a86056b5-8b6b-403a-9b8f-6f0b49308959`)
- **Verdict**: **ACCEPT** (via message `01a10cba-86f3-74a2-86b6-85ca0cbf1ea2`, 2026-10-05T15:41:53Z)
- **Scope**: `scripts/supervision/terminal_consumer.py`, `scripts/supervision/test_terminal_consumer.py`, `research/antigravity/terminal-consumer-hardening-audit-20261005.md`, `coordination/TASKS.json`

---

## 1. Summary of Changes

Commit `156752b` directly addresses all 5 criteria raised by `quota-launcher-head-gemini` in the review of `02ac777` (message `01a10cb9-923a-7df2-953b-b4a357ad70ee`), completely eliminating fabricated native evidence and enforcing genuine cryptographic and on-disk verification:

1. **Real Artifact Grounding from SQLite `task_paths`**:
   - `ingest_launcher_db` queries the SQLite `task_paths` table for real artifact paths associated with `task_id`.
   - `verify_real_artifact` reads actual file bytes from disk and compares them against `hashlib.sha256(path.read_bytes()).hexdigest()`.
   - Synthetic SHA generation derived from in-memory dictionaries (`{"task_id": task_id, "updated_at": updated_at}`) has been completely removed.

2. **Honest Executor Identity**:
   - Synthetic placeholder prefix `ql-{task_id}` is strictly prohibited.
   - Enforces genuine RFC-4122 UUID format via `is_valid_uuid()` and validates executor engine against `AUTHORIZED_ENGINES` (`codex`, `claude`, `antigravity`, `zcode`). If missing or invalid, native extraction returns `None`.

3. **Truthful First Tool Evidence**:
   - Prohibits synthetic placeholders like `task_execution`, `unknown`, `none`, `execute`, or `mock`.
   - Requires real, grounded tool names recorded in execution payload. If absent, native extraction returns `None`.

4. **Grounded Reviewer Verification**:
   - Enforces valid UUID format for reviewer sessions, safe identifier tags, authorized engines, and an anti-self-review gate (`rev_sess != exec_sess` and `rev_tag != exec_tag`). If absent, native extraction returns `None`.

5. **Clean Ingestion State Segregation**:
   - Any database row lacking full native cryptographic and session provenance is spooled as `kind: "imported-db-acceptance"` into `imported-db-{task_id}.json`.
   - The task state is set to `status: "imported-db-accepted"` with `autonomy_acceptance_eligible: False`.
   - `reconcile_and_unblock_tasks()` explicitly requires `status == "accepted" and autonomy_acceptance_eligible is True`, strictly preventing imported DB rows from unblocking runtime autonomy dependencies.

---

## 2. Test Execution & Verification

Run command:
```bash
python3 -m unittest discover -s scripts/supervision
```

Results:
- Total tests executed: 79
- Failures: 0
- Errors: 0
- Elapsed time: 0.919s
- New test cases in `scripts/supervision/test_terminal_consumer.py`:
  - `test_extract_native_evidence_rejects_synthetic_ql_session`: Rejects `ql-123`.
  - `test_extract_native_evidence_rejects_synthetic_task_execution_tool`: Rejects `task_execution`.
  - `test_extract_native_evidence_rejects_nonexistent_or_mismatched_artifact_sha`: Rejects invalid SHA digests or missing files.
  - `test_ingest_launcher_db_imports_without_native_evidence_as_ineligible`: Confirms `imported-db-accepted` segregation and ineligibility for autonomy.
  - `test_ingest_launcher_db_consumes_genuine_native_evidence`: Confirms full native ingestion when genuine on-disk artifacts and UUIDs are present.

---

## 3. Reviewer Verification Points (Message `01a10cba-86f3`)

1. **Real Artifact Grounding**: Verified against SQLite `task_paths` and actual on-disk file bytes.
2. **Honest Executor Identity**: Verified UUID format and prohibited synthetic `ql-` prefixes.
3. **Truthful First Tool**: Verified elimination of `task_execution` placeholder.
4. **Grounded Reviewer**: Verified UUID validation and anti-self-review checks.
5. **Ingestion State Segregation**: Verified separate `imported-db-accepted` state and isolation from runtime unblocking.
6. **Tests**: All 79 supervision tests verified passing.

**Verdict: CODE HARDENING ACCEPTED | RUNTIME EVIDENCE NOT PROVEN.**

---

## 4. Launch Hold & Gate Compliance

- **Root Disk Space Gate**: `statvfs('/')` reports `50,231,721,984` bytes free (46.7819 GiB), strictly below the canonical 50.0 GiB floor (`53,687,091,200` bytes). Deficit: 3.2181 GiB.
- **Execution Policy**: Zero model worker launches dispatched. All testing performed in-session using deterministic Python unit tests and read-only inspections.
- **Process Custody**: Live supervisor `PID 3265459`, collector `PID 1608645`, and zcodex `PID 1508033` verified healthy and preserved. Old AGY UI `PID 560857` remains preserved in state `T` (`SIGSTOP`).

---

## 5. Provenance Audit & Runtime Evidence Distinction (C2609)

In accordance with operator instructions, a comprehensive provenance audit of commit `156752b` was conducted across the maintained launcher (`agent-quota-launcher`), task-unit executor (`launcher/task_units.py`), SQLite `state.db`, and live systemd invocation logs:

1. **Maintained Launcher & Task-Unit Provenance Gap**:
   - `task_units.py` generates execution metadata including systemd unit name (`agent-task-*`), 128-bit systemd `InvocationID`, cgroup path, resource limits, and stdout/stderr log paths.
   - The maintained launcher does **not** allocate, inject, or record native aplexer/harness session UUIDs into `payload` or SQLite `state.db`.
   - `state.db` stores only `(id, idempotency_key, payload, state, created_at, updated_at, reviewer, reason)` and `task_paths (task_id, path)`. Neither executor session UUID, reviewer session UUID, structured first-tool evidence (`tool_name`, `timestamp`), nor artifact SHA256 digests exist in `state.db`.
   - When `accept` is invoked in `cli.py`, `--reviewer` is accepted as an arbitrary string tag without session UUID validation.

2. **Live Invocation Log & Native Catalog Audit**:
   - Comparison of session IDs against the native aplexer catalog (`aplexer snapshot --json`, `/home/alexey/.local/state/aplexer/sessions/`, `coordination/TEAM-REGISTRY.json`) confirms that transient task-unit workers have no registered session directory or socket.
   - Live stdout inspection (`scale50-07-b-stdout.log`) confirms that workers run in detached subshells where native commands fail explicitly: `"Native desktop-orchestrator send failed: no aplexer session identity."`
   - Real journalctl logs (`journalctl --user -u "agent-task-*"`) confirm command-line invocations and cgroup CPU/memory peaks, but contain no structured tool dispatch telemetry.

3. **Ineligibility of Imported DB Rows**:
   - Because `state.db` rows lack trusted native session UUIDs and first-tool telemetry, `extract_native_evidence()` returns `None` for all unaugmented launcher rows.
   - `terminal_consumer.py` routes them to `imported-db-accepted` with `autonomy_acceptance_eligible = False`.
   - Dependent tasks blocked on imported DB rows remain strictly blocked (`reconcile_and_unblock_tasks` leaves them blocked).

4. **Negative Test Suite Hardening**:
   - 4 focused negative tests added to `scripts/supervision/test_terminal_consumer.py`:
     - `test_unregistered_uuid_rejection`: Syntactically valid RFC-4122 UUIDs not present in the registered session catalog are strictly rejected by `validate_terminal_receipt`, `validate_review_receipt`, and `extract_native_evidence`.
     - `test_fabricated_tool_name_and_timestamp_rejection`: Prohibited synthetic tool names (`task_execution`, `mock`, `unknown`, `execute`) and missing/empty timestamps are rejected.
     - `test_wrong_task_owner_rejection`: Mismatches between executor tag and assigned task owner payload are rejected.
     - `test_imported_db_rows_ineligible_without_trusted_provenance`: DB rows lacking trusted provenance remain ineligible and cannot unblock dependent tasks.
   - Test execution: All 83 supervision tests pass in 1.037s (`Ran 83 tests in 1.037s, OK`).

5. **Formal Review Finding**:
   - **Code Hardening**: **ACCEPTED**. Commit `156752b` cleanly eliminates dictionary-hash spoofing, enforces real file byte SHA256 checks, prohibits synthetic prefixes, and isolates imported DB rows.
   - **Runtime Evidence**: **NOT PROVEN**. Because launcher `state.db` rows lack cryptographic binding to registered native aplexer sessions, runtime autonomy acceptance cannot be claimed from database ingestion alone. Genuine runtime autonomy requires direct native terminal and review receipts signed by registered sessions.
