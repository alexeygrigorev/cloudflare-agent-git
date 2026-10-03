# Muse round 24: rev1c/rev1d delegate (muse-r2) — CHANGES, head-confirmed

Head: muse-reviewer (7e6e9bb0). Delegate: native session muse-r2 (ad652b55,
closed after capture), headless opencode executor (opencode-go, fresh quota
Go 100/98/98 checked pre-dispatch, --auto bounded, 800s cap, read-only repo
+ /tmp), brief with no prior-verdict contamination. First tool: PTY probe;
usage: one bounded review run. Delegate skipped rev3/rev4 suites correctly
(they write into research/zcode — out of bounds for a reviewer).

## Delegate verdict CHANGES, all three points head-confirmed by me
1. **Lexical fallback lock (strongest).** canonical_lock_for resolves only
   for the canonical-repo check; the sibling fallback
   (`events_path.parent / (name + ".lock")`, no resolve()) yields divergent
   locks for same-resolved-file via different relative spellings, different
   cwds, or symlinks — I verified the code path; the race is structural,
   not probabilistic. rev1d's "ONE lock domain per journal file" holds ONLY
   for experiment/events.jsonl (and identical-spelling callers). Explicit
   divergent lock_path additionally opts out with zero warning. Recommend:
   resolve() before deriving sibling locks; reject-or-warn on explicit
   non-canonical lock_path. (ZCode's file; not mine to edit.)
2. **Two crash paths on arbitrary input (both reproduced by me via import,
   /tmp files):** unserializable set value → key hashes (default=str) then
   bare `json.dumps` write raises TypeError out of append_event_dedup;
   non-dict `event` arg → AttributeError on `.items`. A "durable" journal
   helper should validate-and-reject (or coerce) instead of propagating.
   Moderate; fail-loud, but a twin with odd content crashes the caller.
3. **REQUIRED_FIELDS mirror 12/12** (delegate's programmatic diff; consistent
   with my round-11 schema match). Labeling honest. No finding.

## H3 note (per task framing)
H3 principal "warning consumed" activity is engineering-review use of the
adapter machinery — it is NOT A01 warning-adoption benefit and must not be
cited as such. Recorded here so no one upgrades it.
No R2/D1 action (pending, separate scope); no repeat of f2178fb work.
