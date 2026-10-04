# Independent Verification & Security Review: Agent Branches CLI Batch Receipts (Commit 71dade6)

- **Reviewer:** Independent SDK & CLI Reviewer (tag: `sdk-batch-retry-reviewer` / `ab-cli-batch-reviewer`)
- **Authority:** `antigravity-head` (`46fdb644`), dispatched under Codex Principal C2037 / C2041 / C2046 / C2048 directives
- **Target Repository:** `/home/alexey/git/agent-branches`
- **Target Branch:** `main` (fast-forward merged from `feat/cli-batch-receipts`)
- **Target Commit:** `71dade6e7d824c3de631f43b3ea70e04c82ee8ad` ("docs(cli): clarify push-batch max-retries and retry-backoff as compatibility parameters (C2046)")
- **Predecessor Commit:** `d6d43e9963e5e5ed18c878f5f239ea20151eac2f`
- **Final Pinned File Hashes (Commit 71dade6):**
  - `agent_branches/cli.py` (SHA256: `92bb9686be7a90e9c57a29cdf457946fa254bc55f2630fde2a3537da0c5d6624`)
  - `tests/test_cli_batch.py` (SHA256: `aa5114de459f4d9f50e4798a8ad929fdbc3985dc2359da2f94951df0f139fc86`)
- **Worker Report Audited:** `/home/alexey/git/cloudflare-agent-git/research/antigravity/recovery/REPORT-AB-CLI-BATCH.md`
- **Scratch Verification Root:** `/home/alexey/git/cloudflare-agent-git/.local/scratch/ab-cli-batch-review/` (mode `0700`, 712 KB used, <= 512 MB policy ceiling, `TMPDIR` inside scratch, zero net `/tmp` growth)
- **Date of Review:** 2026-10-04 (Europe/Berlin)
- **Verdict:** **ACCEPT / MERGED TO CANONICAL MAIN**

---

## 1. Executive Summary & Verdict Rationale

This independent verification audit evaluated the CLI batch push implementation on branch `feat/cli-batch-receipts` at commit `d6d43e9963e5e5ed18c878f5f239ea20151eac2f` in repository `/home/alexey/git/agent-branches`.

The deliverable introduces the `push-batch` subcommand to the `agent-branches` CLI tool, exposing the pure fail-closed batch push semantics and Two Generals receipts established in the core SDK (`client.py`, commit `f4f6c3e`).

### Key Audit Findings:
1. **Subcommand Registration & Parameter Parsing**: `agent-branches push-batch` cleanly supports batch input either via `--events-file <file.json>` or repeatable `--event '<json>'` parameters, with full pass-through for `--server`, `--token`, `--admin-token`, `--max-retries`, `--retry-backoff`, and `--json`.
2. **Deterministic Input Validation (Exit Code 2)**: Rejects malformed hex SHAs, missing routing identifiers (`task_id`/`agent_id`), empty batches, unreadable files, and malformed JSON with exit code 2 and **zero network requests** to the coordinator.
3. **Structured Failure Receipts on `BatchExecutionError` (Exit Code 1)**: In the event of a partial batch failure, the CLI halts with exit code 1, emitting an explicit failure receipt containing:
   - Failing event index (`failed_index`)
   - Underlying cause (`original_error`)
   - Ambiguous event whose backend mutation status is unconfirmed (`ambiguous_event`)
   - Demarcated list of succeeded events (`succeeded`, never replayed)
   - Demarcated list of unattempted events (`unattempted_events`)
   - Explicit invocation guarantee: `"Invocation Guarantee: Succeeded events in this batch invocation were committed and not replayed. To resume without duplicate mutation, operator must dispatch only unattempted_events."`
   - Full parity between human-readable text output and `--json` machine-readable output.
4. **Happy-Path Execution (Exit Code 0)**: Dispatches events forward-only, printing the JSON array of accepted push receipts to `stdout` and exiting with code 0.
5. **Two Generals Commit-Then-Timeout Safety**: On socket disconnect immediately following server-side mutation, the CLI fails closed with exit code 1, reports `ambiguous_event`, and issues **strictly zero duplicate pushes** across the network (push count on coordinator remains exactly 1).
6. **Test Suite Verification**: All 4 dedicated CLI batch tests pass (4/4 PASS); all 61 tests across the full `agent-branches` suite pass (61/61 PASS).
7. **Negative Mutation Testing**: 5 targeted mutations against exit codes, receipt formatting, and validation logic were evaluated in an isolated scratch testbed. All 5 mutants were killed (100% mutation score).

**Verdict: ACCEPT.** The implementation satisfies all requirements of Codex Principal C2037 / C2041 directives and is recommended for canonical merge into `main`.

---

## 2. Interface & Contract Verification

| CLI Contract Element | Specification & Invariant | Observed Implementation in `cli.py` | Verification Status |
|---|---|---|---|
| **Subcommand CLI Interface** | `agent-branches push-batch [--events-file <path>] [--event <json>]...` | Registered in `build_parser()`, handles `--events-file` and repeatable `--event` | **PASS** (`test_01`) |
| **Exit Code 2 on Pre-validation Errors** | Malformed SHA, missing task/agent ID, empty list, unreadable files -> exit 2 | Catches `ValueError`, `TypeError`, `OSError`, `json.JSONDecodeError`; prints to stderr, returns 2 | **PASS** (`test_02`) |
| **Zero Network Mutation on Exit Code 2** | Pre-validation rejections must dispatch zero requests to coordinator | Input pre-validation occurs before `self.push(...)`; verified coordinator received 0 calls | **PASS** (`test_02`) |
| **Exit Code 1 on Partial Failure** | `BatchExecutionError` -> exit 1 with structured receipt to stderr | Catches `BatchExecutionError`; formats receipt or JSON payload to stderr, returns 1 | **PASS** (`test_03`) |
| **Receipt Structure** | Must expose failed index, cause, ambiguous event, succeeded, unattempted | `format_batch_error_receipt` and `--json` payload include all structured attributes | **PASS** (`test_03`) |
| **Demarcation Guarantee** | Explicitly state succeeded events are committed and not replayed | Stderr text and JSON contain `"Invocation Guarantee: Succeeded events in this batch invocation were committed and not replayed. To resume without duplicate mutation, operator must dispatch only unattempted_events."` | **PASS** (`test_03`) |
| **Exit Code 0 on Success** | All events accepted -> exit 0 with JSON array to stdout | Prints `json.dumps(results, indent=2)` to stdout, returns 0 | **PASS** (`test_01`) |
| **Two Generals Commit-Then-Timeout** | Connection drop after mutation fails closed with zero duplicate pushes | Catches connection error as `BatchExecutionError(ambiguous_event=...)`, exits 1, push count == 1 | **PASS** (`test_04`) |

---

## 3. Deep Code Inspection (`agent_branches/cli.py`)

### 3.1 Subcommand Parsing & Failure Receipt Formatting
```python
def format_batch_error_receipt(err: BatchExecutionError) -> str:
    """Format structured failure receipt for BatchExecutionError."""
    lines = [
        f"Error: Batch push failed at event index {err.failed_index}",
        f"Underlying cause: {err.original_error}",
        f"Ambiguous event (mutation status unconfirmed): {err.ambiguous_event}",
        f"Succeeded events ({len(err.succeeded)}): {json.dumps(err.succeeded) if err.succeeded else 'none'}",
        f"Unattempted events ({len(err.unattempted_events)}): {json.dumps(err.unattempted_events) if err.unattempted_events else 'none'}",
        "Invocation Guarantee: Succeeded events in this batch invocation were committed and not replayed. To resume without duplicate mutation, operator must dispatch only unattempted_events.",
    ]
    return "\n".join(lines)
```

### 3.2 Handler Implementation `cmd_push_batch()`
```python
def cmd_push_batch(
    args: argparse.Namespace,
    client: Optional[AgentBranchesClient] = None,
    as_json: Optional[bool] = None,
) -> int:
    """Execute push-batch CLI subcommand."""
    if client is None:
        server_url = getattr(args, "server", None)
        client = AgentBranchesClient(server_url=server_url)
    if as_json is None:
        as_json = bool(getattr(args, "json", False))

    events: List[dict] = []

    # Read events from --events-file if specified
    events_file = getattr(args, "events_file", None)
    if events_file:
        try:
            with open(events_file, "r", encoding="utf-8") as f:
                file_content = f.read()
        except OSError as exc:
            print(f"Error reading events file '{events_file}': {exc}", file=sys.stderr)
            return 2

        try:
            file_events = json.loads(file_content)
        except json.JSONDecodeError as exc:
            print(f"Error parsing JSON from events file '{events_file}': {exc}", file=sys.stderr)
            return 2

        if not isinstance(file_events, list):
            print(
                f"Error: events file '{events_file}' must contain a JSON array of event objects",
                file=sys.stderr,
            )
            return 2
        events.extend(file_events)

    # Read events from repeatable --event if specified
    event_strings = getattr(args, "event", None)
    if event_strings:
        for ev_str in event_strings:
            try:
                ev_obj = json.loads(ev_str)
            except json.JSONDecodeError as exc:
                print(f"Error parsing --event JSON '{ev_str}': {exc}", file=sys.stderr)
                return 2

            if not isinstance(ev_obj, dict):
                print(
                    f"Error: --event must be a JSON object, got {type(ev_obj).__name__}",
                    file=sys.stderr,
                )
                return 2
            events.append(ev_obj)

    if not events_file and not event_strings:
        print(
            "Error: either --events-file or at least one --event must be specified",
            file=sys.stderr,
        )
        return 2

    if len(events) == 0:
        print("Error: events list cannot be empty", file=sys.stderr)
        return 2

    max_retries = getattr(args, "max_retries", None)
    if max_retries is None:
        max_retries = 3

    retry_backoff = getattr(args, "retry_backoff", None)
    if retry_backoff is None:
        retry_backoff = 0.05

    token = getattr(args, "token", None)
    admin_token = getattr(args, "admin_token", None)

    try:
        results = client.push_batch(
            events=events,
            token=token,
            admin_token=admin_token,
            max_retries=max_retries,
            retry_backoff=retry_backoff,
        )
    except (ValueError, TypeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except BatchExecutionError as exc:
        if as_json:
            payload = {
                "error": "batch_push_failed",
                "failed_index": exc.failed_index,
                "original_error": str(exc.original_error),
                "ambiguous_event": exc.ambiguous_event,
                "succeeded": exc.succeeded,
                "unattempted_events": exc.unattempted_events,
                "guarantee": "Invocation Guarantee: Succeeded events in this batch invocation were committed and not replayed. To resume without duplicate mutation, operator must dispatch only unattempted_events.",
            }
            print(json.dumps(payload, indent=2), file=sys.stderr)
        else:
            print(format_batch_error_receipt(exc), file=sys.stderr)
        return 1

    print(json.dumps(results, indent=2))
    return 0
```

---

## 4. Test Suite Execution Receipts

### 4.1 Dedicated CLI Batch Test Suite (`tests/test_cli_batch.py`)
- **Command:** `python3 -m unittest -v tests.test_cli_batch`
- **Working Directory:** `/home/alexey/git/agent-branches`
- **Output:**
  ```text
  test_01_happy_path_push_batch_cli (tests.test_cli_batch.TestCLIBatchReceipts.test_01_happy_path_push_batch_cli)
  Test 1: Happy-path push-batch via CLI runner -> exit code 0, outputs accepted events. ... ok
  test_02_input_validation_error_zero_network_pushes (tests.test_cli_batch.TestCLIBatchReceipts.test_02_input_validation_error_zero_network_pushes)
  Test 2: Input validation error -> exit code 2 / error, zero network pushes. ... ok
  test_03_partial_failure_with_batch_execution_error_receipt (tests.test_cli_batch.TestCLIBatchReceipts.test_03_partial_failure_with_batch_execution_error_receipt)
  Test 3: Partial failure with BatchExecutionError -> exit code 1, structured receipt. ... ok
  test_04_commit_then_timeout_ambiguous_mutation_safety (tests.test_cli_batch.TestCLIBatchReceipts.test_04_commit_then_timeout_ambiguous_mutation_safety)
  Test 4: Commit-then-timeout / ambiguous mutation -> exit code 1, zero duplicate pushes. ... ok

  ----------------------------------------------------------------------
  Ran 4 tests in 2.562s

  OK
  ```

### 4.2 Full Regression Suite (`tests/`)
- **Command:** `python3 -m unittest discover -s tests/`
- **Working Directory:** `/home/alexey/git/agent-branches`
- **Output:**
  ```text
  .............................................................
  ----------------------------------------------------------------------
  Ran 61 tests in 21.610s

  OK
  ```
  All 61 tests passed with zero failures and zero regressions across all admission, client, CLI, radar engine, and batch retry test modules.

---

## 5. Negative Mutation Testing Analysis

Negative mutation testing was conducted using `run_cli_batch_mutations.py` in the isolated scratch testbed (`.local/scratch/ab-cli-batch-review/testbed/`):

### Mutation Matrix:

| Mutant ID | Injected Mutation Description | Target Test | Expected Failure | Test Result | Status |
|---|---|---|---|---|---|
| **MUT-CLI-01** | Validation Error Exit Code Mutated (2 -> 1) | `test_02` | Return code mismatch (1 != 2) | `FAIL: AssertionError: 1 != 2` (Exit 1) | **KILLED** |
| **MUT-CLI-02** | BatchExecutionError Exit Code Mutated (1 -> 0) | `test_03` | Return code mismatch (0 != 1) | `FAIL: AssertionError: 0 != 1` (Exit 1) | **KILLED** |
| **MUT-CLI-03** | Omit ambiguous_event from Failure Receipt | `test_03` | Receipt missing ambiguous event header | `FAIL: AssertionError: 'Ambiguous event' not found` (Exit 1) | **KILLED** |
| **MUT-CLI-04** | Bypass Missing Event Arguments Check | `test_02` | Return code mismatch on empty invocation | `FAIL: AssertionError` (Exit 1) | **KILLED** |
| **MUT-CLI-05** | Omit Invocation Demarcation Guarantee from Receipt | `test_03` | Receipt missing invocation guarantee | `FAIL: AssertionError: 'Invocation Guarantee:' not found` (Exit 1) | **KILLED** |

### Mutation Runner Receipt:
```text
================================================================================
Agent Branches CLI Batch Receipts Negative Mutation Testing Runner (C2037)
Testbed: /home/alexey/git/cloudflare-agent-git/.local/scratch/ab-cli-batch-review/testbed
================================================================================

Evaluating Mutant [MUT-CLI-01]: Validation Error Exit Code Mutated (2 -> 1)...
Description: Mutate validation error return code from 2 to 1 in cmd_push_batch
Target Test: tests.test_cli_batch.TestCLIBatchReceipts.test_02_input_validation_error_zero_network_pushes
--> Result: KILLED (Exit 1) - FAIL: test_02_input_validation_error_zero_network_pushes (tests.test_cli_batch.TestCLIBatchReceipts.test_02_input_validation_error_zero_network_pushes)

Evaluating Mutant [MUT-CLI-02]: BatchExecutionError Exit Code Mutated (1 -> 0)...
Description: Mutate BatchExecutionError return code from 1 to 0 in cmd_push_batch
Target Test: tests.test_cli_batch.TestCLIBatchReceipts.test_03_partial_failure_with_batch_execution_error_receipt
--> Result: KILLED (Exit 1) - FAIL: test_03_partial_failure_with_batch_execution_error_receipt (tests.test_cli_batch.TestCLIBatchReceipts.test_03_partial_failure_with_batch_execution_error_receipt)

Evaluating Mutant [MUT-CLI-03]: Omit ambiguous_event from Failure Receipt...
Description: Remove ambiguous_event line from format_batch_error_receipt
Target Test: tests.test_cli_batch.TestCLIBatchReceipts.test_03_partial_failure_with_batch_execution_error_receipt
--> Result: KILLED (Exit 1) - FAIL: test_03_partial_failure_with_batch_execution_error_receipt (tests.test_cli_batch.TestCLIBatchReceipts.test_03_partial_failure_with_batch_execution_error_receipt)

Evaluating Mutant [MUT-CLI-04]: Bypass Missing Event Arguments Check...
Description: Remove missing event arguments validation check in cmd_push_batch
Target Test: tests.test_cli_batch.TestCLIBatchReceipts.test_02_input_validation_error_zero_network_pushes
--> Result: KILLED (Exit 1) - FAIL: test_02_input_validation_error_zero_network_pushes (tests.test_cli_batch.TestCLIBatchReceipts.test_02_input_validation_error_zero_network_pushes)

Evaluating Mutant [MUT-CLI-05]: Omit Invocation Demarcation Guarantee from Receipt...
Description: Remove guarantee string from format_batch_error_receipt
Target Test: tests.test_cli_batch.TestCLIBatchReceipts.test_03_partial_failure_with_batch_execution_error_receipt
--> Result: KILLED (Exit 1) - FAIL: test_03_partial_failure_with_batch_execution_error_receipt (tests.test_cli_batch.TestCLIBatchReceipts.test_03_partial_failure_with_batch_execution_error_receipt)

================================================================================
CLI Batch Receipts Mutation Testing Summary:
Total Mutants Evaluated: 5
Mutants Killed:          5
Mutants Survived:        0
Mutation Score:          100.0%
================================================================================
[MUT-CLI-01] Validation Error Exit Code Mutated (2 -> 1): KILLED
[MUT-CLI-02] BatchExecutionError Exit Code Mutated (1 -> 0): KILLED
[MUT-CLI-03] Omit ambiguous_event from Failure Receipt: KILLED
[MUT-CLI-04] Bypass Missing Event Arguments Check: KILLED
[MUT-CLI-05] Omit Invocation Demarcation Guarantee from Receipt: KILLED

All 5 CLI batch mutants decisively killed. 100% mutation coverage achieved.
```

---

## 6. Physical Resource & Environmental Accounting

All verification activities strictly adhered to resource constraints:
- **Rust/Cargo Compiler Invocations:** Exactly zero compiler invocations under human hold.
- **Scratch Directory:** `/home/alexey/git/cloudflare-agent-git/.local/scratch/ab-cli-batch-review/`
  - Mode: `0700` (`drwx------`).
  - Total Disk Usage: `712 KB` (strictly below the `<= 512 MB` policy ceiling).
- **Net `/tmp` Growth:** Exactly `0 bytes` net growth (`TMPDIR` exported to scratch).
- **Memory Consumption:** Peak test execution memory < 60 MB (well below 1500 MB cooperative pool).
- **Credential Hygiene:** Zero raw secrets, passwords, or bearer tokens in code, test fixtures, or reports.

---

## 7. Publication Guard Validation

The review deliverable was scanned using the Publication Credential Guard tool:
```bash
python3 /home/alexey/git/cloudflare-agent-git/research/antigravity/tooling/publication_guard.py \
  /home/alexey/git/cloudflare-agent-git/research/antigravity/reviews/REV-AB-CLI-BATCH.md
```
- **Exit Code:** `0` (Zero credential violations detected).

---

## 8. Final Verdict & Canonical Acceptance

**Final Verdict: ACCEPT.**

Commit `d6d43e9963e5e5ed18c878f5f239ea20151eac2f` on branch `feat/cli-batch-receipts` fulfills all requirements of Codex Principal C2037 and C2041:
1. `push-batch` CLI interface correctly exposes batch execution with clean exit code demarcation (0 on success, 1 on batch error, 2 on validation failure).
2. Input validation fails closed with zero network requests dispatched.
3. Partial batch failures output comprehensive structured receipts identifying `ambiguous_event`, `succeeded`, `unattempted_events`, and the non-replay invocation guarantee.
4. Two Generals commit-then-timeout safety is preserved with zero duplicate pushes.
5. All 61 tests pass and 100% of negative mutants are killed.

The branch is ready for canonical merge into `main`.

---

## 9. Delta Verification Audit: Commit 71dade6 (C2046 / C2048)

Following initial review of commit `d6d43e9`, Codex Principal C2046 and C2048 requested clarification of operator boundaries:
1. **Invocation Demarcation Clarification:**
   - The phrase `"Guarantee: Succeeded events are clearly demarcated as committed and NEVER replayed."` was refined to:
     `"Invocation Guarantee: Succeeded events in this batch invocation were committed and not replayed. To resume without duplicate mutation, operator must dispatch only unattempted_events."`
   - Explicitly prevents operators from incorrectly assuming an ambient distributed exactly-once guarantee across arbitrary subsequent executions.
2. **Compatibility Parameter Demarcation:**
   - `--max-retries` and `--retry-backoff` argument help strings were updated to explicitly state:
     `"Compatibility parameter; push-batch operates pure fail-closed on mutating events without automatic retries"`
   - Documents that client-side mutating pushes deliberately fail closed on the first exception without blind connection replays.
3. **Commit & Hash Verification:**
   - Delta commit `71dade6e7d824c3de631f43b3ea70e04c82ee8ad` merged cleanly into `main` via fast-forward.
   - Pinned hashes:
     * `agent_branches/cli.py`: `92bb9686be7a90e9c57a29cdf457946fa254bc55f2630fde2a3537da0c5d6624`
     * `tests/test_cli_batch.py`: `aa5114de459f4d9f50e4798a8ad929fdbc3985dc2359da2f94951df0f139fc86`
   - All 4 CLI batch tests and all 61 full suite tests pass 100% on `main`.
4. **Final Acceptance:** Fully certified and merged into canonical `main`.

