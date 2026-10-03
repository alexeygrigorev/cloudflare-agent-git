# R9: Runtime Single-Effect Verification and Dupexec Fix Audit

**Date:** 2026-10-03  
**Team:** a16-runtime-protocol  
**Owner / Author:** `antigravity-head` (executed via subagent `a1a7e84f-207b-4b6d-94aa-467bbbdacfb3`)  
**Repository Tested:** `/home/alexey/git/codex-zcode` (commit `bf9d7ed22a70fd205045c75688f1f1a79877ee8f`)  
**Binary Tested:** `/home/alexey/git/codex-zcode/codex-rs/target/debug/zcodex` (direct execution, zero global install)  

---

## 1. Executive Summary

This report documents the empirical validation of the fix for the double-execution ("dupexec") bug in `codex-zcode` (commit `bf9d7ed22a`), and provides a full accounting of target physical growth, resource guard adherence, and single-effect proof under strict sandbox and scratch budgets.

### Key Results
1. **Synthetic Adapter / Mode Regression Proof:** In direct comparative testing using an identical probe stub (`probe_stub.cjs`) under identical prompts, the old binary (`~/.local/lib/zcodex/zcodex`, which spawns the ZCode cold wire with `--mode yolo`) produced **3 side effects** for a single tool call (2 inner stub executions across turns + 1 outer client execution). In contrast, the newly built debug binary (`codex-rs/target/debug/zcodex`, which spawns with `--mode build`) produced **exactly 1 side effect** (0 inner stub executions, 1 outer client execution). This confirms the CLI cold-spawn mode flag regression.
2. **Inner Denial Mechanism Confirmed on Real Production CJS:** Under `--mode build`, the real production ZCode harness (`/opt/ZCode/resources/glm/zcode.cjs`) explicitly rejects write-capable tool calls (`permission.resolved decision=deny, reason="No permission client configured for Bash"`), while continuing to stream authoritative `tool_input_start` and `tool_call` events to the parent client. This establishes real child denial in production CJS.
3. **Separate Bounded Evidence & Open Scope:** The synthetic adapter regression (3 vs 1 count) and real production child denial are distinct bounded evidence points. End-to-end live execution combining the actual outer client with production CJS on identical tasks, as well as retry/resume with fixed operation IDs, remain separate validations pending independent review.
4. **Zero Global Install:** Neither `/home/alexey/.local/bin/zcodex` nor `/home/alexey/.local/lib/zcodex/zcodex` was touched or overwritten. Both retain their historical timestamps (Sep 26 22:03 and Sep 26 21:41) and SHA-256 checksums.
5. **Target Resource Accounting:** The incremental cargo build resulted in a physical target growth of **+12,259,708,928 bytes (~12.26 GB)**, exceeding the 512 MiB incremental threshold. This was immediately recognized as a resource violation: all `cargo` and `rustc` processes were permanently halted (0 running), zero broad rebuilds or cleans were attempted, and host free disk remained safely at **103 GiB** (well above the 8 GiB floor). All builds remain permanently frozen.

---

## 2. Resource Measurement & Growth Audit

### 2.1 Disk Space & Host Headroom
- **Filesystem:** `/dev/nvme0n1p3` mounted on `/`
- **Pre-build Available Space:** `115 GiB` (`122,913,226,752` bytes)
- **Post-build Available Space:** `103 GiB` (`110,516,428,800` bytes)
- **Safety Margin:** 103 GiB free $\gg$ 8 GiB hard floor.

### 2.2 Physical Target Growth
- **Pre-build Target (`du -s -B1 target` in `codex-rs`):** `42,601,840,640` bytes (~42.60 GB)
- **Post-build Target (`du -s -B1 target` in `codex-rs`):** `54,861,549,568` bytes (~54.86 GB)
- **Net Growth Delta:** `+12,259,708,928` bytes (~12.26 GB / ~11.42 GiB)
- **Build Duration:** 8 minutes 12 seconds (`~/.cargo/bin/cargo build --manifest-path Cargo.toml --bin zcodex`)

### 2.3 Root Cause of 512 MiB Guard Breach
1. **Incremental Workspace Scope:** The `codex-rs` workspace comprises ~380 crates. Recompiling the core CLI binary `zcodex` from source after modifications in `client.rs` caused incremental recompilation and link artifact generation across dozens of dependent internal crates.
2. **Unstripped Debug Binary Size:** The single unstripped debug binary `zcodex` is `1,545,061,640` bytes (~1.54 GB) by itself—more than 3x the 512 MiB threshold—before accounting for `.rlib`, `.rmeta`, `.o`, and incremental query cache files.
3. **Guard Implementation Defect:** The subagent was instructed on before/after sizes and host floor bounds, but lacked an active in-flight polling loop during `cargo build` to kill the compilation process group upon reaching a 512 MiB target delta.
4. **Remediation & Current Policy:** All future builds are permanently halted. No `cargo clean`, `cargo test`, or `cargo build` is permitted in `codex-rs`. The existing binary at `codex-rs/target/debug/zcodex` is frozen.

---

## 3. Binary Verification and Integrity

| Binary | Location | Size (bytes) | SHA-256 Checksum | mtime | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Installed Wrapper** | `~/.local/bin/zcodex` | 181 | `098a12806eb2a9b49282799fd0320a9b217574c90d7cc6790006053e16269296` | 2026-09-26 22:03 | **Untouched** |
| **Installed Binary** | `~/.local/lib/zcodex/zcodex` | 385,674,664 | `dce345ed47fb4190bb85771ad8ff1dc39cc8c19665fa433475c715689f7268e9` | 2026-09-26 21:41 | **Untouched** |
| **New Debug Binary** | `codex-rs/target/debug/zcodex` | 1,545,061,640 | `bc72fcf78044ad6078fbd8501a16b6c90b253e053dcc7666a250917184761f69` | 2026-10-03 04:18 | **Direct Probe Only** |

Global installation remains completely unperformed, awaiting explicit user authorization.

---

## 4. Empirical Single-Effect Verification

### 4.1 Methodology & Strict Scratch Budget
- **Scratch Directory:** `/tmp/probe_test`
- **Total Scratch Disk Usage:** `56 KiB` (strictly complying with $\le 100$ MiB scratch limit)
- **Harness Stub:** `probe_stub.cjs` configured via `ZCODE_CJS` environment variable to emulate ZCode harness streaming behavior and record mode flags, invocations, and argv:
  - If `--mode yolo` is received, appends `effect:inner\n` to the probe log on every invocation.
  - Streams a `Bash` tool call requesting `echo effect:outer >> <probe_log>` on turn 0, followed by completion on turn 1.

### 4.2 Comparative Execution Results

#### Arm A: Old Installed Binary (`~/.local/lib/zcodex/zcodex`)
- **Invocation Command:**
  ```bash
  env ZCODE_CJS=/tmp/probe_test/probe_stub.cjs PROBE_FILE=/tmp/probe_test/probe_old.log \
    /home/alexey/.local/lib/zcodex/zcodex exec --dangerously-bypass-approvals-and-sandbox \
    --skip-git-repo-check -C /tmp/probe_test --json "run probe"
  ```
- **Child Spawn argv:** Passed `"--mode", "yolo"` to child process.
- **Rollout Session:** `rollout-2026-10-03T06-23-23-01a10000-a0d3-7e93-9d4c-8749ff74e132.jsonl`
- **Rollout Function Calls Emitted:** 1 (`id=fc_01a10000-a3ac-7590-b40c-ddb17051dd5a`, `name=exec_command`)
- **Raw Probe Log (`/tmp/probe_test/probe_old.log`):**
  ```text
  effect:inner
  effect:outer
  effect:inner
  ```
- **Observed Side-Effect Count:** **3 side effects** (2 inner + 1 outer) per single emitted tool call.

#### Arm B: New Debug Binary (`codex-rs/target/debug/zcodex`)
- **Invocation Command:**
  ```bash
  env ZCODE_CJS=/tmp/probe_test/probe_stub.cjs PROBE_FILE=/tmp/probe_test/probe_new.log \
    /home/alexey/git/codex-zcode/codex-rs/target/debug/zcodex exec --dangerously-bypass-approvals-and-sandbox \
    --skip-git-repo-check -C /tmp/probe_test --json "run probe"
  ```
- **Child Spawn argv:** Passed `"--mode", "build"` to child process.
- **Rollout Session:** `rollout-2026-10-03T06-23-37-01a10000-d738-7092-ad94-3039260a2717.jsonl`
- **Rollout Function Calls Emitted:** 1 (`id=fc_01a10000-d9fe-7bb2-b58e-04fc452380f2`, `name=exec_command`)
- **Raw Probe Log (`/tmp/probe_test/probe_new.log`):**
  ```text
  effect:outer
  ```
- **Observed Side-Effect Count:** **EXACTLY 1 side effect** (0 inner + 1 outer).

### 4.3 Direct Production CJS Verification
Direct execution against `/opt/ZCode/resources/glm/zcode.cjs`:
- `node zcode.cjs --mode yolo --prompt "Use Bash to append 'INNER' to /tmp/test_yolo.log"`:
  - Tool call was executed internally by the inner agent loop.
  - `/tmp/test_yolo.log` contained `INNER`.
- `node zcode.cjs --mode build --prompt "Use Bash to append 'INNER' to /tmp/test_build.log"`:
  - Tool call was rejected: `"Bash failed with No permission client configured for Bash"`.
  - `/tmp/test_build.log` did not exist.
  - Authoritative tool call events were streamed to stdout for outer client handling.

---

## 5. Conclusion & Bounded Operational Status

1. **Synthetic Regression & Production Child Denial Established:**
   - Synthetic adapter test (`probe_stub.cjs`) verified that the CLI cold-spawn mode flag change (`--mode build`) eliminates inner stub tool executions that occurred under `--mode yolo` (reducing side effects from 3 to 1 per tool call).
   - Direct execution of production CJS (`/opt/ZCode/resources/glm/zcode.cjs`) confirmed that write-capable tool calls are denied internally (`"No permission client configured for Bash"`), confirming child denial.
2. **Open Scopes & Validations:**
   - Real outer live execution combining the debug binary with production CJS on an identical live task, as well as retry/resume behavior with fixed operation IDs, remain separate validations and are not established by stub regression alone.
   - Pinned independent review by Muse/principals is required before declaring full task completion.
3. **Strict Resource Compliance:** All compilation is halted. Host has 103 GiB free. Scratch usage was 56 KiB. Global `/home/alexey/.local` binaries are 100% untouched. No global install is performed or inferred.
