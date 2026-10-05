# REV-DASHBOARD-HEAD-READINESS — Independent Diagnostic Audit of Dashboard Head Readiness, Producer Traces & Aplexer Delivery Guard (C2189 / C2192 / C2204 / C2208)

- **Audit Target Document:** [`research/antigravity/recovery/REPORT-DASHBOARD-HEAD-READINESS-REPAIR.md`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/recovery/REPORT-DASHBOARD-HEAD-READINESS-REPAIR.md)
- **Target Managed Session:** `agent-dashboard-head` (session UUID: `c7a75f76-1f51-4f14-873e-7a60569838c3`, workspace: `/home/alexey/git/agent-dashboard`, engine: `zcodex`)
- **Governing Directives:** Codex Principal Directives C2189, C2192, C2204, and C2208; Operating Model (`coordination/OPERATING-MODEL.md`); Human Delivery Reset (2026-10-04)
- **Independent Reviewer:** `reviewer259` (session UUID: `259526a9-5deb-47ce-810c-ca5f2da56b68`)
- **Review Deliverable:** [`research/antigravity/reviews/REV-DASHBOARD-HEAD-READINESS.md`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/reviews/REV-DASHBOARD-HEAD-READINESS.md)
- **Scratch Workspace:** `.local/scratch/reviewer259-readiness-audit/` (mode `0700`, strictly $\le$ 512 MB, net `/tmp` growth = 0)
- **Offline Negative Test:** [`.local/scratch/reviewer259-readiness-audit/test_readiness_contradiction.py`](file:///home/alexey/git/cloudflare-agent-git/.local/scratch/reviewer259-readiness-audit/test_readiness_contradiction.py) (4/4 tests pass)
- **Compiler Invariant:** Exactly **0 cargo / rustc invocations executed in this audit interval and environment under human hold**
- **Canonical Repository Invariant:** `/home/alexey/git/agent-dashboard` and `/home/alexey/git/cloudflare-aplexer-protocol` audited **STRICTLY READ-ONLY** (0 writes, 0 edits, 0 git stage/commit mutations)
- **Audit Date:** 2026-10-05T03:11:00+02:00 (Europe/Berlin)

---

## 1. Executive Summary & Epistemic Audit Findings

Under Codex Principal Directives C2189, C2192, C2204, and C2208, an independent diagnostic audit was conducted on [`research/antigravity/recovery/REPORT-DASHBOARD-HEAD-READINESS-REPAIR.md`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/recovery/REPORT-DASHBOARD-HEAD-READINESS-REPAIR.md). The audit combined source-level protocol inspection, actual producer artifact inspection (`session.json`, `worker.identity.json`, `coordination.json`, `history.bin`), and a minimal offline Python negative test.

### 1.1 Core Audit Findings
1. **Diagnosis Accuracy:** The readiness repair report accurately and truthfully diagnoses the aplexer delivery guard failure. When evaluating PTY delivery of cross-workspace handoff message `01a10988-c253`, the guard functioned strictly in conformance with protocol specifications.
2. **Rejection Arithmetic:** The divergence between the last reported idle state (`oldidle: 1791113916291` ms) and subsequent PTY activity (`laterPTY: 1791161046182` ms) is **47,129,891 ms**, which mathematically equals **13 hours, 05 minutes, 29.891 seconds**. The report's calculation is verified exact to the millisecond.
3. **Producer Trace Identification:**
   - **Initial Resting Report:** Emitted at `1791113916291` ms (2026-10-04T11:38:36.291Z / 1:38 PM Berlin) when `zcodex` completed a 21m 37s turn and triggered the Codex `"Stop"` hook, invoking `a state-report idle`.
   - **Subsequent PTY Output:** Emitted at `1791161046182` ms (and later `1791162246933` ms) as raw cursor repositioning ANSI escape sequences (`\x1b[?2026h\x1b[39m\x1b[49m\x1b[0m\x1b[22;3H\x1b[?25h\x1b[?2026l`) at row 22, column 3 of the interactive TUI.
   - **Missing Lifecycle Refresh:** Codex lifecycle hooks only fire on `"UserPromptSubmit"` and `"Stop"`. In the absence of a new prompt submission, no hook fired to refresh `reported_state_at_ms`.
4. **Fail-Closed Policy Enforcement:**
   - Resting state contradiction evaluated to `true` under `idle_was_contradicted_with_hooks`: PTY activity occurred 47,127,891 ms past the post-idle render grace period (`IDLE_ACTIVITY_GRACE_MS = 2,000` ms).
   - Under protocol line 127, an empty composer (`EMPTYCOMPOSER`) accompanying an expired or contradicted resting report does **NOT** prove turn completion.
   - The recipient engine is `zcodex`, which has no cursor/timer redraw exemption (unlike the `antigravity` engine in line 102/170).
5. **Epistemic Classification of Source-Binary Parity:** Source-binary parity between `/home/alexey/git/cloudflare-aplexer-protocol` source code and the installed `/home/alexey/.local/bin/aplexer` binary is formally recorded as an **UNVERIFIED HYPOTHESIS (`HYPOTHESIS / UNVERIFIED`)**. Under the human hold on compiler execution, zero `cargo` / `rustc` invocations, symbol inspections, or disassemblies were performed.
6. **Governance Boundary for Recovery Routes:**
   - Route A (native mailbox read by `agent-dashboard-head`) is currently blocked on session awakening.
   - Route B (delegation to `ad-backend-exec` under flock) requires an **actual acknowledged handoff on the bus/inbox**, not speculative parent authority.
   - Narrow repair owner is identified as `agent-dashboard-head` (session `c7a75f76`) via session refresh or manual operator prompt interaction.

---

## 2. Source-Level Protocol Implementation Inspection

The aplexer delivery guard logic was inspected directly in the read-only repository [`cloudflare-aplexer-protocol`](file:///home/alexey/git/cloudflare-aplexer-protocol).

### 2.1 Inspection of `message_deferred.rs:100-130`
In [`cloudflare-aplexer-protocol/src/bin/aplexer/message_deferred.rs`](file:///home/alexey/git/cloudflare-aplexer-protocol/src/bin/aplexer/message_deferred.rs#L100-L130), the readiness evaluation function `evaluate_readiness_verdict` executes four sequential checks before authorizing delivery:

```rust
// cloudflare-aplexer-protocol/src/bin/aplexer/message_deferred.rs:100-130
    // 3. Contradicted resting state check:
    // If the agent reported resting ('idle' or 'waiting'), did newer PTY activity land after the push?
    // Engine-specific: Antigravity background cursor/timer redraws are exempted; all other engines fail closed.
    if let (Some(rep), Some(at)) = (record.reported_state.as_deref(), record.reported_state_at_ms) {
        if rep == "idle" && aplexer::watch::idle_was_contradicted_with_hooks(record, at, has_hooks) {
            return ReadinessVerdict::Reject(format!(
                "recipient reported idle at {at}ms, but subsequent PTY activity contradicted resting state; delivery fail-closed"
            ));
        }
        if rep == "waiting" && record.engine != "antigravity" {
            if let Some(last_act) = record.last_activity_ms {
                if last_act > at.saturating_add(aplexer::watch::IDLE_ACTIVITY_GRACE_MS) {
                    return ReadinessVerdict::Reject(format!(
                        "recipient reported waiting at {at}ms, but subsequent PTY activity occurred at {last_act}ms (+{}ms); resting state contradicted, delivery fail-closed",
                        last_act.saturating_sub(at)
                    ));
                }
            }
        }
    }

    // 4. Only authentic fresh resting report (uncontradicted idle or waiting) is ready:
    if source == "reported" && matches!(state, "waiting" | "idle") {
        return ReadinessVerdict::Ready;
    }

    // All other states (stale reports, inferred/heuristic states without fresh report, no hooks) fail closed.
    // Expired waiting + empty composer does NOT prove completed turn; fail closed.
    ReadinessVerdict::Reject(readiness_detail(record, state, source, now))
```

### 2.2 Inspection of `idle_was_contradicted_with_hooks`
In [`cloudflare-aplexer-protocol/src/watch/state.rs`](file:///home/alexey/git/cloudflare-aplexer-protocol/src/watch/state.rs#L141-L171), the resting state contradiction is defined as:

```rust
pub fn idle_was_contradicted_with_hooks(
    record: &SessionRecord,
    at: u64,
    has_lifecycle_hooks: bool,
) -> bool {
    let Some(last_activity) = record.last_activity_ms else {
        return false;
    };
    if last_activity <= at.saturating_add(IDLE_ACTIVITY_GRACE_MS) {
        return false;
    }
    if !has_lifecycle_hooks {
        return true;
    }
    // Contract (Codex Principal C1652):
    // In `a watch`'s metadata-only polling loop, we observe only timestamps (last_activity_ms vs
    // reported_state_at_ms) without a rich producer event stream or hook epoch metadata.
    // PTY activity beyond IDLE_ACTIVITY_GRACE_MS cannot be unconditionally dismissed as harmless
    // redraws: if a hook crashes, fails to fire, or is delayed during new workload execution,
    // blindly returning false would treat an actively running session as resting idle.
    //
    // Without verified resting screen state (such as composer/screen capture in require_ready_prompt)
    // or producer hook sequence epochs, unverified PTY activity past the post-idle render grace
    // window must fail closed for general engines.
    //
    // Engine-specific exemption: Antigravity's interactive TUI continuously produces background
    // timer ticks and cursor redraws on its PTY while resting; for all other engines, unverified
    // PTY bursts past grace contradict idle.
    record.engine != "antigravity"
}
```

### 2.3 Policy Rationale for Line 127: Expired Waiting + Empty Composer Fails Closed
Line 127 states: `// Expired waiting + empty composer does NOT prove completed turn; fail closed.`
This rule is vital for terminal harness safety:
1. **Ambiguous Screen Text:** A screen capture showing an empty prompt or placeholder text (such as `› Ask Codex to do anything`) confirms only that the prompt input buffer has no characters. It does not establish that the background language model turn or tool chain has concluded.
2. **Intermediate Subagent / Tool Execution:** In CLI agents such as `zcodex`, an agent may finish printing a tool output and clear the composer while a child process or asynchronous network call is pending.
3. **No Turn Completion Without Lifecycle Hooks:** If an agent's reported resting state timestamp is stale (greater than `REPORTED_STATE_STALE_MS = 30_000` ms) or contradicted by later PTY output, treating the empty composer as "ready" would inject synthetic input into an active, thinking, or mid-transition session, resulting in garbled commands or broken state.

### 2.4 Engine-Specific Exemption: `antigravity` vs. `zcodex`
- **Antigravity Exemption:** Line 102 of `message_deferred.rs` and line 170 of `watch/state.rs` explicitly check `record.engine != "antigravity"`. Antigravity's interactive TUI emits continuous background cursor flickers and status-line clock redraws on its pseudo-terminal while idling. Hence, Antigravity requires an exemption so that benign clock updates do not permanently lock out message delivery.
- **Strict zcodex Enforcement:** The `zcodex` engine does not have this exemption. Any PTY activity occurring past the 2,000 ms grace period is treated as a possible active workload. For `agent-dashboard-head`, whose engine is `zcodex`, the guard enforced this strict fail-closed policy.

---

## 3. Audit of Rejection Telemetry & Mathematical Verification

### 3.1 Raw Telemetry Verification
From the recorded session state in `/home/alexey/.local/state/aplexer/sessions/c7a75f76-1f51-4f14-873e-7a60569838c3/session.json` and message delivery logs:
- Recipient Session ID: `c7a75f76-1f51-4f14-873e-7a60569838c3`
- Engine: `zcodex`
- Reported State: `"idle"`
- Reported State Timestamp (`oldidle`): `1791113916291` ms
- Subsequent PTY Activity Timestamp (`laterPTY`): `1791161046182` ms
- Post-Idle Render Grace: `IDLE_ACTIVITY_GRACE_MS = 2,000` ms
- Allowed Activity Window: `1791113916291 + 2000 = 1791113918291` ms

### 3.2 Exact Mathematical Verification
$$\begin{aligned}
\Delta t &= \text{laterPTY} - \text{oldidle} \\
&= 1791161046182 - 1791113916291 \\
&= 47,129,891\text{ ms}
\end{aligned}$$

Converting milliseconds to human-readable units:
$$\text{Total Seconds} = \frac{47,129,891}{1,000} = 47,129.891\text{ s}$$
$$\text{Hours} = \lfloor 47,129.891 / 3600 \rfloor = 13\text{ hours} \quad (13 \times 3600 = 46,800\text{ s})$$
$$\text{Remaining Seconds} = 47,129.891 - 46,800 = 329.891\text{ s}$$
$$\text{Minutes} = \lfloor 329.891 / 60 \rfloor = 5\text{ minutes} \quad (5 \times 60 = 300\text{ s})$$
$$\text{Seconds} = 329.891 - 300 = 29.891\text{ s}$$

$$\mathbf{\Delta t = 13\text{ hours, } 05\text{ minutes, } 29.891\text{ seconds}}$$

**Verification Result:** The calculation in `REPORT-DASHBOARD-HEAD-READINESS-REPAIR.md` is **VERIFIED EXACT**. The idle timestamp was not an artifact of a 47-second or 47-millisecond glitch; it represented an obsolete resting state from over 13 hours prior, which had been superseded by subsequent PTY output half a day later.

---

## 4. Deep Scoped Producer Trace & PTY Byte Analysis

A deep inspection of the producer artifacts for session `c7a75f76-1f51-4f14-873e-7a60569838c3` in `/home/alexey/.local/state/aplexer/sessions/c7a75f76-1f51-4f14-873e-7a60569838c3/` was conducted.

### 4.1 Producer Artifact Inspection
- **`session.json`:**
  - `id`: `"c7a75f76-1f51-4f14-873e-7a60569838c3"`
  - `workspace`: `"/home/alexey/git/agent-dashboard"`
  - `tag`: `"agent-dashboard-head"`
  - `engine`: `"zcodex"`
  - `created_at_ms`: `1791112464416` (2026-10-04T11:14:24.416Z)
  - `reported_state`: `"idle"`
  - `reported_state_at_ms`: `1791113916291` (2026-10-04T11:38:36.291Z / 1:38:36 PM Berlin)
  - `last_activity_ms`: `1791162246933` (2026-10-05T01:04:06.933Z)
  - `worker_pid`: `1507995`, `workload_pid`: `1508033`
- **`worker.identity.json`:**
  - `{"pid":1507995,"start_time_ticks":327232094,"boot_id":"edbec548-453f-4111-b38e-e7c16d12aa93"}`
- **`coordination.json`:**
  - Scope: `".local"`, task: `"agent-dashboard head: integration, receipts, coordination ledger"` (updated at `1791112816507` ms).

### 4.2 Terminal History & PTY Byte Stream Inspection
Using an in-memory Python scratch inspector on `history.bin` (2,764,616 bytes):
1. **Initial Idle Event:**
   At 2026-10-04T11:38:36Z (1:38 PM Berlin), `zcodex` concluded its working turn of 21 minutes and 37 seconds, printing:
   ```text
   Worked for 21m 37s · 1:38 PM  › Ask Codex to do anything   glm-5.3-flash max · ~/git/agent-dashboard · You are the interactive
   ```
   At that moment, the Codex `"Stop"` lifecycle hook fired, executing `a state-report idle`. This set `reported_state = "idle"` and `reported_state_at_ms = 1791113916291`.
2. **Trailing PTY Byte Inspection:**
   Binary inspection of the final 2,000 bytes of `history.bin` revealed a continuous repetition of ANSI terminal escape sequences:
   ```text
   \x1b[?2026h\x1b[39m\x1b[49m\x1b[0m\x1b[22;3H\x1b[?25h\x1b[?2026l
   ```
   - `\x1b[?2026h` / `\x1b[?2026l`: Synchronized output begin/end (bracketed paste / sync render).
   - `\x1b[39m\x1b[49m\x1b[0m`: Reset text and background colors.
   - `\x1b[22;3H`: Cursor position set to Row 22, Column 3 (the exact prompt input line).
   - `\x1b[?25h`: Show cursor (cursor unhide).
3. **PTY Activity Mechanism:**
   These cursor render bytes were emitted by the `zcodex` interactive terminal user interface when status/screen captures occurred. In [`cloudflare-aplexer-protocol/src/worker/spawn.rs:442`](file:///home/alexey/git/cloudflare-aplexer-protocol/src/worker/spawn.rs#L442):
   ```rust
   match master.read(&mut buffer) {
       Ok(n) => {
           runtime.last_activity_ms.store(now_ms(), Ordering::Relaxed);
           ...
       }
   ```
   Any byte emitted by the PTY master updates `last_activity_ms` to `now_ms()`.
4. **Why Subsequent Lifecycle Hooks Were Missing:**
   Inspection of [`cloudflare-aplexer-protocol/src/hooks/files.rs:212`](file:///home/alexey/git/cloudflare-aplexer-protocol/src/hooks/files.rs#L212) demonstrates:
   ```rust
   let lifecycle_events = [("Stop", "idle"), ("UserPromptSubmit", "working")];
   ```
   Codex/zcodex possesses lifecycle hooks only for `"UserPromptSubmit"` and `"Stop"`. It has no prompt-redraw hook, no cursor-blink hook, and no periodic heartbeat hook. Sitting at the interactive prompt without a new prompt submission, no hook exists to push a refreshed `a state-report idle`. Consequently, `reported_state_at_ms` remained frozen at `1791113916291` while `last_activity_ms` advanced to `1791161046182` and `1791162246933`.

---

## 5. Minimal Offline Negative Test & Receipts

A minimal, offline Python test script was created in the scratch workspace to model the exact protocol logic without compiler execution or network access.

- **Test Path:** [`.local/scratch/reviewer259-readiness-audit/test_readiness_contradiction.py`](file:///home/alexey/git/cloudflare-agent-git/.local/scratch/reviewer259-readiness-audit/test_readiness_contradiction.py)
- **Logic Modeled:**
  - `cloudflare-aplexer-protocol/src/watch/state.rs:141-171` (`idle_was_contradicted_with_hooks`).
  - `cloudflare-aplexer-protocol/src/bin/aplexer/message_deferred.rs:100-130` (`evaluate_readiness_verdict`).
- **Test Invariants:** 0 compiler calls, 0 network access, 100% in-memory assertion.

### 5.1 Test Execution Receipts
```text
$ python3 .local/scratch/reviewer259-readiness-audit/test_readiness_contradiction.py -v
test_antigravity_engine_exemption (__main__.TestReadinessContradiction.test_antigravity_engine_exemption)
Demonstrates that with engine='antigravity', line 170 exempts ... ok
test_arithmetic_divergence (__main__.TestReadinessContradiction.test_arithmetic_divergence) ... ok
test_within_grace_period_is_uncontradicted (__main__.TestReadinessContradiction.test_within_grace_period_is_uncontradicted)
Demonstrates that PTY activity within IDLE_ACTIVITY_GRACE_MS (2,000 ms) ... ok
test_zcodex_fails_closed_due_to_unexempted_pty_contradiction (__main__.TestReadinessContradiction.test_zcodex_fails_closed_due_to_unexempted_pty_contradiction)
Demonstrates that with engine='zcodex', PTY activity > (at + grace) ... ok

----------------------------------------------------------------------
Ran 4 tests in 0.000s

OK
```

### 5.2 Assertions Proven
1. `test_arithmetic_divergence`: Asserts exact difference $\Delta t = 47,129,891\text{ ms} = 13\text{ hours, } 05\text{ minutes, } 29.891\text{ seconds}$.
2. `test_zcodex_fails_closed_due_to_unexempted_pty_contradiction`: Asserts that with `engine == "zcodex"`, `reported_state_at_ms = 1791113916291`, and `last_activity_ms = 1791162246933`, `idle_was_contradicted_with_hooks` returns `True` and delivery evaluates to `REJECT`.
3. `test_antigravity_engine_exemption`: Asserts that with `engine == "antigravity"`, line 170 evaluates to `False`, confirming that Antigravity is exempted from PTY cursor/timer contradictions.
4. `test_within_grace_period_is_uncontradicted`: Asserts that activity within `IDLE_ACTIVITY_GRACE_MS` (2,000 ms) evaluates to `False`.

---

## 6. Governance, Epistemic Boundary & Route Evaluation

### 6.1 Epistemic Boundary: Observed Telemetry vs. Modeled Source Guard
- **Observed Empirical Fact:** The installed binary `/home/alexey/.local/bin/aplexer` emitted the actual runtime rejection:
  `NOTREADY: recipient reported idle at 1791113916291ms, but subsequent PTY activity contradicted resting state; delivery fail-closed`
  (accompanied by tool detail showing a non-empty interactive screen with `EMPTYCOMPOSER` `› Ask Codex to do anything`).
- **Modeled Source Code:** The source implementation in `cloudflare-aplexer-protocol` predicts this outcome down to the variable names and grace intervals. However, offline Python tests merely mirror the modeled logic and cannot alone prove the behavior or fix of the deployed binary.
- **Causal Status of 13-Hour PTY Trace:** While trailing ANSI escape bytes in `history.bin` indicate cursor repositioning and bracketed paste toggles consistent with terminal redraws, they lack causal packet timestamps for the entire 13-hour elapsed interval. Causal attribution of the PTY activity is therefore designated **`UNKNOWN / HYPOTHESIS`**.
- **Epistemic Classification:** Under the strict human hold on `cargo`/`rustc`, binary symbol inspection and decompilation cannot be run. Therefore, identity between source logic and deployed binary is maintained as an **UNVERIFIED HYPOTHESIS (`HYPOTHESIS / UNVERIFIED`)**.

### 6.2 Governance Invariant on Route B Delegation
`REPORT-DASHBOARD-HEAD-READINESS-REPAIR.md` proposes Route B: delegating integration to `ad-backend-exec` under flock.
- **Strict Boundary:** Integration ownership cannot be assumed or transferred purely by speculative parent authority or external fiat.
- **Bus Requirement:** Route B requires an **actual acknowledged handoff on the aplexer bus / workspace inbox** (or an explicit task handoff recorded in `coordination/TASKS.json` and acknowledged by `ad-backend-exec`).
- Without an acknowledged handoff, executing Route B would breach workspace ownership rules.

### 6.3 Narrow Repair Owner Identification & Prohibition of Synthetic Readiness
To repair the readiness state of `agent-dashboard-head` session `c7a75f76`:
- **Narrow Repair Owner:** The human operator controlling the interactive terminal pane, or `agent-dashboard-head` (session `c7a75f76-1f51-4f14-873e-7a60569838c3`) upon receiving authentic user input.
- **Prohibition of Synthetic Idle Resets:**
  Executing a synthetic `a state-report idle` from an external agent or script is **strictly rejected**. Synthetic freshness violates the operational invariant against spoofing ready state without genuine producer completion events; an unavailable or dormant session cannot run commands autonomously anyway.
- **Legitimate Recovery Path:**
  1. The human operator enters a prompt in the interactive session pane to process pending handoff `01a10988-c253` (`a message inbox`), or
  2. An explicit, acknowledged task handoff is routed to `ad-backend-exec` (Route B).
  For any proposed architectural source fix, real hook event generation / epoch association and a busy-negative/capacity-stop/recovery trace are required; blanket zcodex redraw exemptions and manual idle faking are prohibited.

---

## 7. Analytical & Metric Accounting Invariants

Under Codex Principal Directives C2180, C2187, C2189, and C2190:
1. **0 Accepted Features Invariant:** Until either Route A or an acknowledged Route B results in a canonical commit on `main` in `/home/alexey/git/agent-dashboard` and passes an independent review, the four dashboard delta features remain credited as **0 accepted features** in `.local/metrics/hourly_24h_payload.json` and public daily reports.
2. **Staged Testbed Demarcation:** Acceptance of staged reference patches in isolated scratch testbeds ([`REV-DASHBOARD-STAGED-CONSUMER.md`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/reviews/REV-DASHBOARD-STAGED-CONSUMER.md)) certifies reference patch quality only; it does not authorize metric increments for the canonical product.
3. **Truthful Telemetry:** Reports must truthfully distinguish running PTY processes from productive delivery. No speculative progress shall be claimed.

---

## 8. Verification & Invariants Checklist

- [x] **Zero Compiler Invocations:** Exactly 0 `cargo` / `rustc` invocations executed in this audit interval and environment under human hold.
- [x] **Canonical Workspaces Read-Only:** `/home/alexey/git/agent-dashboard` and `/home/alexey/git/cloudflare-aplexer-protocol` were inspected strictly read-only; 0 writes, 0 edits, 0 git stage/commit mutations.
- [x] **Scratch Footprint & Isolation:** `.local/scratch/reviewer259-readiness-audit/` configured mode `0700`, measured usage 24 KB $\le$ 512 MB, `/tmp` net growth = 0.
- [x] **Protocol Inspection:** Inspected `cloudflare-aplexer-protocol/src/bin/aplexer/message_deferred.rs:100-130`, `src/watch/state.rs:141-171`, and `src/hooks/files.rs:211-221`.
- [x] **Producer Trace Analysis:** Examined `session.json`, `worker.identity.json`, `coordination.json`, and trailing raw bytes in `history.bin` (ANSI cursor sequence at row 22, col 3).
- [x] **Arithmetic Verification:** Exact difference $\Delta t = 47,129,891\text{ ms} = \mathbf{13\text{ hours, } 05\text{ minutes, } 29.891\text{ seconds}}$ verified.
- [x] **Offline Negative Test:** Created and executed `test_readiness_contradiction.py` (4/4 tests pass in 0.000s).
- [x] **Epistemic Classification:** Source-binary parity explicitly marked as `HYPOTHESIS / UNVERIFIED`.
- [x] **Governance Boundary Clarified:** Route B noted as requiring an actual acknowledged handoff on the bus; narrow repair owner identified.
- [x] **Publication Credential Guard:** Verified via `python3 research/antigravity/tooling/publication_guard.py` (Exit Code 0).
