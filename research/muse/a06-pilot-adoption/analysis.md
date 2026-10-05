# A06 pilot-adoption experiment — adequacy analysis (head: muse-reviewer)

Preregistered-correct outcome: REJECT-or-TIE (C2 fails open via R17; E4/E5 pending).

## Arm outcomes
- **Arm A** (muse-r18, ordinary format, 14 calls): REJECT — C2 fail (R17 unrefuted) + C4 fail (no named head/monitoring). Self-verified all pins; independently detected mid-experiment pilot-dir change (refined `test1_active_tool_negative` shape, 41/154 msgs/parts, WAL/SHM present) and correctly held the decision (refined Test 1 doesn't exercise the reasoning-gap path; chronology uncorroborated). Confidence high on decision, medium-low on Test-1 specifics — calibrated.
- **Arm B** (muse-r19, card format, 5 calls): REJECT — C2 fail + C4 fail-as-missing. Verified 2 binary pins itself; flagged C1-partial honestly (spec pin unverifiable under card-only rules). Yielded 7 card-clarity defects (missing filename, missing R2 sha, unexplained `66f`, short-hash spec pin, no head/monitoring/rollback-procedure fields).

## Adequacy scoring (descriptive, N=1/arm)
- Decision adequacy: BOTH adequate (REJECT matches preregistered-correct; criterion mapping explicit; REJECT-over-TIE reasoned, not defaulted).
- Defect yield: A found decision-driving mechanism + scope gap + documented the pilot-dir change with correct non-update of the decision; B found template-level gaps. Complementary, not overlapping.
- Effort: A 14 calls vs B 5 calls for the same decision — card is cheaper; raw-source arm produced deeper corroboration behavior (independent pin checks, change detection).
- Format effect (descriptive only): no decision divergence observed; card's missing fields forced an honest C4-fail-as-missing and C1-partial, while raw-source arm could check more. Card template needs the 7 listed fields before it can support C1/C4 fully.

## Failed-comparison finding (codex-principal 01a100f8-4cb6; recorded, v0 preserved)

Arm access was NOT equal: Arm B was prohibited from opening any raw evidence file while
Arm A opened them. Same packet in two formats was therefore not tested — what ran was
(card-only) vs (card-claims-plus-raw-access). The 14-vs-5 tool-call gap CANNOT show card
benefit; if anything it reflects the access asymmetry. Preserved actual outputs and B's
template defects stand as useful design feedback only. A corrected pending-source
experiment must allow BOTH arms identical raw-source access plus optional card navigation,
with frozen hashes before launch. The "card is cheaper" line above is WITHDRAWN as
unsupported by this design.

## Corrections accepted post-hoc (codex-principal 01a100f4-c587; v0 preserved, not rewritten)

1. **Calibration, not unfamiliar decision.** Principals had already chosen HOLD before these
   arms ran. This experiment calibrates format effects against a known decision; it is NOT
   a test of whether review format changes an unfamiliar adoption outcome. No product-efficacy
   inference.
2. **Packet version-mixing (head error).** The pilot dir was overwritten by owner rerun
   `492cf76` during the experiment while the packet referenced frozen `3a82375`/R14 labels
   without frozen hashes of the versions actually reviewed. Arm A independently detected the
   change and held its decision correctly, but the packet as designed was version-mixed.
   Next genuine decision requires the corrected producer revision with immutable equal
   packets and a separate digest/pin taken BEFORE reviewers run.
3. **R17 fail-open scope limit.** R17 established NO composer/deliver guard in producer
   source + a false-`idle` mechanism; consumer-side fail-open delivery was NOT observed —
   "invites mid-turn delivery" is a hazard statement, not an established consumer outcome.
   C2-fail reasoning in both arms rests on the open mechanism + pending items, which is
   sufficient for REJECT-as-caution but must not be cited as proof of consumer harm.
4. Exposure/uncertainty: head (muse-reviewer) knew the principals' HOLD posture and the
   R17 finding before designing the experiment; reviewers were fresh but the design was
   not blind. Recorded here, not corrected retroactively.

## Follow-ups (not claims)
1. Owner rerun artifacts landed mid-experiment (refined Test 1 shape) — needs its own pinned review trigger (closes R14's PENDING-OWNER-RERUN); this experiment does not approve them.
2. Card template iteration per B's 7 findings before card-format use in real adoption gates.
3. Ant owns the actual adoption decision; both arms advise REJECT on current evidence.
