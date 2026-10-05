# Root-Cause Diagnosis & Remedy: FileBus Reply Duplicate Delivery & Default Idempotency (C2132 / C2133 / C2135)

- **Date:** 2026-10-05 (Europe/Berlin)
- **Author:** antigravity-head (`46fdb644-9b58-4e2f-aab3-9be5e1e33337`)
- **Directives:** Codex Principal C2132, C2133, C2134, C2135, C2136
- **Artifact:** `research/antigravity/recovery/REPORT-BUS-REPLY-IDEMPOTENCY-DIAGNOSIS.md`
- **Patch Artifact:** `research/antigravity/recovery/bus-default-idempotency-and-semantic-replay.patch` (SHA256: `6494985fb62f3a7a3f86b69dccd73f299ab15ec7598f370ac83ec92521568cab`)
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
   - Body SHA256: `3fb31c92bb2aa686919f60c3215a3be828a02aec17385ad7c331b242e901ee92`

2. **Delivery 2 (`a0a53b68-16d7-4a4a-98a7-d1c8770ac109`):**
   - Created at: `2026-10-04T23:27:49Z` (exactly 1 second later)
   - Auto Idempotency Key: `c25b4316-9bae-4837-934d-4bf22519ded6`
   - Sender: `369e1e44-678f-4918-a061-e8400651d6eb`
   - Recipient: `f3635fd0-db4a-4767-847b-a86bcde7144d`
   - Reply To: `6ad717ea-2e9f-45a3-8422-da87846e0f47`
   - Payload Digest: `71b02153d26e90e33ef828ce9d2a0bfe49cf6e68e2531eceffca5f41022f4171`
   - Body SHA256: `3fb31c92bb2aa686919f60c3215a3be828a02aec17385ad7c331b242e901ee92`

Both messages are byte-identical across body, payload digest, sender, recipient, and reply target, yet they carried distinct auto-generated idempotency keys. This constituted a real duplicate-delivery effect.

*(Note on Body SHA256: The body contains Unicode em-dash `\u2014` in "push_batch \u2014 no time.sleep", yielding exact UTF-8 byte SHA256 `3fb31c92bb2aa686919f60c3215a3be828a02aec17385ad7c331b242e901ee92`, correcting earlier draft transcription.)*

---

## 2. Root Cause Analysis

### 2.1 The Bus Implementation Defect (`coordination/bus.py`)
In canonical `agent-bus/coordination/bus.py::_send_locked`:

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

**Epistemic Boundary:** From the recorded logs alone, the exact root cause among Candidates A, B, and C remains **UNKNOWN**. We do NOT claim single-effect certainty or invent a definitive trigger; instead, the bus protocol itself must be made robust against all three by implementing deterministic default idempotency, alias persistence, and semantic replay deduplication.

---

## 3. Isolated Snapshot Correction & Verification (C2133 / C2135)

In accordance with C2132 ("in isolated owned snapshot, independent negative test, preserve canonical bus dirtyowner/history"), canonical `/home/alexey/git/agent-bus` was kept strictly read-only and uncommitted.

The repair was developed and validated in `.local/scratch/bus-idempotency-snapshot/agent-bus/`.

### 3.1 Pinned Patch (`coordination/bus.py`)

```python
--- /home/alexey/git/agent-bus/coordination/bus.py	2026-10-04 14:28:12.726647070 +0200
+++ .local/scratch/bus-idempotency-snapshot/agent-bus/coordination/bus.py	2026-10-05 02:02:05.013197595 +0200
@@ -281,11 +281,24 @@
         if recipient_id not in identities:
             raise BusError("unknown_recipient", recipient_id)
         self._require_same_project(sender, identities[recipient_id])
-        key = idempotency_key or _new_id()
-        digest = payload_digest(body, data)
         messages: dict[str, Any] = self._read(self._messages, {})
+        self._require_reply_target_locked(
+            sender=sender,
+            sender_id=sender_id,
+            identities=identities,
+            messages=messages,
+            kind=kind,
+            reply_to=reply_to,
+        )
+        digest = payload_digest(body, data)
+        key = idempotency_key or (
+            f"reply:{reply_to}:{sender_id}:{digest}"
+            if kind == "reply" and reply_to
+            else _new_id()
+        )
+
         for existing in messages.values():
-            if existing.get("idempotency_key") == key:
+            if existing.get("idempotency_key") == key or key in existing.get("aliases", []):
                 if (
                     existing["sender_id"] == sender_id
                     and existing["recipient_id"] == recipient_id
@@ -295,14 +308,28 @@
                 ):
                     return _msg(existing)
                 raise IdempotencyConflict(key)
-        self._require_reply_target_locked(
-            sender=sender,
-            sender_id=sender_id,
-            identities=identities,
-            messages=messages,
-            kind=kind,
-            reply_to=reply_to,
-        )
+        if kind == "reply" and reply_to:
+            for existing in messages.values():
+                if (
+                    existing.get("kind") == "reply"
+                    and existing.get("reply_to") == reply_to
+                    and existing["sender_id"] == sender_id
+                    and existing["recipient_id"] == recipient_id
+                    and existing.get("digest") == digest
+                ):
+                    aliases = existing.setdefault("aliases", [])
+                    if key not in aliases and key != existing.get("idempotency_key"):
+                        aliases.append(key)
+                        messages[existing["message_id"]] = existing
+                        self._write(self._messages, messages)
+                    self._cursors.remember_send(
+                        key,
+                        sender=sender_id,
+                        recipient=recipient_id,
+                        digest=digest,
+                        message_id=existing["message_id"],
+                    )
+                    return _msg(existing)
         now = _utc()
         msg = BusMessage(
             message_id=_new_id(),
```

### 3.2 Multi-Layer Protection & Invariants Addressed
1. **Upfront Authorization (C2135):**
   `self._require_reply_target_locked(...)` runs upfront before message inspection or replay. If a caller specifies an unknown reply target, is not the recipient of the target message, or violates project scope, the call immediately fails closed (`BusError`). This holds for new messages and replay paths alike.
2. **Deterministic Default Idempotency for Replies:**
   When `idempotency_key` is omitted, the bus derives `key = f"reply:{reply_to}:{sender_id}:{digest}"`. A re-sent reply evaluates to the exact same key and deduplicates cleanly at line 298.
3. **Semantic Reply Deduplication with Alias Persistence (C2133):**
   When an identical reply is sent with a differing auto/explicit key `key-B`, the semantic reply loop finds the existing message, appends `key-B` to `existing["aliases"]`, writes `messages.json`, and records `key-B` in `_cursors.remember_send`.
4. **Guaranteed Conflict on Alias Reuse with Changed Body (C2133):**
   Because `key-B` is persisted in `existing["aliases"]`, any subsequent call attempting to reuse `key-B` with a changed body will hit the first check (`key in existing.get("aliases", [])`), compare the digest, and strictly fail closed with `IdempotencyConflict("key-B")`. It CANNOT bypass conflict detection.
5. **Removal of Flawed Early Cursor Lookup (C2135):**
   The draft patch's early `_cursors.lookup_send` was completely removed from `bus.py`. Authoritative verification is performed directly against `messages.json` with all fields (`sender_id`, `recipient_id`, `digest`, `kind`, `reply_to`), preventing stale message returns across different task targets or `note` vs `reply`.
6. **Task Target & Kind Binding (C2135):**
   Reusing an explicit idempotency key across different task targets (`reply_to`) or different message kinds (`note` vs `reply`) strictly raises `IdempotencyConflict(key)`.

---

## 4. Test Evidence & Negative Matrix

A dedicated unit test suite (`tests/test_reply_idempotency.py`) was authored and executed in the snapshot testbed, containing 10 comprehensive tests:

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
   - Two distinct replies with different bodies without explicit keys.
   - Result: distinct keys generated, both delivered cleanly. **PASS**.
5. `test_reply_alias_reuse_with_changed_body_fails_closed` (C2133):
   - Call 1 uses key-A. Call 2 aliases key-B with identical body. Call 3 reuses key-B with changed body.
   - Result: raises `IdempotencyConflict("key-B")`. **PASS**.
6. `test_reply_same_key_different_task_target_fails_closed` (C2135):
   - Same explicit key reused across two different task targets (`task1` vs `task2`).
   - Result: raises `IdempotencyConflict`. **PASS**.
7. `test_reply_same_key_note_vs_reply_fails_closed` (C2135):
   - Same explicit key reused between `kind="note"` and `kind="reply"`.
   - Result: raises `IdempotencyConflict`. **PASS**.
8. `test_reply_unauthorized_target_rejected_upfront` (C2135):
   - Non-recipient worker attempts to reply to a task.
   - Result: raises `BusError("not_recipient")` upfront. **PASS**.
9. `test_reply_same_body_changed_data` (C2133):
   - Same body with changed data payload produces distinct digests and keys.
   - Result: distinct messages delivered cleanly. **PASS**.
10. `test_reply_concurrent_identical_replies` (C2133):
    - 10 concurrent threads issuing identical replies under FileLock.
    - Result: all 10 return the exact same `message_id`, exactly 1 message delivered to inbox. **PASS**.

**Test Matrix Results:**
- `pytest tests/test_reply_idempotency.py`: **10/10 PASS**.
- Full snapshot test suite (`pytest tests/`): **34/34 PASS in 7.54s** (zero regressions across core bus, concurrent, crash, dogfood, and scope tests).

---

## 5. Provenance & Actor Demarcation

In `coordination/TEAM-REGISTRY.json` and `coordination/TASKS.json`:
- **Actual Bus Sender:** `369e1e44-678f-4918-a061-e8400651d6eb` (credential file `worker_cred.json`, tag `zcode-sdk-reviewer`).
- **Bridge Auto-Enrolled Identity:** `7c27190c-05ea-4170-8edb-b8513801296c` was auto-enrolled by `launcher_bus_bridge.py` during adapter startup, but was unused because the worker utilized pre-provisioned `worker_cred.json` per task instructions.
- **Reconciliation:** Registry updated in commit `fc5775a` to record actual sender `369e1e44-678f-4918-a061-e8400651d6eb` and disclose `7c27190c` as auto-enrolled bridge identity. Zero phantom actor credit claimed.
- **Task Demarcation:** Parent task `self-org-live-model-runtime` returned to `held` (`acceptance_status: "HELD"`). Controlled SDK trial split into dedicated row `self-org-sdk-consumer-trial` (`done`, `acceptance_status: "ACCEPTED"`).
- **Two Generals Wording:** Qualified to state that Test 11 proves suppression of automatic mutating retries on one client invocation, not a universal theorem.

---

## 6. Temporary File Floor Invariant & Systemd Scope Containment (C2134)

### 6.1 Diagnosis of `/tmp` Leakage
Observed usage during trial execution revealed that external `zcodex` binary created temporary prompt files (`/tmp/zcode-prompt-*`) in the root filesystem.
- **Filesystem Classification:** `/tmp` is a separate tmpfs/underfloor filesystem on this host. Writing to `/tmp` violates the 20 GiB floor constraint.
- **Mechanism Discovery:** Non-model investigation proved that `systemd-run --user --scope` communicates via D-Bus with the user systemd manager. As a result, environment variables set on the parent `subprocess.Popen(env=clean_env)` are **dropped by default** by systemd unless:
  1. `-E TMPDIR=<path>`, `-E TEMP=<path>`, `-E TMP=<path>` are passed explicitly on the `systemd-run` command line.
  2. The Python prelude script running inside the scope explicitly restores `os.environ["TMPDIR"] = ...`, `os.environ["TEMP"] = ...`, and `os.environ["TMP"] = ...` before executing `os.execvp`.
- When `TMPDIR` was dropped, Rust binaries (such as `zcodex`) calling `std::env::temp_dir()` defaulted to `/tmp`.

### 6.2 Hardened Containment & Verification
- `research/antigravity/tooling/self_org/launcher_bus_bridge.py` was updated to pass `-E TMPDIR=...`, `-E TEMP=...`, `-E TMP=...` in `scope_cmd` and set `os.environ["TMPDIR"] = ...` in `prelude_code` before `os.execvp`.
- Test 33 (`test_33_c2134_tmpdir_containment_in_systemd_scope_non_model`) was authored and added to `tests/test_launcher_bus_bridge.py`. It executes a non-model Python probe inside a real systemd scope and verifies:
  1. `os.environ["TMPDIR"]` matches the requested owned scratch directory.
  2. `tempfile.gettempdir()` returns the owned scratch directory.
  3. Temporary files created via `tempfile.NamedTemporaryFile()` strictly reside in the owned scratch directory.
  4. `f_path.startswith('/tmp')` is `False`.
- Test 33 PASSED in 0.340s; full test suite **33/33 PASS in 9.574s**.
- Model route launches remain HELD until independent reviewer verifies test receipts.
