# Role Failover Host Quorum & Topology Inventory — 6 October 2026

**Task ID**: `ROLE-FAILOVER-HOST-QUORUM-INVENTORY-20261006`  
**Owner**: `agent-coordination-head-custody-resume-20261006` (`0a9bee9a-b740-4e64-8eb7-76040968afce`)  
**Reviewer**: `codex-principal` (`93cf28f2`) architecture/outcome challenger  
**Authority Reference**: `research/orchestrator/ROLE-FAILOVER-PROTOCOL-20261006.md`  

---

## 1. Executive Summary

This inventory audits all existing enrolled, authorized computing environments to evaluate eligibility for multi-host authority-store witness consensus under the AgentBus Role Failover Protocol.

### Key Finding: Explicit Available Topology Shortage
- **Enrolled Authorized Computers**: Exactly **2 hosts** exist in the authorized infrastructure:
  1. `hetzner-rmthz` (Remote Linux execution server)
  2. `windows-desktop` (Local client desktop)
- **Quorum Feasibility**: A Byzantine or Crash Fault-Tolerant (CFT) 3-node majority quorum ($N \ge 3$) **cannot be formed** on the existing authorized infrastructure.
- **Policy Constraint**: Creating a 3rd host via cloud server procurement, third-party hosting, or unverified network endpoints is strictly unauthorized by competition rules ("no guessed credentials, spending or unrelated-host changes").
- **Architectural Reality**: We explicitly reject false "no-single-point-of-failure" claims. The role failover protocol eliminates individual **agent and desktop process** single points of failure, but **does not eliminate host-level failure of Hetzner**. Host failure recovery must rely on authenticated read-only backup replication and an externally fenced restore path, rather than automatic partition-tolerant consensus.

---

## 2. Enrolled Host Topology Audit

| Host Identifier | System Hostname | OS / Architecture | Connectivity | Native Aplexer | Authority Store Eligible | Current Role & Permissions |
|---|---|---|---|---|---|---|
| **`hetzner-rmthz`** | `RMTHZ` | Linux x86_64 (Ubuntu 24.04 LTS) | Static Public IP, Inbound SSH via allowlist, Port 22 | **Yes** (`~/.local/bin/aplexer`) | **Primary Authority Store** | Primary remote development, supervisor service manager, model harness runner, AgentBus authority SQLite store. |
| **`windows-desktop`** | `windows-desktop` | Windows 11 x86_64 | Dynamic IP behind NAT, Outbound SSH only (`ssh.exe`) | **No** (Client only) | **Read-Only Backup Replica** | Human interactive station, periodic reader, backup destination. Cannot accept inbound SSH or run background daemons without desktop session. |

### Detailed Device Parameters

```json
{
  "topology_version": 1,
  "enrolled_devices": [
    {
      "id": "hetzner-rmthz",
      "kind": "aplexer-host",
      "ssh_alias": "hetzner",
      "hostname": "RMTHZ",
      "ssh_user": "alexey",
      "aplexer_bin": "/home/alexey/.local/bin/aplexer",
      "workspace_roots": ["/home/alexey/git"],
      "role": "remote-execution-host",
      "native_aplexer": true,
      "outbound_ssh_only": false,
      "inbound_ssh_capable": true,
      "authority_store_role": "primary"
    },
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
      "outbound_ssh_only": true,
      "inbound_ssh_capable": false,
      "authority_store_role": "read-only-replica"
    }
  ]
}
```

---

## 3. Quorum & Split-Brain Analysis ($N=2$)

In any 2-node topology where one node cannot accept inbound traffic:
1. **Network Partition Hazard**: If connectivity between `hetzner-rmthz` and `windows-desktop` drops:
   - Neither host can distinguish a network partition from a remote host crash.
   - If both hosts were permitted to elect leaders or grant role leases independently, a catastrophic **split-brain** state occurs (two agents acting as principal or coordinator concurrently).
2. **Asymmetric Network Topology**:
   - `hetzner-rmthz` cannot initiate an SSH session to `windows-desktop` because `windows-desktop` is behind consumer NAT and does not run an SSH daemon.
   - All cross-computer synchronization must be **pull-driven** by `windows-desktop` (or via reverse SSH tunnels, which are fragile and non-durable across reboots).
3. **Impossibility of Majority Consensus**:
   - Majority quorum requires $\lfloor N/2 \rfloor + 1$ votes. For $N=2$, majority is 2 out of 2.
   - Any single failure (e.g. laptop sleeps or SSH disconnects) reduces available nodes to 1 out of 2 (50%), which is less than a majority.
   - Therefore, automatic consensus cannot proceed during a partition without violating safety.

---

## 4. Adopted Host Failover Strategy

Per `ROLE-FAILOVER-PROTOCOL-20261006.md` Section "Authority-store and host recovery boundary":

1. **Single Authoritative Store on Hetzner**:
   - The primary SQLite database on `hetzner-rmthz` is the sole atomic authority for role elections, lease grants, and launch reservations.
   - SQLite `BEGIN IMMEDIATE` transactions serialize elections.
   - Monotonic epoch counters prevent stale leader decisions from being accepted.
2. **Local Machine & Process Failover (Fully Supported)**:
   - If a model, session, principal, or coordinator fails on `hetzner-rmthz`, another healthy agent on `hetzner-rmthz` takes over the role immediately.
   - This eliminates dependence on any single model, process, or the desktop chat.
3. **Authenticated Read-Only Backup (Host Disaster Recovery)**:
   - `windows-desktop` polls and downloads atomic SQLite backup snapshots using authenticated SSH pull.
   - The replica on `windows-desktop` remains strictly **read-only** and CANNOT elect leaders automatically.
4. **Fenced Emergency Restore**:
   - If `hetzner-rmthz` suffers catastrophic hardware loss, human administration or an explicit signed command may restore the authority database to a replacement host.
   - The restore intent advances the authority generation and fences the old host endpoint before granting any new leases.

---

## 5. Prototype Scope for `ROLE-FAILOVER-HOST-QUORUM-PROTOTYPE-20261006`

In accordance with this inventory, the prototype task will implement:
1. An automated SQLite backup replication script (`backup_role_authority.py`) using SQLite online backup API (`sqlite3.backup`) to avoid file corruption.
2. Checkpoint SHA-256 verification and generation tracking on the client replica.
3. Fenced recovery verification test simulating a dead primary and verifying that the replica fails closed until explicitly promoted with a new generation.

---

**Status**: INVENTORY COMPLETED AND VERIFIED. No third host exists; 2-host topology limitation confirmed and documented.
