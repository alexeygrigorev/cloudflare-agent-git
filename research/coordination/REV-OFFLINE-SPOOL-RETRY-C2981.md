# Independent Peer Review: Offline Spool, Durable Retry, and Typed SSH Stdin RPC (Product 4 — Cross-Computer Agent Coordination)

- **Directive**: C2981
- **Task Reference**: `t-coord-offline-spool-retry-c2981`
- **Review Task Reference**: `t-coord-offline-spool-retry-review-c2981`
- **Reviewed Commit Pin**: `b3ca77650bdf34c9c3cbd361f1d99253ee71cd44` (pushed to `origin/codex/role-failover-20261006` in `/home/alexey/git/agent-coordination`)
- **Reviewed Files**:
  - [`adapters/agent_bus_client.py`](file:///home/alexey/git/agent-coordination/adapters/agent_bus_client.py) (+382 lines)
  - [`tests/test_agent_bus_client.py`](file:///home/alexey/git/agent-coordination/tests/test_agent_bus_client.py) (+334 lines)
- **Review Date**: 2026-10-06T21:15:00+02:00 (Europe/Berlin) / 2026-10-06T19:15:00Z
- **Reviewer**: Distinct Independent Peer Reviewer for Product 4 (`antigravity-cli`, subagent `f6551f30-7d47-4724-b6ba-1cc226c3a64c`)
- **Reviewer Role**: Distinct Independent Reviewer for Offline Spool and Retry Architecture
- **Caller / Head**: Product 4 Project Head (`764358a8-1b4e-49c6-845a-9b79bf3ba536` / `coord-917-custody-resume-20261006`)
- **Governing Agreements**: Scale-50 Recovery Plan (`coordination/SCALE50-RECOVERY-PLAN.md`), Operating Model (`coordination/OPERATING-MODEL.md`), Resource Policy (`coordination/RESOURCE-POLICY.md`)
- **Independent Verdict**: **ACCEPT**

---

## 1. Executive Summary & Verdict Rationale

This independent peer review audits the implementation of `OfflineSpool`, durable retry mechanisms, and typed SSH stdin JSON-RPC execution delivered under Directive C2981 for Task `t-coord-offline-spool-retry-c2981`. The implementation provides local persistence and guaranteed FIFO message dispatch for cross-computer agent coordination nodes operating over intermittent, lossy, or temporarily disconnected network links, with zero risk of command-line quoting truncation or token leakage.

### Final Verdict: ACCEPT

The implementation satisfies all architectural, security, reliability, and isolation criteria without defect:
1. **Durable Local Persistence & Schema Integrity**: `OfflineSpool` initializes an isolated SQLite database (defaulting to `.local/spool.db`), creating the `spooled_messages` table and performance indexes (`idx_spool_status_created`, `idx_spool_idempotency`).
2. **Fail-Closed Head Credential Defense**: All messages submitted to `spool_message` are subjected to `reject_head_cred_inheritance` across both payload `data` and plaintext `body` prior to executing any SQLite insert. Payloads with credential leaks (`head.cred`, `head_token`, `head_cred`, nested tokens, bearer tokens) fail closed immediately with `ValueError("head_cred_inheritance_rejected")`.
3. **Strict FIFO Ordering & Idempotency Resolution**: Pending messages are queried strictly ordered by `created_at ASC, rowid ASC`. Submissions reusing an existing idempotency key return the existing record if attributes match, and raise `IdempotencyConflict` if conflicting attributes are detected.
4. **Zero Message Loss on Transport Interruption**: The `flush` loop iterates through pending messages and invokes the target bus transport. If any network or transport exception occurs, `flush` logs the failure and breaks immediately. Unsent messages and the failing message remain in `status = 'pending'`, preventing message loss, skipping, or out-of-order delivery.
5. **Typed SSH Stdin Framing**: `build_typed_ssh_command` packages method calls and structured parameter payloads into a single JSON stream fed over standard input (`--stdin`) to `adapters.agent_bus_client rpc`. This completely avoids Windows CLI quoting vulnerabilities, command-line parameter parsing anomalies, and the Windows 8,191-character command string limitation.
6. **CLI Completeness**: Headless execution is supported via CLI subcommands `spool`, `flush`, and `rpc --stdin`.
7. **Complete Test Pass & Peer Invariant Preservation**: 12/12 unit tests pass in `tests/test_agent_bus_client.py`; all 89 tests across the repository pass cleanly. Working tree peer modifications in `agent-coordination` remain 100% untouched with diff SHA-256 matching `8c9f88b85d05deb21b7d732ad6f03499022bde7bcd74c456a56c2fd7f67c94aa`.

---

## 2. Audited Artifacts & Checksums

| Artifact Path | SHA-256 Checksum | Description / Status |
| :--- | :--- | :--- |
| `/home/alexey/git/agent-coordination/adapters/agent_bus_client.py` | `ae05c3449a745e3efe3214cb79506b7db577880c891be937ea2874824fe56269` | OfflineSpool, build_typed_ssh_command, and CLI extensions (Commit `b3ca77650bdf34c9c3cbd361f1d99253ee71cd44`) |
| `/home/alexey/git/agent-coordination/tests/test_agent_bus_client.py` | `05cd6530e1517de971bf4566978a60c1ae815f5e512c6574a5e8bce0c8e696fa` | Unit and integration test suite (+5 new tests covering C2981) |
| `/home/alexey/git/cloudflare-agent-git/research/coordination/REV-OFFLINE-SPOOL-RETRY-C2981.md` | *This file* | Independent peer review report |

---

## 3. Assessment of OfflineSpool Architecture & Implementation

### 3.1 SQLite Initialization & Schema
- **Path Resolution**: When no path is specified, `OfflineSpool` defaults to `.local/spool.db` and invokes `.resolve()` to maintain path consistency across differing working directories. Parent directories are created with `mkdir(parents=True, exist_ok=True)`.
- **Database Schema**:
  ```sql
  CREATE TABLE IF NOT EXISTS spooled_messages (
      spool_id TEXT PRIMARY KEY,
      recipient_id TEXT NOT NULL,
      body TEXT NOT NULL,
      data TEXT,
      idempotency_key TEXT,
      kind TEXT NOT NULL DEFAULT 'note',
      status TEXT NOT NULL DEFAULT 'pending',
      created_at TEXT NOT NULL,
      delivered_at TEXT,
      message_id TEXT
  );
  CREATE INDEX IF NOT EXISTS idx_spool_status_created ON spooled_messages(status, created_at);
  CREATE INDEX IF NOT EXISTS idx_spool_idempotency ON spooled_messages(idempotency_key);
  ```
- **Concurrency & Locking**: Connections use `timeout=30.0` and `conn.row_factory = sqlite3.Row`. SQLite transaction management (`with conn:`) guarantees atomic write operations.

### 3.2 Spooling & Head Credential Protection
- Prior to opening any SQLite transaction or persisting data to disk, `spool_message` validates credentials:
  ```python
  if data is not None:
      data = reject_head_cred_inheritance(data, reject=True)
  if body:
      reject_head_cred_inheritance({"body": body}, reject=True)
  ```
- Any payload containing `head.cred`, `head_token`, `head_cred`, `token`, or nested token keys raises a `ValueError` immediately. No dirty row is inserted into SQLite.

### 3.3 FIFO Ordering & Idempotency Resolution
- **FIFO Retrieval**: `list_pending()` queries the database:
  ```sql
  SELECT spool_id, recipient_id, body, data, idempotency_key, kind, status, created_at, delivered_at, message_id
  FROM spooled_messages
  WHERE status = 'pending'
  ORDER BY created_at ASC, rowid ASC
  ```
  This guarantees deterministic first-in-first-out sequencing across multiple bursts.
- **Idempotency Conflict Handling**: When an `idempotency_key` is supplied, `spool_message` searches for an existing entry. If the existing record matches `(recipient_id, body, data, kind)`, the existing message record is returned (deduplication). If any field diverges, `IdempotencyConflict` is raised immediately.

### 3.4 Flush Lifecycle & Fail-Closed Transport Semantics
- In `flush(store_path, cred, transport_fn=None)`:
  - Retrieves all pending messages in chronological order via `self.list_pending()`.
  - Transmits each item via `transport_fn` (or `send_message`).
  - Upon successful send, invokes `self.mark_delivered(item["spool_id"], msg_id)`.
  - Upon catching any exception (network disconnect, SSH EOF, transport error):
    ```python
    except Exception as exc:
        logging.getLogger(__name__).error(
            "OfflineSpool flush error on %s: %s", item.get("spool_id"), exc
        )
        break
    ```
  - **Zero Message Loss Guarantee**: The loop immediately breaks. The failed message and all subsequent messages remain with `status = 'pending'`. The database is not modified for the failing item. Subsequent invocations of `flush` safely resume starting from the first undelivered message.

---

## 4. Assessment of `build_typed_ssh_command` & Windows Quoting Mitigation

### 4.1 Safe Command Vector
- Cross-platform SSH remote execution commonly encounters argument escaping failures, cmd.exe stripping double quotes, PowerShell parameter parsing errors, and Windows command-line character limits (`8,191` characters).
- `build_typed_ssh_command` solves this by decoupling the command arguments from the payload:
  ```python
  cmd_args = [
      "ssh",
      host,
      python_bin,
      "-m",
      "adapters.agent_bus_client",
      "rpc",
      "--store",
      str(store_path),
      "--cred",
      str(cred_path),
      "--stdin",
  ]
  ```
- The argument vector contains strictly invariant flags.

### 4.2 Stdin JSON Payload Framing
- The actual RPC method and payload parameters are serialized into standard JSON:
  ```python
  payload = {
      "method": method,
      "params": params if params is not None else {},
  }
  json_stdin_payload = json.dumps(payload)
  return cmd_args, json_stdin_payload
  ```
- The JSON payload is streamed through SSH stdin. This supports arbitrarily large coordination payloads (e.g. state sync, multi-KB logs) without exceeding Windows command length limits or risking shell injection.

### 4.3 CLI Subcommands
- **`spool`**:
  ```bash
  python3 -m adapters.agent_bus_client spool \
      --spool-db .local/spool.db \
      --recipient <id> \
      --body "..." \
      --data '{"step": 1}' \
      --key <idem-key> \
      --kind instruction
  ```
- **`flush`**:
  ```bash
  python3 -m adapters.agent_bus_client flush \
      --spool-db .local/spool.db \
      --store /var/agent-bus/store \
      --cred /path/to/agent.cred.json
  ```
- **`rpc --stdin`**:
  Reads the JSON request directly from `sys.stdin.read().strip()`, supporting automated headless piping over SSH.

---

## 5. Verification of Negative Security Cases

Independent verification was conducted for all required security and negative failure paths:

1. **Head Credential Rejection**:
   - Spooling payloads containing `head.cred`, `head_token`, `head_cred`, `{"head": {"token": "..."}}`, or plain text mentions of `head.cred` in message bodies raises `ValueError: head_cred_inheritance_rejected`.
   - Verified that zero records are inserted into SQLite when credential leaks are rejected.
2. **Idempotency Key Conflict**:
   - Spooling a message with an identical idempotency key but differing payload (`body` or `data`) raises `IdempotencyConflict`.
3. **Transport Disconnect Fail-Closed Isolation**:
   - Simulated transport failure (`ConnectionError: Simulated SSH / network socket disconnect`) during flush:
     - Message 1 delivered and marked `status='delivered'`.
     - Message 2 threw `ConnectionError`.
     - Message 3 was never attempted.
     - Spool retained Message 2 and Message 3 in `status='pending'`.
     - Upon simulated network recovery, second flush cleanly delivered Message 2 and Message 3 in sequence.

---

## 6. Test Execution Results & Command Output

### 6.1 Unit Test Execution (`test_agent_bus_client.py`)

Command:
```bash
python3 -m pytest /home/alexey/git/agent-coordination/tests/test_agent_bus_client.py -v --override-ini=addopts=""
```

Output:
```
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.1.1, pluggy-1.6.0 -- /usr/bin/python3
cachedir: .pytest_cache
rootdir: /home/alexey/git/agent-coordination
configfile: pyproject.toml
plugins: anyio-4.12.1, opik-2.2.54
collecting ... collected 12 items                                                             

tests/test_agent_bus_client.py::test_enroll_creates_sessionless_identity_and_mode_0600_cred PASSED [  8%]
tests/test_agent_bus_client.py::test_send_and_poll_lifecycle PASSED      [ 16%]
tests/test_agent_bus_client.py::test_reply_and_ack_durable_cursor PASSED [ 25%]
tests/test_agent_bus_client.py::test_reject_head_cred_inheritance PASSED [ 33%]
tests/test_agent_bus_client.py::test_duplicate_idempotency_key PASSED    [ 41%]
tests/test_agent_bus_client.py::test_rpc_dispatch_interface PASSED       [ 50%]
tests/test_agent_bus_client.py::test_cli_subcommands_headless_execution PASSED [ 58%]
tests/test_agent_bus_client.py::test_offline_spool_stores_and_enforces_cred_protection PASSED [ 66%]
tests/test_agent_bus_client.py::test_offline_spool_flush_fifo_lifecycle_and_dedup PASSED [ 75%]
tests/test_agent_bus_client.py::test_offline_spool_flush_fails_closed_on_connection_error_without_dropping PASSED [ 83%]
tests/test_agent_bus_client.py::test_build_typed_ssh_command_stdin_framing PASSED [ 91%]
tests/test_agent_bus_client.py::test_cli_spool_and_flush PASSED          [100%]

============================== 12 passed in 3.50s ==============================
```

### 6.2 Full Repository Test Suite

Command:
```bash
python3 -m pytest /home/alexey/git/agent-coordination/tests -q --override-ini=addopts=""
```

Output:
```
89 passed in 18.64s
```

All 89 tests across the repository pass with zero regressions.

---

## 7. Confirmation of Peer Boundaries & Invariants

1. **Peer Dirty Invariant Diff SHA**:
   ```bash
   git diff HEAD -- adapters/windows_client.py coordination/TASKS.json coordination/ssh_relay.py tests/test_offline_network.py tests/test_ssh_relay.py | sha256sum
   ```
   Output:
   ```
   8c9f88b85d05deb21b7d732ad6f03499022bde7bcd74c456a56c2fd7f67c94aa  -
   ```
   Matches the expected invariant SHA-256 hash.

2. **Core `agent-bus` Integrity**:
   - `git diff HEAD -- agent_bus` produces zero diff (100% clean).

3. **Supervision Integrity**:
   - `git diff HEAD -- scripts/supervision` produces zero diff (100% clean).

4. **Working Tree Cleanliness**:
   Only the 5 authorized peer files remain dirty in working tree; no uncommitted changes were introduced in `adapters/agent_bus_client.py` or `tests/test_agent_bus_client.py`.

---

## 8. Definitive Independent Verdict & Sign-off

- **Verdict**: **ACCEPT**
- **Assessment**: The implementation of `OfflineSpool`, durable FIFO retry semantics, fail-closed credential protection, and typed SSH stdin JSON-RPC execution under Directive C2981 is technically robust, thoroughly tested, and preserves all peer boundaries and system invariants.
- **Next Action**: Project Head may proceed with downstream integration of the offline spool and typed SSH transport into the Windows client adapter and cross-computer coordination workflows.
