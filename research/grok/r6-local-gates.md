# Grok round-6 local gates

2026-10-02, Europe/Berlin. Author: grok-head, aplexer session `39e95f91-19ee-48fc-8a83-c25e199813b6`. This is the interactive resume of conversation `01a0fe00-6ecd-7c73-a852-e9862578d192`. The previous shell session was `3b664830-1a4f-4f30-ba94-67828f32021c`. `coordination/grok.stop` only stops the headless loop. It is not project completion.

No sign-off. Shortlist draft 3 is SHA-256 `4133312b5d48ee7721cc65a0225a49a7c81156ab4d4be662e2d261563ff5a52d`. Same six IDs. I did not edit it. Root had about 61 GiB free and `/tmp` about 48 GiB. Scratch for the storage run peaked at 470,904,832 bytes and was deleted. That is under the 512 MiB cap.

## R6-1. A14's local tie reproduces

I ran `python3 -B research/codex/runtime-isolation-fixture.py`. Source SHA-256 `6a1c96df7a9c09d0987b2a6edf6ee15abec2b9dc048837a21b37608cf12350b9`. Shared SQLite: task A later reads `value-B`. Fresh checks, explicit per-task databases, and the ordinary separate-resource control all read their own values. Cleanup removed the scratch. This matches `research/codex/runtime-isolation-validation.md`.

I accept the local conclusion: separate files work, and the ordinary control uses the same mechanism as the proposed arm. That is not a Workers Previews run and not a reason to delete A14 from the unapproved six by myself. Folding the slot into A01 verification is Codex draft 3's proposal. I agree the local evidence supports that proposal. It is not a principal signature.

## R6-2. A local partial clone withholds an unread blob, then loses the saving when the blob is checked out

`research/grok/r6_partial_clone_fixture.py`. Git 2.43.0. One 33,554,432-byte incompressible blob plus `src/app.py`. Allocation is unique regular-file `st_blocks * 512`. `--no-local` so Git does not hardlink the origin object store. Origin has `uploadpack.allowFilter=true`. This is local Git, not ArtifactFS, not Artifacts v2, and not pnpm.

| Arm | Allocated bytes | Blob file present |
|---|---:|---|
| Full clone, no checkout | 33,681,408 | no |
| Full clone, checkout | 67,244,032 | yes |
| `blob:none`, no checkout | 122,880 | no |
| `blob:none` plus sparse `src/` | 151,552 | no |
| Same partial clone after `assets/blob.bin` checkout | 67,280,896 | yes |
| Two linked worktrees, union | 100,835,328 | yes in both |
| Two full clones, union | 134,492,160 | yes in both |

The partial clone is not shallow. Its filter is `blob:none`. Sparse checkout of `src/` keeps the blob out of the worktree and out of the measured objects. Checking the blob out brings the tree back to the full-checkout size. Two linked worktrees are 33,656,832 bytes below two full clones, which is 25.0% of the two-clone total. That saving is one shared object database. Both worktrees still hold a copy of the blob. It is not a 40% result and not a 90% result. The pnpm union result is a different baseline and was not rerun.

Tradeoff: partial clone plus sparse checkout is an incumbent for "do not fetch an unread blob." The cost appears on first read. A remote mount that hydrates the same blob on read has the same shape unless it never stores the blob locally. I did not install ArtifactFS.

Kill test for an A16 byte claim on source blobs: same blob, three arms, partial-sparse before read, partial-sparse after the task reads the blob, and two linked worktrees. A claim passes only if the arm the task actually reads still beats the linked-worktree union by a margin declared before the run. The unread 151,552-byte arm does not count as the task's cost. Reverse only with that table. The 40% pnpm-plus-sparse margin remains Claude's declared package margin, still unmeasured here.

## R6-3. A script can follow an unfinished diff and miss a warning that arrives after it commits

`research/grok/r6_wip_script_fixture.py`. A and B edit different files. The oracle is outside the repo: cache a read, bulk-update, read again.

| Arm | Warning source | Merge | Oracle |
|---|---|---:|---:|
| Late | completed commit subject `a adds cache` | 0 | 1 |
| Early | uncommitted `cache.py` diff contains the cache clear | 0 | 0 |

The early script is written to obey that diff. A model is not in the loop. The late script has already committed the bypass when the completed commit appears, and the clean merge fails the oracle. This separates the two protocol arms. It does not pass the uptake gate in `research/zcode/independent/a01-uptake-protocol.md`.

The live gate that remains: one genuinely bound z.ai session, not a new Codex process, on a fresh `/tmp` fixture, with `wip_basis=uncommitted_diff`. Record `emit`, `consume`, and `agent_action` from that protocol. Compare with the same model and no live notice. N=1 is a smoke test. The 3-agent / 10-push sample is still the kill test. I did not launch that session. There is no lane, and a second writer on this checkout is the failure I am avoiding.

## Decisions

| ID | Decision | Outcome | What reverses it |
|---|---|---|---|
| D-G16 | Treat local `blob:none` plus sparse checkout as the unread-blob incumbent. Do not count its small size after the task reads the blob. | Fixture deleted its scratch. | A read arm beats linked worktrees by a predeclared margin. |
| D-G17 | Accept the rerun A14 tie. Do not edit the six. | Same shared-read failure and same ordinary-control pass. | A live preview workflow beats Workers Previews on attestation or repair, not on separate files. |
| D-G18 | Keep scripted WIP results out of the uptake numerator. | Arms differ. No model. | One bound z.ai run records a vector-current action that the no-notice arm does not. |

## Requests

Reply accept, modify, or reject on R6-1, R6-2, and R6-3. No sign-off is requested.
