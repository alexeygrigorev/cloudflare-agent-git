# Muse round 14: transcript-locate 86ce5d4 + Bunny f2178fb re-review

Reviewer: muse-reviewer (7e6e9bb0). Shared-target discipline: relinked in the
worktree under test, digests recorded; no clean/new profiles; no dirty-main
touch; all destructive probes in /tmp scratch.

## A. fix/zcodex-transcript-locate 86ce5d4 — APPROVE (binary a96c00f7)

Rebuilt in ~/git/aplexer-wt/transcript; digest `a96c00f7...` matches Claude's
recorded build exactly. Suites: transcript 6/6, lib 506/506 (report's 506
confirmed), agent_events subset 38/38.
- Root cause correctly identified (recorded env lacks CODEX_HOME; fork
  defaults to ~/.zcodex) and fixed at the right layer (engine-aware root
  list; CODEX_HOME still pins exactly one root for any engine). ✓
- codex (non-z) path byte-identical behavior: `_` arm → single .codex root;
  public `locate_codex_transcript` hardcodes "codex". ✓
- Ambiguity: merged multi-root pool re-sorted newest-first
  (`candidates_newest_first` over all roots); caller refusal path untouched;
  mtime + session_meta-cwd filters apply per candidate regardless of home.
  e2e decoy test covers the two-home shape. `walk_jsonl` tolerates missing
  roots (no new crash surface). ✓
- No interference with idempotency lane (untouched files; envelope/recipient
  not involved). Merge sequencing stays with antigravity-head.

## B. Bunny f2178fb re-review — provenance repair verified, one residual hole

Executed: replay.sh 8/8 exit 0; negative-tests.sh 12/12 exit 0 with live
TIMEOUT (exit 4) and FAIL(rc=3) rows — N3 now genuinely tested (manifest
skipped in-copy by design, documented). Payload byte-identical before/after;
MANIFEST 21/21.
- Provenance rule (fixture-aware source membership) closes my round-12
  franken-tree hole for the CROSS-fixture case (N9b pins it; N9c pins
  stowaways). My requested attack — same-name foreign content slipping past
  comm: analyzed — content trust roots in MANIFEST (pinned bytes), which the
  rule assumes, not replaces. Given manifest integrity the rule is sound;
  without it no filename rule could hold. Correct layering, not a hole.
- RESIDUAL (demonstrated in disposable copy): same-fixture label swap
  (f1-A built from B overlay, label kept) still passes 8/8 silently.
  Provenance is fixture-aware, not label-aware. Bounded (requires script
  edit, visible in diff); scripts unpinned by MANIFEST (git hash is the
  pin). Proposed: per-case content assertions (the documented OrderedDict
  check, generalized per case with correct per-case markers). Not applied
  (Bunny's file).
- Count discipline on 12: each asserts a distinct reason + nonzero exit plus
  a clean control; N9b/N9c assert refusals (non-vacuous by construction —
  removing the guard flips them to BAD). No inflation beyond the 12 lines.
- Symlink note: no symlinks in payload; `find -type f` scans would miss a
  smuggled link — one-line hardening (`! -type d`), theoretical only.
- Abandon-harness question: NO — hand-running is strictly weaker (zero
  guards). The harness is convincing for its stated scope (mechanical
  reproducibility with fail-closed guards); the label-binding residual is
  documented above. My round-12 residue judgement stands unchanged.
