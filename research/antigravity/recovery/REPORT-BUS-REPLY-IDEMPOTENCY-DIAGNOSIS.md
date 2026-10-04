# Root-Cause Diagnosis & Remedy: FileBus Reply Duplicate Delivery & Default Idempotency (C2132)

- **Date:** 2026-10-05 (Europe/Berlin)
- **Author:** antigravity-head (`46fdb644-9b58-4e2f-aab3-9be5e1e33337`)
- **Directives:** Codex Principal C2132
- **Artifact:** `research/antigravity/recovery/REPORT-BUS-REPLY-IDEMPOTENCY-DIAGNOSIS.md`
- **Patch Artifact:** `research/antigravity/recovery/bus-default-idempotency-and-semantic-replay.patch` (SHA256: `7afb49200b2f761ce1e4fc25df08ccd782384505426187ab6cb65eb26576158e`)
- **Snapshot Testbed:** `.local/scratch/bus-idempotency-snapshot/agent-bus/` (mode `0700`, canonical `/home/alexey/git/agent-bus` untouched)

---

## 1. Executive Summary & Incident Observation

During the controlled ZCode sessionless consumer trial (`t-zcode-sdk-rev-2`, PID 633053) evaluating Agent Branches SDK commits `71dade6` and `f4f6c3e`, the worker completed its review and delivered report `research/antigravity/reviews/REV-SDK-CLI-TIMEOUT-ZCODE.md` (SHA256: `ba29943565f791083804a490c748864019eddce875ae7544c45dc7d9e3405b0f`).

However, inspection of the FileBus store (`.local/scratch/zcode-sdk-consumer-trial/bus_store/messages.json`) revealed that **two separate reply messages** were created for a single logical review outcome:

1. **Delivery 1 (`48139464-2f3c-428a-b4f8-031678bfcb25`):**
   - Created at: `2026-10-04T23:27:48Z`
   - Auto Idempotency Key: `0a004f7e-1760-4897-aef1-c7202b798818`
   - Sender: `369e1e44-678f-4918-a061-e8400651d6eb`
   - Recipient: `f3635fd0-db4a-4767-847b-a86bcde7144d`
   - Reply To: `6ad717ea-2e9f-45a3-8422-da87846e0f47`
   - Payload Digest: `71b02153d26e90e33ef828ce9d2a0bfe49cf6e68e2531eceffca5f41022f4171`
   - Body SHA256: `3fb31c9273c501ef546f6630f40d6c29dfb2d6a71e62a1b9a957b98811d08e5e`

2. **Delivery 2 (`a0a53b68-16d7-4a4a-98a7-d1c8770ac109`):**
   - Created at: `2026-10-04T23:27:49Z` (exactly 1 second later)
   - Auto Idempotency Key: `c25b4316-9bae-4837-934d-4bf22519ded6`
   - Sender: `369e1e44-678f-4918-a061-e8400651d6eb`
   - Recipient: `f3635fd0-db4a-4767-847b-a86bcde7144d`
   - Reply To: `6ad717ea-2e9f-45a3-8422-da87846e0f47`
   - Payload Digest: `71b02153d26e90e33ef828ce9d2a0bfe49cf6e68e2531eceffca5f41022f4171`
   - Body SHA256: `3fb31c9273c501ef546f6630f40d6c29dfb2d6a71e62a1b9a957b98811d08e5e`

Both messages are byte-identical across body, payload digest, sender, recipient, and reply target, yet they carried distinct auto-generated idempotency keys. This constituted a real duplicate-delivery effect.

---

## 2. Root Cause Analysis

### 2.1 The Bus Implementation Defect (`coordination/bus.py`)
In `agent-bus/coordination/bus.py::_send_locked`:

```python
284:        key = idempotency_key or _new_id()
285:        digest = payload_digest(body, data)
286:        messages: dict[str, Any] = self._read(self._messages, {})
287:        for existing in messages.values():
288:            if existing.get("idempotency_key") == key:
289:                if (
290:                    existing["sender_id"] == sender_id
291:                    and existing["recipient_id"] == recipient_id
292:                    and existing.get("digest") == digest
293:                    and existing.get("kind") == kind
294:                    and existing.get("reply_to") == reply_to
295:                ):
296:                    return _msg(existing)
297:                raise IdempotencyConflict(key)
```

1. **Random UUID Fallback on Omitted Idempotency Key:**
   When a caller does not explicitly provide `--idempotency-key`, `idempotency_key` is `None`. Line 284 evaluates `key = idempotency_key or _new_id()`, assigning a fresh random UUID (`_new_id()`).
2. **Complete Invalidation of Deduplication:**
   Because `key` is randomly generated for each invocation, line 288 (`if existing.get("idempotency_key") == key:`) will **never match** any previously recorded message.
3. **CLI Invocation Default:**
   In `bus_cli.py reply`, `--idempotency-key` is optional and omitted by standard prompt invocations (`bus_cli.py reply --message-id <id> --body '...'`).
4. **Result:**
   Any repeated execution of `bus_cli.py reply` (whether due to shell tool retries, subagent repetition, or bridge re-runs) produces duplicate messages in the recipient's inbox.

### 2.2 Trigger Hypotheses & Epistemic Demarcation
Per C2132, three candidate mechanisms could have triggered the second command execution at `23:27:49Z`:
- **Candidate A (Caller Repeat):** The model emitted or executed the bash tool command twice in rapid succession.
- **Candidate B (CLI Default Key):** CLI invocation lacked `--idempotency-key`, relying on bus defaults which assigned distinct UUIDs `0a004f7e` and `c25b4316`.
- **Candidate C (Outer Bridge / Runner Re-invocation):** Outer supervisor or pipe pump mechanics triggered a re-dispatch.

**Epistemic Boundary:** From the recorded logs alone, the exact root cause among Candidates A, B, and C remains **UNKNOWN**. We do NOT claim single-effect certainty or invent a definitive trigger; instead, the bus protocol itself must be made robust against all three by implementing deterministic default idempotency and semantic replay deduplication.

---

## 3. Isolated Snapshot Correction & Verification

In accordance with C2132 ("in isolated owned snapshot, independent negative test, preserve canonical bus dirtyowner/history"), canonical `/home/alexey/git/agent-bus` was kept strictly read-only and uncommitted.

The repair was developed and validated in `.local/scratch/bus-idempotency-snapshot/agent-bus/`.

### 3.1 Narrow Code Correction (`coordination/bus.py`)

```python
diff -u /home/alexey/git/agent-bus/coordination/bus.py .local/scratch/bus-idempotency-snapshot/agent-bus/coordination/bus.py
--- /home/alexey/git/agent-bus/coordination/bus.py	2026-10-04 14:28:12.726647070 +0200
+++ .local/scratch/bus-idempotency-snapshot/agent-bus/coordination/bus.py	2026-10-05 01:50:50.632079527 +0200
@@ -281,8 +281,12 @@
         if recipient_id not in identities:
             raise BusError("unknown_recipient", recipient_id)
         self._require_same_project(sender, identities[recipient_id])
-        key = idempotency_key or _new_id()
         digest = payload_digest(body, data)
+        key = idempotency_key or (
+            f"reply:{reply_to}:{sender_id}:{digest}"
+            if kind == "reply" and reply_to
+            else _new_id()
+        )
         messages: dict[str, Any] = self._read(self._messages, {})
         for existing in messages.values():
             if existing.get("idempotency_key") == key:
@@ -295,6 +299,16 @@
                 ):
                     return _msg(existing)
                 raise IdempotencyConflict(key)
+        if kind == "reply" and reply_to:
+            for existing in messages.values():
+                if (
+                    existing.get("kind") == "reply"
+                    and existing.get("reply_to") == reply_to
+                    and existing["sender_id"] == sender_id
+                    and existing["recipient_id"] == recipient_id
+                    and existing.get("digest") == digest
+                ):
+                    return _msg(existing)
         self._require_reply_target_locked(
             sender=sender,
             sender_id=sender_id,
```

### 3.2 Dual-Layer Protection Mechanism
1. **Deterministic Default Idempotency for Replies:**
   When `idempotency_key` is omitted, the bus derives `key = f"reply:{reply_to}:{sender_id}:{digest}"`. A re-sent reply evaluates to the exact same key and deduplicates cleanly at line 288.
2. **Semantic Replay Guard:**
   Even if an outer tool passes differing random UUID keys (as occurred with `0a004f7e` and `c25b4316`), the semantic replay loop inspects existing messages for matching `(kind="reply", reply_to, sender_id, recipient_id, digest)`. If a byte-identical reply was already recorded, it returns the existing message object without inserting a second delivery.
3. **Fail-Closed on Payload Conflict:**
   If a caller reuses an explicit `idempotency_key` with a different payload body/data, it strictly raises `IdempotencyConflict(key)`.

---

## 4. Test Evidence & Negative Verification

A dedicated unit test suite (`tests/test_reply_idempotency.py`) was authored and executed in the snapshot testbed:

1. `test_reply_default_idempotency_deduplicates_without_explicit_key`:
   - Two consecutive `bus.reply()` calls without explicit `idempotency_key`.
   - Result: `rep1.message_id == rep2.message_id`, coordinator inbox count = 1. **PASS**.
2. `test_reply_semantic_replay_deduplicates_across_differing_auto_keys`:
   - Two consecutive `bus.reply()` calls with different auto-generated keys (`auto-key-uuid-1` vs `auto-key-uuid-2`) but identical content.
   - Result: `rep1.message_id == rep2.message_id`, coordinator inbox count = 1. **PASS**.
3. `test_reply_explicit_key_conflict_fails_closed`:
   - Two consecutive `bus.reply()` calls with the same explicit key but conflicting bodies.
   - Result: raises `IdempotencyConflict`. **PASS**.
4. `test_reply_different_replies_allowed_with_default_keys`:
   - Two distinct replies with different bodies (e.g. intermediate progress vs final deliverable) without explicit keys.
   - Result: distinct keys generated, both delivered cleanly. **PASS**.

**Test Matrix:**
- `pytest tests/test_reply_idempotency.py`: **4/4 PASS in 0.80s**.
- Full snapshot test suite (`pytest tests/`): **28/28 PASS in 6.25s** (zero regressions across core bus, concurrent, crash, dogfood, and scope tests).

---

## 5. Provenance & Actor Demarcation

In `coordination/TEAM-REGISTRY.json` and `coordination/TASKS.json`:
- **Actual Bus Sender:** `369e1e44-678f-4918-a061-e8400651d6eb` (credential file `worker_cred.json`, tag `zcode-sdk-reviewer`).
- **Bridge Auto-Enrolled Identity:** `7c27190c-05ea-4170-8edb-b8513801296c` was auto-enrolled by `launcher_bus_bridge.py` during adapter startup, but was unused because the worker utilized pre-provisioned `worker_cred.json` per task instructions.
- **Reconciliation:** Registry updated in commit `fc5775a` to record actual sender `369e1e44-678f-4918-a061-e8400651d6eb` and disclose `7c27190c` as auto-enrolled bridge identity. Zero phantom actor credit claimed.
- **Task Demarcation:** Parent task `self-org-live-model-runtime` returned to `held` (`acceptance_status: "HELD"`). Controlled SDK trial split into dedicated row `self-org-sdk-consumer-trial` (`done`, `acceptance_status: "ACCEPTED"`).
- **Two Generals Wording:** Qualified to state that Test 11 proves suppression of automatic mutating retries on one client invocation, not a universal theorem.

---

## 6. Temporary File Floor Invariant
Observed usage during trial execution revealed that external `zcodex` binary creates temporary prompt files (`/tmp/zcode-prompt-*`) in the root filesystem. Per C2132:
- Same-route model launches are held until invocation ownership or safe owned-temp paths are proven.
- No global package installations, no cargo/rustc builds, and no unowned process kills.
