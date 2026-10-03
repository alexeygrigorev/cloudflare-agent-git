# Muse round 9 (C-0124): replay.sh negative + shadow-runner topology — both confirmed

Reviewer: muse-reviewer (7e6e9bb0). Scope: owned paths only; no protocol edits,
no replay-script edits (Bunny owns), no cargo builds this turn (gate closed),
all destructive probes in disposable /tmp copies, canonical files untouched
(verified: `git status` clean on peers' paths before/after).

## 1. Bunny replay.sh return-2 defect — CONFIRMED on 39df33e, REPAIRED in working tree (uncommitted)

Codex's negative reproduces exactly. In a disposable copy of 39df33e's
replay.sh (`set -uo pipefail`, no `-e`, bare call sites, no row-count
assertion), an appended bad 9th case (`NOPE-DIR` overlay) prints MISSING and
the script still exits **0 with 8 PASS rows** — skipped case invisible.
Demonstrated, not asserted.
The working tree (uncommitted Bunny edits) already repairs it: `set -e`,
`|| rc=$?` capture + `setup_err`, EXPECTED_CASES exact-8-unique structure
gate, 30s oracle timeout (124 distinguished), mktemp fail-closed. Verified
in disposable copies: (a) clean run → 8/8 PASS, exit 0; (b) wrapped bad case
→ SETUP FAILURE, setup/structure=1, exit 3. Remaining action is Bunny's
commit, not my edit. One residual gap even in the fixed version: oracles run
without `timeout` only if ORACLE_TIMEOUT is honored — it is (line 73/121).
`KEEP=1` leaves scratch — documented inspection aid, fine.
Verdict: defect real, fix real, awaiting Bunny commit; my round-8 replay
result stands (I ran the corrected order with overlay assertions, 8 genuine
cases — my AB rerun, not the shorthand).

## 2. ZCode 71d3cd4 shadow runner — hygiene good, headline finding INVALID (concur Codex)

Read-only dry-run machinery is well-built: scratch-repo bundle fetches (main
repo never written), bundle verify + SHA containment, gated --emit (refuses
without all-SHA-verified), null≠failure semantics, self-cleaning scratch.
But the headline "zero eligible warnings" structural finding tests the wrong
topology. The runner derives eligibility from same-path writer pairs in the
manifest; the harness `scan_once` (skeleton-v0.py:423+) pairs WIP across
agents that each have their OWN worktree (`spec["wt"]` per agent id) —
cross-worktree by construction, and the v0.3/0.4 plan specifies "separate
clones, two writers per arm" with no shared-worktree requirement anywhere.
"No shared-worktree pairs" therefore cannot imply "condition never existed";
the runner's own caveat repeats the same wrong premise. Correct next step,
already anticipated by the plan's binding rules: eligibility from FROZEN
EVENT evidence (emit/delivered/consume/interface_observed in the fair run's
receipts/journals), which the runner already counts as tokens but does not
bind. Until then: relabel to "no shared-worktree pairs in manifest
(topology check); eligibility UNDETERMINED". The 8/8 SHA bundle verification
stands as a provenance result independent of the eligibility claim.
Side note: ZCode's own log shows dupexec twin-append artifacts (4254a4c,
9cac35d) — dry-run default (no writes) is the right posture until the mode
fix lands; any emitted results file must itself be single-effect checked.

## 3. Ant dupexec + continuation — acceptance restated, no movement to review

No new owner output to review this turn (no built patch, test still
commented per Grok/Codex). Standing acceptance, unchanged: pinned source +
target/binary hash, before/after side-effect COUNT (2→1) on a probe op,
same-op retry exactly-once, session resume functional. Child-CJS BUILD
denial alone proves neither outer one-effect nor retry/resume. No 485 rerun:
no protocol source change since my 485/485 run requires it (watch-stack
commits ARE new — targeted readiness/deferred suites on the merged head
belong to Antigravity's integration sequencing with digest discipline, not
to me under the closed build gate).

## 4. Scheduler / process
General auto-scheduler stays WITHHELD (concur): no bound chain + negatives
yet. No Claude draft input used. Next: re-verify Bunny's replay.sh commit
when landed; re-check shadow-runner eligibility binding when rebound to
frozen events.
