# Incidents, 2-7 October 2026 (historical)

Historical only. Not part of agent context. Do not read this file unless you are investigating project history.

This is a record of operational incidents from the first week of the project: outages, recoveries, out-of-memory kills, stuck agents, duplicate executions, lost handoffs and similar failures. It was written after the fact from the project's own notes. It does not set any rule. Where current rules came out of an incident, the rules live on `main`, not here.

Each entry gives the date, what happened, the root cause, what was changed, and the source files. Every source path refers to tag `pre-cleanup-20261007` (commit `7a0b82c`). Read a source with:

```
git show pre-cleanup-20261007:<path>
```

Facts were checked against the sources. Anything the sources do not state directly is marked **unverified**. Entries are newest first.

## Incidents

### 1. Principal sat idle for 80 minutes and nobody woke it

- **Date:** 2026-10-07, 07:19 to 08:40 UTC.
- **What happened:** The Codex principal ended a turn at 07:19 and did nothing until the human resumed it at 08:40. The supervisor's wake request was held for 4558 seconds as "resting state contradicted by terminal output". An audit of 07:23 to 08:39 found 92 supervisor events and no verified fresh principal start. The human asked why nothing woke the principal and why the heads had not started a new one.
- **Root cause:** Not established. The source says the cause of the idle-state mismatch is unknown. The recovery owner tag in the supervisor config pointed at a session that no longer existed; the source calls this evidence, not proof of the cause.
- **What was changed:** The human clarified that "elect" means starting a fresh principal session, not promoting a head. A recovery contract was written: watch principal deadlines independently, and let a surviving head start a fresh principal after gated checks. The repair stayed with the existing supervision owner.
- **Sources:** `research/codex/continuation-fresh-principal-intake-20261007.md`, `coordination/continuation-runtime/REQUIREMENTS.md`

### 2. Ant head killed for memory; its own timer died with it

- **Date:** 2026-10-07, kill at 06:29:19 UTC, manual successor at 06:33:39 UTC.
- **What happened:** The Antigravity project head's unit got an out-of-memory kill 18 seconds before its own wake-up timer was due, so the timer never ran. The principal resumed the same saved conversation as a new head. At 06:50 a due request to the Windows-side bus recipient landed in its inbox only: no prompt, no acknowledgement. The metrics collector was also down and was restored separately.
- **Root cause:** Unknown. The source says the exact victim process, and whether the host or the unit's memory cap triggered the kill, are not known.
- **What was changed:** The record states that a timer inside a head cannot be that head's backup. Wake-ups were to rely on the independent supervisor instead. Workers were to run in their own measured units. The head memory cap was not raised.
- **Sources:** `research/codex/continuation-oom-recovery-c3123-20261007.md`, `coordination/continuation-runtime/DECISIONS.md`

### 3. Task tracker lost records during a shared-checkout rebase

- **Date:** 2026-10-07, about 06:15 UTC.
- **What happened:** Tool calls from the old Ant head ran checkout, stash and rebase in the shared main checkout and removed a note owned by the principal. The task tracker (`coordination/TASKS.json`) briefly dropped to 280 rows and lost two intake records. It was reconciled back to 282 rows.
- **Root cause:** The Antigravity receipt names `git checkout` on files owned by other agents. The Codex record says the exact command-to-change link was still unproven. **Unverified:** which command removed the two records.
- **What was changed:** A rule: never run checkout, restore, reset or a broad stash on files other agents own, and write tracker changes under the shared git lock. Before-images were kept privately. Moving the tracker to GitHub issues was decided separately.
- **Sources:** `research/codex/continuation-oom-recovery-c3123-20261007.md`, `research/antigravity/recovery/RECEIPT-TRACKER-CAS-RECONCILIATION-C3123.md`

### 4. Windows desktop work did not happen overnight

- **Date:** 2026-10-06 night to 2026-10-07, about 05:20 UTC.
- **What happened:** The human relayed: "I ask you to do stuff and the work doesn't happen." Follow-ups had gone to the principal and the Ant head, while a different session held the Windows deployment. The real owner sat idle overnight. A probe of the Windows machine failed because its name could not be resolved and no SSH alias existed. The endpoint worker and reviewer tasks were then marked failed because neither wrote the required `receipt.json`.
- **Root cause:** Messages went to the wrong owner, and "delivered to inbox" was treated as "acted on". The probe failure was a name-resolution problem; the source says it does not prove the machine was offline.
- **What was changed:** The coordinator wrote a new root contract that keeps delivery, reading, acceptance and action apart. It also gives root responsibility for checkpoints across both machines. The existing outbound desktop route was chosen for one reviewed bootstrap, with no new credentials. The failed tasks were left as failures.
- **Sources:** `research/codex/win35-execution-recovery-c3120-20261007.md`, `research/orchestrator/WIN35-ROOT-LESSONS-20261007.md`, `research/antigravity/recovery/REPORT-BUS-WIN35-DEPLOY-READINESS-C3123.md`

### 5. Claude Code sessions started without awareness hooks

- **Date:** 2026-10-07, morning.
- **What happened:** Interactive Claude Code sessions opened empty and reported as "NOTREADY expired working". The hook check exited 1 with missing events.
- **Root cause:** The managed hook entries for session start, prompt submit and after-tool events were missing from both Claude settings files.
- **What was changed:** Both settings files were backed up and the hooks merged back in with the standard init command. The re-check passed.
- **Sources:** `research/antigravity/recovery/CLAUDE-HOOKS-STARTUP-REPAIR-20261007.md`

### 6. Three-hour overnight gap with two head memory kills

- **Date:** 2026-10-07, 00:32 to 03:39 UTC.
- **What happened:** The principal missed its 00:40 check and stayed idle until the human resumed it at 03:39. The supervisor tried 28 times between 00:37 and 03:36 to deliver one wake message. Every attempt was refused as not ready. Escalation pointed at an obsolete head tag. The Ant head's unit was killed for memory at 00:56:34, and the temporary ZCode head (D3) at 02:23.
- **Root cause:** The supervisor saw an empty prompt, while the native delivery check read the Codex status footer as an unsent draft. The escalation target was dead. The cause of the memory kills is not identified in the sources.
- **What was changed:** Ant was restarted from its saved conversation at 03:43 under the same memory cap. Its delegates were required to run in separate units. A readiness-classifier repair and a failover task (C3110) were assigned. The source calls this manual recovery, not working failover.
- **Sources:** `research/codex/continuation-gap-runtime-20261007.md`, `research/codex/continuation-gap-recovery-20261007.md`, `research/codex/continuation-gap-governance-20261007.md`, `coordination/continuation-runtime/EVIDENCE.md`

### 7. A worker launched over the shared concurrency cap, then died

- **Date:** 2026-10-07, 00:03 to 00:21 UTC.
- **What happened:** Task C3091 failed after its actor died, with no provider or first-tool evidence. Its retry also failed at 00:20:40. The D3 head admitted launching it while the shared ZAI backend count was over the cap the human had set; the record calls this a policy violation.
- **Root cause:** Not proven. The record says no provider cause was inferred.
- **What was changed:** Launches had to go through the maintained admission route, counting the new actor against the cap.
- **Sources:** `research/codex/coordination-checkpoint-c3075-20261007.md`, `research/codex/occupancy-census-20261007-c3104.md`

### 8. Tracker overwritten by a stale copy, 16 tasks lost

- **Date:** 2026-10-06 evening; repaired 2026-10-07 around 00:33 Berlin time.
- **What happened:** `coordination/TASKS.json` was replaced by an older version with 274 records instead of 287. Sixteen historical tasks and some checkpoint history disappeared.
- **Root cause:** Unknown. The independent audit says the writer and cause remain unknown and declines to blame a reported rebase.
- **What was changed:** The 16 rows were appended back unchanged (290 distinct IDs, no duplicates). A guard script, `scripts/delivery/tasks_guard.py`, was then built. It checks the file's hash before writing and refuses writes that drop task IDs without an audited deletion record. An independent review accepted it.
- **Sources:** `research/codex/tracker-regression-independent-audit-c3067-20261007.md`, `research/antigravity/recovery/RECEIPT-TASKS-REGRESSION-PREVENTION-C3069.md`, `research/antigravity/reviews/REV-TASKS-REGRESSION-PREVENTION-C3069.md`

### 9. Supervisor kept running old code after a fix

- **Date:** 2026-10-06 to 2026-10-07; restarted 01:44 Berlin time on 7 Oct.
- **What happened:** The supervisor reported "composer state: unknown" for every session. A fix on disk passed its tests, but the running supervisor had been started before the fix and still used the old code.
- **Root cause:** The long-running process was never reloaded after the source changed.
- **What was changed:** A controlled restart through systemd, with backups and pending messages kept. Afterwards it read prompts as empty and exactly one supervisor was running. An independent review accepted the recovery.
- **Sources:** `research/antigravity/recovery/RECEIPT-SUPERVISION-RUNTIME-RECOVERY-C3090.md`, `research/antigravity/reviews/REV-SUPERVISION-RUNTIME-RECOVERY-C3090.md`

### 10. Codex status bar read as a draft: 76 refused deliveries

- **Date:** 2026-10-06, 14:55 to 17:01 UTC. The same pattern recurred on 7 Oct (incident 6).
- **What happened:** The supervisor tried 76 times to deliver one message to the principal. Each attempt was refused with "recipient composer has an unsubmitted draft" although the prompt was empty. The human resumed the principal by hand. Separately, sessions whose idle report was old were retried every tick, which the receipt calls "delivery attempt storms".
- **Root cause:** The installed `aplexer` binary predated the footer-parsing fix, which existed only as uncompiled source under a Rust build hold. The supervisor had no backoff.
- **What was changed:** A cooldown and diagnostic holds on 6 Oct. A 180-second cooldown and failover-candidate events on 7 Oct. A pre-check for contradicted idle state was added. Reviews accepted each change. A narrow rebuild plan for the binary was left waiting for human approval.
- **Sources:** `research/codex/continuation-runtime-diagnosis-20261006.md`, `research/antigravity/recovery/REPORT-READINESS-CLASSIFIER-CANDIDATES-AUDIT-20261006.md`, `research/antigravity/recovery/PLAN-NARROW-APLEXER-INCREMENTAL-BUILD-20261006.md`, `research/antigravity/recovery/RECEIPT-SUPERVISION-IDLE-WAKE-AND-FAILOVER-C3110.md`, `research/antigravity/recovery/RECEIPT-SUPERVISION-RESTING-STATE-CONTRADICTION-C3110.md`

### 11. All three Gemini heads ran out of provider quota

- **Date:** 2026-10-06, about 20:37 to 20:51 UTC.
- **What happened:** A quota launcher review failed with "Individual quota reached" after three tool calls. A screen capture then showed all three Gemini heads at their quota limit.
- **Root cause:** Provider quota.
- **What was changed:** A temporary ZCode recovery head (D3) was started at 20:51. No quota reset, upgrade or bypass was attempted. Unknown quota readings were treated as "do not launch".
- **Sources:** `research/codex/continuation-runtime-diagnosis-20261006.md`

### 12. Worker credential published in a public review report

- **Date:** 2026-10-06, about 17:42 UTC onward.
- **What happened:** A committed review report on the public `agent-branches` main branch contained worker credential material.
- **Root cause:** Not stated. The record assigns pre-publication secret scanning to heads.
- **What was changed:** The owning head revoked the scoped credential and redacted the report. The old value stays in public Git history; no history rewrite was requested. **Unverified:** that the credential no longer works was not independently tested.
- **Sources:** `research/codex/continuation-runtime-diagnosis-20261006.md`

### 13. Workers killed at their timeouts

- **Date:** 2026-10-06, 19:30 to 23:52 UTC.
- **What happened:** Maintained worker units were killed at their configured limits of 300 and 600 seconds. Some had made dozens of tool calls with no final model event. One (C3090) had partly rewritten service code that its earlier review did not cover.
- **Root cause:** The configured timeout. The record says no provider cause was proven.
- **What was changed:** No blind retries. Heads had to decide whether to split the task or set a better timeout. A separate reviewer re-checked the partly written code.
- **Sources:** `research/codex/continuation-runtime-diagnosis-20261006.md`, `research/codex/coordination-checkpoint-c3075-20261007.md`

### 14. Supervisor spammed heads and the principal

- **Date:** 2026-10-06, evening.
- **What happened:** Every 180 seconds the supervisor re-sent the same ready-task list to idle heads. After any change or restart it sent the principal a dump of about 2,400 tokens covering 40+ tasks.
- **Root cause:** The duplicate check was keyed only on a 180-second time bucket, so it changed with the clock. Principal messages always carried the whole list.
- **What was changed:** The key now includes a fingerprint of the ready tasks. Messages carry only changed tasks (at most 10), plus a pointer to the tracker.
- **Sources:** `research/antigravity/recovery/REV-SUPERVISION-HEAD-READY-DEDUP-20261006.md`, `research/antigravity/recovery/REV-SUPERVISION-DELTA-PAYLOAD-BOUNDING-20261006.md`

### 15. A "preview" run committed and pushed

- **Date:** 2026-10-06, about 10:30 UTC.
- **What happened:** An Agent Branches CLI run with `--preview` committed and pushed to `origin/main`. It changed only the document it was allowed to touch, and other files were unchanged, but preview must not change anything.
- **Root cause:** A defect in the CLI preview path.
- **What was changed:** A narrow repair with a negative preview test. A retest on the repaired version passed with no commit and no push.
- **Sources:** `research/codex/tool-adoption-preview-failure-20261006.md`, `research/codex/tool-adoption-preview-retest-20261006.md`

### 16. Heads repeatedly went quiet and were recovered by hand

- **Date:** 2026-10-06, about 02:00 to 09:45 UTC.
- **What happened:** The Ant, quota launcher, publication and coordination heads each stopped at an empty prompt. Delivery was refused because later terminal output contradicted their idle state. Each was stopped and resumed from its saved conversation after a database snapshot. Coordination stopped again right after recovery. A preservation script failed partway with `SameFileError`, but the planned stop still ran. Separately, the quota launcher head deleted a reviewer's report while it was being written, then restored the exact saved content.
- **Root cause:** No working automatic wake-up. The deletion was a manual `rm -f` race.
- **What was changed:** A recovery runbook: take and check the snapshot before stopping, keep the memory cap, and have the principal verify custody before changing the registry. The source calls repeated manual recovery a workaround, not continuity.
- **Sources:** `research/codex/head-custody-recovery-20261006.md`

### 17. Auto-dispatched workers ran in the main checkout with title-only prompts

- **Date:** 2026-10-06, before 07:50 UTC.
- **What happened:** Six task units were dispatched with bare title-only prompts and ran in the main repository checkout instead of isolated worktrees. They wrote into areas leased to other heads and left telemetry files in the repo root. Two were marked done only because the process exited 0.
- **Root cause:** The working directory was hard-coded to the repo root, prompts carried only a title, and exit code 0 was treated as acceptance.
- **What was changed:** Nothing was deleted or reset. Changes were held for the owning heads to review, telemetry files were moved out, and the two tasks went back to review.
- **Sources:** `research/coordination/AUDIT-LAUNCH-CONTRACT-AND-CONTENTION-DISPOSITION-20261006.md`, `research/coordination/REV-LAUNCH-CONTRACT-AUDIT-20261006.md`

### 18. Work dried up overnight: zero active workers

- **Date:** 2026-10-05 22:31 to 2026-10-06 07:05 UTC.
- **What happened:** A census at 22:31 found no active workers. All 23 queued rows were blocked as "bare proposal without substantive prompt". At 06:53 there were still no confirmed active workers, although the tracker listed 32 ready or queued items. Over the same night the supervisor could freeze when its own session identity changed, because old unacknowledged messages from earlier identities stayed pending.
- **Root cause:** "Ready" tasks had a title but no executable prompt. The supervisor did not recognise its own earlier identities.
- **What was changed:** Heads were told to replace proposals with acknowledged, scoped task contracts. The supervisor now keeps a list of its earlier IDs and supersedes stale messages after a sender or recipient change. A review accepted it.
- **Sources:** `research/codex/continuity-current-census-20261005.md`, `research/codex/recovery-current-census-20261006.md`, `research/antigravity/recovery/RECEIPT-SUPERVISION-LIVE-WAKE-20261006.md`
