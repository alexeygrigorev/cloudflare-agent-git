# A06 adoption decision

2026-10-03. Reviewer: grok-head `8840df13-d5e9-451f-b567-a3da6ecad891`, conversation `01a0fe00-6ecd-7c73-a852-e9862578d192`. This session replaces `39e95f91`. Assignment `01a0ff60-14c0` (`C-0124-G-A06-REAL-DECISION`) and handoff `01a0ff63-833e`. Plan `b66611c` stays the prospective design. Cards D1 and R1 stay excluded from timing.

## Preregistration and exposure

Question, fixed before the source read: for pending task `G-A01-SHADOW-CONSUME-20261003`, does this team adopt ZCode's shadow-consume runner as the result of that task?

Owner of the patch: `zcode-independent`. Artifact: `research/zcode/independent/a01-shadow-consume-runner-v0.py` at `71d3cd4b07856f03226ea635524d4c17881509ad`, event-line dedup `4254a4c`. Same evidence for a plain reading and for this card: that file, `a01-harness-skeleton-v0.py` `scan_once`, `a01-consumer-adapter-plan-v03.md` line 19, and Muse `research/muse/review-round9.md` section 2. No extra test. The runner was not executed. No hidden corrected label.

Prior exposure: commit subjects from `git log` were visible before the file was opened. The diff, `scan_once`, the plan line, and Muse section 2 were then read in this turn. This is an adoption decision. It is not a blind timing or catch-rate measurement.

## Card

Claim in the runner: empty `shared_worktree_pairs` means the harness warning condition never existed, so `eligible_warnings` is 0, `zero_warning_undefined` is true, and `discovery_action` is `none`.

Pinned source: `eligibility_structure` reads distinct paths from the bundle manifest and from `--cwd` fields in `a01_fair_run.py`. `main` sets the zero-warning flag when no two manifest repos share a path. The caveat says a single writer per worktree means the two-writer conflict never existed.

Checker: `scan_once` in `a01-harness-skeleton-v0.py` pairs WIP trees across agents. Each agent has its own `spec["wt"]`. The v0.3 plan says separate clones and two writers per arm. A missing shared path does not show that the cross-worktree pair scan had nothing to compare.

Observed outcome: the fair-pair launch used separate directories. That matches the manifest shape the runner treats as zero. It does not match a reading of `scan_once`, which compares peers in different worktrees. Token counts in receipt filenames are collected and are not bound to an emit or consume event.

Excluded guarantees: uptake, a re-run of the runner, bundle SHA containment (the commit message says 8/8; this turn did not rehash), and production dupexec one-effect. `--emit` stays off.

Decision: reject adoption of `eligible_warnings: 0` as the shadow-consume result. Withhold emit. The task stays open and unlabeled, not closed as null benefit. Next bounded event is a ZCode revision that either binds eligibility to frozen emit, delivered, or consume events, or labels eligibility undetermined. Grok does not edit that file.

## CodeRabbit

Vendor pages [navigation](https://docs.coderabbit.ai/change-stack/navigation) and [snapshots](https://docs.coderabbit.ai/change-stack/snapshots), read 2026-10-03, already provide layered reading order, per-snapshot viewed progress, and a merge control that refuses a stale snapshot. Change Stack is preview. Those controls do not record an excluded guarantee. A card that says "separate directories do not prove zero eligible warnings" is the difference under test. CodeRabbit effectiveness was not measured. This is the same incumbent limit as `b66611c`.

## A05

A05 asks whether two plausible alternatives for one task change the selected outcome when policy, tools, and evidence are the same, with ties allowed and discarded effort counted. This decision is one claim on one artifact. It does not choose between two task implementations. The fair A01 writers had complementary jobs, so that pair still does not score A05. The gates stay separate.

## Limits

No live trial, no new writer, no dupexec patch, no sign-off, and no sixth-slot claim. Antigravity owns implementation. Muse `2d6712c` already called the headline invalid; this card agrees from the source above and does not add a second experiment.

## Rev1 update

2026-10-03, same reviewer, handoff `01a0ff74-63ec`. Read `9ed2ab2a873ca81f87dd263022bc02d43cc33c48`, `22a556e5a48a1e1fb7784f542dd8d0acbfc6e2a5`, `a65a5e36270234446e5c4e383e07da2d0f6f1eb8`, and Muse `993055ffc24b0bfd47ae2acdc98dcf443290f4fa` (`research/muse/review-round11.md`). The runner was not re-executed in this turn.

`derive_eligibility` no longer reads shared paths. `withdrawn_claims` lists structural zero, the shared-worktree eligibility condition, and the claim that the conflict never existed. On the retained timeline the function returns `eligible_warnings` `"unknown"` and `warning_rate` `"undefined"`. `finding.binding_target_claimable` is `False`, and the binding note retracts the zero-warning success path. Default `--emit` still returns 2 when bundle SHAs are unverified, before a result file is written. Muse reports that refusal as exit 2 with no file, schema keys 12/12 against the skeleton, and a reproduced unknown label. Those process results are Muse's; the source matches the refusal branch and the unknown branches.

`22a556e` repeats the `9ed2ab2` plan addendum. `a65a5e3` deletes that second copy. One addendum remains in `a01-consumer-adapter-plan-v03.md`.

Decision update: accept rev1 as the correction of the rejected v0 claim. The shadow-consume task stays unlabeled. Unknown is the recorded state, not a null-benefit close. Emit to the repo default stays off until Codex accepts rev1, which the runner docstring still requires. Muse's open items stay with ZCode: filename overlap is a precondition rather than a conflict finding, the `(event, ts)` dedup key drops or duplicates the wrong lines, typed counts are presence-only, and the repo-default emit gate is not enforced in `main` beyond the SHA and sanitizer checks. None of those reopen structural zero.
