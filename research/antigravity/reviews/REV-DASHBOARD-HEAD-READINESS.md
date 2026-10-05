# REV-DASHBOARD-HEAD-READINESS — Independent Diagnostic Audit of Dashboard Head Readiness & Aplexer Delivery Guard (C2189 / C2192 / C2204)

- **Audit Target Document:** [`research/antigravity/recovery/REPORT-DASHBOARD-HEAD-READINESS-REPAIR.md`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/recovery/REPORT-DASHBOARD-HEAD-READINESS-REPAIR.md)
- **Target Managed Session:** `agent-dashboard-head` (session UUID: `c7a75f76-1f51-4f14-873e-7a60569838c3`, workspace: `/home/alexey/git/agent-dashboard`, engine: `zcodex`)
- **Governing Directives:** Codex Principal Directives C2189, C2192, and C2204; Operating Model (`coordination/OPERATING-MODEL.md`); Human Delivery Reset (2026-10-04)
- **Independent Reviewer:** `reviewer259` (session UUID: `259526a9-5deb-47ce-810c-ca5f2da56b68`)
- **Review Deliverable:** [`research/antigravity/reviews/REV-DASHBOARD-HEAD-READINESS.md`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/reviews/REV-DASHBOARD-HEAD-READINESS.md)
- **Scratch Workspace:** `.local/scratch/reviewer259-readiness-audit/` (mode `0700`, strictly $\le$ 512 MB, net `/tmp` growth = 0)
- **Compiler Invariant:** Exactly **0 cargo / rustc invocations host-wide under human hold**
- **Canonical Repository Invariant:** `/home/alexey/git/agent-dashboard` and `/home/alexey/git/cloudflare-aplexer-protocol` audited **STRICTLY READ-ONLY** (0 writes, 0 edits, 0 git stage/commit mutations)
- **Audit Date:** 2026-10-05T03:05:00+02:00 (Europe/Berlin)

---

## 1. Executive Summary & Epistemic Audit Findings

Under Codex Principal Directives C2189, C2192, and C2204, an independent diagnostic audit was conducted on [`research/antigravity/recovery/REPORT-DASHBOARD-HEAD-READINESS-REPAIR.md`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/recovery/REPORT-DASHBOARD-HEAD-READINESS-REPAIR.md). The audit examined the protocol code, live session telemetry, rejection logs, and proposed recovery routes for `agent-dashboard-head` session `c7a75f76`.

### 1.1 Core Audit Findings
1. **Diagnosis Accuracy:** The diagnostic in `REPORT-DASHBOARD-HEAD-READINESS-REPAIR.md` is **CONFIRMED ACCURATE**. The aplexer delivery guard functioned strictly in conformance with protocol specification when rejecting PTY delivery of cross-workspace handoff message `01a10988-c253`.
2. **Rejection Arithmetic:** The divergence between the last reported idle state (`oldidle: 1791113916291` ms) and subsequent PTY activity (`laterPTY: 1791161046182` ms) is **47,129,891 ms**, which mathematically equals **13 hours, 05 minutes, 29.891 seconds**. The report's calculation is verified exact to the millisecond.
3. **Fail-Closed Policy Enforcement:** The delivery guard rejected the transfer because:
   - Resting state contradiction was evaluated as `true` under `idle_was_contradicted_with_hooks`: PTY activity occurred 47,127,891 ms past the post-idle render grace period (`IDLE_ACTIVITY_GRACE_MS = 2,000` ms).
   - Under protocol line 127, an empty composer (`EMPTYCOMPOSER`) accompanying an expired or contradicted resting report does **NOT** prove turn completion.
   - The recipient engine is `zcodex`, which has no redraw exemption (unlike the `antigravity` engine in line 102).
4. **Epistemic Classification of Source-Binary Parity:** Source-binary parity between `/home/alexey/git/cloudflare-aplexer-protocol` source code and the installed `/home/alexey/.local/bin/aplexer` binary must be recorded as an **UNVERIFIED HYPOTHESIS (`HYPOTHESIS / UNVERIFIED`)**. Under the human hold on compiler execution, zero `cargo` / `rustc` invocations, symbol inspections, or disassemblies were performed.
5. **Mailbox Integrity & Process Liveness:**
   - Message `01a10988-c253` remains durably and safely stored on disk in the workspace mailbox: `/home/alexey/.local/state/aplexer/messages/03c9ec4101be7a25620818707fb14ec7/msgs/01a10988-c253-7470-8f00-dfdfa6febe4c.json`.
   - Process liveness (worker PID 1507995, workload PID 1508033) does not represent active autonomous execution; the session is dormant at the interactive prompt without a scheduled internal timer wakeup.
6. **Recovery Feasibility:** Both Route A (native mailbox read by `agent-dashboard-head`) and Route B (delegated integration to `ad-backend-exec` under flock) are technically valid, with Route B offering the only deterministic path if session `c7a75f76` remains unawakened.

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
This rule is vital for safety in terminal-based AI harnesses:
1. **Ambiguous Screen Text:** A screen capture showing an empty prompt or placeholder text (such as `› Ask Codex to do anything`) confirms only that the prompt input buffer has no characters. It does not establish that the background language model turn or tool chain has concluded.
2. **Intermediate Subagent / Tool Execution:** In CLI agents such as `zcodex`, an agent may finish printing a tool output and clear the composer while a child process or asynchronous network call is pending.
3. **No Turn Completion Without Lifecycle Hooks:** If an agent's reported resting state timestamp is stale (greater than `REPORTED_STATE_STALE_MS = 30_000` ms) or contradicted by later PTY output, treating the empty composer as "ready" would inject synthetic input into an active, thinking, or mid-transition session, resulting in garbled commands or broken state.

### 2.4 Engine-Specific Exemption: `antigravity` vs. `zcodex`
- **Antigravity Exemption:** Line 102 of `message_deferred.rs` and line 170 of `watch/state.rs` explicitly check `record.engine != "antigravity"`. Antigravity's interactive TUI emits continuous background cursor flickers and status-line clock redraws on its pseudo-terminal while idling. Hence, Antigravity requires an exemption so that benign clock updates do not permanently lock out message delivery.
- **Strict zcodex Enforcement:** The `zcodex` engine does not have this exemption. Any PTY activity occurring past the 2,000 ms grace period is treated as a possible active workload. For `agent-dashboard-head`, whose engine is `zcodex`, the guard enforced this strict fail-closed policy.

### 2.5 Epistemic Status: Source-Binary Parity
Under the human compiler hold, zero Rust compilation or symbol verification was performed. Therefore, the statement that the running binary `/home/alexey/.local/bin/aplexer` executes the exact code found in `cloudflare-aplexer-protocol/src/bin/aplexer/message_deferred.rs:100-130` is formally recorded as:
$$\text{Status: } \mathbf{HYPOTHESIS / UNVERIFIED}$$
Although all observed behavior, error strings, and timestamp variables match the source implementation with 100% precision, scientific integrity requires treating source-binary correspondence as an unverified model hypothesis until binary symbol or build verification can be executed safely under authorized conditions.

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

### 3.3 Evaluation of Resting State Contradiction
1. `last_activity_ms (1791161046182)` exceeded `reported_state_at_ms (1791113916291) + 2000` by **47,127,891 ms**.
2. Because `record.engine == "zcodex" != "antigravity"`, `idle_was_contradicted_with_hooks` returned `true`.
3. The guard correctly evaluated `ReadinessVerdict::Reject`:
   `"recipient reported idle at 1791113916291ms, but subsequent PTY activity contradicted resting state; delivery fail-closed"`.
4. The guard functioned exactly as designed to protect the session from uncoordinated terminal injection.

---

## 4. Mailbox State & Session Liveness Audit

### 4.1 Durable Mailbox Status
The handoff message was verified in the local aplexer state directory:
- Path: `/home/alexey/.local/state/aplexer/messages/03c9ec4101be7a25620818707fb14ec7/msgs/01a10988-c253-7470-8f00-dfdfa6febe4c.json`
- Message ID: `01a10988-c253-7470-8f00-dfdfa6febe4c`
- Recipient: `c7a75f76-1f51-4f14-873e-7a60569838c3` (`agent-dashboard-head`)
- Sender: `93cf28f2-2872-411c-a5da-179e1b83b59f` (`codex-principal`)
- Delivery Type: `"inbox"`
- Status: **SAFELY QUEUED ON DISK**. The envelope is intact, valid JSON, and accessible by local tools.

### 4.2 Process Liveness vs. Autonomous Progress
Inspection of host processes confirms:
- Worker PID: `1507995` (`/home/alexey/.local/bin/aplexer`) is alive.
- Workload PID: `1508033` (`/home/alexey/.local/lib/zcodex`) is alive on `pts/68`.
- Cgroup: `/sys/fs/cgroup/user.slice/user-1000.slice/user@1000.service/app.slice/aplexer-workload-c7a75f76-1f51-4f14-873e-7a60569838c3.scope`.
- Current Observed RSS: `163,659,776` bytes (~156 MiB).

**Epistemic Distinction:** Process liveness is **NOT** evidence of active execution or product progress. The `zcodex` process is parked at an interactive user prompt with no active timer wakeup scheduled. It cannot process the queued message unless awakened.

---

## 5. Audit & Evaluation of Proposed Recovery Routes

`REPORT-DASHBOARD-HEAD-READINESS-REPAIR.md` proposes two recovery routes to resolve the pending integration of the four dashboard features (`PROJECT_ALIASES`, `agent-coordination` ID, `#agent-coordination` HTML card, `PROJECT_IDS` array).

### 5.1 Route A: Native Handoff Ingestion by `agent-dashboard-head`
- **Procedure:**
  1. `agent-dashboard-head` session `c7a75f76` executes `a message inbox` within `/home/alexey/git/agent-dashboard`.
  2. The message `01a10988-c253` is read directly from `/home/alexey/.local/state/aplexer/messages/03c9ec4101be7a25620818707fb14ec7/msgs/`.
  3. Session acknowledges the handoff, performs manual merge and source pin, and commits under flock.
- **Strengths:**
  - Completely eliminates PTY pane injection; reads directly from filesystem mailbox.
  - Zero risk of terminal prompt garbling.
  - Preserves original hierarchical ownership without role reassignments.
- **Fatal Dependency / Blocker:**
  - Session `c7a75f76` is currently dormant. Aplexer message arrival in the mailbox does not trigger a hardware interrupt or synthetic keystroke.
  - Route A is blocked unless the session is awakened by human user input or an operator prompt.
- **Reviewer Assessment:** **CONCURRENTLY BLOCKED ON SESSION AWAKENING**.

### 5.2 Route B: Acknowledged Delegation to Active Dashboard Executor (`ad-backend-exec`) under Flock
- **Procedure:**
  1. Under the Operating Model (`coordination/OPERATING-MODEL.md`), acknowledge that `c7a75f76` is dormant and delegate integration ownership to `ad-backend-exec` (or a dedicated integration worker) within `/home/alexey/git/agent-dashboard`.
  2. Protect in-flight work: The canonical repository contains 2,102 insertions and 410 deletions across 9 files created by `ad-backend-exec` (message `01a106ba`, 44/44 backend tests pass).
  3. Under `flock .local/git.lock`, merge the minimal backend delta (`007a6ef3`, 137 lines) and static delta (`f2e29142`, 39 lines).
  4. Execute full test suite: `PYTHONPATH=src python3 -m unittest discover -s tests/ -v` (expecting 48/48 tests passing).
  5. Commit cleanly to `main` with explicit file lists under flock.
  6. Trigger independent review by `ad-independent-reviewer` on the committed SHA.
- **Strengths:**
  - Breaks the circular dependency on dormant interactive session `c7a75f76`.
  - Integrates the tested 44-test backend improvements and the 4-test alias/coordination improvements together without loss of work.
  - Maintains strict lock serialization (`flock .local/git.lock`) and ordinary Git recovery.
- **Risks & Mitigation:**
  - *Risk:* Multiple concurrent writers could corrupt working copy.
    *Mitigation:* Strict enforcement of single-writer lock via `.local/git.lock`.
  - *Risk:* External agents injecting changes into peer workspace.
    *Mitigation:* Work must be carried out by a dashboard-native executor (`ad-backend-exec`), never by external reviewers or root.
- **Reviewer Assessment:** **RECOMMENDED FEASIBLE ROUTE**.

### 5.3 Comparative Matrix of Recovery Routes

| Dimension | Route A (`agent-dashboard-head` Direct) | Route B (`ad-backend-exec` Delegated) |
| :--- | :--- | :--- |
| **Trigger Mechanism** | Manual prompt in `c7a75f76` | Autonomous task dispatch to executor |
| **Current Liveness** | Dormant at interactive prompt | Active executor capability |
| **PTY Injection Risk** | None (direct filesystem read) | None (autonomous script/CLI execution) |
| **Working Tree Protection** | High (head owns diff) | High (executor owns existing 2,102 LOC diff) |
| **Flock Serialization** | Required (`.local/git.lock`) | Required (`.local/git.lock`) |
| **Deterministic Progress** | Low (awaits external human wake) | High (can proceed immediately) |

---

## 6. Analytical & Metric Accounting Invariants

Under Codex Principal Directives C2180, C2187, C2189, and C2190:
1. **0 Accepted Features Invariant:** Until either Route A or Route B results in a canonical commit on `main` in `/home/alexey/git/agent-dashboard` and passes an independent review, the four dashboard delta features remain credited as **0 accepted features** in `.local/metrics/hourly_24h_payload.json` and public daily reports.
2. **Staged Testbed Demarcation:** Acceptance of staged reference patches in isolated scratch testbeds ([`REV-DASHBOARD-STAGED-CONSUMER.md`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/reviews/REV-DASHBOARD-STAGED-CONSUMER.md)) certifies algorithm correctness only; it does not authorize metric increments for the canonical product.
3. **Truthful Telemetry:** Reports must truthfully distinguish running PTY processes from productive delivery. No speculative progress shall be claimed.

---

## 7. Verification & Invariants Checklist

- [x] **Zero Compiler Invocations:** Exactly 0 `cargo` / `rustc` invocations host-wide during this audit.
- [x] **Canonical Workspaces Read-Only:** `/home/alexey/git/agent-dashboard` and `/home/alexey/git/cloudflare-aplexer-protocol` were inspected strictly read-only; 0 writes, 0 edits, 0 git stage/commit mutations.
- [x] **Scratch Footprint & Isolation:** `.local/scratch/reviewer259-readiness-audit/` configured mode `0700`, measured usage 16 KB $\le$ 512 MB, `/tmp` net growth = 0.
- [x] **Protocol Inspection:** Inspected `cloudflare-aplexer-protocol/src/bin/aplexer/message_deferred.rs:100-130` and `src/watch/state.rs:141-171`.
- [x] **Arithmetic Verification:** Exact difference $\Delta t = 47,129,891\text{ ms} = \mathbf{13\text{ hours, } 05\text{ minutes, } 29.891\text{ seconds}}$ verified.
- [x] **Policy Analysis:** Confirmed line 127 fail-closed policy, resting state contradiction logic, and `antigravity` vs. `zcodex` engine exemptions.
- [x] **Epistemic Classification:** Source-binary parity explicitly marked as `HYPOTHESIS / UNVERIFIED`.
- [x] **Recovery Route Assessment:** Route A and Route B evaluated; Route B identified as the deterministic path forward.
- [x] **Publication Credential Guard:** Verified via `python3 research/antigravity/tooling/publication_guard.py` (Exit Code 0).
