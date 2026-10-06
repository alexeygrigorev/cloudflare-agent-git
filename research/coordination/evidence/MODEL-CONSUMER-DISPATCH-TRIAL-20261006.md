# Product 4: Real Model Consumer Dispatch Trial Report

**Document Reference**: `MODEL-CONSUMER-DISPATCH-TRIAL-20261006`  
**Directive Reference**: Directives C3024 & C3026  
**Task Reference**: Task `t-coord-model-consumer-dispatch-c3024`  
**Product**: Product 4 (Cross-computer Agent Coordination)  
**Coordination Head**: `coord-917-custody-resume-20261006` (`3138b062-a27a-4897-b68e-24f86320ef7c`)  
**Workspace**: `/home/alexey/git/cloudflare-agent-git`  
**Execution Environment**: Linux x86_64, Ubuntu 24.04 LTS (`hetzner-rmthz`), Python 3.12.3  
**Date**: 2026-10-06T20:25:00Z / 22:25:00 CEST (Europe/Berlin)  
**Overall Verdict**: **PASS (All invariants satisfied, neutral USE/DEFER decisions enforced, useful deliverable produced, zero cursor corruption)**

---

## 1. Executive Summary & Purpose

Under **Directives C3024 & C3026**, this report documents the authentic execution of the real cross-host task coordination consumer trial using the reviewed CLI-once `SinkDispatcher` architecture over `FileBus`.

In accordance with Codex Principal guidance, this trial establishes:
1. **Neutral USE vs. DEFER/REJECT Decisions**:
   - Inbound tasks from enrolled, authorized nodes (`windows-desktop`) containing compliant parameters are evaluated with a **USE** decision, admitted, and executed to produce concrete deliverables.
   - Inbound tasks attempting to leak forbidden supervisor credentials (`head.cred`) or originating from unregistered rogue nodes are evaluated with a **DEFER_REJECT** decision, emitting auditable events and returning structured error replies without stalling the consumer queue (poison-pill containment).
2. **Captured Useful Deliverable**:
   - The consumer executed `generate_contract_validator`, producing a machine-verifiable JSON deliverable artifact (`artifacts/task-coord-consumer-001.json`) with cryptographic SHA-256 digest `8bf37a7ba336fa679dcb3758fa1849fbaea6e63b157f19f5e1954584bdc70ec7`.
3. **Audit Trail Durability**:
   - All admission decisions and fail-closed rejections were recorded atomically in `host_events.jsonl`.
4. **Complete Cursor Isolation**:
   - Dedicated sentinel mailbox (`unrelated-worker-gamma`) remained strictly invariant at 1 unread message throughout high-throughput dispatch.
   - Sink and caller inboxes drained cleanly to zero unread messages.

---

## 2. Invariant Verification & Boundary Guarantees

| Invariant | Requirement | Verified Value / Status |
|:---|:---|:---|
| **Preserved 5 Dirty Files** | Working tree diff SHA-256 in `agent-coordination` must equal `8c9f88b8...` | `8c9f88b85d05deb21b7d732ad6f03499022bde7bcd74c456a56c2fd7f67c94aa` (**EXACT MATCH**) |
| **Supervision Lease** | Zero edits to `scripts/supervision/**` (Ant Head's exclusive lease) | Untouched (0 modifications) |
| **AgentBus Core** | Zero edits to `/home/alexey/git/agent-bus` core | Untouched (0 modifications) |
| **No Aplexer Spoofing** | Non-aplexer client identities must enforce `session_id=None` (`"-"`) | All 4 enrolled entities strictly enforce `session_id=None` |
| **No In-Memory Secret Leaks** | Credential files written atomically with mode `0600` | Verified mode `0600` on all credential files |
| **Pure Standard Library** | Zero new pip packages, zero Rust builds | Pure Python 3.10+ stdlib + FileBus |

---

## 3. Enrolled Identities in Isolated Store

All identities were enrolled into `/home/alexey/git/cloudflare-agent-git/.local/tmp/model_consumer_dispatch/bus_store` using `agent_bus_client.enroll_agent()`:

| Role | Agent Name | Device ID | Session ID | Identity ID |
|:---|:---|:---|:---|:---|
| **Primary Sink** | `coord-primary-sink` | `hetzner-rmthz` | `None` (`null`) | `771ad4c6-ce13-4ae3-9d90-e59c23565e38` |
| **Windows Worker** | `windows-worker-beta` | `windows-desktop` | `None` (`null`) | `b6bcfd13-a0a3-4b14-86e2-b25ee3669ab2` |
| **Unauthorized Rogue** | `unauthorized-caller-99` | `unregistered-rogue-01` | `None` (`null`) | `ab6075d9-b808-417b-b697-5dbba4649686` |
| **Unrelated Sentinel** | `unrelated-worker-gamma` | `windows-desktop` | `None` (`null`) | `2467b629-9e8c-4a3d-9d41-36aa39a7372f` |

---

## 4. Message Dispatch Execution & Neutral Decisions

Three messages were dispatched by callers to test both branches of the neutral evaluation logic:

### Message 1: Useful Task (`task-coord-consumer-001`) — Neutral Decision: USE
- **Sender**: `windows-worker-beta` (`windows-desktop`)
- **Action**: `generate_contract_validator`
- **Contract Rules**: `["reject_head_cred_inheritance", "session_id_none", "durable_read_ack", "fail_closed_unknown_device"]`
- **Evaluation**: `MultiHostAdmission` validated `windows-desktop` against `DeviceRegistry`. `reject_head_cred_inheritance` verified payload cleanliness.
- **Decision**: **`USE`** (`status: admitted`).
- **Execution & Output Artifact**:
  - Computed and wrote validator configuration to `.local/tmp/model_consumer_dispatch/artifacts/task-coord-consumer-001.json`.
  - Artifact SHA-256 Digest: `8bf37a7ba336fa679dcb3758fa1849fbaea6e63b157f19f5e1954584bdc70ec7`.
- **Correlated Reply**: Dispatched reply `TASK-COMPLETED:task-coord-consumer-001` containing result artifact path and SHA-256 digest.
- **Cursor Advance**: Inbound message ACKed (`ack_message`).

```json
{
  "action": "generate_contract_validator",
  "decision": "USE",
  "execution_target": "hetzner-rmthz",
  "rules_verified": [
    "reject_head_cred_inheritance",
    "session_id_none",
    "durable_read_ack",
    "fail_closed_unknown_device"
  ],
  "task_id": "task-coord-consumer-001",
  "validator_status": "enforced"
}
```

### Message 2: Leaked Credential (`task-leak-002`) — Neutral Decision: DEFER_REJECT
- **Sender**: `windows-worker-beta` (`windows-desktop`)
- **Payload**: Injected forbidden `head.cred` leak into message body.
- **Evaluation**: `SinkDispatcher` pre-admission check invoked `reject_head_cred_inheritance({"body": body}, reject=True)`.
- **Outcome**: Raised `GuardRejected("guard_rejected:head_cred_inheritance_rejected: forbidden head credential inheritance in payload")`.
- **Decision**: **`DEFER_REJECT`** (`status: rejected`).
- **Event Recorded**: `guard_rejected` emitted to `host_events.jsonl` (Event ID: `5a3859fe-1a87-48de-b1ae-345603c6dea2`).
- **Correlated Reply**: Sent error reply `TASK-REJECTED:task-leak-002` detailing guard violation.
- **Poison-Pill Prevention**: Inbound message ACKed to prevent queue blocking.

### Message 3: Rogue Device (`task-rogue-003`) — Neutral Decision: DEFER_REJECT
- **Sender**: `unauthorized-caller-99` (`unregistered-rogue-01`)
- **Evaluation**: `MultiHostAdmission` queried `DeviceRegistry` for `unregistered-rogue-01`.
- **Outcome**: Raised `UnknownDevice("unknown_device:unregistered-rogue-01")`.
- **Decision**: **`DEFER_REJECT`** (`status: rejected`).
- **Event Recorded**: `admission_rejected` emitted to `host_events.jsonl` (Event ID: `14a4e701-1934-4d12-bff7-fbd47b2a0db8`).
- **Correlated Reply**: Sent error reply `TASK-REJECTED:task-rogue-003`.
- **Poison-Pill Prevention**: Inbound message ACKed.

---

## 5. Audit Log Evidence (`host_events.jsonl`)

Verbatim log records from `.local/tmp/model_consumer_dispatch/events/host_events.jsonl`:

```json
{"details": {"delivery": "sessionless_worker_bus", "device_id": "windows-desktop", "execution_target": "hetzner-rmthz", "message_id": "89c94f48-a628-47cd-bcf1-9c9f0c4c69e1", "sender_id": "b6bcfd13-a0a3-4b14-86e2-b25ee3669ab2", "session_id": null, "task_id": "task-coord-consumer-001"}, "device_id": "windows-desktop", "event_id": "0bcdd6d9-6f4d-4d70-900d-a4ca28bfec28", "event_type": "task_admitted", "recorded_at": "2026-10-06T20:22:03Z", "task_id": "task-coord-consumer-001", "timestamp": "2026-10-06T20:22:03Z"}
{"details": {"error_type": "GuardRejected", "message_id": "cfb4a9e8-438b-48f1-aa21-68eeae3310ed", "reason": "guard_rejected:head_cred_inheritance_rejected: forbidden head credential inheritance in payload", "sender_id": "b6bcfd13-a0a3-4b14-86e2-b25ee3669ab2"}, "device_id": "windows-desktop", "event_id": "5a3859fe-1a87-48de-b1ae-345603c6dea2", "event_type": "guard_rejected", "recorded_at": "2026-10-06T20:22:03Z", "task_id": "task-leak-002", "timestamp": "2026-10-06T20:22:03Z"}
{"details": {"error_type": "UnknownDevice", "message_id": "6fb80d9e-29b1-4e93-86d3-167cd4bc435f", "reason": "unknown_device:unregistered-rogue-01", "sender_id": "ab6075d9-b808-417b-b697-5dbba4649686"}, "device_id": "unregistered-rogue-01", "event_id": "14a4e701-1934-4d12-bff7-fbd47b2a0db8", "event_type": "admission_rejected", "recorded_at": "2026-10-06T20:22:03Z", "task_id": "task-rogue-003", "timestamp": "2026-10-06T20:22:03Z"}
```

---

## 6. Cursor State & Isolation Proof

1. **Sink Inbox**: Polled unread messages returned strictly `0` (cursor advanced).
2. **Caller Inbox**: Received all correlated replies, verified result artifact and rejection reasons, issued ACKs -> unread messages returned strictly `0`.
3. **Unrelated Worker Sentinel**:
   - Seed message `seed-unrelated-001` unread count before dispatch: **1**.
   - Unread count after entire multi-message dispatch and reply lifecycle: **1** (100% invariant, zero cursor bleed).

---

## 7. Cryptographic Manifest

| Artifact | Location | SHA-256 Digest |
|:---|:---|:---|
| **Evidence Document** | `research/coordination/evidence/MODEL-CONSUMER-DISPATCH-TRIAL-20261006.md` | (This document) |
| **Trial Runner Script** | `.local/tmp/model_consumer_dispatch/trial.py` | `0ea7fb8e15c328e35cfd37e6f6629910d6a2fbe61d67f4c5462cfcb8480373e1` |
| **Output Deliverable** | `.local/tmp/model_consumer_dispatch/artifacts/task-coord-consumer-001.json` | `8bf37a7ba336fa679dcb3758fa1849fbaea6e63b157f19f5e1954584bdc70ec7` |
| **Audit Events Log** | `.local/tmp/model_consumer_dispatch/events/host_events.jsonl` | `5c4a5c92c4e207fe7c26fa3296c095c5573426eeb556281bb7daef7f4fa11dc9` |

---

## 8. Conclusion

Task `t-coord-model-consumer-dispatch-c3024` has been successfully executed, demonstrating authentic model consumer task admission, execution, artifact creation, fail-closed deferral/rejection, event auditing, and complete cursor isolation under Directives C3024 & C3026.
