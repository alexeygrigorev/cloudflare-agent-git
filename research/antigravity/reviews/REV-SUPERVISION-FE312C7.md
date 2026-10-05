# Independent Review: Supervision Fail-Closed Restoration (fe312c7)

- **Reviewer:** muse-reviewer-fe312 (Muse Spark, independent; launched by antigravity-head `46fdb644` under Codex Principal C1462 directive)
- **Commit under review:** `fe312c7` — "supervision: remove unsafe installed binary fallback, restore fail-closed semantics, and record sb-reviewer-sup REQUEST_CHANGES"
- **Date:** 2026-10-04 (review executed ~01:25 CEST / 23:25 UTC 2026-10-03)
- **Workspace:** `/home/alexey/git/cloudflare-agent-git`, branch `main`, HEAD = `fe312c7`
- **Verdict:** **ACCEPT**

No Rust build, no global install, no `/tmp` allocation (pytest ran with
`TMPDIR=.local/scratch/muse-fe312-review/`) was performed or needed.

## 1. Code inspection findings

Diff examined via `git show fe312c7 -- scripts/supervision/service.py scripts/supervision/test_service.py`
(plus live-file reads of `service.py:1-50,370-409` and repo-wide grep):

1. **`INSTALLED_BINARY` fully removed.** The constant definition
   (`os.environ.get('SUPERVISION_FALLBACK_APLEXER_BINARY', ...)`) is gone from
   `service.py:9`, and repo-wide grep for `INSTALLED_BINARY|fallback_binary|fallback`
   in `scripts/supervision/*.py` returns only the single safety comment at
   `service.py:388`. No functional fallback reference remains.
2. **`fallback_binary` removed from manifest generation.** The
   `manifest['fallback_binary'] = {...}` block is deleted; live
   `.local/supervision/binary-manifest.json` confirms keys are exactly
   `path, sha256, selected_at, authority, supports_idempotency_key, send_recovery`
   with `fallback_binary` absent.
3. **Fail-closed delivery restored and verbatim.** The ~20-line conditional retry
   block (tag + `'unsubmitted draft'` + `'GPT-'` match, second `subprocess.run`
   against the installed binary, `outcome = fallback_outcome` overwrite) is deleted.
   The replacement at `service.py:388-392` writes the primary reviewed `BINARY`
   outcome verbatim via `atomic(PRIVATE / f"delivery-{pending['id']}.json", outcome)`
   and sets `pending['delivery'] = status` from that same outcome. A `not-ready`
   refusal is therefore preserved in both the delivery audit record and pending
   state — no overwrite path exists.
4. **Test drives `service.run()` directly.** `test_service_run_fail_closed_delivery_and_negatives`
   (renamed from the c14b474 fallback test) stubs `command`/`subprocess.run` and calls
   `service.run()` end-to-end. It asserts: (a) `not-ready` outcome recorded verbatim in
   `delivery-m1.json` with the draft detail intact and `state.json` pending delivery ==
   `not-ready`, using only the pinned binary; (b)/(c) fresh-screen draft and busy still
   deny delivery (zero `deliver` calls); (d) a clean `submitted` outcome records
   `submitted`. Grep confirms zero `INSTALLED|fallback|installed-aplexer` remnants in
   `test_service.py`. The old tautological inline-reimplementation shape is gone.

No other files in the commit touch runtime behavior (`TEAM-REGISTRY.json`,
`coordination/antigravity.md`, `REV-SUPERVISION-C14B474.md` are record-keeping only).

## 2. Test execution results

```
TMPDIR=.local/scratch/muse-fe312-review python3 -m pytest -v scripts/supervision/test_service.py
26 passed in 0.08s
```

All 26 tests pass, including the rewritten
`test_service_run_fail_closed_delivery_and_negatives` (fail-closed verbatim
preservation + fresh-screen negatives + submitted happy path). Fail-closed delivery
is strictly enforced by the test: any reintroduction of a fallback overwrite would
break assertion (a) (`status == 'not-ready'`, single-binary call list).

## 3. Runtime provenance confirmation

- **Process:** PID `3915539`, `python3 scripts/supervision/service.py`, session `3038209d`.
  `ps` STARTED = `Sat Oct 3 21:07:56 2026` with elapsed `04:13` at 01:21 CEST —
  i.e. **21:07 CEST = 19:07 UTC** (ps reports local time; corroborated by
  `binary-manifest.json` `selected_at: 2026-10-03T19:07:57Z`). Note: the task brief's
  "21:07 UTC" label appears to conflate timezones; the material fact is unaffected:
  process start (≈19:07 UTC) **predates** commit `c14b474` (23:37 CEST = 21:37 UTC)
  by ~2.5h, so the running process never loaded the unsafe fallback code introduced
  in `c14b474` and removed in `fe312c7`. No restart/reload since (elapsed matches
  start wall-clock; manifest timestamp matches process start).
- **Zero fallback footprint:** all 6 `delivery-*.json` records have `fallback: ABSENT`
  (`fallback_records=0` across the full set); the 3 most recent (incl.
  `delivery-01a10381-…`, the GPT-6 status-bar `not-ready` case) preserve refusal
  detail verbatim with no `fallback` key. `status.json`: `degraded=false`,
  `errors=[]`, clean ongoing monitoring (`codex-principal` working/composer-busy,
  last request `delivery: not-ready` correctly unreconciled).
- **Old unsafe fallback stays OFF:** no running code path references it (per §1),
  no manifest entry advertises it, no delivery record was produced by it.

## 4. Notes (non-blocking)

- Timezone labelling: process-start and commit timestamps above are given in both
  CEST and UTC; future directives should state the zone explicitly to avoid the
  2h ambiguity (harmless here — ordering holds under either reading).
- The underlying Codex GPT-6 status-bar footer parsing limitation (fail-closed stall
  on `01a10381-…`) remains an accepted known limitation per `coordination/antigravity.md`
  §48, pending a structural parser update; it is correctly handled by refusal +
  durable queue + `exact_ack()` reconciliation, not by fallback.

## 5. Conclusion

Commit `fe312c7` completely removes the unsafe installed-binary fallback, restores
verbatim fail-closed delivery semantics, backs them with a `service.run()`-driven
test, and leaves the running supervisor (PID 3915539) in clean, never-contaminated,
`degraded=false` operation with zero fallback records. **ACCEPT** — no changes requested.
