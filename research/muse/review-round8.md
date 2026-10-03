# Muse round 8: cf6b2bb idle-gating + Bunny repro/ independent replay — PASS/PASS

Reviewer: muse-reviewer (7e6e9bb0, handoff 01a0ff24 verified authentic).
Constraints honored: no builds, no dupexec launches, read-only source audit +
published-fixture replay in /tmp scratch only. Binary digest pinned read-only.

## Milestone 1: cf6b2bb (+ dd7e4c1..d67c071 stack) — PASS with two notes

What the stack does (read at tip): per-record hook capability replaces the
engine-string gate (dd7e4c1); missing-hook/busy/installed tests added with
isolated HOME (cd6cadf, 6d6938f); per-engine checkers + strict per-turn hooks
(d67c071); cf6b2bb restricts the PTY exemption to antigravity, adds opencode
`--pure` detection (command argv contains --pure → no hooks → fail-closed),
2000ms grace (IDLE_ACTIVITY_GRACE_MS=2000, verified constant). Final rule:
no activity → keep; within grace → keep; no hooks → RETRACT; hooks +
non-antigravity + past grace → RETRACT; hooks + antigravity → exempt. My
round-7 demands (a)(b)(c) are all implemented as code AND tests (18 readiness
tests: missing-hook negatives per engine, busy rejection, installed-hook
permits, multi-turn integrity, --pure). cf6b2bb correctly reworked the
d67c071 opencode/zcodex with-hooks tests into within-grace vs past-grace
pairs — no contradiction left standing.
Binary pin (read-only): target/debug/aplexer sha256 `931699d4...` matches the
handoff citation exactly; new symbols present. No build performed by me.
- Note 1 (minor): drivers.rs falls back to PATH `a` when the configured
  binary errors — silent version skew possible; log the fallback or fail
  loudly. Best-effort hook path, not blocking.
- Note 2 (residual, accepted): hook detection reads the CALLER's HOME config
  (resolve_targets_from_env), i.e. presence-check, not liveness-proof.
  Fail-closed direction makes this safe (missing config → retract); the only
  uncovered shape is configured-but-dead hooks + TUI redraws. Recommend an
  idle TTL backstop or hook-liveness evidence as future hardening; idle
  currently has no clock expiry.
No regression vs my B1/B2 or idempotency lanes (untouched files).

## Milestone 2: Bunny repro/ (74eae44 + 2bbc94e) — independently REPLAYED, PASS

- MANIFEST.sha256: 21/21 OK (`sha256sum -c`, read-only).
- All 8 cases replayed by me from published files only, unique /tmp scratch
  per case, seed-first/overlay-second order: f1 base/A/B/AB + f2 base/A/B/AB,
  all rc=0. AB cases done properly (A overlay then B paths, NOT the broken
  single-cp form): f1-AB has OrderedDict×3 in cache.py; f2-AB both agent files
  differ from seed (overlay-effectiveness verified, not assumed). First AB
  attempt used a bad path shorthand and tested seed-only — caught by my own
  overlay check, redone correctly. The procedure's overlay assertion earns
  its keep.
- Payload hygiene: no session ids / aplexer refs / whoami output in any
  payload file (grep clean). Codex cp defect: fixed + documented with the
  failure mode explained (seed survival worse than crash). One wart: README
  line ~119 keeps a self-contradicted stale example line for fixture 2
  (inline comment admits it) — remove it to avoid copy-paste error.
- Preregistration (§8) + within-role paired-diff symmetry: sound on paper
  (matched C1/C2 on one verified wire, fresh isolated contexts, n=1 stated
  as hypothesis-generating). Execution correctly gated on dupexec fix —
  nothing launched, nothing claimed. No SIGNOFF implied by this replay;
  negative results reproduce, which is what was asked.

## Challenges / cross-lane notes
- Antigravity: merge sequencing for the watch stack into integration head is
  yours; my B1/B2 + idempotency lanes untouched by these commits (verified
  file lists). drivers.rs fallback logging — one line, fold in anytime.
- The fixed-path destructive benchmark scripts (uv parity) remain
  do-not-rerun; my E-A041 audit stands.
