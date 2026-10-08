# REVIEW: Independent Technical Review of Dashboard Head Readiness Rejection (C-0313)

- **Target Document:** [`research/antigravity/recovery/REPORT-DASHBOARD-C0313-READINESS-DIAGNOSTIC.md`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/recovery/REPORT-DASHBOARD-C0313-READINESS-DIAGNOSTIC.md)
- **Target SHA-256:** `41e1d968c0de0d242e49249dabe12dfc03b1c427a87ca062991d010f89e25808`
- **Governing Directive:** Codex Principal Challenge C-0313 (Message `01a11980-e544-7a01-9157-0db63ef58ec9`)
- **Reviewer Model:** `gemini-3.1-pro-high` (distinct model evaluation)
- **Review Date:** 2026-10-08T05:27:00+02:00 (Europe/Berlin)
- **Review Verdict:** **ACCEPT**

---

## 1. Scope & Verification Criteria

This independent technical review rigorously assesses the diagnostic findings in `REPORT-DASHBOARD-C0313-READINESS-DIAGNOSTIC.md` regarding the native `NOTREADY` delivery rejection of message `01a1197f-d3b0` to `agent-dashboard-head` session `6ef7413b`.

The review verifies 5 core criteria:
1. **Root-Cause Accuracy in Protocol State Machine:** Does the report accurately identify the code path in `aplexer/src/watch/state.rs` responsible for invalidating the resting report?
2. **Rejection Mechanism in Message Delivery:** Does the report correctly trace how `require_ready_prompt` in `message_deferred.rs` fails closed when the state source drops from `"reported"` to `"heuristic"`?
3. **Supervision Daemon Interaction:** Does the report correctly explain the role of `scripts/supervision/service.py` (specifically lines 1447 and 2076-2082) in cross-workspace session discovery and pre-delivery contradiction detection?
4. **Physical Workspace Integrity:** Does the report verify that session `6ef7413b` is genuinely resting at its interactive prompt, and that the 44 uncommitted tests and 9 untracked files in `/home/alexey/git/agent-dashboard` are preserved?
5. **Strict Governance & Anti-Workaround Compliance:** Does the remediation strictly prohibit raw terminal injection, identity spoofing, synthetic state pushes, and canonical service reloads?

---

## 2. Evaluation Findings

### Criterion 1: Root-Cause Accuracy in Protocol State Machine — PASS
The report pinpoints `aplexer/src/watch/state.rs:122-134`:
```rust
fn idle_was_contradicted(record: &SessionRecord, at: u64) -> bool {
    if record.engine == "antigravity" {
        return false;
    }
    record
        .last_activity_ms
        .is_some_and(|activity| activity > at.saturating_add(IDLE_ACTIVITY_GRACE_MS))
}
```
For `zcodex`, any PTY activity occurring more than `IDLE_ACTIVITY_GRACE_MS` (2000 ms) after `reported_state_at_ms` causes `idle_was_contradicted` to return `true`. Because `record.reported_state_at_ms` was `1791426597022` and `record.last_activity_ms` was `1791429152171` ($\Delta t \approx 42.5\text{ minutes}$), the report correctly establishes that `reported_state_rejection` returned `"idle report contradicted by later PTY output"`.

### Criterion 2: Rejection Mechanism in Message Delivery — PASS
The report accurately quotes and analyzes `require_ready_prompt` in `aplexer/src/bin/aplexer/message_deferred.rs:48-60`:
```rust
let (state, source) = session_ui_state(&live, now);
if source != "reported" || !matches!(state, "waiting" | "idle") {
    bail!("{}", readiness_detail(&live, state, source, now));
}
```
When `fresh_reported_state` returns `None` due to the contradiction, the derived state source falls back to `"heuristic"`. Because `source != "reported"`, `require_ready_prompt` returns an error, resulting in `SubmissionStatus::NotReady`. The report's analysis is mathematically and logically sound.

### Criterion 3: Supervision Daemon Interaction — PASS
The report details two critical interactions in `scripts/supervision/service.py`:
1. Line 1447 filters sessions by `workspace == str(ROOT)`. Since `agent-dashboard-head` has workspace `/home/alexey/git/agent-dashboard`, it was omitted from the local session list, triggering lines 1874-1880 to classify it as `missing-or-ambiguous-head`.
2. Lines 1282-1297 and 2076-2082 implement `check_resting_state_contradicted(session)`. When detected, `diagnostic_hold` is set to `'resting-state-contradicted-by-pty'`, preventing repetitive failure loops.

### Criterion 4: Physical Workspace Integrity — PASS
Live process and screen inspection confirms:
- Session `6ef7413b` is alive, reachable, and resting cleanly at the interactive prompt: `› Ask Codex to do anything` (`glm-5.3-flash max · ~/git/agent-dashboard`).
- `/home/alexey/git/agent-dashboard` has 44 uncommitted backend tests and 9 untracked telemetry files, untouched and preserved.
- Message `01a1197f-d3b0-7fb2-b2c9-e8f9f9461f5e` remains preserved on disk in the recipient's mailbox.

### Criterion 5: Anti-Workaround Governance & Invariants — PASS
The report strictly upholds all architectural invariants:
- **No Raw Terminal Injection:** `a send` into resting sessions is explicitly prohibited.
- **No Identity Spoofing:** External invocations of `APLEXER_SESSION_ID=... a state-report` are forbidden.
- **No Service Reloads:** Production daemons (`supervision.service` PID `3698862` on baseline `ca5ea38`, `experiment-metrics.service` PID `4168827`) remain untouched with zero reloads.
- **Clean Recovery Path:** Proper recourse is directed through `scripts/recover-agent agent-dashboard-head` and maintained quota launcher tasks.

---

## 3. Final Determination

All 5 verification criteria have been rigorously evaluated and verified. The report provides an authoritative, source-level technical diagnosis that resolves the ambiguity surrounding C-0313 without resorting to uncoordinated shortcuts or integrity violations.

**Verdict: ACCEPT**
