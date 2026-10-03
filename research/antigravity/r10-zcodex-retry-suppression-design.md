# R10: ZCodex Denial Suppression & Tool-Boundary Turn Termination Design

**Author:** `antigravity-head` (`46fdb644`), Integration Owner for `cloudflare-aplexer-protocol` & Head of `a16-runtime-protocol`  
**Date:** 2026-10-03T07:10:00+02:00 (Europe/Berlin)  
**Reference Tickets:** `01a10014-a645` (Claude Principal), `01a10014-61f6` (Desktop Orchestrator), `01a10022-cc5f` (Claude Principal), `01a10027-681b` (Claude Principal)  
**Independent Review Target:** `muse-reviewer` (`7e6e9bb0`)  
**Target Repository:** `/home/alexey/git/codex-zcode` (`codex-rs/core/src/client.rs`)  
**Resource Constraint:** STRICT DESIGN ONLY — ZERO COMPILATION / ZERO BUILD.

---

## 1. Executive Summary

In R9, comparative live append-only testing demonstrated that cold-spawning `zcode.cjs` under `--mode build` successfully eliminates unrecorded inner tool execution (reducing duplicate marker lines from 2 to 1 in controlled prompts). However, as independently counted by `muse-reviewer` (Round 23, commit `48be7a9`) on rollout `01a1000a-8f19`, an unconstrained prompt provoked **two distinct outer `exec_command` tool calls** (`633571b1` and `e9c52a05`), executed ~16 seconds apart, both exiting 0.

### Verdict of Record (Muse Round 23):
> *"Inner duplicate eliminated in observed runs; outer retry duplicates still possible (demonstrated, not hypothetical); no exactly-once claim."*

This document provides the formal **DIAGNOSIS**, **architectural design**, **patch diff**, and **test plan** for ticket `01a10014-a645`. It identifies why inner denials provoke outer model retries and designs the structural solution: **terminating the inner child turn at the tool boundary** so that the outer Codex `ToolCallRuntime` exclusively executes tool calls, manages conversation history, and drives subsequent turns with authentic tool results.

---

## 2. Deep Technical Diagnosis

### 2.1 The Two Nested ReAct Loops
The fundamental flaw in cold-spawn `stream_zcode` (`codex-rs/core/src/client.rs`) is an impedance mismatch between two competing ReAct loops:
1. **Outer ReAct Loop (Codex Engine):**
   - Codex drives conversations turn-by-turn.
   - On each turn, Codex calls `client.stream(&prompt)` to obtain the model's output.
   - If the model emits `ResponseItem::FunctionCall`, Codex's `ToolCallRuntime` executes the tool call (applying sandboxing, permissions, timeouts, and transcript logging).
   - Once executed, Codex appends `ResponseItem::FunctionCallOutput` to `prompt.input` and invokes the next turn (`client.stream(&prompt)`).
   - In `client.rs`, lines 3331-3368 show this design clearly: `zcode_flatten_transcript` serializes past tool calls and tool outputs, appending:
     `"Continuation: previous tool calls have already been executed. Use the recorded tool results above and answer the user now without calling the same tools again."`
2. **Inner ReAct Loop (Node `zcode.cjs`):**
   - When `node zcode.cjs --prompt ...` is spawned, `zcode.cjs` does not behave like a single-turn completion API. It initializes its own full agent loop (`Agent`, `Task`, `ToolScheduler`).
   - When the inner model outputs a tool call (`Bash`), `zcode.cjs` attempts to execute the tool internally inside Node.

### 2.2 Mechanism of the Double Execution & Outer Retry
- **Under `--mode yolo`:**
  - `zcode.cjs` auto-approves `Bash` and executes it internally (producing Side Effect 1).
  - Meanwhile, `client.rs` intercepts the streamed `model.streaming` event and emits `ResponseItem::FunctionCall` to Codex.
  - Codex's `ToolCallRuntime` executes the tool call externally (producing Side Effect 2).
  - Outcome: **Double Execution (2 side effects per tool call)**.
- **Under `--mode build`:**
  - `zcode.cjs` configures `createDenyPermissionBroker()` (located at offset ~4,898,489 of `zcode.cjs`), which immediately returns:
    `{ decision: "deny", reason: "No permission client configured for Bash" }`.
  - `zcode.cjs` appends this failure to the inner model's conversation history as a tool error.
  - The inner model receives the denial and believes the command failed.
  - Because `client.rs` continues reading stdout in its `while let Some(line) = ...` loop, `zcode.cjs` continues into Turn 2 of its inner loop:
    1. The inner model emits text: `"The Bash call failed with a permission-client error. Let me retry once in case it's transient."`
    2. The inner model emits a SECOND `tool_call` (call ID `e9c52a05`) ~16s later.
  - `client.rs` blindly processes this second tool call and emits a SECOND `ResponseItem::FunctionCall` to Codex's `tx`.
  - When `zcode.cjs` eventually terminates, Codex's `ToolCallRuntime` executes **both** function calls.
  - Outcome: **Outer Model Retry Duplication (2 distinct outer calls executed)**.

### 2.3 Why Process-Level Interception Fails
The denial `"No permission client configured for Bash"` is generated entirely in Node memory and transmitted directly over the network to the GLM API during the child's autonomous turn. `codex-rs` runs as an external OS process reading stdout over a pipe; it cannot intercept or alter what Node's JS runtime sends to the GLM backend once the inner loop continues past the tool call.

Therefore, the only robust, correct mechanism is to **halt the child process at the tool boundary**.

---

## 3. The Structural Solution: Tool-Boundary Turn Termination

### 3.1 Architectural Contract
When `stream_zcode` detects that the model has finalized a tool call (or a batch of parallel tool calls):
1. All tool calls in the initial model generation are emitted to Codex (`OutputItemDone(FunctionCall)`).
2. The streaming loop halts immediately.
3. The child process (`node zcode.cjs`) is gracefully disposed (`dispose_and_wait_once`), terminating before it can query `DenyPermissionBroker` or prompt GLM for an inner retry.
4. `stream_zcode` sends `ResponseEvent::Completed { end_turn: Some(true), ... }`.
5. Codex's `ToolCallRuntime` takes sole responsibility for running the tool, logging the output, and initiating Turn 2 with the recorded results in context.

### 3.2 State Machine for Tool Boundary Detection
- **Leading Text (Thinking/Explanations):**
  If the model outputs text deltas before tool calls, `started_output` is true. When `tool_input_start` or `tool_call` arrives, lines 3700-3716 of `client.rs` already finalize and emit the leading `ResponseItem::Message`. This is preserved.
- **Parallel Tool Calls (Batching):**
  A model may emit multiple tool calls in a single completion (e.g. `ls` and `pwd`).
  In ZCode NDJSON, these arrive with `tool_input_start`, deltas, and `tool_call` within milliseconds of each other.
  `pending_tools: HashMap<String, PendingZcodeTool>` tracks pending calls.
  The turn termination triggers when:
  `emitted_tool_calls > 0 && pending_tools.is_empty()`
  To protect against sub-millisecond arrival jitter between sibling tool calls, a brief drain timeout (e.g., 50ms) or checking for non-tool events cleanly finalizes the batch.
- **Pure Text Turns (Final Answers):**
  If `emitted_tool_calls == 0`, the child runs to its natural completion (`result` event or EOF). This path remains completely untouched.

---

## 4. Concrete Patch Diff (`codex-rs/core/src/client.rs`)

```diff
--- a/codex-rs/core/src/client.rs
+++ b/codex-rs/core/src/client.rs
@@ -3656,6 +3656,8 @@ impl ModelClient for ZcodeClient {
             // Set when the stream went silent past the idle window; the turn
             // is failed and the child torn down below.
             let mut stalled: Option<Duration> = None;
+            // Set when the model has emitted tool calls and reached the tool boundary.
+            let mut tool_boundary_reached = false;
             while let Some(line) = match pending_line.take() {
                 Some(line) => Some(line),
                 None => match zcode_process::next_stream_line(&mut lines, idle_timeout).await {
@@ -3879,6 +3881,14 @@ impl ModelClient for ZcodeClient {
                             }
                             emitted_tool_calls += 1;
                             completed_tool_ids.insert(tool_call_id.to_string());
+                            // End inner turn at the tool boundary: once authoritative
+                            // tool calls are emitted and no sibling tool inputs are
+                            // pending, stop reading from the child. Allowing the child
+                            // to continue into its own inner loop would provoke fake
+                            // permission denials and uncoordinated outer retries.
+                            if pending_tools.is_empty() {
+                                tool_boundary_reached = true;
+                                break;
+                            }
                         } else {
                             // Orphan `tool_call` without a prior
                             // `tool_input_start` (should not happen, but be
@@ -3912,6 +3922,10 @@ impl ModelClient for ZcodeClient {
                             }
                             emitted_tool_calls += 1;
                             completed_tool_ids.insert(tool_call_id.to_string());
+                            if pending_tools.is_empty() {
+                                tool_boundary_reached = true;
+                                break;
+                            }
                         }
                     }
                     if is_tool_input_end {
@@ -3972,7 +3986,7 @@ impl ModelClient for ZcodeClient {
             // raw deltas (the 421 KiB poisoning path). Emit a capped,
             // validated fallback instead. Skip when the turn already
             // failed (session.error) or stalled so a dead turn does not
             // sprout half-formed tools.
-            if failed.is_none() && stalled.is_none() {
+            if failed.is_none() && stalled.is_none() && !tool_boundary_reached {
                 for (tool_call_id, pending) in std::mem::take(&mut pending_tools) {
                     if completed_tool_ids.contains(&tool_call_id) {
                         continue;
@@ -4014,7 +4028,7 @@ impl ModelClient for ZcodeClient {
             let status = match startup_status {
                 Some(status) => status,
-                None if stalled.is_some() || aborted => {
+                None if stalled.is_some() || aborted || tool_boundary_reached => {
                     zcode_process::dispose_and_wait_once(&mut child).await
                 }
                 // The stream ended on its own; the child is on its way out.
@@ -4032,7 +4046,7 @@ impl ModelClient for ZcodeClient {
             let reply_bytes = response_text.len();
             let stderr_text = zcode_stderr_tail(&stderr_tail);
             match (status, failed) {
-                (Ok(status), None) if status.success() => {
+                (Ok(status), None) if status.success() || tool_boundary_reached => {
                     // Finalize the reply from the text actually streamed: the
                     // completed item must match what the user watched, and on
                     // tool turns this trailing segment is the only
```

---

## 5. Rigorous Test Plan & Negative Verification

The test plan exercises all execution paths without requiring a full cargo compile until an authorized disk guard is present:

### 5.1 Synthetic Adapter Unit Tests (`core/src/zcode_tests.rs`)
1. **Single Tool Call Teardown:**
   - Input: NDJSON stream emitting `text_delta` ("thinking"), `tool_input_start` ("exec_command"), `tool_call` (args), followed by synthetic inner denial (`"No permission client configured"`).
   - Assertion: `stream_zcode` yields `Message`, `FunctionCall`, and terminates immediately.
   - Check: The child process is signaled `SIGTERM`/killed; the synthetic denial is never processed; exactly 1 `FunctionCall` is emitted to `tx`.
2. **Parallel Tool Calls (Sibling Batching):**
   - Input: NDJSON stream emitting two interleaved tool calls (`tool_input_start` A, `tool_input_start` B, `tool_call` A, `tool_call` B).
   - Assertion: `pending_tools` prevents early exit on tool A; teardown occurs only after tool B is emitted. Both calls are yielded.
3. **Pure Text Turn (Zero Tools):**
   - Input: NDJSON stream emitting `text_delta` ("final answer"), `result` event, exit 0.
   - Assertion: Full text is emitted; child exits cleanly on its own (`tool_boundary_reached = false`).

### 5.2 Live Comparative Regression Probe
1. **Unconstrained Probe Rerun:**
   - Prompt: `"Use Bash to create /tmp/test.txt containing 'OK'. Do nothing else."`
   - Evaluate trace against rollout `01a1000a-8f19`:
     - Expected: Exactly 1 outer `exec_command` tool call.
     - Expected: Zero 16-second delay; child process reaped in <100ms.
     - Expected: Turn 2 receives the tool result from `ToolCallRuntime` and emits final text with zero model retries.

### 5.3 Negative Cases & Edge Guards
1. **Aborted Invocations:** If the client drops the stream (`tx.is_closed()`), teardown remains immediate.
2. **Stall Timeout:** If the child hangs before emitting `tool_call`, the idle timeout kills the process as before.
3. **Truncated Tool Input:** If the stream drops before `tool_call`, the fallback flush handles pending tools.

---

## 6. Resource Compliance & Rollout Policy

1. **Compilation Guard:** In accordance with Root directive `CHECK0224` and Claude Principal instructions, **no `cargo build`, `cargo clean`, or `cargo test` is executed**. Target directory remains untouched (+12.26 GB growth violation halted).
2. **Safe Reversible Rollout Gate:** Root directive `01a10014-61f6` authorizes scoped reversible deployment only after:
   - Independent peer review by `muse-reviewer` (`7e6e9bb0`).
   - Implementation in an isolated branch/worktree.
   - Validation that disk and quota budgets remain strictly within physical limits.
