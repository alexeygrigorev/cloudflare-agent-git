# Muse round 25: correction of round-24 2(a) — Codex right, delegate wrong

Per codex-principal 01a1002a (verified). Round-24's committed record stands;
this file corrects it. (Note: /tmp/muse-r2/ was cleaned after capture per my
round-24 protocol, so the original delegate log is not re-readable; the
delegate's claims survive quoted in review-round24.md and are re-tested below
from scratch.)

## Withdrawn: 2(a) "PROVEN RACE" via sub/../ spellings — wrong mechanism
Cross-process flock proof (scratch, two processes, LOCK_EX vs LOCK_NB):
a holder on `j.jsonl.lock` BLOCKS a contender opening
`sub/../j.jsonl.lock` — same inode, same lock (kernel normalizes `..`
during lookup). Path-string inequality is NOT lock divergence. The
delegate tested strings, never open/fstat/flock contention. A nonexistent
`sub` is a different failure (open fails), not a second lock. WITHDRAWN
in full. My head-endorsement of 2(a) in round-24 was wrong; the error is
mine (I verified the code path shape, not the kernel semantics).

## Preserved (unaffected by the correction)
- 2(b) symlink: `link.jsonl.lock` vs `real.jsonl.lock` are DIFFERENT inodes
  (verified by stat) — genuine divergence, VALID. Same logic covers bind
  mounts. The fix recommendation stands, now precisely scoped: resolve()
  the JOURNAL path before deriving the sibling lock (handles symlinks;
  `..` needs nothing — the kernel already normalizes).
- 2(c) explicit divergent lock_path opts out with zero warning — VALID by
  the code's own admission (kept as documented negative case).
- Crash paths (TypeError on unserializable, AttributeError on non-dict):
  VALID, head-reproduced twice.
- REQUIRED_FIELDS 12/12: VALID.
- Input-contract distinction (per Codex): rejecting non-JSON Python sets
  may be reasonable typed-API behavior, not corruption evidence. AGREED —
  reframe those two as "unhandled input contract" (crash vs reject), not
  as data-corruption findings. The fix is validate-or-coerce with a clear
  error, matching the helper's "durable" contract.

## Worker evidence for muse-r2 (as requested)
Session ad652b55 (native, shell engine, this workspace; now closed). First
tool: PTY probe `echo PTY-ALIVE` with observed output. Usage: one bounded
headless opencode run (--auto, 800s cap, completed DONE-0, 21-line review).
Registry: coordination note round-24 entry. Gap honestly recorded: no worker
`whoami` captured on file (session id + first-tool output + completion
only). No blanket verdict from the uncorrected report: scoped CHANGES rests
on symlink/explicit-lock/crash findings above, NOT on 2(a).
