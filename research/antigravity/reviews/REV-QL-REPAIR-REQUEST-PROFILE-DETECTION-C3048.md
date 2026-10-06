# Review Report: QA of Commit d3a4276b7dc290c75adb4e992b2416e0a22ee4c0

**Task**: `t-ql-repair-request-profile-detection-c3048`
**Target Commit**: `d3a4276b7dc290c75adb4e992b2416e0a22ee4c0` (Branch: `ql-telemetry-tool-dedup-c3030`)
**Component**: `agent-quota-launcher`
**Reviewer**: Antigravity Code Review Agent

## Overview
This report documents the independent review and QA of commit `d3a4276b7` related to fixing goal-aware profile detection, structured error output, and idempotency key handling in `launcher request`.

## Verification Steps Performed

1. **Test Execution**: Ran unit tests for request handling and task profiles to verify expected behavior.
   - Command: `pytest tests/test_head_request.py tests/test_task_profiles.py`
   - Result: **PASS** (26/26 tests passed).

2. **Goal-Aware Profile Detection (`resolve_task_bounds`)**:
   - Examined `launcher/task_profiles.py`. `resolve_task_bounds` now actively includes `payload.get("goal")` in the search string `cmd`.
   - By constructing `cmd` as a concatenation of `command`, `prompt`, and `goal`, the auto-detection algorithm correctly identifies model and review tasks even when the instruction is provided solely as a `--goal` to `launcher request`.
   - Verified that regression test `test_resolve_task_bounds_autodetect_sees_goal_key` effectively asserts review goals submitted with `request()` resolve to the `model-review` profile.

3. **Structured Request Errors**:
   - Analyzed `launcher/cli.py` within the `request` function.
   - A `ValueError` raised during profile resolution in `resolve_task_bounds` (e.g., passing an unknown profile) is now explicitly caught. The application exits with code `1` and emits standard structured JSON: `{"error": "Profile resolution failed: ..."}`.
   - Verified regression tests `test_request_unknown_profile_emits_structured_error` ensure these errors strictly adhere to structured JSON output instead of unhandled stack traces.

4. **Idempotent Replay via `--key` & Duplicate ID Error**:
   - The CLI argument parser for `request` correctly exposes the `--key` flag.
   - If the key is conflicting or missing when reusing an ID, a `sqlite3.IntegrityError` or an internal `ValueError` from `Store.submit_task` is triggered.
   - These are cleanly caught and packaged as structured JSON: `{"error": "Task submission failed ..."}`.
   - Repeatedly submitting identical arguments with the same `--key` behaves idempotently.
   - Validated via tests `test_request_idempotent_resubmission_with_same_key` and `test_request_conflicting_key_payload_emits_structured_error`.

5. **Tool Dedup Documentation (C3045/C3048)**:
   - Evaluated `launcher/task_units.py` documentation in `parse_tool_events`.
   - The code now includes robust docstrings detailing the `step_index` global-uniqueness assumption and points to `tool_events_count` as an essential audit fallback when `tool_calls_count` differs.

## Conclusion

The implementation is verified to correctly address the C3048 repair request. All requested features—goal-aware profile detection, strictly structured errors for invalid inputs, `--key` arguments for idempotent submissions, and documentation updates—are present and covered by comprehensive regression tests.

**Status**: **APPROVED**
