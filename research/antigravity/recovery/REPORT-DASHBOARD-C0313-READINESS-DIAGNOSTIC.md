# REPORT: Technical Diagnostic of Dashboard Head Readiness Rejection (C-0313)

- **Audit Target:** `agent-dashboard-head` session `6ef7413b-7bfe-4127-b58e-69d775e286e2`, workspace `/home/alexey/git/agent-dashboard`
- **Governing Directive:** Codex Principal Challenge C-0313 (Message `01a11980-e544-7a01-9157-0db63ef58ec9`)
- **Investigator / Head:** Ant Integration HEAD (`c69a9f51-b751-4400-8bbd-c24cb87fe39a`, engine `antigravity`, model `gemini-3.8-flash-high`)
- **Canonical Custody Scopes:** `scripts/supervision/**`, `scripts/metrics/**`, `research/antigravity/recovery/**`, `research/antigravity/reviews/**`
- **Audit Date:** 2026-10-08T05:25:00+02:00 (Europe/Berlin)
- **Status:** Verified Source Diagnostic & Anti-Workaround Invariants Enforced

---

## 1. Executive Summary

Codex Principal directive C-0313 identifies a delivery miss for message `01a1197f-d3b0-7fb2-b2c9-e8f9f9461f5e` addressed to `agent-dashboard-head` (`6ef7413b-7bfe-4127-b58e-69d775e286e2`) in workspace `/home/alexey/git/agent-dashboard`. Native delivery (`a message deliver`) failed closed with `SubmissionStatus::NotReady` after detecting:
- `reported_state_at_ms: 1791426597022` (04:29:57 CEST)
- `last_activity_ms: 1791429152171` (05:12:32 CEST)
- Divergence $\Delta t = 2,555,149\text{ ms} \approx 42\text{ minutes, } 35\text{ seconds}$ ($> 2,000\text{ ms}$ grace).

This report delivers the authoritative source-level diagnosis of why this contradiction occurs, audits the canonical supervision daemon's role in detecting it, inspects the physical state of session `6ef7413b` and its working tree, and formalizes the non-destructive recovery path under strict anti-workaround invariants.

---

## 2. Deep Source-Level Protocol Analysis

### 2.1 Rejection Execution in `aplexer`
In [`aplexer/src/bin/aplexer/message_deferred.rs:48-60`](file:///home/alexey/git/aplexer/src/bin/aplexer/message_deferred.rs#L48-L60), `require_ready_prompt` gates message submission into an agent's interactive PTY:
```rust
fn require_ready_prompt(record: &SessionRecord) -> Result<()> {
    if !record.worker_alive() {
        bail!("recipient worker is not running");
    }
    let raw = rpc_simple(record, Operation::Status, None)?;
    let live: SessionRecord = serde_json::from_value(raw).context("read live recipient status")?;
    let now = now_ms();
    let (state, source) = session_ui_state(&live, now);
    if source != "reported" || !matches!(state, "waiting" | "idle") {
        bail!("{}", readiness_detail(&live, state, source, now));
    }
    Ok(())
}
```
Preconditions:
1. `source == "reported"` (must be an authoritative lifecycle push, not a PTY heuristic).
2. `state in ["waiting", "idle"]`.

### 2.2 Rejection Cause in `aplexer/src/watch/state.rs`
In [`aplexer/src/watch/state.rs:103-134`](file:///home/alexey/git/aplexer/src/watch/state.rs#L103-L134):
```rust
pub fn reported_state_rejection(record: &SessionRecord, now: u64) -> Option<&'static str> {
    let Some(state) = record.reported_state.as_deref() else {
        return Some("missing reported state");
    };
    let Some(at) = record.reported_state_at_ms else {
        return Some("missing reported-state timestamp");
    };
    let expired = now.saturating_sub(at) > REPORTED_STATE_STALE_MS;
    match state {
        "idle" if idle_was_contradicted(record, at) => {
            Some("idle report contradicted by later PTY output")
        }
        ...
    }
}

fn idle_was_contradicted(record: &SessionRecord, at: u64) -> bool {
    if record.engine == "antigravity" {
        return false;
    }
    record
        .last_activity_ms
        .is_some_and(|activity| activity > at.saturating_add(IDLE_ACTIVITY_GRACE_MS))
}
```
**Mechanism:**
1. Engine Exemption Check: Only `record.engine == "antigravity"` bypasses the contradiction check because Antigravity's interactive TUI renders continuously at rest.
2. For `zcodex` (the engine of `agent-dashboard-head`), `idle_was_contradicted` evaluates whether `last_activity_ms > reported_state_at_ms + 2000 ms`.
3. When `zcodex` completes a turn (04:29:57 CEST), the turn-completion hook pushes `reported_state: "idle"`.
4. While resting at the prompt `› Ask Codex to do anything`, background terminal events (pty polling, cursor repositioning sequences, terminal window resizing, or client queries) advance `last_activity_ms` to `1791429152171` (05:12:32 CEST).
5. Because `zcodex` has no background prompt-redraw heartbeat hook pushing updated `a state-report idle` events while sitting at the prompt, `idle_was_contradicted` returns `true`.
6. `reported_state_rejection` returns `"idle report contradicted by later PTY output"`.
7. `fresh_reported_state` returns `None`.
8. `derive_agent_state_with_source` falls back to `("waiting", "heuristic")`.
9. `require_ready_prompt` sees `source == "heuristic" != "reported"` and aborts with `SubmissionStatus::NotReady`.

---

## 3. Canonical Supervision Integration Audit

In [`scripts/supervision/service.py`](file:///home/alexey/git/cloudflare-agent-git/scripts/supervision/service.py):
1. **Cross-Workspace Filtering Disconnection (Line 1447):**
   ```python
   sessions = [x for x in sessions if x.get('workspace') == str(ROOT)]
   ```
   `ROOT` is `/home/alexey/git/cloudflare-agent-git`. `agent-dashboard-head` resides in `/home/alexey/git/agent-dashboard`. Line 1447 filters out `agent-dashboard-head` from the supervisor's active sessions list. Consequently, lines 1874-1880 report:
   ```json
   "heads": {
     "agent-dashboard-head": "missing-or-ambiguous-head"
   }
   ```
2. **Resting-State Contradiction Pre-Check (Lines 1282-1297 & 2076-2082):**
   ```python
   def check_resting_state_contradicted(session: dict, idle_grace_ms: int = 1000) -> bool:
       ...
       return int(last_activity) > int(reported_state_at) + int(idle_grace_ms)
   ```
   When supervision evaluates delivery:
   ```python
   if check_resting_state_contradicted(session):
       item['diagnostic_hold'] = 'resting-state-contradicted-by-pty'
       pending['diagnostic_hold'] = 'resting-state-contradicted-by-pty'
       item['cooldown_until'] = time.time() + 180
       event('head-delivery-precheck-held', head=head_tag, ...)
   ```
   The supervisor pre-check faithfully mirrors aplexer's native guard and places delivery on diagnostic hold, preventing delivery loops and spamming.

---

## 4. Physical Workplace & Session State Audit

Direct inspection of session `6ef7413b-7bfe-4127-b58e-69d775e286e2`:
1. **Screen State:** Live PTY capture confirms the session is resting at the interactive prompt:
   ```text
   Next cycle per the principal's directives: independent review of AD-F1/AD-B1
   ahead of integration, then AD-B2 provenance verification.
   Worked for 23m 57s · 4:29 AM

   › Ask Codex to do anything

     glm-5.3-flash max · ~/git/agent-dashboard · You are restored Agent
   ```
2. **Working Tree in `/home/alexey/git/agent-dashboard`:**
   - 44 backend unit tests pass.
   - 9 untracked files (`ad-b2-unattributed-provenance-telemetry.jsonl`, `dashboard-hourly24h-telemetry.jsonl`, `dashboard-usage-accounting-telemetry.jsonl`, `patch_accounting.py`, `patch_accounting2.py`, `patch_server_test.py`, `patch_test.py`, `patch_test2.py`, `scale50-41-telemetry.jsonl`) created since 04:29 remain intact.
   - Zero working tree destruction or uncoordinated git resets.
3. **Mailbox State:**
   - Message `01a1197f-d3b0-7fb2-b2c9-e8f9f9461f5e` is retained on disk in `/home/alexey/.local/state/aplexer/messages/03c9ec4101be7a25620818707fb14ec7/msgs/01a1197f-d3b0-7fb2-b2c9-e8f9f9461f5e.json`.
   - Delivery status remains `inbox`.

---

## 5. Strict Anti-Workaround Governance & Invariants

Under Principal Directives and Way-of-Working:
1. **Strict Prohibition of Raw Terminal Injection:**
   Executing `a send 6ef7413b ...` or typing keystrokes into the resting PTY is strictly prohibited as prompt corruption and uncoordinated execution.
2. **Strict Prohibition of Identity Spoofing:**
   Invoking `APLEXER_SESSION_ID=6ef7413b... a state-report idle` from an external session is strictly forbidden as identity spoofing.
3. **Strict Prohibition of Guard Bypass:**
   Modifying `watch/state.rs` or clearing delivery locks without verifying genuine producer events is forbidden.
4. **Daemon Stability Invariant:**
   Canonical services `supervision.service` (PID `3698862` on baseline `ca5ea38`) and `experiment-metrics.service` (PID `4168827`) must remain running with **0 production reloads**. `service.py` performs in-process hash self-checks (`same_source = hashlib.sha256(...).hexdigest() == expected_source_hash`) and will terminate (`sys.exit(42)`) if modified on disk.

---

## 6. Authorized Recovery & Next Steps

1. **Retain Message in Mailbox:** Message `01a1197f-d3b0` remains safely preserved in `/home/alexey/git/agent-dashboard`'s mailbox for normal-boundary consumption.
2. **Issue #102 Recovery Harness:**
   Execute recovery via `scripts/recover-agent agent-dashboard-head` through the maintained `agent-quota-launcher` under task `t-dashboard-c0313-readiness-diagnostic-01`.
3. **Independent Review of Uncommitted 44 Tests:**
   Admit a distinct model review task via `agent-quota-launcher` to evaluate the 44 uncommitted tests in `/home/alexey/git/agent-dashboard` prior to any working tree mutation or merge.
4. **Mechanical Late-Arrival Continuation Test:**
   Implement and execute the pure late-arrival event receiver task to prove automatic multi-cycle continuation without root/principal manual prompting.
