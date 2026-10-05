# REPORT: Hardened Typed SSH FileBus RPC Client & Namespaced Envelope (C2151 / C2154 / C2156 / C2162 / C2164 / C2166 / C2171 / C2175 / C2181 / C2182 / C2184 / C2185 / C2186)

**Directives**: Codex Principal Directives C2151, C2154, C2156, C2162, C2164, C2166, C2171, C2175, C2181, C2182, C2184, C2185, C2186  
**Author / Role**: Self-Organization Architect & Implementer (tag: `architect06`)  
**Parent**: `antigravity-head` (`46fdb644`, id: `245c7bba-9a7b-45c1-87a7-4537f289f9a5`)  
**Workspace**: `/home/alexey/git/cloudflare-agent-git`  
**Snapshot Workspace**: `/home/alexey/git/cloudflare-agent-git/.local/scratch/bus-ssh-rpc-snapshot/agent-bus/`  
**Snapshot TMPDIR**: `/home/alexey/git/cloudflare-agent-git/.local/scratch/bus-ssh-rpc-snapshot/tmp/` (mode `0700`, zero writes to host `/tmp`)  
**Date**: 2026-10-05  
**Credential Validation**: `research/antigravity/tooling/publication_guard.py` (Exit Code `0` CLEAN)  

---

## 1. Executive Summary

Under Codex Principal Directives C2151, C2154, C2156, C2162, C2164, C2166, C2171, C2175, C2181, C2182, C2184, C2185, and C2186, a hardened, narrow, typed SSH FileBus RPC client, namespaced identity envelope, and structured framing protocol have been implemented and validated within an isolated snapshot repository at `.local/scratch/bus-ssh-rpc-snapshot/agent-bus/`.

### 1.1 Key Achievements & C2171 / C2181 / C2185 Hardenings
1. **Canonical Invariant Preserved**: The canonical repository `/home/alexey/git/agent-bus/` pre-existing dirty working copy was strictly preserved; zero **new** canonical changes or branch pollution were introduced.
2. **OpenSSH Option Normalization & Policy Enforcement (C2171 / C2181 / C2185)**:
   - Case-insensitive parsing: Normalizes option keywords and values (`stricthostkeychecking=no`, `batchmode=no`, `BATCHMODE=YES`).
   - Spacing & tokenization: Handles attached (`-oKey=Val`) and detached (`-o`, `Key=Val` or `-o`, `Key`, `Val`) forms, as well as spaces around `=`.
   - Strict enforcement: `BatchMode=yes` and `StrictHostKeyChecking=yes` are strictly mandatory. Any non-`yes` value (`accept-new`, `no`, `off`, `ask`) fails closed immediately with `ValueError`.
   - Duplicate handling & precedence: Evaluates all occurrences of options. If conflicting values are passed (e.g. one `yes` and one `no`), the non-`yes` option triggers an immediate `ValueError`, preventing OpenSSH "first wins" command-line bypass. Identical duplicate options normalize cleanly.
   - Untrusted directive defense & Default-Deny Allowlist (C2185/C2186): Directives that execute arbitrary local commands (`ProxyCommand`, `LocalCommand`, `PermitLocalCommand`, `KnownHostsCommand`) or include external configuration files (`Include`) are rejected fail-closed by default. An explicit default-deny allowlist `ALLOWED_SSH_OPTION_KEYS` is enforced for `-o` flags. Custom proxying is permitted only when explicit custom trust (`allow_custom_proxycommand=True`) is configured.
   - Positional Destination Defense (C2181): Bare positional tokens in `ssh_opts` (not beginning with `-`) are strictly rejected with `ValueError`, preventing destination hijacking before `--`.
   - Narrow Top-Level Flag Allowlist (C2181): Only authorized SSH flags (`-o`, `-p`, `-i`, `-l`, `-c`, `-F`, `-4`, `-6`, `-C`, `-q`, `-v`, `-vv`, `-vvv`, `-T`, `-N`, `-n`) are accepted; `-F` requires custom trust; `-p` requires valid integer port (1–65535).
3. **Fail-Closed Omission over Regex Redaction (C2166)**: Public exceptions (`TransportError`, `TransportTimeout`, `FramingError`, `AuthError`) completely omit raw stdout and stderr strings from error messages and exception attributes. Exceptions carry strictly bounded, sanitized error codes (e.g., `code="remote_transport_failed"`, `exit_code=proc.returncode`, `reason="invalid_json_framing"`, `reason="remote_auth_rejected"`). Raw stdout/stderr and `err.doc` are never embedded in exception messages.
4. **Decoupled Exception Chaining (C2166)**: When handling `subprocess.TimeoutExpired`, `json.JSONDecodeError`, or `ValueError`, exceptions are decoupled via `raise ... from None` outside `except` blocks. This ensures both `__cause__` and `__context__` are `None` and `__suppress_context__` is `True`, permanently preventing raw stdout/stderr from leaking via Python traceback inspection.
5. **Request ID Mismatch Guard (C2166)**: If `resp.request_id != req.request_id`, raises `FramingError("request_id_mismatch") from None` without printing or reflecting unredacted payload data.
6. **Host Option Injection Defense (C2162)**: Rejects host names starting with a hyphen (`-`) and inserts `--` before the host argument in the SSH argv list (`ssh [...] -- <host> <command>...`), preventing OpenSSH flag injection.
7. **Remote Shell Argument Escaping (C2162)**: All command arguments (`bus_cli_path`, `--store`, `store_path`, `rpc`) are escaped via `shlex.quote()` on the client side.
8. **POSIX Remote-Shell Scope Boundary (C2164 / C2171)**: Escaping guarantees are formally demarcated for POSIX-compliant login shells (`sh`, `bash`, `dash`, `zsh`). Windows remote targets (`cmd.exe` / `powershell.exe`) feature distinct escaping and locking semantics and remain explicitly held / out-of-scope for remote execution.
9. **Component & FakeRunner Isolation Disclosure (C2171)**: All tests evaluate client command assembly, escaping, and exception decoupling against component runner mocks (`default_subprocess_runner` / mock runner); remote invocation assumes POSIX login shells (`shlex.quote`), not an unverified universal guard or an active multi-host network. Two-host gate remains HELD until live multi-host testing.
10. **Zero Credential or Payload Leakage in Argv**: Message bodies, metadata, tokens, and credentials are transmitted strictly over stdin JSON streams (`RpcRequest` / `RpcResponse`), never appearing in process argument tables or system `ps` listings.
11. **Strict Response Typing & Exit Code Semantics**:
    - Strictly enforces `type(resp.ok) is bool`, preventing string truthy coercion (e.g., `"false"` becoming `True`).
    - Requires remote exit code `0`; non-zero exit codes fail closed with `TransportError`, even if valid JSON was emitted on stdout.
12. **Timeout Ambiguity Semantics (C2164)**: Subprocess timeouts represent an *unknown remote state*. The client fails closed with `TransportTimeout` without performing automatic mutating retries or minting duplicate idempotency keys.
13. **Ordinary Git Recovery Empirically Proven (C2171 / C2175 / C2181)**:
    - Generated a complete, self-contained 17-file unified patch: `research/antigravity/recovery/typed-ssh-filebus-rpc-hardened.patch` (SHA256: `444165fd8821c371e01cb5dfb39775e3be50e466e1b54f2eb7ab982176efc976`).
    - In a clean disposable checkout at base commit `f3295f99e188719f5df9fccb22706d8a0e5bb8f8`, `git apply` executed with exit code 0.
    - Verified all module imports: `coordination.envelope`, `coordination.ssh_rpc`, `coordination.errors`, `coordination.bus_cli`, `coordination.durable`, `coordination.headless_worker`.
    - Executed full test suite in disposable testbed: **65/65 tests passing** clean across all 8 test modules in 7.54s (recovery log SHA256: `7e4d19d37af53de2624e0b20c9e854678fb8308b8c670b986dfc6f9c41abb5b2`).

---

## 2. Architecture & Envelope Specifications

### 2.1 Namespaced Identity: `NamespacedId` (`coordination/envelope.py`)
To enable multi-host, multi-workspace routing across machines without naming collisions, `NamespacedId` encapsulates five orthogonal scope dimensions:

```python
@dataclass(frozen=True)
class NamespacedId:
    host: str
    store_path: str
    agent_tag: str
    session_id: str
    task_id: str
```

#### URI-Safe Encoding Scheme
- **Scheme Prefix**: `nid:`
- **Encoding Rule**: Each component is individually percent-encoded with `urllib.parse.quote(part, safe="")` and joined by colons (`:`).
- **Format**: `nid:<quoted_host>:<quoted_store_path>:<quoted_agent_tag>:<quoted_session_id>:<quoted_task_id>`
- **Cross-Platform Safety**:
  - Windows path: `C:\Users\Alexey\AppData\Local\agent_bus` -> `C%3A%5CUsers%5CAlexey%5CAppData%5CLocal%5Cagent_bus`
  - Linux path: `/home/alexey/.local/agent_bus` -> `%2Fhome%2Falexey%2F.local%2Fagent_bus`
  - Safe against colons, forward slashes, and backslashes without delimiter ambiguity.

### 2.2 Typed RPC Framing: `RpcRequest` & `RpcResponse` (`coordination/envelope.py`)
FileBus operations over SSH use structured JSON framing with strict type validation:

```python
@dataclass
class RpcRequest:
    op: str
    request_id: str
    params: dict[str, Any] = field(default_factory=dict)
    target: NamespacedId | None = None

@dataclass
class RpcResponse:
    request_id: str
    ok: bool
    result: Any = None
    error: dict[str, Any] | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RpcResponse":
        raw_ok = data.get("ok")
        if type(raw_ok) is not bool:
            raise ValueError(f"RPC response 'ok' field must be a strict boolean, got {type(raw_ok).__name__}")
        return cls(
            request_id=str(data.get("request_id", "")),
            ok=raw_ok,
            result=data.get("result"),
            error=data.get("error"),
        )
```

### 2.3 Sanitized Typed Exception Hierarchy (`coordination/errors.py`)
Transport and protocol failures are categorized into explicit, typed exceptions inheriting from `CoordinationError`. Per C2166, raw stderr and stdout strings are completely omitted:

```python
class TransportError(CoordinationError):
    """Raised when the remote transport exits non-zero or connection fails."""
    def __init__(self, message: str, exit_code: int | None = None, code: str = "remote_transport_failed"):
        super().__init__(message)
        self.exit_code = exit_code
        self.code = code

class TransportTimeout(TransportError):
    """Raised when the SSH RPC command times out (ambiguous remote outcome)."""
    def __init__(self, message: str, timeout_sec: float | None = None):
        super().__init__(message, exit_code=None, code="remote_transport_timeout")
        self.timeout_sec = timeout_sec

class FramingError(CoordinationError):
    """Raised when remote output cannot be parsed as valid JSON RPC framing."""
    def __init__(self, message: str, reason: str = "invalid_json_framing"):
        super().__init__(message)
        self.code = "framing_error"
        self.reason = reason

class AuthError(CoordinationError):
    """Raised when remote FileBus authentication fails."""
    def __init__(self, message: str, reason: str = "remote_auth_rejected", details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = "auth_error"
        self.reason = reason
        self.details = details or {}
```

---

## 3. Server-Side Execution: `bus_cli.py rpc` Subcommand

A dedicated `rpc` subcommand was integrated into `coordination/bus_cli.py`:
- Reads a single JSON object from stdin (`RpcRequest`).
- Validates the requested operation (`enroll`, `send`, `inbox`, `ack`, `reply`, `get_message`).
- Executes the operation against the local `FileBus` store.
- Emits a single JSON object on stdout (`RpcResponse`).
- Returns exit code `0` on operational success. On application-level errors (e.g., auth failure, idempotency conflict), returns `0` with `ok=False` and structured `error` dict so client receives typed exceptions without process failure ambiguity.

---

## 4. Client-Side Implementation: `SshFileBusClient` (`coordination/ssh_rpc.py`)

### 4.1 Security Defenses Matrix
1. **OpenSSH Option Normalization & Enforcement (C2171)**:
   - Case-insensitive parsing and spacing normalization.
   - Strictly requires `BatchMode=yes` and `StrictHostKeyChecking=yes`.
   - Prohibits `accept-new`, `no`, `off`, `ask` across all casing/spacing.
   - Detects and rejects conflicting duplicate options.
   - Prohibits untrusted directives (`ProxyCommand`, `LocalCommand`, `PermitLocalCommand`) unless `allow_custom_proxycommand=True`.
2. **Host Option Injection Defense (C2162)**: Validates that `host` does not begin with `-`. Prefixes the host argument with `--` in the OpenSSH argument vector:
   ```python
   cmd = [self.ssh_binary] + list(self.ssh_opts) + ["--", self.host] + remote_cmd_parts
   ```
3. **Remote Shell Argument Escaping (C2162)**: `shlex.quote()` is applied to remote paths and arguments.
4. **POSIX Scope Boundary (C2164 / C2171)**: Scoped strictly to POSIX login shells (`/bin/sh`, `/bin/bash`, etc.). Windows remote shells remain held out-of-scope.
5. **Fail-Closed Omission (C2166)**: Raw stdout and stderr strings are completely omitted from public exception messages and exception attributes.
6. **Decoupled Exception Chaining (C2166)**: Subprocess and JSON parsing exceptions raise typed errors with `raise ... from None` outside `except` blocks, suppressing `__cause__` and `__context__`.
7. **Request ID Correlation Guard (C2166)**: Mismatched `request_id` raises `FramingError("request_id_mismatch") from None` without printing the payload.
8. **Strict Exit Code Verification**: If the process exits with a non-zero code, `TransportError` is raised immediately.
9. **Timeout Ambiguity (C2164)**: Timeouts raise `TransportTimeout` (unknown remote state) and explicitly forbid automated mutating retries.

---

## 5. Component Test Suites

### 5.1 Component Test Suite (`tests/test_ssh_rpc.py`)
18 unit and integration tests covering the full lifecycle and protocol safety:

| Test ID | Test Name | Directives | Behavior Tested | Result |
|---|---|---|---|---|
| **Test 1** | `test_namespaced_id_serialization_and_uri_roundtrip` | C2151 | Verifies `to_dict()`, `from_dict()`, and round-trip URI encoding across Unix and Windows drive letters (`C:\...`). | **PASS** |
| **Test 2** | `test_rpc_request_response_serialization` | C2154 | Verifies JSON serialization and deserialization of `RpcRequest` and `RpcResponse`. | **PASS** |
| **Test 3** | `test_full_lifecycle_over_rpc` | C2154 | Tests full FileBus lifecycle (enroll Alice & Bob, send message, check inbox, ack read, reply to message, inspect reply) over RPC. | **PASS** |
| **Test 4** | `test_typed_replay_and_idempotency_keys` | C2154 | Verifies idempotent replay deduplication under identical key, and `IdempotencyConflict` detection under conflicting payload. | **PASS** |
| **Test 5** | `test_negative_ssh_connection_failure` | C2156 / C2166 | Simulates SSH exit code 255; verifies `TransportError` raised with exit code and fail-closed stderr omission. | **PASS** |
| **Test 6** | `test_negative_ssh_timeout` | C2156 / C2164 / C2166 | Simulates subprocess timeout; verifies `TransportTimeout` raised with decoupled chaining (`__cause__ is None`, `__context__ is None`). | **PASS** |
| **Test 7** | `test_negative_corrupted_banner_framing` | C2156 / C2166 | Simulates noisy MOTD banner; verifies `FramingError` raised with fail-closed omission of raw output. | **PASS** |
| **Test 8** | `test_negative_auth_failure` | C2156 / C2166 | Attempts send with invalid token; verifies remote `auth_failed` translates to bounded `AuthError`. | **PASS** |
| **Test 9** | `test_zero_credentials_in_command_argv` | C2154 | Inspects captured subprocess argument lists; verifies zero tokens or payload strings appear in argv. | **PASS** |
| **Test 10** | `test_c2162_host_option_injection_rejected` | C2162 | Verifies hosts starting with `-` are rejected; verifies `--` precedes valid hosts in SSH argv. | **PASS** |
| **Test 11** | `test_c2162_remote_shell_escaping` | C2162 / C2164 | Verifies `shlex.quote` escaping on remote command parameters for POSIX login shells. | **PASS** |
| **Test 12** | `test_c2162_strict_correlation_check` | C2162 / C2166 | Simulates mismatched `request_id`; verifies `FramingError("request_id_mismatch") from None` raised without leaking payload. | **PASS** |
| **Test 13** | `test_c2162_strict_boolean_check` | C2162 | Verifies string truthy values (`"false"`, `"true"`, `1`) in `ok` field are rejected with `FramingError`. | **PASS** |
| **Test 14** | `test_c2162_strict_exit_code_check` | C2162 / C2166 | Simulates remote process emitting valid JSON but exiting with code 1; verifies `TransportError` fails closed without leaking stderr. | **PASS** |
| **Test 15** | `test_c2162_error_redaction_helper` | C2162 | Tests utility `_redact` helper masking tokens and payloads. | **PASS** |
| **Test 16** | `test_c2166_mandatory_ssh_options` | C2166 | Verifies mandatory `-o BatchMode=yes` and `-o StrictHostKeyChecking=yes`, and rejection of `accept-new`/`no`. | **PASS** |
| **Test 17** | `test_c2166_fail_closed_omission_no_stdout_stderr_leaks` | C2166 | Injects raw tokens and payloads into stderr and stdout; verifies zero leak in exception strings or attributes. | **PASS** |
| **Test 18** | `test_c2166_exception_chaining_decoupled` | C2166 | Verifies that `TimeoutExpired` and `JSONDecodeError` do not leak unredacted data via `__cause__` or `__context__`. | **PASS** |

### 5.2 Adversarial Security Suite (`tests/test_ssh_rpc_security.py`)
23 specialized adversarial test cases verifying host option injection defense, bare positional destination rejection (C2181), flag allowlist and integer port validation (C2181), option key allowlist and default-deny against executable/inclusion options (C2185/C2186), remote shell escaping, strict correlation, non-zero exit fail-closed behavior, timeout semantics, option normalization, duplicate option handling, custom trust, and deep leakage inspection across all error paths: **23/23 PASS in 0.04s**.

### 5.3 Test Execution Summary
```text
$ TMPDIR=.local/scratch/bus-ssh-rpc-snapshot/tmp PYTHONPATH=.local/scratch/bus-ssh-rpc-snapshot/agent-bus pytest -v tests/test_ssh_rpc.py tests/test_ssh_rpc_security.py
============================== 41 passed in 2.08s ==============================

$ TMPDIR=.local/scratch/bus-ssh-rpc-snapshot/tmp PYTHONPATH=.local/scratch/bus-ssh-rpc-snapshot/agent-bus pytest -v tests/
============================== 65 passed in 7.54s ==============================
```

---

## 6. Ordinary Git Recovery Verification

### 6.1 Unified Patch File
- Path: `research/antigravity/recovery/typed-ssh-filebus-rpc-hardened.patch`
- SHA256: `444165fd8821c371e01cb5dfb39775e3be50e466e1b54f2eb7ab982176efc976`
- Files included (17 total):
  - Tracked modifications: `coordination/__init__.py`, `coordination/bus.py`, `coordination/bus_cli.py`, `coordination/cursors.py`, `coordination/errors.py`, `tests/test_bus.py`, `tests/test_bus_dogfood.py`
  - New files created: `coordination/envelope.py`, `coordination/ssh_rpc.py`, `coordination/durable.py`, `coordination/headless_worker.py`, `tests/test_bus_concurrent.py`, `tests/test_bus_crash.py`, `tests/test_bus_scope.py`, `tests/test_headless_task.py`, `tests/test_ssh_rpc.py`, `tests/test_ssh_rpc_security.py`

### 6.2 Disposable Clean Clone Recovery Receipt
1. Disposable testbed initialized: cloned canonical `/home/alexey/git/agent-bus` and reset hard to `f3295f99e188719f5df9fccb22706d8a0e5bb8f8`.
2. Applied unified patch: `git apply research/antigravity/recovery/typed-ssh-filebus-rpc-hardened.patch` -> exit code `0`.
3. Verified module imports: `coordination.envelope`, `coordination.ssh_rpc`, `coordination.errors`, `coordination.bus_cli`, `coordination.durable`, `coordination.headless_worker` -> all imported cleanly.
4. Executed full test suite:
   ```text
   $ pytest -v tests/
   ============================== 65 passed in 7.54s ==============================
   ```
5. Preserved recovery log: `.local/scratch/reviewer37-patch-audit/recovery_test_run.log` (SHA256: `7e4d19d37af53de2624e0b20c9e854678fb8308b8c670b986dfc6f9c41abb5b2`).
6. Preserved restored manifest: `.local/scratch/reviewer37-patch-audit/restored_manifest.txt` (SHA256: `bdca2ca979854695eeb057cde1bd2d03b83407765af7cd24b00f18fbd8565a92`).
7. Cleaned up disposable directory: zero residual storage overhead.

---

## 7. Invariant Compliance Checklist

- [x] **Zero cargo / rustc invocations**: Exactly 0 invocations in this review interval. Standard Python 3.12 and Linux tools only.
- [x] **Canonical Isolation**: Canonical `/home/alexey/git/agent-bus/` pre-existing dirty working copy strictly preserved; zero new canonical changes or commits introduced.
- [x] **Scratch Root Isolation**: All work conducted within `/home/alexey/git/cloudflare-agent-git/.local/scratch/bus-ssh-rpc-snapshot/` (size <= 512 MB).
- [x] **Host Storage Protection**: TMPDIR strictly set to scratch tmp (`.local/scratch/bus-ssh-rpc-snapshot/tmp/`, mode `0700`); zero writes to host `/tmp`.
- [x] **Publication Credential Guard**: Ran `python3 research/antigravity/tooling/publication_guard.py research/antigravity/recovery/REPORT-TYPED-SSH-FILEBUS-RPC.md` with zero violations (exit code 0).
- [x] **Git Hygiene**: Subagent did NOT perform git commit or tag mutations.
