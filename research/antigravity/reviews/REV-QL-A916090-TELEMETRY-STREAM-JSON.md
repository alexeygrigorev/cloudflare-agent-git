# Independent Peer Review: QL Commit a916090 (Structured Invocation and Tool Telemetry Capture)

- **Reviewer**: `agent-coordination-head-gemini` (session `8d4c026c-319a-412f-96aa-fe4651347690`)
- **Review Date**: 2026-10-05T19:00:00+02:00
- **Repository**: `/home/alexey/git/agent-quota-launcher`
- **Target Commit**: `a9160902bc984defd9a473f627e532c99db58010` (`feat(telemetry): capture genuine structured invocation and tool events alongside artifact`)
- **Base Commit**: `8486acf9606aa254d825f6e990086f161ea5c5fe`
- **Review Request Receipt**: `01a10cfe-1073-77e0-b36f-92a3631fcb83`
- **Verdict**: **ACCEPT**

---

## 1. Summary of Changes

Commit `a916090` addresses the observability and first-tool tracing gap discovered during task `scale50-17`, where `--output-format text` omitted structured tool invocation events from worker execution receipts:

1. **Structured Stream CLI Invocation** (`launcher/launch.py`):
   - Changed the Antigravity adapter launch arguments from `--output-format text` to `--output-format stream-json`.
   - Allows the Antigravity CLI process to stream genuine NDJSON event objects (`init`, `step_update`, `result`) into the task's stdout log.

2. **Telemetry Extraction & Ingestion** (`launcher/task_units.py`):
   - Added `extract_telemetry_events(stdout_path: Path) -> List[Dict[str, Any]]`: Reads lines from the task stdout log and parses JSON records matching standard lifecycle events (`init`, `step_update`, `result`).
   - Added `parse_tool_events(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]`: Filters `step_update` events where `step_type == "tool"`, extracting `tool_name`, `step_index`, `state`, `duration_seconds`, and structured `tool_info` parameter payloads.
   - Updated `execute_transient_task_unit()`:
     - Extracts parsed events and populates execution receipts with `tool_calls_count`, `first_tool` (containing name, state, duration, and parameter summary), `model_status`, and token `usage`.
     - Preserves full telemetry directly in the task workspace at `<workspace>/<task_id>-telemetry.jsonl` alongside final markdown artifacts.
   - **Anti-Fabrication Guard**: If a worker outputs plain text or unformatted logs, `extract_telemetry_events()` parses zero events, `tool_calls_count` is 0, and `first_tool` is `None`. No synthetic tool events or placeholder telemetry are ever fabricated.

3. **Regression Tests** (`tests/test_telemetry.py`):
   - `test_antigravity_stream_json_argv`: Verifies correct CLI invocation flags.
   - `test_extract_and_parse_genuine_tool_events`: Validates multi-step NDJSON tool parsing and field mapping.
   - `test_no_synthesized_events_on_plain_text`: Asserts zero tool events when stdout is plain text.
   - `test_execute_transient_task_unit_preserves_telemetry_alongside_artifact`: Verifies end-to-end telemetry file preservation in task workspace and receipt structure.

---

## 2. Test & Verification Evidence

1. **Diff Inspection**:
   - `launcher/launch.py`: 1 insertion, 1 deletion.
   - `launcher/task_units.py`: 96 insertions. Clean separation of concerns with robust exception handling on JSON parsing.
   - `tests/test_telemetry.py`: 183 insertions providing full coverage of the new code paths.

2. **Test Suite Execution**:
   - Executed `python3 -m unittest discover tests -v` in `/home/alexey/git/agent-quota-launcher`.
   - Result: **185 passed** in 13.38s (including all 4 telemetry tests).
   - Zero test regressions or failures.

3. **Anti-Fabrication & Safety Audit**:
   - The implementation strictly relies on real event streams emitted by the runtime engine.
   - In the event of engine failure or missing JSON stream, the receipt truthfully records `tool_calls_count: 0` and `first_tool: None`.
   - Workspace telemetry is saved safely inside the task-local workspace boundary, avoiding global `/tmp` leakage.

---

## 3. Review Verdict & Recommendations

- **Verdict**: **ACCEPT**.
- **Action**:
  - Authorize QL Head (`a86056b5`) to proceed with the admitted retry of task `scale50-20` (ReadACK timestamp invariant test) in `/home/alexey/git/agent-bus/.local/scale50/scale50-20` using the reviewed commit `a916090` and task-local `TMPDIR` isolation.
  - Coordinate parallel admission of `scale50-29` and `scale50-30` under the human RAM override policy while continuing strict root storage monitoring.
