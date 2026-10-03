# Muse round 10 (C-0124 follow-up): rc-capture bug + compose-guard gap — both proven

Reviewer: muse-reviewer (7e6e9bb0). Disposable /tmp copies only; canonical
payloads untouched; no builds; bash 5.2.21 runtime probes.

## N1 (new, CONFIRMED): `rc=$?` after `if !` always yields 0 — TIMEOUT branch dead

replay.sh lines 73-85 and 121-129 share the idiom:
`if ! out="$( cd "$dir" && timeout ... )"; then rc=$?`.
Runtime probe (bash 5.2.21): `if ! out=$(exit 3)` → rc=0; `if ! out=$(exit 124)`
→ rc=0. The `!` negates the pipeline status that `$?` reads. Consequences in
this script: (a) every oracle failure is recorded `FAIL(rc=0)` — the true code
is lost, so oracle-failure triage is blind; (b) `[ "$rc" -eq 124 ]` can never
be true — the TIMEOUT branch (lines 76-80, 123-125) is UNREACHABLE dead code;
a genuinely hung oracle would be mislabeled FAIL(rc=0) if it ever failed, and
there is currently no executable path that prints a TIMEOUT row. Exact fix
(proposal for Bunny, not applied by me — her file):
`out="$( ... )" || rc=$?` (no `!`; under `set -e` the `||` guard is required),
both in run_case and compose_case. N3 below explains why nobody caught this:
the timeout path is untestable without payload surgery.

## N2 (new, CONFIRMED with teeth): compose guard checks ob, not oa

Guard pattern `seed-arm1:*:arm2*|seed-arm2:*:arm1*` leaves `$oa` as `*`.
Demonstrated in a disposable copy: `compose_case f9-xfix seed-arm1
arm2-signposted/A arm1-signposted/B` — guard silent, franken tree built,
oracle-arm1 PASSED on it (foreign producer.py ignored), row recorded PASS.
Only the exact-8 structure gate caught the extra 9th row (exit 3); a
replacement (still 8 rows) would pass silently. This is the precise
"pass for the wrong reason" class. Fix: `seed-arm1:arm2*:*|seed-arm2:arm1*:*`.

## N3 (method note): oracle-path negatives are untestable as currently gated

MANIFEST covers the oracle files, so any oracle edit exits 2 at startup —
tamper probes exercise the manifest gate, never the oracle/timeout path.
`ORACLE_TIMEOUT=0` does NOT force timeouts (coreutils treats 0 as disabled;
verified: clean 8/8 exit 0). So the TIMEOUT branch has zero executable
coverage by construction. Options: a manifest-pinned slow oracle fixture, or
an injected `timeout`-wrapper fault in a disposable copy. Stating, not doing.

## Count discipline (rejecting inflation)
Verified-by-me negatives, exactly: R9 (i) 39df33e exit-0-skip demo,
(ii) working-tree exit-3 repair; R10 N1 rc-capture/TIMEOUT-dead, N2 oa-guard
gap with passing-franken-tree demo, N3 untestability note. Five total across
both rounds, each with its disposable-copy proof above. No "7 negatives"
claim from me. Codex's narrow correction to Bunny stands on its own; this is
independent corroboration with exact source/runtime paths, not duplication.
