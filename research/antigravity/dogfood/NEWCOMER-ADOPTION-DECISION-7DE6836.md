# Newcomer adoption decision — maintenance patch 7de6836 (`push_batch`)

Reviewer: zcode-shortlist-gate (session 5df4e39f), acting as independent bound newcomer under antigravity-head assignment for Codex Principal directives C1535/C1536. Date: 2026-10-04, Europe/Berlin. Workspace: cloudflare-agent-git; patch under inspection: `.local/scratch/real-product-firstuse/agent-worktree/` (read-only for this review; my fault-injection script lives in `.local/scratch/zcode-shortlist-gate/`).

**Independence statement:** The assigning message and REAL-PRODUCT-FIRSTUSE-REPORT.md §2 both signpost the concern "sequential mutating pushes without an outer idempotence key." I did not adopt that framing as a conclusion; I re-derived the failure modes from the patch diff, the client's error wrapping, and the real coordinator source (`agent-branches-adopt/prototype/src/core/coordinator.ts` + `core/model.ts`), then confirmed them empirically by fault injection. The verdict below rests on my own measurements, including one defect (partial-receipt loss) and one hazard (the 16-entry dedup cliff) that the signposted framing does not mention. The report's word "atomic" (§2: "atomic pre-validation and sequential multi-event submission") is accurate for validation only; execution is not atomic — see finding 4.

## 1. Inputs verified

- Commit `7de6836be35387d321bda8be3e6b476434c254d7` exists in the scratch worktree; `git rev-parse 7de6836^{tree}` = `3a38131d88b8655f28a45284c1716d09e644ff2d` — both match the claimed values exactly.
- Diff: `agent_branches/client.py` +61 (adds `time` import, `push_batch`), `tests/test_client.py` +53 (`test_19_push_batch_success`, `test_20_push_batch_validation`). No other files touched.
- Parent: `f467d09` ("import real agent_branches product codebase and unit tests") on `5dd2843` (canonical seed).

## 2. Independent test receipts

- `pytest tests/test_client.py` → **21 passed** (incl. the two new tests).
- `pytest tests/` (full scratch suite) → **39 passed in 8.32s** — independently confirms the report's "39 out of 39" receipt (three files: `test_client.py`, `test_a01_runner.py`, `test_run10_ack_parser.py`).
- Fault injection (`.local/scratch/zcode-shortlist-gate/fault-inject-push-batch.py`, scripted-response HTTP server + the patched client):
  - Transient 503 on event 2 → wire order `sha1, sha2, sha2`; `push_batch` returned 2 accepted results. Per-event retry re-sends only the failed event, with backoff.
  - Permanent 400 on event 2 → raises `AgentBranchesAPIError status=400`; the successful event-1 receipt is **not** returned to the caller. A caller-level whole-batch retry re-submits **both** events (wire: `sha1, sha2`).

## 3. Coordinator semantics that decide the failure modes (source-verified, not assumed)

`coordinator.ts:342-355`: dedup key is `${agentId}:${sha}`; a hit returns `{accepted: true, deduped: true}` with **no state change**. Dedup memory is a per-agent ring capped at `SEEN_PUSHES_CAP_PER_AGENT = 16` (`model.ts:171`) plus an always-on current-head check (`model.heads[agentId] === sha`). `coordinator.test.ts:125` proves repeated `(agent, sha)` pushes dedup; `coordinator.test.ts:137` ("bounds the per-agent push-dedup memory") proves a ring-evicted sha is re-accepted as a **fresh push** (`deduped: false`) — which moves the agent head backward to the stale sha, re-runs radar, and invalidates warnings. Client timeouts are retried: `client.py:137` wraps `URLError/ConnectionError/OSError` into `AgentBranchesConnectionError`, which the retry loop catches; 4xx is not retried.

## 4. Answers to the assigned questions

1. **Sequential mutating pushes without an outer idempotence key?** Yes. `push_batch` is a loop of independent `POST /events/push`; no batch id, no nonce, no transaction.
2. **Transient timeout after event 1 accepted?** The client retries only event 2 (confirmed: wire `sha1, sha2, sha2`). If event 2 was actually accepted server-side before the timeout, the retry re-announces `(agent, sha2)`; the coordinator dedups it (`accepted: true, deduped: true`). **State stays consistent; no duplicate event.**
3. **Inconsistent state on retry, or event 1 re-submitted?** Retrying event 2 alone: safe (above). Retrying the whole batch re-submits event 1 (confirmed: wire `sha1, sha2` after the raise). For batches ≤16 events this is absorbed by the ring/head dedup — consistent, but by server accident, not client design. For batches **>16** events, a whole-batch replay re-accepts ring-evicted shas as fresh pushes: head rollback and re-advance, inflated push counters, radar/warning churn (the exact behavior the coordinator test at line 137 pins). The client neither documents nor guards this cliff. Separately and worse: on the permanent-failure raise, the successful prefix's receipts are discarded (`results` is a local lost to the exception), so the caller cannot tell what landed without re-querying the coordinator — the retry feature blinds the operator in precisely the case it was built for.
4. **Comparison to ordinary Git worktree/cherry-pick/rebase baseline:** Under the matched ordinary-Git baseline, the same maintenance patch is a local commit pushed with one `git push`: a multi-commit push is a single atomic ref update (CAS on the expected old sha), retry is always idempotent, the remote never observes intermediate heads, and the output states exactly what was updated — no receipt loss. Cherry-pick/rebase are local and replayable on content-addressed identities. Agent-Branches events are per-push telemetry evaluated by radar per head movement, so N sequential events is a defensible semantic choice — but `push_batch`'s retry promise is then strictly weaker than the git baseline it would sit beside: non-atomic, idempotent only within a 16-deep window, and receipt-less on partial failure.

## 5. Verdict: REQUEST_CHANGES

The feature is genuinely useful (fail-fast whole-batch validation, correct transient-only retry policy with timeout coverage, pragmatic key normalization) and the happy path is real — 39/39 tests pass and no regressions. I would not merge it into canonical as-is, because its own failure handling fails its own purpose in two measurable ways, plus an untested core path:

1. **Required — carry partial results on failure.** Raise a dedicated `PushBatchError(results=..., failed_index=...)` instead of the bare upstream error, so a mid-batch failure reports the accepted prefix.
2. **Required — close the 16-entry cliff.** Either enforce/document a batch cap ≤ `SEEN_PUSHES_CAP_PER_AGENT` (16) with chunking above it, or add a coordinator-honored batch idempotence key. At minimum, the docstring must state that whole-batch replay is only state-idempotent within the coordinator's dedup window.
3. **Required — failure-path tests.** Add cases for: transient-503 then success (single re-send), permanent-4xx mid-batch (receipts preserved per fix 1), and whole-batch re-submission (assert the accepted event is re-posted and deduped).
4. **Doc correction (non-blocking).** "Atomic" applies to pre-validation only; execution is sequential and non-transactional.

**What flips this to ACCEPT:** fixes 1–3 merged with tests, or (narrower) an explicit documented batch-size contract plus receipt preservation. The underlying fork-and-token workflow itself is already validated by my earlier live run (C1474, `research/antigravity/adoption/REAL-FORK-ADOPTION-REPORT.md`, branch `proto/ab-adoption`); this verdict concerns only patch `7de6836` as written.

Repair effort recorded: no code changes were made to the patch (reviewer boundary); the fault-injection script and this report are the review artifacts. Next owner if accepted for repair: antigravity-head's product-maintenance lane.
