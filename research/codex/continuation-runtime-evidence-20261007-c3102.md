# Continuation runtime evidence — C3102

Observed 2026-10-07T00:18:55.260732+00:00. Administrative metadata only: no native identity/mailbox actions, provider execution, lifecycle mutation, tests or product code review. Private transcript bodies and credentials remain private. Coverage is the existing Ant conversation, selected supervision receipts, the D3 isolated task store and Git object metadata; whole-fleet coverage remains unknown.

The older diagnostic is preserved without restoration or further append. Its exact beforeimage at this checkpoint is 162141 bytes, SHA-256 `cdb0128c82677b56387143a74b6d5fcd20f94df9e213e39b8d69de74c28b5dca`. A private immutable copy exists under the owned C3102 evidence directory. Earlier disappearance of sections remains an unattributed custody problem; no writer or causal explanation is established.

## Message delivery and continuation

Exact envelope `01a113aa-3715-71c2-af6f-839e65d39d90` was created 00:01:24.841101 UTC, from supervisor `7bff6e1d-5a78-47b7-8a03-00361800cafd` to Ant head `3b522ddb-8dc8-41b4-a382-f76baab33b0a`. The existing supervision receipt and persisted last-request both record delivery `inbox`. A native exact-consumer-cursor ACK is preserved, timestamp 00:03:47.355780. This is not a guarded native submission receipt.

In the actual Ant conversation `ea14b401-20e9-4e48-ab08-d15be08da30d`, completed commands already ran continuously from 00:00:45 to 00:01:26, including step26108 at 00:01:23.599937 immediately before creation. Step26114 executed message-show at 00:01:28.860221; step26117 executed ACK at 00:01:33.196137. Thus this envelope does not establish an ended-head idle wake. A separate later delivery attempt is not excluded, but no corresponding guarded SUBMITTED record has been found in this bounded inspection.

Native schedule26772 was recorded 00:13:23.848279 with duration180s, condition `any`, and full callback: “Check for new peer messages, monitor supervision state, and continue next product iteration”. Discrete callback26776 at 00:16:24.656376 references26772; first subsequent completed run-command26778 occurred 00:16:26.881428. This proves a timer callback followed by an actual model tool, separately from message-delivery causality. The principal reports a separate same-envelope strict delivery rejection at 00:16 with NOTREADY; that negative is principal-observed, not a helper-executed action.

## Branches CLI publication and review provenance

Ant step26566 at 00:09:29.341861 returned structured status `failed`. Corrected actual `agent_branches.cli sync git` step26573 at 00:09:45.085715 returned `synced`, publishing `df8117e5d07134f4d3a354440f9399ee648aef80` on `recovery/metrics-and-supervision-c3098`. This is an actual owner CLI action, distinct from a manual Git-only claim. Numeric command exit is not independently extracted here.

Read-only remote inspection verified main `7f3e3006c00e93481286a6c85cd2ef99e9ab53c1` and the recovery branch above. All seven declared owned paths have identical Git blobs in these two commits: watcher, supervision tests, C3098 receipt, C3098 review, C3097 review, delivery guard and guard tests. Blob inclusion/equality is established; no additional commit-ancestry claim is made.

Distinct native reviewer `043c65f0-46d7-4184-9ffa-d23ae08cadd6` first completed run-command at 00:10:03.430585 and wrote `research/antigravity/reviews/REV-BRANCHES-DOGFOOD-SYNC-C3098.md` at 00:12:21.348183. The 15,739-byte report SHA-256 is `c5632d32346a4c57c4c518945f6ff4a5cbfe26de71f4b34b1f0fbe85b50109a1`; write metadata binds full source563a007 and recoverydf8117. Claimed receipt385cf0ab was not resolved as a local Git object or matching filename in this bounded check; its exact receipt location remains required. No code verdict is independently supplied by this helper.

## Watcher and earlier independent actors

Installed watcher path is `scripts/supervision/systemd/supervision_watcher.sh`, SHA-256 `18486ed1aa4c41aac736f6026c28fbed16aaf114a89ab3790039aacdc55f840c`. Existing watcher instances1/2 both executed it and journaled finished runs at 00:02:44,00:03:44,00:04:44 UTC; their latest inspected 00:09:44 runs had actual exit0. This proves bounded oneshot execution, not a cap-crossing or idle-delivery result.

Native implementer a2d9d6d6 first tool00:00:46.435632, receipt-write00:03:21.810861, last-send00:03:33.333601. Distinct reviewer b5fca232 first tool00:03:52.846815, report-write00:05:08.784199, last-send00:05:16.191708; report SHA-256 `964538e4ed46a0572cbd39571ef7ecbfff02e4f53162c3792647886cad7cb392`, containing the full watcher and test byte hashes. C3097 distinct reviewer2531d952 first tool00:03:53.257928 and report-write00:06:03.552893; report SHA-256 `418a292c312ee28fd6d33ba10e6c2e23dd567834324086d739ee1f3fdde597a1`. These are completed-history actors, not current ACTIVE counts.

## D3 isolated admission limit

At this checkpoint the third isolated store still records `t-zcode-qa-c3091-v2` as starting, created00:08:19/updated00:08:43, reason launching viazai. Both exact named task/controller units are not-found. Legacy launcherPID3861937 still exists, but no provider CID, immutable source receipt or model first-tool has been recovered. A live launcher does not establish a useful executor or healthy quota admission. The head owns reconciliation of this same task and actual provider evidence before any retry. Earlier task death and head-reported shell timeout remain separate evidence classes.

Current useful executor lower-bound from this inspection is not established after the completed reviewer tails; Ant's current head tool is head activity, not a delegated worker. READY reserve and total active fleet remain unknown. Next owners: Ant supplies exact receipt385cf0ab and advances a concrete reviewed successor; D3 reconciles the existing v2 admission with real actor/provider evidence. Principals retain genuine delivery authority and preserve queued NOTREADY envelopes.

## Addendum — 00:20 UTC bounded checkpoint

The principal reports Ant's genuine formal retraction of the idle-delivery claim. This agrees with the independently observed already-active command chronology; the helper did not read native inbox or send an ACK.

The previously unresolved receipt is now located: `research/antigravity/recovery/RECEIPT-BRANCHES-DOGFOOD-SYNC-C3098.md` in remote main7f3e300 has Git blob `c82eee6bbd52f93efce5b073e84659aecc6519f3`, 6,630 bytes and SHA-256 `385cf0abca87ded5dc9e017341849f03b70b363f75964e1899ff68126a3c287b`. Thus385cf0ab was a SHA-256 prefix, rather than a Git object identifier.

New distinct native reviewer `c92df45e-47de-490f-9d71-ccbfa93c11cb` first completed view-file00:17:49.923857 on the exact C3102 disposition receipt. It wrote `research/antigravity/reviews/REV-EXACT-IDLE-DELIVERY-DISPOSITION-C3102.md` at00:19:28.019308: 20,007 bytes/SHA-256 `f0c4aa20a3dd6564655d586d5cc7aa5f293661cd35d4742e0f7112a36bbdc5d2`. Last observed send-message00:19:36.165221 was still pending(status2); no provider-final or completed parent delivery is inferred from that snapshot. This is review provenance, not helper code acceptance. D3v2 still records starting/updated00:08:43; no new model first action was established.

A later bounded parent-history read confirms actual completion callback26937 at00:19:37.942656 explicitly namingc92df45e. The reviewer report write metadata contains full source pins563a007b6ca731b592e79c8385c4005a049108bb anddf8117e5d07134f4d3a354440f9399ee648aef80. No new timer was present in that inspected post-spawn history.

## Addendum — 00:24 UTC actual maintained v3 admission

The third isolated store now has `t-zcode-round-record-review-c3098`, created00:21:31 and starting00:21:58/task-units lease antigravity. Its immutable source receipt validates `202d29a43dbd4357725d187901177450396ed0ba` at00:21:31.590522, no fallback, timeout900, competition cwd. Actual controllerPID91825/start00:21:47/invocation0dc60acc34c942c195d5ceb21bf70237 and workerPID98640/start00:21:58/invocation19565d8cf9bb43f69523fd51d7195d0f were loaded/active. Worker768MiB/100Tasks; systemd RuntimeMax is infinity, so900 is an outer policy rather than a unit runtime guard. Executable `/home/alexey/.local/bin/agy` was invoked with `gemini-3.1-pro-high`. Fresh quota/reservation receipt was not recovered in this bounded check.

Actual stdout binds model conversation `e4a2080f-6fb9-406c-bf52-0b074c4339b4`, first completed view-file00:22:07.822009. Five actual tool events existed; latest completed run-command00:23:41.093524. This establishes one current useful maintained model actor in the covered scope, not a global fleet count or completed independent acceptance. No final report was inferred.

Ant scheduled26981 at00:20:21.257248/180s/any, then separately scheduled26990 at00:20:28.858291 with the same callback: “Check on aplexer inbox, verify Bus327 loopback spike coordination status, and resume useful independent work.” Actual callback26997 at00:23:21.918949 references26981. This records two schedule requests rather than inventing a single timer; scheduler cancellation/deduplication of26990 was not established.
First subsequent head tool26999 was run_command at2026-10-07T00:23:23.853049+00:00, status3.

## Addendum — 00:27 UTC loopback provenance

The loopback spike implementation is directly attributable to Ant head write-to-file steps27035/27038/27044 and subsequent replace-file-content calls through27119. It is head implementation, not evidence of a separately delegated implementer or maintained task-unit execution. Three files existed in the claimed spike directory at this snapshot: adapter.py15,405 bytes/SHA5637cf8c16e6e59c6e7838714512d7c0dcce2fe6c59e9be09e1ab6355a08ce85; test_loopback_spike.py15,627 bytes/SHA4b4cb37dea8961b413ebde85078a273374a9cdfe6eb6786db1380157969fff7c; client.sh3,508 bytes/SHA3e69b73aacb86baa39d6db39c3108bb8e22e513cb45d54a51dfea9789a276be1. The claimed receipt was not present in that directory.

Distinct native reviewerf7044808-6b7e-48db-a9ad-675d2737a563, parent Ant/spawn27128, first completed run00:26:30.788237 and latest completed view00:26:58.741032. No report write existed at that snapshot. Source acceptance and physical/non-SSH adoption are not inferred.
Existing maintained v3 latest recovered tool metadata: {'idx': 29, 'status': 3, 'time': '2026-10-07T00:27:08.880871+00:00', 'tool': 'run_command'}. No final outcome is inferred.

The receipt is present at the separate recovery path `research/antigravity/recovery/RECEIPT-BUS-WIN35-LOOPBACK-SPIKE-20261007.md`: 9,725 bytes/SHA-25615e2ebce38cdd27e9ca5fd260cae66b10a0db51f59f309a4e4bab4bea2bdd0b1. Its absence from the spike directory is a path correction, not a missing deliverable.

## Addendum — 00:30 UTC report and terminal checkpoint

Loopback reviewerf7044808 wrote `research/antigravity/reviews/REV-BUS-WIN35-NONSSH-LOOPBACK-SPIKE-20261007.md` at00:27:50.131117, 16,286 bytes/SHA-25650b3d25f2453489f00f5bba0b8a4178938bd3ea726e68436f0120307ca46b8c8. Its final observed send-message completed00:28:02.980030; actual Ant parent callback27218 arrived00:28:04.020395. This proves distinct reviewer artifact and handback, not helper endorsement of its code verdict.

Maintained v3 actor e4a2080f wrote `research/zcode/REV-RECOVERY-ROUND-RECORD-C3098.md` at00:28:04.502435, 2,450 bytes/SHA-256e499001941fefabfd391579f13a6197a2f6df321ba60534e3a38c05d9704c4da. Store transition00:28:12 is completed-awaiting-review, reason task-units sibling unit exit0. Both exact units are now collected/not-found: default ExecMainStatus0 on those missing units is not used as independent terminal proof. Existing stdout remains bound to actor CID and includes a success/result marker; whole final-provider semantics were not inferred from the marker alone. No current ACTIVE worker is inferred from the now-ended task. Head owns result acceptance and the next useful successor.

## Addendum — loopback publication metadata

Read-only Git object comparison of claimed main2016f679323795f7878dda0f8f476cb321ff1045 and recovery12a38ffbfd3a4695e4d3e6139658844f78370852 establishes the following byte metadata. Four implementation/receipt artifacts and the separate independent review are counted separately; no code review or ancestry conclusion is implied. Cross-head next-task custody remains pending until genuine ACK.

- `research/antigravity/spikes/bus_win35_loopback/adapter.py`: main 15405 bytes/SHA-256 `5637cf8c16e6e59c6e7838714512d7c0dcce2fe6c59e9be09e1ab6355a08ce85`; identical recovery bytes: True.
- `research/antigravity/spikes/bus_win35_loopback/client.sh`: main 3508 bytes/SHA-256 `3e69b73aacb86baa39d6db39c3108bb8e22e513cb45d54a51dfea9789a276be1`; identical recovery bytes: True.
- `research/antigravity/spikes/bus_win35_loopback/test_loopback_spike.py`: main 15627 bytes/SHA-256 `4b4cb37dea8961b413ebde85078a273374a9cdfe6eb6786db1380157969fff7c`; identical recovery bytes: True.
- `research/antigravity/recovery/RECEIPT-BUS-WIN35-LOOPBACK-SPIKE-20261007.md`: main 9938 bytes/SHA-256 `b0e2a8fff948e2fb0b9a0e74f0ad41fe11565907774e1e74ae1ee9c8fea742fc`; identical recovery bytes: True.
- `research/antigravity/reviews/REV-BUS-WIN35-NONSSH-LOOPBACK-SPIKE-20261007.md`: main 16286 bytes/SHA-256 `50b3d25f2453489f00f5bba0b8a4178938bd3ea726e68436f0120307ca46b8c8`; identical recovery bytes: True.
