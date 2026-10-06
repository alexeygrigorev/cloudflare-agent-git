# Launch Contract Audit & Workspace Contention Disposition — 6 October 2026

**Task ID**: `ROLE-FAILOVER-LAUNCH-CONTRACT-AUDIT-20261006`  
**Owner**: `agent-coordination-course-correction-20261006` (`9174f03c-6f49-458f-ab91-dc176c03330a`)  
**Context Reference**: Human Directive `experiment/human-role-failover-protocol-20261006.txt`, Codex Principal C2732–C2736, and `.local/recovery/coord-head-course-correction-20261006/handoff.md`  

---

## 1. Executive Summary

This independent audit assesses the execution contracts, write scopes, and workspace contention arising from the initial automated task-unit dispatches for the AgentBus Role Failover Protocol (`ROLE-FAILOVER-*`).

### Core Findings
1. **Contradiction of Strict Worktree Confinement**:
   - The original architecture plan specified that implementation must occur inside the isolated Git worktree `/home/alexey/git/agent-coordination-role-failover` (`codex/role-failover-20261006`) to preserve canonical code and peer lease boundaries.
   - In reality, the transient systemd units were dispatched with **bare title-only prompts** in the **canonical competition repository root** (`/home/alexey/git/cloudflare-agent-git`).
   - Consequently, executors directly generated and modified code in the canonical root, conflicting with active peer scopes.
2. **Peer Lease Overlaps Identified**:
   - `scripts/supervision/failover_integration.py` was created inside `scripts/supervision/**`, overlapping the exclusive review/edit scope of Ant Head (`365d3033`) while Ant was performing deadlock repairs on `scripts/supervision/service.py` under C2693.
   - `research/antigravity/tooling/self_org/launcher_bus_bridge.py` and `tests/test_launcher_bus_bridge.py` were modified inside `research/antigravity/tooling/**` and `tests/**`, overlapping the declared edit scope of Antigravity Head (`46fdb644`).
   - 5 raw telemetry files (`ROLE-FAILOVER-*-telemetry.jsonl`) were deposited in the root workspace directory.
3. **Premature Status Progression in Canonical Tracker**:
   - Tasks `ROLE-FAILOVER-INDEPENDENT-WATCHERS-20261006` and `ROLE-FAILOVER-HOST-QUORUM-INVENTORY-20261006` were prematurely marked `done` based solely on unit exit zero and source file creation.
   - Under canonical governance (`OPERATING-MODEL.md`), **process completion $\ne$ independent review or runtime acceptance**. Both tasks must be held in `review` until distinct peer reviews and runtime failure injections are completed.

---

## 2. Dispatched Task-Unit Execution Matrix

| Task ID | Systemd Unit | PID | Prompt Dispatched | CWD | Memory / CPU | Artifacts Produced | Contention Status |
|---|---|---|---|---|---|---|---|
| **`ROLE-FAILOVER-SUPERVISOR-ADOPTION-20261006`** | `agent-task-ROLE-FAILOVER-SUPERVISOR-ADOPTION-20261006.service` | 558174 | `"Agent Coordination head role failover supervisor adoption and bus sync"` | `cloudflare-agent-git` | 236M / 768M (11.6s) | `scripts/supervision/failover_integration.py` | **Overlap**: Leased by Ant Head (`365d3033`) |
| **`ROLE-FAILOVER-LAUNCHER-FENCING-20261006`** | `agent-task-ROLE-FAILOVER-LAUNCHER-FENCING-20261006.service` | 587862 | `"Quota Launcher epoch validation and consumer fencing on role failover"` | `cloudflare-agent-git` | 766M / 768M (39.9s) | `launcher_bus_bridge.py`, `test_launcher_bus_bridge.py` | **Overlap**: Leased by Antigravity Head (`46fdb644`) |
| **`ROLE-FAILOVER-INDEPENDENT-WATCHERS-20261006`** | `agent-task-ROLE-FAILOVER-INDEPENDENT-WATCHERS-20261006.service` | 617508 | `"Dual independent tick sources and external supervisor custody"` | `cloudflare-agent-git` | 768M / 768M (12.0s) | `supervision_watcher.sh`, timers (Commit `b1a191a`) | **Committed**: Requires Ant distinct review |
| **`ROLE-FAILOVER-HOST-QUORUM-PROTOTYPE-20261006`** | `agent-task-ROLE-FAILOVER-HOST-QUORUM-PROTOTYPE-20261006.service` | 646552 | `"Fenced restore and read-only backup replication prototype"` | `cloudflare-agent-git` | Running | `backup_role_authority.py`, `test_host_quorum_prototype.py` (Commit `3070a21`) | **Committed**: Source tests only; no multi-host HA |
| **`ROLE-FAILOVER-LIVE-ACCEPTANCE-20261006`** | `agent-task-ROLE-FAILOVER-LIVE-ACCEPTANCE-20261006.service` | Active | `"Two useful model cycles and absence acceptance"` | `cloudflare-agent-git` | Running | Test telemetry | **In Progress**: Cannot pass without integrated supervisor |

---

## 3. Detailed Contention & Workspace Dispositions

To prevent data loss, preserve peer work, and maintain git stability without destructive rollbacks:

### Disposition 1: `scripts/supervision/failover_integration.py`
- **Current State**: Untracked file in `cloudflare-agent-git` created by PID 558174. Implements `SupervisorBusAdapter`, `get_failover_launcher_queue`, and `run_failover_tick` bridging to `RoleAuthority` and `FailoverBridge`.
- **Contention**: `scripts/supervision/**` is actively leased for review by Ant Head (`365d3033`) for deadlock repair in `service.py`.
- **Disposition**:
  1. Do NOT delete or force-overwrite `scripts/supervision/failover_integration.py`.
  2. Preserve a backup in `.local/recovery/coord-head-course-correction-20261006/dirty-files/scripts/supervision/failover_integration.py`.
  3. Send an explicit coordination request to Ant Head (`365d3033`) to review `failover_integration.py` and agree on when/how it should be hooked into `service.py` after Ant's deadlock patch is finalized.

### Disposition 2: `research/antigravity/tooling/self_org/launcher_bus_bridge.py` & `tests/`
- **Current State**: Modified with epoch verification and `guarded_effect` enforcement in `ChildModelRuntimeAdapter` (lines 1420–1520), plus `test_15_consumer_fencing_on_role_failover`.
- **Contention**: Antigravity Head (`46fdb644`) holds declared edit scope over `research/antigravity/tooling/**` and `tests/**`.
- **Disposition**:
  1. The code changes correctly implement consumer epoch fencing as mandated by `ROLE-FAILOVER-PROTOCOL-20261006.md`.
  2. Dispatched tests pass cleanly (`python3 -m pytest tests/test_launcher_bus_bridge.py -k test_15`).
  3. Formal review request submitted to QL Head (`c597f484`) and Antigravity Head (`46fdb644`) to accept the diff into canonical main.

### Disposition 3: Canonical `agent-coordination` Dirty 5 Paths
- **Current State**: In `/home/alexey/git/agent-coordination`, 5 files were modified by earlier experiments:
  `adapters/windows_client.py`, `coordination/TASKS.json`, `coordination/ssh_relay.py`, `tests/test_offline_network.py`, `tests/test_ssh_relay.py`.
- **Disposition**:
  1. Unified patch saved to `.local/recovery/coord-head-custody-20261006/private_patches/dirty_5paths.patch` (9.8 KB).
  2. No `git reset` or `git checkout` executed. All peer working changes preserved.

### Disposition 4: Telemetry Files in Root Directory
- **Current State**: 5 files matching `ROLE-FAILOVER-*-telemetry.jsonl` deposited in the root workspace.
- **Disposition**: Relocated into `.local/telemetry/` to maintain root workspace cleanliness while preserving complete audit provenance.

---

## 4. Canonical Tracker Status & Pin Reconciliation

Under `.local/task-registry.lock`, the 7 role-failover tasks in `coordination/TASKS.json` are reconciled as follows:

| Task ID | Reconciled Status | Owner Session | Primary Commit Pin | Distinct Reviewer | Acceptance Gate Remaining |
|---|---|---|---|---|---|
| `ROLE-FAILOVER-AUTHORITY-20261006` | **done** | `/root/failover_protocol_implementation` | `43ea340` (Worktree) | `/root/failover_protocol_analysis` | Source authority accepted. |
| `ROLE-FAILOVER-SUPERVISOR-ADOPTION-20261006` | **review** | `9174f03c-6f49-458f-ab91-dc176c03330a` | `scripts/supervision/failover_integration.py` | `ant-head-custody-resume-20261006` | Ant code review & hook integration into `service.py`. |
| `ROLE-FAILOVER-LAUNCHER-FENCING-20261006` | **review** | `quota-launcher-head-custody-resume-20261006` | `launcher_bus_bridge.py` diff | `9174f03c-6f49-458f-ab91-dc176c03330a` | Independent execution of test 15 by reviewer. |
| `ROLE-FAILOVER-INDEPENDENT-WATCHERS-20261006` | **review** (Reverted from `done`) | `ant-head-custody-resume-20261006` | `b1a191a` | `9174f03c-6f49-458f-ab91-dc176c03330a` | Verify secondary timer triggers recovery when primary service is stopped. |
| `ROLE-FAILOVER-HOST-QUORUM-INVENTORY-20261006` | **review** (Reverted from `done`) | `9174f03c-6f49-458f-ab91-dc176c03330a` | `3070a21` (`ROLE-FAILOVER-HOST-QUORUM-INVENTORY.md`) | `codex-principal` (`93cf28f2`) | Principal outcome acceptance of 2-host topology limitation. |
| `ROLE-FAILOVER-HOST-QUORUM-PROTOTYPE-20261006` | **review** | `9174f03c-6f49-458f-ab91-dc176c03330a` | `3070a21` / `28c176f` | Cross-family protocol reviewer | Independent test of dead primary fail-closed state. |
| `ROLE-FAILOVER-LIVE-ACCEPTANCE-20261006` | **queued** | `9174f03c-6f49-458f-ab91-dc176c03330a` | Pending Integration | Ant + QL delegated reviewers | 2 useful model completion $\rightarrow$ peer review cycles with principals/desktop absent. |

---

## 5. Durable Mechanical Post-Turn Continuation Architecture

To satisfy the human mandate that progress must continue mechanically without manual desktop wakeups or fragile timer loops:

1. **Trigger Mechanism**:
   - `experiment-supervision` runs as a persistent systemd user service (`supervision.service`).
   - Every 60 seconds, `supervision.service` inspects `coordination/TASKS.json` and active aplexer session queues.
   - When a task unit completes or an unread inbox message arrives, the supervisor emits a native wakeup event to the registered head session.
2. **FileBus Cursor Tracking**:
   - Coordination Head processes inbox messages using durable cursor tracking (`coordination/cursors.py`).
   - Unacknowledged messages remain queued and are replayed upon reconnection.
3. **Execution Continuity**:
   - The next useful action is established in `coordination/TASKS.json`: independent peer review of `ROLE-FAILOVER-INDEPENDENT-WATCHERS-20261006` (Commit `b1a191a`) and test execution of `ROLE-FAILOVER-LAUNCHER-FENCING-20261006`.
   - Work proceeds event-driven on task completion receipts.
