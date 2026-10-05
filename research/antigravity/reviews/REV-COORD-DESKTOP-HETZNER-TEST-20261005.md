# Independent Peer Review: Audit of `coord-desktop-hetzner-test` (Cross-Computer Message Exchange & Network Disconnect Simulation)

**Date & Time**: 2026-10-05T23:35:00Z (2026-10-06 01:35:00 Berlin)  
**Auditor / Reviewer**: `antigravity` (Independent Reviewer Subagent)  
**Parent Caller ID**: `ea14b401-20e9-4e48-ab08-d15be08da30d`  
**Target Repository**: `/home/alexey/git/agent-coordination`  
**Audited Task ID**: `coord-desktop-hetzner-test`  
**Task Log File**: `/home/alexey/git/agent-quota-launcher/.local/launcher-config/coord-desktop-hetzner-test-stdout.log`  
**Audited Session / Conversation ID**: `5d68b065-a500-48b1-8bff-52766fb6eb7e`  
**Verdict**: **ACCEPTED**

---

## 1. Executive Summary & Audit Matrix

An independent technical audit was conducted on task `coord-desktop-hetzner-test` executed in `/home/alexey/git/agent-coordination`. The goal of the audited task was to simulate and validate desktop-to-Hetzner cross-computer message exchange across network disconnects, offline queue buffering, and cursor resumption.

The audit verified:
1. **Model identity and environment**: Executed strictly under model `gemini-3.1-pro-high` as registered in the launcher task unit.
2. **First tool execution**: Verified genuine execution of the model's initial tool call before response generation.
3. **Execution status & clean exit**: Process completed with status `SUCCESS` and exit code `0` recorded in `agent-quota-launcher`'s `state.db`.
4. **Code deliverable & architecture**:
   - `coordination/ssh_relay.py`: Enhanced `SshRelay.send()` to catch `TransportUnavailable` network disconnect exceptions, cleanly queue messages into `CursorStore`'s offline outbox, defer send deduplication until true transmission, and fix path delimiter unpacking in `_pad()` for multi-segment directory workspaces.
   - `tests/test_offline_network.py`: Implemented `FlakyTransport` and end-to-end simulation test `test_desktop_to_hetzner_offline_queues_and_resumes` verifying desktop-to-Hetzner queuing during network drops, recovery, queue flushing via `retry_offline()`, and cursor recording.
   - `tests/test_ssh_relay.py`: Maintained compatibility with wrapped command dispatch.
5. **Full test suite validation**: Complete repository test suite in `/home/alexey/git/agent-coordination` passed cleanly (35 passed in 1.79s).

### Audit Evaluation Matrix

| # | Inspection Item | Verification Requirement | Observed Evidence | Verdict |
|---|---|---|---|:---:|
| **1** | Model Identity | Model configured and run as `gemini-3.1-pro-high` | `coord-desktop-hetzner-test-stdout.log` `init` event: `"model": "gemini-3.1-pro-high"`; confirmed in session transcript metadata | **PASS** |
| **2** | First Model Tool Execution | Genuine first tool invocation by model before output synthesis | Step index 2 executed `run_command` (`ls -la && ls -la coordination/`) returning real filesystem status at timestamp `2026-10-06T01:19:04+02:00` | **PASS** |
| **3** | Execution Lifecycle & Exit Code | Task completed successfully with exit code 0 | `coord-desktop-hetzner-test-stdout.log` result event: `status: "SUCCESS"`; launcher `state.db` records `task-units sibling unit exit 0`; stderr is 0 bytes | **PASS** |
| **4** | Offline Queue Buffering | On transport failure, messages buffer in outbox without dropping | `SshRelay.send()` catches `TransportUnavailable`, calls `self.store.queue_offline()`, returns receipt with `delivery: "queued_offline"` | **PASS** |
| **5** | Deduplication Timing & Resumption | Send is not remembered until actual network transmission succeeds | Removed premature `remember_send()` from exception handler; `retry_offline()` successfully transmits and records idempotency key on success | **PASS** |
| **6** | Workspace Path Integrity | Namespaced ID parsing supports multi-segment workspace paths | `_pad()` updated to anchor from device and trailing tags, joining intermediate segments into `workspace` | **PASS** |
| **7** | Disconnect Simulation Suite | Explicit automated test verifying disconnect, recovery, and cursor | `tests/test_offline_network.py` passes with `FlakyTransport` simulating network outage and recovery | **PASS** |
| **8** | Full Test Suite Execution | All tests in `agent-coordination` pass cleanly | `pytest -v tests/` executed: 35 passed in 1.79s | **PASS** |

---

## 2. Sibling Task Unit Execution Audit

### 2.1 Launcher Metadata & Model Verification
The task was launched under `agent-quota-launcher` with the following configuration recorded in `/home/alexey/git/agent-quota-launcher/.local/launcher-config/state.db`:
- **Task ID**: `coord-desktop-hetzner-test`
- **Idempotency Key**: `ql-enqueue-coord-desktop-hetzner-test-02ec02f5d1e6`
- **Enqueued Status**: `completed-awaiting-review`
- **Model Requirements**:
  ```json
  {
    "provider": "antigravity",
    "model": "gemini-3.1-pro-high"
  }
  ```

In `/home/alexey/git/agent-quota-launcher/.local/launcher-config/coord-desktop-hetzner-test-stdout.log`:
- **Line 0 (Init Event)**:
  ```json
  {
    "event": "init",
    "conversation_id": "5d68b065-a500-48b1-8bff-52766fb6eb7e",
    "init": {
      "model": "gemini-3.1-pro-high",
      "cwd": "/home/alexey/git/agent-coordination",
      "permission_mode": "always-proceed"
    }
  }
  ```
- **Session Transcript Metadata**:
  The conversation transcript in `~/.gemini/antigravity-cli/brain/5d68b065-a500-48b1-8bff-52766fb6eb7e/.system_generated/logs/transcript.jsonl` verifies:
  ```json
  {
    "step_index": 0,
    "source": "USER_EXPLICIT",
    "type": "USER_INPUT",
    "content": "<USER_REQUEST>\nSimulate desktop-to-Hetzner message exchange across network disconnects, validating offline queue buffering and cursor resumption.\n</USER_REQUEST>\n<USER_SETTINGS_CHANGE>\nThe user changed setting `Model Selection` from None to Gemini 3.1 Pro (High).\n</USER_SETTINGS_CHANGE>"
  }
  ```

### 2.2 Genuine First Model Tool Execution
The task executed real tool calls from its first active turn:
- **Event 4 (Step 2 Active)**:
  ```json
  {
    "event": "step_update",
    "step_update": {
      "conversation_id": "5d68b065-a500-48b1-8bff-52766fb6eb7e",
      "step_index": 2,
      "state": "ACTIVE",
      "step_type": "tool",
      "tool_name": "run_command",
      "tool_info": {
        "name": "run_command",
        "parameters": {
          "CommandLine": "ls -la && ls -la coordination/"
        }
      }
    }
  }
  ```
- **Event 5 (Step 2 Done)**:
  Completed with duration 0.028s, returning the file structure of `/home/alexey/git/agent-coordination`.

Subsequent steps inspected `coordination/ssh_relay.py`, `coordination/cursors.py`, and `tests/test_ssh_relay.py`, applied code edits using `replace_file_content` / `write_to_file`, and ran unit tests.

### 2.3 Task Completion & Exit Code
- **Event Result**:
  ```json
  {
    "event": "result",
    "result": {
      "conversation_id": "5d68b065-a500-48b1-8bff-52766fb6eb7e",
      "status": "SUCCESS",
      "duration_seconds": 255.888,
      "num_turns": 1,
      "usage": {
        "input_tokens": 212264,
        "output_tokens": 19731,
        "thinking_tokens": 12106,
        "cache_read_tokens": 2254252,
        "total_tokens": 231995
      }
    }
  }
  ```
- **Database Entry (`state.db`)**:
  ```text
  coord-desktop-hetzner-test | completed-awaiting-review | 2026-10-05 21:26:03 | 2026-10-05 23:23:11 | task-units sibling unit exit 0
  ```
- **Stderr Log**: `/home/alexey/git/agent-quota-launcher/.local/launcher-config/coord-desktop-hetzner-test-stderr.log` is 0 bytes (clean execution, no unhandled exceptions).

---

## 3. Code Deliverables & Implementation Review

### 3.1 Network Disconnect Handling (`coordination/ssh_relay.py`)
In `SshRelay.send()`:
```python
try:
    catalog = self.catalog(target.id, request.recipient.workspace)
    entry = catalog.resolve_tag(request.recipient.workspace, request.recipient.agent_tag)
    inspect_delivery_guard(entry, request.delivery)

    import shlex
    aplexer_bin = target.aplexer_bin or "aplexer"
    inner_argv = [
        aplexer_bin,
        "message",
        "send",
        "--to",
        request.recipient.agent_tag,
        "--json",
        request.body,
    ]
    if request.data is not None:
        inner_argv.extend(["--data", json.dumps(request.data, separators=(",", ":"))])
        
    quoted_inner = " ".join(shlex.quote(a) for a in inner_argv)
    cd_command = f"cd {shlex.quote(request.recipient.workspace)} && {quoted_inner}"
    argv = ["sh", "-c", cd_command]
    raw = self.transport.run(target, argv)
    payload = json.loads(raw) if raw.strip() else {}
    message_id = payload.get("id") or new_message_id()
    self.store.remember_send(
        key,
        sender=request.sender.render(),
        recipient=request.recipient.render(),
        digest=digest,
        message_id=message_id,
    )
    self.store.mark_sent(key, message_id)
    return SendReceipt(...)
except TransportUnavailable:
    message_id = new_message_id()
    self.store.queue_offline(
        {
            "idempotency_key": key,
            "message_id": message_id,
            "sender": request.sender.render(),
            "recipient": request.recipient.render(),
            "body": request.body,
            "data": request.data,
            "correlation_token": request.correlation_token,
            "bridge_device_id": bridge,
            "originating_agent": origin.render(),
        }
    )
    return SendReceipt(
        message_id=message_id,
        idempotency_key=key,
        sender=request.sender,
        recipient=request.recipient,
        delivery="queued_offline",
        recorded_at="",
        catalog_resolved_session_id=None,
        catalog_observed_at="",
        bridge_device_id=bridge,
        originating_agent=origin,
        payload_sha256=digest,
    )
```

**Key Architectural Strengths**:
1. **Exception Isolation**: `TransportUnavailable` exceptions (thrown by SSH disconnects, timeout, or network unavailability during catalog inspection or remote execution) are caught cleanly.
2. **Offline Outbox Buffering**: Instead of dropping messages or propagating errors up to calling agents, messages are queued via `self.store.queue_offline()`.
3. **Correct Idempotency Semantics**: The earlier implementation eagerly called `self.store.remember_send()` during the offline queuing branch. That prevented subsequent network retries because `lookup_send()` would treat the message as already sent. The updated code defers `remember_send()` until genuine network transmission succeeds in `send()`.
4. **Shell Isolation**: Uses `cd <workspace> && aplexer ...` ensuring remote commands execute within the targeted repository workspace.

### 3.2 Workspace Path Unpacking Fix (`coordination/ssh_relay.py`)
In `_pad()`:
```python
def _pad(parts: list[str]) -> tuple[str, str, str, str, str | None]:
    while len(parts) < 5:
        parts.append("-")
    
    device = parts[0]
    task = parts[-1]
    session = parts[-2]
    tag = parts[-3]
    workspace = "/".join(parts[1:-3])
    
    return device, workspace, tag, task, None if session == "-" else session
```
- **Problem Fixed**: Splitting a rendered `NamespacedId` (e.g. `desktop-local//home/alexey/git/cloudflare-agent-git/agent-coordination-head/...`) produced extra slash tokens. A naive index slice corrupted the workspace path.
- **Correction**: Anchors `device` at `parts[0]`, `task` at `parts[-1]`, `session` at `parts[-2]`, `tag` at `parts[-3]`, and safely rejoins `parts[1:-3]` as the multi-segment workspace path.

### 3.3 Offline Network Simulation Test (`tests/test_offline_network.py`)
The new test suite provides an explicit simulation of the desktop-to-Hetzner communication path:
```python
def test_desktop_to_hetzner_offline_queues_and_resumes(tmp_path: Path):
    transport = FlakyTransport()
    relay = SshRelay(
        DeviceRegistry.load(EXAMPLE),
        transport,
        CursorStore(tmp_path),
        local_device_id="desktop-local"
    )

    req = SendRequest(
        sender=NamespacedId("desktop-local", "/ac", "gui", "t1", "s1"),
        recipient=NamespacedId("hetzner-rmthz", "/home/alexey/git/cloudflare-agent-git", "codex-principal", "t1"),
        body="hello",
        data={"action": "test"},
        idempotency_key="msg-1",
        correlation_token="tok-1",
    )

    # 1. Network disconnected, simulates desktop sending to Hetzner
    transport.is_offline = True
    receipt1 = relay.send(req)
    assert receipt1.delivery == "queued_offline"
    
    pending = relay.store.pending_outbox()
    assert len(pending) == 1
    assert pending[0]["body"] == "hello"
    
    # 2. Network reconnects
    transport.is_offline = False
    
    # Retry offline queue
    receipts = relay.retry_offline()
    assert len(receipts) == 1
    assert receipts[0].delivery == "inbox"
    
    # Queue should be empty now
    assert len(relay.store.pending_outbox()) == 0
    
    # The cursor should remember the message ID
    assert relay.store.lookup_send(
        "msg-1",
        sender=req.sender.render(),
        recipient=req.recipient.render(),
        digest=receipts[0].payload_sha256
    ) == receipts[0].message_id
```

The test validates:
- Disconnect scenario -> returns receipt with `queued_offline`, stores row in pending outbox.
- Reconnect scenario -> `retry_offline()` retries pending sends, converts them to delivered receipts (`delivery == "inbox"`).
- Outbox state -> drained to 0 pending rows.
- Cursor store -> remembers the message ID for idempotency deduplication upon resumption.

---

## 4. Test Suite Execution Verification

Execution of the full test suite in `/home/alexey/git/agent-coordination`:
```bash
python3 -m pytest -v tests/
```

### Results Summary
```text
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.1.1, pluggy-1.6.0
rootdir: /home/alexey/git/agent-coordination
configfile: pyproject.toml
plugins: anyio-4.12.1, opik-2.2.54
collected 35 items

tests/test_adapter_cli.py .                                              [  2%]
tests/test_bus.py .....                                                  [ 17%]
tests/test_bus_dogfood.py .                                              [ 20%]
tests/test_cursors.py ...                                                [ 28%]
tests/test_device_registry.py .....                                      [ 42%]
tests/test_envelope.py ..                                                [ 48%]
tests/test_guards.py ...                                                 [ 57%]
tests/test_offline_network.py .                                          [ 60%]
tests/test_sessionless_worker_bus.py .......                             [ 80%]
tests/test_ssh_relay.py ......                                           [ 97%]
tests/test_worker_bus_cli.py .                                           [100%]

============================== 35 passed in 1.79s ==============================
```

All 35 tests across the entire repository pass with zero failures and zero warnings.

---

## 5. Audit Verdict & Conclusion

- **Model Execution**: Verified genuine `gemini-3.1-pro-high` execution with real tool calls.
- **Exit Status**: Verified exit code 0 and `SUCCESS` status in launcher `state.db`.
- **Functionality**: Verified resilient cross-computer offline buffering, queue draining on reconnection, and cursor resumption.
- **Regressions**: Verified zero regressions across the 35-test suite.

**Final Verdict**: **ACCEPTED**
