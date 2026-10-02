# Local validation, execution round 1

2026-10-02. Run `python3 research/codex/merge-fixture.py` from repo root. Requires Python 3 and Git, no credentials or dependency installation. The script creates a disposable synthetic repository, commits baseline and two separate branches, runs individual checks, merges, and checks the combined state. It removes the temporary repository on exit. This is a deterministic fixture, not a live concurrent-agent demo, market study or Artifacts integration validation.

Observed result: A's one check passes (exit 0); B's two checks pass (exit 0); Git textual merge succeeds (exit 0); combined checks fail (exit 1) with `KeyError: 'given'`. A migrates the greeting contract and existing caller while B adds a new caller using the old contract. The new caller's failure establishes the concrete acceptance fixture for a merged-state gate. It does not prove an intent-reapplication agent can fix it or that a new platform beats GitHub merge queue.

The fixture deliberately includes an approved-contract-change scenario: a baseline acceptance suite needs versioned policy evolution when the human approves an API migration. Blindly freezing every historical test is insufficient, while letting a candidate choose its own required suite permits tampering. Prototype design must distinguish human-approved policy updates from agent changes and identify the exact policy version in each receipt.

Next falsification: run two actual coding-agent processes from the same base, hold their final commits, combine and test, preserve failed attempts, then reapply one unchanged task contract on the fresh base with bounded retries. Remote Artifacts publication and stale-head denial need their own tests. No such pass is claimed here.
