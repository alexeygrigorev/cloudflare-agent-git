# REPORT: Typed SSH FileBus RPC Client & Namespaced Envelope Implementation (C2151 / C2154 / C2156 / C2162 / C2164 / C2166)

**Directives**: Codex Principal Directives C2151, C2154, C2156, C2162, C2164, C2166  
**Author / Role**: Self-Organization Architect & Implementer (tag: `architect06`)  
**Parent**: `antigravity-head` (`46fdb644`, id: `245c7bba-9a7b-45c1-87a7-4537f289f9a5`)  
**Workspace**: `/home/alexey/git/cloudflare-agent-git`  
**Snapshot Workspace**: `/home/alexey/git/cloudflare-agent-git/.local/scratch/bus-ssh-rpc-snapshot/agent-bus/`  
**Snapshot TMPDIR**: `/home/alexey/git/cloudflare-agent-git/.local/scratch/bus-ssh-rpc-snapshot/tmp/` (mode `0700`, zero writes to host `/tmp`)  
**Date**: 2026-10-05  
**Credential Validation**: `research/antigravity/tooling/publication_guard.py` (Exit Code `0` CLEAN)  

---

## 1. Executive Summary

Under Codex Principal Directives C2151, C2154, C2156, C2162, C2164, and C2166, a hardened, narrow, typed SSH FileBus RPC client, namespaced identity envelope, and structured framing protocol have been implemented and comprehensively validated within an isolated snapshot repository at `.local/scratch/bus-ssh-rpc-snapshot/agent-bus/`.

### 1.1 Key Achievements & C2166 Hardenings
1. **Canonical Invariant Preserved**: The canonical repository `/home/alexey/git/agent-bus/` remains **100% untouched** (zero canonical dirt, zero branch pollution).
2. **Fail-Closed Omission over Regex Redaction (C2166)**: Rather than relying on brittle regex matching over raw remote output, public exceptions (`TransportError`, `TransportTimeout`, `FramingError`, `AuthError`) completely omit raw stdout and stderr strings from error messages and exception attributes. Exceptions carry strictly bounded, sanitized error codes (e.g., `code="remote_transport_failed"`, `exit_code=proc.returncode`, `reason="invalid_json_framing"`, `reason="remote_auth_rejected"`). Raw stdout/stderr and `err.doc` are never embedded in exception messages.
3. **Decoupled Exception Chaining (C2166)**: When handling `subprocess.TimeoutExpired`, `json.JSONDecodeError`, or `ValueError`, exceptions are decoupled via `raise ... from None` outside `except` blocks. This ensures both `__cause__` and `__context__` are `None` and `__suppress_context__` is `True`, permanently preventing raw stdout/stderr from leaking via Python traceback inspection.
4. **Mandatory Strict Host Key Checking & BatchMode (C2166)**: Enforces `-o BatchMode=yes` and `-o StrictHostKeyChecking=yes` in the OpenSSH argument list. Explicitly prohibits insecure options such as `StrictHostKeyChecking=accept-new` or `no`.
5. **Request ID Mismatch Guard (C2166)**: If `resp.request_id != req.request_id`, raises `FramingError("request_id_mismatch") from None` without printing or reflecting unredacted payload data.
6. **Host Option Injection Defense (C2162)**: Rejects host names starting with a hyphen (`-`) and inserts `--` before the host argument in the SSH argv list (`ssh [...] -- <host> <command>...`), preventing OpenSSH flag injection.
7. **Remote Shell Argument Escaping (C2162)**: Because OpenSSH concatenates command arguments and passes them to the remote user login shell (`$SHELL -c "<cmd>"`), all command arguments (`bus_cli_path`, `--store`, `store_path`, `rpc`) are escaped via `shlex.quote()` on the client side.
8. **POSIX Remote-Shell Scope Boundary (C2164)**: Escaping guarantees are formally demarcated for POSIX-compliant login shells (`sh`, `bash`, `dash`, `zsh`). Windows remote targets (`cmd.exe` / `powershell.exe`) feature distinct escaping and locking semantics and remain explicitly held / out-of-scope for remote execution.
9. **Zero Credential or Payload Leakage in Argv**: Message bodies, metadata, tokens, and credentials are transmitted strictly over stdin JSON streams (`RpcRequest` / `RpcResponse`), never appearing in process argument tables or system `ps` listings.
10. **Strict Response Typing & Exit Code Semantics**:
    - Strictly enforces `type(resp.ok) is bool`, preventing string truthy coercion (e.g., `"false"` becoming `True`).
    - Requires remote exit code `0`; non-zero exit codes fail closed with `TransportError`, even if valid JSON was emitted on stdout.
11. **Timeout Ambiguity Semantics (C2164)**: Subprocess timeouts represent an *unknown remote state*. The client fails closed with `TransportTimeout` without performing automatic mutating retries or minting duplicate idempotency keys.
12. **URI-Safe Namespaced Identity (`NamespacedId`)**: Structured identity representation supporting round-trip percent-encoding safe against Windows drive letters (e.g. `C:\...`) and Unix/Windows path slashes (`/`, `\`).
13. **100% Component & Full Suite Pass Rate**:
    - `tests/test_ssh_rpc.py`: **18/18 tests passing** in 2.10s.
    - `tests/test_ssh_rpc_security.py`: **16/16 tests passing** in 0.03s.
    - Full snapshot test suite: **58/58 tests passing** in 10.28s with zero host `/tmp` writes.

---

## 2. Architecture & Envelope Specifications

### 2.1 Namespaced Identity: `NamespacedId` (`coordination/envelope.py`)
To enable multi-host, multi-workspace routing across machines (e.g., desktop orchestrator to Hetzner cloud nodes) without naming collisions, `NamespacedId` encapsulates five orthogonal scope dimensions:

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
    """Raised when the remote transport exits non-zero or connection fails.
    Carries bounded, structured, sanitized error codes and exit code.
    Raw stdout and stderr are completely omitted.
    """
    def __init__(self, message: str = "remote_transport_failed", exit_code: int | None = None, code: str = "remote_transport_failed"):
        super().__init__(message)
        self.exit_code = exit_code
        self.code = code

class TransportTimeout(TransportError):
    """Raised when the remote command execution exceeds the timeout limit.
    Represents an unknown remote state with zero automated mutating retries.
    """
    def __init__(self, message: str = "transport_timeout", timeout_sec: float | None = None, code: str = "transport_timeout"):
        super().__init__(message=message, exit_code=None, code=code)
        self.timeout_sec = timeout_sec

class FramingError(CoordinationError):
    """Raised when remote output is corrupted, non-JSON, or malformed framing.
    Carries bounded, structured reasons only; raw output and doc strings omitted.
    """
    def __init__(self, message: str = "invalid_json_framing", reason: str = "invalid_json_framing", code: str = "framing_error"):
        super().__init__(message)
        self.reason = reason
        self.code = code

class AuthError(CoordinationError):
    """Raised when authentication or authorization fails on the remote FileBus."""
    def __init__(self, message: str = "remote_auth_rejected", reason: str = "remote_auth_rejected", code: str = "auth_error"):
        super().__init__(message)
        self.reason = reason
        self.code = code
```

---

## 3. Remote CLI RPC Server (`coordination/bus_cli.py`)

In `coordination/bus_cli.py`, the `rpc` subcommand handles streaming requests over stdin:

```bash
python3 coordination/bus_cli.py --store <store_path> rpc
```

1. **Stdin Ingestion**: Reads raw input from `sys.stdin` and parses `RpcRequest`.
2. **Operation Dispatch**:
   - `enroll` / `register`: Calls `bus.register(agent_name, device_id, project_id, task_id, ...)`.
   - `send`: Calls `bus.send(sender_id, token, recipient_id, body, data, idempotency_key)`.
   - `inbox`: Calls `bus.inbox(identity_id, token, unread_only)`.
   - `ack`: Calls `bus.ack(identity_id, token, message_id)`.
   - `reply`: Calls `bus.reply(sender_id, token, message_id, body, data, idempotency_key)`.
   - `get`: Calls `bus.get(identity_id, token, message_id)`.
3. **Structured Response & Exit Code Contract**:
   - Catches `CoordinationError`, extracts error code and message, serializes `RpcResponse` to JSON, and prints to stdout with immediate flush.
   - Exits code `0` whenever an `RpcResponse` is successfully emitted (even when `ok == False`), reserving non-zero process exit codes exclusively for uncaught fatal crashes or transport failures.

---

## 4. Typed SSH Client: `SshFileBusClient` (`coordination/ssh_rpc.py`)

### 4.1 Interface & Execution
`SshFileBusClient` provides a high-level Pythonic interface for remote FileBus operations:

```python
client = SshFileBusClient(
    host="hetzner-worker-1",
    store_path="/home/alexey/.local/agent_bus",
    bus_cli_path="/home/alexey/git/agent-bus/coordination/bus_cli.py",
)

# Enroll
identity_id, token = client.enroll(agent_name="worker-1", device_id="hetzner-01")

# Send
msg_id = client.send(
    sender_id=identity_id,
    token=token,
    recipient_id=peer_id,
    body="Task dispatch payload",
    idempotency_key="tx-100",
)

# Inbox
messages = client.inbox(identity_id=identity_id, token=token, unread_only=True)

# Ack
ack_record = client.ack(identity_id=identity_id, token=token, message_id=msg_id)

# Reply
reply_id = client.reply(
    sender_id=identity_id,
    token=token,
    message_id=msg_id,
    body="Task completed successfully",
    idempotency_key="reply-tx-100",
)
```

### 4.2 Security Constraints Enforced (C2162 / C2164 / C2166)
1. **Mandatory SSH Hardening (C2166)**: Enforces `-o BatchMode=yes` and `-o StrictHostKeyChecking=yes`. Explicitly rejects `StrictHostKeyChecking=accept-new` or `no`.
2. **Host Option Injection Defense (C2162)**: Validates that `host` does not begin with `-`. Prefixes the host argument with `--` in the OpenSSH argument vector:
   ```python
   cmd = [self.ssh_binary] + list(self.ssh_opts) + ["--", self.host] + remote_cmd_parts
   ```
3. **Remote Shell Argument Escaping (C2162)**: `shlex.quote()` is applied to remote paths and arguments.
4. **POSIX Scope Boundary (C2164)**: Scoped strictly to POSIX login shells (`/bin/sh`, `/bin/bash`, etc.). Windows remote shells remain held out-of-scope.
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
16 specialized adversarial test cases verifying host option injection defense, remote shell escaping, strict correlation, non-zero exit fail-closed behavior, timeout semantics, and deep leakage inspection across all error paths: **16/16 PASS in 0.03s**.

### 5.3 Test Execution Summary
```text
$ TMPDIR=.local/scratch/bus-ssh-rpc-snapshot/tmp PYTHONPATH=.local/scratch/bus-ssh-rpc-snapshot/agent-bus pytest -v tests/test_ssh_rpc.py
============================== 18 passed in 2.10s ==============================

$ TMPDIR=.local/scratch/bus-ssh-rpc-snapshot/tmp PYTHONPATH=.local/scratch/bus-ssh-rpc-snapshot/agent-bus pytest -v tests/test_ssh_rpc_security.py
============================== 16 passed in 0.03s ==============================

$ TMPDIR=.local/scratch/bus-ssh-rpc-snapshot/tmp PYTHONPATH=.local/scratch/bus-ssh-rpc-snapshot/agent-bus pytest tests/
============================= 58 passed in 10.28s ==============================
```

---

## 6. Invariant Compliance Checklist

- [x] **Zero cargo / rustc invocations**: Verified zero calls. Standard Python 3.12 and Linux tools only.
- [x] **Canonical Isolation**: Canonical `/home/alexey/git/agent-bus/` remains 100% untouched.
- [x] **Scratch Root Isolation**: All work conducted within `/home/alexey/git/cloudflare-agent-git/.local/scratch/bus-ssh-rpc-snapshot/` (size <= 512 MB).
- [x] **Host Storage Protection**: TMPDIR strictly set to scratch tmp (`.local/scratch/bus-ssh-rpc-snapshot/tmp/`, mode `0700`); zero writes to host `/tmp`.
- [x] **Publication Credential Guard**: Ran `python3 research/antigravity/tooling/publication_guard.py research/antigravity/recovery/REPORT-TYPED-SSH-FILEBUS-RPC.md` with zero violations (exit code 0).
- [x] **Git Hygiene**: Subagent did NOT perform git commit or tag mutations.
