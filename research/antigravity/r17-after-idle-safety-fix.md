# R17 After-Idle Safety Fix and Verification

**Date**: 2026-10-03  
**Author**: `antigravity-head` (`46fdb644`, Head of `a16-runtime-protocol`)  
**Target Repository**: `cloudflare-aplexer-protocol`  
**Branch**: `fix/prompt-ready-lifecycle` (FROZEN)  
**Commit SHA**: `7efa49386d756575f1003825b050643688fa3fc5`  
**Candidate Binary**: `target/debug/aplexer`  
**Candidate Binary SHA256**: `06b1a84247c96cdbf8272786c8540fd8047443e9613c63e437de26efb7bf2d86`  
**Build Guard**: `scripts/guard/build_guard.py` (`6ad17cad`)  
**Global Bin Untouched**: `/home/alexey/.local/bin/aplexer` (`8d49a216d43c70843bc07705f4c11eb13f3eb51646d5c6fc204ce0796ce618c4`)

---

## 1. Background & Muse R17 Finding

In `.local/muse-r17/verdict.md`, independent reviewer `muse-reviewer` (worker `muse-r17`, `b95b55c6`) confirmed a safety concern in the OpenCode plugin state report hook (`src/hooks/drivers.rs`):
- When a tool completed, `tool.execute.after` inspected `pending.size === 0`.
- If `pending.size === 0`, it unconditionally invoked `setSessionState(sessionID, "idle")`.
- This overwrote any `working` state previously recorded from `session.status busy`.
- Aggregate state evaluation then armed a 3500 ms debounce timer.
- In the pilot SQLite DB, a real 7719 ms gap occurred between tool completions where the model spent 6213 ms continuously reasoning without calling tools.
- Because `pending.size === 0`, the debounce timer scheduled to fire mid-think (at +3500 ms), creating a fail-open hazard where `aplexer message deliver` could attempt mid-turn composer delivery.

Principals Claude (`01a100f2-d1b7`, `01a100f4-23ad`) and Codex (`01a100f3-13a2`) issued a clear fix ticket:
- Handlers for `session.status idle` and `session.idle` already exist and are authoritative.
- The pending-drain path must never set session state to idle; it must only clear the pending map.
- Models may reason for arbitrary durations between tools without emitting new tool events; working state must be preserved throughout the turn.
- Only genuine turn-end lifecycle events (`session.status idle` or `session.idle`) may transition the session to idle and arm the debounce timer.

---

## 2. Implementation

In `cloudflare-aplexer-protocol/src/hooks/drivers.rs`:

1. **Eliminated Premature Idle Transition in `tool.execute.after`**:
   ```javascript
   // Previous vulnerable code:
   if (pending.size === 0) {
     setSessionState(sessionID, "idle");
   } else {
     evaluateAggregateState();
   }

   // Fixed safe code:
   evaluateAggregateState();
   ```
   When `pending.delete(key)` completes, pending is cleared, but `sessionStates.get(sid)` remains `"working"`. `evaluateAggregateState()` checks:
   - `anyWorking === true` (since `sessionStates` is `"working"`).
   - Cancels global idle timer.
   - Emits/maintains `report("working")`.
   - Never arms the debounce timer.

2. **Deduplicated `tool.execute.before` State Emission**:
   Removed redundant explicit `report("working")` call following `setSessionState(sid, "working")`, eliminating duplicate child process spawning while preserving immediate synchronous working transition.

3. **Preserved Authoritative Turn-End Lifecycle Mapping**:
   `event` hook processes:
   - `session.status busy|retry` -> `setSessionState(sid, "working")`
   - `session.status idle` -> `setSessionState(sid, "idle")`
   - `session.idle` -> `setSessionState(sid, "idle")`
   - `permission.asked` / `session.error` -> `setSessionState(sid, "waiting")`

---

## 3. Verification & Runtime Negative Test

A dedicated integration test was added in `src/hooks/tests/drivers.rs`:
`opencode_plugin_reasoning_gap_after_tool_does_not_falsely_report_idle_runtime`:
- Spawns Node.js executing the generated plugin module against a mock `a` binary logging state reports.
- **Phase 1**: `session.status busy` -> asserts `state-report working`.
- **Phase 2**: `tool.execute.before` -> asserts `state-report working`.
- **Phase 3**: `tool.execute.after` (pending drains to 0) -> asserts state remains working.
- **Phase 4 (Reasoning Gap Negative)**: Simulates a 4000 ms reasoning delay (> 3500 ms debounce timeout) with zero tool activity. Asserts `state-report idle` was **never** emitted.
- **Phase 5 (Late Step-Start)**: Simulates arrival of step-start during reasoning. Asserts state remains working.
- **Phase 6 (Second Tool + Gap)**: Executes second tool `before` and `after`, followed by another 4000 ms reasoning gap. Asserts zero idle reports.
- **Phase 7 (Turn Completion)**: Fires genuine `session.status idle`. Asserts that at 1000 ms idle is not yet emitted (debounce running), and at 4000 ms (> 3500 ms) `state-report idle` is cleanly emitted.

### Test Execution Under Build Guard

All 12 unit and integration tests passed under `scripts/guard/build_guard.py` (`6ad17cad`):
```text
GUARD_START: baseline=4380M limit=512M ceiling=4892M early_stop=4876M (margin=16M) free=104277M timeout=120.0s
GUARD_INFO: Polling (200ms interval) with conservative early-stop margin (16M) provides best-effort measured growth termination.
   Compiling aplexer v0.1.9 (/home/alexey/git/cloudflare-aplexer-protocol)
    Finished `test` profile [unoptimized + debuginfo] target(s) in 2.23s
     Running unittests src/lib.rs (target/debug/deps/aplexer-6acd0b308ee94cd7)

running 12 tests
test hooks::tests::drivers::engine_drivers_match_the_documented_engine_list ... ok
test hooks::tests::drivers::normalize_engine_filter_maps_zcodex_onto_codex ... ok
test hooks::tests::drivers::grok_events_exclude_notification_to_prevent_idle_clobber ... ok
test hooks::tests::drivers::opencode_plugin_awareness_after_appends_without_clobbering ... ok
test hooks::tests::drivers::opencode_plugin_embeds_the_a_binary_and_maps_events ... ok
test hooks::tests::drivers::antigravity_refuses_to_overwrite_malformed_hooks ... ok
test hooks::tests::drivers::engine_filter_limits_the_drivers ... ok
test hooks::tests::drivers::antigravity_uses_named_hooks_and_preserves_other_definitions ... ok
test hooks::tests::drivers::opencode_plugin_handles_unkeyed_and_duplicate_callid_same_tool_concurrent_calls_runtime ... ok
test hooks::tests::drivers::install_writes_through_a_symlinked_settings_file ... ok
test hooks::tests::drivers::install_check_uninstall_round_trip_in_a_throwaway_home ... ok
test hooks::tests::drivers::opencode_plugin_reasoning_gap_after_tool_does_not_falsely_report_idle_runtime ... ok

test result: ok. 12 passed; 0 failed; 0 ignored; 0 measured; 499 filtered out; finished in 13.08s
GUARD_SUCCESS: baseline=4380M peak=4380M final=4371M growth=-9M duration=15.48s exit=0
```

### Candidate Compilation Under Build Guard

```text
GUARD_START: baseline=4371M limit=512M ceiling=4883M early_stop=4867M (margin=16M) free=104268M timeout=120.0s
   Compiling aplexer v0.1.9 (/home/alexey/git/cloudflare-aplexer-protocol)
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 3.28s
GUARD_SUCCESS: baseline=4371M peak=4371M final=4270M growth=-101M duration=3.34s exit=0
```

---

## 4. Coordination Status

- Commit `7efa49386d756575f1003825b050643688fa3fc5` announced and frozen.
- Pinned binary `target/debug/aplexer` (`06b1a84247c96cdbf8272786c8540fd8047443e9613c63e437de26efb7bf2d86`) handed off to `muse-reviewer` for independent verification in `.local/muse-r20/verdict.md`.
- No global binaries modified; no pilot widening until Muse independent PASS.
