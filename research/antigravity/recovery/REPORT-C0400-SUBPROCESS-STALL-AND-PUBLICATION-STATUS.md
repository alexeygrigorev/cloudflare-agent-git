# Technical Diagnosis: C-0400 Subprocess Stall & Publication Head Custody

- **Observer:** Ant Integration HEAD (`ant-integration-head-recovery`, session UUID `c69a9f51-b751-4400-8bbd-c24cb87fe39a`)
- **Engine / Model:** `antigravity` / `gemini-3.8-flash-high`
- **Timestamp:** 2026-10-08T06:02:00+02:00 (04:02:00 UTC)
- **Status:** **CANONICAL EMPIRICAL DIAGNOSIS**

---

## 1. C-0400 Root Native Exec Stall (1973s) Empirical Diagnosis

### A. Incident Overview and Exact Rollout Target
- **Log Source:** `/home/alexey/.codex/sessions/2026/10/02/rollout-2026-10-02T20-18-45-01a0fdd7-109e-7972-9199-e082a7a1383d.jsonl`
- **Thread ID:** `01a0fdd7-109e-7972-9199-e082a7a1383d`
- **Turn ID:** `01a1197f-2073-7021-a63f-348adbc290b9`
- **Call ID:** `call_2a7ff946f9e54e8f9ebbfdf41d20958a`
- **Start Time:** `2026-10-08T03:22:40.870Z` (ordinal 91621)
- **Abort Time:** `2026-10-08T03:55:43.717Z` (ordinal 91623)
- **Total Duration:** 1982.8 seconds (stalled ~1973 seconds with zero output until root manual abort via Escape)

### B. Executed Command Sequence
The tool call invoked `exec_command` with a multi-line chained shell command:
```bash
a message send --to desktop-orchestrator 'ping-b65dc05fbfab. Genuine f09 Codex principal active. ...'
sqlite3 -readonly -json /home/alexey/git/agent-quota-launcher/.local/launcher-config/state.db "SELECT id,state,updated_at FROM tasks WHERE id LIKE 'crh1008-%' ORDER BY updated_at DESC LIMIT 9;"
sha256sum research/antigravity/reviews/REV-METRICS-BLIND-EVENT-02-QUALIFICATION.md
sqlite3 -readonly -json /home/alexey/git/agent-quota-launcher/.local/launcher-config/state.db "SELECT id,report_sha256,status,verdict FROM review_receipts WHERE id=48;"
```

### C. Conclusive Empirical Lock Evidence
1. **Unwritten Ping Reply:**
   - Inspection of the aplexer workspace message store (`a message log | grep "ping-b65dc05fbfab"`) demonstrates that **only** the incoming ping (`01a11986-f260`) exists.
   - The reply payload containing `ping-b65dc05fbfab` was **never written to disk or recorded on the bus**.
   - This proves conclusively that the execution stalled on the **very first command** (`a message send`) before emitting an envelope ID or reaching subsequent commands.
2. **Kernel File Lock Mechanics (`libc::flock`):**
   - In `aplexer/src/messaging/store.rs:61`, message submission calls:
     ```rust
     let _mailbox = FileLock::exclusive(&mailbox_lock_path(mp), false)?;
     ```
   - In `aplexer/src/persist.rs:244-251`, `FileLock::exclusive(path, nonblocking)` executes:
     ```rust
     let mut op = libc::LOCK_EX;
     if nonblocking {
         op |= libc::LOCK_NB;
     }
     if unsafe { libc::flock(file.as_raw_fd(), op) } != 0 { ... }
     ```
   - Passing `nonblocking: false` causes the kernel to place the calling thread into an uninterruptible sleep awaiting `LOCK_EX` on `<workspace-mailbox>/mailbox.lock`.
   - Any concurrent holder of `mailbox.lock` (e.g. concurrent session listing, message indexing, or GC) results in an indefinite sleep if no process timeout is applied.
3. **Execution Model Vulnerability:**
   - Codex Code Mode executes subprocesses synchronously to EOF without default timeout guards.
   - Because the command was not wrapped in `timeout 8s ...`, the process remained blocked for 1982.8 seconds.
   - In subsequent executions (ordinal 91689), principal correctly remediated this by wrapping all external commands in `timeout 8s`.

---

## 2. Canary 47 Store Lifecycle Writes Clarification

To ensure unambiguous operational execution for Canary 47:
1. **Authorized Lifecycle Operations:**
   - Standard task lifecycle transitions (`launcher admit`, `launcher start`, `launcher complete`, `launcher record-review`, `launcher accept`) via the maintained `agent-quota-launcher` CLI and python store API under the owning head/launcher process are **fully authorized and required**.
2. **Prohibited Canonical Store Mutations:**
   - "No canonical Store mutation" strictly prohibits direct, out-of-band SQLite manipulations, manual schema alterations, configuration edits, or tampering with immutable historical receipt rows.

---

## 3. Publication Head Recovery Actor Verification & Oct 8 Custody

1. **Session Retirement Record:**
   - Session `cfe991d4-82e0-4ac8-9521-4eaf9479a54d` was retired into `/home/alexey/.local/state/aplexer/retired-sessions/cfe991d4-82e0-4ac8-9521-4eaf9479a54d/tombstone.json` at `finished_at_ms: 1791430555045` (05:35:55 CEST) with cause `"finished"`.
2. **Clean Transcript Completion:**
   - Native transcript at `/home/alexey/.gemini/antigravity-cli/brain/ab6ce5b3-964d-4134-b160-0945237fa968/.system_generated/logs/transcript.jsonl` (step 13974) confirms the actor completed all assigned tasks (October 7 standup fact packet assembly and Sonnet recovery audit) and observed an empty inbox before cleanly terminating.
   - No orphan processes, unacknowledged warnings, or unhandled exceptions occurred.
3. **Preserved Staged Artifacts:**
   - Staged in `.local/recovery/publication-head-recovery-20261007/`:
     * `STANDUP-EVIDENCE-PACKET-20261007.md` (SHA-256 verified)
     * `REV-STANDUP-EVIDENCE-PACKET-20261007.md`
     * `FAILED-CONTRACT-AUDIT-SONNET-RECOVERY.md`
     * `claude-quota-check-0258-cleared.json`
4. **Resumed October 8 Publication Custody:**
   - Named successor for October 8 publication intake: `main` (`6e9a7c6f`, Claude Opus writer session).
   - Human draft (`6e9a7c6f`) and writer draft (`e67cafb2`) remain strictly protected against resets or overwrites.
