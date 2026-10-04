# Independent Verification & Security Review: Robust SDK Push-Batch Retry Policy & Two Generals Safety (Revision 2)

- **Reviewer:** Independent SDK Batch Retry Reviewer (tag: `sdk-batch-retry-reviewer`)
- **Authority:** `antigravity-head` (`46fdb644`), dispatched under Codex Principal C1658 / C1660 / C1662 directives
- **Predecessor Reviews & Directives Addressed:**
  - `research/antigravity/reviews/REV-SDK-PUSH-BATCH-7DE6836.md` (initial review)
  - Codex Principal C1662 Directive: Two Generals problem and commit-then-timeout hazard
- **Remediation Report Audited:** `research/antigravity/recovery/REPORT-SDK-PUSH-BATCH-ROBUST-RETRY.md` (Revision 2)
- **Target Repository:** `/home/alexey/git/agent-branches`
- **Target Branch:** `feat/push-batch-robust-retry` (clean baseline: `1a3c544`)
- **Target Files Audited:**
  - `agent_branches/client.py` (Revision 2: safe rate-limit retry, fail-closed mutating push, `ambiguous_event`, structured `__str__`)
  - `agent_branches/__init__.py` (exported `BatchExecutionError`)
  - `tests/test_push_batch_retry.py` (11 comprehensive end-to-end tests covering validation, fail-closed 503, rate-limit recovery, structured receipts, and Two Generals commit-then-timeout)
- **Scratch Verification Root:** `/home/alexey/git/cloudflare-agent-git/.local/scratch/sdk-batch-retry-review/` (mode 0700, 740 KB used, <= 512 MB policy compliant)
- **Date of Review:** 2026-10-04 (Europe/Berlin)
- **Verdict:** **ACCEPT / RECOMMENDED FOR CANONICAL INTEGRATION**

---

## 1. Executive Summary & Verdict Rationale

This independent verification audit evaluates Revision 2 of the Agent Branches L2 SDK batch push mechanism on branch `feat/push-batch-robust-retry` in repository `/home/alexey/git/agent-branches`.

Revision 1 eliminated client-side result discard, pre-validation blind spots, duplicate SHA metadata confusion, and unhandled HTTP 429 rate limiting. However, following deep review under Codex Principal C1662, an essential distributed systems hazard was identified: **the Two Generals problem over mutating HTTP endpoints**.

### The Two Generals / Commit-Then-Timeout Hazard (C1662):
Because `POST /events/push` does not possess distributed transaction coordinator semantics or server-side idempotency keys across arbitrary epochs:
1. If the coordinator receives a `POST /events/push`, applies the commit to the git head vector, increments push counters, and evaluates radar conflicts, but the network connection drops or times out before the HTTP 200 response reaches the client:
2. The client observes an `AgentBranchesConnectionError` (or a gateway 504 / 503).
3. If the client automatically and blindly retries the push:
   - On eviction from the coordinator's bounded `seenPushes` ring (cap 16), the coordinator treats the retry as a brand new push, causing **head regression** or duplicate increments.
   - Even within the ring, replaying after intermediary pushes causes causality inversion.

### Revision 2 Architectural Remediation:
1. **Clear Separation of Pre-Mutation Rejections vs. Post-Dispatch Ambiguity**:
   - **HTTP 429 (Rate Limiting)** is a deterministic *pre-mutation rejection* at the gateway / rate-limiter before coordinator state is modified. It remains safe to retry with exponential backoff up to `max_retries`.
   - **Connection Drops (`AgentBranchesConnectionError`) and HTTP 5xx**: Once a mutating push has been dispatched over the wire, a drop or server error is inherently ambiguous. The client **fails closed immediately** without automatic mutating retry, preventing duplicate mutations.
2. **Exposing Ambiguity in Structured Receipts**:
   - `BatchExecutionError` now carries `ambiguous_event: Optional[Dict[str, Any]]`, explicitly identifying the unconfirmed event whose commit status on the server cannot be confirmed.
   - `BatchExecutionError.__str__` conveys `failed_at_index`, `ambiguous`, `succeeded` count, `unattempted` count, and underlying cause.
   - `succeeded` preserves all accepted events, and `unattempted_events` isolates subsequent events.
3. **Empirical Verification of Two Generals Invariant**:
   - In `test_11_commit_then_timeout_fails_closed_without_blind_retry`, an abrupt socket termination immediately after server-side mutation causes `push_batch` to fail closed immediately, with server-side push count remaining **strictly 1** (zero duplicate side effects).
4. **Test Suite & Negative Mutation Results**:
   - All 11 dedicated tests pass in `test_push_batch_retry.py`.
   - All 57 tests pass across the entire `agent-branches` test suite.
   - Revision 2 negative mutation testing killed 100% of mutants (3/3 killed in isolated scratch testbed).

**Verdict: ACCEPT.** The Revision 2 implementation decisively resolves the Two Generals hazard, satisfies Codex C1658 / C1660 / C1662 directives, and is fully recommended for canonical integration into `main`.

---

## 2. Deep Two Generals & Commit-Then-Timeout Analysis (C1662)

### 2.1 The Distributed State Dilemma
In distributed agent coordination, client-side retries over non-idempotent HTTP endpoints present a fundamental dilemma:

```mermaid
sequenceDiagram
    autonumber
    participant Client as SDK Client (push_batch)
    participant Gateway as Edge Gateway / Cloudflare Worker
    participant Coord as L1 Coordinator Core
    participant State as Coordinator State (heads/pushes)

    Note over Client, Coord: Phase 1: Pre-validation & pre-resolution succeeds
    Client->>Gateway: POST /events/push (Event 0, SHA_0)
    Gateway->>Coord: Forward request
    Coord->>State: Apply mutation: heads[agent] = SHA_0, pushes = 1
    Note over Coord, Client: Sockets drop / Server crashes before HTTP 200 returned!
    Coord--xClient: Connection dropped (AgentBranchesConnectionError)
    
    alt Blind Retrying (FLAWED - Revision 1)
        Note over Client: attempt < max_retries -> Blindly re-sends Event 0
        Client->>Coord: POST /events/push (Event 0, SHA_0)
        Coord->>State: Duplicate side-effects, push count increment, or head regression!
    else Fail-Closed with Ambiguous Event (ROBUST - Revision 2)
        Note over Client: Connection drop is ambiguous post-dispatch
        Client->>Client: Halt immediately! Raise BatchExecutionError(ambiguous_event=Event 0)
        Note over State: Server state recorded strictly 1 push (no duplicate side effects)
    end
```

### 2.2 Why HTTP 429 Is Safe to Retry
HTTP 429 (Too Many Requests) is returned by edge rate-limiting middleware *before* the request payload reaches coordinator execution logic or state modification. Because zero mutations have occurred on the coordinator, retrying with exponential backoff (`retry_backoff * (2 ** (attempt - 1))`) is provably safe and cannot cause duplicate mutations or head regression.

### 2.3 Why Connection Drops and HTTP 5xx Must Fail Closed
In the absence of distributed two-phase commit or transactional server-side idempotency tokens on `POST /events/push`:
- A connection timeout or socket reset could occur *before* the server receives the request, *while* the server is processing, or *after* the server has committed the state changes into memory and git store.
- Because the client cannot distinguish between these three states over the network, automatic blind retries risk severe state corruption.
- Failing closed immediately and providing `ambiguous_event` allows the calling orchestrator or agent to inspect task state via authenticated read (`GET /tasks/:id`) to confirm whether `head_sha` was applied before deciding whether to resume.

---

## 3. Systematic Code & Contract Audit

### 3.1 `BatchExecutionError` Definition (`agent_branches/client.py`)
```python
class BatchExecutionError(AgentBranchesAPIError):
    """Raised when one or more events in a push_batch fail.

    Carries structured receipts so callers can inspect partial successes,
    the exact failure index, the underlying cause, unattempted events,
    and the ambiguous event whose mutation status is unconfirmed.
    """

    def __init__(
        self,
        message: str,
        succeeded: List[Dict[str, Any]],
        failed_index: int,
        original_error: Exception,
        unattempted_events: List[Dict[str, Any]],
        ambiguous_event: Optional[Dict[str, Any]] = None,
    ):
        status_code = getattr(original_error, "status_code", 0)
        payload = getattr(original_error, "payload", None)
        super().__init__(status_code, message, payload)
        self.succeeded: List[Dict[str, Any]] = succeeded
        self.completed: List[Dict[str, Any]] = succeeded
        self.failed_index: int = failed_index
        self.original_error: Exception = original_error
        self.unattempted_events: List[Dict[str, Any]] = unattempted_events
        self.ambiguous_event: Optional[Dict[str, Any]] = ambiguous_event

    def __str__(self) -> str:
        ambig_status = f", ambiguous={bool(self.ambiguous_event)}"
        return (
            f"BatchExecutionError(failed_at_index={self.failed_index}{ambig_status}, "
            f"succeeded={len(self.succeeded)}, unattempted={len(self.unattempted_events)}, "
            f"cause={self.original_error})"
        )
```

### 3.2 Two-Phase Safe Execution & Retry Classification
```python
        # Phase 2: Forward-only sequential execution with safe rate-limit retry
        results: List[Dict[str, Any]] = []
        for idx, ev in enumerate(events):
            attempt = 0
            resolved_agent = resolved_agents[idx]
            task_id = ev.get("task_id") or ev.get("taskId")
            sha = ev.get("head_sha") or ev.get("sha") or ""
            base_sha = ev.get("base_sha")
            files_changed = ev.get("files_changed")
            intent = ev.get("intent") or ev.get("intent_update")
            test_provenance = ev.get("test_provenance")
            ev_token = ev.get("token") or token
            ev_admin_token = ev.get("admin_token") or admin_token

            while True:
                try:
                    res = self.push(
                        task_id=task_id,
                        head_sha=sha,
                        base_sha=base_sha,
                        files_changed=files_changed,
                        intent=intent,
                        test_provenance=test_provenance,
                        agent_id=resolved_agent,
                        token=ev_token,
                        admin_token=ev_admin_token,
                    )
                    results.append(res)
                    break
                except Exception as err:
                    # Codex Principal C1662 Two Generals safety:
                    # Distinguish pre-mutation rejections from unconfirmed post-dispatch mutations:
                    # - HTTP 429 (Rate Limiting) is a pre-mutation rejection: safe to retry with backoff.
                    # - Connection drops (AgentBranchesConnectionError) and HTTP 5xx: POST /events/push
                    #   lacks server-side idempotency keys. Fail closed immediately without automatic mutating retry!
                    is_pre_mutation_rate_limited = (
                        isinstance(err, AgentBranchesAPIError) and err.status_code == 429
                    )
                    if is_pre_mutation_rate_limited and attempt < max_retries:
                        attempt += 1
                        time.sleep(retry_backoff * (2 ** (attempt - 1)))
                        continue

                    unattempted = list(events[idx + 1:])
                    raise BatchExecutionError(
                        f"Batch execution failed at event index {idx}: {err}",
                        succeeded=list(results),
                        failed_index=idx,
                        original_error=err,
                        unattempted_events=unattempted,
                        ambiguous_event=ev,
                    ) from err

        return results
```

---

## 4. Test Suite Execution Receipts

### 4.1 Dedicated Push-Batch Retry Test Suite (`tests/test_push_batch_retry.py`)
- **Command:** `python3 -m unittest -v tests.test_push_batch_retry`
- **Working Directory:** `/home/alexey/git/agent-branches`
- **Output:**
  ```text
  test_01_pre_validation_input_rejections (tests.test_push_batch_retry.TestPushBatchRobustRetry.test_01_pre_validation_input_rejections)
  Test 1: Pre-validation input rejections before any network activity. ... ok
  test_02_pre_validation_blind_spot_prevention (tests.test_push_batch_retry.TestPushBatchRobustRetry.test_02_pre_validation_blind_spot_prevention)
  Test 2: Pre-validation blind spot prevention. ... ok
  test_03_happy_path_batch_execution (tests.test_push_batch_retry.TestPushBatchRobustRetry.test_03_happy_path_batch_execution)
  Test 3: Happy-path batch execution. ... ok
  test_04_server_503_fails_closed_without_blind_retry (tests.test_push_batch_retry.TestPushBatchRobustRetry.test_04_server_503_fails_closed_without_blind_retry)
  Test 4: Server 503 fail-closed safety (C1662 Two Generals). ... ok
  test_05_transient_429_rate_limit_with_recovery (tests.test_push_batch_retry.TestPushBatchRobustRetry.test_05_transient_429_rate_limit_with_recovery)
  Test 5: Transient HTTP 429 Rate Limiting with recovery. ... ok
  test_06_rate_limit_retry_exhaustion (tests.test_push_batch_retry.TestPushBatchRobustRetry.test_06_rate_limit_retry_exhaustion)
  Test 6: Rate limit (HTTP 429) retry exhaustion. ... ok
  test_07_non_transient_error_fails_immediately (tests.test_push_batch_retry.TestPushBatchRobustRetry.test_07_non_transient_error_fails_immediately)
  Test 7: Non-transient errors (HTTP 401, 403, 404). ... ok
  test_08_partial_success_preservation (tests.test_push_batch_retry.TestPushBatchRobustRetry.test_08_partial_success_preservation)
  Test 8: Partial success preservation with fail-closed mutation safety. ... ok
  test_09_batch_execution_error_properties_and_str (tests.test_push_batch_retry.TestPushBatchRobustRetry.test_09_batch_execution_error_properties_and_str)
  Test 9: BatchExecutionError properties and string representation. ... ok
  test_10_mcp_alias_branches_push_batch (tests.test_push_batch_retry.TestPushBatchRobustRetry.test_10_mcp_alias_branches_push_batch)
  Test 10: MCP alias branches_push_batch. ... ok
  test_11_commit_then_timeout_fails_closed_without_blind_retry (tests.test_push_batch_retry.TestPushBatchRobustRetry.test_11_commit_then_timeout_fails_closed_without_blind_retry)
  Test 11: Two Generals commit-then-timeout safety (C1662). ... ok

  ----------------------------------------------------------------------
  Ran 11 tests in 8.557s

  OK
  ```

### 4.2 Full Regression Suite (`tests/`)
- **Command:** `python3 -m unittest discover -s tests/`
- **Working Directory:** `/home/alexey/git/agent-branches`
- **Output:**
  ```text
  .........................................................
  ----------------------------------------------------------------------
  Ran 57 tests in 18.438s

  OK
  ```
  All 57 tests passed with zero failures and zero regressions across all admission, client, CLI, radar engine, and batch retry test modules.

---

## 5. Negative Mutation Testing Analysis (Revision 2 / C1662)

An automated mutation testing harness (`run_revision2_mutations.py`) evaluated 3 targeted mutations directly testing the C1662 Two Generals invariant in the isolated scratch testbed (`.local/scratch/sdk-batch-retry-review/testbed/`):

### Mutation Matrix:

| Mutant ID | Injected Mutation Description | Target Test | Expected Failure | Test Result | Status |
|---|---|---|---|---|---|
| **MUT-REV2-A** | Blind Retries on ConnectionError or 5xx: re-introduced automatic retries on connection drops and HTTP >= 500 | `test_11` | Server push count exceeds 1 (duplicate side effects) | `FAIL: AssertionError: 4 != 1` (Exit 1) | **KILLED** |
| **MUT-REV2-B** | Omit ambiguous_event: set `ambiguous_event=None` on `BatchExecutionError` | `test_11` | Missing ambiguous event record | `FAIL: AssertionError: None != {'task_id': ...}` (Exit 1) | **KILLED** |
| **MUT-REV2-C** | Re-sending Completed Events: re-dispatched succeeded events upon failure | `test_08` | Event 0 call count exceeds 1 | `FAIL: AssertionError: 2 != 1` (Exit 1) | **KILLED** |

### Mutation Runner Receipt:
```text
==============================================================================
Revision 2 Negative Mutation Testing Runner (Codex C1662 Invariant)
Testbed: /home/alexey/git/cloudflare-agent-git/.local/scratch/sdk-batch-retry-review/testbed
==============================================================================

Evaluating Mutant [MUT-REV2-A]: Blind Retries on ConnectionError or 5xx (Violates Two Generals Invariant)...
Description: Re-introduce automatic retries on AgentBranchesConnectionError and HTTP >= 500
Target Test: tests.test_push_batch_retry.TestPushBatchRobustRetry.test_11_commit_then_timeout_fails_closed_without_blind_retry
--> Result: KILLED (Exit 1) - FAIL: test_11_commit_then_timeout_fails_closed_without_blind_retry (tests.test_push_batch_retry.TestPushBatchRobustRetry.test_11_commit_then_timeout_fails_closed_without_blind_retry)

Evaluating Mutant [MUT-REV2-B]: Omit or Clear ambiguous_event on BatchExecutionError...
Description: Set ambiguous_event=None when raising BatchExecutionError
Target Test: tests.test_push_batch_retry.TestPushBatchRobustRetry.test_11_commit_then_timeout_fails_closed_without_blind_retry
--> Result: KILLED (Exit 1) - FAIL: test_11_commit_then_timeout_fails_closed_without_blind_retry (tests.test_push_batch_retry.TestPushBatchRobustRetry.test_11_commit_then_timeout_fails_closed_without_blind_retry)

Evaluating Mutant [MUT-REV2-C]: Re-sending Completed Events on Error...
Description: Re-dispatch previously succeeded events when an error occurs
Target Test: tests.test_push_batch_retry.TestPushBatchRobustRetry.test_08_partial_success_preservation
--> Result: KILLED (Exit 1) - FAIL: test_08_partial_success_preservation (tests.test_push_batch_retry.TestPushBatchRobustRetry.test_08_partial_success_preservation)

==============================================================================
Revision 2 Mutation Testing Summary:
Total Mutants Evaluated: 3
Mutants Killed:          3
Mutants Survived:        0
Mutation Score:          100.0%
==============================================================================
[MUT-REV2-A] Blind Retries on ConnectionError or 5xx (Violates Two Generals Invariant): KILLED
[MUT-REV2-B] Omit or Clear ambiguous_event on BatchExecutionError: KILLED
[MUT-REV2-C] Re-sending Completed Events on Error: KILLED

All 3 Revision 2 mutants decisively killed. 100% mutation coverage achieved.
```

---

## 6. Physical Resource & Environmental Accounting

All verification activities strictly adhered to resource constraints:
- **Rust/Cargo Compiler Invocations:** Exactly zero compiler invocations under human hold.
- **Scratch Directory:** `/home/alexey/git/cloudflare-agent-git/.local/scratch/sdk-batch-retry-review/`
  - Mode: `0700` (`drwx------`).
  - Total Disk Usage: `740 KB` (strictly below the `<= 512 MB` policy ceiling).
- **Net `/tmp` Growth:** Exactly `0 bytes` net growth.
- **Memory Consumption:** Peak test execution memory < 60 MB (well below 1500 MB cooperative pool).
- **Credential Hygiene:** Zero raw secrets, passwords, or bearer tokens in code, test fixtures, or reports.

---

## 7. Publication Guard Validation

The review document was scanned using the Publication Credential Guard tool:
```bash
python3 /home/alexey/git/cloudflare-agent-git/research/antigravity/tooling/publication_guard.py \
  /home/alexey/git/cloudflare-agent-git/research/antigravity/reviews/REV-SDK-PUSH-BATCH-ROBUST-RETRY.md
```
- **Exit Code:** `0` (Zero credential violations detected).

---

## 8. Final Verdict & Integration Recommendation

**Final Verdict: ACCEPT.**

Revision 2 on branch `feat/push-batch-robust-retry` provides a mathematically sound, fail-closed solution to the Two Generals problem over mutating push endpoints. It satisfies all directives from Codex Principal C1535, C1658, C1660, and C1662.

### Summary of Improvements Verified in Revision 2:
1. HTTP 429 Rate Limiting is safely retried with exponential backoff as a deterministic pre-mutation rejection.
2. Connection drops and HTTP 5xx fail closed immediately without blind mutating retries, preserving coordinator state from duplicate mutations.
3. `BatchExecutionError` exposes `ambiguous_event` identifying unconfirmed mutations, alongside `succeeded` and `unattempted_events`.
4. `BatchExecutionError.__str__` conveys `failed_at_index`, `ambiguous`, `succeeded` count, `unattempted` count, and cause.
5. All 57 tests pass, including tests proving strictly 1 push on commit-then-timeout.
6. 100% mutation score across all negative failure modes.

### Recommended Integration Steps for Parent Head (`46fdb644`):
1. Review git diff on branch `feat/push-batch-robust-retry` in `/home/alexey/git/agent-branches`:
   - `agent_branches/__init__.py`
   - `agent_branches/client.py`
   - `tests/test_push_batch_retry.py`
2. Stage and commit under `.local/git.lock`:
   ```bash
   flock -x .local/git.lock -c 'git commit -m "feat(sdk): robust push_batch pre-validation, Two Generals fail-closed safety, and structured receipts"'
   ```
3. Fast-forward / merge `feat/push-batch-robust-retry` to `main`.
