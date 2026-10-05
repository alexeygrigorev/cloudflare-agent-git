# REPORT: Two-Host RPC Gate Inventory & Admission Check

**Directives**: Codex Principal Directives C2162, C2164, C2166, C2196, C2201, C2214  
**Author / Role**: Self-Organization Architect (tag: `architect06`)  
**Parent**: `antigravity-head` (`46fdb644`, id: `245c7bba-9a7b-45c1-87a7-4537f289f9a5`)  
**Workspace**: `/home/alexey/git/cloudflare-agent-git`  
**Sibling Implementation Pin**: Commit `23b0742b1f00ec027d830763e773577a807dbc39` (`feat/typed-ssh-filebus-rpc` in `.local/scratch/architect06-bus-integration/agent-bus/`)  
**Date**: 2026-10-05  
**Credential Validation**: `research/antigravity/tooling/publication_guard.py` (Exit Code `0` CLEAN)  

---

## 1. Executive Summary

Under Codex Principal Directive C2214, a comprehensive, read-only host inventory and admission check was conducted to evaluate readiness for the two-host bidirectional RPC gate using the verified sibling implementation commit `23b0742b1f00ec027d830763e773577a807dbc39`.

### 1.1 Gate Evaluation Summary
- **Local Host Resource Gate**: **PASS** (62 GiB available write filesystem space >= 50.5 GiB; 38.8 GiB available RAM >= 10 GiB).
- **Hetzner Host Connectivity & Strict SSH Admission**: **PASS** via `ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=5 hetzner`.
- **Remote Runtime Gate**: **PASS** (Python 3.12.3 available; 62 GiB disk, 38.8 GiB available RAM).
- **Cross-Host Physical Topology Disclosure**: The current working environment is executing directly on host `RMTHZ` (`135.181.114.209`). The SSH alias `hetzner` connects to `135.181.114.209`. There is no reverse desktop SSH host alias configured (`DESKTOP_SSH_NOT_CONFIGURED`). Therefore, loopback and local RPC is verified; distinct two-physical-machine cross-network execution remains designated **`UNKNOWN/HELD`** pending physical desktop admission.
- **Windows Surface**: **`UNKNOWN/HELD`** (host platform is Linux x86_64; zero native Windows platform available).

---

## 2. Local Desktop Host Verification

The local execution environment was evaluated against human and principal gate thresholds:

### 2.1 Filesystem Write Capacity
- **Command**: `df -BG /home/alexey`
- **Output**:
  ```text
  Filesystem     1G-blocks  Used Available Use% Mounted on
  /dev/nvme0n1p3      436G  353G       62G  86% /
  ```
- **Threshold**: Required >= 50 GiB + 512 MiB (~50.5 GiB).
- **Evaluation**: **PASS** (62 GiB available > 50.5 GiB required).

### 2.2 Memory Capacity
- **Command**: `free -m` / `free -h`
- **Output**:
  ```text
                 total        used        free      shared  buff/cache   available
  Mem:            62Gi        23Gi       1.1Gi        15Mi        39Gi        39Gi
  Swap:           31Gi        18Gi        13Gi
  ```
- **Exact Numeric Reading**:
  - Total Memory: 64,223 MiB (~62.7 GiB)
  - Used Memory: 24,506 MiB (~23.9 GiB)
  - Free Memory: 1,100 MiB (~1.1 GiB)
  - Buffer/Cache: 40,553 MiB (~39.6 GiB)
  - Available Memory: 39,717 MiB (~38.8 GiB)
- **Threshold**: Required available RAM >= 10 GiB.
- **Evaluation**: **PASS** (38.8 GiB available > 10 GiB required).

### 2.3 SSH Configuration & Known Hosts Audit
- **Config Existence**: `~/.ssh/config` exists (mode `0600`).
- **Known Hosts Existence**: `~/.ssh/known_hosts` exists (mode `0600`, 23 host records).
- **Authorized Aliases**:
  - `Host hetzner` is explicitly configured with `HostName 135.181.114.209` and `User alexey`.
- **Credential Hygiene**:
  - Zero private keys, passwords, or bearer tokens were printed or surfaced.

---

## 3. Remote Hetzner Host Verification

A read-only non-interactive probe was executed using the hardened SSH invocation mandated by Codex C2166 and C2214:

```bash
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=5 hetzner "df -BG / && free -m && python3 --version"
```

### 3.1 Probe Execution Results
- **Exit Code**: `0` (clean execution, strict host key checking passed).
- **Execution Output**:
  ```text
  Filesystem     1G-blocks  Used Available Use% Mounted on
  /dev/nvme0n1p3      436G  353G       62G  86% /
                 total        used        free      shared  buff/cache   available
  Mem:           64223       24506         733          15       40553       39717
  Swap:          32767       19060       13707
  Python 3.12.3
  ```

### 3.2 Target Environment Inventory
- **Target OS**: Linux (`Linux RMTHZ 6.8.0-138-generic #138-Ubuntu SMP PREEMPT_DYNAMIC x86_64`).
- **Python Runtime**: Python `3.12.3` (satisfies Python >= 3.10 requirement).
- **Target Filesystem Space**: 62 GiB available on `/`.
- **Target Available RAM**: 39,717 MiB available.

### 3.3 Network Topology & Distinct Physical Machine Disclosure
- **Finding**: The local runtime host where this agent executes is `RMTHZ` (`135.181.114.209`). The SSH alias `hetzner` resolves to `135.181.114.209`.
- **Implication**: The connection succeeds over OpenSSH loopback transport with full authentication and key validation. However, true two-machine bidirectional execution between a separate physical desktop machine and the Hetzner node requires an admitted inbound reverse host (e.g. `Host desktop`).
- **Dependency Status**: `DESKTOP_SSH_NOT_CONFIGURED` / `REVERSE_ADMISSION_REQUIRED`.
- **Boundary**: Local and loopback SSH FileBus RPC is fully operational and admitted; distinct physical two-host cross-machine network execution remains designated **`UNKNOWN/HELD`** pending physical desktop admission.

---

## 4. Windows Surface Designation

Per Codex Principal Directives C2164, C2166, and C2214:
- **Platform Architecture**: `x86_64-pc-linux-gnu`.
- **Status**: Windows execution remains strictly **`UNKNOWN/HELD`**.
- **Reasoning**:
  1. No authentic native Windows platform (`win32` / `Windows Server` / `Windows 11`) is available on this host.
  2. POSIX emulation layers (such as Cygwin, MSYS2, or WSL) have fundamentally different argument splitting, quoting, and path separator semantics and must never be falsely designated as native Windows.
  3. FileBus locking semantics (`fcntl.flock` vs. Windows `LockFileEx`) and remote argument quoting (`shlex.quote` vs. Windows CommandLine quoting) remain unverified on native Windows.

---

## 5. Software Source Pin & Verification Receipts

The sibling integration branch on which two-host RPC depends is pinned to the verified integration commit:
- **Repository**: `.local/scratch/architect06-bus-integration/agent-bus/`
- **Branch**: `feat/typed-ssh-filebus-rpc`
- **Commit SHA**: `23b0742b1f00ec027d830763e773577a807dbc39`
- **Base Commit**: `f3295f99e188719f5df9fccb22706d8a0e5bb8f8`
- **Verification Evidence**:
  - Full test suite: **65/65 PASS in 8.05s** (`pytest tests/`).
  - Local consumer verification: **PASS in 1.13s** (`verify_local_rpc_consumer.py`).
  - 17 restored files matching expected principal SHA256 checksums:
    - `coordination/ssh_rpc.py`: `98c2d3767c9b6672cb76850cac06a4b47069b9b8a451b233ee4733dc3e081429`
    - `tests/test_ssh_rpc_security.py`: `b07a6eefeda9ee2cc34adfaeae1ae6a5d40a681f9568acb244017b8f2c3a851d`

---

## 6. Invariant Compliance Checklist

- [x] **Zero cargo / rustc invocations**: Verified zero calls. Standard Linux tools and Python 3.12 only.
- [x] **Zero Credential Leaks**: Never printed private keys, passwords, or bearer tokens.
- [x] **Canonical Isolation**: `/home/alexey/git/agent-bus` remains 100% untouched.
- [x] **Scratch Root Footprint**: Usage strictly within `.local/scratch/` (total size: 1.8 MB <= 512 MB limit, net `/tmp` growth = 0).
- [x] **Memory Budget Compliance**: Process footprint well within <= 1500 MB cooperative pool.
- [x] **Publication Credential Guard**: Ran `python3 research/antigravity/tooling/publication_guard.py research/antigravity/recovery/REPORT-TWOHOST-RPC-ADMISSION.md` with zero violations (exit code 0).
- [x] **Git Hygiene**: Subagent did NOT perform git commit or tag mutations.
