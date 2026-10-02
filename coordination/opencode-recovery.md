# OpenCode runtime recovery — diagnosis and relaunch record

Owner: aplexer session tag `opencode-runtime-recovery` (zcodex/ZAI), session dfb10ee4-5b7e-4828-8a3d-3f09cd81f0ec, started 2026-10-02 ~20:58 Europe/Berlin under a 60-minute bounded mandate. This file and `.local/opencode-recovery/` + `scripts/opencode-recovery-peer.sh` are the only paths I write.

## Diagnosis: local init was never the blocker

Root cause of the zero-byte round-1 stalls: `scripts/peer-loop.sh` launched `opencode run --model opencode/<model>-free`, and the plain `opencode` provider has **no auth entry** in this environment. `~/.local/share/opencode/auth.json` (236 B, mirrored to the isolated copy) contains only `opencode-go` and `zai-coding-plan`. The CLI boots fine and then waits on an unauthenticated provider route; with `--print-logs` the log simply ends at `message=init`, which looked like an "init stall". Provider keys: `172.65.90.x:443` (Cloudflare front) connects were attempted in probes; the earlier 25–35 s probes were also too short to see post-init phases (my probes show init→watcher in ~1 s).

Evidence (all bounded probes logged in `.local/opencode-recovery/probe-*`, exit codes in the run notes below):

| # | Probe | Binary | cwd | Model | Timeout | Result |
|---|-------|--------|-----|-------|---------|--------|
| 1 | baseline scratch | baseline | scratch | `opencode/muse-spark-1.3-contributor-free` | 60s | exit 124, hung at provider wait after `project copy refresh started` |
| 2 | strace probe | baseline | scratch | `opencode/muse-spark-1.3-contributor-free` | 40s | exit 124; ~24 git children (snapshot machinery), one transient `fatal: Unable to create ...index.lock` from concurrent git race (no stale lock before or after), connects to 443 |
| 3 | go muse scratch | baseline | scratch | `opencode-go/muse-spark-1.3-contributor` | 150s | **exit 0, "OK" in ~2.2s** |
| 4 | go muse repo root | baseline | repo | same as 3 | 120s | **exit 0, "REPO-OK" in ~4s** |
| 5 | global binary + go muse | installed global ELF | repo | same as 3 | 60s | **exit 0, "GLOBAL-GO-OK"** — binary was NOT the blocker |
| 6 | go space-bunny | baseline | repo | `opencode-go/space-bunny-free` | 60s | **exit 0, "BUNNY-OK"** |

Negative/other findings preserved:
- CPU has AVX2; baseline-vs-JSC binary choice was irrelevant to the stall.
- `strace` saw the zombie-git hypothesis as normal snapshot-machinery git spawns plus a transient index.lock race between opencode's own concurrent git children; no stale lock persisted.
- Cold-start "project copy refresh" into a fresh isolated DB took >59 s once (probe 1) and 0.15 s warm (probe 3) — first boot after cache wipe is slower; keep generous first-run timeouts.
- `quse go` before Go dispatch: 5h 100%, weekly 100%, monthly 99%, limit_reached=false (2026-10-02 ~21:05–21:15 Berlin). Free `opencode/*` provider status remains unknown/unauthenticated.

## Routing change (documented, no family/version substitution)

- Requested `opencode/muse-spark-1.3-contributor-free` → dispatched as **`opencode-go/muse-spark-1.3-contributor`** (same model family/version, authenticated provider; the `-free` suffix does not exist under `opencode-go` for this model).
- Requested `opencode/space-bunny-free` → dispatched as **`opencode-go/space-bunny-free`** (same id, authenticated provider).
- Workaround is experiment-local: isolated `XDG_DATA_HOME=.local/opencode-isolated` + `XDG_CONFIG_HOME=.local/opencode-config` + `--pure`; global installation, DB, auth, and unrelated processes untouched.

## Relaunch

`scripts/opencode-recovery-peer.sh` (owned; peer-loop.sh untouched): bounded loop, max 3 attempts, 100-min round timeout, backoff 120s×attempt, stops on `coordination/<role>.stop`, streams via tee to `.local/muse/recovered-round-*.log` / `.local/space-bunny/recovered-round-*.log`.

At 21:21 Berlin the tags `muse-reviewer` (session c0838d96) and `space-bunny-head` (session 7564a895) came up running exactly this launcher with models `opencode-go/muse-spark-1.3-contributor` and `opencode-go/space-bunny-free`; my own `aplexer start` calls seconds later found them already running ("already belongs to session"), so the launcher was adopted by the concurrent orchestrator check (21:20 heartbeat window) from my on-disk script/prompts. No duplicate launch attempted. Both verified running with genuine bound identities, memory cap 1536M, real tool activity on their owned targets (muse: reading `test-idempotency*.sh` repair files; bunny: reading policy/runtime notes).

Peer mandates (prompts in `.local/opencode-recovery/prompts/`): both read policy + five Pro outputs (`research/orchestrator/pro-angle-1..5.md`); Muse performs real code review of aplexer repair 9730367 incl. folded-in corrections (repo `/home/alexey/git/cloudflare-aplexer-protocol`, tip b69787f; store.rs atomicity, key scoping, payload conflict, reply dedup, tests) → `research/muse/repair-9730367-review.md` + `coordination/muse.md`; Space Bunny produces `research/space-bunny/shortlist-feasibility-round1.md` + `coordination/space-bunny.md`; each commits owned paths under `.local/git.lock` and sends a native reply to `desktop-orchestrator` from its own identity.

Recovery claim status: route recovery **verified by probes 3–6**; peer productivity claim deferred until each peer saves an incremental deliverable and its native reply lands (peers budgeted ~75 min from 21:21; verification continues in `.local/opencode-recovery/`).

## Provenance correction and migration state (21:35 Europe/Berlin update)

Corrected per desktop-orchestrator RECOVERY-PROVENANCE-CORRECTION1920: the desktop orchestrator did NOT launch my peer script; I verified receipts instead of attributing. Verified state:

- **Muse**: headless round 1 (opencode session `ses_f01efa751ffeCumog1qyjzvQt2`) completed cleanly ~21:23:30, committed `ce10ff6` (repair review approve-with-corrections + Pro/shortlist challenge; files `research/muse/repair-9730367-review.md`, `research/muse/pro-shortlist-challenge.md`, `coordination/muse.md`), sent its native reply to desktop-orchestrator. Its conversation was then resumed INTERACTIVELY as aplexer session `07d34106` with TUI verified by the orchestrator — do not duplicate or relaunch. Spot-check of its review held up (the `DEBUG: body=` eprintln exists at `message_routing.rs:161` in the repair repo). Routed to muse-reviewer by native message: the orchestrator's additional review items (quota-error handling, structured `data` in payload compare — already independently found by Muse, manual identity-spoof tests, tag-reuse/GC boundary) and the no-integration-approval constraint.
- **Space Bunny**: headless round 1 (opencode session `ses_f01ef9c54ffe86f5DrG7n8GCsY`) still running productively; incremental deliverable `research/space-bunny/shortlist-feasibility-round1.md` (32.8KB) already saved by 21:31. Checkpoint requested via native inbox message for interactive resume of the exact session with: isolated XDG env + baseline executable + `--pure --auto --session ses_f01ef9c54ffe86f5DrG7n8GCsY --model opencode-go/space-bunny-free` (no `run`, no `--format json`).
- **No further headless rounds**: `coordination/space-bunny-head.stop` (created 21:29 by orchestrator/root, committed in 77491f0) gates my wrapper at the next attempt boundary without touching the active turn; my wrapper by design runs only one round on success. My own future launches obey the interactive-head policy; this helper's mandate ends after this update, reply, and commit.

Launch command actually used for the record (headless round 1 only, now superseded by interactive policy): `aplexer start --tag <role> --memory 1536M -- bash scripts/opencode-recovery-peer.sh <role>` — my two `start` calls at ~21:27 returned "already belongs to session", i.e. both tags were live before my calls; the adopting party was not the desktop orchestrator (per its correction) and I have no receipt naming it, so provenance is left as "another local actor adopted the prepared launcher"; exact session ids above are the authoritative record.

## Helper close-out (21:45 Europe/Berlin)

- Provenance-correction section above confirmed present in the committed file (verified via `git show HEAD:` at 21:40); no follow-up commit was needed for it.
- `space-bunny-head` (session 7564a895) ended its headless turn cleanly per the 21:2x CHECKPOINT REQUEST: after commit 9214e86 it added self-corrections 9c6480c + 8e75d71 (including its own disclosure of three misattributed peer paths in 9c6480c — my `coordination/opencode-recovery.md` was not touched by it), journaled its round-1 major-decision entry, and sent native ROUND-1-DELIVERED + CORRECTION messages to desktop-orchestrator. aplexer records are now gone with no unacknowledged warnings — clean exit, not a crash. Interactive resume stays with the orchestrator per USER14; this helper did not relaunch it.
- `muse-reviewer` (interactive 07d34106) still running, worker alive and reachable at close-out.
- Negative finding: my final RECOVERY-VERIFIED message to desktop-orchestrator was sent twice (msg ids 01a0fe1e-33f1… and 01a0fe1e-356b…, byte-identical) — double-send, content identical, no correction needed.
- `experiment/events.jsonl` carries one still-uncommitted journal line from space-bunny-head (2026-10-02T19:34:24Z, round-1 major decision). Not my owned path; left in the working tree for its owner/the orchestrator to commit.
- Mandate complete; this helper ends. No further headless launches; wrapper stays gated by `coordination/space-bunny-head.stop`.

## Helper close-out (21:45 Europe/Berlin)

- Provenance-correction section above confirmed present in the committed file (verified via `git show HEAD:` at 21:40); no follow-up commit was needed for it.
- `space-bunny-head` (session 7564a895) ended its headless turn cleanly per the 21:2x CHECKPOINT REQUEST: after commit 9214e86 it added self-corrections 9c6480c + 8e75d71 (including its own disclosure of three misattributed peer paths in 9c6480c — my `coordination/opencode-recovery.md` was not touched by it), journaled its round-1 major-decision entry, and sent native ROUND-1-DELIVERED + CORRECTION messages to desktop-orchestrator. aplexer records are now gone with no unacknowledged warnings — clean exit, not a crash. Interactive resume stays with the orchestrator per USER14; this helper did not relaunch it.
- `muse-reviewer` (interactive 07d34106) still running, worker alive and reachable at close-out.
- Negative finding: my final RECOVERY-VERIFIED message to desktop-orchestrator was sent twice (msg ids 01a0fe1e-33f1… and 01a0fe1e-356b…, byte-identical) — double-send, content identical, no correction needed.
- `experiment/events.jsonl` carries one still-uncommitted journal line from space-bunny-head (2026-10-02T19:34:24Z, round-1 major decision). Not my owned path; left in the working tree for its owner/the orchestrator to commit.
- Mandate complete; this helper ends. No further headless launches; wrapper stays gated by `coordination/space-bunny-head.stop`.
