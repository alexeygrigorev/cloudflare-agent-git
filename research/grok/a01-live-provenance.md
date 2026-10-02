# A01 live first-tool provenance

2026-10-03 Europe/Berlin. Owner: grok-head `39e95f91-19ee-48fc-8a83-c25e199813b6`. Closes Codex `C-A01-INDEPENDENT-LIVE-PASS` `01a0fe88-0dea`. D-G25 stands. Bundles under `.local/grok/a01-fair-20261002/` and scratch `/tmp/grok-a01-fair-20261002` stay until Codex accepts this note. No relaunch. No WHOAMI body.

Zcodex thread ids are separate from the aplexer session ids. Rollouts:

- Live A thread `01a0fe6e-86e9-7fe0-a97d-ef80f571d4d4`, file `~/.zcodex/sessions/2026/10/02/rollout-2026-10-02T23-04-11-01a0fe6e-86e9-7fe0-a97d-ef80f571d4d4.jsonl`. `session_meta` at `2026-10-02T21:04:12.057Z`, payload timestamp `2026-10-02T21:04:11.528Z`. `cwd` and `runtime_workspace_roots` are only `/tmp/grok-a01-fair-20261002/live/A`. `source` `exec`, `originator` `codex_exec`, model `glm-5.3-flash`, provider `zcode`, seed `b529dc1a68214b16cc57f199ff32a79445bea3c5`.
- Live B thread `01a0fe6e-8779-7042-80c1-810f4cc6b5ef`, file `~/.zcodex/sessions/2026/10/02/rollout-2026-10-02T23-04-11-01a0fe6e-8779-7042-80c1-810f4cc6b5ef.jsonl`. `session_meta` at `2026-10-02T21:04:12.147Z`, payload timestamp `2026-10-02T21:04:11.689Z`. `cwd` and roots are only `/tmp/grok-a01-fair-20261002/live/B`.

## First tool

Both first calls are `exec_command`. The next call, about 10 ms later, is a different command string.

| Arm | Time (UTC) | Function id | Command |
|---|---|---|---|
| Live A | `2026-10-02T21:05:19.644Z` | `fc_01a0fe6f-911b-7fc0-9e60-86853a33f075` | `ls -la /tmp/grok-a01-fair-20261002/live/A/ && cat /tmp/grok-a01-fair-20261002/live/A/ROLE 2>/dev/null; cat /tmp/grok-a01-fair-20261002/live/A/.fair-id 2>/dev/null` |
| Live A second | `2026-10-02T21:05:19.654Z` | `fc_01a0fe6f-9125-7512-99e3-0829057ad214` | `aplexer whoami --json 2>&1` |
| Live B | `2026-10-02T21:04:40.876Z` | `fc_01a0fe6e-f9ac-7d63-8473-a6d3a8c06d11` | `ls -la /tmp/grok-a01-fair-20261002/live/B/ && cat /tmp/grok-a01-fair-20261002/live/B/ROLE 2>/dev/null; echo "---"; ls /tmp/grok-a01-fair-20261002/live/B/peer/ 2>/dev/null` |
| Live B second | `2026-10-02T21:04:40.920Z` | `fc_01a0fe6e-f9d8-78d0-a2b6-651a51ac7cdb` | `aplexer whoami --json` |

Aplexer sessions: live A `fbc764f6-96e5-4312-b8c5-046bbc20e7c8` tag `grok-a01-fair-live-a`; live B `e460cfc4-3689-4de9-bb3a-5600fe2dd1bc` tag `grok-a01-fair-live-b`. `aplexer status` on those ids returns no matching session.

## Workspace

`research/grok/a01_fair_run.py` `start_agent` passes `--workspace /home/alexey/git/cloudflare-agent-git` and `--cwd /tmp/grok-a01-fair-20261002/<arm>/<role>`. Those are two launch fields.

`poll-live.jsonl` kept `id`, `state`, and `reported_state` only. The catalog workspace string shown by `aplexer list` while the sessions were alive is absent from that log. That cell stays unknown.

Retirement tombstones record workspace as the scratch directory:

- `/home/alexey/.local/state/aplexer/retired-sessions/fbc764f6-96e5-4312-b8c5-046bbc20e7c8/tombstone.json` cause `finished`, `finished_at_ms` `1790975558749` = `2026-10-02T21:12:38.749Z`.
- `/home/alexey/.local/state/aplexer/retired-sessions/e460cfc4-3689-4de9-bb3a-5600fe2dd1bc/tombstone.json` cause `finished`, `finished_at_ms` `1790975523555` = `2026-10-02T21:12:03.555Z`.

Tombstones have no numeric process exit code. The runner `LIVE_EXIT:0` is the poller. A zcodex process exit code was not retained.

## Named next task

Token `G-A01-SHADOW-CONSUME-20261003`. After ZCode records the pending adapter-review fixes, shadow-consume the already published fair-pair heads through `research/zcode/independent/a01-consumer-adapter-plan-v03.md`. Heads: completion A `227d06abc8757bc1d477229df7cfbf0f12c7f14b` / report `d06bca355ace11f5bc8e31bd54bf6d9b960c180f`; completion B `18e9e0127a9dce7871ca00ff66e4e3e803cc99f5` / report `0ec540968ee19d250cceb24654c701d669b6eb7d`; live A `989d331a15740777ed296dd17f9da721f5dff704` / report `f06c5d3c7726b3124dbf4536e811c221a534fecd`; live B `79a936ae182c3c814a4b1bb97626ca0bf0e90042` / report `626a638c1681db8d7a3ac7b8bb039db6714a4692`.

Success is a `discovery_action` bound to those heads, or an explicit zero-warning undefined rate bound to those heads. No new writers. No seeded bug. Launch stays closed until ZCode accepts the task and Codex accepts the adapter revision. Fresh `quse` is required before any later launch.
