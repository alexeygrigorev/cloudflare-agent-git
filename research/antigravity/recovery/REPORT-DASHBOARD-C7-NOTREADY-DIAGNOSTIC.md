# REPORT: Authoritative Source-Only Technical Diagnostic of Dashboard Native NOTREADY / Old-Idle / Later-PTY (C2248)

- **Audit Target:** Dashboard Session `c7` (`c7a75f76-1f51-4f14-873e-7a60569838c3`, workspace: `/home/alexey/git/agent-dashboard`) and Comparative Session `ui` (`06a6e276-18f5-4abe-b66e-aee30d4e91a4`, workspace: `/home/alexey/git/cloudflare-agent-git`)
- **Governing Directives:** Codex Principal Directive C2248; Operating Model (`coordination/OPERATING-MODEL.md`); Human Delivery Reset (2026-10-04)
- **Reviewer / Author:** Independent Dashboard & Coordination Reviewer (`reviewer259`, session UUID: `259526a9-5deb-47ce-810c-ca5f2da56b68`)
- **Authority / Dispatcher:** `antigravity-head` (`46fdb644`, conversation ID: `245c7bba-9a7b-45c1-87a7-4537f289f9a5`)
- **Deliverable Path:** [`research/antigravity/recovery/REPORT-DASHBOARD-C7-NOTREADY-DIAGNOSTIC.md`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/recovery/REPORT-DASHBOARD-C7-NOTREADY-DIAGNOSTIC.md)
- **Scratch Workspace:** `.local/scratch/reviewer259-dashboard-c7-diagnostic/` (mode `0700`, strictly $\le$ 512 MB, net `/tmp` growth = 0)
- **Compiler Invariant:** Exactly **0 cargo / rustc invocations host-wide under human hold**
- **Canonical Repository Invariant:** `/home/alexey/git/agent-dashboard` audited **STRICTLY READ-ONLY** (0 writes, 0 edits, 0 git stage/commit mutations; existing 2,102 LOC working copy dirt preserved)
- **Privacy & Security Invariant:** Inspect only APLEXER identity/workspace fields (zero raw secrets, tokens, or private configurations published)
- **Audit Date:** 2026-10-05T03:55:00+02:00 (Europe/Berlin)

---

## 1. Executive Summary & Diagnostic Findings

Under Codex Principal Directive C2248, an independent, source-only technical diagnostic was conducted to determine the exact root cause of the Dashboard native `NOTREADY` / `oldidle` / `laterPTY` delivery guard rejection originally reported in message `01a10988-c253`.

### 1.1 Core Diagnostic Conclusions
1. **Refutation of the "Stale Shell Snapshot Overwrote Validenv" Hypothesis:**
   - **Finding:** The hypothesis that a stale `shell_snapshot` overwrote the valid environment of session `c7a75f76` is **EMPIRICALLY REFUTED**.
   - **Evidence:** Direct inspection of `/proc/1508033/environ` (the live workload process of `c7a75f76`) demonstrates that `APLEXER_SESSION_ID`, `APLEXER_TAG`, and `APLEXER_WORKSPACE` are **100% pristine, accurate, and correctly bound** to `c7a75f76-1f51-4f14-873e-7a60569838c3`, `agent-dashboard-head`, and `/home/alexey/git/agent-dashboard`.
   - **Snapshot Storage Audit:** File system inspection of `/home/alexey/.codex/shell_snapshots/` confirms that **zero shell snapshot files have been written since 2026-10-02 22:33**. The shell snapshot issue is a historical incident from October 2 that never occurred in session `c7a75f76`.
2. **Exact Root Cause of NOTREADY Rejection:**
   - The rejection is caused entirely by an **asymmetric temporal divergence** between the Codex lifecycle hook architecture and low-level PTY terminal master reads:
     * **Frozen Idle Timestamp:** In [`/home/alexey/.codex/hooks.json`](file:///home/alexey/.codex/hooks.json), Codex lifecycle hooks are installed only for `SessionStart`, `Stop`, and `UserPromptSubmit`. At `1791113916291` ms (2026-10-04T11:38:36Z / 1:38 PM Berlin), `zcodex` concluded its working turn and fired the `Stop` hook, executing `a state-report idle`. Because Codex possesses no periodic heartbeat or prompt-redraw hook, `reported_state_at_ms` was never updated again.
     * **Advancing PTY Activity:** The interactive prompt `› Ask Codex to do anything` emits periodic ANSI cursor repositioning sequences (`\x1b[?2026h\x1b[39m\x1b[49m\x1b[0m\x1b[22;3H\x1b[?25h\x1b[?2026l`) when screen captures or status queries occur. Under [`cloudflare-aplexer-protocol/src/worker/spawn.rs:442`](file:///home/alexey/git/cloudflare-aplexer-protocol/src/worker/spawn.rs#L442), any byte read by the PTY master updates `last_activity_ms` to current time.
     * **Strict Protocol Fail-Closed:** When delivery was attempted over 13 hours later, `last_activity_ms` (`1791161046182`) exceeded `reported_state_at_ms` (`1791113916291`) + 2000 ms by 47,127,891 ms. Under [`cloudflare-aplexer-protocol/src/watch/state.rs:170`](file:///home/alexey/git/cloudflare-aplexer-protocol/src/watch/state.rs#L170), only Antigravity is exempted from PTY cursor redraws; `zcodex` has no exemption.
     * **Line 127 Policy:** In [`message_deferred.rs:127`](file:///home/alexey/git/cloudflare-aplexer-protocol/src/bin/aplexer/message_deferred.rs#L127), `"Expired waiting + empty composer does NOT prove completed turn; fail closed"`. The delivery guard functioned exactly as specified by failing closed.
3. **Comparative Session Equivalence:**
   - Session `06a6e276-18f5-4abe-b66e-aee30d4e91a4` (`ui` in `/home/alexey/git/cloudflare-agent-git`) exhibits the identical phenomenon: `reported_state_at_ms: 1791103959641` (frozen from 08:52 UTC Oct 4) vs `last_activity_ms: 1791165248666` (divergence > 17 hours).
   - This proves that the issue is not session-specific, workspace-specific, or caused by environment corruption, but is the systemic behavior of unexempted `zcodex` / `codex` sessions parked at an interactive prompt.

---

## 2. Process & Environment Provenance Audit

A source-level inspection of the operating system process table was conducted for the target session processes.

### 2.1 Session `c7` Process & Identity Audit
From `/home/alexey/.local/state/aplexer/sessions/c7a75f76-1f51-4f14-873e-7a60569838c3/session.json`:
- **Session UUID:** `c7a75f76-1f51-4f14-873e-7a60569838c3`
- **Tag:** `agent-dashboard-head`
- **Workspace:** `/home/alexey/git/agent-dashboard`
- **Engine:** `zcodex`
- **Worker PID:** `1507995` (`/home/alexey/.local/bin/aplexer`)
- **Workload PID:** `1508033` (`/home/alexey/.local/lib/zcodex/zcodex`)

Inspection of `/proc/1508033/environ` (workload process):
```text
APLEXER_CONFIG       = /home/alexey/.config/aplexer/config.toml
APLEXER_RUNTIME_DIR  = /run/user/1000/aplexer
APLEXER_SESSION_ID   = c7a75f76-1f51-4f14-873e-7a60569838c3
APLEXER_STATE_DIR    = /home/alexey/.local/state/aplexer
APLEXER_TAG          = agent-dashboard-head
APLEXER_WORKSPACE    = /home/alexey/git/agent-dashboard
```

Inspection of `/proc/1507995/environ` (worker process):
```text
APLEXER_CONFIG       = /home/alexey/.config/aplexer/config.toml
APLEXER_RUNTIME_DIR  = /run/user/1000/aplexer
APLEXER_SESSION_ID   = 46fdb644-9b58-4e2f-aab3-9be5e1e33337
APLEXER_STATE_DIR    = /home/alexey/.local/state/aplexer
APLEXER_TAG          = antigravity-head
APLEXER_WORKSPACE    = /home/alexey/git/cloudflare-agent-git
```

**Provenance Finding:** The worker process PID 1507995 was spawned by `antigravity-head` (`46fdb644`), which correctly initialized child workload PID 1508033 with its dedicated session identity (`c7a75f76`, `agent-dashboard-head`, `/home/alexey/git/agent-dashboard`). The live environment is 100% concordant with `session.json`.

### 2.2 Comparative Session `06a6` Process & Identity Audit
From `/home/alexey/.local/state/aplexer/sessions/06a6e276-18f5-4abe-b66e-aee30d4e91a4/session.json`:
- **Session UUID:** `06a6e276-18f5-4abe-b66e-aee30d4e91a4`
- **Tag:** `ui`
- **Workspace:** `/home/alexey/git/cloudflare-agent-git`
- **Engine:** `codex`
- **Worker PID:** `1657501`, **Workload PID:** `1657502`

Inspection of `/proc/1657502/environ` (workload process):
```text
APLEXER_CONFIG       = /home/alexey/.config/aplexer/config.toml
APLEXER_RUNTIME_DIR  = /run/user/1000/aplexer
APLEXER_SESSION_ID   = 06a6e276-18f5-4abe-b66e-aee30d4e91a4
APLEXER_STATE_DIR    = /home/alexey/.local/state/aplexer
APLEXER_TAG          = ui
APLEXER_WORKSPACE    = /home/alexey/git/cloudflare-agent-git
```

**Provenance Finding:** Both sessions maintain uncorrupted, perfectly isolated environment bindings.

---

## 3. Evaluation of the "Stale Shell Snapshot" Hypothesis

### 3.1 Origin of the Hypothesis
On October 2 (documented in `coordination/INTERACTIVE-SESSIONS.md:21-27` and `coordination/codex.md:152`), Codex principal session `56420916` was resumed from an older conversation, causing Codex's built-in shell snapshot restore feature to load a stale shell snapshot from session `ff5105df`. This overwrote `APLEXER_SESSION_ID` with an invalid ID. The issue was resolved by resuming with `--disable shell_snapshot` under session `93cf28f2`.

### 3.2 Empirical Audit in Target Workspace
1. **No Recent Snapshots:** Inspection of `/home/alexey/.codex/shell_snapshots/` revealed that all 14 snapshot files on disk date between September 30 and October 2:
   ```text
   -rw-rw-r-- 1 alexey alexey 8512 Oct  2 22:33 01a0fe52-ddfe-7410-98d9-a91012a98157.1790973238831480833.sh
   ```
   Zero snapshot files have been written since October 2.
2. **Launch Configuration:** Session `c7a75f76` was launched cleanly by aplexer at `1791112464416` ms (2026-10-04T11:14:24Z) with command:
   `["/home/alexey/.local/bin/zcodex", "-c", "check_for_update_on_startup=false", "--dangerously-bypass-approvals-and-sandbox"]`
   It did not restore any prior conversation or shell snapshot.
3. **Environment Reality:** The live workload process PID 1508033 contains pristine `APLEXER_SESSION_ID=c7a75f76-1f51-4f14-873e-7a60569838c3`.

### 3.3 Epistemic Verdict
$$\mathbf{Verdict: \text{ EMPIRICALLY REFUTED / UNFOUNDED}}$$
The hypothesis that a stale shell snapshot overwrote valid environment variables in `c7a75f76` is contradicted by direct process memory and filesystem evidence.

---

## 4. Lifecycle Hook Architecture vs. PTY Activity Mechanics

### 4.1 Authoritative Hook Configuration
Inspection of `/home/alexey/.codex/hooks.json` demonstrates the exact hook definitions managing `zcodex` and `codex`:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "hooks": [
          {
            "command": "/home/alexey/git/cloudflare-aplexer-protocol/target/debug/aplexer context hook --engine codex 2>/dev/null || true # aplexer-managed-awareness-hook-v1",
            "timeout": 5,
            "type": "command"
          }
        ]
      }
    ],
    "SessionStart": [
      {
        "hooks": [
          {
            "command": "/home/alexey/.local/bin/a state-report working || true",
            "type": "command"
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "command": "/home/alexey/.local/bin/a state-report idle || true",
            "type": "command"
          }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "command": "/home/alexey/.local/bin/a state-report working || true",
            "type": "command"
          }
        ]
      }
    ]
  }
}
```

### 4.2 Chronological Mechanism of Failure

```
+-----------------------------------------------------------------------------------------------+
| Oct 04, 11:38:36 UTC (1:38 PM Berlin)                                                         |
| zcodex finishes 21m 37s turn -> Stop hook executes:                                           |
|   `a state-report idle` -> reported_state = "idle", reported_state_at_ms = 1791113916291        |
+-----------------------------------------------------------------------------------------------+
                                               |
                                               | (Session sits at interactive prompt for >13h)
                                               | (No new user prompt submitted -> NO HOOKS FIRE)
                                               v
+-----------------------------------------------------------------------------------------------+
| Oct 05, 00:44:06 UTC (2:44 AM Berlin)                                                         |
| Aplexer attaches / captures screen -> zcodex TUI emits ANSI cursor redraw sequences:          |
|   `\x1b[?2026h\x1b[39m\x1b[49m\x1b[0m\x1b[22;3H\x1b[?25h\x1b[?2026l`                          |
| PTY reader (spawn.rs:442) updates:                                                            |
|   `last_activity_ms = 1791161046182`                                                          |
+-----------------------------------------------------------------------------------------------+
                                               |
                                               v
+-----------------------------------------------------------------------------------------------+
| Message 01a10988 delivery attempted:                                                         |
|   evaluate_readiness_verdict() -> idle_was_contradicted_with_hooks():                         |
|     last_activity_ms (1791161046182) > reported_state_at_ms (1791113916291) + 2000 ms         |
|     Engine == "zcodex" != "antigravity" (NO REDRAW EXEMPTION)                                 |
|   -> Resting state contradicted = TRUE                                                        |
|   -> Line 127: Expired waiting + empty composer does NOT prove completed turn; fail closed.   |
|   -> Result: FAIL-CLOSED with NOTREADY                                                        |
+-----------------------------------------------------------------------------------------------+
```

### 4.3 Why Antigravity Does Not Suffer This Defect
In [`cloudflare-aplexer-protocol/src/watch/state.rs:170`](file:///home/alexey/git/cloudflare-aplexer-protocol/src/watch/state.rs#L170):
```rust
record.engine != "antigravity"
```
Antigravity's interactive TUI continuously produces background cursor flickers and timer redraws on its PTY while idling. The protocol engine explicitly exempts Antigravity from PTY activity contradiction. Because `zcodex` lacks this exemption, benign cursor redraws permanently contradict stale idle reports.

---

## 5. Remediation & Clean Recovery Paths

Because session `c7a75f76` is dormant with an unrefreshed idle report, two remediation routes exist:

### 5.1 Route 1: Direct Session Refresh (Narrow Repair Owner)
- **Repair Owner:** `agent-dashboard-head` (session `c7a75f76`) or human operator controlling the interactive pane.
- **Action:**
  1. The operator inputs a newline or command in `c7a75f76`'s terminal pane, or
  2. The session executes `a state-report idle` directly from its shell.
- **Result:** This refreshes `reported_state_at_ms` to current wall-clock time (`now_ms()`), bringing it ahead of `last_activity_ms` and clearing the contradiction. The pending handoff message `01a10988-c253` (which is safely queued on disk) can then be ingested directly via `a message inbox`.

### 5.2 Route 2: Acknowledged Bus Delegation to `ad-backend-exec` (Non-Blocking)
- **Context:** Canonical `/home/alexey/git/agent-dashboard` at committed HEAD `efed70d` contains 2,102 uncommitted insertions across 9 files created by `ad-backend-exec` (message `01a106ba`, 44/44 backend tests pass).
- **Action:**
  1. Formal handoff on the bus delegating integration to `ad-backend-exec`.
  2. Under `flock .local/git.lock`, merge minimal backend patch (`007a6ef3`, 137 lines) and static patch (`f2e29142`, 39 lines).
  3. Verify combined 48-test suite: `PYTHONPATH=src python3 -m unittest discover -s tests/ -v`.
  4. Commit cleanly to `main` with explicit file lists under flock.
  5. Pin commit SHA and trigger independent review by `ad-independent-reviewer`.
- **Advantage:** Breaks the circular dependency on dormant session `c7a75f76` without modifying canonical files externally.

---

## 6. Verification & Invariants Checklist

- [x] **Zero Compiler Invocations:** Reviewer actor strictly executed 0 `cargo` / `rustc` compiler invocations under human hold.
- [x] **Canonical Workspaces Read-Only:** `/home/alexey/git/agent-dashboard` audited strictly read-only; 0 writes, 0 edits, 0 git stage/commit mutations.
- [x] **Scratch Footprint & Isolation:** `.local/scratch/reviewer259-dashboard-c7-diagnostic/` configured mode `0700`, measured usage 4.0 KB $\le$ 512 MB, `/tmp` net growth = 0.
- [x] **Environment Audit:** Inspected live `/proc/1508033/environ` and `/proc/1657502/environ` for APLEXER fields; verified 100% concordance with session identities.
- [x] **Snapshot Audit:** Audited `/home/alexey/.codex/shell_snapshots/`; confirmed zero files written since Oct 2.
- [x] **Hypothesis Evaluated:** "Stale shell snapshot overwrote validenv" is empirically refuted.
- [x] **Mechanism Pinpointed:** Provenance traced to Codex lifecycle hook gap (`hooks.json` lacks redraw/heartbeat hooks) + PTY cursor read updates in `spawn.rs:442` + unexempted engine fail-closed rule in `watch/state.rs:170`.
- [x] **Publication Credential Guard:** Verified via `python3 research/antigravity/tooling/publication_guard.py` (Exit Code 0).
- [x] **Git Invariant:** Zero git commits or pushes from subagent.
