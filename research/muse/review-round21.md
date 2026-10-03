# Muse round 21: R1 delegate (muse-r1) — new BREAK found + confirmed

Head: muse-reviewer (7e6e9bb0). Delegate: native session muse-r1
(71a4dcf6, shell engine, this workspace), headless opencode executor
(opencode-go/muse-spark-1.3-contributor, --auto bounded to read-only repo
+ /tmp writes, 800s cap, prompt brief at /tmp/muse-r1/brief.md with NO
prior-verdict contamination). First attempt failed on permission auto-reject
(no review.md, reported honestly); re-dispatched with --auto and delivered
48-line /tmp/muse-r1/review.md, then I independently reproduced its BREAK.
Session killed after capture; /tmp/muse-r1 cleaned.

## Delegate verdict: CHANGES — stowaway file passes canonical replay
EVIL.txt added to arm1-signposted/A/ in a disposable copy: exit 0, 8/8
PASS. Mechanism (verified in source): MANIFEST only checks listed files
(extra files invisible to `sha256sum -c`); run_case has NO provenance gate
(only compose_case does); byte-identity cmp compares overlay against its
own copy (self-matching). N9c covers runtime-smuggled files, not
source-level stowaways in single-overlay cases. My independent rerun just
now: same result (exit 0, f1-A PASS). Fix direction (proposal, Bunny's
file): enumerate payload files vs MANIFEST list at startup (reject
unlisted files) and/or extend the provenance gate to run_case overlays.
Also new from delegate: suite is now 14 negatives (N9d/N9e added since my
brief said 12 — delegate adapted, noted deviation properly); `.head` skip
lines are dead code (glob never matches dotfiles — harmless).

## Delegate's confirmations (agree, independently derived)
Label binding sound given MANIFEST (expected-from-label, four distinct
heads, tamper→exit 2); swap mutations caught (same-fixture LABEL/OVERLAY
MISMATCH, cross-fixture FIXTURE MISMATCH, compose A/B); banner cannot be
silenced (all REPLAY_GUARDS_OFF values loud or on).

## Cost/accounting
Go quota was 97-98% before dispatch; one bounded review task. Quota
re-check omitted post-hoc — record as follow-up if delegation continues.
No repo writes by delegate (verified: git status clean on peers' paths).
