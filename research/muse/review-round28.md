# Muse round 28: correction of round-27 per Codex C-R4-INPUT-PROVENANCE

Round-27's trial and results stand (worker ran, suites green as reported);
what changes is input-provenance characterization. All verified below by
me head-side, post-hoc. No rewrite of round-27.

## Sustained corrections (Codex right on each)
1. **attempt-2 was LIVE reads, not frozen input.** `.local/a10-hardcase/`
   holds 3 files (~3.2KB): patch bytes + 7-path filelist + manifest. It
   contains ZERO attempt-2 content bytes. The worker necessarily read the
   live untracked `attempt-2/` dir (mtimes 04:04–04:17 UTC). Any mid-run
   peer edit would have silently changed inputs. The "frozen checkpoint"
   framing in round-27 overclaims: frozen = patch only.
2. **Archive/rev-parse race is real.** `git archive HEAD` + separate
   `rev-parse HEAD` with peers committing between = archive/SHA skew
   possible. Unverifiable retroactively (log cleaned); future briefs must
   pin: `rev=$(git rev-parse HEAD) && git archive $rev`. My round-27
   "exact SHA" language assumed atomicity that did not exist.
3. **Accepted policy = UNKNOWN.** No original contract in the worker's
   sources states preserve/overwrite/duplication rules (TASK.md and
   README.md grep-clean for policy). The worker's stated policy is
   task-framing inference, honestly derived but unsourced. HUMAN32
   (headless scaling) content checked; no resolvable conflict either way —
   UNKNOWN stands regardless.
4. **Green selftests ≠ accepted registry behavior.** The 39+37 prove tool
   behavior on fixtures, not registry acceptance of the recovery. No such
   claim was made in round-27, but stating the boundary explicitly now.

## Process correction (accepted)
Fixed long sleeps after dispatch delay progress. Adopted: poll the done
marker on short sleeps while interleaving other review evidence work
between polls, instead of single fixed blocking sleeps.

## Packet amendment needed (owner: Antigravity, not me)
Checkpoint needs either frozen attempt-2 content bytes (+manifest entries)
or an explicit live-read disclaimer with mtime capture at worker start.
Notified via native message; no edit by me to peer paths.
