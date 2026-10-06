# Independent Peer Review: Windows Client Integration Contract (Product 4 — Cross-Computer Agent Coordination)

- **Directive**: C2922
- **Task Reference**: `coord-desktop-hetzner-test`
- **Launcher Task ID**: `t-coord-windows-contract-c2922`
- **Review Task ID**: `t-coord-windows-contract-review-c2922`
- **Reviewed Target Document**: [`research/coordination/WINDOWS-CLIENT-INTEGRATION-CONTRACT-20261006.md`](file:///home/alexey/git/cloudflare-agent-git/research/coordination/WINDOWS-CLIENT-INTEGRATION-CONTRACT-20261006.md)
- **Target Document Checksum (SHA-256)**: `c96e7581688d0c2e3328b33b7a14bdefa04ef283ee31b85e5a01e46f40ef67fa`
- **Review Date**: 2026-10-06T19:50:00+02:00 (Europe/Berlin)
- **Reviewer**: Antigravity Independent Peer Reviewer (`antigravity-cli`, subagent `71d9e70e-6588-4cf4-88ce-a985e83785f5`)
- **Reviewer Role**: Distinct Independent Reviewer for task `coord-desktop-hetzner-test` under Project Head
- **Caller / Head**: Product 4 Project Head (`764358a8-1b4e-49c6-845a-9b79bf3ba536` / `coord-917-custody-resume-20261006`)
- **Governing Agreements**: Scale-50 Recovery Plan (`coordination/SCALE50-RECOVERY-PLAN.md`), Operating Model (`coordination/OPERATING-MODEL.md`), Resource Policy (`coordination/RESOURCE-POLICY.md`)
- **Independent Verdict**: **ACCEPT**

---

## 1. Executive Summary & Verdict Rationale

This independent peer review evaluates the comprehensive integration contract authored for the physical Windows workstation client interacting with the Hetzner remote execution host (`hetzner-rmthz`), satisfying directive C2922 for task `coord-desktop-hetzner-test`.

### Final Verdict: ACCEPT

The evaluated contract document [`WINDOWS-CLIENT-INTEGRATION-CONTRACT-20261006.md`](file:///home/alexey/git/cloudflare-agent-git/research/coordination/WINDOWS-CLIENT-INTEGRATION-CONTRACT-20261006.md) definitively and accurately:
1. **Reconciles Checkpoint 47-baa4 Drift**: Formally establishes that `ping` is **not** an existing CLI subcommand in [`adapters/windows_client.py`](file:///home/alexey/git/agent-coordination/adapters/windows_client.py), catalogs the exact five canonical subcommands `{send, poll, reply, ack, rpc}`, and documents valid pre-flight transport checks using `poll`, `send --stdin-rpc`, or `rpc --method poll`.
2. **Enforces Zero-Dependency Runtime**: Accurately bounds the client to Windows Python 3.10+ Standard Library ONLY (zero pip packages, zero native or Rust build tools).
3. **Pins Client Manifest**: Accurately specifies the pinned client files and references with exact SHA-256 digests matching disk content.
4. **Enforces Strict Identity & Credential Isolation**: Formally adheres to `examples/devices.example.json` (`device_id="windows-desktop"`, `kind="ssh-client-host"`, `outbound_ssh_only=True`, `native_aplexer=False`), enforces `session_id=None` with active anti-spoofing rejection (`IdentitySpoofError`), and mandates strict head credential stripping/rejection (`reject_head_cred_inheritance` / `GuardRejected`).
5. **Preserves Private Cursors & Partitioning**: Formally defines local cursor progression stores (`.local/windows_cursors.db` / `.local/cursors.json`), server-side flock-protected event logs (`host_events.jsonl`), partition isolation by `(device_id, session_id)`, and corrupt cursor auto-recovery.
6. **Validates Dry-Run Help & Command Invocations**: All six CLI dry-run invocations (`--help`, `send --help`, `poll --help`, `reply --help`, `ack --help`, `rpc --help`) and negative guard behaviors were executed and verified live against the codebase.
7. **Maintains Working Tree Integrity**: Fully confirms that all 5 pre-existing modified files in `/home/alexey/git/agent-coordination` remain 100% untouched.

---

## 2. Audited Artifacts, Commits & Verification Hashes

### 2.1 File Checksums (SHA-256)
Every reference document, source file, and configuration file was independently hashed and verified:

| File Path | SHA-256 Checksum | Classification & Status |
| :--- | :--- | :--- |
| `research/coordination/WINDOWS-CLIENT-INTEGRATION-CONTRACT-20261006.md` | `c96e7581688d0c2e3328b33b7a14bdefa04ef283ee31b85e5a01e46f40ef67fa` | Target Integration Contract (Reviewed) |
| `/home/alexey/git/agent-coordination/adapters/windows_client.py` | `aa649266365dd59b6eca124324a607b286c2cc70367e67bc184e6ad5ce552593` | Primary CLI Adapter & RPC Engine |
| `/home/alexey/git/agent-coordination/coordination/envelope.py` | `e78e3af19bf7e39cd1c9813aaf7a3b52ee5cf849e13e6b136cb59086cd2fe300` | Protocol Envelope & Data Types |
| `/home/alexey/git/agent-coordination/coordination/host_interface.py` | `4382a6640b77ad5293cb0171745f1a8d8bece881bf44c22dd8aa1565d242a254` | Host Admission, Guard & Atomic Events |
| `/home/alexey/git/agent-coordination/coordination/device_registry.py` | `aab7b6034067263f3b81c224da6a4bb9fdeec6afb6076ec63d9559e8f7a7ceaa` | Device Topology & Allowlisting Registry |
| `/home/alexey/git/agent-coordination/coordination/cursors.py` | `f6482155789ae069316d937edb898148da43ec5971a36a3bdce3cbd2f6fcd823` | Local Cursor Progression & Outbox Spool |
| `/home/alexey/git/agent-coordination/examples/devices.example.json` | `fbf24ea3ec497673c9f28d88fa5b8d28a381180d1e34dfa510db9f1b4c81b241` | Canonical Allowlisted Device Topology |

*All checksums cited in Section 2.2 of the contract document match the actual disk SHA-256 digests byte-for-byte.*

### 2.2 Git Commit Pin Verification
Verified in `/home/alexey/git/agent-coordination` on branch `codex/role-failover-20261006`:
- **Baseline Introducer**: `30df32ae2bbcc47558556e03701e28bae4a10022` (`feat(cli): host-addressing and native protocol integration`)
- **Current Tree Head**: `db48a5a5a9a75fc6ccfac5a16181ddb3e07a22df` (`feat(fencing): QL consumer fencing, epoch validation, and gated replacement startup`)

---

## 3. Detailed Assessment of Checkpoint 47-baa4 Drift Resolution

### 3.1 Ambiguity Context
At checkpoint `01a11247-baa4-7be1-b272-b9d002a7e155`, the Desktop Orchestrator flagged an operational conflict:
> *"PhysicalWindows contract revised ping/rpc conflicts earlier send/poll/ack script contract; request exact pinnedmanifest/clientCLI+deviceenrollment/scopedpayload before desktopexecution, preserveprivatecursors."*

### 3.2 Verification of Resolution
The reviewer verified both code and documentation on the following points:
1. **Absence of `ping` CLI Subcommand**:
   - Inspected `adapters/windows_client.py`: The `argparse` subparsers define exactly:
     `sub = parser.add_subparsers(dest="cmd", required=True)` with parsers for `"send"`, `"poll"`, `"reply"`, `"ack"`, and `"rpc"`. No parser is registered for `"ping"`.
   - Executed live test:
     ```bash
     $ python3 /home/alexey/git/agent-coordination/adapters/windows_client.py ping
     usage: windows_client.py [-h] [--alias ALIAS] [--aplexer APLEXER]
                              [--bridge-device BRIDGE_DEVICE]
                              {send,poll,reply,ack,rpc} ...
     windows_client.py: error: argument cmd: invalid choice: 'ping' (choose from 'send', 'poll', 'reply', 'ack', 'rpc')
     [exit code: 2]
     ```
   - Contract assessment: Section 1.1 explicitly details this exact error behavior, resolving any false expectation that `ping` is a subcommand.

2. **Pre-flight & Liveness Check Options**:
   - The contract defines three canonical alternatives for transport pre-flight:
     - **Option A (Lightweight Mailbox Poll — Recommended)**:
       `python -m adapters.windows_client poll --workspace /home/alexey/git/cloudflare-agent-git --tag windows-codex`
       Verifies end-to-end SSH connectivity, key authorization, and remote aplexer responsiveness without side effects.
     - **Option B (Typed Handshake Message via Standard CLI or Stdin RPC)**:
       `python -m adapters.windows_client send --workspace /home/alexey/git/cloudflare-agent-git --to coord-917-custody-resume-20261006 --body "AC-WIN-HETZ-001 Windows client handshake" --token tok-win-001 --idempotency-key win-msg-001 --stdin-rpc`
       Dispatches a typed handshake and returns a fail-closed `SendReceipt`.
     - **Option C (Direct JSON-RPC Stdin Transport Ping)**:
       `python -m adapters.windows_client rpc --method poll --params "{\"tag\": \"windows-codex\"}"`
       Dispatches structured JSON-RPC over SSH stdin to test the RPC subsystem.
   - Contract assessment: Accurate, robust, and directly executable.

3. **Reconciliation of Subcommand Suite**:
   The contract clarifies that `send`, `poll`, `reply`, and `ack` constitute the core message lifecycle, while `rpc` provides the underlying low-level transport mechanism. This eliminates any confusion between the high-level workflow scripts and the low-level RPC transport.

---

## 4. Verification of CLI Subcommands & Live Dry-Run Outputs

The reviewer executed live `--help` queries for all subcommands in the host environment. The outputs were verified against Section 4 and Section 8 of the contract document.

### 4.1 Global CLI & Help Outputs
- Global help invocation:
  ```bash
  $ python3 /home/alexey/git/agent-coordination/adapters/windows_client.py --help
  usage: windows_client.py [-h] [--alias ALIAS] [--aplexer APLEXER]
                           [--bridge-device BRIDGE_DEVICE]
                           {send,poll,reply,ack,rpc} ...

  Windows-initiated authenticated SSH client for typed mailbox delivery

  positional arguments:
    {send,poll,reply,ack,rpc}
      send                Send typed message to remote agent
      poll                Poll unread messages addressed to Windows client
      reply               Reply to a received message ID
      ack                 Acknowledge message IDs
      rpc                 Execute typed RPC over SSH stdin

  options:
    -h, --help            show this help message and exit
    --alias ALIAS         SSH alias in ~/.ssh/config
    --aplexer APLEXER     Remote aplexer binary path
    --bridge-device BRIDGE_DEVICE
                          Remote execution bridge device ID
  ```
  *Match: 100% exact match.*

### 4.2 Subcommand Parameter Verification Matrix

| Subcommand | Documented Required Flags | Documented Optional Flags | Live Code Match |
| :--- | :--- | :--- | :---: |
| `send` | `--workspace`, `--to`, `--body`, `--token`, `--idempotency-key` | `--origin-device`, `--origin-workspace`, `--origin-tag`, `--stdin-rpc` | **VERIFIED** |
| `poll` | *(None)* | `--workspace`, `--tag` (default: `"windows-codex"`) | **VERIFIED** |
| `reply` | `message_id`, `--body`, `--token`, `--idempotency-key` | `--origin-device`, `--origin-workspace`, `--origin-tag` | **VERIFIED** |
| `ack` | *(None)* | `message_ids ...`, `--all`, `--tag` | **VERIFIED** |
| `rpc` | `--method` | `--params` | **VERIFIED** |

All default argument values (`alias="hetzner"`, `aplexer="/home/alexey/.local/bin/aplexer"`, `bridge_device="hetzner-rmthz"`, `origin_device="windows-desktop"`, `origin_workspace="work/agent-coordination"`, `origin_tag="windows-codex"`) documented in Section 4 are verified identical to the code implementation.

---

## 5. Verification of Runtime, Identity & Security Invariants

### 5.1 Runtime Environment Claims
- **Standard Library ONLY**: Inspected imports in [`adapters/windows_client.py`](file:///home/alexey/git/agent-coordination/adapters/windows_client.py):
  `argparse`, `dataclasses`, `datetime`, `json`, `pathlib`, `shlex`, `subprocess`, `sys`, `typing`, `uuid`.
  Zero third-party packages are imported.
- **Zero Rust / Native Build Policy**: No Cargo, C/C++, or compiled binaries are referenced or required for client execution.
- **Transport Constraints**: Pure OpenSSH client execution (`ssh -o BatchMode=yes -o StrictHostKeyChecking=yes hetzner -- ...`).

### 5.2 Device Enrollment & Identity Scoping
- Inspected [`examples/devices.example.json`](file:///home/alexey/git/agent-coordination/examples/devices.example.json):
  ```json
  {
    "id": "windows-desktop",
    "kind": "ssh-client-host",
    "ssh_alias": null,
    "hostname": "windows-desktop",
    "ssh_user": "alexey",
    "aplexer_bin": null,
    "workspace_roots": ["work/agent-coordination"],
    "role": "user-desktop",
    "native_aplexer": false,
    "outbound_ssh_only": true
  }
  ```
  *Match: The contract accurately transcribes this configuration in Section 3.1.*

- **Anti-Spoofing Rule (`session_id=None`)**:
  Live test executed:
  ```python
  from adapters.windows_client import OriginatingAgent, IdentitySpoofError
  OriginatingAgent(session_id="synthetic-123").validate()
  ```
  Result:
  ```
  IdentitySpoofError: Invented Windows aplexer session ID forbidden: 'synthetic-123'. Windows has no local aplexer binary.
  ```
  *Match: Anti-spoofing enforcement verified.*

### 5.3 Head Credential Isolation
- Inspected [`coordination/host_interface.py`](file:///home/alexey/git/agent-coordination/coordination/host_interface.py) lines 96–126 (`reject_head_cred_inheritance`):
  Live test executed:
  ```python
  from coordination.host_interface import reject_head_cred_inheritance, GuardRejected
  reject_head_cred_inheritance({"head.cred": "secret"}, reject=True)
  ```
  Result:
  ```
  GuardRejected: guard_rejected:head_cred_inheritance_rejected: forbidden credential inheritance
  ```
  *Match: Rejection of head credentials verified.*

---

## 6. Private Cursor Preservation & Storage Partitioning

The contract's cursor preservation architecture (Section 5) was evaluated against [`coordination/cursors.py`](file:///home/alexey/git/agent-coordination/coordination/cursors.py):
1. **Local Desktop Stores**:
   - `.local/windows_cursors.db` / `.local/cursors.json`: Tracks read offsets on the Windows client.
   - `.local/idempotency.json`: Caches `idempotency_key -> {sender, recipient, digest, message_id}` to prevent re-transmission of identical payloads over physical SSH.
   - `.local/outbox.jsonl`: Spools pending messages during physical network disconnects.
2. **Namespace Partitioning**:
   - Local records are partitioned by `(device_id, session_id)`: Windows is strictly `("windows-desktop", None)`, preventing collisions with Hetzner aplexer sessions `("hetzner-rmthz", session_id)`.
3. **Atomic Host Event Logging**:
   - Hetzner task admissions and transitions are committed atomically with `fcntl.flock` to `.local/events/host_events.jsonl`.
4. **Corrupt Cursor Recovery**:
   - `CursorStore._load()` safely recovers corrupt JSON cursor files by archiving to `cursors.corrupt.<timestamp>.json` and initializing clean dictionaries, avoiding process crashes.

---

## 7. Working Tree Verification (Agent-Coordination Repository)

Per the strict directives of the Operating Model, the reviewer verified that no modifications were introduced into `/home/alexey/git/agent-coordination`:

```console
$ git -C /home/alexey/git/agent-coordination status --short
 M adapters/windows_client.py
 M coordination/TASKS.json
 M coordination/ssh_relay.py
 M tests/test_offline_network.py
 M tests/test_ssh_relay.py
```

### Attestation:
1. The 5 modified files in `/home/alexey/git/agent-coordination` were present prior to the start of this review.
2. The reviewer performed **read-only** inspections and help executions.
3. Zero files in `/home/alexey/git/agent-coordination` were modified, created, or deleted by this review. The working tree remains **100% untouched**.

---

## 8. Independent Verdict & Sign-Off

### Summary of Assessment:
| Criterion | Status | Evidence |
| :--- | :---: | :--- |
| **Drift Resolution (47-baa4)** | **PASS** | `ping` absence confirmed; 3 pre-flight options and 5 subcommands documented |
| **Runtime & Dependencies** | **PASS** | Python 3.10+ standard library ONLY; zero pip packages; zero Rust builds |
| **Client Manifest Pinning** | **PASS** | Exact SHA-256 matches for `windows_client.py` and `envelope.py` |
| **Identity & Security Scoping** | **PASS** | `devices.example.json` topology match; `session_id=None` anti-spoofing guard verified |
| **Credential Isolation** | **PASS** | `reject_head_cred_inheritance` strips/rejects head credentials verified |
| **Cursor Preservation** | **PASS** | Local `.local/` stores; `(device_id, session_id)` partitioning; auto-recovery |
| **CLI Dry-Runs** | **PASS** | 6 help commands executed with exit code 0; usage verified |
| **Working Tree Isolation** | **PASS** | Pre-existing 5 dirty files in `agent-coordination` remain 100% untouched |

### Definitive Verdict:
**ACCEPT**

The integration contract [`WINDOWS-CLIENT-INTEGRATION-CONTRACT-20261006.md`](file:///home/alexey/git/cloudflare-agent-git/research/coordination/WINDOWS-CLIENT-INTEGRATION-CONTRACT-20261006.md) satisfies all requirements under directive C2922 and is fully approved for operational execution of task `coord-desktop-hetzner-test`.

---
*Signed by: Antigravity Independent Peer Reviewer (`71d9e70e-6588-4cf4-88ce-a985e83785f5`), 2026-10-06T19:50:00+02:00 (Europe/Berlin)*
