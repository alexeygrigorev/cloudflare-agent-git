# Independent Challenger Review: Loopback OpenSSH FileBus RPC Trial (Codex C2219 / C2221)

- **Reviewer**: Independent Challenger Reviewer (`reviewer37`, subagent conversation ID: `37aa1067-8bda-4dde-95b8-7b5bb927bd1f`)
- **Reviewer Identity ID**: `163fa1fb-38ac-47ba-a73c-afe0778fec7d`
- **Authority**: Dispatched by `antigravity-head` (`46fdb644`, conversation ID: `245c7bba-9a7b-45c1-87a7-4537f289f9a5`) under Codex Principal Directives C2219 and C2221; auditing trial under Directives C2162, C2164, C2166, C2214, and C2217; existing human authority (`experiment/human-cross-computer-product-20261004.txt`).
- **Target Integration Repository**: `/home/alexey/git/cloudflare-agent-git/.local/scratch/architect06-bus-integration/agent-bus`
- **Pinned Sibling Commit**: `23b0742b1f00ec027d830763e773577a807dbc39` atop `f3295f99e188719f5df9fccb22706d8a0e5bb8f8` (`feat/typed-ssh-filebus-rpc`)
- **Audited Trial Script**: `/home/alexey/git/cloudflare-agent-git/.local/scratch/architect06-bus-integration/verify_loopback_ssh_rpc.py`
- **Audited Trial Report**: `/home/alexey/git/cloudflare-agent-git/research/antigravity/recovery/REPORT-LOOPBACK-SSH-RPC-TRIAL.md`
- **Audited Trial Store**: `/home/alexey/git/cloudflare-agent-git/.local/scratch/loopback-ssh-trial/store`
- **Audit Testbed**: `.local/scratch/reviewer37-ssh-negatives/` (mode `0700`, <= 512 MB, zero net `/tmp` growth)
- **Canonical Repositories Status**: Canonical `/home/alexey/git/agent-bus` and `/home/alexey/git/agent-dashboard` remained strictly read-only throughout this review.
- **Compiler Invariant**: Exactly `0` `cargo` or `rustc` invocations executed during this review interval and audit environment under human hold (scoped strictly to reviewer actions and subprocesses).
- **Date**: 2026-10-05T03:30:00+02:00 (Europe/Berlin)
- **Verdict**: **BOUNDED ACCEPTANCE (SELF-HOST OPENSSH / LINUX CLIENT SCOPE)**
  *(Self-host OpenSSH RPC lifecycle and negative security defenses verified on Linux; live multi-host network execution across distinct physical machines remains UNKNOWN/HELD)*

---

## 1. Executive Summary & Review Scope

Under Codex Principal Directives C2219 and C2221, an independent challenger review was performed on the loopback OpenSSH FileBus RPC integration trial conducted by `architect06` (under Directives C2214 and C2217).

This review evaluated:
1. **Happy-Path Receipts & Timing Analysis**: Verification of the 8-step multi-agent handshake lifecycle and an empirical audit of the timing data reported in `REPORT-LOOPBACK-SSH-RPC-TRIAL.md`.
2. **Live Adversarial & Negative Test Execution**: An independent test suite (`test_ssh_rpc_negatives.py`) executed against a real OpenSSH daemon (`host="hetzner"`) exercising spaces in store paths, credential and traceback redaction on authentication failures, positional destination injection defenses, and strict host key checking policy bypass rejection.
3. **Epistemic Boundaries**: Rigorous classification of physical network topology boundaries, ambient SSH configuration trust boundaries, and platform scope limitations.

---

## 2. Happy-Path Audit & Timing Nuance

The happy-path trial script (`verify_loopback_ssh_rpc.py`) executed an 8-step handshake over real OpenSSH subprocesses connecting to destination `hetzner`.

### Receipts Audit:
- **Enrollment**: Successfully enrolled identities `ssh-alice` (`7141c340...`) and `ssh-bob` (`34192145...`).
- **Piped RPC Dispatch**: Alice sent a structured message to Bob, Bob retrieved it from his unread inbox, acknowledged it (`acked_at: 2026-10-05T01:16:47Z`), verified the unread inbox was empty, replied with correlation metadata, and Alice retrieved and validated the correlated reply.
- **Total Reported Duration**: 3.019 seconds for 8 sequential OpenSSH process invocations.

### Timing Nuance in Section 4 Table:
In Section 4 of `REPORT-LOOPBACK-SSH-RPC-TRIAL.md`, the timing breakdown lists:
```text
| Inbox Verification | inbox | OpenSSH (hetzner) | 0.350s | 0 unread messages |
```
**Challenger Finding**: An inspection of the source code in `verify_loopback_ssh_rpc.py` (lines 119–123) reveals:
```python
    # 6. Verify Bob unread inbox is empty
    inbox_bob_after = client.inbox(identity_id=bob_id, token=bob_tok, unread_only=True)
    assert len(inbox_bob_after) == 0, f"Expected 0 unread messages, got {len(inbox_bob_after)}"
    print("  [OK] Verified Bob unread inbox is empty after ACK")
```
Unlike Steps 1–5, 7, and 8, Step 6 did not record a distinct `t_step = time.monotonic()` timestamp delta or print its duration in the execution log. The reported duration of `0.350s` was mathematically back-calculated by subtracting the sum of the 7 individually timed operations ($2.669\text{s}$) from the total run duration ($3.019\text{s}$). While the aggregate time of $3.019\text{s}$ is accurate and the back-calculation is mathematically sound ($3.019 - 2.669 = 0.350\text{s}$), discrete telemetry for Step 6 was absent in the benchmark script itself.

---

## 3. Independent Negative Verification Suite: `test_ssh_rpc_negatives.py`

To independently challenge the implementation's resilience against misconfigurations, adversarial options, and credential leaks, a dedicated negative test suite was created in `.local/scratch/reviewer37-ssh-negatives/test_ssh_rpc_negatives.py` and executed against the live OpenSSH daemon:

```text
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.1.1, pluggy-1.6.0
rootdir: /home/alexey/git/cloudflare-agent-git
plugins: anyio-4.12.1, opik-2.2.54
collected 4 items

.local/scratch/reviewer37-ssh-negatives/test_ssh_rpc_negatives.py::test_store_path_with_spaces_over_real_ssh PASSED [ 25%]
.local/scratch/reviewer37-ssh-negatives/test_ssh_rpc_negatives.py::test_auth_failure_redaction_over_real_ssh PASSED [ 50%]
.local/scratch/reviewer37-ssh-negatives/test_ssh_rpc_negatives.py::test_destination_injection_defense PASSED [ 75%]
.local/scratch/reviewer37-ssh-negatives/test_ssh_rpc_negatives.py::test_strict_host_key_checking_bypass_rejection PASSED [100%]

============================== 4 passed in 2.34s ===============================
```

### Detailed Negative Case Analysis:

1. **Store Path with Spaces (`test_store_path_with_spaces_over_real_ssh`)**:
   - **Threat / Edge Case**: Paths containing whitespace (e.g. `/path/to/store with spaces in name`) frequently suffer from word-splitting bugs when passed through remote shell execution strings (`ssh host python3 bus_cli.py --store ...`).
   - **Verification**: A store was initialized at `.local/scratch/reviewer37-ssh-negatives/store with spaces in name`. `SshFileBusClient` enrolled an identity, sent a message, retrieved the inbox, and acknowledged the message over real OpenSSH.
   - **Outcome**: PASSED. Remote command assembly in `_execute_rpc` properly applies `shlex.quote(self.store_path)` and `shlex.quote(self.bus_cli_path)`, preventing POSIX remote login shells from splitting the path arguments.

2. **Authentication Failure Redaction & Decoupled Chaining (`test_auth_failure_redaction_over_real_ssh`)**:
   - **Threat / Edge Case**: When an unprivileged or hostile agent provides an invalid token, unhandled exceptions or error messages may echo the provided token, raw stdout/stderr, or remote Python tracebacks into logs or parent process context.
   - **Verification**: Enrolled identity `bob-auth` and subsequently issued an inbox query with invalid bearer token `SUPER_SECRET_INVALID_TOKEN_99999` over real OpenSSH.
   - **Outcome**: PASSED.
     * Raised `AuthError` fail-closed.
     * `str(err)` contained `Remote authentication error (invalid_token)` and completely omitted the invalid bearer token.
     * `str(err)` contained zero traceback text, file paths, or line numbers (`Traceback`, `File "` absent).
     * Exception chaining was strictly decoupled: `err.__cause__ is None` and `err.__context__ is None`, guaranteeing zero leakage via exception inspection.

3. **Destination Injection Defense (`test_destination_injection_defense`)**:
   - **Threat / Edge Case**: An attacker supplies a bare destination operand (e.g. `['attacker.com']`) or tunneling flags in `ssh_opts` to redirect the SSH connection before the `--` separator.
   - **Verification**: Tested positional arguments without leading `-` and disallowed flags (`-D`, `-L`, `-R`, `-X`, `-Y`, `-A`, `-w`).
   - **Outcome**: PASSED. Any positional argument in `ssh_opts` without a `-` prefix is immediately rejected with `ValueError("Positional destination argument in ssh_opts is prohibited...")`. All disallowed flags fail closed with `ValueError("Prohibited or unrecognized SSH option flag...")`.

4. **Strict Host Key Checking Bypass Rejection (`test_strict_host_key_checking_bypass_rejection`)**:
   - **Threat / Edge Case**: An agent attempts to bypass MITM verification by specifying `-o StrictHostKeyChecking=accept-new`, `-o StrictHostKeyChecking=no`, or `-o BatchMode=no`.
   - **Verification**: Tested attached, detached, and spaced variations of `StrictHostKeyChecking=no`, `accept-new`, `off`, `ask`, and `BatchMode=no`, as well as dangerous executable options (`KnownHostsCommand=/bin/true`).
   - **Outcome**: PASSED. Option normalization parses keywords case-insensitively and fails closed with `ValueError("StrictHostKeyChecking must be 'yes'...")` or `ValueError("BatchMode must be 'yes'...")`. Untrusted options outside `ALLOWED_SSH_OPTION_KEYS` fail closed with `ValueError("OpenSSH option ... is prohibited...")`.

---

## 4. Epistemic Demarcation & Physical Boundary Classification

1. **Topology Demarcation (Self-Host vs. Physical Multi-Machine)**:
   - In the audit environment, the OpenSSH destination alias `hetzner` resolves to a local loopback / self-host OpenSSH endpoint on host `RMTHZ`.
   - While this trial validates authentic OpenSSH process execution, Unix socket creation, authentication handshakes, and process argument isolation against a real `sshd` process, it **does not demonstrate two distinct physical or virtual machines communicating across a physical network**.
   - Distinct physical multi-machine execution across WAN/LAN remains **`UNKNOWN/HELD`**.

2. **Network Resilience & Jitter**:
   - Loopback OpenSSH execution incurs negligible packet loss, zero MTU fragmentation, and sub-millisecond round-trip times.
   - Real WAN network hazards (TCP connection drops, NAT traversal timeouts, asymmetric routing, DNS delays, SSH keepalive timeouts under load) remain **untested and unmeasured**.

3. **Reverse Desktop Host Input Dependency**:
   - To achieve bidirectional cross-computer communication between the desktop node and the Hetzner node, a reverse SSH endpoint or network path back to the desktop is required as an external input from `desktop-orchestrator` / human root.

4. **Platform Scope Limitations (POSIX vs. Windows)**:
   - All tests were executed on Linux (`x86_64`, kernel 6.8).
   - Windows execution (`cmd.exe` / `powershell.exe`) remains strictly **`UNKNOWN/HELD`**. Windows lacks POSIX `fcntl.flock`, does not support `O_DIRECTORY` file descriptors, and uses incompatible argument escaping rules that make `shlex.quote` unsafe.

---

## 5. Invariant & Governance Receipts

1. **Compiler Hold**:
   - Exactly **`0`** `cargo` or `rustc` invocations were executed during this review interval and audit environment under human hold (scoped strictly to reviewer actions and subprocesses).
2. **Canonical Repositories**:
   - `/home/alexey/git/agent-bus` and `/home/alexey/git/agent-dashboard` remained completely untouched and strictly read-only.
3. **Scratch Resource Isolation**:
   - Testbed confined strictly to `.local/scratch/reviewer37-ssh-negatives/` (mode `0700`, total size 44 KB $\le$ 512 MB).
   - `TMPDIR` was set strictly inside `.local/scratch/reviewer37-ssh-negatives/tmp` with zero net growth in system `/tmp`.
4. **Git Tree Cleanliness**:
   - Zero `git commit` or `git push` commands were issued.
5. **Publication Guard**:
   - Verified via `python3 research/antigravity/tooling/publication_guard.py research/antigravity/reviews/REV-LOOPBACK-SSH-RPC.md` with clean exit code `0`.

---

## 6. Adoption Verdict

**VERDICT: BOUNDED ACCEPTANCE (SELF-HOST OPENSSH / LINUX CLIENT SCOPE)**

The loopback OpenSSH FileBus RPC implementation in `feat/typed-ssh-filebus-rpc` (commit `23b0742b1f00ec027d830763e773577a807dbc39`) is accepted for single-node / self-host OpenSSH integration on Linux/POSIX client nodes.

**Boundaries & Held States**:
- **Physical Multi-Machine Cross-Network Execution**: Designated **`UNKNOWN/HELD`** pending bidirectional network execution between distinct physical machines.
- **Ambient Configuration Trust Boundary**: Ambient user configurations (`~/.ssh/config`) are an administrative trust boundary; universal protection against hostile local ambient configs is withheld unless local config evaluation is suppressed (`-F /dev/null`).
- **Timing Telemetry Requirement**: Future benchmarking scripts must capture discrete `monotonic()` timestamps for all individual operations (including post-ACK inbox queries) rather than back-calculating from aggregate cycle times.
- **Windows Platform Surface**: Strictly designated **`UNKNOWN/HELD`** (zero Windows execution performed).
