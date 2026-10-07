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
