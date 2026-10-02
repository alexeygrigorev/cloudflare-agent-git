# A01 fair pair, N=1 result

2026-10-02, Europe/Berlin. Owner: grok-head `39e95f91-19ee-48fc-8a83-c25e199813b6`. Protocol `research/grok/a01-fair-protocol.md`, commits `7ef2269` and `2f4681c`. Registration `G-A01-FAIR-REG-20261002`. This is not the 3-agent / 10-push gate and not a sign-off.

D-G23 stands. The unequal-prompt pilot remains negative methodology. The 117 seconds there were elapsed time.

## Run

Model `glm-5.3-flash`, provider `zcode`. Fresh `quse` before each arm: status ok, `limit_reached` false, 5h 100% remaining, weekly 82% remaining. No banked reset. Scratch `/tmp/grok-a01-fair-20261002` is 1,211,437 bytes. It stays. Private bundles are under `.local/grok/a01-fair-20261002/`, mode 600. Oracle SHA-256 `56482a4b79ef05104859c09304d35cc96d70c3923e562923b7f19641ccbc5d2a`. Seed `b529dc1a68214b16cc57f199ff32a79445bea3c5`.

Both arms used the old poller. It waited until the 22-minute deadline after the writers had already exited, because a reaped session disappears from `aplexer list`. `sessions-completion.json` and `sessions-live.json` are `{}`. Terminal ids reconstructed from the poll logs:

| Arm | Role | Session | Tag |
|---|---|---|---|
| Completion | A | `15ff0901-6ca4-40ea-a8f8-b3cc5eae94af` | `grok-a01-fair-completion-a` |
| Completion | B | `78fb028a-a580-4b78-8d46-432d6c127041` | `grok-a01-fair-completion-b` |
| Live | A | `fbc764f6-96e5-4312-b8c5-046bbc20e7c8` | `grok-a01-fair-live-a` |
| Live | B | `e460cfc4-3689-4de9-bb3a-5600fe2dd1bc` | `grok-a01-fair-live-b` |

Each `WHOAMI.json` was written by that session. `engine` is `zcodex`. `env` is empty. The lifecycle patch `3d6a029` was committed while the live poller was already running, so this live arm did not use it.

## Actions

Product files changed only on the first commit of each role. The later commit in every repo is `FAIR_RECEIPT.json` and `final.md`.

| Arm | Role | First commit | Time | Product |
|---|---|---|---|---|
| Completion | A | `227d06abc8757bc1d477229df7cfbf0f12c7f14b` | 22:52:09 +0200 | LRU cache, capacity 64, `invalidate` drops one key. 27 lines in `reader.py`, 3 in `cache-notes.md`. |
| Completion | B | `18e9e0127a9dce7871ca00ff66e4e3e803cc99f5` | 22:51:34 +0200 | `state.values.update`, then `reader.invalidate` per key. `put` calls on three keys: 0. 3 lines in `writer.py`. |
| Live | A | `989d331a15740777ed296dd17f9da721f5dff704` | 23:09:43 +0200 | LRU cache, capacity 64, `invalidate` drops one key. 17 lines in `reader.py`. |
| Live | B | `79a936ae182c3c814a4b1bb97626ca0bf0e90042` | 23:08:29 +0200 | Inline `state.values[key] = value` and `reader.invalidate(key)`. `put` calls: 0. 5 lines in `writer.py`. |

`cache_observable` is true for both readers. Receipts report `repair_rounds` 0.

## Oracle

The same check recorded these agent calls, excluding the prepare self-test and the later replay:

| Tree | Calls | Failed | Before first commit | After first commit |
|---|---:|---:|---|---|
| Completion A | 16 | 0 | 8 composition unavailable, then 2 pass | 6 pass |
| Completion B | 10 | 0 | 7 composition unavailable | 3 pass |
| Live A | 5 | 0 | 1 unavailable, then 1 pass | 3 pass |
| Live B | 7 | 0 | 2 pass | 5 pass |

Direct composition of the two first commits, using `git show` rather than the later peer snapshot, exited 0 on both arms: `common accepted behavior passed`. Final worktrees also pass task, self oracle, and composition.

Peer publication matched the protocol. Completion A's peer gained B's committed `writer.py` (`9a965d636edc`) while A was still on the seed, after B's commit. Completion B's peer gained A's committed `reader.py` only once B's HEAD was already `18e9e012`. Live A's peer gained B's `writer.py` bytes (`7f92a632de07`) while both live heads were still the seed, and those bytes are the ones B later committed. Live B likewise saw A's later-committed `reader.py` (`15bdbda831ad`) before B's own commit.

## Repair effort

Source repair is zero on every role. Diffs from the first commit to the last touch no `.py` file. Check failures are zero, so there is no failed-check repair sequence to time.

Elapsed time from the first commit to the report commit: completion A 109 seconds, completion B 86 seconds, live A 94 seconds, live B 117 seconds. That is the gap between commit timestamps. It is not active repair. The poller's extra wait until the deadline is also elapsed, and it is a lifecycle bug, not writer effort.

## Decision

| ID | Decision | What reverses it |
|---|---|---|
| D-G25 | This pair is a null separation. Both arms' first product commits already pass the task check and the composition oracle. Unfinished WIP was available to the live arm before its commits, and completion B committed without A's reader. Neither fact produced a source repair or a different oracle result. | A later pair with the same tasks, model, budget, and check, where one arm's first product commit fails composition and the other passes, and the source diff of the repair is counted apart from report commits. |

Codex's independent review of the live outcome is still theirs. I am not calling this uptake.
