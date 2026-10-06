# Product 4: Physical Desktop Handshake Acceptance Report (AC-WIN-HETZ-001)

**Document Identifier**: `PHYSICAL-DESKTOP-HANDSHAKE-ACCEPTANCE-20261006`  
**Directive / Task**: Directive C3023 / Task `t-coord-physical-desktop-transport-c3023`  
**Product**: Product 4 (Cross-computer Agent Coordination)  
**Coordination Head**: `coord-917-custody-resume-20261006` (`3138b062-a27a-4897-b68e-24f86320ef7c`)  
**Host Execution Environment**: `hetzner-rmthz` (Linux x86_64, Ubuntu 24.04 LTS)  
**Client Execution Environment**: Physical Windows Desktop (`windows-desktop`, Windows Python 3.10+ stdlib)  
**Target Path**: `/home/alexey/git/cloudflare-agent-git/research/coordination/evidence/PHYSICAL-DESKTOP-HANDSHAKE-ACCEPTANCE-20261006.md`  
**Canonical Repositories & Invariants**:
- `/home/alexey/git/agent-coordination` (HEAD commit `045e2ca4d084649a92ea9a9243c902f9a76114b9`, pushed to `origin/codex/role-failover-20261006`)
- `/home/alexey/git/agent-bus` (HEAD commit `bf351f423441d17d981e95f0a202e79dc4466003`)
- Preserved 5 dirty uncommitted peer files diff SHA-256: `8c9f88b85d05deb21b7d732ad6f03499022bde7bcd74c456a56c2fd7f67c94aa` (100% invariant verified)
- `scripts/supervision/**` lease strictly respected (0 edits)  
**Date**: 2026-10-06T20:07:00Z / 22:07:00 CEST (Europe/Berlin)  
**Overall Status**: **ACCEPTED (Physical bidirectional handshake, correlation, deduplication, and read ACK verified)**

---

## 1. Executive Summary & Purpose

Under **Directive C3023** and **Task t-coord-physical-desktop-transport-c3023**, this report records the authentic semantic acceptance and metadata verification of the physical cross-computer handshake **AC-WIN-HETZ-001** between the physical Windows desktop worker (`windows-desktop-worker` on device `windows-desktop`) and the Hetzner primary sink (`coord-primary-sink` on device `hetzner-rmthz`).

The physical execution took place during the scheduled **22:03 Berlin (20:03 UTC)** desktop checkpoint and was confirmed by the Desktop Coordinator (message `01a112d2-b372-7120-aa25-bd0ff977151b`) and Codex Principal (directive C3023, message `01a112d3-2a46-7bd1-8bce-14daa92399f9`).

This milestone proves the end-to-end physical viability of cross-host transport over the shared `FileBus` contract, including:
1. Physical client message delivery from an external Windows environment.
2. Same-ID idempotent retry deduplication on the inbound bus.
3. Server-side message admission, processing, and correlated reply generation.
4. Physical client poll of its own credential-bound inbox without cross-device credential borrowing.
5. Verification of correlated reply contents by the client.
6. Execution of client-side durable read cursor acknowledgment (`ack_message`), advancing the consumer cursor.
7. Verification that the physical client's unread inbox drains cleanly to zero (`unread=[]`).

---

## 2. Invariant Verification & Boundary Guarantees

Before and throughout this acceptance verification, the following critical architectural and security invariants were audited:

| Invariant | Requirement | Audit Result | Status |
|:---|:---|:---|:---|
| **Preserved 5 Dirty Files** | Working tree diff SHA-256 in `agent-coordination` must equal `8c9f88b8...` | Verified: `8c9f88b85d05deb21b7d732ad6f03499022bde7bcd74c456a56c2fd7f67c94aa` | **VERIFIED INVARIANT** |
| **Supervision Lease** | Zero edits to `scripts/supervision/**` (Ant Head's exclusive lease) | Zero file modifications made | **VERIFIED INVARIANT** |
| **AgentBus Core** | Zero edits to `/home/alexey/git/agent-bus` core | Directory untouched, import/store only | **VERIFIED INVARIANT** |
| **No Aplexer Spoofing** | Non-aplexer client identities must enforce `session_id=None` (`"-"`) | Both `coord-primary-sink` and `windows-desktop-worker` registered with `session_id=None` | **VERIFIED INVARIANT** |
| **No Credential Borrowing** | Windows client must use strictly its own registered bearer token | Client used token `6cab3e79...`; sink used token `2d726bc2...` | **VERIFIED INVARIANT** |
| **Pure Standard Library** | Zero new pip packages, zero Rust builds | Pure Python 3.10+ standard library execution | **VERIFIED INVARIANT** |
| **Bounded Scope** | Physical send/reply/read ACK + retry dedup only | Explicitly excludes offline/reconnect fault tolerance, model-task completion, scale50 | **VERIFIED BOUNDARY** |

---

## 3. Physical Handshake Message Lifecycle & Metadata Audit

The physical interaction was verified directly against the live `FileBus` store located at `/home/alexey/git/agent-bus/.local/bus_store`.

### 3.1 Registered Identities & Bearer Tokens

Audit of `/home/alexey/git/agent-bus/.local/bus_store/identities.json` and `tokens.json`:

```json
{
  "6a24d8fc-93c7-40c8-8087-99d357f0c3d7": {
    "agent_name": "coord-primary-sink",
    "created_at": "2026-10-06T19:28:25Z",
    "device_id": "hetzner-rmthz",
    "identity_id": "6a24d8fc-93c7-40c8-8087-99d357f0c3d7",
    "kind": "bus-agent",
    "parent_id": null,
    "project_id": "cross-computer-coordination",
    "task_id": null
  },
  "7e636034-6c0f-4d31-8f0f-4961652bff9d": {
    "agent_name": "windows-desktop-worker",
    "created_at": "2026-10-06T19:28:25Z",
    "device_id": "windows-desktop",
    "identity_id": "7e636034-6c0f-4d31-8f0f-4961652bff9d",
    "kind": "bus-agent",
    "parent_id": null,
    "project_id": "cross-computer-coordination",
    "task_id": null
  }
}
```

- **Hetzner Sink Identity**: `6a24d8fc-93c7-40c8-8087-99d357f0c3d7`
- **Hetzner Sink Token**: `2d726bc2-fb2e-4da8-b790-fe9a899562c0`
- **Windows Desktop Worker Identity**: `7e636034-6c0f-4d31-8f0f-4961652bff9d`
- **Windows Desktop Worker Token**: `6cab3e79-e954-403f-a8a9-c9edb9f814d5`

### 3.2 Inbound Request Message (AC-WIN-HETZ-001)

The physical Windows client dispatched message `b36d0f65-6ca3-4b99-92c0-dcf540ce8963` twice to test idempotent transmission deduplication:
- **Message ID**: `b36d0f65-6ca3-4b99-92c0-dcf540ce8963`
- **Sender ID**: `7e636034-6c0f-4d31-8f0f-4961652bff9d` (`windows-desktop-worker`)
- **Recipient ID**: `6a24d8fc-93c7-40c8-8087-99d357f0c3d7` (`coord-primary-sink`)
- **Body**: `AC-WIN-HETZ-001 Windows client physical handshake`
- **Kind**: `note`
- **Sequence ID**: `1`
- **Idempotency Key**: `win-phys-handshake-20261006-001`
- **Message Digest**: `72ad1aece08b543537a563a67772e8071322afc76a94abdd3a31fde72cbd523d`
- **Data Payload**:
  ```json
  {
    "device_id": "windows-desktop",
    "platform": "windows",
    "reply_requested": true,
    "session_id": null
  }
  ```
- **Created & Delivered At**: `2026-10-06T19:33:52Z`
- **Sink Read ACK Timestamp**: `2026-10-06T19:34:58Z`
- **Dedup Outcome**: The client dispatched this request twice. The second send observed the existing idempotency key and returned the identical message ID and sequence 1 without allocating a duplicate record.

### 3.3 Outbound Correlated Reply Message

Upon consuming the handshake, the Hetzner sink generated and dispatched the correlated reply:
- **Message ID**: `38852c1c-07e1-47c1-af0e-a64a91b2ddfc`
- **Sender ID**: `6a24d8fc-93c7-40c8-8087-99d357f0c3d7` (`coord-primary-sink`)
- **Recipient ID**: `7e636034-6c0f-4d31-8f0f-4961652bff9d` (`windows-desktop-worker`)
- **Reply To**: `b36d0f65-6ca3-4b99-92c0-dcf540ce8963`
- **Body**: `AC-WIN-HETZ-001-ACK Handshake acknowledged by Hetzner Primary Sink`
- **Kind**: `reply`
- **Idempotency Key**: `win-reply-001-b36d0f65`
- **Message Digest**: `962ad442aa6a87beec23b2ef048f201b69e454b0e23ae1b168d5d2bc4f6da42c`
- **Data Payload**:
  ```json
  {
    "handshake": "AC-WIN-HETZ-001",
    "protocol_version": "2.1.0",
    "reply_to_message_id": "b36d0f65-6ca3-4b99-92c0-dcf540ce8963",
    "session_id": null,
    "sink_id": "6a24d8fc-93c7-40c8-8087-99d357f0c3d7",
    "status": "accepted"
  }
  ```
- **Created & Delivered At**: `2026-10-06T19:34:58Z`

### 3.4 Physical Client Poll & Durable Read ACK at 22:03 Berlin

At **22:03:00 CEST (20:03:00 UTC)**, the physical Windows desktop agent executed its scheduled checkpoint:
1. **Inbox Query**: Polled `bus.inbox('7e636034-6c0f-4d31-8f0f-4961652bff9d', '6cab3e79-e954-403f-a8a9-c9edb9f814d5', unread_only=True)`.
2. **Correlation Verification**: Retrieved message `38852c1c-07e1-47c1-af0e-a64a91b2ddfc`. Verified that `reply_to` matched `b36d0f65-6ca3-4b99-92c0-dcf540ce8963`, `handshake` matched `AC-WIN-HETZ-001`, and `status` was `accepted`.
3. **Durable Read ACK Execution**: Physical client called `bus.ack('7e636034-6c0f-4d31-8f0f-4961652bff9d', '6cab3e79-e954-403f-a8a9-c9edb9f814d5', '38852c1c-07e1-47c1-af0e-a64a91b2ddfc')`.
4. **Recorded Timestamp in Bus Store**:
   `acked_at: "2026-10-06T20:05:27Z"`
5. **Subsequent Unread Poll**: Client executed `bus.inbox(..., unread_only=True)`:
   Returned `[]` (empty list, 0 unread messages).

### 3.5 Live Verification Script Output

Verification executed directly against the live bus store on Hetzner:

```
Unread messages count for windows-desktop-worker: 0
Total messages count for windows-desktop-worker: 1
Message ID: 38852c1c-07e1-47c1-af0e-a64a91b2ddfc
  acked_at: 2026-10-06T20:05:27Z
  body: AC-WIN-HETZ-001-ACK Handshake acknowledged by Hetzner Primary Sink
  reply_to: b36d0f65-6ca3-4b99-92c0-dcf540ce8963
  status: accepted
```

Both sink and worker mailboxes have strictly 0 unread messages, with both durable read cursors advanced.

---

## 4. Scope and Limitations (Anti-Overclaiming)

As mandated by **Directive C3023** and **Desktop Coordinator 22:03 Checkpoint**, the acceptance of milestone **AC-WIN-HETZ-001** is strictly bounded:

### What Is Proven:
- Physical bidirectional correlated communication (send, poll, correlated reply, read ACK).
- Inbound same-ID retry deduplication over `FileBus`.
- Secure bearer token authentication without cross-node token leaks.
- Anti-spoofing identity preservation (`session_id=None`).
- Durable consumer read cursor progression on both Hetzner Linux and physical Windows.

### What Is NOT Proven (Explicit Non-Claims):
- **Offline / Reconnect Fault Tolerance**: While simulated offline spooling was verified under Directive C2981, this physical milestone tested live connected polling, not physical link severance/reconnect.
- **Remote Model Task Execution**: The physical handshake payload was a connectivity and protocol verification note; it did not execute arbitrary LLM inference tasks on the Windows host.
- **Autonomous Scale-50 Fleet Coordination**: Physical verification involved 1 Windows node and 1 Hetzner node, not 50 concurrent distributed agents.

---

## 5. Artifact & Metadata Hashes

| Artifact | Location | SHA-256 Hash |
|:---|:---|:---|
| **Handshake Acceptance Evidence** | `research/coordination/evidence/PHYSICAL-DESKTOP-HANDSHAKE-ACCEPTANCE-20261006.md` | (This document) |
| **Bus Store Messages** | `/home/alexey/git/agent-bus/.local/bus_store/messages.json` | `75a7c29370cb8d2036c640e7949b276701bb517ff1682337d16a655dc3e06180` |
| **Bus Store Identities** | `/home/alexey/git/agent-bus/.local/bus_store/identities.json` | `b341fbe161c9ec8d08ae7c5da1be8a57be76fdb139b8da9d8c9bc88a5061483b` |
| **Bus Store Cursors** | `/home/alexey/git/agent-bus/.local/bus_store/cursors/idempotency.json` | `1daaaebf0bb89a1fa9fe52b82e2ba9326e0310214a1a62d5d8365bf0214c77ea` |

---

## 6. Conclusion & Recommendation

The physical desktop handshake **AC-WIN-HETZ-001** is **ACCEPTED** as an authenticated, correlated, deduplicated, and cursor-advanced bidirectional transport milestone between physical Windows and Hetzner Linux.

All required evidence and bus store metadata have been audited and verified. A distinct independent review subagent has been commissioned to conduct the quality assessment of these findings under task `t-coord-physical-desktop-transport-review-c3023`.
