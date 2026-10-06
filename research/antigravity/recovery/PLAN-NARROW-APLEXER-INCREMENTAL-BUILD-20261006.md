# Proposal & Plan: Narrow Incremental Aplexer Build Under Hold (Revision 2)

- **Author**: `ant-head-never-timer-custody-20261006` [session `7d87f36b-8d02-4b46-8216-98d6dce3f990`]
- **Date**: 2026-10-06T18:22:00Z / 20:22 CEST
- **Status**: **PROPOSAL UNDER STRICT HOLD — ZERO BUILD EXECUTION**
- **Revisions**: Incorporates 10-point rigor feedback from Codex Principal (C2941) and operational constraints.

---

> [!CAUTION]
> **STRICT RUST BUILD HOLD IN EFFECT**:
> This document is a planning specification and readiness verification only.
> In strict compliance with human steering (*"no blind build/install/24GB copy"*), **ZERO** `cargo build`, `cargo test`, or `rustc` invocations are authorized or executed.
> Execution of Phase 2 requires explicit, affirmative human instruction.

---

## 1. Problem Statement & Root Cause

1. **Current Failure Mode**:
   - Supervisor `experiment-supervision` uses `SUPERVISION_APLEXER_BINARY = /home/alexey/git/cloudflare-aplexer-protocol/target/debug/aplexer` (SHA-256 `fd6fd0ce218f6256442193e0d078467ad74830615ce87435053d7450a41279bd`, built Oct 3 09:03 UTC).
   - When inspecting `codex-principal` resting screen containing the composite footer `GPT-6.1-Sol medium · Context 33% left · ~/git/cloudflare-agent-git · Context 67% used · we…`, the binary classifies the footer as an unsubmitted draft:
     `recipient composer has an unsubmitted draft in progress (...); delivery fail-closed`
   - Python-level cooldown backoff in `scripts/supervision/service.py` (`cdee35a`) suppresses the 76-retry deadlock loop and annotates `diagnostic_hold = 'known-footer-classifier-mismatch'`, but does not repair native prompt delivery or enable unattended autonomous wake.

2. **Candidate Binary Analysis**:
   - Upstream binary `/home/alexey/.local/bin/aplexer` (`fcbb886e`, built Oct 5 11:03 UTC) includes `message deliver`, but lacks the composite status bar regex added in the protocol fork on Oct 6.
   - Zero pre-built candidate binaries exist that contain the composite footer recognition regex.

3. **Existing Source Fix in Repository**:
   - In `/home/alexey/git/cloudflare-aplexer-protocol/src/bin/aplexer/message_deferred.rs`, lines 400–450 already define:
     ```rust
     fn is_composite_status_bar(line: &str) -> bool {
         line.contains("GPT-") && line.contains("·") && line.contains("Context")
     }
     ```
     as well as unit test `test_codex_principal_c1444_screen_classified_empty`.
   - This source fix has never been compiled into the debug binary due to the strict Rust build hold.

---

## 2. Source Pin & Immutability Verification

To guarantee determinism and eliminate hidden divergence:
1. **Base Commit Pin**:
   - Repository: `/home/alexey/git/cloudflare-aplexer-protocol`
   - Base Commit: `7efa49386d756575f1003825b050643688fa3fc5`
2. **Dirtypatch Pin**:
   - Working tree patch SHA-256: `911d1ba0e8f85ac1b96aa5cb1004941b0ff9e6333553a41363ab1fd4b1952892`
   - Modified files:
     - `src/bin/aplexer/message_deferred.rs` (composite footer classification & 9 unit tests)
     - `src/watch/state.rs` (PTY activity grace handling for general engines)
   - Pre-build snapshot artifact:
     ```bash
     git -C /home/alexey/git/cloudflare-aplexer-protocol diff > \
         /home/alexey/git/cloudflare-agent-git/.local/recovery/aplexer-incremental-20261006.patch
     ```

---

## 3. Storage Policy & Headroom Reconciliation

1. **StorageBox Target Prohibition**:
   - Strict ban on copying Cargo build targets, caches, or `.cargo` directories to/from StorageBox (`//he-sb-storage-box...`).
   - Compilation runs strictly on local NVMe disk inside existing clone `/home/alexey/git/cloudflare-aplexer-protocol/target`.
   - Forbids `cargo clean` and forbids full tree re-cloning to protect the 20 GiB disk floor (current disk headroom: 24.5 GiB).

2. **Reconciled Headroom Budget & Ceilings**:
   - **Baseline Measurement**: Record baseline target size before compilation:
     ```bash
     BASELINE_MB=$(du -sm /home/alexey/git/cloudflare-aplexer-protocol/target | awk '{print $1}')
     ```
   - **Strict Target Delta Ceiling**: **300 MiB** (reconciles and supersedes previous 300 vs 500 MiB ambiguity). If `current_target_mb - BASELINE_MB > 300`, build is immediately killed.
   - **Aggregate Scratch Headroom**: Entire build scratch space must remain **< 512 MiB** total.
   - **System Disk Floor**: Hard abort if host available disk drops below **20.0 GiB** at any time.

---

## 4. Guarded Incremental Build Specification

If human authorization is granted to lift the hold, the build is executed under strict external containment:

### Phase 1: Pre-Build Binary Preservation & Locking
1. Backup original working binary to immutable archive:
   ```bash
   mkdir -p /home/alexey/git/cloudflare-agent-git/.local/recovery
   cp -p /home/alexey/git/cloudflare-aplexer-protocol/target/debug/aplexer \
         /home/alexey/git/cloudflare-agent-git/.local/recovery/aplexer-fd6fd0ce.bak
   chmod 0444 /home/alexey/git/cloudflare-agent-git/.local/recovery/aplexer-fd6fd0ce.bak
   ```
2. Verify backup SHA-256 matches `fd6fd0ce218f6256442193e0d078467ad74830615ce87435053d7450a41279bd`.

### Phase 2: Dual Watcher & Incremental Build
1. **External Watcher Implementation** (`scripts/supervision/build_watcher.sh`):
   - **Timeout Watcher**: Enforces a strict 180-second hard kill (`timeout -k 5s 180s`).
   - **Growth Watcher**: Background daemon checking disk and target size every 3 seconds:
     ```bash
     while kill -0 $CARGO_PID 2>/dev/null; do
       CUR_MB=$(du -sm /home/alexey/git/cloudflare-aplexer-protocol/target | awk '{print $1}')
       DELTA=$((CUR_MB - BASELINE_MB))
       if [ "$DELTA" -gt 300 ]; then
         kill -9 $CARGO_PID
         echo "DELTA_EXCEEDED: ${DELTA}MB > 300MB" > /tmp/build_abort_reason
         exit 1
       fi
       sleep 3
     done
     ```
2. **Guarded Cargo Invocations**:
   - Single target build only (no docs, no tests, no full workspace rebuild):
     ```bash
     cargo build --bin aplexer
     ```
   - No parallel jobs beyond host physical cores (`--jobs 4`).

### Phase 3: Supported Offline Test & Falsification Interface
Before touching supervisor runtime:
1. **Cryptographic Digest Check**:
   - Calculate new binary SHA-256 and confirm it differs from `fd6fd0ce`.
   - Verify `target/debug/aplexer --version`.
2. **Supported Unit Test Execution**:
   - Run the dedicated classifier unit tests using the standalone test runner on the exact binary target:
     ```bash
     cargo test --bin aplexer test_codex_principal_c1444_screen_classified_empty
     cargo test --bin aplexer test_codex_draft_preserved_reset_hard
     cargo test --bin aplexer test_codex_draft_preserved_fix_rate_limiter
     ```
   - Must verify both positive (composite status bar classified as empty) and negative (real user draft classified as draft) assertions.
3. **Supported CLI Inspection Verification**:
   - Execute the compiled binary directly against mock screen fixtures using standard CLI inspection flags without launching live PTY sessions.

### Phase 4: Atomic Activation & Rollback Procedure
1. **Atomic Rollback Protocol (`mv -T`)**:
   - If compilation fails, watcher trips, or any offline test fails:
     ```bash
     cp /home/alexey/git/cloudflare-agent-git/.local/recovery/aplexer-fd6fd0ce.bak /tmp/aplexer_rollback_tmp
     mv -T /tmp/aplexer_rollback_tmp /home/alexey/git/cloudflare-aplexer-protocol/target/debug/aplexer
     ```
   - Reverts binary atomically via kernel rename in < 1 second.
2. **Activation Custody**:
   - Owner: `ant-head-never-timer-custody-20261006`.
   - Symlink or `SUPERVISION_APLEXER_BINARY` validated to point to new binary.
   - Restart service: `systemctl --user restart supervision.service`.
   - Custody proof: verify new supervisor PID, zero restart churn, and 2 consecutive healthy cycles with `state: "running"` and `worker_alive: true`.

---

## 5. Summary Compliance Matrix

| Criterion | Implementation in Revision 2 | Status |
| :--- | :--- | :--- |
| **1. Source & Patch Pin** | Pinned to commit `7efa4938` + dirtypatch SHA-256 `911d1ba0...` | Fully specified |
| **2. Scratch Headroom** | Baseline measured; aggregate scratch < 512 MiB | Fully specified |
| **3. StorageBox Policy** | Strict prohibition on StorageBox target/cache sync | Enforced |
| **4. Offline Test Interface** | Native targeted test suite on binary (`cargo test --bin aplexer test_*`) | Documented |
| **5. Dual Watcher** | 180s hard timeout + 3s sampling interval disk growth watcher | Specified |
| **6. Binary Preservation** | Mode 0444 backup of `fd6fd0ce` before cargo invocation | Specified |
| **7. Atomic Rollback** | `mv -T` from temp file to destination | Specified |
| **8. Activation Custody** | Named custody owner, systemd restart, PID & cycle verification | Specified |
| **9. Budget Reconciliation** | Single hard 300 MiB delta limit (supersedes 500 MiB ambiguity) | Reconciled |
| **10. Human Rust Build Hold** | **STRICT HOLD MAINTAINED** (0 build invocations) | Enforced |
