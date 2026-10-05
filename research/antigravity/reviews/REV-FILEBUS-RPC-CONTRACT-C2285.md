# Independent Technical Review: FileBus Remote RPC Dispatch Contract & Envelope Verification (Codex Directives C2285 / C2293)

- **Reviewer**: Independent Challenger Reviewer (`reviewer37`, subagent conversation ID: `37aa1067-8bda-4dde-95b8-7b5bb927bd1f`)
- **Reviewer Identity ID**: `163fa1fb-38ac-47ba-a73c-afe0778fec7d`
- **Authority**: Dispatched by `antigravity-head` (`46fdb644`, conversation ID: `245c7bba-9a7b-45c1-87a7-4537f289f9a5`) under Codex Principal Directives C2285 and C2293; auditing sibling integration codebase under Directives C2162, C2164, C2166, C2214, C2217, C2224, C2226, C2267, C2274, C2285, and C2293; authorized by human cross-computer steering (`experiment/human-cross-computer-product-20261004.txt`).
- **Target Repositories & Snapshots**:
  - Snapshot: `/home/alexey/git/cloudflare-agent-git/.local/scratch/bus-ssh-rpc-snapshot/agent-bus`
  - Integration: `/home/alexey/git/cloudflare-agent-git/.local/scratch/architect06-bus-integration/agent-bus` (commit `23b0742b`)
- **Tested Target CLI Path**: `.local/scratch/bus-ssh-rpc-snapshot/agent-bus/coordination/bus_cli.py` (identical to `.local/scratch/architect06-bus-integration/agent-bus/coordination/bus_cli.py` at commit `23b0742b`)
- **Tested Target CLI SHA256**: `a7a8c37459216f011267a37c52006245c91140474d12dd8006d735e1e5300715`
- **Diagnostic Deliverable**: `research/antigravity/recovery/test_filebus_rpc_contract.py`
  - **SHA256**: `e312ca99fdf6ab071554a0830f06a92d63b68323309516e71cc88c9aedfa7d49`
- **Review Deliverable**: `research/antigravity/reviews/REV-FILEBUS-RPC-CONTRACT-C2285.md`
- **Audit Testbed**: `.local/scratch/reviewer37-contract-check/` (mode `0700`, <= 512 MB, zero net `/tmp` growth)
- **Canonical Repositories Status**: Canonical `/home/alexey/git/agent-bus` and `/home/alexey/git/agent-dashboard` remained strictly read-only throughout this review.
- **Compiler Invariant**: Exactly `0` `cargo` or `rustc` invocations executed during this review interval and audit environment under human hold.
- **Date**: 2026-10-05T04:50:00+02:00 (Europe/Berlin)
- **Status / Verdict**: **BOUNDED ACCEPTANCE (DISPATCH CONTRACT VERIFIED / EXECUTABLE ENVELOPE CONFIRMED)**

---

## 1. Executive Summary & Directive C2285 Motivation

In Directive C2285, Codex Principal identified a critical epistemic divergence between the actual Python dispatcher implementation and an illustrative documentation example in `REPORT-TWOHOST-DESKTOP-HETZNER-RPC.md`:

1. **The Divergence**:
   - In earlier draft documentation of `REPORT-TWOHOST-DESKTOP-HETZNER-RPC.md` (Section 6.1), an illustrative PowerShell snippet demonstrated how a Windows client might stream an RPC JSON envelope over OpenSSH.
   - However, that snippet placed `token` at the envelope root and used `params.to` (mirroring CLI command-line argument syntax) rather than the actual schema required by `bus_cli.py rpc`.
2. **The Actual Dispatch Contract**:
   - The actual `cmd_rpc` dispatcher in `coordination/bus_cli.py` (lines 193–201) indexes `p = req.params` directly:
     ```python
     elif op == "send":
         msg = bus.send(
             sender_id=p["sender_id"],
             token=p["token"],
             recipient_id=p["recipient_id"],
             body=p["body"],
             data=p.get("data"),
             idempotency_key=p.get("idempotency_key"),
         )
     ```
   - Consequently, any envelope with a top-level `token` fails with `KeyError: 'token'`. Any envelope with `params.to` instead of `params.recipient_id` fails with `KeyError: 'recipient_id'`.
3. **Audit Objective (Directive C2285)**:
   - Establish an offline, 100% isolated unit test suite validating the exact parameter dispatch contract across all supported RPC operations (`send`, `inbox`, `reply`, `ack`, `get`, `enroll`).
   - Confirm that invalid schemas fail closed (`ok: false`).
   - Validate the executable contract comparison between pre-correction and post-correction documentation snippets.

---

## 2. Source Code Contract Audit (`cmd_rpc` in `coordination/bus_cli.py`)

A comprehensive audit of lines 154–260 in `coordination/bus_cli.py` reveals the exact protocol specification:

### 2.1 Envelope Structure
The top-level JSON request must parse into an `RpcRequest`:
```json
{
  "request_id": "<string>",
  "op": "<enroll|send|inbox|ack|reply|get|show>",
  "params": { ... }
}
```

### 2.2 Operation Parameter Matrix

| Operation (`op`) | Required Parameters in `params` | Optional Parameters in `params` | Result on Success (`ok: true`) |
| :--- | :--- | :--- | :--- |
| **`enroll`** / **`register`** | `agent_name`, `device_id` | `project_id`, `task_id`, `parent_id`, `parent_token` | Identity public dict with `token` |
| **`send`** | `sender_id`, `token`, `recipient_id`, `body` | `data`, `idempotency_key` | Public `BusMessage` dict |
| **`inbox`** | `identity_id`, `token` | `unread_only` (default: `true`) | List of public `BusMessage` dicts |
| **`ack`** | `identity_id`, `token`, `message_id` | *(none)* | Updated public `BusMessage` dict (`acked_at` populated) |
| **`reply`** | `sender_id`, `token`, `message_id`, `body` | `data`, `idempotency_key` | Public reply `BusMessage` dict (`reply_to` populated) |
| **`get`** / **`show`** | `identity_id`, `token`, `message_id` | *(none)* | Public `BusMessage` dict |

### 2.3 Fail-Closed Exception Handling
When a required parameter is omitted from `params`:
1. Python raises a `KeyError` on dictionary access (`p[...]`).
2. The outer `except Exception as exc:` handler in `cmd_rpc` intercepts the error:
   ```python
   except Exception as exc:
       resp = RpcResponse(
           request_id=req.request_id,
           ok=False,
           error={"code": "internal_error", "message": str(exc)},
       )
   ```
3. The response is serialized with `ok: false` and printed to `stdout` with process exit code `0` (or `1` for framing/empty errors).
4. The client receives clean structured failure framing and fails closed.

---

## 3. Empirical Test Execution Receipts

The test suite [`research/antigravity/recovery/test_filebus_rpc_contract.py`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/recovery/test_filebus_rpc_contract.py) was executed in an isolated scratch testbed (`.local/scratch/reviewer37-contract-check/`):

```text
$ python3 research/antigravity/recovery/test_filebus_rpc_contract.py -v
test_01_send_valid_schema (__main__.TestFileBusRpcDispatchContract.test_01_send_valid_schema)
Confirms that a fully compliant send envelope succeeds and creates a message. ... ok
test_02_send_negative_top_level_token (__main__.TestFileBusRpcDispatchContract.test_02_send_negative_top_level_token)
Confirms that placing 'token' at the envelope root (outside 'params') ... ok
test_03_send_negative_params_to_instead_of_recipient_id (__main__.TestFileBusRpcDispatchContract.test_03_send_negative_params_to_instead_of_recipient_id)
Confirms that using params['to'] instead of params['recipient_id'] ... ok
test_04_send_negative_missing_sender_id (__main__.TestFileBusRpcDispatchContract.test_04_send_negative_missing_sender_id)
Confirms that omitting sender_id fails closed. ... ok
test_05_inbox_valid_and_negative (__main__.TestFileBusRpcDispatchContract.test_05_inbox_valid_and_negative)
Tests valid inbox query and negative missing-token schema. ... ok
test_06_reply_valid_and_negative (__main__.TestFileBusRpcDispatchContract.test_06_reply_valid_and_negative)
Tests valid reply envelope and negative missing-message_id schema. ... ok
test_07_ack_valid_and_negative (__main__.TestFileBusRpcDispatchContract.test_07_ack_valid_and_negative)
Tests valid ack envelope and negative missing-token schema. ... ok
test_08_get_valid_and_negative (__main__.TestFileBusRpcDispatchContract.test_08_get_valid_and_negative)
Tests valid get op and negative missing fields. ... ok
test_09_unsupported_op (__main__.TestFileBusRpcDispatchContract.test_09_unsupported_op)
Tests that unsupported operations fail closed with unsupported_op error code. ... ok
test_10_empty_and_malformed_stdin (__main__.TestFileBusRpcDispatchContract.test_10_empty_and_malformed_stdin)
Tests that empty input or malformed JSON exit code 1 with clean framing error. ... ok
test_11_twohost_report_illustrative_schema_comparison (__main__.TestFileBusRpcDispatchContract.test_11_twohost_report_illustrative_schema_comparison)
Directly evaluates the illustrative PowerShell JSON payload from ... ok

----------------------------------------------------------------------
Ran 11 tests in 4.821s

OK
```

### 3.1 Key Test Outcomes
1. **Valid Envelopes Verified (Tests 1, 5, 6, 7, 8)**:
   - `send`, `inbox`, `reply`, `ack`, and `get` operations execute cleanly with `ok: true`.
   - Message payloads are properly persisted to the isolated store, retrieved, replied to, and marked acknowledged with `acked_at` timestamps.
2. **Top-Level Token Negative Test (Test 2)**:
   - When `token` is placed at the JSON root, `cmd_rpc` raises `KeyError: 'token'`.
   - Response emitted: `{"request_id": "...", "ok": false, "error": {"code": "internal_error", "message": "'token'"}}`.
3. **`params.to` Negative Test (Test 3)**:
   - When `params.to` is provided instead of `params.recipient_id`, `cmd_rpc` raises `KeyError: 'recipient_id'`.
   - Response emitted: `{"request_id": "...", "ok": false, "error": {"code": "internal_error", "message": "'recipient_id'"}}`.
4. **Illustrative Report Schema Comparison (Test 11)**:
   - Evaluated the logical JSON schema payload from `REPORT-TWOHOST-DESKTOP-HETZNER-RPC.md` before vs after the Directive C2285 fix.
   - Pre-fix snippet failed closed with `ok: false` due to missing `sender_id`/`token`/`recipient_id`.
   - Post-fix snippet succeeded with `ok: true` and returned an authentic `message_id`.
   - **Crucial Epistemic Qualification (Directive C2293)**: Test 11 strictly tests the **logical RPC JSON schema** formatting offline under Linux; it did **NOT** execute the native Windows PowerShell runtime environment, native PowerShell cmdlet pipeline (`ConvertTo-Json`), or native Windows OpenSSH (`ssh.exe`) client invocation. Native Windows runtime execution remains independently demarcated.

---

## 4. Documentation & Client Alignment Verification

1. **`REPORT-TWOHOST-DESKTOP-HETZNER-RPC.md` Corrected**:
   - The illustrative PowerShell snippet in Section 6.1 of `REPORT-TWOHOST-DESKTOP-HETZNER-RPC.md` was inspected and verified to contain the correct schema:
     ```powershell
     $rpc_envelope = @{
         request_id = "req-$([guid]::NewGuid().ToString())"
         op = "send"
         params = @{
             sender_id = "01ace831-6d23-4c05-a6df-1a58099aca67"
             token = $dpapi_decrypted_token
             recipient_id = "91d2a63b-fe47-4b53-bee8-2ada24259439"
             body = "..."
             data = @{ ... }
             idempotency_key = "desktop-root-review-4497403a-v1"
         }
     } | ConvertTo-Json -Compress -Depth 10
     ```
   - This snippet is now 100% structurally identical to the validated executable contract.
2. **`windows_rpc_diagnostic_driver.py` Alignment**:
   - The repaired diagnostic driver (`windows_rpc_diagnostic_driver.py`, SHA256: `2fd1be4ef2b9d0437ac47e3635f13212886f2e8c56d0dea94919f057a3205d44`) reuses `SshFileBusClient`.
   - `SshFileBusClient` constructs envelopes that strictly conform to this contract:
     - `send`: passes `sender_id`, `token`, `recipient_id`, `body`.
     - `inbox`: passes `identity_id`, `token`, `unread_only`.
     - `reply`: passes `sender_id`, `token`, `message_id`, `body`.
     - `ack`: passes `identity_id`, `token`, `message_id`.
     - `get`: passes `identity_id`, `token`, `message_id`.
3. **Driver Scope Demarcation (Directive C2293)**:
   - The Windows diagnostic driver `research/antigravity/recovery/windows_rpc_diagnostic_driver.py` (SHA256: `2fd1be4ef2b9d0437ac47e3635f13212886f2e8c56d0dea94919f057a3205d44`) contains client-side regex sanitization/error fallbacks (`sanitize_text`) and CLI option handling.
   - It requires separate, dedicated review before desktop use, and does **NOT** inherit acceptance from these 11 offline RPC dispatch contract tests.
   - Acceptance in this report is strictly confined to the remote `cmd_rpc` dispatch contract and envelope schema of `bus_cli.py` (`a7a8c37459216f011267a37c52006245c91140474d12dd8006d735e1e5300715`).

---

## 5. Invariant Compliance & Governance Receipts

1. **Compiler Invariant**:
   - Exactly **`0`** `cargo` or `rustc` invocations executed during this review interval and audit environment under human hold.
2. **Canonical Repositories Cleanliness**:
   - Canonical `/home/alexey/git/agent-bus` and `/home/alexey/git/agent-dashboard` remained completely untouched and strictly read-only.
3. **Offline & Network Invariant**:
   - Zero model API calls, zero external network calls, zero OpenSSH network connections.
   - All tests executed as purely local Python subprocesses against ephemeral scratch FileBus stores.
4. **Scratch Resource Isolation**:
   - Confined strictly to `.local/scratch/reviewer37-contract-check/` (mode `0700`, size < 100 KB $\le$ 512 MB).
   - Zero net growth on system `/tmp`.
5. **Subagent Git Constraints**:
   - Zero `git commit` or `git push` commands were issued.
6. **Publication Guard Verification**:
   - Verified via `python3 research/antigravity/tooling/publication_guard.py research/antigravity/recovery/test_filebus_rpc_contract.py research/antigravity/reviews/REV-FILEBUS-RPC-CONTRACT-C2285.md` with clean exit code `0`.

---

## 6. Final Audit Verdict

**STATUS: BOUNDED ACCEPTANCE (DISPATCH CONTRACT VERIFIED / EXECUTABLE ENVELOPE CONFIRMED)**

1. **Target Provenance Recorded**: The exact target CLI audited is `coordination/bus_cli.py` (SHA256: `a7a8c37459216f011267a37c52006245c91140474d12dd8006d735e1e5300715`), verified identical between snapshot `.local/scratch/bus-ssh-rpc-snapshot/` and integration branch `feat/typed-ssh-filebus-rpc` (`23b0742b`).
2. **Exact Dispatch Contract Confirmed**: The `rpc` subcommand in `coordination/bus_cli.py` strictly requires `params["sender_id"]`, `params["token"]`, `params["recipient_id"]`, and `params["body"]` for `op == "send"`.
3. **Fail-Closed Verification**: Schemas with top-level tokens or CLI flag naming (`params.to`) fail closed with `ok: false` and `internal_error`.
4. **Illustrative Documentation Aligned**: `REPORT-TWOHOST-DESKTOP-HETZNER-RPC.md` has been verified to reflect the true executable contract.
5. **Test 11 Epistemic Qualification (Directive C2293)**: Test 11 tests the logical RPC JSON schema structure offline under Linux; it did **NOT** execute the native Windows PowerShell runtime invocation, native PowerShell cmdlet pipeline (`ConvertTo-Json`), or native Windows OpenSSH (`ssh.exe`) client invocation. Native Windows runtime execution remains independently demarcated.
6. **Windows Diagnostic Driver Demarcation (Directive C2293)**: Windows diagnostic driver `windows_rpc_diagnostic_driver.py` (SHA256: `2fd1be4ef2b9d0437ac47e3635f13212886f2e8c56d0dea94919f057a3205d44`), which contains regex error fallback logic (`sanitize_text`), requires separate review before desktop use, and does **NOT** inherit acceptance from these 11 offline RPC contract tests.
7. **Test Suite Delivered**: 11/11 tests pass in `research/antigravity/recovery/test_filebus_rpc_contract.py` (SHA256: `e312ca99fdf6ab071554a0830f06a92d63b68323309516e71cc88c9aedfa7d49`).
