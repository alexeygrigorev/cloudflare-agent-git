---
name: prepare-daily-journal
description: Prepare and verify this project's daily public journal on remote Codex, coordinating genuine Claude Opus prose, approved visuals, independent reviews and publication. Reuse a verified existing daily article without duplicate writing or republication.
---

Remote Codex owns evidence collection, preparation, visual acquisition and acceptance, review coordination, publication checks, metadata, deployment verification and recovery. The publication coordinator remains accountable for independent acceptance and release; reviewers remain distinct actual agents. Desktop issues commands and observes, bridging a missing authenticated browser or ImageGen capability only. Neither desktop nor either principal is a routine prep executor or QA approval dependency. Claude Opus writes the prose; preserve Claude principal's protected draft.

Read the latest entries of `_docs/founder-journal/journal.md`, the recent GitHub issues and the agents bus history FIRST, then AGENTS.md and `_docs/way-of-working.md`. The writing, visual, design-review, publishing and signup rules live in the writer skill, `.claude/skills/daily-writeup/SKILL.md`; read it in full and don't copy its rules here. Paths are repository-relative.

## Dispatch and admission

The existing daily automation, run from `/home/alexey/git/cloudflare-agent-git`, picks the Berlin edition date and issues exactly one command:

```bash
python3 .agents/skills/prepare-daily-journal/scripts/dispatch.py 2026-10-06 prepare
```

`DATE validate` is the read-only forward check. `DATE prepare --check` runs admission only and never launches a model.

What `scripts/dispatch.py` enforces:

- Admission: at least 10 GiB MemAvailable, at least 50 GB free on the task mount, the private task directory under 512 MiB, and a fresh `scripts/quota-gate.py` pass (Codex launches only above 15% remaining in every window).
- Launch: one native aplexer session tagged `daily-journal-codex-DATE-MODE`, `--memory 1500M`, `--pids 256`, verified by the worker through `a whoami` (tag, workspace and memory cap). It requests no model override.
- Run: Codex starts through `scripts/launch-codex.sh`, which runs the quota gate again, with `TMPDIR` set to the private `tmp/` folder. The worker stops the run after 60 minutes or once the private folder reaches 500 MiB, and writes `receipt.json` with the reason.

Exact dedup key is `daily-journal:YYYY-MM-DD:prepare` (or `validate`). Private logs live in `.local/journal/remote-preparation/DATE/MODE/`: `launch.json`, `identity.json`, `prompt.txt`, `events.jsonl`, `stderr.log`, `final.md`, `progress.md`, `receipt.md` and `receipt.json`. An existing launch or receipt means inspect and reuse; never delete the fence or use `--fresh`. A failed launch without a launch receipt is still checked against the exact native tag. No restart, busy injection or protected composer submission. Recovery needs the publication head's review of the actual terminal result and one explicitly owned replacement task token, keeping the original output. No automatic retry loop and no new cron, service or scheduler.

Keep total incremental storage across related task outputs within 512 MiB, not only this log folder; reviewers may reuse existing previews and assets. No /tmp files, dependency copies, Rust builds or global installs. Observed usage comes from the actual child response, never from quota readings. The head verifies real `whoami`, first-action ACK, incremental output within the recorded checkpoint and final semantic acceptance; captured events alone don't imply success. Unknown or exhausted quota, or a runtime failure, holds Codex prep with a truthful failure, and a different provider can't be called Codex. During a genuine dependency wait, keep partial output and the next owned action without idle polling.

Automation prompt (desktop installs it once; remote creates no other automation):

> Dispatch remote Codex with prepare-daily-journal/scripts/dispatch.py for the Berlin edition date; observe its private incremental progress and genuine completion. Remote Codex owns preparation/visual acceptance/reviews/publication checks/deployment recovery with public-journal-site; dedicated genuine Claude Opus writes prose. Reuse existing good daily content/assets. Desktop bridges only a specifically requested unavailable ImageGen/browser capability. No desktop QA approval or principal implementation dependency.

## Steps

1. Verify `a whoami --json` in the real tool process, `a context` and inbox. Send first-action ACK to desktop-orchestrator and public-journal-site, cc codex-principal. Obtain explicit publication ownership ACK before peer-owned writes. Register actual task, team/head/parent/native identity, owned files, first action, checkpoints and usage source through the head; never infer agreement from delivery or silence.
2. Deduplicate exact `daily-journal:DATE:MODE` and native message IDs. If the date already has a good published article, successful actual Opus response and verified dated assets, validate read-only and keep them. A rewrite replaces the same page and keeps its original publication time; no duplicate writer, no needless regeneration of approved art. A quiet day still gets a short report, as the writer skill says; never invent progress.
3. Pin the exact preceding 24 elapsed hours ending at 09:00 Europe/Berlin in UTC and Berlin, using zoneinfo (DST days are not assumed to be 24 local clock hours). Use half-open hourly buckets. Cover FOUR separately owned products: Agent Branches, Agent Dashboard, Agent Quota Launcher and Cross-computer Agent Coordination. Distinguish source cutoff, interval end, later corrections, report production and accepted_at times. Collect direct artifacts/tests/independent acceptance, hourly utilization, measured usage/coverage/unknown gaps, accepted features, unfinished blockers, launcher rules, the task tracker counts from GitHub issues, continuation runtime checklist progress and open founder requests. Preserve qualification when a report is disputed; presence/PIDs/quota percentages are not productive work, tokens or money. Native two-computer delivery, offline recovery and autonomy need their own evidence. Write it as the private fact packet `.local/journal/opus-writer/DATE-FACT-PACKET.md`.
4. Check fresh quotas before every actual model launch and route through existing gates. Run `python3 website/write_daily.py --date DATE --fact-packet PATH`: it refuses to launch when Claude quota is unknown or exhausted, starts one dedicated Opus writer and then a fresh Opus check pass, and fails unless both responses show Opus in `modelUsage` and `check.json` exists. Inspect the actual responses and exit status. Failed capacity keeps partial output and the last good publication; never substitute another provider and call it Codex or Opus.
5. Verify this run's callable image capability; a prior session's tool list is not proof. Reuse approved dated ImageGen art and hashes. Otherwise use an existing authorized verified ImageGen callable with the writer skill's art direction, date, destination and acceptance; if unavailable send ONE precise durable [asset request](#missing-imagegen-capability). Desktop is only the capability bridge; remote owns inspection, hashes, acceptance and integration. Read installed `/home/alexey/git/.agents/skills/diagram-creator/SKILL.md` and its canonical source before using its actual installed renderer. Keep editable dated JSON/SVG and render the publication PNG; inspect the actual PNG, labels, arrows and crop. No substitute stock art, invented tool call, global install, credentials or purchase.
6. Arrange independent factual, editorial and actual rendered desktop/mobile reviews against pinned artifacts. Record real reviewer identity/ACK, candidate/reference/screenshot hashes and PASS/FAIL/UNKNOWN separately. A coordinator's own visual inspection is not independent review; a build/source check is not rendered acceptance. The writer skill's site design section governs design blockers and factual-update exceptions. Preserve existing blocked reference-fidelity tasks.
7. Publish and recover as described below.
8. Write private incremental progress and final receipt with capabilities, pins, checks, limitations, next owner/action/trigger and failure recovery. Send genuine completion to desktop-orchestrator/public-journal-site/codex-principal; leave edit declarations. Existing daily automation dispatches the next date; add no competing scheduler, service or idle work.

## Missing ImageGen capability

A tool listing is not an ImageGen execution; never claim one from it. If the current remote session has no authorized callable ImageGen, write a single private request `.local/journal/remote-preparation/DATE/prepare/asset-request.md`, send its exact path and token to desktop-orchestrator, and keep the reply and digest. Include all of:

- Edition date, source cutoff, a conceptual narrative grounded in that day's evidence, one landscape 3:2 image and output `website/assets/DATE.png` (or the kept sibling if already approved).
- Reference `website/assets/agent-git-illustration.png` with its actual SHA256, and the art direction from the writer skill's visuals section. Replace the narrative with current evidence; don't depict unsupported adoption, completed autonomy or savings.
- Acceptance: returned original bytes, native tool provenance and time, dimensions and SHA256; actual remote visual inspection of style, narrative, crop and misleading claims; an independent reviewer and privacy check; accessible conceptual caption and alt text. Keep the original approved reference and dated art; no needless regeneration.
- Desktop only invokes its authorized ImageGen and transfers the result. Remote Codex accepts and integrates it and owns the rest of the preparation. No broad credentials, paid alternative, global install or silent stock-art fallback. A missing artifact holds the visual step only; record the dependency and continue independent prep.

## Publishing and recovery

For a NEW accepted release, run `python3 website/publish_daily.py DATE --response PRIVATE_RESPONSE --reviewer "REAL REVIEWER" --publish`. The script checks the Opus response, metadata, images, privacy patterns, stylint and share text, keeps an existing `published_at` and records `updated_at` (plus `revised_at` on a rewrite). Without `--reviewer` it records the publication coordinator as the reviewer, so always pass the actual reviewer identity. Don't repair provenance afterwards or bypass its validation.

Stage explicit owned paths and commit under `flock .local/git.lock`, keeping the shared index and dirty files. Push the authorized source checkpoint, then verify CI and deployment success, live HTTP 200, the build-commit SHA and byte-exact image and diagram hashes, and have lane reviewers check the deployed desktop and mobile pages. Pin the prior good release first; a source push alone isn't deployment success. Recovery is a scoped revert or redeploy of accepted website artifacts that keeps peer work and private archives, never a shared reset. An already good published DATE is a read-only run, never an automatic republish. No social posting.

General limits (spend cap, memory and disk floors, no Rust builds or installs, no purchases, no cloud agent execution, no secret or private-voice publication) are in `_docs/way-of-working.md`; the dispatcher bounds above are this task's own.
