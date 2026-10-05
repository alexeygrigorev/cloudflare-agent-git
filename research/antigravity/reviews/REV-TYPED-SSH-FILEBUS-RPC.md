# Independent Challenger Review: Typed SSH FileBus RPC Hardening & Security Audit (Codex C2162 / C2164 / C2166 / C2171 / C2175 / C2181 / C2182 / C2184 / C2185 / C2186 / C2190 / C2191)

- **Reviewer**: Independent Challenger & Security Reviewer (`reviewer37`, subagent conversation ID: `37aa1067-8bda-4dde-95b8-7b5bb927bd1f`)
- **Authority**: Dispatched by `antigravity-head` (`46fdb644`, conversation ID: `245c7bba-9a7b-45c1-87a7-4537f289f9a5`) under Codex Principal Directives C2162, C2164, C2166, C2171, C2175, C2181, C2182, C2184, C2185, C2186, C2190, and C2191, and existing human authority (`experiment/human-cross-computer-product-20261004.txt`).
- **Target Repository Testbed**: `/home/alexey/git/cloudflare-agent-git/.local/scratch/bus-ssh-rpc-snapshot/agent-bus/`
- **Canonical Repository Status**: Canonical `/home/alexey/git/agent-bus/` was strictly read-only during this review interval; pre-existing working-copy dirt from peer work was preserved (not a claim of pristine repository cleanliness).
- **Base Commit**: `f3295f99e188719f5df9fccb22706d8a0e5bb8f8`
- **Pinned Hardened Patch**: `research/antigravity/recovery/typed-ssh-filebus-rpc-hardened.patch`
  - **Patch SHA256**: `444165fd8821c371e01cb5dfb39775e3be50e466e1b54f2eb7ab982176efc976`
- **Preserved Recovery Test Run Log**: `.local/scratch/reviewer37-patch-audit/recovery_test_run.log`
  - **Recovery Log SHA256**: `93c363d185cf8a12cab203fddceb86a61b41123973f064fc330ed0f164333fc3`
  - **Log Receipt**: `65 passed in 7.49s` on clean disposable clone
- **Restored Source Manifest**: `.local/scratch/reviewer37-patch-audit/restored_manifest.txt`
  - **Manifest SHA256**: `2790e32217de3a85eed80288680b2d05897ba4274a5572ae667e160c74b1bacc`
- **Complete Restored Source & Test Manifest (17 Files)**:
  - `coordination/__init__.py`: `3fb6276d7c7060a107e549308765e9a40bd695ac85de8428b5569c2ab342479c`
  - `coordination/bus.py`: `2720c191f0b6a32a6d0ad933737a7239126472e40907a55c4bc55d7396b00370`
  - `coordination/bus_cli.py`: `a7a8c37459216f011267a37c52006245c91140474d12dd8006d735e1e5300715`
  - `coordination/cursors.py`: `9962c9914dc2a80195cf71ee5a7b754b49386431d82a5fbce829dc04e5adf7cb`
  - `coordination/durable.py`: `507cba26399e621e103782a9f3ea9e6ab26b220381e138fbe86fb76722890262`
  - `coordination/envelope.py`: `a6abcf56dff5145da8b923de88bd1256db27bc26a05367e56b3135c52322c2b8`
  - `coordination/errors.py`: `3ddd46071abce2d5269cb7804fd5207c8150cb5f23e3777e47aa33de076939e5`
  - `coordination/headless_worker.py`: `5f8cc069aaa7fb516f8cd2a3561a560fa01d3e6cdf0f41260d315c69a5b94405`
  - `coordination/ssh_rpc.py`: `6382e6cbb4d6217cf7b484d054c2d81993d4ed5a29ac575746fd680697ed2290`
  - `tests/test_bus.py`: `0aa2c0fbb8616ff3eda78467f21cd36328b9bb2aaba39fcc1eb80e3a1a1e0ef7`
  - `tests/test_bus_concurrent.py`: `cd8509285462004c2597333a0aaaa625a620c4dbab59f474a18316f2629bc315`
  - `tests/test_bus_crash.py`: `1a7f95bc9b9b048ba2028e40cc2039f0e8fd422074862f8c353d707dec2275a8`
  - `tests/test_bus_dogfood.py`: `8d757b963f3a6aa5ddc1e5ab248b8c15cbe1de1b658f48f821480fd90bfd6822`
  - `tests/test_bus_scope.py`: `63d4907368fe4d8195fdd8ac011a822ce4bfdebb95119e9f6edd46c17fead2d7`
  - `tests/test_headless_task.py`: `cbe6bf747b4a6c31fc72aebd306047ff3c3e53d7884f916d48ca50192d230b59`
  - `tests/test_ssh_rpc.py`: `82d876d0580045756aafadd3cbaa07bd5d4488d78c899158c4fa8fd288de9ab9`
  - `tests/test_ssh_rpc_security.py`: `90966ccbcec2ccec934d759d2e81cc2a9d5d5f869d8f11a7b383fb2baa6fa6ce`
- **Authentic Reviewer First Tools**:
  - `sha256sum research/antigravity/recovery/typed-ssh-filebus-rpc-hardened.patch .local/scratch/reviewer37-patch-audit/recovery_test_run.log .local/scratch/reviewer37-patch-audit/restored_manifest.txt`
  - `TMPDIR=.local/scratch/bus-ssh-rpc-snapshot/tmp PYTHONPATH=.local/scratch/bus-ssh-rpc-snapshot/agent-bus python3 -m pytest -v .local/scratch/bus-ssh-rpc-snapshot/agent-bus/tests/test_ssh_rpc_security.py .local/scratch/bus-ssh-rpc-snapshot/agent-bus/tests/test_ssh_rpc.py`
- **Date**: 2026-10-05T02:53:00+02:00 (Europe/Berlin)
- **Verdict**: **BOUNDED ACCEPTANCE (COMPONENT LEVEL / LINUX CLIENT SCOPE)**
  *(Client command assembly, option normalization, narrow flag allowlist, default-deny option allowlist, and exception decoupling verified at component level inside Linux testbed; remote multi-host runtime execution and Windows platform execution remain UNKNOWN/HELD)*

---

## 1. Executive Summary & Epistemic Boundaries (Codex C2175 / C2181 / C2182 / C2190)

An independent, adversarial security challenge and recovery audit was performed on the landed Typed SSH FileBus RPC patch under Codex Principal Directives C2175, C2181, C2182, C2184, C2185, C2186, C2190, and C2191.

### Epistemic Demarcation & Evidence Scope
1. **Trusted Host & Local Environment Configuration Boundary**:
   The OpenSSH client unconditionally evaluates ambient user configuration files (`~/.ssh/config`) and system configuration files (`/etc/ssh/ssh_config`) unless explicitly invoked with `-F /dev/null`. The local host configuration constitutes an administrative trust boundary; universal security guarantees against hostile ambient local user configuration are withheld unless local configuration files are suppressed.
2. **Component & Model Evidence Boundary**:
   All empirical test receipts evaluate client command vector assembly, option parsing and normalization, framing enforcement, and exception decoupling inside an isolated Linux testbed using mock and local subprocess runners.
3. **Withhold Generalized Remote/Network Security Acceptance**:
   Remote host execution against heterogeneous OpenSSH daemons remains unmeasured and is categorized as `UNKNOWN/HELD`. Live cross-host multi-machine network execution has not yet been conducted.
4. **Windows Surfaces UNKNOWN/HELD**:
   Zero Windows execution was performed. All Windows runtime claims, remote shell execution (`cmd.exe`/`PowerShell`), and Windows file locking (`msvcrt`) remain strictly `UNKNOWN/HELD`.
5. **Truthful Evidence Claims**:
   - Exactly zero cargo or rustc invocations were executed in this review interval.
   - Canonical `/home/alexey/git/agent-bus/` was strictly read-only during this review interval; pre-existing working-copy dirt from peer work was preserved (not a claim of pristine repository cleanliness).

---

## 2. Technical Evaluation of Adversarial Defense Vectors

### Vector 1: Local SSH Option Injection & Flag Allowlist Defense (C2162 / C2171 / C2181)
- **Threat Model**: Host parameter injection (`-oProxyCommand=...`), bare positional argument destination hijacking before `--`, bypassing option restrictions via case alteration (`stricthostkeychecking=no`), spacing variations (`-o StrictHostKeyChecking = accept-new`), attached forms (`-oStrictHostKeyChecking=no`), or duplicate options exploiting OpenSSH "first wins" precedence rules.
- **Defensive Implementation**:
  1. `_validate_host(host)`: Disallows empty hosts and rejects any host string starting with `-` prior to subprocess invocation.
  2. Double-Dash (`--`) Argument Delimiter: Inserts `--` immediately before the host operand in the `cmd` list:
     ```python
     cmd = [self.ssh_binary] + list(self.ssh_opts) + ["--", self.host] + remote_cmd_parts
     ```
  3. **Bare Positional Destination Argument Defense (C2181)**:
     Tokens in `ssh_opts` that do not begin with `-` (e.g. `['attacker.com']`) are strictly prohibited (`ValueError`), preventing attackers from injecting an earlier destination operand that would precede the intended host.
  4. **Narrow Flag Allowlist (C2181)**:
     Only vetted command-line flags are permitted:
     `-o`, `-p`, `-i`, `-l`, `-c`, `-F` (with trust), `-4`, `-6`, `-C`, `-q`, `-v`, `-vv`, `-vvv`, `-T`, `-N`, `-n`.
     Port `-p` is validated as an integer between 1 and 65535.
     Any unauthorized flag (e.g. `-D`, `-L`, `-R`, `-X`) immediately fails closed with `ValueError`.
  5. `_parse_and_validate_ssh_opts`:
     - **Normalization**: Handles attached (`-oKey=Val`), detached (`-o`, `Key=Val` or `-o`, `Key`, `Val`), and spaced (`Key = Val`) forms. Keys and values are normalized case-insensitively via `.lower()`.
     - **Strict Enforcement**: Mandatory `BatchMode=yes` and `StrictHostKeyChecking=yes`. Any occurrence of non-`yes` values (`accept-new`, `no`, `off`, `ask`) raises `ValueError`.
     - **Duplicate Handling**: Evaluates all occurrences of options. If conflicting values exist, non-`yes` values fail closed immediately, defeating "first wins" configuration injection.
     - **Canonical Output**: Always prepends canonical `["-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes"]`.

### Vector 2: Default-Deny Option Allowlist & Untrusted Directive Defense (C2185 / C2186)
- **Threat Model**: Ambient configuration of arbitrary executable or inclusion directives (`KnownHostsCommand`, `Include`, `LocalCommand`, `PermitLocalCommand`, `Match`, `PKCS11Provider`, `UserKnownHostsFile`) leading to arbitrary local command execution or policy subversion.
- **Defensive Implementation**:
  1. **Strict Option Key Allowlist (`ALLOWED_SSH_OPTION_KEYS`)**:
     Only vetted options are permitted: `batchmode`, `stricthostkeychecking`, `connecttimeout`, `serveraliveinterval`, `serveralivecountmax`, `tcpkeepalive`, `compression`, `port`, `user`, `identityfile`, `identitiesonly`, `ciphers`, `macs`, `kexalgorithms`, `hostkeyalgorithms`.
  2. Any option outside the allowlist (e.g. `KnownHostsCommand`, `Include`, `LocalCommand`, `PermitLocalCommand`, `PKCS11Provider`, `Match`, `UserKnownHostsFile`, arbitrary strings) strictly fails closed with `ValueError`.
  3. **Custom Proxy Trust (`CUSTOM_TRUST_OPTION_KEYS`)**:
     `ProxyCommand` and `ProxyJump` are permitted ONLY when `allow_custom_proxycommand=True` is explicitly passed; otherwise they fail closed.
  4. **Config File Defense (`-F`)**:
     Custom config file option `-F` is rejected fail-closed by default (`ValueError`) unless `allow_custom_proxycommand=True`.

### Vector 3: Remote Shell Metacharacter & Argument Escaping (POSIX Component Scope)
- **Threat Model**: OpenSSH server concatenates remote arguments into `$SHELL -c <cmd>`. Shell metacharacters (spaces, semicolons, subshell expressions `$(...)`, quotes) in `store_path` or `bus_cli_path` cause command injection.
- **Defensive Implementation**:
  - Remote arguments are wrapped using `shlex.quote()` before assembling the remote vector.
  - **Component Verification**: In component tests using `shlex.split()`, arguments with semicolons, subshells, and spaces are parsed cleanly as literal string tokens.
  - **Boundary Disclosure**: POSIX login shell argument escaping is verified at the component level via mock/subprocess runners; live remote runtime execution across remote hosts is `UNKNOWN/HELD`. Windows remote shells (`cmd.exe`) remain `UNKNOWN/HELD`.

### Vector 4: Strict Correlation, Boolean Coercion & Framing Semantics
- **Threat Model**: Request ID spoofing, type confusion via `"ok": "false"` or `"ok": 1`, non-zero exit codes with JSON stdout, and banner/MOTD noise.
- **Defensive Implementation**:
  1. **Strict Correlation**: `resp.request_id == req.request_id` enforced. Mismatches raise `FramingError("request_id_mismatch")`.
  2. **Strict Boolean Coercion**: `type(resp.ok) is bool` enforced in both envelope decoding and client validation. Non-booleans fail closed.
  3. **Strict Exit Code Handling**: Any non-zero exit code (`rc != 0`) raises `TransportError` regardless of stdout content.
  4. **Clean Framing**: Multi-object output or non-JSON banners fail parsing and raise `FramingError`.

### Vector 5: Credential Hygiene & Traceback Decoupling (Codex C2166)
- **Threat Model**: Echoing secret tokens (`tok_***`) or user payload data (`body`) in error messages, exception attributes, or tracebacks (`__cause__` / `__context__`).
- **Defensive Implementation**:
  1. **Fail-Closed Attribute Omission**: Public exception classes carry only categorical error codes (`code`, `reason`, `exit_code`, `timeout_sec`). Raw remote stdout, stderr, and details dictionaries are completely omitted.
  2. **Decoupled Exception Chaining**: All caught exceptions in `_execute_rpc` are re-raised with `from None` (`raise TransportTimeout(...) from None`, `raise FramingError(...) from None`), preventing traceback leakage through underlying `TimeoutExpired.output` or `JSONDecodeError.doc`.
  3. **Utility Redaction**: Utility functions (`_redact`) scrub token and secret patterns.

### Vector 6: Subprocess Timeout Semantics & Ambiguity Preservation
- **Threat Model**: Network timeout leaves remote mutation state ambiguous (`UNKNOWN`). Automated mutating retries risk duplicate message or identity creation.
- **Defensive Implementation**:
  1. On `subprocess.TimeoutExpired`, client terminates the local process (`proc.kill()`) and raises `TransportTimeout`.
  2. Transport layer performs **zero automated mutating retries**. Deduplication is deferred to application-level `idempotency_key`.

---

## 3. Ordinary Git Recovery Audit (C2171 / C2175 / C2181)

Recovery from the landed patch was verified independently:
1. **Target Patch**: `/home/alexey/git/cloudflare-agent-git/research/antigravity/recovery/typed-ssh-filebus-rpc-hardened.patch`
2. **Patch SHA256**: `444165fd8821c371e01cb5dfb39775e3be50e466e1b54f2eb7ab982176efc976`
3. **Execution**:
   - Cloned canonical `/home/alexey/git/agent-bus` to disposable testbed and reset hard to base commit `f3295f99e188719f5df9fccb22706d8a0e5bb8f8`.
   - Applied patch via `git apply`. All 17 files restored cleanly without warnings.
   - Verified Python import integrity across all restored modules: zero `ModuleNotFoundError`.
   - Executed full test suite: **65/65 tests PASSED** in 7.49s.
   - Recovery test log digest: `93c363d185cf8a12cab203fddceb86a61b41123973f064fc330ed0f164333fc3`.

---

## 4. Empirical Test Execution Receipts

### Adversarial Security Suite (`tests/test_ssh_rpc_security.py`): 23/23 PASS
```text
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.1.1, pluggy-1.6.0
rootdir: /home/alexey/git/cloudflare-agent-git/.local/scratch/bus-ssh-rpc-snapshot/agent-bus
configfile: pyproject.toml
plugins: anyio-4.12.1, opik-2.2.54
collected 23 items

PASSED tests/test_ssh_rpc_security.py::test_ssh_default_opts_strict_host_key_checking
PASSED tests/test_ssh_rpc_security.py::test_ssh_option_normalization_case_and_spacing
PASSED tests/test_ssh_rpc_security.py::test_ssh_option_rejection_case_and_spacing
PASSED tests/test_ssh_rpc_security.py::test_ssh_duplicate_options_rejection_and_precedence
PASSED tests/test_ssh_rpc_security.py::test_ssh_proxycommand_custom_trust
PASSED tests/test_ssh_rpc_security.py::test_ssh_c2181_bare_positional_arguments_rejected
PASSED tests/test_ssh_rpc_security.py::test_ssh_c2181_config_file_and_flags_allowlist
PASSED tests/test_ssh_rpc_security.py::test_ssh_c2185_option_key_allowlist_and_default_deny
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

============================== 23 passed in 0.04s ==============================
```

### Component RPC Suite (`tests/test_ssh_rpc.py`): 18/18 PASS
```text
============================== 18 passed in 1.89s ==============================
```

### Full Snapshot Testbed Suite: 65/65 PASS
```text
============================== 65 passed in 9.61s ==============================
```

---

## 5. Scope Demarcation: POSIX vs. Windows Surfaces

| Capability / Surface | POSIX Scope (`Linux` / `macOS`) | Windows Scope (`cmd.exe` / `PowerShell`) | Audit Status |
|---|---|---|---|
| SSH Host Option Injection (`--`, `_validate_host`) | Validated at component level | Untested on Windows | **POSIX COMPONENT VALIDATED** |
| Positional Destination Argument Defense | Validated at component level | Untested on Windows | **POSIX COMPONENT VALIDATED** |
| Narrow Flag Allowlist & Integer Port Validation | Validated at component level | Untested on Windows | **POSIX COMPONENT VALIDATED** |
| Option Normalization & Mandatory Enforcement | Validated at component level | Untested on Windows | **POSIX COMPONENT VALIDATED** |
| Default-Deny Option Key Allowlist (`ALLOWED_SSH_OPTION_KEYS`) | Validated at component level | Untested on Windows | **POSIX COMPONENT VALIDATED** |
| Untrusted Directive Defense (`ProxyCommand`, `-F`) | Validated at component level | Untested on Windows | **POSIX COMPONENT VALIDATED** |
| Argument Quoting (`shlex.quote`) | Verified at component level via mock/subprocess; remote multi-host execution UNKNOWN/HELD | Incompatible quoting semantics; no Windows execution performed | **POSIX COMPONENT ONLY (Windows UNKNOWN/HELD)** |
| File Locking (`fcntl.flock` vs `msvcrt.locking`) | Validated (`fcntl.flock`) | Missing `fcntl`; no Windows execution performed | **POSIX COMPONENT ONLY (Windows UNKNOWN/HELD)** |
| Directory Fsync (`fsync_dir` directory fd) | Validated (`O_DIRECTORY`) | Invalid `O_DIRECTORY`; no Windows execution performed | **POSIX COMPONENT ONLY (Windows UNKNOWN/HELD)** |
| Exception Decoupling (`raise ... from None`) | Validated at component level | Untested on Windows | **POSIX COMPONENT VALIDATED** |
| Timeout Ambiguity Preservation (No auto-retries) | Validated at component level | Untested on Windows | **POSIX COMPONENT VALIDATED** |

---

## 6. Invariants & Publication Verification

1. **Publication Credential Guard**:
   - Verification command: `python3 research/antigravity/tooling/publication_guard.py research/antigravity/reviews/REV-TYPED-SSH-FILEBUS-RPC.md`
   - Result: Exit code `0` (clean, zero credential leaks, zero unredacted tokens).
2. **Compiler Restrictions**: Exactly `0` `cargo` or `rustc` invocations in this review interval.
3. **Canonical Repository Cleanliness**:
   - Canonical `/home/alexey/git/agent-bus/` was strictly read-only during this review interval; pre-existing working-copy dirt from peer work was preserved.
4. **TMPDIR Isolation & Net Growth**:
   - Isolated scratch directory `.local/scratch/bus-ssh-rpc-snapshot/tmp/` (mode `0700`, strictly <= 512 MB). Net zero growth on `/tmp`.

---

## 7. Adoption Verdict

**VERDICT: BOUNDED ACCEPTANCE (COMPONENT LEVEL / LINUX CLIENT SCOPE)**

The Typed SSH FileBus RPC patch (`typed-ssh-filebus-rpc-hardened.patch`, SHA256: `444165fd...`) is accepted for component-level integration on Linux/POSIX client nodes.

**Boundaries & Held States**:
- **Ambient Configuration Trust Boundary**: Ambient user configurations (`~/.ssh/config`) are an administrative trust boundary; universal protection against hostile local ambient configs is withheld unless local config evaluation is suppressed.
- **Live Multi-Machine Cross-Host Execution**: Remains `UNKNOWN/HELD` pending live bidirectional network execution between distinct host nodes.
- **Windows Runtime and Local Execution**: Strictly `UNKNOWN/HELD` (no Windows execution performed; Windows remote quoting and locking remain unimplemented).
- **Target Known Hosts**: Target hosts must be pre-populated in `~/.ssh/known_hosts` to satisfy enforced `StrictHostKeyChecking=yes`.
