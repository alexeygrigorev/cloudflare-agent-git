# Evidence card: ca1 scoped-pilot adoption packet (neutral, complete — Arm B format)

Same evidence as Arm A receives as raw sources. No issue withheld from either arm.

## E1. Pins (verify before use)
- Candidate binary: sha256 `ca1e8030da0efb62504d1777a6f2a60358b002c1c0b1ace3a7268e817e5bbcd1` (79,382,632 B; lives in `.local/producer-review/bin/`, not the pilot dir).
- Rollback CLI: sha256 `8d49a216d43c70843bc07705f4c11eb13f3eb51646d5c6fc204ce0796ce618c4` (7,487,016 B).
- Pilot spec: `research/antigravity/r12-scoped-ca1-pilot-verification.md` == `git show 3a82375` byte-for-byte.

## E2. What the pilot showed (frozen artifacts + DB copy: 1 session / 25 msgs / 94 parts)
- CONFIRMED: both receive cycles with artifacts + ACKs; turn stop→start ordering monotonic; identities as recorded.
- PENDING (owner rerun in progress): fail-closed `not-ready` rejection DURING confirmed active child-tool execution; zero PTY leakage. Frozen rejection cites pre-sleep harness ts (1791015055238), ~22.5 s before the sleep tool window — grounding on the active-tool window not established.
- DOC DEFECTS (owner to fix): report says deliver exit 0 vs JSON says 1 (JSON consistent with harness); manifest size fields stale (hashes authoritative).

## E3. Safety finding (standalone, mechanism + gap arithmetic)
- On `tool.execute.after` with pending drained, session state is set `idle` without lifecycle authority; aggregate reports `idle` after bare 3500 ms tool-quiescence. No turn-completion event exists in code; no composer/deliver guard found.
- A real 7719 ms model-busy gap (6213 ms continuous reasoning, zero active tool) contains the timer fire point ~4.2 s before the next tool start: false-`idle` fires mid-think absent rescue signals (which exist but are not contractually guaranteed).
- Failing direction is fail-OPEN (premature `idle` invites mid-turn delivery).

## E4. Producer + guard status
- Producer logic (conflict radar): independent negatives + cargo checks green (APPROVE, pinned).
- 66f-committed guard script: CHANGES (no post-completion growth gate; final-measurement WARNING not fail-closed; see full note). Repaired R2 guard script: independently APPROVED as sound, BUT its files are UNCOMMITTED (pin by sha256 only, re-verify on copy).

## E5. Known unknowns (apply to any decision)
- Plugin-visible `session.status` stream and `state-report` emission log are unobservable from frozen artifacts.
- DB `step-start`→plugin-event delivery is not contractually established.
- R2 guard bytes could change/vanish without git trace until committed.

## Decision criteria (apply as written; tie/reject allowed)
ADOPT iff: (C1) pins verifiable; (C2) no open safety concern on the delivery path; (C3) rollback path hash-verified; (C4) scope bounded to one named head with monitoring. Else REJECT (name the failing criterion) or TIE with reason.
