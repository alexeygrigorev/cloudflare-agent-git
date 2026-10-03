# Muse round 17: pane-delivery verification — NO COMMIT YET + negative spec

Reviewer: muse-reviewer (7e6e9bb0), per claude-principal 01a0ffdc. Searched:
cloudflare-aplexer-protocol all branches, ~/git/aplexer all branches
(incl. fix/continuation-readiness-pane-race — ZERO unique commits, same tip),
aplexer-wt worktrees. No pane-delivery verification / readiness commit
exists. The only uncommitted pane-adjacent diff (~/git/aplexer dirty tree)
is a stale duplicate of already-reviewed a7040ac content — inspected
read-only, untouched. Verdict to Claude + antigravity-head: nothing to
review yet; staying available.

## Negative-test specification for the forthcoming fix (reviewer demand)

The sec-27.3 plan (verify paste landed or agent working before recording
delivery=pane, else uncertain/inbox) is reviewable only with these negatives;
I will hold the fix to all four plus the interplay check:

- N-P1 late-input TUI: fake TUI accepts PTY bytes but renders late/drops
  them. `--pane` send must record delivery uncertain/inbox, NEVER pane.
  Assert on the persisted envelope, not the exit code alone.
- N-P2 idle opencode composer (positive control): empty idle composer,
  `--pane` succeeds with delivery=pane and the framed text readable in the
  PTY capture.
- N-P3 busy/draft composer: unsubmitted draft bytes present; `--pane` must
  refuse, queue, or provably preserve the draft — assert draft bytes intact
  in capture afterwards. Silent overwrite is the failure.
- N-P4 delivery-uncertain not freely retryable (Codex constraint): after an
  uncertain outcome (.attempt marker present), an immediate retry must NOT
  perform a second PTY injection — assert exactly one PTY write in the
  capture log and a non-success resubmission outcome naming the stored id.
- Interplay (must not regress): keyed retry still returns the same envelope
  id via write_message_in_idempotent; pane reservation still keyed by
  message id (submit_message_in prior_submission). Any change to
  finish_pane/submit_message_in re-opens my round-3 pane analysis.

Mechanism note for the implementer: the current safety already lives in the
submission reservation (.attempt marker + delivery==Pane short-circuit),
not in finish_send; the fix should strengthen the VERIFICATION before
marking, not add a second tracking layer that can disagree with it.
