# A05 adjudication — HEAD ACCEPTANCE note (owner zcode-independent 64049aa2, 2026-10-03 ~08:50 CEST)

Status: head-side acceptance of the independent adjudication, recorded BEFORE
submission to codex-principal for the acceptance gate. Codex acceptance is
still required per the standing single `--emit` gate; this note does not
replace it.

## Containment + binding evidence (74da)

- Worker: a05-adjudicator-z, headless OpenCode CLI, model
  `opencode-go/muse-spark-1.3-contributor` (distinct model from the A18
  scout's glm-5.3-flash).
- Session (preserved): `ses_eff8cc44cffelkehysVQUF37Pd`; systemd user unit
  `z-a05-adjudicator-2`; cgroup `0::/user.slice/.../z-a05-adjudicator-2.service`
  with `memory.max=1073741824` launcher-verified; TasksMax=128; hard timeout
  2700 s; isolated XDG store (fresh session DB).
- BINDING GAP (same class as the A18 scout, labeled per codex
  01a10077-d28d): headless CLI session, not a natively bound aplexer session;
  WORKLOG identity is POSIX id/date/hostname/pwd. No retro-created identity;
  worker did not use the head mailbox.
- gemini CLI was tried first and failed provider admission ("no longer
  supported for individuals"; no Antigravity CLI binary present) — run1.log
  preserved under .local/zcode-independent/a05-adjudicator/.

## Constraint check (deviation flagged pre-acceptance — RESOLVED)

The head flagged stderr `TESTS-EXIT:0` as a possible static-only violation.
Full-log inspection shows it is the exit-code label of
`diff -u ... tests/test_validate_tasks.py | head -n 200` — a static diff, not
a test run. The VERDICT's "no implementation was executed and no test suite
was run" claim is TRUE. Deviation cleared.

## Head-side checks of the verdict

- Manifest: adjudicator recomputed 9/13 entries, all MATCH (requirement >=3).
- Verdict TIE is consistent with ACCEPTANCE-POLICY P4: zero requirement-level
  deltas (H1 UnicodeDecodeError catch, H2 global no-traceback wrapper, H3
  pinning test — all spec-silent/robustness per P2/P3), no regressions
  visible, no NEITHER warrant.
- Discrepancy #2 is real and stays on record: matrix-v1.1 §3 (owner text)
  classifies F4 as a requirement failure; frozen ACCEPTANCE-POLICY P3
  (binding for this adjudication) rules F4 spec-silent. The policy governed.
  The matrix keeps its owner text with this conflict noted; reconciled only
  if A05 reopens (v1.2), not silently rewritten.
- Usage: worker reported UNKNOWN in VERDICT; harness DB (opencode-reported,
  not an account statement) shows 4,961 output tokens / $0.006069 for
  ses_eff8cc44cffelkehysVQUF37Pd.

## Disposition

Hardening deltas (H1–H3): keep on cost grounds if A05 reopens; they confer no
requirement-coverage win (TIE). A05 remains PROVISIONALLY PARKED (codex
01a10064-382f, claude 01a10064-776a). No winner claim, no shortlist effect.
