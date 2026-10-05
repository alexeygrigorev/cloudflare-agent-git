# Independent Challenger Review: Agent-Bus Default Idempotency & Semantic Replay (Codex C2133 / C2135 / C2136)

- **Reviewer**: Independent Challenger & Negative Reviewer (tag: `reviewer37`, conversation ID: `37aa1067-8bda-4dde-95b8-7b5bb927bd1f`)
- **Authority**: Dispatched by `antigravity-head` (`46fdb644`, conversation ID: `245c7bba-9a7b-45c1-87a7-4537f289f9a5`) under Codex Principal C2133, C2135, and C2136 directives and existing human authority (`experiment/human-self-organization-20261004.txt`).
- **Snapshot Audited**: `/home/alexey/git/cloudflare-agent-git/.local/scratch/bus-idempotency-snapshot/agent-bus/` (FROZEN/PINNED)
- **Patch Audited**: `/home/alexey/git/cloudflare-agent-git/research/antigravity/recovery/bus-default-idempotency-and-semantic-replay.patch`
  - SHA256: `6494985fb62f3a7a3f86b69dccd73f299ab15ec7598f370ac83ec92521568cab`
- **Canonical Base Compared**: `/home/alexey/git/agent-bus/` (READ-ONLY, ZERO MUTATIONS)
- **Testbed Execution Root**: `/home/alexey/git/cloudflare-agent-git/.local/scratch/self-org-challenge/bus-idempotency/` (mode `0700`, strictly <= 512 MB, zero net `/tmp` growth)
- **Date**: 2026-10-05T02:06:00+02:00 (Europe/Berlin)
- **Verdict**: **BOUNDED ACCEPTANCE**
  *(Verified default reply idempotency, semantic replay deduplication, alias collision defense, and upfront authorization; strictly bounded to reply kind pending canonical integration)*

---

## 1. Executive Summary & Problem Demarcation

Under Codex Principal Directives C2133, C2135, and C2136:
> *"Adversarial verification of C2133 challenges: Alias persistence (Call 1 uses key-A, Call 2 uses key-B with identical body aliasing, Call 3 reusing key-B with changed body strictly fails closed with IdempotencyConflict); test same body with changed data; test concurrent identical replies under FileLock; test wrong actor/target authorization failure."*
> *"Adversarial verification of C2135 challenges: Early _cursors.lookup_send removal (verify bus does not return stale message before kind/reply_to/authorization checks); re-auth / reply target authorization upfront on replay paths (reject non-recipients with BusError('not_recipient')); same explicit key across different task targets fails closed; same explicit key for note vs reply fails closed."*

In canonical `agent-bus` (`/home/alexey/git/agent-bus/coordination/bus.py`):
1. `reply()` without an explicit `idempotency_key` generated a random UUID via `_new_id()`, causing retried replies or duplicate executions to produce distinct, duplicate messages in the recipient's inbox.
2. `self._require_reply_target_locked` was evaluated *after* checking `messages.values()` for existing idempotency keys. Consequently, an unauthorized caller or replay could retrieve an existing message before authorization checks were enforced.
3. Multiple calls using differing client-generated idempotency keys for byte-identical replies failed to recognize semantic equivalence, creating duplicate replies.
4. Aliased keys introduced across multiple calls lacked persistence and collision verification against subsequent tampered payloads.

The snapshot under audit resolves these defects through four tightly coupled mechanisms:
1. **Upfront Authorization**: `_require_reply_target_locked` runs immediately after recipient lookup, before any message iteration or replay lookup.
2. **Deterministic Default Reply Keys**: Default key derived deterministically as `f"reply:{reply_to}:{sender_id}:{digest}"` for `kind="reply"`.
3. **Semantic Replay & Alias Registration**: Byte-identical replies to the same message alias new keys into `existing["aliases"]` and persist to disk.
4. **Strict Alias Collision Defense**: Both `idempotency_key` and any registered `aliases` are verified against the incoming payload digest, failing closed with `IdempotencyConflict(key)` if tampered.

---

## 2. Exact Code Diff Analysis: Canonical vs Snapshot

The audited patch (`bus-default-idempotency-and-semantic-replay.patch`, SHA256: `6494985f...`) introduces a single 68-line hunk in `coordination/bus.py`:

```diff
--- /home/alexey/git/agent-bus/coordination/bus.py
+++ .local/scratch/bus-idempotency-snapshot/agent-bus/coordination/bus.py
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
-        self._require_reply_target_locked(...)
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
+                    self._cursors.remember_send(...)
+                    return _msg(existing)
```

---

## 3. Adversarial Audit of C2133 Challenges

### 3.1 Alias Persistence Across Calls and Restart
- **Vulnerability**: If an aliased key `key-B` is attached to a message `M1` during Call 2, a subsequent Call 3 reusing `key-B` with a modified payload could either overwrite `M1` or bypass conflict detection if aliases are not checked or not persisted to disk.
- **Hardening Verification**:
  1. **Call 1**: Worker replies to Task 1 with `body="Review complete: ACCEPT"` and `idempotency_key="key-A"`. Message `M1` created.
  2. **Call 2**: Worker replies to Task 1 with identical body and `idempotency_key="key-B"`. Semantic replay logic attaches `"key-B"` into `existing["aliases"]` and writes to disk. Returns `M1`.
  3. **Call 3**: Worker replies to Task 1 reusing `"key-B"` with modified body `"Review complete: REJECT"`. Line 301 matches `"key-B"` in `existing.get("aliases", [])`, detects digest mismatch, and raises `IdempotencyConflict("key-B")`.
  4. **Disk Persistence Verification**: Re-instantiated a fresh `FileBus` instance from disk. Call 3 repeated against the new instance strictly raised `IdempotencyConflict("key-B")`, proving aliases are durably persisted in `messages.json`.

### 3.2 Payload Digest Invariants (Same Body, Changed Data)
- **Vulnerability**: Idempotency keys must not ignore structured `data` dicts; two replies with identical body strings but distinct metrics/results must not collide or falsely deduplicate.
- **Hardening Verification**:
  - `payload_digest(body, data)` hashes canonical JSON representation of `data` alongside `body`.
  - With default keys: `reply(task1, body="Task Status", data={"run": 1})` and `reply(task1, body="Task Status", data={"run": 2})` produced different digests, distinct default keys (`reply:task1:w1:<digest1>` vs `reply:task1:w1:<digest2>`), and resulted in both messages being delivered to the coordinator inbox (count = 2).
  - With explicit keys: Reusing `"explicit-data-key"` with changed `data` strictly raised `IdempotencyConflict("explicit-data-key")`.

### 3.3 Concurrent Identical Replies Under FileLock
- **Vulnerability**: Multiple parallel threads or subagents retrying identical replies simultaneously could race during `_read` / `_write`, resulting in duplicate messages or torn `aliases` arrays.
- **Hardening Verification**:
  - Executed 16 concurrent threads via `ThreadPoolExecutor(max_workers=8)` submitting identical replies with distinct auto keys (`auto-key-0` through `auto-key-15`) under real `FileLock`.
  - All 16 threads received the exact same `message_id`.
  - Coordinator inbox contained exactly 1 message.
  - On-disk message record cleanly contained all alias keys without JSON corruption.

### 3.4 Wrong Actor Authorization Failure
- **Vulnerability**: Worker 2 attempting to reply to a task assigned to Worker 1.
- **Hardening Verification**:
  - Worker 2 called `reply(task1, body="Imposter reply")`.
  - `_require_reply_target_locked` verified that `task1["recipient_id"] == worker1.identity_id != worker2.identity_id` and immediately raised `BusError("not_recipient")`.

---

## 4. Adversarial Audit of C2135 Challenges

### 4.1 Upfront Authorization on Replay Paths (Early Cursor Removal)
- **Vulnerability**: In canonical code, `_require_reply_target_locked` occurred after checking existing messages. An unauthorized caller supplying a known idempotency key could bypass recipient authorization and obtain a message receipt. Furthermore, early cursor lookups bypassed bus state verification.
- **Hardening Verification**:
  - `_cursors.lookup_send` was completely removed from the `send()` execution path.
  - `_require_reply_target_locked` was placed at line 285, prior to checking existing messages or semantic replays.
  - Tested: Worker 1 legitimately replied with `key="stale-probe-key"`. Worker 2 then attempted to send a reply to Task 1 using the same key `"stale-probe-key"`.
  - Result: Worker 2 was immediately rejected with `BusError("not_recipient")`. The existing message was never leaked.

### 4.2 Target Isolation: Same Key Across Different Task Targets
- **Vulnerability**: If an explicit idempotency key is reused across different tasks, matching on key and digest alone without checking `reply_to` would cause the bus to falsely return Task 1's reply as the response to Task 2.
- **Hardening Verification**:
  - Worker 1 replied to Task 1 with `idempotency_key="cross-target-key"`.
  - Worker 1 then replied to Task 2 with identical body and `idempotency_key="cross-target-key"`.
  - Line 307 verified `existing.get("reply_to") == reply_to` (`task1 != task2`).
  - Result: Raised `IdempotencyConflict("cross-target-key")`. Task 1's reply was never returned for Task 2.

### 4.3 Kind Isolation: Same Explicit Key for Note vs Reply
- **Vulnerability**: Reusing an idempotency key across different message kinds (e.g. `note` vs `reply`) could allow a note to masquerade as a task reply.
- **Hardening Verification**:
  - Worker sent a `note` with `idempotency_key="note-reply-shared-key"`.
  - Worker subsequently attempted to send a `reply` to Task 1 with the same key.
  - Line 306 verified `existing.get("kind") == kind` (`"note" != "reply"`).
  - Result: Strictly raised `IdempotencyConflict("note-reply-shared-key")`.

---

## 5. Negative Mutation Matrix (5 Mutants Evaluated & Killed)

Evaluated in `.local/scratch/self-org-challenge/bus-idempotency/test_adversarial_idempotency.py`:

| # | Mutant Behavior Injected | Vulnerability Exposed | Hardened Defense Behavior | Verdict |
|---|---|---|---|---|
| **Mutant 1** | `_require_reply_target_locked` placed after idempotency lookup | Unauthorized caller supplying known key retrieves existing message | Upfront check at line 285 raises `BusError("not_recipient")` | **KILLED** |
| **Mutant 2** | `if existing.get("idempotency_key") == key:` only (omits alias check) | Subsequent call reusing aliased key with changed body bypasses conflict check | Line 301 checks `key in existing.get("aliases", [])` and raises `IdempotencyConflict` | **KILLED** |
| **Mutant 3** | Reverts default reply key to `_new_id()` (random UUID) | Retried reply creates duplicate inbox message | Line 294 computes deterministic `reply:{reply_to}:{sender_id}:{digest}` | **KILLED** |
| **Mutant 4** | Omits `existing.get("reply_to") == reply_to` in match check | Same key across different tasks falsely returns old task reply | Line 307 verifies `reply_to` equality; mismatches raise `IdempotencyConflict` | **KILLED** |
| **Mutant 5** | Omits `existing.get("kind") == kind` in match check | Reusing key for note and reply falsely aliases different message types | Line 306 verifies `kind` equality; mismatches raise `IdempotencyConflict` | **KILLED** |

---

## 6. Test Execution Receipts

### 6.1 Snapshot Test Suite Execution
Command: `pytest -v tests/` inside `.local/scratch/bus-idempotency-snapshot/agent-bus/`

```
tests/test_bus.py ...........                                            [ 32%]
tests/test_bus_concurrent.py ..                                          [ 38%]
tests/test_bus_crash.py .....                                            [ 52%]
tests/test_bus_dogfood.py .                                              [ 55%]
tests/test_bus_scope.py ....                                             [ 67%]
tests/test_headless_task.py .                                            [ 70%]
tests/test_reply_idempotency.py ..........                               [100%]

============================== 34 passed in 7.79s ==============================
```

### 6.2 Independent Adversarial Test Suite Execution
Command: `python3 .local/scratch/self-org-challenge/bus-idempotency/test_adversarial_idempotency.py -v`

```
test_c2133_alias_persistence_and_conflict_on_changed_body (__main__.AdversarialBusIdempotencyTests.test_c2133_alias_persistence_and_conflict_on_changed_body) ... ok
test_c2133_concurrent_identical_replies (__main__.AdversarialBusIdempotencyTests.test_c2133_concurrent_identical_replies) ... ok
test_c2133_same_body_changed_data (__main__.AdversarialBusIdempotencyTests.test_c2133_same_body_changed_data) ... ok
test_c2133_wrong_actor_authorization_failure (__main__.AdversarialBusIdempotencyTests.test_c2133_wrong_actor_authorization_failure) ... ok
test_c2135_same_key_different_task_targets_fails_closed (__main__.AdversarialBusIdempotencyTests.test_c2135_same_key_different_task_targets_fails_closed) ... ok
test_c2135_same_key_note_vs_reply_fails_closed (__main__.AdversarialBusIdempotencyTests.test_c2135_same_key_note_vs_reply_fails_closed) ... ok
test_c2135_upfront_auth_on_replay_paths (__main__.AdversarialBusIdempotencyTests.test_c2135_upfront_auth_on_replay_paths) ... ok
test_c2136_default_key_deterministic_replay (__main__.AdversarialBusIdempotencyTests.test_c2136_default_key_deterministic_replay) ... ok
test_mutant_1_auth_checked_after_idempotency_lookup (__main__.NegativeMutationMatrixTests.test_mutant_1_auth_checked_after_idempotency_lookup) ... ok
test_mutant_2_ignoring_aliases_in_conflict_check (__main__.NegativeMutationMatrixTests.test_mutant_2_ignoring_aliases_in_conflict_check) ... ok
test_mutant_3_random_key_on_reply_without_key (__main__.NegativeMutationMatrixTests.test_mutant_3_random_key_on_reply_without_key) ... ok
test_mutant_4_ignoring_reply_to_in_match (__main__.NegativeMutationMatrixTests.test_mutant_4_ignoring_reply_to_in_match) ... ok
test_mutant_5_ignoring_kind_in_match (__main__.NegativeMutationMatrixTests.test_mutant_5_ignoring_kind_in_match) ... ok

----------------------------------------------------------------------
Ran 13 tests in 3.958s

OK
```

---

## 7. Resource, Scratch, and Publication Guard Invariants

1. **Publication Credential Guard**:
   - Command: `python3 research/antigravity/tooling/publication_guard.py research/antigravity/reviews/REV-BUS-DEFAULT-IDEMPOTENCY.md`
   - Exit Code: `0` (Zero credentials, zero private keys, zero leaked tokens).
2. **Compiler Invariant**: Exactly `0` `cargo` or `rustc` invocations.
3. **Scratch Budget & Isolation**:
   - Scratch root `/home/alexey/git/cloudflare-agent-git/.local/scratch/self-org-challenge/` mode: `0700`.
   - Total disk usage: `116 KiB` (strictly below the 512 MB ceiling).
4. **Ambient `/tmp` Invariant**:
   - Zero temporary files written to ambient `/tmp` (all test runs configured with local scratch TMPDIR).
   - Net `/tmp` growth: `0 bytes`.
5. **Git Invariant**:
   - Zero git commits or stage mutations executed by subagent. Canonical `/home/alexey/git/agent-bus/` remains 100% untouched.

---

## 8. Formal Verdict

**VERDICT: BOUNDED ACCEPTANCE**

### Conditions and Scope of Acceptance:
1. **Verified Mechanisms (ACCEPTED)**:
   - Default deterministic reply idempotency (`reply:{reply_to}:{sender_id}:{digest}`) is robust and eliminates duplicate replies on retry.
   - Semantic replay deduplication properly detects identical replies with differing auto keys and registers persistent on-disk aliases.
   - Reusing an aliased key with modified content strictly fails closed with `IdempotencyConflict(key)`.
   - `_require_reply_target_locked` runs upfront, preventing message leaking to unauthorized callers.
   - Multi-threaded concurrent reply generation under `FileLock` guarantees exactly one message delivered to inbox.
2. **Operational Boundaries (BOUNDED)**:
   - Default determinism and semantic replay are strictly scoped to `kind == "reply"` with valid `reply_to`. Messages of kind `note` or `task` intentionally continue to generate unique IDs if no explicit `idempotency_key` is supplied.
   - The canonical repository `/home/alexey/git/agent-bus/` remains unmodified in this review; application of the patch (`bus-default-idempotency-and-semantic-replay.patch`) should be orchestrated by the principal/head.
