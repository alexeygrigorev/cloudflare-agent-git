# REPORT: Deployed-Binary / Source-Pin Forensic Receipts & Temp Environment Boundaries (C2145 / C2149)

**Directives**: Codex Principal Directives C2145 & C2149 (and C2134, C2136, C2141)  
**Author / Role**: Self-Organization Architect (tag: `architect06`)  
**Parent**: `antigravity-head` (`46fdb644`, id: `245c7bba-9a7b-45c1-87a7-4537f289f9a5`)  
**Workspace**: `/home/alexey/git/cloudflare-agent-git`  
**Scratch Root**: `/home/alexey/git/cloudflare-agent-git/.local/scratch/self-org-arch/` (mode `0700`, <= 512 MB)  
**Date**: 2026-10-05  
**Credential Validation**: `research/antigravity/tooling/publication_guard.py` (Exit Code `0` CLEAN)  

---

## 1. Executive Summary & Epistemic Boundaries (C2149)

Under Codex Principal Directives C2145 and C2149, a read-only forensic inspection was conducted to audit the deployed `zcodex` executable, its bash wrapper, the upstream `codex-zcode` source tree, and the temporary file creation mechanisms.

### 1.1 Strict Separation of Facts, Inferences, and Unknowns
1. **Empirical Fact 1 (Deployed Binary Fingerprint)**:
   - Path: `/home/alexey/.local/lib/zcodex/zcodex`
   - File Size: 385,842,520 bytes (368 MiB)
   - GNU Build ID: `9ddfd453a7fda881b49849b0a8e019698a6067da`
   - SHA256: `dce345ed47fb4190bb85771ad8ff1dc39cc8c19665fa433475c715689f7268e9`
2. **Empirical Fact 2 (Source Repository Pin)**:
   - Repository: `/home/alexey/git/codex-zcode/`
   - HEAD Commit: `bf9d7ed22a70fd205045c75688f1f1a79877ee8f` (*"Spawn the Zcode cold wire in build mode so tool calls run once"*)
   - Working Tree State: Clean (0 uncommitted changes).
3. **Epistemic Unknown (Source-to-Binary Parity)**:
   - **Status: UNKNOWN (UNPROVEN)**.
   - The Build ID `9ddfd453...`, binary SHA `dce345ed...`, and git commit `bf9d7ed...` are separate forensic facts.
   - In the absence of a reproducible build receipt, compiler artifact manifest, or signed build provenance record, **no causal mapping proves that the deployed binary was compiled from that exact commit**. Parity cannot be certified without reproducible build evidence.
4. **Empirical Fact 3 (Source Code Tempfile Mechanism)**:
   - In `/home/alexey/git/codex-zcode/codex-rs/core/src/client.rs` lines 942–956, temporary prompt files are created via:
     `std::env::temp_dir().join(format!("zcode-prompt-{}", uuid::Uuid::new_v4().as_simple()))`.
   - `ZcodePromptFileGuard` (lines 358–372) implements RAII `Drop` to remove the file on normal completion or error handling.
   - **Limitation**: Rust `Drop` destructors **do not execute** on `SIGKILL`, uncatchable process aborts, or kernel panics.
5. **Empirical Fact 4 (Test 33 Scope & Boundary)**:
   - Test 33 in `tests/test_launcher_bus_bridge.py` empirically proves Python subprocess tempfile containment (`tempfile.NamedTemporaryFile`) within `.local/tmp` under systemd `-E TMPDIR=...` and prelude `os.environ["TMPDIR"] = ...`.
   - **Boundary**: Test 33 does **NOT** execute the compiled Rust `zcodex` binary or the Node `zcode.cjs` model chain. Whole-chain empirical zero `/tmp` for the live model execution path is **NOT** proven by Test 33.
6. **Operating Invariant (Model Route Status)**:
   - **Live same-route external model adapter execution remains strictly HELD** under Directives C2118, C2133, and C2142 pending authentic end-to-end integration and producer attribution.
   - **Zero cargo / rustc compiler invocations**: Entire audit was conducted strictly read-only with 0 compiler invocations host-wide.

---

## 2. Deployed Executable & Wrapper Verification

### 2.1 Wrapper Script Audit (`/home/alexey/.local/bin/zcodex`)
- **Path**: `/home/alexey/.local/bin/zcodex`
- **File Type**: Bourne-Again shell script, ASCII text executable (mode `0755`)
- **Exact File Content**:
  ```bash
  #!/usr/bin/env bash
  # Launch the last explicitly installed zcodex build, independent of Cargo's target directory.
  set -euo pipefail

  exec /home/alexey/.local/lib/zcodex/zcodex "$@"
  ```
- **Analysis**:
  - The script executes `exec` directly, replacing the shell process with the target binary.
  - The caller's process environment (including `TMPDIR`, `TEMP`, and `TMP`) is passed through to `/home/alexey/.local/lib/zcodex/zcodex`.

### 2.2 Deployed Binary Forensic Markers (`/home/alexey/.local/lib/zcodex/zcodex`)
- **Path**: `/home/alexey/.local/lib/zcodex/zcodex`
- **File Size**: 385,842,520 bytes (368 MiB)
- **ELF Type**: ELF 64-bit LSB pie executable, x86-64, dynamically linked, stripped
- **GNU Build ID**: `9ddfd453a7fda881b49849b0a8e019698a6067da`
- **SHA256 Checksum**: `dce345ed47fb4190bb85771ad8ff1dc39cc8c19665fa433475c715689f7268e9`
- **String Markers**:
  - Contains explicit strings matching `TMPDIR`, `TMP`, `SHELL`, `LC_ALL`, and `LOGNAME`.
  - References `gix_tempfile::handle::Writable` (gitoxide's `gix-tempfile` crate).
  - Contains error strings: `"The tempfile with id ... wasn't available anymore"`.

---

## 3. Source Repository Inspection (`/home/alexey/git/codex-zcode/`)

### 3.1 Git Repository Metadata
- **Directory**: `/home/alexey/git/codex-zcode`
- **HEAD Commit**: `bf9d7ed22a70fd205045c75688f1f1a79877ee8f`
  ```text
  commit bf9d7ed22a70fd205045c75688f1f1a79877ee8f (HEAD -> main)
  Author: Alexey Grigorev <alexey.s.grigoriev@gmail.com>
  Date:   Sat Oct 3 04:45:44 2026 +0200

      Spawn the Zcode cold wire in build mode so tool calls run once
  ```
- **Working Tree State**: Clean (`git status -s` returns 0 entries, exit code 0).
- **Cargo Workspace Lockfile**:
  - Path: `/home/alexey/git/codex-zcode/codex-rs/Cargo.lock`
  - Version: 4
  - Package `codex-cli`: version `0.0.0`

### 3.2 Source-to-Binary Parity Assessment
- **Build ID**: `9ddfd453a7fda881b49849b0a8e019698a6067da`
- **Binary Hash**: `dce345ed47fb4190bb85771ad8ff1dc39cc8c19665fa433475c715689f7268e9`
- **Source HEAD**: `bf9d7ed22a70fd205045c75688f1f1a79877ee8f`
- **Forensic Assessment**: **UNKNOWN**.
  While the repository source contains the ZCode cold-wire modifications, there is no cryptographically verifiable build log or binary metadata proving that the binary at `/home/alexey/.local/lib/zcodex/zcodex` was produced from commit `bf9d7ed`.

---

## 4. Source Code Forensic Analysis: Tempfile Generation in `client.rs`

Inspection of `/home/alexey/git/codex-zcode/codex-rs/core/src/client.rs` provides direct evidence of where prompt files are generated and managed.

### 4.1 Exact Source Implementation: `write_zcode_prompt_file`
From `client.rs` lines 942–956:

```rust
/// Spawning `node zcode.cjs --prompt <text>` with the prompt inline hits
/// `E2BIG` ("Argument list too long") once the flattened transcript exceeds
/// `MAX_ARG_STRLEN` (~128 KiB). Passing only small argv entries (loader,
/// runtime path, prompt file path) and rebuilding the real argv in-process
/// avoids the `execve` limit without changing what ZCode sees.
const ZCODE_PROMPT_LOADER: &str = r#"const fs=require("fs");const r=process.argv[1];const f=process.argv[2];const p=fs.readFileSync(f,"utf8");process.argv=[process.argv[0],r,"--prompt",p,...process.argv.slice(3)];require(r);"#;

fn write_zcode_prompt_file(prompt: &str) -> std::io::Result<PathBuf> {
    use std::io::Write as _;
    let path =
        std::env::temp_dir().join(format!("zcode-prompt-{}", uuid::Uuid::new_v4().as_simple()));
    let mut options = std::fs::OpenOptions::new();
    options.write(true).create_new(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        options.mode(0o600);
    }
    let mut file = options.open(&path)?;
    file.write_all(prompt.as_bytes())?;
    Ok(path)
}
```

### 4.2 RAII Guard & Cleanup Limitations: `ZcodePromptFileGuard`
From `client.rs` lines 358–372 and line 3459:

```rust
/// Removes a ZCode prompt temp file when it goes out of scope.
///
/// The streaming task can exit early (spawn failure, client disconnect) or be
/// cancelled; relying on explicit `remove_file` calls at each exit leaked
/// files (observed as stale `zcode-prompt-*` entries in `/tmp`). Holding this
/// guard for the task lifetime makes cleanup unconditional.
struct ZcodePromptFileGuard {
    path: PathBuf,
}

impl Drop for ZcodePromptFileGuard {
    fn drop(&mut self) {
        let _ = std::fs::remove_file(&self.path);
    }
}
```

### 4.3 Epistemic Evaluation of Cleanup Behavior
1. **Normal & Handled Exit**: The `ZcodePromptFileGuard` calls `std::fs::remove_file` when dropped at the end of the streaming task.
2. **Abnormal Termination / Crash**: As defined by Rust's language semantics, `Drop` implementations **do not execute** if the process receives an uncatchable signal (such as `SIGKILL`), encounters a double panic, or is forcibly terminated by an external supervisor. In such cases, the prompt file remains on disk.
3. **Historical Residue**: When `zcodex` was previously executed without explicit `TMPDIR` redirection, prompt files were created in host `/tmp`, explaining the observed accumulation of stale `zcode-prompt-*` files.

---

## 5. Python Environment Containment & Test 33 Scope

### 5.1 Environment Configuration in `launcher_bus_bridge.py`
In `research/antigravity/tooling/self_org/launcher_bus_bridge.py`:

1. **Systemd Scope Command** (lines 1510–1512):
   ```python
   scope_cmd = [
       "systemd-run",
       "--user",
       "--scope",
       "--collect",
       f"--unit={unit_name}",
       "-p", f"MemoryMax={requested_memory_mb}M",
       "-E", f"TMPDIR={tmpdir_path}",
       "-E", f"TEMP={tmpdir_path}",
       "-E", f"TMP={tmpdir_path}",
       "--",
       sys.executable,
       str(prelude_script),
   ] + list(command_argv)
   ```
2. **Prelude Environment Injection** (lines 1493–1495):
   ```python
   os.environ["TMPDIR"] = "{tmpdir_path}"
   os.environ["TEMP"] = "{tmpdir_path}"
   os.environ["TMP"] = "{tmpdir_path}"

   os.execvp(sys.argv[1], sys.argv[1:])
   ```

### 5.2 Test 33 Boundaries & Findings
Test 33 in `tests/test_launcher_bus_bridge.py` (`test_33_c2134_tmpdir_containment_in_systemd_scope_non_model`):
- Spawns a Python child process within a verified systemd scope.
- Asserts that `tempfile.gettempdir()` resolves to `.local/tmp`.
- Creates a `NamedTemporaryFile` and asserts its path begins with `.local/tmp`.
- Confirms `is_in_tmp` is strictly `False`.
- Validates on-disk receipts (`child_tmpdir_receipt.json` and `containment_verified_*.json`).

### 5.3 What Test 33 Proves vs. Does Not Prove
- **Proven**: Standard Python child processes running under the hardened `launcher_bus_bridge` scope correctly inherit `TMPDIR` and constrain Python-managed temporary files within `.local/tmp`.
- **Not Proven**: Test 33 does **not** invoke `/home/alexey/.local/bin/zcodex`, does **not** invoke `node zcode.cjs`, and does **not** evaluate multi-process child tree behavior under live model queries. Therefore, whole-chain empirical zero `/tmp` for the live model execution path is **not** proven by Test 33.

---

## 6. Maintainer Intake Recommendation: Source-to-Binary Attestation

To resolve the epistemic gap between source repositories and installed binary artifacts, the project should adopt a formal source-to-binary attestation contract:
1. **Build Manifest Requirement**: Any deployed binary must be accompanied by an installation manifest recording:
   - Git commit SHA and tree hash of the exact source build tree.
   - Build environment metadata (rustc version, cargo lockfile hash).
   - Compiler invocation flags and target triple.
   - SHA256 and GNU Build ID of the resulting binary.
2. **Deterministic / Reproducible Builds**: Ensuring binary builds are reproducible bit-for-bit from source to eliminate unproven binary provenance.

---

## 7. Invariant Compliance Checklist

- [x] **Zero cargo / rustc invocations**: Verified zero calls. Forensic audit used standard inspection tools (`file`, `readelf`, `sha256sum`, `git`).
- [x] **Source-to-Binary Parity Classified as UNKNOWN**: Rigorously documented that Build ID, binary hash, and git commit are separate facts without a proven build mapping.
- [x] **Tempfile Mechanism Documented**: Exact code for `write_zcode_prompt_file` and `ZcodePromptFileGuard` cited from `client.rs`.
- [x] **Cleanup Limitations Acknowledged**: Stated that `Drop` does not protect against `SIGKILL` or abnormal crashes.
- [x] **Test 33 Epistemic Bounds Defined**: Confined to Python subprocess containment; whole-chain model path zero `/tmp` not claimed.
- [x] **Same-Route Model Adapter Held**: Confirmed live external model execution path remains strictly HELD under C2118 / C2133 / C2142.
- [x] **Publication Credential Guard**: Ran `python3 research/antigravity/tooling/publication_guard.py research/antigravity/recovery/REPORT-ZCODEX-SOURCEPIN-PARITY.md` (exit code 0).
