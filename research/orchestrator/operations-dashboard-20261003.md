# Private operations, ownership and continuous oversight

Recorded 2026-10-03T04:01:45.355288+00:00. Human31 is preserved verbatim in experiment/USER-INSTRUCTIONS.md; role policy commit5774715.

## Operating responsibilities

Principals monitor all teams, maintain coverage, verify actual head/executor output, inspect blocked work, arrange corrective actions and check each other. Codex covers Grok/ZCode/Bunny; Claude covers Antigravity/Muse/integration/resources, with acknowledged shared coverage when one is unavailable. Heads own goals, backlogs, implementation/research teams, integration and recovery. Executors own scoped artifacts/tests and report completion. Reviewers independently check pinned results. Principals do not create their own implementation teams. Heads may use useful headless/harness workers as needed under actual quotas/resources; historical fixed worker caps do not apply.

coordination/OPERATING-MODEL.md, TEAM-REGISTRY.json and TASKS.json define roles, current assignments, acceptance, dependencies, next actions and task ownership. Shared updates use .local/task-registry.lock and atomic replacement. Owner assertions, message delivery, receiver ACK and independently accepted outcomes remain separate.

## Live private services

The dashboard is bound only to Hetzner127.0.0.1:8766. Desktop access uses an SSH loopback tunnel. There is no public telemetry endpoint. Collector snapshots every60s; the browser refreshes every30s. Supervisor also samples every60s and durably notifies the responsible principals on meaningful queue changes or an acknowledged new unexplained-idle episode. >5min ready-work idle calls for investigation; task-specific progress checkpoints initially default20min and can be adjusted with evidence.

The immutable private supervisor CLI copy SHA256 is8d49a216d43c70843bc07705f4c11eb13f3eb51646d5c6fc204ce0796ce618c4. It avoids dependency on an actively changing development build. Its missing native idempotency-key capability is explicitly detected: durable intent/receipt reuse and uncertain-response freeze prevent blind retries; this is not an exactly-once guarantee. It uses genuine binding and original sender IDs, two fresh empty idle/waiting observations plus immediate recheck, native delivery guards and fresh Codex quota gates. Busy work, drafts, feedback menus, missing state and uncertain delivery deny input. It never forges state/senders or submits a human draft.

The current snapshot at 2026-10-03T04:01:32.960309+00:00 records 9 registered execution agents, 8 live workload roots and 2 reported-working hooks. These change over time and are not accepted productive-work counts. Services/writers are excluded from execution counts. Supervision status at 2026-10-03T04:01:41.464643+00:00 has 0 reported service errors. See live data for current state rather than treating this report as a permanent count.

## Actual response and useful work

Both principals responded through genuine aplexer messages. Claude reply01a0ffda-2f1a-7b81-bb67-b333cbd4cf32 and Codex01a0ffdd-a8bb-7271-8cb8-bfd6e6d600af identify owners, task updates, next checks and native blockers. Codex subsequently ACKed current service envelope01a0ffe0-ccf4-7592-98a7-409fab3ef569 and replied01a0ffe1-e507-7e70-b948-d1fe1cc27a58. Root inspected actual updated TASKS, Bunny incumbent research5817275, Muse bounded negatives/external-report verificationb8ca24d and ongoing Antigravity source tools; later Bunny negative corrections4937506 and scribe evidence integration0d35081 are present.

One initial root-authored Codex activation after fresh empty composer checks and quota was explicit idle fallback input, not automatic native repair. Grok and ZCode still have queued work with stale native readiness and no verified first action for those assignments. Antigravity owns the repair; Muse independently reviews it and principals own alternate useful execution/receiver recovery. The services detect this gap. General all-head autonomous wake-up, uninterrupted productive execution, and native cross-host outage recovery are not proven. Healthy productive sessions were preserved; no duplicate principal or worker was launched by root for this setup.

## Measurements and experiment data

The dashboard records team/role/live/hook/stale/unknown/unregistered counts, tasks and dependencies, registered evidence file metadata, observed idle durations and transitions, sampled task-state time, workload-root CPU/RSS, host load/free disk and account quota windows. Token sources show input/output/cache breakdown, cumulative native conversation totals, first-observed baselines and interval deltas with coverage. Cached input is a subset, not added again. Resumed conversation identities are deduplicated. Services and editorial writers are separate roles.

At this sample 7 registered agents lack direct usage observations. Missing telemetry remains unknown. Historical native counters include history before collection began at03:37:37UTC; they are not experiment-period spend. Provider quota is account-wide, not agent tokens or paid cost. The completed Opus daily writer has real modelUsage and a provider-reported list-price estimate, explicitly not an actual subscription bill. Native harness usage can be registered only from real cumulative provider metadata with exact identity and stable event IDs. No raw prompts or credentials are collected.

Snapshots, task transitions, source baselines and exports remain private under .local/metrics. Verified compressed archives preserve history; collection visibly pauses at its256MiB history cap instead of discarding experimental data. The private exporter supports the final experiment analysis. Sampled hook time and token counts do not measure useful work: join outcomes to task acceptance, independent reviews, negative results and corrections. CPU/RSS presently cover root processes only, not their descendant workloads. File counts cover registered paths, not every artifact in an entire repository.

Principal diagnosis01a0ffe3-fb59-77a1-952c-c8585413fdb4 found exporter evidence_files_latest initialized to0 without assignment. Root accepted the finding and requested a narrow distinct-file/coverage correction and regression test. These old zeros are placeholder defects, not measured absence of output. Compression integrity is also strengthened with SHA256 before replacing collector-owned originals. The supervisor's operational history is being retained as verified archives rather than overwritten spools.

## Verification and persistence

Root ran the collector/adapters test discovery and supervisor tests before deployment. Final regression results are recorded in the commit event after the exporter/retention corrections. Actual dashboard DOM shows team tables, live state, tasks, quotas and cumulative/interval usage. Both services are genuinely bound aplexer processes; actual status and receiver evidence, rather than CLI startup alone, establish operation.

The existing30min orchestration and09:00 daily standup schedules retain their cadence and now include Human31 ownership, private telemetry and between-turn supervision checks. Root heartbeats are oversight, not a substitute for the continuous service/head loops. Pause30min monitoring only after the genuine selection/productive handoff gates and verified between-turn supervision; those gates are currently not met.

No raw metrics were published. No purchase, token creation, quota reset redemption, global binary installation or existing-worktree deletion was performed. Public journal corrections are separately reviewed and deployed; internal telemetry stays private.
