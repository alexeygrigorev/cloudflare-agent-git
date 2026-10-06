# Proposal & Plan: Narrow Incremental Aplexer Build Under Hold (No Build Execution)

- **Author**: `ant-head-never-timer-custody-20261006` [session `7d87f36b-8d02-4b46-8216-98d6dce3f990`]
- **Date**: 2026-10-06T18:05:00Z / 20:05 CEST
- **Status**: **PROPOSAL UNDER STRICT HOLD — ZERO BUILD EXECUTION**
- **Context**: In response to `codex-principal` C2934 and `desktop-orchestrator` 20:03 Berlin coordinator check.

---

## 1. Problem Statement & Root Cause

1. **Current Failure Mode**:
   - Supervisor `experiment-supervision` uses `SUPERVISION_APLEXER_BINARY = /home/alexey/git/cloudflare-aplexer-protocol/target/debug/aplexer` (SHA-256 `fd6fd0ce218f6256442193e0d078467ad74830615ce87435053d7450a41279bd`, built Oct 3 09:03 UTC).
   - When inspecting `codex-principal` resting screen containing the composite footer `GPT-6.1-Sol medium · Context 33% left · ~/git/cloudflare-agent-git · Context 67% used · we…`, the binary classifies the footer as an unsubmitted draft:
     `recipient composer has an unsubmitted draft in progress (...); delivery fail-closed`
   - Python-level cooldown backoff in `scripts/supervision/service.py` (`cdee35a`) suppresses the 76-retry deadlock loop and annotates `diagnostic_hold = 'known-footer-classifier-mismatch'`, but does not repair native prompt delivery or enable unattended autonomous wake.

2. **Candidate Binary Findings**:
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
   - This source fix has never been compiled into the debug binary due to the strict Rust build hold (*"no blind build/install/24GB copy"*).

---

## 2. Narrow Bounded Incremental Build Plan (Hold Maintained)

If human or principal authorization is granted to lift the hold for an incremental build, the execution must adhere to the following bounded constraints:

### Phase 1: Pre-Build Rollback Preservation
1. Preserve the current working binary:
   ```bash
   cp -p /home/alexey/git/cloudflare-aplexer-protocol/target/debug/aplexer \
         /home/alexey/git/cloudflare-agent-git/.local/recovery/aplexer-fd6fd0ce.bak
   ```
2. Verify backup SHA-256 matches `fd6fd0ce218f6256442193e0d078467ad74830615ce87435053d7450a41279bd`.
3. Check available disk space (ensuring > 20 GiB hard floor is maintained; current available: ~24.5 GiB).

### Phase 2: Bounded Incremental Compilation
1. Do **NOT** run `cargo clean` (which would trigger a 24 GiB rebuild).
2. Execute bounded incremental compilation for the single `aplexer` binary target:
   ```bash
   cd /home/alexey/git/cloudflare-aplexer-protocol
   cargo build --bin aplexer
   ```
3. Record exact delta disk usage (target delta budget <= 300 MiB).
4. Measure compilation duration and capture build logs privately in `.local/recovery/`.

### Phase 3: Offline Verification & Falsification Tests
Before updating any supervisor selector or pointing to the new binary:
1. **Sha256 and Version Check**:
   - Inspect new binary hash, confirm it differs from `fd6fd0ce`.
   - Run `target/debug/aplexer --version`.
2. **Positive Test (Composite Footer Accepted as Empty)**:
   - Run `target/debug/aplexer message deliver` against a saved mock screen capture containing `GPT-6.1-Sol medium · Context 33% left · ~/git/cloudflare-agent-git · Context 67% used`.
   - Must classify prompt as empty (not draft).
3. **Negative Test (Real Draft Rejected Fail-Closed)**:
   - Run `target/debug/aplexer message deliver` against a screen capture containing actual user text in composer (`› let x = 1`).
   - Must reject with `recipient composer has an unsubmitted draft in progress`.
4. **Negative Test (Busy State Rejected Fail-Closed)**:
   - Run against a session in `working` / `busy` state.
   - Must reject fail-closed.

### Phase 4: Activation & Rollback Procedure
1. If all 3 validation checks pass:
   - Update `SUPERVISION_APLEXER_BINARY` in `supervision.service` environment or symlink.
   - Restart `supervision.service`.
   - Observe 2 live cycles.
2. **Immediate Rollback Trigger**:
   - If any verification check fails, compilation delta exceeds 500 MiB, or unexpected behavior occurs:
   ```bash
   cp -fp /home/alexey/git/cloudflare-agent-git/.local/recovery/aplexer-fd6fd0ce.bak \
          /home/alexey/git/cloudflare-aplexer-protocol/target/debug/aplexer
   ```
   - Rollback is atomic and takes < 1 second.

---

## 3. Governance Compliance
- **Current Action**: This document is a planning deliverable only.
- **Hold Status**: **HELD**. Zero `cargo build` commands have been executed.
- **Decision Prerequisite**: Requires explicit human operator authorization to execute Phase 2.
