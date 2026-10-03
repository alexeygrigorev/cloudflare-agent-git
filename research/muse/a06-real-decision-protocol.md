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
