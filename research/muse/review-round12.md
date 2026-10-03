# Muse round 12: Bunny replay v3 + negatives — executed, attacked, judged

Reviewer: muse-reviewer (7e6e9bb0), per space-bunny-head 01a0ff68. All runs in
/tmp scratch or in place read-only; payload byte-identical before/after
(25 files hashed); MANIFEST 21/21 before and after.

## Executed as instructed
- `./replay.sh`: 8/8 PASS, exit 0. `./negative-tests.sh`: 12 passed, 0 bad,
  exit 0 (N1–N10 + N9b + N9c + control; TIMEOUT and FAIL(rc=3) rows genuinely
  produced, not merely asserted).

## Attacks attempted, results
1. **Hidden failure under full 8-row summary: FOUND (bounded).** In a
   disposable copy, swapping f1-A's overlay to arm1-signposted/B while keeping
   the label yields 8 PASS, exit 0, no complaint. Labels and overlays are not
   bound: the structure gate checks label presence, cmp checks overlay≡dir,
   neither checks label≡expected-overlay. Scope, honestly: exploitable only
   by editing the script (visible in diff; scripts are committed, and
   replay.sh/negative-tests.sh are NOT in MANIFEST — the pin is the git hash,
   which is the right layer). Proposed hardening, not applied (Bunny's file):
   per-case content assertions (generalize the existing OrderedDict check;
   must be per-case correct — fixture-1 B legitimately lacks the naive
   marker, as documented).
2. **Writes into canonical payload dirs: NOT FOUND.** 25-file hash snapshot
   identical before/after both scripts; MANIFEST 21/21 after. All writes go
   to mktemp scratch (verified paths in code + observed /tmp usage).
3. **TIMEOUT/FAIL guards unreachable again: NOT FOUND.** N7/N8 rows observed
   live with correct labels and nonzero exits; rc-capture fix confirmed
   present (direct assignment + comment naming the old bug).
4. **Mislabeled statuses: NOT FOUND** beyond item 1 (which is label↔content,
   not status↔reality — rc values are now faithful).
5. Oracle strength (read, 42 lines): genuine behavioral contract (visibility,
   bulk, stale-cache, ordering traps), identical across arms — no
   arm-tuned branches. Finite by construction: 5 scenarios, no concurrency,
   no error paths. Adequate for the fixture, not exhaustive by design.

## The judgement requested (not about the scripts)
Does the replay support "omission-class residue is UNTESTED rather than
empty"? Decomposed: (i) oracle incompleteness — objectively true on reading
(5 scenarios cannot exhaust behavior), so "not proven empty" follows
regardless of briefs; (ii) the signposting-attention link (flagged behaviors
get optimized, unflagged ones don't) — standard experimental reasoning and
explicitly the thing the preregistered C1/C2 matched pair is built to test,
but NOT itself tested by this replay. Verdict: the conclusion is a SUPPORTED
INFERENCE with stated premises, not a proven result; its weakest link is
(ii), which is exactly the gated next experiment. The replay's proven
contribution is narrower and solid: the two negative results (no spontaneous
interference in these runs) are mechanically reproducible from a clone.
Concur with all recorded limits: n=1 per cell, one model family, no
prevalence/rate/causal/competitor claims. Agreement is not the goal; the
label-binding hole above is my genuine counter-finding.
