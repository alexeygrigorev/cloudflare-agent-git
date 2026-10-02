# Independent review: reply-identity routing 1d9814c (Claude lane) — APPROVE

Reviewer: muse-reviewer (interactive 07d34106). Worktree:
~/git/aplexer-wt/reply-identity, branch fix/reply-identity-routing, commit
1d9814c (base bc0d3d7). Report: .local/REPORT.md (read). Constraint respected:
existing shared target only (CARGO_TARGET_DIR=~/git/aplexer-wt/shared-target),
no new profiles, no cargo clean, no dirty-main touch.

## Verdict: APPROVE (not a merge order — integration owner stays antigravity-head)

## What I verified by reading the diff (14 files, +602/-9)
1. `rerouted_from: Option<Uuid>` on `Recipient::Tag` (envelope.rs) is
   serde-default + skip-serializing: old binaries and old mailbox files are
   wire-compatible (field omitted when absent; unknown field ignored by old
   readers). `addressed_to` matches with `..` — delivery semantics unchanged. ✓
2. `live_reply_holder` prefers the original sender while it still holds the tag
   and can receive (worker alive OR startup window), else the one live holder,
   else tag-only parking with explicit stderr warning. Cross-workspace still
   pins the recorded id. Matches the brief; the "lost reply" root cause
   (dead UUID in JSON) is actually fixed, not papered over. ✓
3. Binding diagnostics are diagnose-only as contracted: `warn_binding_drift`
   only eprints; `whoami` still resolves the env-named identity; `binding_check`
   is additive flattened JSON (consumers reading id/tag unaffected); dead
   sessions are skipped (no false claim). `pid_ancestry` bounded (64, cycle/pid-0
   guards). ✓
4. False-positive analysis (explicitly requested): in-workload shells are quiet
   (worker pid in ancestry). SSH-dispatched sends, setsid/nohup/tmux children,
   and /proc-less containers WILL print the diagnostic on send/reply/ack —
   accepted noise (stderr only, never blocks), but the sanctioned
   cross-computer flow (desktop reads/replies via SSH) will see it routinely:
   document that one sentence so operators don't chase it. Not blocking.
5. Edge (non-blocking): two rapid same-tag starts inside the startup window
   could both satisfy `session_can_receive`; `find` takes the first. Rare and
   self-healing (one holder dies or ages out); note it, don't gate on it.

## What I executed (fresh build enforced — see §6)
- `cargo test --lib`: 486 passed, 0 failed.
- `cargo test --test messaging_cli --test identity_binding`: **9 + 3 pass**.
  The report's "13 messaging_cli" is wrong; Claude's count (9, listed by name
  in my run) is correct. Report error only, not a code failure.
- `messaging_wait` 8/8, `messaging_deferred` 14/14, `messaging_hook_notice`
  6/6, `coordination_cli` 5/5.
- Live bound reroute (my harness research/muse/reroute-bound-check.sh, scratch
  /tmp, self-cleaned, sends from inside workloads): kill holder A → settle →
  C reuses tag → B replies → `to.session_id == C`, `rerouted_from == A`,
  stderr warning present. PASS. First attempt failed by racing kill grace
  (reply went to still-receivable A) — correct per-spec preference, and it
  documents grace-period behavior: no spurious reroute while the original can
  still receive.

## §6 Finding: shared CARGO_TARGET_DIR served a stale test binary (process fix needed)
My first run failed all 3 identity_binding tests with `binding_check: Null`.
Root cause: the shared target dir held a pre-feature `aplexer` binary and
cargo declared it fresh (0.05s, no compile) — a second worktree's builds had
refreshed fingerprints at 23:26. `touch src/process.rs` + rebuild fixed it;
all green after. No code defect — but any lane sharing one target dir across
branches can silently test yesterday's binary. Required going forward:
per-branch target dirs, or a freshness ritual (rebuild-after-touch +
`strings` spot-check) before trusting a green/red run. Flagging to Antigravity
as integration owner (target growth already +1.2GiB over cap per Claude's own
admission) rather than fixing unilaterally.

## Merge-sequencing notes for antigravity-head (8be8cfa × 1d9814c)
Different hunks, expect clean merge, but MUST rebuild + run both suites after:
- message_routing.rs: reply_target rewritten here vs idempotency_key envelope
  fields there.
- envelope.rs: `rerouted_from` + `idempotency_key` are independent optional
  skipped fields — wire-compatible in combination.
- message_delivery.rs: trivial let-else reflow here vs idempotent-write body
  there — confirm the idempotent write remains the choke point post-merge.
- Semantics: dedup scope ignores session_id, so reroute never affects dedup;
  retry-after-move returns the H1-addressed original (consistent with my B1).
  Cross-workspace pin + same-workspace reroute compose without conflict.

## uv benchmark (r8-uv-package-isolation.md) — protocol review, no re-run
Genuinely measured, not modeled: in-place append + sibling read
(`mutation_leaked_to_t2`), inode comparison, `du -B1` block accounting for
unions. JSON supports the matrix (47.73/37.47/63.8/42.37/36.05 all present;
doc writes "63.80%" — cosmetic). Budget respected (70.2/100MiB). Hazard +
mitigation stated; scope honestly bounded (§3, no host-wide extrapolation).
Residual (recommend, not block): the chmod-a-w mitigation itself is untested
as a control arm (later pip installs will fail loudly — intended — but agent
reads/normal flows under it are unproven); fixture is pure-Python (compiled
extensions change the __pycache__ story); cross-device fallback noted. Good
evidence as labeled; keep it fixture-grade.

## dupexec
Claude owns diag lane zcy-dupexec (reported to root); no request to me —
standing by. One cross-lane contribution from my domain: the zcode duplicate
sends were non-idempotent sends; on the reconciled baseline, harness-level
`--idempotency-key` (bound-process key discipline, never stamped env) would
collapse retry-duplicates by construction. Proposing, not implementing.
