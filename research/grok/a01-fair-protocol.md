# A01 fair pair, preregistered

2026-10-02, Europe/Berlin. Owner: grok-head `39e95f91-19ee-48fc-8a83-c25e199813b6`. This is the corrected execution already authorized by HEARTBEAT2024 `01a0fe4d-bec0` and HEARTBEAT2024-MILESTONES `01a0fe4f-3634`. No new root assignment. D-G23 stands: `a7ecdd4` / `ab84753` is feasibility and negative methodology. The 117 second gap between `3418b21` and `95a2ead` is elapsed commit time, not repair effort.

## What is the same

- Tasks: `research/codex/a01-live/task-a.md` SHA-256 `dcd4a4e9660fafa8dcdc62b90330c1ff5c0fa3e3afaa31b3683f6052d7a3ab03` and `task-b.md` SHA-256 `c99a0c0057d968ccaa43f5443f07543aeca922cc45e6db4984299b3ec4a3a138`, plus `research/grok/a01-fair-interface.md` byte-identical on every session. Prepared prompt SHA-256 A `17c08e5b0e8714eb1bfa86798f0681f33c248a2154752c8f779ffabe5ad95116`, B `cd77753d2a6d1afdaa348eef8732a933fe3cf3e3493e60ac8101e3cd3e52d1ea`. Seed commit `b529dc1a68214b16cc57f199ff32a79445bea3c5`. Check SHA-256 `aa11fae87c064a53139ab20c68882933537ff8a5ba950920a31fcf69cdf6192e`. Scratch self-test passed before dispatch.
- Model `glm-5.3-flash`, provider `zcode`. Timeout 20 minutes. Memory cap 512M and 64 pids per session.
- Oracle: `research/codex/a01-live/oracle.py` SHA-256 `56482a4b79ef05104859c09304d35cc96d70c3923e562923b7f19641ccbc5d2a`. Both arms run `research/grok/a01_fair_check.py`.
- Two writers per arm, arms one after the other because the cap is two live executors.

## What differs

`a01_fair_publish.py` copies the other writer's owned files into `./peer`.

- Completion copies `git show HEAD:file` and only after the bytes differ from the seed.
- Live copies the working tree, including uncommitted bytes, under the same rule.

The prompt does not say which policy is active. A peer that still matches the seed stays empty, so the baseline sibling is not treated as unfinished WIP.

## Scoring

Per role, report the 2x2. Task pass and oracle pass are both required. Oracle pass with task fail is a failure.

- Role A task pass: committed or present `cache-notes.md` nonempty and `reader.py` differs from the seed. `cache_observable` is recorded and not required. The task allows a correct bypass.
- Role B task pass: `bulk-notes.md` nonempty, `writer.py` differs from the seed, and `update_many` of three keys calls `put` fewer than three times.
- Self oracle: the common oracle on that role's own tree.
- Composition: role A's reader with the peer writer, or role B's writer with the peer reader. Unavailable when the peer file is absent. That is not a failure during the session. The arm result still reports composition of the final trees once both sides exist.

Repair effort is the count of check invocations after the first commit, the later commits, and the numstat of owned files after the first commit. Wall-clock between commits is elapsed only.

N=1 is not the 3-agent / 10-push gate and not a sign-off.

## Workflow changes under human22

- Separate clones, not four worktrees of one repo. Tradeoff: a few extra kilobytes and no shared object store. Gain: each index is independent, after the first pilot's ambiguous "nothing added" commits. Shared Git was not proven index corruption. Success signal: each repo's log replays from its bundle. Failure signal: a session commits the other writer's file as its own.
- Headless `zcodex exec`, not an interactive composer. The project head stays interactive. Tradeoff: one-shot sessions can exit before `final.md` exists, as the notice arm did. Success signal: `FAIR_RECEIPT.json` and at least one commit per role. A missing receipt is a recovery gap. It is not invented.
- Codex's seed under `.local/codex/a01-pilot-20261002/` is not the run directory. The same three source files are cloned into a new scratch. The offered seed stays unmodified.
- ZCode harness files are not edited. This driver is the execution lane's thin runner.

## Evidence

Scratch `/tmp/grok-a01-fair-20261002` stays until an independent reviewer releases it. A private bundle goes to `.local/grok/a01-fair-20261002/`, which Git ignores. Do not delete either as scratch cleanup.

## Decisions

| ID | Decision | What reverses it |
|---|---|---|
| D-G23 | The unequal-prompt pair remains negative methodology. | Unchanged by this protocol. |
| D-G24 | Run this equal-policy pair once. Do not call a separated outcome uptake proof. | Prompts, model, timeout, or check command differ across arms, or the completion peer receives uncommitted bytes. |
