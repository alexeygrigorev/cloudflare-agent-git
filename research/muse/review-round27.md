# Muse round 27: A10 HARD CASE worker (muse-r4) — RECOVERY COMPLETE, verified

Head: muse-reviewer (7e6e9bb0), per claude-principal (Codex 01a10035-d061).
Delegate: native session muse-r4 (closed/reaped), headless opencode executor
(--auto bounded, 800s cap), brief limited to checkpoint + committed baseline
+ current HEAD read-only. Checkpoint .local/a10-hardcase/ verified intact
(patch + filelist SHA256 match MANIFEST).

## Worker first output (report, 13 lines)
Task/base/policy/done-not-done all stated: stdlib-only TASKS.json validator
task; attempt-1 base 7ad05d7 + uncommitted 2-hunk patch; attempt-2 uncommitted
dir; accepted policy = preserve attempt-1 verbatim, no overwrite, no third
copy. Rebase performed in disposable copy (git archive HEAD → /tmp): patch
applied zero-fuzz, 6/7 attempt-2 files restored (stale .pyc excluded),
suites 39/39 + 37/37 green first run. UNKNOWNs: session-start epoch (not
captured), attempt-2 author id, live TASKS content at attempt time. Wrong
actions: one ineffective git command in non-repo copy. Repair effort: zero
tool-code fixes needed. RECOVERY: COMPLETE.

## Head verification (mine)
- Re-ran both suites in the worker's disposable copy: 39/39 + 37/37 — exact.
- Checkpoint SHA256 intact post-run; frozen paths untouched.
- Canonical concurrent edits (claude.md, a05 attempt-1 files) predate the
  worker (mtimes 04:19–05:00 UTC vs worker window) and sit in peer-owned
  lanes — unattributed to muse-r4 (brief forbade, log clean).
- Session reaped, /tmp cleaned. No mailbox, no network, no canonical writes.

## Assessment
A cold worker CAN rebase interrupted work onto a moved base from checkpoint
+ committed history alone, with honest UNKNOWNs and zero tool repair. n=1,
no generality claim. The 27s-class recovery (round 26) reproduced at harder
scope with real test proof.
