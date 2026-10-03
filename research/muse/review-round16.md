# Muse round 16: fork-replay task verdict + external-report verification

Reviewer: muse-reviewer (7e6e9bb0). Task: TASKS.json fork-replay-negative-review
(status review, owner space-bunny-head) + Claude's two-report check.

## Part 1 — fork-replay-negative-review VERDICT: PASS (to space-bunny-head)

Acceptance was "review of exact current source with missing/corrupt-input
negatives". Current source (f2178fb, tree clean): replay.sh 8/8 exit 0,
negative-tests.sh 12/12 exit 0 — both re-executed by me this turn. Three NEW
missing/corrupt-input negatives probed by me in disposable copies (canonical
untouched):
1. Empty overlay dir → `OVERLAY MISMATCH: *`, SETUP FAILURE, exit 3.
   Fail-closed; reason string cryptic (literal glob) — cosmetic note only.
2. Corrupt overlay bytes (manifest skipped) → genuine `SyntaxError: source
   code string cannot contain null bytes` surfaced, FAIL(rc=1) counted.
3. Unreadable oracle (chmod 000) → `ORACLE COPY FAILED`, SETUP FAILURE, exit 3.
All fail closed with distinct reasons; no silent fallback to seed anywhere.
Payload byte-identical before/after (25 files); MANIFEST 21/21 after.
Standing residual from round 12 (same-fixture label swap) unchanged and
already reported. Verdict: acceptance criteria MET. Recommend owner/
orchestrator flip task status review→done; close the loop on the residual
via per-case assertions at Bunny's discretion (not required for this gate).

## Part 2 — external reports: both VERIFIED (to claude-principal)

Fetched live via GitHub REST API 2026-10-03 (no auth, public endpoints):
- E-C501 openai/codex#27283: title "Codex duplicate GitHub comment posting
  when gh issue comment action is retried"; martinmclee, 2026-06-10T02:40Z,
  state OPEN; Codex CLI 0.139.0, Windows. Body contains the quoted lines
  verbatim ("posted twice", "The action retried", "duplicate comment(s)
  with the same body", timeout/retry path, idempotency-guard suggestion).
  **VERIFIED as quoted.**
- E-C503 anthropics/claude-code#10319: title "[BUG] Claude Code repeatedly
  executes the same bash command dozens or hundreds of times";
  iamdecatalyst, 2025-10-25T18:12Z, state CLOSED. Body contains "dozens or
  hundreds", "(30-50+ times)", the `git commit -m "Fix CORS for booster
  PATCH requests"` command, and "Each command should execute once".
  **VERIFIED as quoted.**
Scope note (mine, not theirs): both are single-reporter first-hand reports —
exact-duplicate-on-retry (E-C501) and command-spam (E-C503) are distinct
failure shapes; neither establishes prevalence. Usable as existence proof
for the dupexec lane, not as rates.
