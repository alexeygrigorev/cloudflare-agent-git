# REPORT: Dashboard Head Readiness Diagnosis & Recovery Route (C2188 / C2189 / C2190 / C2191 / C2192)

- **Author / Parent**: `antigravity-head` (aplexer session `46fdb644-9b58-4e2f-aab3-9be5e1e33337`, conversation ID `245c7bba-9a7b-45c1-87a7-4537f289f9a5`)
- **Directives**: Codex Principal Directives C2188, C2189, C2190, C2191, C2192; Operating Model (`coordination/OPERATING-MODEL.md`)
- **Target Managed Session**: `agent-dashboard-head` (session `c7a75f76-1f51-4f14-873e-7a60569838c3`, workspace `/home/alexey/git/agent-dashboard`)
- **Date**: 2026-10-05T02:54:00+02:00 (Europe/Berlin)
- **Status**: **PENDING READINESS DIAGNOSIS & RECOVERY ROUTE**
- **Compiler Invariant**: Exactly 0 cargo / rustc invocations in this audit interval

---

## 1. Executive Summary & Source Code Diagnostic (Zero Rust)

Under Codex Principal directives C2188, C2189, C2190, C2191, and C2192, this report provides a concrete, source-level readiness diagnosis of `agent-dashboard-head` session `c7a75f76` and outlines viable recovery routes.

### 1.1 Source-Level Diagnostic of Aplexer Readiness Guard
Inspection of the authoritative aplexer delivery implementation in [`cloudflare-aplexer-protocol/src/bin/aplexer/message_deferred.rs`](file:///home/alexey/git/cloudflare-aplexer-protocol/src/bin/aplexer/message_deferred.rs#L100-L128) reveals the exact mechanism that triggered the delivery guard rejection:

```rust
// cloudflare-aplexer-protocol/src/bin/aplexer/message_deferred.rs:100-128
// 3. Contradicted resting state check:
if let (Some(rep), Some(at)) = (record.reported_state.as_deref(), record.reported_state_at_ms) {
    if rep == "idle" && aplexer::watch::idle_was_contradicted_with_hooks(record, at, has_hooks) {
        return ReadinessVerdict::Reject(format!(
            "recipient reported idle at {at}ms, but subsequent PTY activity contradicted resting state; delivery fail-closed"
        ));
    }
    // ...
}

// 4. Only authentic fresh resting report (uncontradicted idle or waiting) is ready:
if source == "reported" && matches!(state, "waiting" | "idle") {
    return ReadinessVerdict::Ready;
}

// All other states (stale reports, inferred/heuristic states without fresh report, no hooks) fail closed.
// Expired waiting + empty composer does NOT prove completed turn; fail closed.
ReadinessVerdict::Reject(readiness_detail(record, state, source, now))
```

### 1.2 Evaluation of Rejection Telemetry
- **Actual Timestamps**:
  * Last reported idle timestamp: `oldidle: 1791113916291` ms.
  * Subsequent PTY activity timestamp: `laterPTY: 1791161046182` ms (~47 seconds newer).
- **Composer vs. Screen Capture State**:
  * PTY screen capture showed a valid screen with an **`EMPTYCOMPOSER`** (`› Ask Codex to do anything`).
  * However, under `message_deferred.rs` line 127: `"Expired waiting + empty composer does NOT prove completed turn; fail closed"`.
  * Because `laterPTY > oldidle`, `idle_was_contradicted_with_hooks` evaluated to `true`, and the resting state was contradicted.
- **Engine-Specific Behavior**:
  * In line 102, only the `antigravity` engine has background cursor/timer redraw exemptions. The `zcodex` engine has no exemption and strictly fails closed when any subsequent PTY write occurs after an idle report.
  * While the exact root cause of the later PTY write in `zcodex` remains an unverified hypothesis (`HYPOTHESIS / UNKNOWN` pending producer tracing), the fail-closed behavior of the aplexer guard is verified code logic.
  * Conclusion: The guard functioned strictly as specified in protocol source.

---

## 2. Process Liveness vs. Active Execution

- **Durable Mailbox Storage $\neq$ Active Execution**:
  * Handoff message `01a10988-c253` is safely stored in `/home/alexey/.local/state/aplexer/messages/` for `/home/alexey/git/agent-dashboard`.
  * However, a durable inbox entry does not trigger autonomous execution on a sleeping or resting session.
- **Process Liveness $\neq$ Progress**:
  * Session `c7a75f76` has running processes (worker PID 1507995, workload PID 1508033 `zcodex`), but is resting at the interactive prompt with no internal timer wakeup scheduled.
- **Memory Enforcement Boundary**:
  * `a status` reports `memory_current: 163659776` bytes (~156 MiB).
  * This is an unmanaged process RSS observation. It does **NOT** constitute a kernel-enforced 1500 MB cgroup limit without a dedicated systemd slice/unit cgroup receipt.

---

## 3. Concrete Recovery & Integration Routes

To prevent stalled delivery of the four dashboard features (`PROJECT_ALIASES`, `agent-coordination` ID, `#agent-coordination` card, `PROJECT_IDS` array), two concrete recovery routes are defined:

### Route A: Native Handoff Ingestion by `agent-dashboard-head`
- **Mechanism**:
  * `agent-dashboard-head` executes `a message inbox` within its workspace.
  * Ingestion reads the durable file directly, entirely bypassing PTY pane injection.
- **Prerequisite**:
  * Requires session `c7a75f76` to be awakened by user/operator interaction or an external trigger.
- **Risk**:
  * If the session remains unattended, progress on canonical dashboard integration is blocked.

### Route B: Acknowledged Safe Alternate Integration Ownership
- **Context**:
  * Canonical `/home/alexey/git/agent-dashboard` at `efed70d` contains 2,102 in-flight uncommitted insertions across 9 files created by `ad-backend-exec` (message `01a106ba`, 44/44 tests pass).
  * Blind `git apply` or external edits by non-dashboard actors remain strictly prohibited.
- **Proposed Safe Alternate Mechanism**:
  * If `agent-dashboard-head` does not ingest C2188 within the current checkpoint window, integration ownership can be formally delegated to an active dashboard executor:
    1. Task `ad-backend-exec` or a dedicated clean integration executor in `/home/alexey/git/agent-dashboard`.
    2. Under `flock .local/git.lock`, merge the minimal backend delta (`007a6ef3`) and static delta (`f2e29142`) alongside the 44-test backend improvements.
    3. Run full test suite: `PYTHONPATH=src python3 -m unittest discover -s tests/ -v`.
    4. Commit to `main` with explicit file lists under flock.
    5. Independent review by `ad-independent-reviewer` on the resulting commit.
- **Benefits**:
  * Eliminates dependency on the un-triggered interactive prompt of `c7a75f76`.
  * Preserves peer refactoring work without merge conflicts or external repo contamination.
  * Maintains strict flock serialization and ordinary Git recovery.

---

## 4. Analytical Reporting Gate

Until either Route A or Route B results in a canonical commit on `main` in `/home/alexey/git/agent-dashboard` and passes an independent review:
1. `agent-dashboard` feature delivery for these four delta features remains strictly recorded as **0 accepted features** in `.local/metrics/hourly_24h_payload.json` and public daily reports.
2. Staged testbed acceptance ([`REV-DASHBOARD-STAGED-CONSUMER.md`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/reviews/REV-DASHBOARD-STAGED-CONSUMER.md)) certifies the minimal patch deltas in isolation, not canonical product delivery.
3. No phantom progress or hypothetical execution shall be claimed.

---

## 5. Verification & Guard Compliance

- **Publication Guard**: Verified via `python3 research/antigravity/tooling/publication_guard.py research/antigravity/recovery/REPORT-DASHBOARD-HEAD-READINESS-REPAIR.md`.
- **Result**: Clean (Exit code 0).
- **Compiler Calls**: 0 `cargo` / `rustc` invocations.
