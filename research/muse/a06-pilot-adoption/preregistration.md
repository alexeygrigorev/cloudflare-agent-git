# A06 pilot-adoption review experiment — preregistration (head: muse-reviewer)

Date: 2026-10-03. Owner: muse-reviewer (`d575342d`). Scope: `research/muse/a06-pilot-adoption/`.
Ordered by codex-principal `01a100f0-de63`; Grok's queued prospective review untouched (notified, no transfer).

## Decision under study
Should ca1 (candidate binary sha256 `ca1e8030da0efb62504d1777a6f2a60358b002c1c0b1ace3a7268e817e5bbcd1`)
be adopted for use on ONE existing head? Reviewers ADVISE; Ant owns the actual adoption decision.

## Evidence packet (IDENTICAL for both arms; no asymmetric hints, no seeded defects)
1. `.local/pilot-ca1/PILOT-REPORT.md` + `pilot_results.json` (frozen pilot evidence).
2. R14 verdict `.local/muse-r14/verdict.md` (pins/cycles/ordering CONFIRMED; E4+E5 PENDING-OWNER-RERUN; E6 exit-code doc conflict; stale manifest sizes).
3. R17 verdict `.local/muse-r17/verdict.md` (SAFETY-CONCERN-CONFIRMED: after→idle on pending-drain + 3500 ms timer can report idle mid-think; no composer guard; no turn-completion event).
4. Producer verdicts: R10 producer APPROVE (fidelity/negatives/cargo) + guard split note (66f guard CHANGES; R2 guard APPROVE but UNCOMMITTED — pin by sha256 only).
5. Pins: binary `ca1e8030…`, rollback CLI `8d49a216…`, spec `3a82375` byte-identical.
6. Known unknowns disclosed to BOTH arms: session.status stream unobservable from DB copy; state-report emission log absent; DB step-start→plugin-event delivery not contractually established; R2 files uncommitted.

## Arms (same model `opencode-go/muse-spark-1.3-contributor`, same tools, fresh reviewers with no ca1 context)
- **Arm A (ordinary review)**: reviewer receives the packet as raw sources and reviews as an ordinary Git/source/test evidence review.
- **Arm B (evidence-card review)**: reviewer receives the SAME packet pre-structured as `evidence-card.md` (authored neutrally, all issues above included).

## Preregistered decision criteria (both arms apply these; tie/reject allowed)
- ADOPT iff ALL hold: (C1) all pins verifiable; (C2) no open SAFETY-CONCERN on the delivery path; (C3) rollback path exists and is hash-verified; (C4) scope bounded to one named head with monitoring.
- Else REJECT (state which criterion fails), or TIE/abstain with reason if evidence insufficient.
- Correct decision under these criteria given the packet: REJECT-or-TIE (C2 failsopen via R17; E4/E5 pending) — recorded here BEFORE reviewers run, for adequacy scoring, NOT shared with reviewers.

## Recorded per reviewer
Decision, criterion mapping, defects found (with artifact refs), confidence, wall-time, command count approximation, model/route, first-tool evidence. Effort/commands/decision-adequacy only — no infrastructure-tests-as-efficacy, no timing-blindness claims, no product-efficacy inference.

## Analysis plan
Compare arms on: decision adequacy (match to preregistered-correct outcome + criterion coverage), defects surfaced, effort. N=1 per arm — descriptive only, no statistical claim.
