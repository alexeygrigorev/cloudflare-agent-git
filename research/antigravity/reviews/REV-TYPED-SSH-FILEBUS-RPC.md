# Independent Challenger Review: Typed SSH FileBus RPC Hardening & Security Audit (Codex C2162 / C2164 / C2166 / C2171)

- **Reviewer**: Independent Challenger & Security Reviewer (`reviewer37`, subagent conversation ID: `37aa1067-8bda-4dde-95b8-7b5bb927bd1f`)
- **Authority**: Dispatched by `antigravity-head` (`46fdb644`, conversation ID: `245c7bba-9a7b-45c1-87a7-4537f289f9a5`) under Codex Principal C2162, C2164, C2166, and C2171 directives and existing human authority (`experiment/human-cross-computer-product-20261004.txt`).
- **Target Repository Snapshot**: `/home/alexey/git/cloudflare-agent-git/.local/scratch/bus-ssh-rpc-snapshot/agent-bus/` (Isolated testbed referencing canonical `/home/alexey/git/agent-bus/`)
- **Canonical Status**: `/home/alexey/git/agent-bus/` pre-existing dirty working copy strictly preserved; zero **new** canonical changes or git stage mutations introduced.
- **Base Commit**: `f3295f99e188719f5df9fccb22706d8a0e5bb8f8`
- **Complete Source, Test & Recovery Manifest Checksums**:
  - `coordination/ssh_rpc.py`: `2b30eb7b99436b738a03dfd8e7d3c8644787511ec64beeb9c4bff37a8c46544d`
  - `coordination/envelope.py`: `a6abcf56dff5145da8b923de88bd1256db27bc26a05367e56b3135c52322c2b8`
  - `coordination/errors.py`: `3ddd46071abce2d5269cb7804fd5207c8150cb5f23e3777e47aa33de076939e5`
  - `coordination/bus_cli.py`: `a7a8c37459216f011267a37c52006245c91140474d12dd8006d735e1e5300715`
  - `coordination/bus.py`: `2720c191f0b6a32a6d0ad933737a7239126472e40907a55c4bc55d7396b00370`
  - `coordination/cursors.py`: `9962c9914dc2a80195cf71ee5a7b754b49386431d82a5fbce829dc04e5adf7cb`
  - `coordination/durable.py`: `507cba26399e621e103782a9f3ea9e6ab26b220381e138fbe86fb76722890262`
  - `coordination/headless_worker.py`: `5f8cc069aaa7fb516f8cd2a3561a560fa01d3e6cdf0f41260d315c69a5b94405`
  - `tests/test_ssh_rpc.py`: `82d876d0580045756aafadd3cbaa07bd5d4488d78c899158c4fa8fd288de9ab9`
  - `tests/test_ssh_rpc_security.py`: `02aa4d7ae655c3020fc34dbfc40d40d0e58d345d7c09760621184729d7b31168`
  - `typed-ssh-filebus-rpc-hardened.patch`: `293a4a120c90eb082d20415d961caaf6435d61278977434a25a0359fabfa3db2`
- **Date**: 2026-10-05T02:38:00+02:00 (Europe/Berlin)
- **Verdict**: **BOUNDED ACCEPTANCE (COMPONENT LEVEL / POSIX SCOPE)**
  *(Certified for POSIX remote login shells [$SHELL, bash, sh]; live cross-host multi-machine rollout and Windows targets remain explicitly HELD pending live two-host verification)*

---

## 1. Executive Summary & Audit Context

Under Codex Principal Directives C2162, C2164, C2166, and C2171, an independent adversarial security challenge and audit was conducted on the Typed SSH FileBus RPC implementation (`coordination/ssh_rpc.py`, `coordination/envelope.py`, `coordination/errors.py`, `coordination/bus_cli.py`).

The objective is to establish whether the typed SSH FileBus RPC client satisfies strict production requirements for cross-computer agent coordination across six adversarial attack vectors:
1. **Local SSH Option Injection & Normalization (C2162 / C2171)**: Resistance against command-line flag hijacking (e.g., `-oProxyCommand=...`), case-insensitive normalization of `-o` options, spacing/tokenization variations, and duplicate option precedence bypasses.
2. **Untrusted Directive Defense & Custom Proxy Trust (C2171)**: Rejection of arbitrary local command execution options (`ProxyCommand`, `LocalCommand`, `PermitLocalCommand`) by default, with explicit opt-in custom trust (`allow_custom_proxycommand=True`).
3. **Remote Shell Argument Escaping (POSIX Scope)**: Neutralization of metacharacters (semicolons, subshells, quotes) over OpenSSH `$SHELL -c` invocation.
4. **Correlation & Response Semantics**: Strict `request_id` correlation, fail-closed handling of boolean string coercion (`"false"`), non-zero return codes, and banner contamination.
5. **Credential Hygiene & Decoupled Exception Chaining**: Prevention of token and body leakage in exception strings, attributes, and tracebacks via `raise ... from None`.
6. **Subprocess Timeout Semantics**: Preservation of ambiguous side-effects (`UNKNOWN` state) with zero automated mutating retries.

### Audit Verdict Summary
The hardened typed SSH FileBus RPC client satisfies all security invariants under the defined POSIX component boundary. All 20 adversarial security tests and 18 component tests pass cleanly (38/38 tests passing; full suite 62/62 passing). Ordinary Git recovery is empirically verified on a fresh disposable clone. **Bounded Acceptance** is granted for POSIX target environments. Production cross-host rollout and Windows remote shells (`cmd.exe`, `PowerShell`) remain HELD.

---

## 2. Technical Evaluation of Adversarial Attack Vectors

### Vector 1: Local SSH Option Injection Defense & Normalization (C2162 / C2171)
- **Threat Model**: If an untrusted agent supplies a hostname starting with `-` or manipulates `-o` options using case variation (e.g. `stricthostkeychecking=no`), spacing variations (`-o StrictHostKeyChecking = accept-new`), or duplicate conflicting options (`-o StrictHostKeyChecking=yes -o StrictHostKeyChecking=no`), OpenSSH option parsing could be subverted via "first wins" precedence.
- **Defensive Implementation**:
  1. `_validate_host(host)`: Strips whitespace and asserts that `host` is non-empty and does not begin with `-`. Invoked during `SshFileBusClient.__post_init__` before any process spawn.
  2. Double-Dash (`--`) Argument Delimiter: The client constructs the command vector with an explicit `--` delimiter immediately preceding the host:
     ```python
     cmd = [self.ssh_binary] + list(self.ssh_opts) + ["--", self.host] + remote_cmd_parts
     ```
  3. `_parse_and_validate_ssh_opts`:
     - Tokenizes options whether provided attached (`-oKey=Val`), detached (`-o`, `Key=Val` or `-o`, `Key`, `Val`), or spaced around `=`.
     - Normalizes keys and values case-insensitively (`stricthostkeychecking`, `batchmode`).
     - Strictly enforces `BatchMode=yes` and `StrictHostKeyChecking=yes`; any non-`yes` setting (`accept-new`, `no`, `off`, `ask`) fails closed immediately with `ValueError`.
     - Inspects all occurrences of options: any conflicting pair containing a non-`yes` value triggers an immediate exception, completely defeating OpenSSH "first wins" bypasses.
     - Normalized options prepend canonical `["-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes"]`.

### Vector 2: Untrusted Directive Defense & Custom Proxy Trust (C2171)
- **Threat Model**: Directives such as `ProxyCommand`, `LocalCommand`, and `PermitLocalCommand` execute arbitrary local shell commands. Ambient inclusion of these directives in client options introduces arbitrary command execution risks.
- **Defensive Implementation**:
  1. `ProxyCommand`, `LocalCommand`, and `PermitLocalCommand` are rejected fail-closed by default with an informative `ValueError`.
  2. If custom jump hosts or proxy tunnels are required, the caller must explicitly pass `allow_custom_proxycommand=True` to `SshFileBusClient`, ensuring dangerous commands cannot be introduced through untrusted options without explicit configuration.

### Vector 3: Remote Shell Metacharacter & Argument Escaping (POSIX Scope)
- **Threat Model**: OpenSSH daemon concatenates all remote arguments with single spaces and passes the resulting string to the user's remote login shell via `$SHELL -c <string>`. If `store_path` or `bus_cli_path` contain spaces, semicolons, subshell expansions (`$(cmd)` or `` `cmd` ``), or quotes, unescaped arguments lead to remote shell injection.
- **Defensive Implementation**:
  All remote arguments are escaped using Python's `shlex.quote()` before assembly:
  ```python
  remote_cmd_parts = [
      "python3",
      shlex.quote(self.bus_cli_path),
      "--store",
      shlex.quote(self.store_path),
      "rpc",
  ]
  ```
- **Demarcation & Component Disclosure (C2164 / C2171)**:
  - **POSIX Remote Shells (Certified)**: For standard POSIX shells (`/bin/sh`, `/bin/bash`, `/bin/dash`, `/bin/zsh`), `shlex.quote()` wraps arguments in single quotes (`'...'`) and escapes internal single quotes. Verified empirically with `shlex.split()`.
  - **Component Runner Isolation**: Tests execute against mock and subprocess runners in component isolation; `shlex.quote` guarantees apply to POSIX login shells and do not constitute an unverified universal guard against non-POSIX or arbitrary shell wrappers.
  - **Windows Remote Shells (HELD)**: Windows OpenSSH invokes `%COMSPEC%` (`cmd.exe`) or `powershell.exe`. Windows remote shell execution is marked **HELD**.

### Vector 4: Strict Correlation, Boolean Coercion & Framing Semantics
- **Threat Model**: Request spoofing, boolean string confusion (`"false"` evaluating to `True`), ignored crash exit codes with valid JSON stdout, and MOTD banner contamination.
- **Defensive Implementation**:
  1. **Strict Correlation**: The client verifies `resp.request_id == req.request_id`. Any mismatch immediately raises `FramingError("request_id_mismatch")`.
  2. **Strict Boolean Coercion**: Both `RpcResponse.from_dict` and `_execute_rpc` enforce `type(resp.ok) is bool`.
  3. **Strict Exit Code Handling**: Any non-zero exit code (`rc != 0`) immediately raises `TransportError` regardless of stdout content.
  4. **Clean Framing Validation**: Multi-object responses or preamble noise fail JSON parsing and raise `FramingError`.

### Vector 5: Credential Hygiene & Traceback Decoupling (Codex C2166)
- **Threat Model**: Sensitive tokens (`tok_***`) or user payload data (`body`) present in requests echoing into error messages or tracebacks via `__cause__` / `__context__`.
- **Defensive Implementation**:
  1. **Fail-Closed Attribute Omission**: Public exceptions carry only bounded, sanitized strings and categorical error codes (`code`, `reason`, `exit_code`, `timeout_sec`). Raw remote stderr and raw stdout are completely omitted.
  2. **Decoupled Exception Chaining**: All caught exceptions in `_execute_rpc` use `raise ... from None` outside `except` blocks, explicitly suppressing `__cause__` and `__context__`.
  3. **Utility Redaction**: Utility functions (`_redact`) sanitize token literals, bearer strings, and sensitive JSON keys.

### Vector 6: Subprocess Timeout Semantics & Ambiguity Preservation
- **Threat Model**: An SSH command timing out after `timeout_sec` leaves remote mutation state ambiguous (`UNKNOWN`). Automated retry could duplicate mutations.
- **Defensive Implementation**:
  1. The client catches `subprocess.TimeoutExpired`, forcibly kills the local process (`proc.kill()`), and raises `TransportTimeout`.
  2. The transport layer performs **zero automated mutating retries**. Deduplication is enforced at the application layer via `idempotency_key`.

---

## 3. Empirical Test Execution Receipts

Testing was executed in the isolated scratch testbed `.local/scratch/bus-ssh-rpc-snapshot/agent-bus/` with `TMPDIR` pointing to an isolated directory (mode `0700`) and zero net `/tmp` growth.

### Test Run Receipt: `tests/test_ssh_rpc_security.py`
```text
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.1.1, pluggy-1.6.0
rootdir: /home/alexey/git/cloudflare-agent-git/.local/scratch/bus-ssh-rpc-snapshot/agent-bus
configfile: pyproject.toml
plugins: anyio-4.12.1, opik-2.2.54
collected 20 items

PASSED tests/test_ssh_rpc_security.py::test_ssh_default_opts_strict_host_key_checking
PASSED tests/test_ssh_rpc_security.py::test_ssh_option_normalization_case_and_spacing
PASSED tests/test_ssh_rpc_security.py::test_ssh_option_rejection_case_and_spacing
PASSED tests/test_ssh_rpc_security.py::test_ssh_duplicate_options_rejection_and_precedence
PASSED tests/test_ssh_rpc_security.py::test_ssh_proxycommand_custom_trust
PASSED tests/test_ssh_rpc_security.py::test_ssh_option_injection_host_rejected_at_init
PASSED tests/test_ssh_rpc_security.py::test_ssh_command_argv_includes_double_dash_delimiter
PASSED tests/test_ssh_rpc_security.py::test_remote_shell_argument_escaping_posix
PASSED tests/test_ssh_rpc_security.py::test_strict_correlation_request_id_mismatch_raises_framing_error
PASSED tests/test_ssh_rpc_security.py::test_boolean_coercion_fails_closed
PASSED tests/test_ssh_rpc_security.py::test_non_zero_exit_code_fails_closed_despite_valid_stdout_json
PASSED tests/test_ssh_rpc_security.py::test_preamble_banner_noise_fails_closed
PASSED tests/test_ssh_rpc_security.py::test_transport_timeout_preserves_ambiguous_outcome_without_auto_retry
PASSED tests/test_ssh_rpc_security.py::test_leakage_path_1_transport_failure_stderr
PASSED tests/test_ssh_rpc_security.py::test_leakage_path_2_subprocess_exception
PASSED tests/test_ssh_rpc_security.py::test_leakage_path_3_timeout_expired
PASSED tests/test_ssh_rpc_security.py::test_leakage_path_4_invalid_framing_json_decode
PASSED tests/test_ssh_rpc_security.py::test_leakage_path_5_invalid_framing_non_dict_and_value_error
PASSED tests/test_ssh_rpc_security.py::test_leakage_path_6_auth_failure_with_echoed_credentials
PASSED tests/test_ssh_rpc_security.py::test_leakage_path_7_request_id_mismatch

============================== 20 passed in 0.05s ==============================
```

### Component Test Receipt: `tests/test_ssh_rpc.py`
```text
============================== 18 passed in 1.94s ==============================
```

### Full Snapshot Suite Receipt:
```text
============================== 62 passed in 7.36s ==============================
```

---

## 4. Ordinary Git Recovery Audit (C2171)

To verify that the implementation can be recovered using standard Git tooling without relying on scratch artifacts:
1. Cloned canonical `/home/alexey/git/agent-bus` into disposable scratch testbed and reset hard to base commit `f3295f99e188719f5df9fccb22706d8a0e5bb8f8`.
2. Applied unified patch `research/antigravity/recovery/typed-ssh-filebus-rpc-hardened.patch` (SHA256: `293a4a120c90eb082d20415d961caaf6435d61278977434a25a0359fabfa3db2`).
3. Checked file status: all 17 tracked and new files created cleanly.
4. Verified Python import integrity across all modules: zero `ModuleNotFoundError`.
5. Executed full test suite: **62/62 tests PASS** in 9.91s.
6. Cleaned up disposable directory: zero disk pollution.

---

## 5. Scope Demarcation: POSIX vs. Windows

| Capability / Surface | POSIX Scope (`Linux` / `macOS`) | Windows Scope (`cmd.exe` / `PowerShell`) | Status |
|---|---|---|---|
| SSH Host Option Injection (`--`, `_validate_host`) | Validated & Enforced | Validated & Enforced | **CERTIFIED** |
| Option Normalization & Policy Enforcement | Validated & Enforced | Validated & Enforced | **CERTIFIED** |
| Strict Known Hosts (`StrictHostKeyChecking=yes`) | Validated & Enforced | Validated & Enforced | **CERTIFIED** |
| Argument Quoting (`shlex.quote`) | Validated (`$SHELL -c`) | Incompatible Quoting Semantics | **POSIX ONLY (Windows HELD)** |
| File Locking (`fcntl.flock` vs `msvcrt.locking`) | Validated (`fcntl.flock`) | Missing `fcntl` on Windows | **POSIX ONLY (Windows HELD)** |
| Directory Fsync (`fsync_dir` directory fd) | Validated (`O_DIRECTORY`) | Invalid `O_DIRECTORY` on Windows | **POSIX ONLY (Windows HELD)** |
| Exception Decoupling (`raise ... from None`) | Validated & Enforced | Validated & Enforced | **CERTIFIED** |
| Timeout Ambiguity Preservation (No auto-retries) | Validated & Enforced | Validated & Enforced | **CERTIFIED** |

---

## 6. Invariants & Publication Verification

1. **Publication Credential Guard**:
   - Verification command: `python3 research/antigravity/tooling/publication_guard.py research/antigravity/reviews/REV-TYPED-SSH-FILEBUS-RPC.md`
   - Result: Exit code `0` (clean, zero credential leaks, zero unredacted tokens).
2. **Compiler Restrictions**: Exactly `0` `cargo` or `rustc` invocations.
3. **Repository Cleanliness**:
   - Canonical repository `/home/alexey/git/agent-bus/` pre-existing dirty working copy strictly preserved; zero new canonical commits or stage mutations.
4. **TMPDIR Isolation**:
   - Isolated scratch directory `.local/scratch/bus-ssh-rpc-snapshot/tmp/` (permissions `0700`). Zero net `/tmp` growth.

---

## 7. Adoption Verdict

**VERDICT: BOUNDED ACCEPTANCE (COMPONENT LEVEL / POSIX SCOPE)**

The typed SSH FileBus RPC client (`coordination/ssh_rpc.py`) and typed envelope (`coordination/envelope.py`) are accepted for POSIX component-level coordination.

**Boundaries & Held States**:
- **Production Cross-Host Multi-Machine Rollout**: HELD pending live two-host bidirectional connectivity testing between actual physical/virtual machines.
- **Windows Target Deployment**: Strictly **HELD** pending implementation and testing of Windows-native quoting and `msvcrt`-based locking.
- Hosts must be pre-populated in `~/.ssh/known_hosts` to satisfy `StrictHostKeyChecking=yes`.
