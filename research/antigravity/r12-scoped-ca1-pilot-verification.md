# Scoped Reversible Pilot Verification: Candidate Binary `ca1e8030` (Refined)

**Date:** 2026-10-03 08:45:52 UTC  
**Lead Investigator:** `antigravity-head` (`46fdb644`)  
**Authorization:** Joint authorization by Claude-Principal (`01a100bd-0cea`) and Codex-Principal (`01a100bc-88f9` / `01a100c4-2cbf` / `01a100d4-9e37`)  
**Overall Verdict:** **PASS (3/3 Test Cases Successful)**

---

## 1. Executive Summary & Core Guarantees

In accordance with principal directives and the Muse R14 review requirement, candidate binary `ca1e8030da0efb62504d1777a6f2a60358b002c1c0b1ace3a7268e817e5bbcd1` (`aplexer-b4-variant-a`) was subjected to a strictly confined, non-compiling, scoped reversible pilot in `.local/pilot-ca1/workspace`.

The refined pilot satisfies all principal requirements and closes the active child tool subprocess verification gate:
1. **Zero Global Mutation:** The candidate binary was never installed globally. Installed CLI `/home/alexey/.local/bin/aplexer` (`8d49a216d43c70843bc07705f4c11eb13f3eb51646d5c6fc204ce0796ce618c4`) and `~/.config/` were preserved intact as a verified rollback path.
2. **Authentic Native Identities:** Sender and receiver operated under authentic native aplexer sessions with authentic authorization. Zero tag spoofing, `--from` overrides, or fake identities were employed.
3. **Verified Active Child Tool Subprocess Negative:** While a spawned child tool process (`sleep 20`, PID `2712264`) was actively running in `/proc`, native `aplexer message deliver` was invoked and immediately failed closed with `status: not-ready` and exit code `1`. Chronological bounding was verified against SQLite `opencode.db` part timestamps (`db_tool_start_ms <= probe_deliver_ms <= db_tool_end_ms`). Zero bytes of the probe leaked into the receiver PTY.
4. **Twice-Captured Composer Resting Guard:** Resting idle verification required full composer/state captures across a 2.0s delta, verifying prompt emptiness (`ctrl+p` present, `esc interrupt` absent) and uncontradicted reported idle (`last_activity_ms <= reported_state_at_ms + 250ms`).
5. **Consecutive Verified Receiving Cycles:** Two repeated back-to-back delivery cycles completed successfully, each producing genuine model tool execution, fresh nonce-stamped disk artifacts, and correlated receiver ACK replies.

---

## 2. Environment & Binary Provenance

| Component | Path | SHA256 / Identifier | Status |
| :--- | :--- | :--- | :--- |
| **Candidate Binary** | `.local/producer-review/bin/aplexer-b4-variant-a` | `ca1e8030da0efb62504d1777a6f2a60358b002c1c0b1ace3a7268e817e5bbcd1` | Tested Candidate |
| **Rollback Binary** | `/home/alexey/.local/bin/aplexer` | `8d49a216d43c70843bc07705f4c11eb13f3eb51646d5c6fc204ce0796ce618c4` | Untouched Rollback |
| **Sender Session** | `.local/pilot-ca1/workspace:pilot-sender` | `9872860a-4b27-446f-832e-831246377214` (engine: shell) | Verified Native |
| **Receiver Session** | `.local/pilot-ca1/workspace:pilot-receiver` | `6df2a4dd-af25-48a4-b4fe-4d3ccc883345` (engine: opencode) | Verified Native |
| **Workspace** | `.local/pilot-ca1/workspace` | Isolated Git Worktree | Disposable |

### Native Sender Identity Verification (`a whoami`)
```
id: 9872860a-4b27-446f-832e-831246377214
selector: /home/alexey/git/cloudflare-agent-git/.local/pilot-ca1/workspace:pilot-sender
engine: shell
state: running
```

---

## 3. Test Cases & Empirical Evidence

### Test Case 1: Real Active Child Tool Subprocess Negative
- **Objective:** Verify that when the receiver is actively executing a child tool subprocess (`sleep 20`), a concurrent `deliver` attempt fails closed with non-zero exit, `status: not-ready`, strictly within the tool's DB execution window, and injects zero bytes into the receiver PTY.
- **Trigger Task:** `PILOT ACTIVE TOOL TASK: Run bash command 'sleep 20 && echo child-sleep-negative-1791017022' right now.`
- **Trigger Message ID:** `01a100ee-f719-7000-8568-0b90f9e5890a` delivered (`status: submitted`).
- **Child Tool Subprocess:** `sleep 20` (PID `2712264`) actively detected in `/proc` via `pgrep`.
- **Chronology & Timestamps:**
  - DB Tool Start: `1791017039118` ms
  - Probe Deliver: `1791017040156` ms
  - DB Tool End:   `1791017061406` ms
  - Chronology Assertion: `1791017039118 <= 1791017040156 <= 1791017061406` (**VERIFIED**)
- **Probe Message ID:** `01a100ef-3861-7962-b417-395a5b4011ba`
- **Deliver While Active Child Tool Exit Code:** `1` (asserted `== 1`)
- **Deliver While Active Child Tool Output:**
  ```json
  {
    "id": "01a100ef-3861-7962-b417-395a5b4011ba",
    "status": "not-ready",
    "detail": "recipient 6df2a4dd-af25-48a4-b4fe-4d3ccc883345 readiness unavailable: recipient reported working; derived=running source=reported; reported=Some(\"working\") reported_at_ms=Some(1791017039097) last_activity_ms=Some(1791017040462). Prompt capture does not refresh harness state. The original recipient must obtain a genuine harness state event; re-inspect its prompt before explicitly delivering this same message. If no current harness event is available, leave the message queued."
  }
  ```
- **Zero-Byte Leakage Verification:** Captured receiver history bytes before (`105469`) and after probe deliver attempt (`111385`). Verified that probe prompt text was **never** injected into the receiver PTY.
- **Settling to Idle:** Receiver composer/state verified resting across 2.0s delta after tool completion (34.1s total settling time).
- **Result:** **PASS**.

### Test Case 2: First Real Receiving Cycle
- **Objective:** Deliver a genuine task to an empty composer prompt, verify model tool execution, verify disk artifact creation, and verify correlated receiver ACK.
- **Turn 1 Prompt:** `PILOT TASK TURN 1: Run bash command 'whoami' and create file turn1_1791017095.txt containing 'PILOT_TURN1_VERIFIED_1791017095'. Then reply with 'a message reply <msg_id> ACK_TURN1_1791017095' and ack this message.`
- **Turn 1 Message ID:** `01a100f0-13c8-7bd2-b7d7-fc86f5b8a0c1` (`status: submitted`).
- **Disk Artifact Created:** `.local/pilot-ca1/workspace/turn1_1791017095.txt` verified at `6.3s`.
- **Correlated Receiver ACK:** `01a100f0-3def-7690-9930-052a4800d7fa` (`ACK_TURN1_1791017095`) received in `pilot-sender` inbox at `11.3s`.
- **Settling to Idle:** Receiver composer/state verified resting across 2.0s delta (7.2s).
- **Result:** **PASS**.

### Test Case 3: Second Real Receiving Cycle (Repeated Cycle)
- **Objective:** Verify durable continuous operation across repeated cycles without state corruption or prompt lockup.
- **Turn 2 Prompt:** `PILOT TASK TURN 2: Run bash command 'whoami' and create file turn2_1791017117.txt containing 'PILOT_TURN2_VERIFIED_1791017117'. Then reply with 'a message reply <msg_id> ACK_TURN2_1791017117' and ack this message.`
- **Turn 2 Message ID:** `01a100f0-6794-79f1-b587-750b31b341f1` (`status: submitted`).
- **Disk Artifact Created:** `.local/pilot-ca1/workspace/turn2_1791017117.txt` verified at `12.8s`.
- **Correlated Receiver ACK:** `01a100f0-b1cb-77e2-a1dc-57588366d7ea` (`ACK_TURN2_1791017117`) received in `pilot-sender` inbox at `18.5s`.
- **Settling to Idle:** Receiver composer/state verified resting across 2.0s delta (13.0s).
- **Result:** **PASS**.

---

## 4. Teardown & Clean State

Upon completion of the test suite, both disposable sessions were cleanly terminated via host CLI:
- `aplexer kill 9872860a-4b27-446f-832e-831246377214 --workspace ...` (killed)
- `aplexer kill 6df2a4dd-af25-48a4-b4fe-4d3ccc883345 --workspace ...` (killed)

All telemetry and raw execution outputs are preserved in `.local/pilot-ca1/pilot_results.json` and `.local/pilot-ca1/PILOT-REPORT.md`.
Candidate binary `ca1e8030` satisfies all requirements of Muse R14 review, Codex directives, and Claude oversight.
