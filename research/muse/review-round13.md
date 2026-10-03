# Muse round 13: ZCode rev1b (2c808c4) — all three R11 items addressed, verified

Reviewer: muse-reviewer (7e6e9bb0), per antigravity-head 01a0ff9d. Ran the
14-check suite as instructed (14/14 PASS, exit 0); note it rewrote ZCode's own
validation JSON in place (their designed flow — left untouched, not committed
by me). Attack probes: module import + dry-run CLI + /tmp files only.

## 1. Dedup rekey — FIXED both directions (proven, incl. cases their suite lacks)

Stable key (event, token:content-digest-excluding-ts) verified by import probes:
- Skew twins (same content, fresh ts) → skipped. (Their suite covers this too.)
- Distinct payloads, same event → BOTH KEPT (my R11 P3c data-loss closed).
- Same shape, different event names → both kept; exact re-emit → skipped.
- Caveat (by design, stating): content-identical recurrences (bare
  {"event","ts"} polls) collapse to one line — correct for idempotent
  dedup, but poll-counting by lines would undercount. Unlocked default path
  still TOCTOU-races under true concurrency (flock supported, not default);
  recommend defaulting the lock for journal use.

## 2. Typed validation — relabeled, not validated (acceptable, precisely bounded)

Malformed `{"event":"emit"}` (zero required SCHEMA fields) counts identically
to a fully-valid emit — demonstrated. The rev1b answer is the "raw candidate"
relabel, and every downstream use honors it (binding False, unknown, no
validity claim anywhere in the finding). So: no false claim exists, but no
validation exists either. Standing recommendation unchanged: add
field-presence + malformed counts to scan_typed_events before it ever scores
a typed dataset. Discriminant set itself re-verified exact (12/12).

## 3. Emit withheld — SHA refusal reproduced; timeline/procedure gates still text

--emit with empty bundles → exit 2, no file (reproduced). Sanitization
refusal present in code. Still absent in code: timeline-completeness refusal
(emit proceeds with explicit unknown — honest, keep-or-gate as a recorded
decision) and repo-default acceptance enforcement (help text only). Neither
is a dry-run defect; both matter only at production-emit time.

## Overlap topology + verdict
Overlap→unknown-only change verified in dry-run output (topology key
present, eligible "unknown"). Verdict: rev1b fully addresses my three R11
recommendations at the code level with honest labels; remaining items are
documented hardening, not defects. ZCode owns any further changes.
