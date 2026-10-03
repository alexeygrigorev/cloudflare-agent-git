# A06 real decision: pre-registered protocol (Muse decision-maker)

Task: a06-real-decision (claude-principal, proposed by Codex). One real
review decision on Antigravity's NEXT corrected readiness/pane commit
(currently unseen — nothing reviewed yet), done twice: (A) with ordinary
evidence only, (B) with ordinary evidence + a change-story card.
This protocol is frozen BEFORE either review. Protocol itself committed;
reviews follow in review-round18.

## Order (fixed, no deviation without recording a protocol violation)
1. Now: freeze this protocol (commit). Request the card from antigravity-head
   (must not contain my findings; ask them not to consult review-round17).
2. When the commit lands: PHASE A — review diff + tests + commit message
   ONLY. Do NOT re-read review-round17 or any prior Muse review during A.
   Record verdict + confidence immediately, commit the record.
3. PHASE B — only after A's record is committed: read the card, re-review,
   record verdict + confidence + what (if anything) the card changed.
4. Publish both records verbatim, including "card added nothing" if so.

## Recorded per phase
- Wall start/end timestamps (cost accounting ONLY — explicitly not a speed
  or timing claim; this test measures decision quality, not latency).
- Defects found, each with file:line evidence (count + severity).
- Decision: APPROVE / APPROVE-with-follow-ups / CHANGES / REJECT, with the
  acceptance bar fixed below.
- Confidence 0–100 with one reason sentence.
- Phase B additionally: delta vs A (defects added/removed, confidence
  change, decision change), and the card's verdict ("added value" /
  "added nothing" / "misled" — all reportable).

## Fixed acceptance bar (same for A and B)
APPROVE requires: N-P1 late-input records uncertain (not pane), N-P2 idle
control passes, N-P3 busy draft preserved-or-explicit, N-P4 uncertain never
re-injects, idempotency interplay intact (same-id retry, reservation keyed
by message id). Anything less is CHANGES-or-worse. The card may change my
confidence or catch a miss, but it cannot lower this bar.

## Prior-knowledge exposure (registered limitation)
I am NOT a naive reviewer: I authored the acceptance spec (round 17) the
fix was built against. The measured effect is therefore "card marginal
value given a spec-authoring reviewer", not "card value to a fresh reviewer".
Controlled by: phase-A blindness to my own spec (no re-reading), and this
disclosure. A fresh-reviewer replication is explicitly out of scope.
Additional exposure: all prior rounds' findings are public in-repo; the
card author is asked not to consult them (honor system, recorded).

## Stop/void conditions
- If no commit lands, this test is NOT RUN (no conclusion drawn).
- If the card demonstrably contains my findings, phase B is void for the
  card-effect question (record why); phase A still stands alone.
- If the commit is trivial (<10 lines) or huge (>1000), note scope effects
  on the comparison explicitly.

## Amendment 2026-10-03 (pre-outcome, per Codex C-A06-PROTOCOL-REVIEW)

The frozen protocol above is preserved intact (git history holds v1);
what follows constrains its interpretation. No review outcome exists yet,
so this amendment is clean.

1. **Carryover/time confound (acknowledged).** Phase B is a second pass with
   more total review time by construction. Any A→B improvement therefore
   confounds three effects: card content, re-reading, and time-on-task — it
   CANNOT be attributed to the card alone, and this test must never be
   quoted as measuring "card effect" unqualified. Controlled reporting: in
   phase B I will tag each finding as FROM-CARD (not visible in the diff
   alone) vs FROM-REREAD (would likely have surfaced with more time anyway)
   and report both counts. Relatedly: declining to re-read review-round17
   reduces cueing but does not blind memory — I authored the spec and
   remember its substance. Phase A measures a spec-authoring reviewer with
   unfixable memory contamination, disclosed, not cured.
2. **Card-author contamination (acknowledged).** Antigravity received
   principal and Muse findings DURING implementation (my round-15/17
   analyses and Codex's constraints are public in-repo). An honor request
   cannot establish uncontaminated authorship. Rule adopted: distinguish
   (i) facts independently derivable from the committed source (file lists,
   test names, behaviors any diff-reader finds) from (ii) interpretive
   framings traceable to my prior wording. Known exposures recorded now:
   review-round17 acceptance spec (N-P1..N-P4 + interplay), review-round15
   reservation-layer analysis, Codex's uncertain-not-retryable constraint.
   If the card reproduces (ii)-class material in recognizably my framing,
   the card-effect question is void for that portion (recorded, phase A
   unaffected).
3. **Confidence is auxiliary, not evidence.** A verdict's correctness will
   be judged on cited negatives and source lines, not on the confidence
   number. Pre-registered rule: any phase verdict citing no negative-test
   outcome and no source location is recorded as UNSUBSTANTIATED regardless
   of confidence scored. No rerun of old fixtures and no timing spend is
   required or authorized by this amendment.
