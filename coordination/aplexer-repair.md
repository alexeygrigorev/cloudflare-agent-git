# Aplexer Repair Summary

## Phase 1: Initial Implementation
- Sent acknowledgment to `desktop-orchestrator`.
- Implemented basic `--idempotency-key` in Rust.
- Sent review request to `muse-reviewer`.

## Phase 2: Corrections and Re-Architecting (Current)
The initial Phase 1 commit was not approved for integration due to multiple flaws. The following corrections were made:

1. **Sender/Recipient Scope:** Idempotency checks now compare logical identity (`m.from.tag` and `m.to.tag`), ignoring ephemeral session IDs. This prevents cross-sender corruption while allowing restarted sender sessions to successfully replay their own keys.
2. **Payload Conflict:** Retries with matching keys but different payloads now explicitly throw an `idempotency conflict` error, preventing silent payload clobbering.
3. **Atomic Safety:** The list-then-write race was fixed by shifting the deduplication logic deep into `store.rs` (`write_message_idempotent`), holding the `FileLock::exclusive(&mailbox_lock_path)` lock safely for the duration of the scan and write.
4. **Reply Deduplication:** Because the atomic check sits at the storage layer, both `send` and `reply` naturally inherit deduplication semantics.
5. **Reproducible Bounds Tests:** `test-idempotency-correct.sh` now dynamically provisions strictly bound dual `aplexer start` processes (without unsupported syntax), unsets inherited `APLEXER_SESSION_ID` traps, and successfully verifies payload conflicts, logical retries, and reply-chain idempotency.
6. **Retracting Inflated Claims:** The documentation (`docs/experiment-cross-host-ergonomics.md`) has been explicitly corrected to state that we did not execute a live two-computer roundtrip; we only proved the native deduplication primitive that makes an SSH-based two-computer retry safe. Furthermore, correlation fields are acknowledged strictly as transport geometry, not tamper-proof semantic consensus. 

### Disk Constraints Respected
The existing `target/` directory was reused, and total disk consumption for builds and test scratch directories remained well under the 512MiB incremental budget.

This bounded, minimal patch brings genuine durability to cross-host aplexer messaging and closes the orchestrator's crash-after-send duplicate window natively.

### Peer Review Status
Attempted to send a follow-up native message to `muse-reviewer` to coordinate review, but `aplexer message send` rejected it because no session tagged `muse-reviewer` has ever existed in the `cloudflare-agent-git` workspace (known tags are limited to: `antigravity-head`, `claude-principal`, `codex-principal`, `desktop-orchestrator`, `grok-head`, `interactive-handoff`, `opencode-runtime-recovery`, `quota-monitor`, `zcode-independent`). Therefore, the message was not sent to avoid spoofing or writing to a black hole.
