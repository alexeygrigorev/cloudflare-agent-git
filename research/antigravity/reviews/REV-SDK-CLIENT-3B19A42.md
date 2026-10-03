# Independent Review: Commit 3b19a42 — Python SDK Client C1479 Fix & Negative Test Suite

- **Reviewer:** sb-reviewer-sdk (independent reviewer, launched by antigravity-head 46fdb644)
- **Workspace:** /home/alexey/git/agent-branches-l2-client
- **Branch:** proto/l2-client
- **Commit under review:** 3b19a42 `fix(l2-client): resync never replays stale results; authed status reads (C1479)`
- **Scope:** `agent_branches/client.py`, `tests/test_client.py`
- **Date:** 2026-10-03 (UTC)
- **Verdict:** **ACCEPT**

## 1. Commit identity and diff summary

Verified via `git show --stat 3b19a42`:

- `agent_branches/client.py | 156 ++++----` (net +~85)
- `tests/test_client.py | 321 ++++++++----` (net +~250)
- Commit message documents the Codex Principal REQUEST_CHANGES on e882b17 that this commit addresses.

Diff inspected in full (`git show 3b19a42 -- agent_branches/client.py`) and current files read end-to-end (client.py 563 lines, test_client.py 1360 lines).

## 2. Requirement-by-requirement verification

### 2.1 send_checks_with_resync: old checks NEVER replayed on fresh head vector without recomputation

**PASS.** Confirmed by source inspection + test execution:

- The pre-C1479 defect (payload `vector` replaced with fresh heads, old `results` re-POSTed) is gone. No code path assigns `attempt_payload["vector"] = resynced` or equivalent. Verified: string `resynced` no longer appears in `send_checks_with_resync`; `fresh_heads[k]` dict-comprehension resync is gone.
- Default path (`recompute_fn is None`): on first `StaleVectorError`, client attaches `fresh_vector`, then `break`s — exactly 1 POST. No retry, no replay.
- Recompute path: `attempt_payload` is only replaced by `copy.deepcopy(validated)` where `validated = _validated_recomputed_payload(original_vector, fresh_heads, recomputed)`. The original `payload` argument is protected by `copy.deepcopy(payload)` at entry, and tests assert input immutability.
- Source checks (all PASS): no direct vector-from-fresh assignment; `copy.deepcopy(payload)`; `copy.deepcopy(validated)`; validator gate before any retry.

### 2.2 Fail-closed behavior

**PASS.**

- `StaleVectorError` now carries `.fresh_vector` (`__init__` sets `self.fresh_vector = None`; resync success sets `exc.fresh_vector = fresh_heads`). Attached in ALL paths where the resync read succeeds — including fail-closed exits (default no-recompute, max_attempts=1, invalid recompute). If `refresh_head_vector` raises `AgentBranchesError`, `fresh_heads = None` and the original 409 is re-raised without retry.
- `recompute_fn` validation (`_validated_recomputed_payload`) rejects and fails closed on: non-dict payload, missing `contract`, non-list `results`, missing/empty/non-dict `vector`, any original participant missing from recomputed vector, any recomputed vector sha != `fresh_heads[key]` (stale-sha relabeling), non-dict result, non-list pair, pair participant not in vector. All 9 mutation probes PASS (see §4).
- Participant-mismatch pre-check also exists before invoking recompute: `if any(key not in fresh_heads for key in original_vector): break` — never retries with a pruned vector.
- Crashed recompute (`recompute_fn` raises `Exception`): caught, `break`, original `StaleVectorError` re-raised. Stale-vector failure on retry: loop exhausts `max_attempts`, re-raises last `stale_exc`.
- Bounded budget: `for attempt in range(max_attempts)`, `if attempt >= max_attempts - 1 ...: break`. Stub test confirms `max_attempts=3` yields exactly 3 sends + 3 refreshes.
- Auth failures never retried: `send_checks_with_resync` catches only `StaleVectorError`. `TokenExpiredError`/`TokenRevokedError` propagate immediately (test_13 §4 also covers resync-with-revoked-token raising `TokenRevokedError`).

### 2.3 Authenticated status read

**PASS.**

- `get_status(runner_token=None)`: builds `Authorization: Bearer <token>` from explicit arg or `$RUNNER_TOKEN`; passes via `_request(..., headers=...)`. Verified in source.
- `refresh_head_vector(runner_token=None)` forwards to `get_status(runner_token=runner_token)`.
- `send_checks_with_resync(..., runner_token=...)` forwards the same token to both `send_checks` and `refresh_head_vector(runner_token=runner_token)`, so the 409 resync read is authenticated.

### 2.4 Negative test coverage (test_11, test_14, test_15)

**PASS.** All present, substantive, and passing:

- **test_11 (`test_11_stale_vector_fail_closed_without_recompute`)**: real-server 409 via stale vector; `refresh_head_vector` dual-key (agentId+taskId) assertion; `_CountingSendClient` proves 1 POST and no replay without recompute; `fresh_vector` attachment (both agents, then moved-head case); input-payload non-mutation; `max_attempts=1` still attaches fresh vector with 1 send + 1 refresh; `_AlwaysStaleClient` loop-bound check (3 sends/3 refreshes with generic recompute); ghost-agent fail-closed (1 send/1 refresh, fresh_vector attached); missing-vector fail-closed (1 send/1 refresh).
- **test_14 (`test_14_resync_recompute_paths_real_server`)**: real-server, heads moved mid-evaluation. (a) genuine recompute accepted in exactly 2 sends, callback received CURRENT heads, input unmutated; (b) stale-sha smuggling rejected, 1 send; (c) dropped participant rejected, 1 send; (d) raising recompute rejected, 1 send; (e) ghost pair participant rejected, 1 send.
- **test_15 (`test_15_status_reads_carry_runner_token`)**: dedicated `_StatusAuthServer` bearer-protecting GET /status. Unauthenticated read → 401; authenticated read → 200; `refresh_head_vector` without token → 401; with token → correct dual-key heads; `$RUNNER_TOKEN` env fallback → 200.

Pre-existing tests (test_09 stale 409, test_12 expiry, test_13 revocation incl. resync-never-retries-auth) remain intact and passing.

## 3. Test results

Command: `python3 -m unittest -v tests/test_client.py` (workspace root)

```
Ran 15 tests in ~6s — OK (all 15 pass)
test_01 ... ok / test_02 ... ok / test_03 ... ok / test_04 ... ok
test_05 ... ok / test_06 ... ok / test_07 ... ok / test_08 ... ok
test_09 ... ok / test_10 ... ok / test_11 ... ok / test_12 ... ok
test_13 ... ok / test_14 ... ok / test_15 ... ok
```

No skips, no failures. Full suite (not just the three new tests) was run to guard against regressions in token classification, CLI checks, and push flows.

## 4. Mutation / adversarial probes (reviewer-executed)

Ad-hoc probes against the checked-out commit, independent of the suite's own stubs:

| Probe | Result |
|---|---|
| No `resynced`-vector replay path in `send_checks_with_resync` | PASS (absent) |
| `copy.deepcopy(payload)` input protection | PASS |
| `copy.deepcopy(validated)` only retry source | PASS |
| `refresh_head_vector(runner_token=runner_token)` forwarding | PASS |
| `exc.fresh_vector = fresh_heads` attachment | PASS |
| `except Exception` around `recompute_fn` (fail closed) | PASS |
| Catches only `StaleVectorError` (auth propagates) | PASS |
| `_validated_recomputed_payload`: valid accept | PASS |
| reject stale sha / dropped participant / non-dict / missing contract / non-list results / ghost pair / non-list pair / non-dict result | PASS (8/8) |

`_CountingSendClient`/`_AlwaysStaleClient` attempt-count assertions in the suite (send_calls == 1 on every fail-closed path, == 2 on genuine recompute, == 3 on max_attempts=3 stub) corroborate the bounded-budget and no-replay claims with real attempt counts, not just exception types.

## 5. Findings

No blocking findings. Minor observations (non-blocking, for head awareness):

1. `_validated_recomputed_payload` does not verify that `vector` contains ONLY known participants (extra keys beyond the original vector are tolerated). This is lenient but safe: extras cannot relabel stale evidence, and the server remains the final gate. Not a fail-open.
2. `recompute_fn` receives `dict(fresh_heads)` (a copy) — good; but its return value's `contract` value is not checked for `"0.1"` specifically, only presence. Server-side validation covers wire correctness; client-side strictness here is optional.
3. `StaleVectorError.fresh_vector` keys include both agentId and taskId mappings (by design of `refresh_head_vector`). Callers consuming it as a `vector` for recompute should prefer agentId keys; test_14's genuine-recompute example does exactly this. A one-line doc hint would help but is not required for ACCEPT.

## 6. Verdict

**ACCEPT** — Commit 3b19a42 correctly implements the C1479 fail-closed resync contract:

- stale results are never replayed without explicit recomputation;
- default and all invalid/crashed/mismatched recompute paths fail closed after exactly 1 POST with `fresh_vector` attached;
- status/resync reads carry the runner bearer token (explicit arg + `$RUNNER_TOKEN` fallback);
- negative coverage in test_11/14/15 is real (live mock coordinator + attempt counting), and the full 15-test suite passes.
