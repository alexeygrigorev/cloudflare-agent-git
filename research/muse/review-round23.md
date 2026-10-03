# Muse round 23: R9 append-only arms + 01a1000a trace — counted from rollouts

Reviewer: muse-reviewer (7e6e9bb0), per claude-principal 01a0ff1e. All counts
below are from the rollout JSONLs and marker files themselves, not the report
text. No builds, no launches; read-only.

## Counts
- Marker files: old `/tmp/live_append_probe/old/marker.log` = 2 lines
  (MARKER_...2066, ...0059); new `.../new/marker.log` = 1 line (...0868).
  `/tmp/live_outer_probe/probe.txt` = PROBE_OK. Match the report's numbers.
- Arm A rollout (24 lines): 1 exec_command call
  (zcode_tool_eb860a31) + 1 update_goal call; both have recorded outputs.
  1 outer-recorded tool call → 2 side-effect lines (inner .232 + outer .430,
  +198ms). Inner duplication CONFIRMED on old binary.
- Arm B rollout (24 lines): 1 exec_command call (zcode_tool_5e6d0932) +
  1 update_goal call; 1 marker line. Inner duplication absent in this run.
- 4.4 trace (01a1000a, 37 lines): **TWO distinct exec_command call_ids
  (633571b1, e9c52a05), same probe command, ~16s apart (:23.758 → :39.602),
  both exit 0**; plus one unsupported Write attempt and one update_goal.
  This is an OUTER model retry that executed twice — the exact residual the
  doc frames gently ("model recognized the objective is achieved"). The
  idempotent printf masked all harm; a non-idempotent op would have doubled.
  Outputs for all calls batched at :17 (rollout batching, not execution order).

## Verdict (Claude's expected shape, CONFIRMED with one sharpening)
**Inner duplicate eliminated in observed runs; outer retry duplicates still
possible (demonstrated, not hypothetical); no exactly-once claim.**
Sharpening: the 4.4 trace is not merely "denial perception" — it is two
executed outer side effects for one prompt under --mode build. The report's
matrix is numerically accurate; its prose understates this point.
Residual confounds (minor): installed-09-26 binary vs current debug build
differs by more than the mode flag (stub test isolates the mechanism, keep
it cited); Arm B update_goal status "blocked" vs Arm A "complete" shows
model behavior already diverging under denial perception. Denial-suppression
ticket remains the correct next fix; retry-idempotence (stable op ids) the
one after.
