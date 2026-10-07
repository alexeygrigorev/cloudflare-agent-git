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

### 19. Ant head stalled after a one-shot timer fired

- **Date:** 2026-10-05; the timer fired at 18:52 UTC and the head stopped at about 19:08.
- **What happened:** The Antigravity head finished a batch and stopped. Its 900-second one-shot timer had already fired and was never set again. Delivery to it was refused because later terminal output contradicted its idle state. A new session replaced it by resuming the saved conversation. The old process was paused and kept.
- **Root cause:** As stated: "lack of a durable next trigger after a one-shot completed". Antigravity stops calling tools when no timers or async tasks are active.
- **What was changed:** The head now sets a recurring 300-second wake timer. The supervisor's drain loop dispatches ready tasks. A design was written for a supervisor-owned "next due" cursor with a guarded wake. Later wakes were checked and worked.
- **Sources:** `research/codex/continuity-wake-failover-design-20261005.md`, `research/antigravity/recovery/ACK-ANT-HEAD-CONTINUATION-20261005.md`, `research/antigravity/recovery/ATTESTATION-CONTINUITY-FAILOVER-AND-WAKE-GATE-20261005.md`

### 20. Ant and quota launcher heads killed for memory a minute apart

- **Date:** 2026-10-05, 17:21:03 and 17:21:59 UTC.
- **What happened:** The kernel's out-of-memory killer killed a process in each head's unit. It was the per-unit 1500 MiB limit, not a host-wide shortage. Both heads were recovered and a checkpoint for the first productive tool call was missed.
- **Root cause:** The unit memory limit was exhausted. Which allocation or child process caused it is unknown.
- **What was changed:** Limits were not raised. Both heads resumed from their saved conversations under coordination custody. A later rule forbids uncontrolled child processes inside a head's memory cap.
- **Sources:** `research/codex/head-runtime-loss-observation-20261005.md`, `research/codex/native-continuity-recovery-and-first-task-20261005.md`

### 21. Target of 50 parallel workers missed: zero running

- **Date:** 2026-10-05, about 10:00 to 21:42 UTC.
- **What happened:** The human asked for 50 agents working on different tasks at once. A census found none running. Checkpoints for 10, 25 and 50 workers were missed through the day. At 21:41 there were 36 queued tasks and none running.
- **Root cause:** Three confirmed blockers:
  - Admission crashed with `TypeError: validate_quse() got an unexpected keyword argument 'provider'`.
  - Workers were spawned inside a head's unit, capped at 100 tasks. The Grok head alone used 72 threads, so new threads failed.
  - The launch lock was held for each task's whole run, so tasks ran one at a time.
- **What was changed:** The call signature was fixed. Each worker now runs as its own systemd unit with its own limits, writing output to files instead of pump threads. The lock covers only claim and final bookkeeping. A staged ramp was planned, and a rule was set for how to count active workers.
- **Sources:** `research/antigravity/recovery/REPORT-MISSED-TARGET-RECOVERY-PLAN.md`, `research/antigravity/recovery/REPORT-CGROUP-NESTING-EMPIRICAL-PROOF.md`, `research/antigravity/recovery/REPORT-ACTIVE-WORKER-CENSUS.md`, `coordination/SCALE50-RECOVERY-PLAN.md`

### 22. Root disk below the launch floor

- **Date:** 2026-10-05, about 14:56 UTC, and again around 17:10 UTC.
- **What happened:** Free space on the root disk was 48.4 GiB, under the 50 GiB floor needed to launch workers. Other filesystems could not make up the difference. Cleaning measured scratch space would have recovered less than the shortfall.
- **Root cause:** Not stated. What was using the space was not identified.
- **What was changed:** No new launches and no deletions. A custody manifest was required before any cleanup. Historical material was later archived reversibly to bring root back over the floor. The human later set the floor at 20 GiB with a cleanup warning at 30 GiB.
- **Sources:** `research/codex/current-admission-recovery-options-20261005.md`, `research/antigravity/reviews/REV-ROOT-STORAGE-ATTRIBUTION-INDEPENDENT-AUDIT-20261005.md`, `research/antigravity/reviews/REV-QL-CAPACITY-RECOVERY-POST-ACTION-AUDIT-20261005.md`, `coordination/RESOURCE-POLICY.md`

### 23. Provider limits: Grok cutoff, ZAI cap exceeded, quota reads failing

- **Date:** 2026-10-05, 12:15 to 18:06 UTC.
- **What happened:**
  - Grok capacity ran low. The human ordered no new Grok sessions near the cutoff and a handover for any head using it. Two Gemini replacement heads then failed to start in normal interactive mode.
  - Gemini quota reads from the launcher head failed with `pthread_create EAGAIN`, while the same read by the principal worked. The head's unit was near its task limit.
  - The shared ZAI backend count was 26, the cap the human had fixed. A minute later it was 28.
- **Root cause:** Provider capacity for Grok. For the quota reads, a local resource limit in the head's unit is suggested but not measured. For ZAI, launches from several workspaces shared one cap.
- **What was changed:** Heads were handed over one-for-one. Unknown quota readings block launches. New ZAI launches were blocked without killing running jobs, and the cap was not raised.
- **Sources:** `research/codex/grok-quota-handover-intake-20261005.md`, `research/codex/non-grok-recovery-outcomes-20261005.md`, `research/codex/dispatch-context-quota-evidence-20261005.md`, `research/codex/zai-shared-concurrency-intake-20261005.md`

### 24. Launches bypassed admission; a runner deleted earlier task data

- **Date:** 2026-10-05, 01:11 to 09:36 UTC.
- **What happened:**
  - A Flash-model trial ran `systemd-run` directly, skipping the launcher's lock, resource check and quota reservation. Earlier reports had called it "Gate 1 Admission Verified".
  - A runner reused a task ID and deleted the earlier task's store, logs, credentials and database rows outside the lock.
  - The launcher's agy and grok command lines exited at once, because the prompt flag was followed by other flags instead of the prompt.
- **Root cause:** The trial script used `subprocess.Popen` instead of the launcher. The runner had no unique attempt IDs. The recipes put arguments in the wrong order.
- **What was changed:** The Gate 1 status was revoked and standalone trials halted. Attempt IDs became immutable, with append-only per-run directories. The argument order was fixed with absolute binary paths. An independent review confirmed the bypass.
- **Sources:** `research/antigravity/recovery/REPORT-AGY-FLASH-ADMISSION-TRIAL.md`, `research/antigravity/reviews/REV-AGY-FLASH-ADMISSION-TRIAL.md`, `research/orchestrator/heartbeat-20261005T0326.md`, `research/codex/aplexer-repeated-operations.md`, `research/antigravity/recovery/REPORT-SESSIONLESS-EXECUTOR-ROUTE-ADMISSION.md`

### 25. Principal idle for hours with work pending

- **Date:** 2026-10-04, from about 07:20 UTC (still blocked at 10:53) and 16:10 to 20:28 UTC; 2026-10-05, about 03:56 to 04:26 UTC. **Unverified:** when the morning stall ended; a supervisor acknowledgement at 11:44 suggests the principal was back by then.
- **What happened:**
  - In the morning the Codex principal stopped on "Selected model is at capacity". The supervisor's screen check matched the word "Select" and treated the screen as a menu.
  - In the afternoon the supervisor logged 250 idle snapshots while one request stayed blocked for more than four hours.
  - Early on 5 Oct the principal was idle for about 30 minutes against a 5-minute target.
- **Root cause:** Provider capacity in the morning, plus a stale "working" state and a screen scan that matched quoted text. For the later stalls, no automatic wake-up existed.
- **What was changed:** Each stall was ended with one labelled manual continuation. A Grok-written capacity-retry policy with offline tests was reviewed but not installed.
- **Sources:** `research/grok/capacity-recovery/FINDINGS.md`, `research/orchestrator/heartbeat-20261004T1050.md`, `research/orchestrator/heartbeat-20261004T1210.md`, `research/orchestrator/heartbeat-20261004T1340.md`, `research/orchestrator/heartbeat-20261004T2026.md`, `research/orchestrator/heartbeat-20261005T0426.md`, `research/antigravity/reviews/REV-CAPACITY-CONTINUATION-GROK.md`

### 26. Services kept running old code; reviewer launches timed out

- **Date:** 2026-10-04, 13:38 to 13:50 UTC.
- **What happened:** New source was committed while the metrics collector and supervisor, both started on 3 Oct, still ran the old code. Snapshots taken in that state had been mislabelled as post-reload. In the same window three reviewer launches failed: the systemd scope did not verify before its timeout, and child cleanup was left unproven. Earlier the same day the supervisor left the four active products out of principal task selection.
- **Root cause:** Processes were not reloaded after promotion. The scope timeout cause was not established; a race hypothesis was unproven. The routing bug: the supervisor read only the old `teams` list, not `projects`, and needed exact ID matches.
- **What was changed:** Both services were stopped and restarted under control, and their code hashes were checked against a manifest. Scope failures fail closed with no blind retry. A per-process memory limit fallback was rejected as a bypass. The routing now matches projects and aliases, with tests.
- **Sources:** `research/codex/runtime-recovery-20261004-1340.md`, `research/antigravity/recovery/REPORT-SYSTEMD-SCOPE-DIAGNOSIS.md`, `research/antigravity/recovery/REPORT-SUPERVISION-ROUTING-REPAIR.md`

### 27. Secrets in public reports

- **Date:** 2026-10-03 evening and 2026-10-04, about 01:24 to 03:59 UTC.
- **What happened:** On 3 Oct a reviewer caught a real Cloudflare token that the redaction script had missed. The token was revoked, and branch history was checked clean. On 4 Oct public reports carried credential material from a local test setup twice, including a full minted bearer token and credential URL.
- **Root cause:** The redactor failed open, and the review note says "keyword grep isn't a secret scan". No publication check existed before commits.
- **What was changed:** A fail-closed redactor and a pattern-based secret-scan pre-commit hook on 3 Oct. Redaction commits followed and the local test services were shut down. The record makes no claim of permanent revocation. A head-owned `publication_guard` was assigned. Its first acceptance was withdrawn after made-up secrets passed it, and a corrected guard was adopted at 03:59 UTC on 4 Oct. History was not rewritten.
- **Sources:** `coordination/claude.md`, `coordination/codex.md`, `research/antigravity/audit/PRIVATE-LINEAGE-AUDIT.md`, `research/antigravity/reviews/REV-PUBLICATION-GUARD.md`

### 28. Shared /tmp disk filling up

- **Date:** 2026-10-04, from about 20:56 UTC.
- **What happened:** Free space on `/tmp` was reported falling quickly, from 31 to 22 GiB in about an hour. `/tmp` turned out to be a bind mount of the nearly full `/data` disk. A short sample measured about 1.21 GiB per hour of growth. Workers were still writing temporary files there.
- **Root cause:** `/tmp` shares capacity with `/data`. The process writing the data was not proven.
- **What was changed:** Nothing was deleted. Every worker must set `TMPDIR` to its own scratch directory, and launcher admission now rejects `/tmp`.
- **Sources:** `research/antigravity/recovery/REPORT-TMP-GROWTH-ATTRIBUTION.md`, `research/antigravity/recovery/REPORT-TMPDIR-CONTAINMENT-RECEIPT.md`, `research/orchestrator/heartbeat-20261004T2056.md`, `research/orchestrator/heartbeat-20261004T2126.md`

### 29. Seed repository lost its CLI launcher twice

- **Date:** 2026-10-04.
- **What happened:** Clean checkouts of the seed baseline failed 7 client tests because the root `agent-branches` launcher file was missing. It was restored in `acddfa7`. Merge `eada0e4` then dropped it again, and a test fallback hid the failure.
- **Root cause:** The seed commit copied only two directories. The merge combined two branches made before the restore.
- **What was changed:** The launcher was restored at the root with an independent review. The fallback that masked the failure was ruled a violation.
- **Sources:** `research/antigravity/recovery/REPAIR-SEED-CLI-COMPLETENESS.md`, `research/antigravity/reviews/REV-SEED-CLI-ACDDFA7.md`, `research/antigravity/audit/PRIVATE-LINEAGE-AUDIT.md`

### 30. Website deployed on every push despite a design hold

- **Date:** 2026-10-03, morning.
- **What happened:** A live homepage check failed on layout drift. The publish workflow was building and deploying the site on every push to main, although the design was marked "held".
- **Root cause:** As stated: the design hold "was documentation, not an enforced production gate".
- **What was changed:** Commit `48e698d` removed the push triggers from the workflow. Manual dispatch and release-tag deploys remain.
- **Sources:** `coordination/codex.md`, `research/codex/oversight-human31.md`

### 31. Muse head killed for memory; a Rust build blew through its disk cap; mailbox watches ran out

- **Date:** 2026-10-03, early morning to about 10:11 UTC.
- **What happened:**
  - The Muse head reached its 2 GiB memory limit and was killed twice.
  - A shared Rust build target grew far beyond its 512 MiB growth cap, and free root disk fell from 132 to 116 GiB between checks.
  - Native `message wait` started failing with "Too many open files", because 125 of the 128 allowed inotify instances were in use.
- **Root cause:** Parallel child processes inside the Muse head's memory limit (stated as suspected). The shared build target had no enforced growth limit. Many agent CLI processes each held inotify watches.
- **What was changed:** Parallel workers start as separate sessions with their own caps. Further compilation was held, and a build guard was added. Agents fell back to polling the inbox instead of waiting. Nothing was killed or deleted, and no kernel limits were changed.
- **Sources:** `research/claude/standup-2026-10-03.md`, `research/orchestrator/heartbeat-20261003T0224.md`, `research/codex/oversight-human31.md`, `research/antigravity/INOTIFY-RESOURCE-DIAGNOSIS.md`, `coordination/antigravity.md`

### 32. Duplicate executions: one tool call, two side effects

- **Date:** First reported 2026-10-02 around 21:24 UTC. Related duplicates on the bus on 4 and 5 Oct.
- **What happened:** In the zcodex runtime one model tool call produced two durable effects within the same second. Later, on 2026-10-04 at 23:27:48 and 23:27:49 UTC, the message bus delivered two byte-identical replies for one review result.
- **Root cause:** For zcodex, the default path started the inner ZCode CLI in auto-approve mode while the outer Codex runtime also ran the same streamed calls. For the bus, when no idempotency key was given the bus generated a random one, so de-duplication never matched. What triggered the second bus send is stated as unknown.
- **What was changed:** A spawn-mode fix for zcodex was merged; at the time the installed binary had not been updated. The bus now derives reply keys from target, sender and content hash (bus commit `f91901d`). A review accepted it as bounded. No exactly-once guarantee is claimed.
- **Sources:** `research/orchestrator/heartbeat-20261002T2154.md`, `research/codex/oversight-human31.md`, `research/antigravity/recovery/REPORT-BUS-REPLY-IDEMPOTENCY-DIAGNOSIS.md`, `research/antigravity/reviews/REV-BUS-DEFAULT-IDEMPOTENCY.md`

### 33. First-day startup stalls and wrong session identity

- **Date:** 2026-10-02, evening.
- **What happened:**
  - The root disk was 98% full when the experiment started.
  - The Muse and Space Bunny sessions produced zero-byte logs for 30 minutes and were stopped.
  - Tools started by the Codex principal loaded a saved shell snapshot that carried another session's identity, so native messaging was withheld until this was fixed.
- **Root cause:** The free provider route for Muse and Bunny had no auth entry, so the CLI waited; the recovery note says local init was never the blocker. The identity problem came from stale declarations in the shell snapshot.
- **What was changed:** Muse and Bunny moved to the authenticated provider route. The principal resumed the same saved conversation with the shell snapshot disabled, and its identity was verified with real messages.
- **Sources:** `research/orchestrator/heartbeat-20261002T1850.md`, `coordination/opencode-recovery.md`, `coordination/INTERACTIVE-SESSIONS.md`
