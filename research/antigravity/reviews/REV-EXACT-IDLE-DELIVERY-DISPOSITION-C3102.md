# Independent Technical Review: Exact Idle Delivery Disposition & 2-Stage Notification Architecture (Directive C3102)

**Date & Time**: 2026-10-07T00:20:00Z (2026-10-07 02:20:00 Berlin)  
**Task ID**: `t-supervision-exact-idle-delivery-c3102`  
**Directives**: Directive C3102 (Supervisor Delivery Mechanism vs Idle Wake Clarification)  
**Auditor / Independent Reviewer**: Antigravity Independent Review Delegate  
**Reviewer Conversation ID**: `c92df45e-47de-490f-9d71-ccbfa93c11cb`  
**Parent Caller ID**: `ea14b401-20e9-4e48-ab08-d15be08da30d`  
**Head Session ID**: `ant-head-readiness-custody-20261007` [session `3b522ddb-8dc8-41b4-a382-f76baab33b0a`]  
**Target Receipt Under Audit**: [`RECEIPT-EXACT-IDLE-DELIVERY-DISPOSITION-C3102.md`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/recovery/RECEIPT-EXACT-IDLE-DELIVERY-DISPOSITION-C3102.md)  
**Target Supervisor Receipt**: [`.local/supervision/receipt-46c5f719023fc8cac531-ant-head-readiness-custody-20261007.json`](file:///home/alexey/git/cloudflare-agent-git/.local/supervision/receipt-46c5f719023fc8cac531-ant-head-readiness-custody-20261007.json)  
**Target Status File**: [`.local/supervision/status.json`](file:///home/alexey/git/cloudflare-agent-git/.local/supervision/status.json)  
**Target Codebase**: [`service.py`](file:///home/alexey/git/cloudflare-agent-git/scripts/supervision/service.py#L1119-L1188) (lines 1119–1188, 1548–1558, 1784–1795) and [`ack_reconciliation.py`](file:///home/alexey/git/cloudflare-agent-git/scripts/supervision/ack_reconciliation.py#L24-L64)  

---

## 1. Executive Summary & Verdict

Under Directive C3102 and following the rigorous operational inquiries raised by Codex Principal, an independent technical audit and code QA was conducted on the exact delivery disposition of supervisor notification envelope `01a113aa-3715-71c2-af6f-839e65d39d90` and the 2-stage notification architecture implemented in [`service.py`](file:///home/alexey/git/cloudflare-agent-git/scripts/supervision/service.py).

### Core Audit Determinations:
1. **Formal Retraction of Broad Supervisor Idle Wake Verified**:
   The empirical evidence on disk demonstrates unequivocally that envelope `01a113aa-3715` was deposited strictly as an inbox message (`"delivery": "inbox"`) and **never underwent Stage 2 PTY prompt injection** (`"delivery": "submitted"`). The characterization of this event as an "automated supervisor idle wake" was technically inaccurate and has been formally and truthfully retracted in [`RECEIPT-EXACT-IDLE-DELIVERY-DISPOSITION-C3102.md`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/recovery/RECEIPT-EXACT-IDLE-DELIVERY-DISPOSITION-C3102.md).
2. **Preemption by Consumer Read-ACK Confirmed**:
   The Ant head resumed execution autonomously via its native timer callback at `00:03:47.355780 UTC`, inspected its inbox via aplexer commands, and acknowledged the message. The supervisor observed the native consumer cursor on disk (`cursor_sha256: 86d3b320b0bb2216bec98540e91547e67a1f72c31a8153896f8306440d3ac31b`), generated [`native-ack-01a113aa-3715-71c2-af6f-839e65d39d90.json`](file:///home/alexey/git/cloudflare-agent-git/.local/supervision/native-ack-01a113aa-3715-71c2-af6f-839e65d39d90.json), and cleared `pending` to `None`. This preemption completely bypassed Stage 2 delivery (`aplexer message deliver`) before any PTY injection could occur.
3. **Preservation of Authentic Product Deliverables**:
   The formal retraction of the idle wake claim does not invalidate the verified product achievements:
   - The production Agent Branches isolated CLI sync for Directive C3098 (commit `df8117e5d07134f4d3a354440f9399ee648aef80`, landed to `main` at `7f3e300`), independently verified in [`REV-BRANCHES-DOGFOOD-SYNC-C3098.md`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/reviews/REV-BRANCHES-DOGFOOD-SYNC-C3098.md), is authentic, verified, and preserved.
   - The native consumer read-ACK at `00:03:47 UTC` is genuine and backed by cryptographic cursor hashes.
4. **Draft and Busy Protections Active and Enforcing**:
   Live inspection of [`.local/supervision/status.json`](file:///home/alexey/git/cloudflare-agent-git/.local/supervision/status.json) verifies that draft and busy protections are actively operating:
   - Head `coord-917-custody-resume-20261006` exhibits `composer: "menu-or-draft"`, correctly causing pending envelope `01a113aa-37a3` to be held in `blocked_beyond_slo` without prompt disruption.
   - Principal `codex-principal` exhibits `composer: "busy"` (`reported_state: "working"`), strictly suppressing prompt injection.
5. **Code Architecture & Test Suite Health**:
   All 113 supervision tests and 14 delivery tests pass cleanly (`Ran 113 tests in 7.331s, OK`; `Ran 14 tests in 0.058s, OK`).

### Final Unconstrained Verdict: **ACCEPTED**
The disposition receipt [`RECEIPT-EXACT-IDLE-DELIVERY-DISPOSITION-C3102.md`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/recovery/RECEIPT-EXACT-IDLE-DELIVERY-DISPOSITION-C3102.md) accurately, rigorously, and truthfully reconciles empirical disk evidence with codebase mechanics. All safety invariants and operational boundaries remain intact.

---

## 2. Independent Audit Matrix

| # | Audit Item | Verification Requirement | Empirical Observation & Proof | Verdict |
|---|---|---|---|:---:|
| **1** | **Supervisor Receipt Delivery Mode** | Envelope `01a113aa-3715` delivery is `"inbox"` | In `receipt-46c5f719...json`, `"delivery": "inbox"`. Created at `1791331284` (2026-10-07T00:01:24.841101 UTC). | **PASS** |
| **2** | **Supervisor Status Roster State** | Status records `last_request.delivery == 'inbox'`, valid ACK timestamp, cursor SHA, and `pending == None` | In `status.json` under `heads['ant-head-readiness-custody-20261007']`, `delivery: "inbox"`, `acknowledged_at: "2026-10-07T00:03:47.355780+00:00"`, `source: "native-exact-consumer-cursor"`, `cursor_sha256: "86d3b320..."`, `pending: null`. | **PASS** |
| **3** | **Absence of Stage 2 Prompt Submission** | Zero evidence of PTY injection or `"delivery": "submitted"` | Zero `delivery-01a113aa-3715*.json` files exist. Zero `head-delivery-attempt` events recorded in `events.jsonl`. | **PASS** |
| **4** | **Stage 1 Implementation Logic** | [`recorded_send()`](file:///home/alexey/git/cloudflare-agent-git/scripts/supervision/service.py#L1119-L1143) performs inbox deposit only | `recorded_send()` invokes `[binary, 'message', 'send', '--to', tag, '--json']`, saving receipt with `"delivery": "inbox"` without terminal interaction. | **PASS** |
| **5** | **Stage 2 Gatekeeper & Conditions** | [`may_deliver()`](file:///home/alexey/git/cloudflare-agent-git/scripts/supervision/service.py#L1145-L1188) and delivery loop enforce safety gates | Lines 1784–1795 require `may_deliver() == True`, `count >= 2` empty snapshots, cooldown expiry, and fresh screen check `composer == 'empty'`. | **PASS** |
| **6** | **Consumer Read-ACK Preemption** | Consumer ACK clears `pending` before Stage 2 fires | Lines 1703–1710 execute `exact_ack()`, persist `native-ack-*.json`, emit event, and set `pending = None`, causing line 1784 to evaluate `False`. | **PASS** |
| **7** | **Formal Retraction Verification** | Broad supervisor idle wake claim explicitly retracted | Section 1 of `RECEIPT-EXACT-IDLE-DELIVERY-DISPOSITION-C3102.md` formally retracts the idle wake claim with full root-cause clarity. | **PASS** |
| **8** | **Preservation of Dogfood Sync** | Verified production sync commits df8117e5 / 7f3e300 preserved | Commit `df8117e5` on remote and landed commit `7f3e300` on `main` verified intact along with `REV-BRANCHES-DOGFOOD-SYNC-C3098.md`. | **PASS** |
| **9** | **Active Draft Protection Check** | Screens with `menu-or-draft` strictly suppress delivery | `coord-917-custody-resume-20261006` exhibits `composer: "menu-or-draft"`, `status: "blocked_beyond_slo"`, blocking pending message `01a113aa-37a3`. | **PASS** |
| **10** | **Active Busy Protection Check** | Screens with `busy` strictly suppress delivery | `codex-principal` exhibits `composer: "busy"`, `reported_state: "working"`, suppressing prompt injection. | **PASS** |
| **11** | **Supervision Regression Test Suite** | All unit/regression tests in `scripts/supervision` pass | `python3 -m unittest discover -s scripts/supervision` ran 113 tests in 7.331s: 100% OK. | **PASS** |
| **12** | **Delivery Regression Test Suite** | All unit/regression tests in `scripts/delivery` pass | `python3 -m unittest discover -s scripts/delivery` ran 14 tests in 0.058s: 100% OK. | **PASS** |

---

## 3. Empirical Evidence Audit & Reconciliation

### 3.1 Supervisor Receipt Audit
File inspected: [`.local/supervision/receipt-46c5f719023fc8cac531-ant-head-readiness-custody-20261007.json`](file:///home/alexey/git/cloudflare-agent-git/.local/supervision/receipt-46c5f719023fc8cac531-ant-head-readiness-custody-20261007.json)
```json
{
  "schema_version": 1,
  "id": "01a113aa-3715-71c2-af6f-839e65d39d90",
  "workspace": "/home/alexey/git/cloudflare-agent-git",
  "created_at": 1791331284,
  "from": {
    "session_id": "7bff6e1d-5a78-47b7-8a03-00361800cafd",
    "workspace": "/home/alexey/git/cloudflare-agent-git",
    "tag": "experiment-supervision",
    "engine": "shell"
  },
  "to": {
    "tag": "ant-head-readiness-custody-20261007",
    "session_id": "3b522ddb-8dc8-41b4-a382-f76baab33b0a"
  },
  "kind": "note",
  "body": "SUPERVISION-46c5f719023fc8cac531: Head ant-head-readiness-custody-20261007 has 1 ready tasks awaiting dispatch: BRANCHES-OWNED-PATH-REMOTE-SYNC-INTAKE-C2786-20261006. Inspect queues, launch executors, verify first tool output. Update TASKS.json.",
  "delivery": "inbox",
  "idempotency_key": "46c5f719023fc8cac531-ant-head-readiness-custody-20261007"
}
```
**Verification**:
- `created_at`: Unix timestamp `1791331284` corresponds to `2026-10-07T00:01:24 UTC` (specifically `00:01:24.841101+00:00` in service logs).
- `delivery`: `"inbox"` explicitly denotes Stage 1 mailbox deposit only.

### 3.2 Supervisor Status Roster Audit
File inspected: [`.local/supervision/status.json`](file:///home/alexey/git/cloudflare-agent-git/.local/supervision/status.json) under `heads["ant-head-readiness-custody-20261007"]`:
```json
{
  "event_key": "92109657315ec66b7273",
  "ready_snapshot_count": 1,
  "session_id": "3b522ddb-8dc8-41b4-a382-f76baab33b0a",
  "reported_state": "idle",
  "alive": true,
  "composer": "empty",
  "reason": "idle-empty",
  "idle_since": 1791332141.9377568,
  "unexplained_idle_over_slo": false,
  "ready_task_count": 1,
  "episode": 0,
  "last_request": {
    "id": "01a113aa-3715-71c2-af6f-839e65d39d90",
    "sender_id": "7bff6e1d-5a78-47b7-8a03-00361800cafd",
    "sender_tag": "experiment-supervision",
    "recipient_session_id": "3b522ddb-8dc8-41b4-a382-f76baab33b0a",
    "recipient_tag": "ant-head-readiness-custody-20261007",
    "workspace": "/home/alexey/git/cloudflare-agent-git",
    "event": "46c5f719023fc8cac531",
    "delivery": "inbox",
    "created_at": "2026-10-07T00:01:24.841101+00:00",
    "acknowledged_at": "2026-10-07T00:03:47.355780+00:00",
    "ack_evidence": {
      "message_id": "01a113aa-3715-71c2-af6f-839e65d39d90",
      "original_sender_id": "7bff6e1d-5a78-47b7-8a03-00361800cafd",
      "recipient_id": "3b522ddb-8dc8-41b4-a382-f76baab33b0a",
      "source": "native-exact-consumer-cursor",
      "envelope_sha256": "3218a5b6780bab5d51f3d548ad08c83010dcdb138a29891c40e6b3ba26c41e31",
      "cursor_sha256": "86d3b320b0bb2216bec98540e91547e67a1f72c31a8153896f8306440d3ac31b",
      "mailbox_key": "ff8f632ef4db3dc1682bad50bcdc8aaf",
      "read_only": true
    }
  },
  "ready_task_ids": [
    "BRANCHES-OWNED-PATH-REMOTE-SYNC-INTAKE-C2786-20261006"
  ],
  "ready_fingerprint": "b21b85c911df4bb2f9f4",
  "ready_delta": false,
  "sent_event": "46c5f719023fc8cac531",
  "last_notified_ready_fingerprint": "b21b85c911df4bb2f9f4",
  "last_notified_ready_ids": [
    "BRANCHES-OWNED-PATH-REMOTE-SYNC-INTAKE-C2786-20261006"
  ],
  "cooldown_until": 0,
  "ready_deduped": true,
  "status": "ok",
  "pending": null
}
```

### 3.3 Negative Proof of Stage 2 PTY Prompt Injection
1. **Absence of Delivery Artifact**:
   In [`service.py`](file:///home/alexey/git/cloudflare-agent-git/scripts/supervision/service.py#L1796), when Stage 2 delivery executes, it executes `atomic(PRIVATE / f"delivery-{pending['id']}.json", outcome)`.
   Directory inspection of `.local/supervision/` reveals **no** `delivery-01a113aa-3715*` artifact exists. Only [`.local/supervision/native-ack-01a113aa-3715-71c2-af6f-839e65d39d90.json`](file:///home/alexey/git/cloudflare-agent-git/.local/supervision/native-ack-01a113aa-3715-71c2-af6f-839e65d39d90.json) is present.
2. **Event Stream Log Corroboration**:
   In [`.local/supervision/events.jsonl`](file:///home/alexey/git/cloudflare-agent-git/.local/supervision/events.jsonl):
   - At `2026-10-07T00:01:24.883841+00:00`: event `head-request-recorded` logged for `01a113aa-3715`.
   - At `2026-10-07T00:03:47.408179+00:00`: event `pending-reconciled-native-ack` logged with cursor SHA `86d3b320...`.
   - **Zero** `head-delivery-attempt` events exist in the entirety of `events.jsonl`.
3. **Conclusion**:
   Stage 2 prompt delivery (`aplexer message deliver`) never occurred. The recipient agent resumed via its native schedule/timer, read the inbox, and acknowledged the message.

---

## 4. Code Architecture & 2-Stage Pipeline Verification

### 4.1 Stage 1: Mailbox Placement via `recorded_send()`
In [`service.py`](file:///home/alexey/git/cloudflare-agent-git/scripts/supervision/service.py#L1119-L1142):
```python
def recorded_send(binary, tag, key, body, spool, sender_id, supports_key, call=command):
    receiptpath = spool / f'receipt-{key}.json'
    intentpath = spool / f'intent-{key}.json'
    if receiptpath.exists():
        return json.loads(receiptpath.read_text())
    ...
    atomic(intentpath, {'sender_id':sender_id, 'to':tag, 'event_key':key, 'created_at':now(), 'state':'send-may-have-started'})
    args = [binary, 'message', 'send', '--to', tag, '--json']
    if supports_key:
        args += ['--idempotency-key', key]
    ...
    receipt = json.loads(call(args + [body]))
    atomic(receiptpath, receipt)
    return receipt
```
- Operates out-of-band by invoking the aplexer CLI to deposit an envelope into the recipient mailbox.
- Guarantees crash idempotency via prewritten intent files.
- Delivery status returned is always `"delivery": "inbox"`.

### 4.2 Stage 2: Guarded PTY Delivery via `may_deliver()` and Head Delivery Loop
In [`service.py`](file:///home/alexey/git/cloudflare-agent-git/scripts/supervision/service.py#L1784-L1795):
```python
if may_deliver(pending, identity['id'], spool=PRIVATE) and count >= 2 and time.time() >= item.get('cooldown_until', 0):
    fresh_screen = command(['aplexer', 'capture', session['id'], '--screen', '--plain'])
    if composer(fresh_screen, head_tag) == 'empty':
        deliver_args = [BINARY, 'message', 'deliver', pending['id'], '--workspace', str(ROOT), '--json']
        result = subprocess.run(deliver_args, capture_output=True, text=True, timeout=20)
        ...
        outcome = json.loads(result.stdout)
        atomic(PRIVATE / f"delivery-{pending['id']}.json", outcome)
        status = outcome.get('status', outcome.get('delivery', 'delivery-uncertain'))
        pending['delivery'] = status
        event('head-delivery-attempt', head=head_tag, message_id=pending['id'], outcome=status)
```
- Stage 2 prompt injection is strictly conditioned on:
  1. `may_deliver(pending, ...)` returning `True`.
  2. `count >= 2` consecutive cycles of confirmed idle/empty composer.
  3. `time.time() >= cooldown_until`.
  4. An immediate third screen capture confirming `composer(fresh_screen, head_tag) == 'empty'`.

### 4.3 Preemption by Consumer Native Read-ACK
In [`service.py`](file:///home/alexey/git/cloudflare-agent-git/scripts/supervision/service.py#L1703-L1710):
```python
if pending:
    evidence = exact_ack(pending, session['id'], head_tag, ROOT)
    if evidence:
        item['last_request'] = {**pending, 'acknowledged_at': now(), 'ack_evidence': evidence}
        atomic(PRIVATE / ('native-ack-' + pending['id'] + '.json'), evidence)
        event('pending-reconciled-native-ack', head=head_tag, **evidence)
        report['actions'].append({'kind': 'pending-reconciled-native-ack', 'head': head_tag, 'message_id': pending['id']})
        pending = None
```
- Executed on each tick **before** the Stage 2 delivery block.
- Calls `exact_ack(...)` from [`ack_reconciliation.py`](file:///home/alexey/git/cloudflare-agent-git/scripts/supervision/ack_reconciliation.py#L24-L64), which inspects the native aplexer mailbox lock, envelope, and recipient cursor exceptions under a read-only shared lock (`LOCK_SH | LOCK_NB`).
- Once the recipient consumes the envelope, `pending` is set to `None`.
- On line 1784, `may_deliver(None, ...)` returns `False`. Stage 2 is skipped entirely.

---

## 5. Safety Invariants & Operational Protections

### 5.1 Active Draft Protection Check
Inspected in [`.local/supervision/status.json`](file:///home/alexey/git/cloudflare-agent-git/.local/supervision/status.json) under `heads["coord-917-custody-resume-20261006"]`:
- `composer`: `"menu-or-draft"`
- `status`: `"blocked_beyond_slo"`
- `blocking_reason`: `"recipient composer has an unsubmitted draft or menu (menu-or-draft)"`
- `pending.id`: `"01a113aa-37a3-7291-8bc6-158026b52fd5"`
- `pending.delivery`: `"inbox"`
- **Finding**: Despite exceeding SLO (`pending_duration_seconds: 998.05` vs `retry_slo_seconds: 300`), the supervisor **refuses** to deliver the prompt because the recipient screen has an active draft. Fail-closed draft protection is actively functioning.

### 5.2 Active Busy Protection Check
Inspected in [`.local/supervision/status.json`](file:///home/alexey/git/cloudflare-agent-git/.local/supervision/status.json) under `principals["codex-principal"]`:
- `composer`: `"busy"`
- `reported_state`: `"working"`
- `alive`: `true`
- **Finding**: While Codex Principal is actively executing, the supervisor recognizes the busy terminal state and does not attempt PTY prompt submission.

### 5.3 Verified Production Dogfood Sync Integrity
- Commit `df8117e5d07134f4d3a354440f9399ee648aef80` (`origin/recovery/metrics-and-supervision-c3098`)
- Parent: `563a007b6ca731b592e79c8385c4005a049108bb`
- Landed to `main`: `7f3e300b` (`HEAD -> main, origin/main`)
- Deliverable Integrity: 100% verified across all 7 paths by independent reviewer `043c65f0` in [`REV-BRANCHES-DOGFOOD-SYNC-C3098.md`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/reviews/REV-BRANCHES-DOGFOOD-SYNC-C3098.md).

---

## 6. Regression Testing Summary

| Test Suite | Command | Tests Run | Results | Time |
|---|---|:---:|:---:|:---:|
| Supervision Test Suite | `python3 -m unittest discover -s scripts/supervision` | 113 | **PASS** (113/113) | 7.331s |
| Delivery Test Suite | `python3 -m unittest discover -s scripts/delivery` | 14 | **PASS** (14/14) | 0.058s |

Both test suites executed with 0 failures and 0 errors, validating that ACK reconciliation, retention hooks, supervisor status tracking, and delivery guards are robust and fully functional.

---

## 7. Review Conclusion & Unconstrained Verdict

The audit target [`RECEIPT-EXACT-IDLE-DELIVERY-DISPOSITION-C3102.md`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/recovery/RECEIPT-EXACT-IDLE-DELIVERY-DISPOSITION-C3102.md) meets all criteria of rigorous technical reporting:
1. It accurately records the empirical reality that supervisor message `01a113aa-3715` was an inbox delivery and not an automated PTY idle wake.
2. It correctly articulates the 2-stage notification architecture and the preemption mechanism by consumer read-ACK.
3. It preserves verified product achievements (Agent Branches dogfood sync) without conflating them with unverified idle wake mechanisms.
4. It confirms active enforcement of draft and busy guards.

**Final Verdict**: **ACCEPTED**
