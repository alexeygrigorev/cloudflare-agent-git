# Independent Challenger Review: Typed SSH FileBus RPC Dogfood Verification (Codex C2201 / C2203 / C2204)

- **Reviewer**: Independent Challenger Reviewer (`reviewer37`, subagent conversation ID: `37aa1067-8bda-4dde-95b8-7b5bb927bd1f`)
- **Reviewer Identity ID**: `163fa1fb-38ac-47ba-a73c-afe0778fec7d`
- **Authority**: Dispatched by `antigravity-head` (`46fdb644`, conversation ID: `245c7bba-9a7b-45c1-87a7-4537f289f9a5`) under Codex Principal Directives C2201, C2203, and C2204, and existing human authority (`experiment/human-cross-computer-product-20261004.txt`).
- **Target Integration Repository**: `/home/alexey/git/cloudflare-agent-git/.local/scratch/architect06-bus-integration/agent-bus`
- **Target Branch & Commit**: `feat/typed-ssh-filebus-rpc` at `23b0742b1f00ec027d830763e773577a807dbc39` atop `f3295f99e188719f5df9fccb22706d8a0e5bb8f8`
- **FileBus Store**: `/home/alexey/git/cloudflare-agent-git/.local/scratch/rpc-dogfood-review/store`
- **Task Ingestion Message ID**: `51aa653c-f63f-4c53-9e31-d3d4af5a9208`
- **Sender ID (Head)**: `fc418978-a2c4-47c1-a341-4bb4d023bd5a`
- **Task Acknowledged At**: `2026-10-05T01:04:10Z`
- **Reply Message ID**: `350081d7-06a6-4f4f-a8b2-18e78c43953b`
- **Reply Message Digest**: `7fbc628db2a29cd230d13dd09e6d0b51ea8f3c38fe40af83f8ec35aa40d02dcf`
- **Reply Timestamp**: `2026-10-05T01:04:44Z`
- **Canonical Repositories Status**: Canonical `/home/alexey/git/agent-bus` and `/home/alexey/git/agent-dashboard` remained strictly read-only throughout this audit.
- **Immutable Source Manifest Digest**: `bdca2ca979854695eeb057cde1bd2d03b83407765af7cd24b00f18fbd8565a92` (17 files verified)
- **Date**: 2026-10-05T03:05:00+02:00 (Europe/Berlin)
- **Verdict**: **BOUNDED ACCEPTANCE (COMPONENT LEVEL / LINUX CLIENT SCOPE)**
  *(Commit 23b0742b on feat/typed-ssh-filebus-rpc verified with 65/65 tests passing; live multi-host network execution and Windows platform execution remain UNKNOWN/HELD)*

---

## 1. Executive Summary & Dogfood Lifecycle Receipts

Under Codex Principal Directives C2201, C2203, and C2204, an independent dogfood audit of the clean sibling integration commit `23b0742b1f00ec027d830763e773577a807dbc39` was conducted over the real FileBus RPC interface.

### End-to-End RPC Dogfood Interaction
1. **Task Ingestion via RPC (`inbox`)**:
   - Query executed using reviewer identity `163fa1fb-38ac-47ba-a73c-afe0778fec7d` and scoped credentials via `bus_cli.py rpc`.
   - Task message `51aa653c-f63f-4c53-9e31-d3d4af5a9208` successfully retrieved from the unread inbox.
2. **Receipt Acknowledged via RPC (`ack`)**:
   - Dispatched `op="ack"` for message `51aa653c-f63f-4c53-9e31-d3d4af5a9208`.
   - Server returned clean confirmation with `acked_at: 2026-10-05T01:04:10Z`.
3. **Audit Execution**:
   - Bit-for-bit manifest check of all 17 integration files against immutable manifest `bdca2ca979854695eeb057cde1bd2d03b83407765af7cd24b00f18fbd8565a92`.
   - Full test execution in integration repo: **65/65 tests PASSED** in 8.65s.
   - Comprehensive comparative evaluation between Typed SSH FileBus RPC and the ordinary local FileBus CLI baseline.
4. **Verdict Submission via RPC (`reply`)**:
   - Dispatched `op="reply"` to message `51aa653c-f63f-4c53-9e31-d3d4af5a9208` with independent findings and verdict metadata.
   - Generated reply message ID: `350081d7-06a6-4f4f-a8b2-18e78c43953b`.
   - Resulting digest: `7fbc628db2a29cd230d13dd09e6d0b51ea8f3c38fe40af83f8ec35aa40d02dcf`.

---

## 2. Source Manifest Audit: Commit `23b0742b1f00ec027d830763e773577a807dbc39`

All 17 tracked source and test files in `/home/alexey/git/cloudflare-agent-git/.local/scratch/architect06-bus-integration/agent-bus` were hashed and verified against the restored manifest:

| File Path | SHA256 Checksum | Status | Role |
|---|---|---|---|
| `coordination/__init__.py` | `3fb6276d7c7060a107e549308765e9a40bd695ac85de8428b5569c2ab342479c` | MATCH | Package initialization |
| `coordination/bus.py` | `2720c191f0b6a32a6d0ad933737a7239126472e40907a55c4bc55d7396b00370` | MATCH | Core local FileBus engine |
| `coordination/bus_cli.py` | `a7a8c37459216f011267a37c52006245c91140474d12dd8006d735e1e5300715` | MATCH | Unified CLI & stdin RPC dispatcher |
| `coordination/cursors.py` | `9962c9914dc2a80195cf71ee5a7b754b49386431d82a5fbce829dc04e5adf7cb` | MATCH | Cursor tracking & offline storage |
| `coordination/durable.py` | `507cba26399e621e103782a9f3ea9e6ab26b220381e138fbe86fb76722890262` | MATCH | POSIX atomic rename & directory fsync |
| `coordination/envelope.py` | `a6abcf56dff5145da8b923de88bd1256db27bc26a05367e56b3135c52322c2b8` | MATCH | Typed RPC request/response envelopes |
| `coordination/errors.py` | `3ddd46071abce2d5269cb7804fd5207c8150cb5f23e3777e47aa33de076939e5` | MATCH | Categorical error classes with attribute omission |
| `coordination/headless_worker.py` | `5f8cc069aaa7fb516f8cd2a3561a560fa01d3e6cdf0f41260d315c69a5b94405` | MATCH | Headless consumer worker loop |
| `coordination/ssh_rpc.py` | `98c2d3767c9b6672cb76850cac06a4b47069b9b8a451b233ee4733dc3e081429` | MATCH | Hardened SSH RPC client & option normalizer |
| `tests/test_bus.py` | `0aa2c0fbb8616ff3eda78467f21cd36328b9bb2aaba39fcc1eb80e3a1a1e0ef7` | MATCH | Core bus unit tests |
| `tests/test_bus_concurrent.py` | `cd8509285462004c2597333a0aaaa625a620c4dbab59f474a18316f2629bc315` | MATCH | Multi-process lock concurrency tests |
| `tests/test_bus_crash.py` | `1a7f95bc9b9b048ba2028e40cc2039f0e8fd422074862f8c353d707dec2275a8` | MATCH | Crash recovery & corrupt journal tests |
| `tests/test_bus_dogfood.py` | `8d757b963f3a6aa5ddc1e5ab248b8c15cbe1de1b658f48f821480fd90bfd6822` | MATCH | End-to-end CLI workflow tests |
| `tests/test_bus_scope.py` | `63d4907368fe4d8195fdd8ac011a822ce4bfdebb95119e9f6edd46c17fead2d7` | MATCH | Task/project isolation scoping tests |
| `tests/test_headless_task.py` | `cbe6bf747b4a6c31fc72aebd306047ff3c3e53d7884f916d48ca50192d230b59` | MATCH | Worker dispatch & acknowledgment tests |
| `tests/test_ssh_rpc.py` | `82d876d0580045756aafadd3cbaa07bd5d4488d78c899158c4fa8fd288de9ab9` | MATCH | Typed RPC component & lifecycle tests |
| `tests/test_ssh_rpc_security.py` | `b07a6eefeda9ee2cc34adfaeae1ae6a5d40a681f9568acb244017b8f2c3a851d` | MATCH | Adversarial security & allowlist tests |

**Result**: 17 of 17 files verified. Clean tree, zero manifest deviations.

---

## 3. Comparative Architectural & Security Analysis: Typed SSH RPC vs Local CLI Baseline

An empirical evaluation was conducted comparing the `coordination/ssh_rpc.py` (`SshFileBusClient`) and `bus_cli.py rpc` interface against the ordinary local FileBus CLI subcommands (`bus_cli.py send`, `inbox`, `ack`, `reply`).

### 1. Architectural Distinction: Continuous Stdin/Stdout Streaming vs. Discrete CLI Process Invocations
- **Ordinary Local CLI Baseline**:
  - The canonical CLI implementation (`bus_cli.py`) at commit `23b0742b` is already strictly structured: all commands (`send`, `inbox`, `wait`, `show`, `ack`, `reply`, etc.) serialize and return structured JSON via `json.dumps(..., indent=2)`. It does not rely on unstructured plain text or regex parsing.
  - However, each CLI operation requires spawning a discrete Python process. For multi-step workflows (e.g. `inbox` -> `ack` -> `reply`), the runtime incurs repeated Python interpreter initialization, virtual environment loading, and module import overhead for every single operation.
- **Typed SSH FileBus RPC**:
  - Operates via continuous stdin/stdout streaming over a single long-lived process or transport channel (`bus_cli.py rpc`).
  - Structured request envelopes (`RpcRequest`) with explicit `op`, `request_id`, and `params` are piped via standard input, and structured responses (`RpcResponse`) are returned over standard output.
  - Enables connection and process reuse across multiple operations without repeated interpreter startup overhead.
  - Framing validation guarantees that banner noise, MOTD messages, or trailing garbage fail closed with a structured `FramingError`.

### 2. Process Argument Hygiene & `/proc` Exposure Boundary
- **Ordinary Local CLI Baseline**:
  - Authentication hygiene: The CLI already requires `--cred <path>` pointing to a restricted JSON credential file (mode `0600`), and does not accept or pass raw bearer tokens as command-line arguments on `sys.argv`.
  - Command-line exposure: Operation payloads (e.g., `--body <body>`, `--data <json>`) are passed as command-line arguments on `sys.argv`.
  - Process table visibility: On Linux hosts where `/proc` process visibility is unconfined (which depends on kernel configuration, mount options such as `hidepid=1` or `hidepid=2`, container PID namespaces, and LSM policies like SELinux or AppArmor), non-credential command arguments such as message bodies or data payloads can be inspected by other processes under the same user or system-wide if unhardened.
- **Typed SSH FileBus RPC**:
  - Neither tokens, credentials, message bodies, nor arbitrary JSON data are passed on `sys.argv`.
  - All operation parameters are piped exclusively through stdin JSON streams.
  - Inspection of `/proc/<pid>/cmdline` (where permitted by kernel mount options) reveals only:
    `python3 coordination/bus_cli.py --store <store_path> rpc`
  - Message contents, identifiers, and parameters remain strictly confined to process memory and private standard input pipes.

### 3. Fail-Closed Error Suppression & Decoupled Exception Chaining
- **Ordinary Local CLI**:
  - On failure, unhandled Python exceptions dump full tracebacks to `stderr`, potentially echoing input parameters and payloads into terminal logs or parent process buffers.
- **Typed SSH FileBus RPC**:
  - The client implements **fail-closed attribute omission**: exception objects (`TransportError`, `TransportTimeout`, `FramingError`, `AuthError`) expose only categorical error codes (`code`, `reason`, `exit_code`, `timeout_sec`). Raw remote stderr and raw stdout are completely omitted from public attributes.
  - **Decoupled Exception Chaining**: All caught subprocess exceptions (`subprocess.TimeoutExpired`, `json.JSONDecodeError`, `ValueError`) are re-raised with `raise ... from None`. This explicitly sets both `__cause__` and `__context__` to `None`, guaranteeing that sensitive payloads in `TimeoutExpired.output` or `JSONDecodeError.doc` cannot leak into unhandled traceback dumps or log sinks.

### 4. Strict Boolean Typing & Type Coercion Defense
- **Threat Model**: Weak type systems or loose deserialization may evaluate string `"false"`, string `"0"`, or integer `1` as truthy, masking failed remote operations.
- **Hardened Implementation**:
  - Both `RpcResponse.from_dict` and `SshFileBusClient._execute_rpc` enforce strict type checking:
    `if type(resp.ok) is not bool: raise FramingError(...)`
  - String `"false"`, `"0"`, or non-boolean truthy values fail closed immediately.

### 5. OpenSSH Command Construction & Policy Enforcement
- **Local Option Injection**:
  - Preceding `--` delimiter inserted before the host operand guarantees that OpenSSH treats the host argument strictly as a destination, defeating option hijacking (`-oProxyCommand=...`).
- **Bare Positional Destination Argument Defense**:
  - Any token in `ssh_opts` not beginning with `-` (e.g. `['attacker.com']`) is rejected fail-closed with `ValueError` to prevent destination hijacking before `--`.
- **Narrow Flag Allowlist & Integer Port Validation**:
  - Only vetted flags are accepted (`-o`, `-p`, `-i`, `-l`, `-c`, `-F` [with trust], `-4`, `-6`, `-C`, `-q`, `-v`, `-vv`, `-vvv`, `-T`, `-N`, `-n`); port `-p` is verified as an integer between 1 and 65535; disallowed flags (e.g. `-D`, `-L`, `-R`) fail closed.
- **Default-Deny Option Allowlist (`ALLOWED_SSH_OPTION_KEYS`)**:
  - Restricts options to 15 vetted parameters. Arbitrary executable or inclusion directives (`KnownHostsCommand`, `Include`, `LocalCommand`, `PermitLocalCommand`, `Match`, `PKCS11Provider`, `UserKnownHostsFile`) strictly fail closed with `ValueError`.
- **Untrusted Directive Defense**:
  - `ProxyCommand`, `ProxyJump`, and custom config files (`-F`) are prohibited by default and require explicit caller authorization (`allow_custom_proxycommand=True`).
- **Mandatory Policy Enforcement**:
  - Enforces `-o BatchMode=yes` and `-o StrictHostKeyChecking=yes`. Non-`yes` configurations fail closed immediately.
  - Conflicting duplicate options fail closed, defeating OpenSSH "first wins" injection bypasses.

### 6. Epistemic Demarcation & Negative Evidence
- **Unmeasured Quantitative Performance Delta**:
  - While continuous stdin/stdout streaming is functionally verified and architecturally avoids per-command Python interpreter startup, **quantitative throughput and latency performance advantages over the discrete CLI baseline remain unmeasured**.
  - No comparative microbenchmarks or high-frequency load tests were conducted during this review.
- **Shared Underlying Storage Backend**:
  - Both the Typed SSH RPC interface and the discrete CLI baseline execute against the exact same underlying `FileBus` storage engine, utilizing identical directory schemas, atomic rename semantics, JSON message serialization formats, and `fcntl.flock` concurrency locking.
  - Consequently, storage I/O characteristics, lock contention profiles, and disk persistence guarantees are identical across both interfaces.

---

## 4. Empirical Test Execution Receipts

### Integration Repository Suite (`PYTHONPATH=. python3 -m pytest -v tests/`): 65/65 PASS
```text
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.1.1, pluggy-1.6.0
rootdir: /home/alexey/git/cloudflare-agent-git/.local/scratch/architect06-bus-integration/agent-bus
configfile: pyproject.toml
plugins: anyio-4.12.1, opik-2.2.54
collected 65 items

tests/test_bus.py ...........                                            [ 16%]
tests/test_bus_concurrent.py ..                                          [ 20%]
tests/test_bus_crash.py .....                                            [ 27%]
tests/test_bus_dogfood.py .                                              [ 29%]
tests/test_bus_scope.py ....                                             [ 35%]
tests/test_headless_task.py .                                            [ 36%]
tests/test_ssh_rpc.py ..................                                 [ 64%]
tests/test_ssh_rpc_security.py .......................                   [100%]

============================== 65 passed in 8.65s ==============================
```

### Breakdown of Test Results:
- **Core FileBus Suite** (`test_bus*`, `test_headless_task.py`): 24/24 PASSED
- **RPC Component & Lifecycle Suite** (`test_ssh_rpc.py`): 18/18 PASSED
- **Adversarial Security & Allowlist Suite** (`test_ssh_rpc_security.py`): 23/23 PASSED
- **Total**: 65 PASSED, 0 FAILED, 0 SKIPPED in 8.65s.

---

## 5. Scope Demarcation: POSIX vs. Windows Surfaces

| Capability / Surface | POSIX Scope (`Linux` / `macOS`) | Windows Scope (`cmd.exe` / `PowerShell`) | Audit Status |
|---|---|---|---|
| SSH Host Option Injection (`--`, `_validate_host`) | Validated at component level | Untested on Windows | **POSIX COMPONENT VALIDATED** |
| Positional Destination Argument Defense | Validated at component level | Untested on Windows | **POSIX COMPONENT VALIDATED** |
| Narrow Flag Allowlist & Integer Port Validation | Validated at component level | Untested on Windows | **POSIX COMPONENT VALIDATED** |
| Option Normalization & Enforcement | Validated at component level | Untested on Windows | **POSIX COMPONENT VALIDATED** |
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
   - Command: `python3 research/antigravity/tooling/publication_guard.py research/antigravity/reviews/REV-TYPED-SSH-FILEBUS-RPC-DOGFOOD.md`
   - Result: Exit code `0` (clean, zero credential leaks, zero unredacted tokens).
2. **Compiler Restrictions**: Exactly `0` `cargo` or `rustc` invocations executed during this review interval and audit environment under human hold (scoped strictly to reviewer actions and subprocesses).
3. **Canonical Repository Cleanliness**:
   - Canonical repositories `/home/alexey/git/agent-bus` and `/home/alexey/git/agent-dashboard` remained strictly read-only; zero commits, zero stage additions.
4. **TMPDIR Isolation & Memory Budget**:
   - Scratch directory `.local/scratch/reviewer37-rpc-review/` (mode `0700`, <= 512 MB). Net zero growth on `/tmp`. Memory usage strictly within cooperative budget.

---

## 7. Adoption Verdict

**VERDICT: BOUNDED ACCEPTANCE (COMPONENT LEVEL / LINUX CLIENT SCOPE)**

The clean integration branch `feat/typed-ssh-filebus-rpc` at commit `23b0742b1f00ec027d830763e773577a807dbc39` is accepted for component-level integration on Linux/POSIX client nodes.

**Boundaries & Held States**:
- **Ambient Configuration Trust Boundary**: Ambient user configurations (`~/.ssh/config`) are an administrative trust boundary; universal protection against hostile local ambient configs is withheld unless local config evaluation is suppressed (`-F /dev/null`).
- **Unmeasured Performance / Latency Delta**: Quantitative throughput and latency performance advantages over the discrete CLI baseline remain unmeasured; both interfaces utilize the identical underlying FileBus storage backend.
- **Live Multi-Host Network Execution**: Remains `UNKNOWN/HELD` pending live bidirectional network execution between distinct physical/virtual host nodes.
- **Windows Runtime and Local Execution**: Strictly `UNKNOWN/HELD` (zero Windows execution performed; Windows remote quoting and locking remain unimplemented).
- **Target Known Hosts**: Target hosts must be pre-populated in `~/.ssh/known_hosts` to satisfy enforced `StrictHostKeyChecking=yes`.
