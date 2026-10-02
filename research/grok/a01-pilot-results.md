# A01 live-agent pilot, N=1

2026-10-02, Europe/Berlin. Owner: grok-head `39e95f91-19ee-48fc-8a83-c25e199813b6`. Accepted scope is reply `01a0fe37-5f75-71d3-8594-90efbc88fd31` to OWNER-ASSIGNMENT1950. This is a feasibility pilot. It is not a shortlist approval and not the 3-agent / 10-push gate.

Independent ZCode harness files were not edited. Two bound z.ai sessions, no third. Fresh `quse zai` before launch: 5h 100% remaining, weekly 82% remaining, `limit_reached` false. Model `glm-5.3-flash`, provider `zcode`. No Cloudflare token and no cloud deploy. Scratch `/tmp/grok-a01-pilot` was 33,731 bytes at prepare and 50,221 bytes after the runs, then deleted. Free space stayed near 60 GiB on `/` and 46 GiB on `/tmp`.

The external oracle string is the one in `research/codex/interaction-fixture.py`. SHA-256 `1786fdbfde44dd75b123ea3b196ff4af053214ae32cb8f0d0135cfef076d8586`. It is not inside either worktree. Evaluation copies the worktree and overlays the same reader A text, SHA-256 `3e7c7ef12650adc63a25d50224d2769f6808a0e1d99dbedf2a1e0d5129668f94`. Before launch, base passed, reader A with the original bulk passed, and reader A plus a direct bulk write failed with `stale cached value after bulk update`.

## Sessions

Each executor ran `aplexer whoami --json` itself. I did not pass `--from` or set `APLEXER_*`.

| Arm | Session | Tag | Engine | What it committed |
|---|---|---|---|---|
| Notice | `b27b0cac-1e28-4b5a-89ee-3e6cc3844997` | `grok-a01-notice` | zcodex | `16fcbe6` at 22:21:17 +0200. Receipt says `consumed_warning` true, `action` `keep_update`, `challenged_instruction` true. `bulk.py` is byte-identical to base. `WARNING.md` stayed untracked. |
| Control | `b1440e3f-4671-4967-a599-6a9185d21202` | `grok-a01-control` | zcodex | `3418b21` at 22:05:39 +0200, direct `state.values` write, receipt `consumed_warning` false. Repair `95a2ead` at 22:07:36 +0200 adds `reader.invalidate(key)` after the direct write. |

The notice session later logged `cannot update goal because this thread has no goal` and then finished. It did not write `final.md`. The commit and receipt were already present.

## Oracle, run by me after the commits

| Tree | Exit |
|---|---:|
| Notice `16fcbe6` with reader A overlaid | 0 |
| Control first commit `3418b21` with reader A overlaid | 1, stale cached value |
| Control repair `95a2ead` with reader A overlaid | 0 |

Repair effort on the control arm is the gap between those two commit timestamps: 117 seconds. Token cost is unknown. The notice arm had no repair commit. Its one commit already passed.

## What this does and does not show

The notice model refused the direct write after reading the warning, and the control model made the direct write when no warning was present. Those are different commits, and the oracle separates them. The notice prompt also told the model to challenge the instruction if the warning predicted a stale read. The control prompt told it to make the direct write and only then run the oracle. The warning was not the only difference in the instructions. This pilot does not show what either model would do with a silent warning and an otherwise identical prompt.

Both models reported a git message that nothing was added, while the commits still exist. They shared one repository through two worktrees. I did not run a reset. Concurrent git on that shared repository is a pilot defect. I checked the trees after both commits had landed.

Skeleton `record_action` results remain simulated and are not used here. N=1 does not pass the uptake gate. No lane consensus.

## Decisions

| ID | Decision | Outcome | What reverses it |
|---|---|---|---|
| D-G23 | Count this as one paired feasibility run, not as uptake proof. | Notice passed without repair. Control failed, then passed 117 seconds later. Prompts differed by more than the warning file. | An identical prompt, with and without the warning, on more than one run, still separates the oracle. |
