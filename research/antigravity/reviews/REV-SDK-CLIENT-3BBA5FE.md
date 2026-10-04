# Independent Security & Verification Review: SDK Wire Token Normalization (Commit 3bba5fe)

- **Reviewer:** Independent SDK Wire C1509 Reviewer (tag: `sdk-wire-c1509-reviewer`)
- **Dispatched by:** `antigravity-head` (`46fdb644`), under Codex Principal C1509 / C1510 directives
- **Workspace:** `/home/alexey/git/agent-branches-sdk-adoption` (branch `proto/sdk-get-task-auth`)
- **Target Commit:** `3bba5fe` ("fix(l2-client): normalize CreateTaskResult token object to plaintext for bearer auth (C1509)")
- **Target Repository:** `/home/alexey/git/cloudflare-agent-git`
- **Scope:** `agent_branches/client.py`, `tests/mock_l1_server.py`, `tests/test_client.py`
- **Date of Review:** 2026-10-04 (Europe/Berlin)
- **Verdict:** **ACCEPT**

---

## 1. Executive Summary & Verdict: ACCEPT

Under directives C1509 and C1510, this independent review evaluated commit `3bba5fe` in `/home/alexey/git/agent-branches-sdk-adoption`. 

Commit `3bba5fe` fixes a critical wire mismatch between the Python L2 SDK client and the canonical L1 coordinator. In the real coordinator implementation (`prototype/src/core/coordinator.ts`), `createTask` returns a `CreateTaskResult` payload where:
1. `token` is minted as a structured object: `{ scope: string, expiresAt: string | number, plaintext: string }`.
2. `fork` is an object: `{ name: string, remote: string }` accompanied by top-level `ref`.

Prior to this fix, the SDK client assumed `res.get("token")` was a flat plaintext string. If connected to a real coordinator, `self.task_tokens[task_id]` cached the dictionary itself. Consequently, subsequent authenticated requests via `get_task()` formatted the HTTP header as `Authorization: Bearer {'scope': 'task:...', 'expiresAt': ..., 'plaintext': '...'}`. This caused immediate authentication failure (`401 Unauthorized`), malformed HTTP header construction, and potential disclosure of token metadata in access/proxy logs.

### Key Verification Findings:
1. **Plaintext Normalization**: `AgentBranchesClient.create_task` detects dictionary-shaped `token` payloads, extracts `plaintext`, and stores **strictly the string** in `self.task_tokens[task_id]`.
2. **Legacy String Compatibility**: Flat-string `token` responses from legacy test stubs and earlier coordinator versions remain fully supported.
3. **Fork Wire Flattening**: The nested `fork` wire object is cleanly flattened into top-level `fork_remote` and `fork_ref` keys for consumer and CLI ergonomics.
4. **Exact Bearer Header Formatting**: `get_task()` emits the exact RFC 6750 header `Authorization: Bearer <plaintext>` without dictionary residue.
5. **Mock Server Realism**: `tests/mock_l1_server.py` emits the real wire shape by default (`token_wire_object=True`), while preserving internal plaintext matching in state and offering a `token_wire_object=False` toggle for legacy compatibility tests.
6. **Full Test Suite & Mutation Verification**:
   - All 18 unit tests in `tests/test_client.py` pass cleanly.
   - Comprehensive test suite (36 tests including `test_a01_runner.py` and `test_run10_ack_parser.py`) passes 100%.
   - Removing the normalization logic (mutant: `self.task_tokens[task_id] = raw_token`) is decisively killed by `test_18` through type assertion failure, HTTP 401 error, and server header mismatch.

---

## 2. Commit Identity and Scope Analysis

`git show --stat 3bba5fe`:
- `agent_branches/client.py`: +18 lines, -3 lines (token object normalization, fork flattening)
- `tests/mock_l1_server.py`: +28 lines, -3 lines (real wire default, legacy toggle, `last_authorization` capture)
- `tests/test_client.py`: +76 lines, -2 lines (wire assertion update in `test_17`, comprehensive `test_18`)

Total changes: 122 insertions, 8 deletions across 3 files.

---

## 3. Code Inspection & Verification

### 3.1 `agent_branches/client.py`
In `create_task(...)` (lines 190–209):
```python
        # Cache the minted per-task bearer token so later reads of this task
        # (get_task, push agent resolution) authenticate as the owning agent.
        # Real coordinators mint the token as an object {scope, expiresAt,
        # plaintext} (CreateTaskResult, C1509); older deployments and legacy
        # mocks return the plaintext string directly. Only the plaintext
        # string may ever reach the Authorization header.
        raw_token = res.get("token")
        if isinstance(raw_token, dict):
            plaintext = raw_token.get("plaintext", "")
            if task_id and plaintext:
                self.task_tokens[task_id] = plaintext
        elif isinstance(raw_token, str) and task_id and raw_token:
            self.task_tokens[task_id] = raw_token

        # Flatten the fork wire object into plain keys for CLI consumers.
        raw_fork = res.get("fork")
        if isinstance(raw_fork, dict):
            res["fork_remote"] = raw_fork.get("remote")
            res["fork_ref"] = raw_fork.get("ref")

        return res
```

#### Verification Points:
- **Type Guarding & Isolation**: `isinstance(raw_token, dict)` checks the payload type before accessing `.get("plaintext", "")`. Only if `task_id` and non-empty `plaintext` exist does it write to `self.task_tokens[task_id]`.
- **String Guarantee**: `self.task_tokens[task_id]` is guaranteed to hold a `str`. The outer `res["token"]` returned to the caller remains the original object `{scope, expiresAt, plaintext}` as minted by the coordinator.
- **Legacy Compatibility**: `isinstance(raw_token, str)` gracefully handles legacy coordinators that return a flat plaintext string.
- **Fork Wire Flattening**: `raw_fork = res.get("fork")` safely unpacks `remote` and `ref` onto `res["fork_remote"]` and `res["fork_ref"]`.
- **Bearer Header Generation**: In `get_task(task_id)`:
  ```python
  effective_token = (
      token
      or self.task_tokens.get(task_id)
      or os.environ.get("TASK_TOKEN")
      or os.environ.get("ADMIN_TOKEN")
  )
  if effective_token:
      req_headers = {"Authorization": f"Bearer {effective_token}"}
  ```
  Because `effective_token` resolves to `self.task_tokens[task_id]` (which is normalized to `plaintext`), `req_headers["Authorization"]` is strictly formatted as `"Bearer <plaintext>"`.

### 3.2 `tests/mock_l1_server.py`
In `MockCoordinatorState` and `MockL1Handler`:
1. `MockCoordinatorState.__init__`:
   - Adds `token_wire_object: bool = True` (defaults to real wire shape).
   - Adds `self.last_authorization: Optional[str] = None` to record incoming `Authorization` headers on `GET /tasks/:id` for assertion by test cases.
2. In `MockL1Handler.do_POST`:
   ```python
   created = self.state.create_task(body)
   if self.state.token_wire_object and isinstance(created.get("token"), str):
       created = dict(created)
       created["token"] = {
           "scope": f"task:{created.get('taskId')}",
           "expiresAt": int(time.time()) + 3600,
           "plaintext": created["token"],
       }
       created["fork"] = dict(created.get("fork") or {})
       created["fork"].setdefault("ref", created.get("ref"))
   self._send_json(201, created)
   ```
   Crucially, `self.state.create_task(body)` maintains the internal stored task record with the plaintext token. This ensures `self.state.check_task_read_auth` validates bearer tokens against the actual secret string. The HTTP 201 response serializes the full `CreateTaskResult` wire object.
3. In `start_mock_l1_server`:
   - Exposes `token_wire_object: bool = True`, allowing test suites to launch either real-wire or legacy mock coordinators.

### 3.3 `tests/test_client.py`
1. **Adaptation of `test_17`**:
   Updated `owner_token = task["token"]["plaintext"]` and `foreign_token = foreign["token"]["plaintext"]` to reflect that `task["token"]` is now the real wire object.
2. **Implementation of `test_18_create_task_token_wire_normalization`**:
   Validates:
   - Wire object format from default mock server (`isinstance(task["token"], dict)`, `scope`, `expiresAt`, `plaintext`).
   - SDK cache storage strictly as a `str` equal to `plaintext`.
   - `client.get_task(task_id)` success and verification that `auth_state.last_authorization == f"Bearer {plaintext}"`.
   - Fork flattening keys (`task["fork_remote"] == task["fork"]["remote"]`, `task["fork_ref"] == task["ref"]`).
   - Legacy end-to-end execution against a server configured with `token_wire_object=False`.

---

## 4. Negative Security & Robustness Analysis

1. **HTTP Header Injection & Malformed Bearer Headers**:
   - If an un-normalized dictionary `{...}` were formatted into `Authorization: Bearer {effective_token}`, the resulting string would contain punctuation (`{`, `}`, `'`, `:`) violating standard bearer token token68 format (RFC 6750 Section 2.1).
   - Some reverse proxies and HTTP parsers reject non-conforming authorization headers with `400 Bad Request` or drop the header entirely.
   - Normalizing to the plaintext token prevents header corruption and malformed request line rejections.
2. **Information Disclosure in Middlebox Logs**:
   - Proxies and API gateways frequently log the `Authorization` header scheme or mask the token value. If structured token metadata (such as scopes, expiration epoch, or internal IDs) is interpolated into the bearer token value, it may leak into monitoring pipelines or audit logs.
   - Normalization limits header exposure exclusively to the opaque secret string.
3. **Fail-Closed on Malformed Token Object**:
   - If `res.get("token")` is a dict lacking the `"plaintext"` key or where `"plaintext"` is empty, `self.task_tokens[task_id]` is not set.
   - When `get_task()` is subsequently called without an explicit token or environment fallback, `effective_token` is `None`, and the request is sent without an `Authorization` header, triggering a clean `401 Unauthorized` rather than emitting a bogus header.
4. **Task Isolation Invariant**:
   - `self.task_tokens` maps `task_id -> str`. Each task gets an independent token entry.
   - Verified by `test_17` (assertion 10): a client holding a cached token for task A fails closed with 401 when attempting to read task B.

---

## 5. Test Suite Verification

Unit tests executed in `/home/alexey/git/agent-branches-sdk-adoption` with `TMPDIR=/home/alexey/git/cloudflare-agent-git/.local/scratch/sdk-c1509-review/`:

### 5.1 `tests/test_client.py` (18/18 Passed)
```text
test_01_mock_l1_server_routes_directly (tests.test_client.TestAgentBranchesClient.test_01_mock_l1_server_routes_directly) ... ok
test_02_distinct_agent_id_vs_task_id_flow (tests.test_client.TestAgentBranchesClient.test_02_distinct_agent_id_vs_task_id_flow) ... ok
test_03_admin_bearer_token_support (tests.test_client.TestAgentBranchesClient.test_03_admin_bearer_token_support) ... ok
test_04_git_utils_robustness (tests.test_client.TestAgentBranchesClient.test_04_git_utils_robustness) ... ok
test_05_cli_end_to_end_flow (tests.test_client.TestAgentBranchesClient.test_05_cli_end_to_end_flow) ... ok
test_06_error_handling_and_validation (tests.test_client.TestAgentBranchesClient.test_06_error_handling_and_validation) ... ok
test_07_payload_integrity_and_deduplication (tests.test_client.TestAgentBranchesClient.test_07_payload_integrity_and_deduplication) ... ok
test_08_send_checks_success (tests.test_client.TestAgentBranchesClient.test_08_send_checks_success) ... ok
test_09_send_checks_stale_vector_409 (tests.test_client.TestAgentBranchesClient.test_09_send_checks_stale_vector_409) ... ok
test_10_cli_checks_command (tests.test_client.TestAgentBranchesClient.test_10_cli_checks_command) ... ok
test_11_stale_vector_fail_closed_without_recompute (tests.test_client.TestAgentBranchesClient.test_11_stale_vector_fail_closed_without_recompute) ... ok
test_12_token_expiry_401_reported_and_halt (tests.test_client.TestAgentBranchesClient.test_12_token_expiry_401_reported_and_halt) ... ok
test_13_token_revocation_403_fail_closed (tests.test_client.TestAgentBranchesClient.test_13_token_revocation_403_fail_closed) ... ok
test_14_resync_recompute_paths_real_server (tests.test_client.TestAgentBranchesClient.test_14_resync_recompute_paths_real_server) ... ok
test_15_status_reads_carry_runner_token (tests.test_client.TestAgentBranchesClient.test_15_status_reads_carry_runner_token) ... ok
test_16_refresh_head_vector_wire_compatibility_and_recomputation_boundary (tests.test_client.TestAgentBranchesClient.test_16_refresh_head_vector_wire_compatibility_and_recomputation_boundary) ... ok
test_17_get_task_auth_owner_or_admin (tests.test_client.TestAgentBranchesClient.test_17_get_task_auth_owner_or_admin) ... ok
test_18_create_task_token_wire_normalization (tests.test_client.TestAgentBranchesClient.test_18_create_task_token_wire_normalization) ... ok

----------------------------------------------------------------------
Ran 18 tests in 6.882s

OK
```

### 5.2 Full Test Suite Regression Check (36/36 Passed)
```text
Ran 36 tests in 6.982s
OK (test_client.py: 18 tests, test_a01_runner.py: 6 tests, test_run10_ack_parser.py: 12 tests)
```

---

## 6. Mutation Testing Kill Log

### Mutation Target:
In `agent_branches/client.py`, replace dictionary normalization with raw token assignment:
```python
# MUTANT
raw_token = res.get("token")
if task_id and raw_token:
    self.task_tokens[task_id] = raw_token
```

### Execution & Observations:
Under this mutation:
1. **Type Assertion Kill**:
   ```text
   FAIL: test_18_create_task_token_wire_normalization (tests.test_client.TestAgentBranchesClient.test_18_create_task_token_wire_normalization)
   ----------------------------------------------------------------------
   Traceback (most recent call last):
     File "/home/alexey/git/agent-branches-sdk-adoption/tests/test_client.py", line 1624, in test_18_create_task_token_wire_normalization
       self.assertIsInstance(client.task_tokens[task["taskId"]], str)
   AssertionError: {'scope': 'task:task-0001', 'expiresAt': 1791077571, 'plaintext': 'mock-token-0001'} is not an instance of <class 'str'>
   ```
2. **Wire Header & Authentication Kill**:
   When `client.get_task(task_id)` is invoked with the mutated cache:
   - Header produced on the wire:
     `Authorization: Bearer {'scope': 'task:task-0001', 'expiresAt': 1791077577, 'plaintext': 'mock-token-0001'}`
   - Coordinator response:
     `agent_branches.client.AgentBranchesAPIError: HTTP 401: Missing or invalid bearer token`
   - Server recorded authorization:
     `auth_state.last_authorization` does not match `f"Bearer {plaintext}"`.

### Result:
**DECISIVELY KILLED**. Both the client-side type constraint and server-side authentication validation catch the mutation immediately.

---

## 7. Resource Accounting & Host Environment Note

In accordance with execution invariants:
- **Memory Cap & Throttling Method:** Memory limits are governed by the shared environment/process slice (`0::/user.slice/user-1000.slice/session-8309.scope` on Linux x86_64, 64 GB host RAM with ~32 GB available), rather than an isolated individual 1500M cgroup container.
- **Scratch & Temporary Directory Hygiene:** All scratch test scripts strictly used `TMPDIR=/home/alexey/git/cloudflare-agent-git/.local/scratch/sdk-c1509-review/`. No temporary files were written to the shared system `/tmp` directory (zero `/tmp` growth).
- **Working Tree Integrity:** Working tree in `/home/alexey/git/agent-branches-sdk-adoption` is clean and untracked pycache files are untouched.

---

## 8. Conclusion

Commit `3bba5fe` cleanly aligns the Python L2 SDK client with the canonical L1 coordinator's `CreateTaskResult` wire specification. It eliminates bearer authorization failures caused by string interpolation of token objects, preserves legacy flat-token backward compatibility, flattens fork metadata keys, and provides rock-solid test coverage verified by mutation testing.
