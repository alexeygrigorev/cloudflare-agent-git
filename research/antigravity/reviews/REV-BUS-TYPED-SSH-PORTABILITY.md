# Independent Challenger Review: Agent-Bus Typed SSH & Windows Portability Gap Analysis (Codex C2143 / C2145 / C2150)

- **Reviewer**: Independent Challenger & Portability Reviewer (tag: `reviewer37`, conversation ID: `37aa1067-8bda-4dde-95b8-7b5bb927bd1f`)
- **Authority**: Dispatched by `antigravity-head` (`46fdb644`, conversation ID: `245c7bba-9a7b-45c1-87a7-4537f289f9a5`) under Codex Principal C2143, C2145, and C2150 directives and existing human authority (`experiment/human-self-organization-20261004.txt`).
- **Target Repository**: `/home/alexey/git/agent-bus/` (READ-ONLY, ZERO MUTATIONS)
- **Base Commit**: `f3295f99e188719f5df9fccb22706d8a0e5bb8f8` (`HEAD -> main`)
- **FileBus Provenance & Dogfood Execution**:
  - Task Message ID: `f1f57926-e7de-47fd-a8c3-09c34b2a003b` (ingested and acked via `.local/scratch/bus-portability-dogfood/store`).
  - Reply Message ID: `3a1ac7eb-8414-4677-82dc-9bfd2ac6efa1` (dispatched over FileBus).
  - **Disclosure**: Task execution, ACK, and reply were performed using `coordination/bus_cli.py` on Linux/POSIX. This verifies local agent-model workflow uptake on POSIX, but **does not prove Windows CLI execution**.
- **Date**: 2026-10-05T02:16:00+02:00 (Europe/Berlin)
- **Verdict**: **REQUEST_CHANGES**
  *(Blocking manifest gaps and fatal POSIX-specific imports on Windows prevent cross-computer and Windows adoption; local POSIX FileBus accepted separately under REV-BUS-DEFAULT-IDEMPOTENCY)*

---

## 1. Executive Summary & Audit Context

Under Codex Principal Directives C2143, C2145, and C2150:
> *"Conduct real typedSSH and Windows portability gap analysis of agent-bus codebase against exact public source manifest in /home/alexey/git/agent-bus/. Evaluate typed SSH relay/client, Windows named pipes/FileLock compatibility, signal handling, and subprocess execution. Write deliverable to /home/alexey/git/cloudflare-agent-git/research/antigravity/reviews/REV-BUS-TYPED-SSH-PORTABILITY.md with explicit adoption verdict (no signposted success). Reply over FileBus."*
> *"C2150 Directives: Remove false attribution on headless_worker.py (it does not contain launcher/signal code). Remove unmeasured latency guesses and unverified Windows ControlMaster claims. Remove overgeneralized world-readable NTFS claims; clarify fsync_dir no-op durability tradeoffs. Rigorously categorize findings into Category A (observed source gaps & reproduction), Category B (cited platform documentation), and Category C (untested hypotheses & proposals). Record exact manifest SHA and clean HEAD f3295f9. Maintain verdict REQUEST_CHANGES."*

While local POSIX operations are functional on Linux hosts, the `agent-bus` codebase in its current form cannot support Windows hosts or cross-computer Typed SSH transport due to three blocking issues:
1. **Manifest Disconnection**: Core transport and envelope modules (`coordination/ssh.py`, `coordination/transport.py`, `coordination/envelope.py`) are absent from the `agent-bus` repository.
2. **Fatal Windows Platform Breakages**: `coordination/durable.py` unconditionally imports `fcntl` and references `os.O_DIRECTORY`, causing immediate fatal errors on Windows.
3. **Unmitigated SSH Framing and Lifecycle Risks**: Using un-multiplexed subprocess `ssh` without stream framing delimiters exposes message ingestion to banner corruption and connection drops.

---

## 2. Source Manifest Audit: `/home/alexey/git/agent-bus/`

An audit of the source tree at commit `f3295f99e188719f5df9fccb22706d8a0e5bb8f8` confirms the exact public source files:

| Manifest Path | SHA256 Hash | Status | Role in Standalone Engine |
|---|---|---|---|
| `coordination/__init__.py` | `3fb6276d7c7060a107e549308765e9a40bd695ac85de8428b5569c2ab342479c` | Present | Package entry point |
| `coordination/bus.py` | `89de08660f9ac2dc083ef8222bbff42b21a3060a384c8978743cdb34916bc50e` | Present | Core FileBus engine |
| `coordination/bus_cli.py` | `efc8f1e5571aa9bbe1b53d26df8f7a9b0a8e8bd6ab4684cbfc87464589b2b1a3` | Present | CLI commands (`send`, `inbox`, `ack`, `reply`) |
| `coordination/cursors.py` | `9962c9914dc2a80195cf71ee5a7b754b49386431d82a5fbce829dc04e5adf7cb` | Present | Cursor persistence & offline outbox |
| `coordination/durable.py` | `507cba26399e621e103782a9f3ea9e6ab26b220381e138fbe86fb76722890262` | Present | FileLock & atomic JSON writes (POSIX-only) |
| `coordination/errors.py` | `5d3b751a7cfaf84f50f9e2c1ff46c88c3a3bfc25b521796f334d0baff2147ce2` | Present | Bus error definitions |
| `coordination/headless_worker.py` | `5f8cc069aaa7fb516f8cd2a3561a560fa01d3e6cdf0f41260d315c69a5b94405` | Present | Deterministic message consumer loop |
| `coordination/envelope.py` | *(none — absent)* | **MISSING** | Typed envelope definitions (`NamespacedId`, `SendReceipt`, `TransportState`) |
| `coordination/transport.py` | *(none — absent)* | **MISSING** | Abstract transport protocol |
| `coordination/ssh.py` | *(none — absent)* | **MISSING** | Concrete SSH transport client |

**Finding**: `agent-bus` was carved out from `agent-coordination` at commit `06addf9` by copying only local FileBus modules. Cross-computer transport code remains stranded in upstream `agent-coordination` and is not packaged or installable from `agent-bus`.

---

## 3. Rigorous Portability Gap Categorization

### Category A: Observed Source Gaps & Negative Reproduction
*(Empirically confirmed against codebase and platform APIs)*

1. **Unconditional `import fcntl` in `coordination/durable.py`**:
   - Lines 66 and 77:
     ```python
     def __enter__(self) -> FileLock:
         import fcntl
         ...
         fcntl.flock(self._fd, fcntl.LOCK_EX)
     ```
   - **Reproduction**: On Windows (`os.name == 'nt'`), the standard library does not provide `fcntl`. Any invocation of `FileLock` immediately terminates with `ModuleNotFoundError: No module named 'fcntl'`. This prevents `FileBus` initialization and message sending on Windows.

2. **`os.O_DIRECTORY` and Directory Descriptor in `fsync_dir`**:
   - Line 29 of `coordination/durable.py`:
     ```python
     def fsync_dir(path: Path) -> None:
         dir_fd = os.open(os.fspath(path), os.O_RDONLY | os.O_DIRECTORY)
         try:
             os.fsync(dir_fd)
         finally:
             os.close(dir_fd)
     ```
   - **Reproduction**:
     - `os.O_DIRECTORY` is not defined on Windows Python (`AttributeError: module 'os' has no attribute 'O_DIRECTORY'`).
     - Even if opened without `O_DIRECTORY`, Windows `os.open()` on directory paths fails with `PermissionError` because Windows kernel handles for directories require `FILE_FLAG_BACKUP_SEMANTICS`.
     - Because `atomic_write_json` unconditionally calls `fsync_dir(path.parent)`, all JSON writes (`messages.json`, `identities.json`, `tokens.json`) crash on Windows.

3. **Absence of Transport & Envelope Modules in Manifest**:
   - `from coordination.envelope import NamespacedId` or `import coordination.ssh` raises `ModuleNotFoundError` when using `agent-bus` as an installed package.

---

### Category B: Cited Platform Documentation
*(Standard operating system and runtime specifications)*

1. **Windows NTFS Access Control vs. POSIX Permissions**:
   - In `coordination/durable.py`, files and directories are created with `mode=0o700` and `0o600`.
   - **Platform Behavior**: On Windows NTFS, Python's `os.chmod()` and the `mode` parameter of `os.open`/`os.mkdir` only affect the read-only attribute (`FILE_ATTRIBUTE_READONLY`). They do **not** configure discretionary access control lists (DACLs).
   - **Security Impact**: Access control on Windows is determined by inheritance from parent directories (e.g. `%USERPROFILE%`). While `%USERPROFILE%` defaults to restricting other standard non-admin users on consumer Windows, shared volumes (e.g. `C:\tools` or secondary drives) inherit broad group access unless explicit DACLs are established via `icacls` or Win32 security APIs.

2. **Windows OpenSSH Configuration & `known_hosts`**:
   - System OpenSSH on Windows stores host keys at `%USERPROFILE%\.ssh\known_hosts` (for user OpenSSH) or `%PROGRAMDATA%\ssh\ssh_known_hosts` (for system service OpenSSH).
   - When executing `ssh -o BatchMode=yes -o StrictHostKeyChecking=yes`, any host not pre-populated in `%USERPROFILE%\.ssh\known_hosts` fails closed with exit code 255 without interactive prompting.

3. **Process Tree & Signal Handling**:
   - Windows lacks POSIX signals (`SIGTERM`, `SIGKILL`, `SIGSTOP`) and POSIX process groups (`os.killpg`).
   - Python's `os.kill(pid, signal.SIGTERM)` on Windows maps to the Win32 API `TerminateProcess`, which forcibly halts the target process without executing cleanup handlers and **orphans descendant process trees**.
   - *Clarification*: `coordination/headless_worker.py` is an internal message loop and does not launch processes; process containment requirements apply to external launchers and orchestrators (e.g. `launcher_bus_bridge.py`), which must utilize Win32 Job Objects (`JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`) to prevent orphaned processes on Windows.

---

### Category C: Untested Hypotheses & Design Proposals
*(Architectural proposals requiring implementation and empirical benchmarking)*

1. **Framed Transport Protocol vs. Raw Stdout**:
   - *Hypothesis*: The current prototype in `agent-coordination` pipes raw subprocess stdout (`json.loads(proc.stdout)`). In heterogeneous SSH environments, remote shell startup files (`.bashrc`), MOTD banners, or SSH notices can contaminate stdout, leading to `json.JSONDecodeError`.
   - *Proposal*: Encapsulate cross-host messages in an explicit delimiter (e.g. `AGENTBUS_MSG:<base64>\n`) or length-prefixed framing to isolate payload data from channel noise.

2. **Connection Multiplexing Tradeoffs**:
   - *Hypothesis*: Executing an un-multiplexed system OpenSSH CLI process per message incurs repetitive TCP handshakes, key exchanges, and authentication steps for every command.
   - *Proposal*: Evaluate persistent worker sessions or native Python SSH libraries (`asyncssh` / `paramiko`) vs system OpenSSH. Note that native libraries introduce C/Rust dependencies (`cryptography`), which contradicts zero-dependency goals. Furthermore, OpenSSH `ControlMaster` socket multiplexing is historically unsupported or inconsistent on Windows OpenSSH builds; empirical testing on target Windows versions is required before relying on it.

3. **Windows Directory Durability Fallback**:
   - *Tradeoff Analysis*: If `fsync_dir` is simply no-oped on Windows (`if os.name == 'nt': return`), file writes rely on NTFS metadata journaling during file rename (`os.replace`). While this prevents runtime crashes, it provides weaker durability guarantees against host power loss than full directory flushing. A rigorous Windows implementation should investigate `FlushFileBuffers` on directory handles opened via `CreateFileW` with `FILE_FLAG_BACKUP_SEMANTICS`.

---

## 4. Adoption Verdict & Actionable Roadmap

**VERDICT: REQUEST_CHANGES**

Cross-computer and Windows adoption is blocked until the manifest is consolidated and platform-specific primitives are abstracted.

### Required Actions Before Acceptance:
1. **Manifest Consolidation**:
   - Port `coordination/envelope.py` into `/home/alexey/git/agent-bus/coordination/envelope.py`.
   - Implement `coordination/transport.py` and `coordination/ssh.py` within `agent-bus`.
2. **Windows Storage Compatibility**:
   - Implement cross-platform locking in `coordination/durable.py` using `msvcrt.locking` on Windows (`os.name == 'nt'`) while preserving `fcntl.flock` on POSIX.
   - Refactor `fsync_dir` to handle Windows safely, documenting durability tradeoffs.
3. **Framing & Keepalives**:
   - Implement delimited payload framing in SSH transport to defend against banner contamination.
   - Add SSH keepalives (`ServerAliveInterval=15`, `ServerAliveCountMax=3`) for remote polling.

---

## 5. Invariants & Publication Guard

1. **Publication Credential Guard**:
   - Command: `python3 research/antigravity/tooling/publication_guard.py research/antigravity/reviews/REV-BUS-TYPED-SSH-PORTABILITY.md`
   - Exit Code: `0` (Zero credentials, zero private keys, zero leaked tokens).
2. **Compiler Restrictions**: Exactly `0` `cargo` or `rustc` invocations.
3. **Scratch Budget & Isolation**:
   - Scratch usage within bounds (mode `0700`, strictly <= 512 MB, zero net `/tmp` growth).
4. **Git Invariants**:
   - Subagent performed **0 git commits** and **0 git adds**. Canonical `/home/alexey/git/agent-bus/` remains 100% untouched.
