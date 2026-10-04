# Independent Review: agent-branches SDK/CLI fail-closed push semantics (71dade6, f4f6c3e)

- **Reviewer:** zcode-sdk-reviewer (independent ZCode consumer-review session, task ingested via FileBus message `6ad717ea-2e9f-45a3-8422-da87846e0f47`)
- **Commits under review:**
  - `71dade6e7d824c3de631f43b3ea70e04c82ee8ad` — "docs(cli): clarify push-batch max-retries and retry-backoff as compatibility parameters (C2046)" (repo HEAD at review time)
  - `f4f6c3eb417c05beb684fac4301faa1b6183f51a` — "fix(sdk): enforce pure fail-closed on mutating push (remove automatic 429 retry per C1672)"
- **Date:** 2026-10-05 (Europe/Berlin)
- **Workspace:** `/home/alexey/git/agent-branches` — **read-only audit** (no writes, no checkout/reset performed; diffs read via `git show`, live files via read-only inspection at HEAD = 71dade6)
- **Verdict:** **BOUNDED ACCEPTANCE** (semantics and tests are sound; two one-line documentation/hygiene fixes requested, non-blocking)

## 1. Test results

Command (executed in scratch testbed, canonical repo untouched):

```
cd /home/alexey/git/cloudflare-agent-git/.local/scratch/zcode-sdk-consumer-trial/testbed
PYTHONPATH=/home/alexey/git/agent-branches/src:/home/alexey/git/agent-branches \
  python3 -m unittest discover /home/alexey/git/agent-branches/tests/ -v
```

- **Result: 61 tests, 61 passed, 0 failures, 0 errors, 0 skipped — `OK`**
- Duration: **21.157 s** (unittest-reported); 21.27 s wall clock.

## 2. Two Generals invariant and fail-closed mutating semantics

### f4f6c3e — client.py `push_batch`

Diff verified via `git show f4f6c3e -- agent_branches/client.py`. The change removes the
entire `while True` retry loop, including the `is_pre_mutation_rate_limited` branch that
previously replayed `HTTP 429` up to `max_retries` with exponential backoff
(`time.sleep(retry_backoff * 2**(attempt-1))`). At HEAD (71dade6):

- `grep time.sleep agent_branches/client.py` → **no matches anywhere in the package**
  (`import time` remains at line 6 but is now unused — see §4).
- The only `for attempt` loop in `client.py` (line 771) is the checks-resync path: it
  retries `POST /checks` **only** on an application-level `StaleVectorError` (a CONTRACT
  v0.1 pre-mutation rejection carrying fresh heads), requires a `recompute_fn` that
  re-evaluates the full payload at the fresh head vector, fails closed on any
  recompute failure, pruned vector, missing participant, or budget exhaustion, and
  **never retries** `TokenExpiredError`/`TokenRevokedError`. This is a documented,
  contract-bound optimistic-concurrency resubmit with a *changed* payload — not a blind
  replay of the same mutation — and is a defensible distinction from the removed 429
  retry (application-level semantics defined by this coordinator's contract vs.
  transport-level 429/timeout/5xx whose ordering relative to mutation cannot be proven
  across arbitrary backends). Not a violation of the C1672 invariant.
- `push_batch` now executes each event exactly once: any exception (timeout,
  `AgentBranchesConnectionError`, 5xx, **429**, or non-transient 4xx) immediately raises
  `BatchExecutionError` with structured receipts — `succeeded`, `failed_index`,
  `original_error`, `unattempted_events`, `ambiguous_event` (the event whose mutation
  status is unconfirmed). `max_retries`/`retry_backoff` are still accepted and validated
  (`ValueError` on negative/invalid) but are **inert** — pure compatibility parameters.
- Single-event `push()` and the CLI contain no retry logic; remaining "retry" strings in
  `cli.py` are fail-closed messages ("Halting (no retry)").

### Test evidence (tests/test_push_batch_retry.py, as rewritten by f4f6c3e)

- `test_05_rate_limit_429_fails_closed_without_blind_retry`: live HTTP server always
  returns 429; asserts `BatchExecutionError`, `err.status_code == 429`, and
  **`attempts == 1`** — no second request is issued.
- `test_06_rate_limit_429_preserves_partial_success_and_unattempted`: event 0 succeeds,
  event 1 gets 429, event 2 never dispatched; receipts verified.
- `test_04_server_503_fails_closed_without_blind_retry`: 5xx fails closed.
- `test_11_commit_then_timeout_fails_closed_without_blind_retry`: the strongest
  Two Generals test — the server handler records and **commits the push, then kills the
  connection before responding**. Asserts the client raises
  `BatchExecutionError` with `ambiguous_event == event0`, the original error is a
  connection error, and — decisive — the **server-side push count remains exactly 1,
  not 2** (no second mutating request ever hit the wire).
- `tests/test_cli_batch.py::test_04_commit_then_timeout_ambiguous_mutation_safety`
  repeats the commit-then-timeout scenario at the CLI layer.

**Verdict on the invariant: satisfied.** Mutating operations fail closed on timeout,
connection drop, 429, and 5xx without any automatic mutating retry, with honest
"ambiguous event" accounting so an operator can resume with `unattempted_events` only.

## 3. CLI compatibility-parameter documentation (71dade6)

Diff verified via `git show 71dade6`: exactly two `help=` strings in
`agent_branches/cli.py` changed; behavior untouched (2 insertions, 2 deletions).

Live rendering of `push-batch --help` at HEAD confirms both flags now read:

> Compatibility parameter; push-batch operates pure fail-closed on mutating events without automatic retries

This is accurate: `cmd_push_batch` forwards `--max-retries`/`--retry-backoff` into
`client.push_batch`, where they are validated and then ignored (no code path reads them
for control flow). The previous wording ("Max retries for transient connection errors")
was misleading and is fixed. `BatchExecutionError` at the CLI exits 1 with a structured
receipt including the "Invocation Guarantee" note directing the operator to dispatch
only `unattempted_events` on resume.

## 4. Requested bounded fixes (non-blocking, docs/hygiene only)

1. **Stale docstring, `agent_branches/client.py:404`** — `push_batch`'s summary line
   still reads "…with upfront pre-validation **and transient retries**", directly
   contradicting the pure fail-closed Phase 2 docstring immediately below it and the
   actual behavior. The C2046 commit fixed the CLI help but missed this line. One-line fix.
2. **Dead import, `agent_branches/client.py:6`** — `import time` became unused once the
   backoff `time.sleep` was removed in f4f6c3e. Lint hygiene only.

Both are zero-behavioral-impact; neither affects the invariant, semantics, or tests.

## 5. Verdict

**BOUNDED ACCEPTANCE** of 71dade6 and f4f6c3e as consumed at HEAD.

- Two Generals invariant on mutating pushes: **verified in code and proven by tests**
  (commit-then-timeout asserts server push count stays 1).
- Pure fail-closed semantics on timeout/429/5xx/connection drop: **verified**.
- CLI compatibility-parameter help texts: **accurate and verified live**.
- 61/61 unit tests pass (21.2 s) in the scratch testbed against the read-only canonical repo.
- Conditions: apply the two one-line doc/hygiene fixes in §4 in a follow-up docs commit;
  no re-review of behavior required.

Publication guard: `python3 research/antigravity/tooling/publication_guard.py` run on
this file — exit 0 (clean).
