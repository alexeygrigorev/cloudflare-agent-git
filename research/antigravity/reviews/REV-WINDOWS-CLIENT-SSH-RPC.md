# Independent Technical Review: Windows Client vs. Remote POSIX Audit, Unicode RPC Diagnostic Design & Repaired Diagnostic Driver (Codex Directives C2263 / C2267 / C2274)

- **Reviewer**: Independent Challenger Reviewer (`reviewer37`, subagent conversation ID: `37aa1067-8bda-4dde-95b8-7b5bb927bd1f`)
- **Reviewer Identity ID**: `163fa1fb-38ac-47ba-a73c-afe0778fec7d`
- **Authority**: Dispatched by `antigravity-head` (`46fdb644`, conversation ID: `245c7bba-9a7b-45c1-87a7-4537f289f9a5`) under Codex Principal Directives C2263, C2267, and C2274; auditing sibling integration codebase under Directives C2162, C2164, C2166, C2214, C2217, C2224, C2226, and C2274; authorized by human cross-computer steering (`experiment/human-cross-computer-product-20261004.txt`).
- **Target Integration Repository**: `/home/alexey/git/cloudflare-agent-git/.local/scratch/architect06-bus-integration/agent-bus`
- **Pinned Sibling Commit**: `23b0742b1f00ec027d830763e773577a807dbc39` atop `f3295f99e188719f5df9fccb22706d8a0e5bb8f8` (`feat/typed-ssh-filebus-rpc`)
- **Diagnostic Deliverable**: `research/antigravity/recovery/test_windows_client_unicode_rpc.py`
- **Driver Deliverable**: `research/antigravity/recovery/windows_rpc_diagnostic_driver.py`
- **Review Deliverable**: `research/antigravity/reviews/REV-WINDOWS-CLIENT-SSH-RPC.md`
- **Audit Testbed**: `.local/scratch/reviewer37-windows-client-audit/` (mode `0700`, <= 512 MB, zero net `/tmp` growth)
- **Canonical Repositories Status**: Canonical `/home/alexey/git/agent-bus` and `/home/alexey/git/agent-dashboard` remained strictly read-only with respect to reviewer actions and observed subprocesses throughout this review.
- **Compiler Invariant**: Exactly `0` `cargo` or `rustc` invocations executed during this review interval and audit environment under human hold (scoped strictly to reviewer actions and subprocesses).
- **Date**: 2026-10-05T04:26:00+02:00 (Europe/Berlin)
- **Status / Verdict**: **STATUS: SOURCE-CANDIDATE / UNVALIDATED WINDOWS RUNTIME (LINUX FCNTL-SIMULATION ONLY; WIRE UNICODE & NATIVE WINDOWS SUBPROCESS UNVERIFIED)**

---

## 1. Executive Summary & Clarification of the Windows Demarcation

Previous review reports (including earlier drafts of `REV-TYPED-SSH-FILEBUS-RPC-DOGFOOD.md` and `REV-LOOPBACK-SSH-RPC.md`) contained broad statements indicating that "Windows execution remains completely UNKNOWN/HELD" due to the absence of POSIX primitives (`fcntl.flock`, `os.O_DIRECTORY`).

Under Codex Principal Directives C2263 and C2267, an in-depth source-code audit was conducted to rigorously separate the **Client Role** from the **Server/Store Role**:

1. **Source-Level Compatibility vs. Runtime Verification**:
   - The assertion that Windows cannot import the Python client is **technically incorrect at the source level**: `coordination/ssh_rpc.py` (`SshFileBusClient`) does not import `fcntl`, does not call `FileLock`, and does not perform filesystem operations on the bus store.
   - In `coordination/durable.py`, `import fcntl` is isolated **lazily** inside `FileLock.__enter__` and `FileLock.__exit__`. It is never imported at module level. Consequently, `import coordination.bus` and `from coordination.ssh_rpc import SshFileBusClient` import cleanly on non-POSIX platforms lacking `fcntl`.
   - **Crucial Runtime Disclosure (Directive C2267)**: Verification of this behavior was conducted via Linux missing-fcntl simulation (`sys.modules["fcntl"] = None`) and mock runners. It does **not** constitute native Windows execution, native Windows OpenSSH (`ssh.exe`) process invocation, DPAPI token decryption, or live wire transport.
2. **Exact Architectural Boundary**:
   - **Local Windows Server/Store (`FileBus`)**: **`UNKNOWN/HELD`**. Hosting a local `FileBus` store directory on a Windows filesystem requires POSIX `flock` and `O_DIRECTORY` directory fsync, which are unsupported on native Windows without an OS-specific abstraction layer.
   - **Windows Client (`SshFileBusClient` connecting to Linux Rendezvous)**: **SOURCE-CANDIDATE / UNVALIDATED WINDOWS RUNTIME**. While architecturally designed as a pure subprocess client, live native Windows Python execution remains designated **`UNKNOWN/HELD`** pending genuine platform receipts.
3. **Quoting Scope & Withdrawal of Universal Claims**:
   - Earlier universal claims of "zero escaping/truncation risk" are unsupported and withdrawn. PowerShell and Windows `cmd.exe` command-line parsing rules differ significantly from POSIX `shlex` and can introduce subtle quoting behaviors.
   - `shlex.quote` in `_execute_rpc` formats arguments specifically for the **remote POSIX login shell** (`/bin/sh` or `/bin/bash` on the Linux server). While stdin JSON payload streaming avoids command-line exposure, native Windows command line construction across PowerShell environments requires direct platform validation.
4. **Wire UTF-8 vs. Logical JSON Demarcation**:
   - In `coordination/ssh_rpc.py`, `_execute_rpc` invokes `json.dumps(req.to_dict())` with default Python settings (`ensure_ascii=True`), which emits ASCII `\uXXXX` escape sequences for non-ASCII characters on the wire.
   - Consequently, a logical JSON string roundtrip in Python does **not** attest that raw multi-byte UTF-8 wire encoding was tested across network boundaries. Wire-level multi-byte UTF-8 transport across distinct operating systems remains unverified.

---

## 2. Source-Level Code Audit Receipts (Commit `23b0742b`)

### 2.1 Lazy Import of `fcntl` in `coordination/durable.py`
Inspection of `coordination/durable.py` confirms that `fcntl` is never imported at module level:
```python
# coordination/durable.py lines 60-83:
class FileLock:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._fd: int | None = None

    def __enter__(self) -> FileLock:
        import fcntl  # <--- LAZY IMPORT: only executed when acquiring a local lock!

        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        flags = os.O_CREAT | os.O_RDWR
        if hasattr(os, "O_CLOEXEC"):
            flags |= os.O_CLOEXEC
        self._fd = os.open(self.path, flags, 0o600)
        fcntl.flock(self._fd, fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc: object) -> None:
        import fcntl  # <--- LAZY IMPORT: only executed when releasing a local lock!

        if self._fd is not None:
            fcntl.flock(self._fd, fcntl.LOCK_UN)
            os.close(self._fd)
            self._fd = None
```

### 2.2 Complete Isolation of `coordination/ssh_rpc.py`
Inspection of `coordination/ssh_rpc.py` (lines 20–45) shows the complete module dependency graph:
```python
from __future__ import annotations

from dataclasses import dataclass, field
import json
import re
import shlex
import subprocess
from typing import Any, Callable

from coordination.envelope import NamespacedId, RpcRequest, RpcResponse, new_request_id
from coordination.errors import (
    AuthError,
    CoordinationError,
    FramingError,
    IdempotencyConflict,
    TransportError,
    TransportTimeout,
)
```
- `coordination/ssh_rpc.py` imports standard library modules and internal typed envelope/error models.
- It does **not** import `coordination.durable`, `coordination.bus`, or `coordination.cursors`.
- It does **not** import `fcntl`, `termios`, or any POSIX-only standard library modules.

### 2.3 Non-POSIX Import Validation Test
A simulation test was executed on Linux by removing and blocking `fcntl` in Python's module registry (`sys.modules["fcntl"] = None`):
```text
>>> sys.modules['fcntl'] = None
>>> import coordination.envelope
>>> import coordination.errors
>>> import coordination.durable
>>> import coordination.cursors
>>> import coordination.bus
>>> from coordination.ssh_rpc import SshFileBusClient
>>> print("Import successful!")
Import successful!
```
**Audit Result**: All coordination modules and `SshFileBusClient` import cleanly on platforms lacking `fcntl`.

---

## 3. Remote Shell Quoting vs. Client Subprocess Execution

An important architectural nuance audited under C2263 is how arguments are passed when `SshFileBusClient` executes on Windows:

```python
# coordination/ssh_rpc.py lines 366-375:
remote_cmd_parts = [
    "python3",
    shlex.quote(self.bus_cli_path),
    "--store",
    shlex.quote(self.store_path),
    "rpc",
]
cmd = [self.ssh_binary] + list(self.ssh_opts) + ["--", self.host] + remote_cmd_parts
```

1. **Client Subprocess Execution**:
   - `cmd` is an argument list passed directly to `subprocess.Popen(cmd, shell=False)`.
   - On Windows, `subprocess.Popen` transforms `cmd` into a Windows command line string using standard C-runtime escaping (`subprocess.list2cmdline`).
   - The binary executed is `ssh.exe` (or `ssh`).
2. **Remote OpenSSH Execution**:
   - The OpenSSH client transmits all arguments appearing after `host` across the SSH channel to the remote user's login shell on the server.
   - Because the rendezvous server (`hetzner`) is Linux, the remote shell is `/bin/sh` or `/bin/bash` (a POSIX shell).
   - Therefore, `shlex.quote(self.bus_cli_path)` and `shlex.quote(self.store_path)` correctly escape paths with whitespace for the **remote POSIX shell**.
3. **Payload Isolation via Stdin**:
   - Sensitive bearer tokens, request identifiers, message bodies, and structured task data are never included in `remote_cmd_parts` or `cmd`.
   - All operational payloads are serialized to JSON and piped via `proc.communicate(input=stdin_payload)`.
   - Consequently, Windows shell escaping differences (`^`, `&`, `"`, `%`) have zero impact on message payloads.

---

## 4. Stdlib-Only Windows Client & Unicode RPC Diagnostic Design

To empirically validate the Windows client execution model and address the untested Unicode boundary noted in `REPORT-TWOHOST-DESKTOP-HETZNER-RPC.md` (Section 8.2), a clean, stdlib-only diagnostic test suite was authored in:
[`research/antigravity/recovery/test_windows_client_unicode_rpc.py`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/recovery/test_windows_client_unicode_rpc.py)

### 4.1 Diagnostic Test Capabilities:
1. **`test_01_client_import_without_fcntl`**:
   - Formally blocks `fcntl` via `sys.modules["fcntl"] = None`.
   - Confirms that `coordination.envelope`, `coordination.errors`, and `SshFileBusClient` import without `ModuleNotFoundError`.
2. **`test_02_unicode_payload_framing`**:
   - Tests full UTF-8 fidelity across diverse non-ASCII scripts:
     * Cyrillic: `"Тестовое сообщение через RPC: проверка UTF-8 и целостности данных"`
     * German Umlauts: `"Grüße aus Berlin: Überprüfung von Umlauten äöüß und Sonderzeichen"`
     * Japanese / CJK: `"こんにちは世界！FileBus RPC cross-computer message"`
     * Emojis: `"🚀 Windows Desktop ➔ Hetzner Linux Rendezvous 🌐✨"`
     * Mathematical notation: `"∀x ∈ Agents: Verified(x) ∧ Latency(x) < 1000ms"`
   - Verifies that `RpcRequest` and `RpcResponse` round-trip through UTF-8 byte encoding and decoding without character loss, escaping corruption, or schema validation failures.
3. **`test_03_desktop_root_dpapi_stdin_streaming_pattern`**:
   - Matches Desktop Root's verified DPAPI integration pattern (from `REPORT-TWOHOST-DESKTOP-HETZNER-RPC.md`, Section 6.1).
   - Verifies that sensitive DPAPI-decrypted bearer tokens and Unicode message bodies are encapsulated strictly within stdin JSON streams.
   - Asserts that `sys.argv` contains only `['ssh.exe', ..., '--', 'hetzner', 'python3', '<path>', '--store', '<path>', 'rpc']`, with zero tokens or message bodies in process argument strings.
4. **`test_04_windows_client_argument_construction`**:
   - Tests client initialization with `ssh_binary="ssh.exe"`.
   - Verifies that `--` precedes the destination host operand, mandatory `-o BatchMode=yes` and `-o StrictHostKeyChecking=yes` options are enforced, and remote store paths containing whitespace are safely quoted for the remote POSIX shell.

### 4.2 Empirical Test Execution Receipt
```text
$ python3 research/antigravity/recovery/test_windows_client_unicode_rpc.py
test_01_client_import_without_fcntl (__main__.TestWindowsClientAndUnicodeRpc.test_01_client_import_without_fcntl)
Confirms that coordination modules and SshFileBusClient import without fcntl. ... ok
test_02_unicode_payload_framing (__main__.TestWindowsClientAndUnicodeRpc.test_02_unicode_payload_framing)
Verifies full fidelity UTF-8 serialization/deserialization for non-ASCII payloads. ... ok
test_03_desktop_root_dpapi_stdin_streaming_pattern (__main__.TestWindowsClientAndUnicodeRpc.test_03_desktop_root_dpapi_stdin_streaming_pattern)
Verifies that SshFileBusClient encapsulates sensitive parameters strictly in stdin JSON ... ok
test_04_windows_client_argument_construction (__main__.TestWindowsClientAndUnicodeRpc.test_04_windows_client_argument_construction)
Verifies argument construction on Windows: ... ok

----------------------------------------------------------------------
Ran 4 tests in 0.014s

OK
```
**Outcome**: All 4 tests PASSED cleanly in 14 milliseconds.

**Crucial Scope Disclosure (Directive C2267)**:
- All 4 tests in `test_windows_client_unicode_rpc.py` were executed on Linux using a missing-fcntl simulation (`sys.modules["fcntl"] = None`) and a mock subprocess runner.
- They do **NOT** constitute native Windows execution, native Windows OpenSSH (`ssh.exe`) process invocation, DPAPI token decryption on Windows, or live wire transport.
- Furthermore, `test_windows_client_unicode_rpc.py` used `json.dumps(..., ensure_ascii=False)` to verify Unicode serialization, whereas `coordination.ssh_rpc._execute_rpc` uses Python's default `json.dumps(..., ensure_ascii=True)` (which emits `\uXXXX` escape sequences). Logical JSON string roundtripping does not attest raw UTF-8 wire encoding across network boundaries.

---

## 5. Architectural Alignment with Desktop Root's Verified Receipts

In `REPORT-TWOHOST-DESKTOP-HETZNER-RPC.md` (Section 6.1), Desktop Root documented the **DPAPI Remote `--cred` Contradiction**:
- When invoking `bus_cli.py send --cred <path>` across SSH, the remote Python interpreter attempts to resolve `<path>` on the **remote Linux filesystem**, where the Windows DPAPI credential file does not exist.
- Desktop Root resolved this by streaming JSON over stdin to `bus_cli.py rpc`.

**Key Architectural Insight**:
The Python `SshFileBusClient` implementation in `coordination/ssh_rpc.py` operates in the exact same manner as Desktop Root's PowerShell solution:
1. The client maintains credentials locally (e.g. in Windows memory or local storage).
2. It constructs an `RpcRequest` with `op="send"`, embedding the token in `params["token"]`.
3. It pipes the entire JSON request over stdin to `python3 bus_cli.py rpc`.
4. `bus_cli.py rpc` receives the token via stdin, authenticates against the Linux FileBus store, and returns the response over stdout.

### 5.1 Real CLI Diagnostic Driver Delivered & Refactored: `windows_rpc_diagnostic_driver.py` (Directives C2267 & C2274)
Under Codex Principal Directives C2267 and C2274, the standalone diagnostic CLI driver was authored and refactored:
[`research/antigravity/recovery/windows_rpc_diagnostic_driver.py`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/recovery/windows_rpc_diagnostic_driver.py)
- **SHA256**: `2fd1be4ef2b9d0437ac47e3635f13212886f2e8c56d0dea94919f057a3205d44`

**Key Directive C2274 Architectural & Security Corrections**:
1. **Reuse Pinned Typed Client (`SshFileBusClient`)**:
   - Replaced redundant raw subprocess command construction and fragile regex sanitization with direct reuse of `SshFileBusClient` from `coordination.ssh_rpc`.
   - Inherits strict `request_id` correlation, `bool(ok)` verification, fail-closed omission of raw output, and safe decoupled exception chaining.
   - Dynamic repository resolution via `--repo-dir` with automatic fallback scanning of local scratch checkouts.
2. **Elimination of `enroll` Action**:
   - Desktop Root is pre-enrolled (`01ace831-6d23-4c05-a6df-1a58099aca67`).
   - `enroll` is completely eliminated from `--action` choices, argument parser, and execution logic, permanently closing the risk of leaking bearer tokens on stdout.
3. **Strict Stdin Ingestion & Zero Secrets/Payloads on `sys.argv`**:
   - Bearer tokens are read strictly from `sys.stdin` (plain text string or structured JSON).
   - `--body` is completely eliminated from `sys.argv`.
   - If no explicit body is provided via stdin JSON, the driver defaults to a built-in multi-byte UTF-8 verification probe:
     `"RPC-Unicode-Diagnostic: Grüß Gott 🚀 / Привет мир / 2H₂ + O₂ ⇌ 2H₂O / 100% 🎯"` (75 characters, 100 UTF-8 bytes).
   - Custom non-secret bodies can be supplied safely via stdin JSON (`{"token": ..., "body": ...}`).
4. **Sanitized Output Only (Zero Token / Body Leakage)**:
   - Inboxes, lookups, and message acknowledgments NEVER print raw tokens or private message bodies to stdout.
   - Outputs emit clean JSON containing message metadata, message counts, character lengths, byte lengths, and SHA256 body digests.

### 5.2 Empirical Verification Receipts (Directives C2267 & C2274)
1. **Real Rendezvous Store Verification**:
   - Executed against live Hetzner rendezvous store (`.local/scratch/desktop-root-rpc-20261005/store`) with credentials piped via stdin:
     ```bash
     cat .local/scratch/desktop-root-rpc-20261005/head_cred.json | python3 research/antigravity/recovery/windows_rpc_diagnostic_driver.py \
       --host 127.0.0.1 \
       --remote-cli /home/alexey/git/cloudflare-agent-git/.local/scratch/architect06-bus-integration/agent-bus/coordination/bus_cli.py \
       --store /home/alexey/git/cloudflare-agent-git/.local/scratch/desktop-root-rpc-20261005/store \
       --action inbox --all
     ```
   - **Receipt**: Exit code 0; retrieved Desktop Root's authentic cross-computer reply message `b448cc83-3fc1-4290-94c6-796cb160948d` (sender: `01ace831-6d23-4c05-a6df-1a58099aca67`, recipient: `91d2a63b-fe47-4b53-bee8-2ada24259439`, body length 775 bytes, SHA256: `73bcb598b1586e11bb47350fc6c763b8e9d35edc7380d6fcbf4739844883a01a`).
2. **Complete 4-Stage Exchange Lifecycle (Isolated Scratch Store)**:
   - In `.local/scratch/reviewer37-windows-client-audit/test_store`:
     - Stage 1 (`send`): Alice sends default multi-byte Unicode probe to Bob (message `9e2e1328-1d0f-48b1-8665-562af88ee93a`, 75 chars, 100 bytes, SHA256 `64e3542858937d44b5b8e69667e3c3c12b0a83b5b270144a3a55870e2145db98`, `is_default_unicode_probe=true`).
     - Stage 2 (`inbox`): Bob reads unread message (count 1, matching SHA256 `64e35428...`).
     - Stage 3 (`reply`): Bob replies with custom body piped via stdin JSON (reply `cea9e7cd-a0c8-4e46-8cdf-7c64ee34898f`, 50 chars, 55 bytes, SHA256 `64dd9ef751912f97e4b441c1858b8b4186a2097df9c4ecb47815da8809cd2a10`).
     - Stage 4 (`ack`): Alice acknowledges Bob's reply (status `acknowledged`).
3. **Negative Fail-Closed Tests**:
   - Passing `--body` on `sys.argv`: Fails closed (`unrecognized arguments: --body`).
   - Invoking `--action enroll`: Fails closed (`invalid choice: 'enroll'`).
   - Empty stdin: Fails closed with clean error JSON (`"message": "Stdin was empty; expected bearer [REDACTED] or credential JSON"`).

---

## 6. Scope Demarcation Matrix

| Component / Subsystem | Host Platform | Role | Status | Technical Rationale |
| :--- | :--- | :--- | :--- | :--- |
| **`SshFileBusClient`** | **Windows Desktop** | Outbound RPC Client | **SOURCE-CANDIDATE / UNVALIDATED WINDOWS RUNTIME** | Pure stdlib client; imports without `fcntl`; delegates transport to `ssh.exe`; streams JSON over stdin; Linux simulation + mock runner passed; native Windows execution, native `ssh.exe`, and live wire transport remain UNKNOWN/HELD. |
| **`windows_rpc_diagnostic_driver.py`** | **Windows / Linux** | CLI Diagnostic Driver | **VERIFIED ON REAL STORE (REPAIRED C2274)** | Reuses pinned `SshFileBusClient`; reads token strictly from stdin; zero secrets/payloads on `sys.argv`; emits sanitized digests only; verified against real Hetzner rendezvous store over OpenSSH; ready for Windows DPAPI pipe. |
| **`test_windows_client_unicode_rpc.py`** | **Windows / Linux** | Diagnostic Test Suite | **VERIFIED (Linux Simulation & Logical Mock Runner)** | Tests UTF-8 Unicode framing, missing `fcntl` import, and DPAPI stdin streaming pattern with zero dependencies. |
| **Windows OpenSSH Frontend (`ssh.exe`)** | **Windows Desktop** | Subprocess Transport | **VERIFIED (LIVE WAN)** | Empirically verified in live cross-computer test (`REPORT-TWOHOST-DESKTOP-HETZNER-RPC.md`, latency 974ms). |
| **Windows Inbound SSH Listener (`sshd`)** | **Windows Desktop** | Inbound Server | **DISCOURAGED / NOT REQUIRED** | Forward polling/reply pattern eliminates need for inbound ports, NAT hole punching, and desktop daemon management. |
| **Local `FileBus` Backend** | **Windows Desktop** | Local Store / Server | **UNKNOWN / HELD** | Missing native Windows `flock` and `O_DIRECTORY` directory fsync implementations. |
| **Remote `FileBus` Backend** | **Hetzner Linux** | Rendezvous Store | **VERIFIED (LIVE WAN)** | Operates under native Linux POSIX primitives (`fcntl.flock`, `O_DIRECTORY` fsync). |

---

## 7. Invariant Compliance & Governance Receipts

1. **Compiler Invariant**:
   - Exactly **`0`** `cargo` or `rustc` invocations executed during this review interval and audit environment under human hold (scoped strictly to reviewer actions and subprocesses).
2. **Canonical Repositories Cleanliness**:
   - `/home/alexey/git/agent-bus` and `/home/alexey/git/agent-dashboard` remained completely untouched and strictly read-only with respect to all reviewer actions and observed subprocesses.
3. **Scratch Resource Isolation**:
   - Testbed confined strictly to `.local/scratch/reviewer37-windows-client-audit/` (mode `0700`, size 40 KB $\le$ 512 MB).
   - `TMPDIR` set inside scratch directory with zero net growth on system `/tmp`.
4. **Subagent Git Constraints**:
   - Zero `git commit` or `git push` commands were issued.
5. **Publication Guard Verification**:
   - Verified via `python3 research/antigravity/tooling/publication_guard.py research/antigravity/reviews/REV-WINDOWS-CLIENT-SSH-RPC.md research/antigravity/recovery/windows_rpc_diagnostic_driver.py` with clean exit code `0`.

---

## 8. Final Audit Verdict

**STATUS: SOURCE-CANDIDATE / UNVALIDATED WINDOWS RUNTIME (LINUX FCNTL-SIMULATION ONLY; WIRE UNICODE & NATIVE WINDOWS SUBPROCESS UNVERIFIED)**

1. **Source-Only Compatibility**: Source audit confirms that `fcntl` is not imported at module level in `coordination.durable` or `coordination.ssh_rpc`. The Python client architecture does not depend on local POSIX primitives.
2. **Runtime Demarcation**: Tests in `test_windows_client_unicode_rpc.py` were conducted as a Linux missing-fcntl simulation (`sys.modules["fcntl"] = None`) with a mock subprocess runner. Native Windows Python execution, native Windows OpenSSH (`ssh.exe`) process invocation, DPAPI token decryption on Windows, and live wire transport remain **`UNKNOWN / HELD`** pending genuine platform execution receipts.
3. **Wire UTF-8 vs. Logical JSON**: `coordination.ssh_rpc._execute_rpc` and default Python `json.dumps` use `ensure_ascii=True` (emitting `\uXXXX` escape sequences). Therefore, a logical JSON string roundtrip does not attest UTF-8 wire encoding across network boundaries.
4. **Universal Claims Withdrawn**: Earlier claims of zero escaping/truncation risk are withdrawn; PowerShell/cmdline quoting differs from POSIX `shlex`.
5. **Real CLI Diagnostic Driver Delivered & Repaired (C2274)**: `windows_rpc_diagnostic_driver.py` reuses pinned `SshFileBusClient`, completely eliminates `enroll` and `--body`, enforces strict stdin token/payload ingestion, and emits sanitized SHA256 body digests, providing a hardened, verified vehicle for native Windows execution.
6. **Local Windows Store Backend**: Remains strictly designated **`UNKNOWN / HELD`** (lacks native Windows `flock` and `O_DIRECTORY` directory fsync).
