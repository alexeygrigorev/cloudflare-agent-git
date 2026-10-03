# Scoped Reversible Pilot Verification: Candidate Binary `ca1e8030`

**Date:** 2026-10-03 08:12:35 UTC  
**Lead Investigator:** `antigravity-head` (`46fdb644`)  
**Authorization:** Joint authorization by Claude-Principal (`01a100bd-0cea`) and Codex-Principal (`01a100bc-88f9` / `01a100c4-2cbf`)  
**Overall Verdict:** **PASS (3/3 Test Cases Successful)**

---

## 1. Executive Summary & Core Guarantees

In accordance with principal directives, candidate binary `ca1e8030da0efb62504d1777a6f2a60358b002c1c0b1ace3a7268e817e5bbcd1` (`aplexer-b4-variant-a`) was subjected to a strictly confined, non-compiling, scoped reversible pilot in `.local/pilot-ca1/workspace`.

The pilot satisfied all principal requirements:
1. **Zero Global Mutation:** The candidate binary was never installed globally. Installed CLI `/home/alexey/.local/bin/aplexer` (`8d49a216d43c70843bc07705f4c11eb13f3eb51646d5c6fc204ce0796ce618c4`) and `~/.config/` were preserved intact as a verified rollback path.
2. **Authentic Native Identities:** Sender and receiver operated under authentic native aplexer sessions with authentic authorization. Zero tag spoofing, `--from` overrides, or fake identities were employed.
3. **Fail-Closed Busy Rejection:** Active tool execution (`sleep 10`) caused native `aplexer message deliver` to immediately reject subsequent messages with `status: not-ready`, with strictly zero bytes leaked into the receiver's PTY.
4. **Consecutive Verified Receiving Cycles:** Two repeated back-to-back delivery cycles completed successfully, each producing genuine model tool execution, fresh nonce-stamped disk artifacts, and correlated receiver ACK replies.

---

## 2. Environment & Binary Provenance

| Component | Path | SHA256 / Identifier | Status |
| :--- | :--- | :--- | :--- |
| **Candidate Binary** | `.local/producer-review/bin/aplexer-b4-variant-a` | `ca1e8030da0efb62504d1777a6f2a60358b002c1c0b1ace3a7268e817e5bbcd1` | Tested Candidate |
| **Rollback Binary** | `/home/alexey/.local/bin/aplexer` | `8d49a216d43c70843bc07705f4c11eb13f3eb51646d5c6fc204ce0796ce618c4` | Untouched Rollback |
| **Sender Session** | `.local/pilot-ca1/workspace:pilot-sender` | `87eb7416-8ba6-43f6-9782-e04bac46f6ea` (engine: shell) | Verified Native |
| **Receiver Session** | `.local/pilot-ca1/workspace:pilot-receiver` | `77510259-bcdb-4a59-a6a1-15c08571dd6c` (engine: opencode) | Verified Native |
| **Workspace** | `.local/pilot-ca1/workspace` | Isolated Git Worktree | Disposable |

### Native Sender Identity Verification (`a whoami`)
```
id: 87eb7416-8ba6-43f6-9782-e04bac46f6ea
selector: /home/alexey/git/cloudflare-agent-git/.local/pilot-ca1/workspace:pilot-sender
engine: shell
state: running
```

---

## 3. Test Cases & Empirical Evidence

### Test Case 1: Real Busy Negative (Active Tool Execution)
- **Objective:** Verify that when the receiver is actively executing a tool (`sleep 10`), a concurrent `deliver` attempt fails closed and injects zero bytes into the receiver PTY.
- **Trigger Message:** `01a100d0-e6ec-7000-a02d-198d7ba13166` delivered (`status: submitted`).
- **PTY State:** Actively executing `sleep 10 && echo "busy-window-done"` with `esc interrupt` active in PTY.
- **Probe Message:** `01a100d0-edac-7122-9ad3-7f595e8f62d0`.
- **Deliver While Busy Output:**
  ```json
  {
    "id": "01a100d0-edac-7122-9ad3-7f595e8f62d0",
    "status": "not-ready",
    "detail": "recipient 77510259-bcdb-4a59-a6a1-15c08571dd6c readiness unavailable: recipient reported working; derived=running source=reported; reported=Some(\"working\") reported_at_ms=Some(1791015054052) last_activity_ms=Some(1791015055238). Prompt capture does not refresh harness state. The original recipient must obtain a genuine harness state event; re-inspect its prompt before explicitly delivering this same message. If no current harness event is available, leave the message queued."
  }
  ```
- **Zero-Byte Leakage Verification:** Captured full PTY and plain screen; verified that probe message text was **never** injected into the receiver terminal.
- **Result:** **PASS**.

### Test Case 2: First Real Receiving Cycle
- **Objective:** Deliver a genuine task to an empty composer prompt, verify model tool execution, verify disk artifact creation, and verify correlated receiver ACK.
- **Turn 1 Prompt:** `PILOT TASK TURN 1: Run bash command 'whoami' and create file turn1_1791015114.txt containing 'PILOT_TURN1_VERIFIED_1791015114'. Then reply with 'a message reply <msg_id> ACK_TURN1_1791015114' and ack this message.`
- **Turn 1 Message ID:** `01a100d1-d6f4-7c11-9d16-066cf3f2683d` (`status: submitted`).
- **Disk Artifact Created:** `.local/pilot-ca1/workspace/turn1_1791015114.txt` verified at `7.9s`.
- **Correlated Receiver ACK:** `01a100d2-0baf-7150-883d-3272eada8fcc` (`ACK_TURN1_1791015114`) received in `pilot-sender` inbox at `13.0s`.
- **Result:** **PASS**.

### Test Case 3: Second Real Receiving Cycle (Repeated Cycle)
- **Objective:** Verify durable continuous operation across repeated cycles without state corruption or prompt lockup.
- **Turn 2 Prompt:** `PILOT TASK TURN 2: Run bash command 'whoami' and create file turn2_1791015138.txt containing 'PILOT_TURN2_VERIFIED_1791015138'. Then reply with 'a message reply <msg_id> ACK_TURN2_1791015138' and ack this message.`
- **Turn 2 Message ID:** `01a100d2-34a0-7dd3-84e2-17356fe91034` (`status: submitted`).
- **Disk Artifact Created:** `.local/pilot-ca1/workspace/turn2_1791015138.txt` verified at `5.9s`.
- **Correlated Receiver ACK:** `01a100d2-5e14-7792-bae5-033af9643a7c` (`ACK_TURN2_1791015138`) received in `pilot-sender` inbox at `11.1s`.
- **Result:** **PASS**.

---

## 4. Teardown & Clean State

Upon completion of the test suite, both disposable sessions were cleanly terminated via host CLI:
- `aplexer kill 87eb7416-8ba6-43f6-9782-e04bac46f6ea` (killed)
- `aplexer kill 77510259-bcdb-4a59-a6a1-15c08571dd6c` (killed)

All telemetry and raw execution outputs are preserved in `.local/pilot-ca1/pilot_results.json` and `.local/pilot-ca1/PILOT-REPORT.md`.
Candidate binary `ca1e8030` is confirmed functionally viable, fail-closed under active tool execution, and capable of sustained autonomous message delivery.
