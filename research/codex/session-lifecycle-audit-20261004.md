# Idle-session lifecycle audit — 4 October 2026

Read-only delegate audit. No session launch, kill, pane input, identity override, inbox ACK or message-bus operation performed. This report is a recommendation, not evidence of closures or owner agreement.

## Evidence and interpretation

Initial private source: `.local/codex-capacity-recovery/session-audit-1358.json` (70 native session records, captured by principal). The actual file timestamp is 13:56 Berlin; its filename is not a trustworthy capture time. The audit compared `coordination/TEAM-REGISTRY.json`, `coordination/TASKS.json`, published reports and fresh native `aplexer capture <UUID> --screen --plain` outputs. Snapshot `running` means process/session state, not productive execution. Frequent recent timestamps on old ZCode panes are redraw/observation evidence, not completed new work.

**Retention warning:** source `/home/alexey/git/aplexer/src/config/schema.rs` lines 81–90 says `keep_exited` defaults false and natural exit or `a kill` removes record and history. `/home/alexey/git/aplexer/src/worker/lifecycle.rs` lines 486–548 conditions successful removal on no fatal error, empty containment, no OOM and `!keep_exited`. Protocol sibling `src/worker/hub.rs` lines 373–382 explicitly skips final history/screen flush on proven cleanup. This is source inspection, not a verified correspondence between current dirty checkout and installed binary. Preserve private native record, history bytes and terminal capture before any close; do not publish raw logs. Retain ordinary worktrees, branches and provider conversations. Process stopping and history deletion must be separate operator intentions.

## Strong completed-worker closure candidates

Each snapshot row was running/alive, reported idle. Each fresh screen showed completed work and an empty composer. Recheck immediately before closure and reconcile owner queue; never treat this report as perpetual readiness.

| Native UUID / tag | Workspace | Concrete terminal/artifact evidence | Recommendation |
|---|---|---|---|
| `f0bb98e2-c2c8-4c6e-ad91-94e7b2876678` / zcode-auth-reads | `/home/alexey/git/agent-branches-auth-reads` | Registry completed `2302d70`; terminal full auth matrix, 30 Node/91 Vitest/16 sidecar results; explicitly “No further owned work assigned — standing by” | Stop after archive; completed implementation, no stated remaining task |
| `72528de0-c1c1-46c7-915d-f7552af927fd` / zcode-l2-client | `/home/alexey/git/agent-branches-l2-client` | Terminal SDK 15/15 +18 regressions, completion `01a1042d`, edit declaration released; initial registry e882b17 superseded by further work | Stop after archive; completed SDK correction |
| `bfa644c6-1ab6-4769-a12e-3f283cbaa566` / zcode-webhook-auth | `/home/alexey/git/agent-branches-webhook` | Published head reports `1658d54`; terminal strict retention tests 49/49,91/91,16/16; work leave, inbox empty, clean tree | Stop after archive; no remaining owned work on pane |
| `3104eb21-6fc5-420f-85fb-0148fd58878f` / zcode-sdk-adopt | `/home/alexey/git/agent-branches-sdk-adoption` | Actual terminal `cbf72e2` matches origin; 20/20; work declaration released; explicitly all C1499/C1509/C1515/C1518/C1532 complete | Stop after archive; idle waiting for hypothetical future assignment is not retention reason |
| `6a5cc1f8-4a96-4426-90b5-15f1e568ca14` / muse-reviewer-radar | `/home/alexey/git/agent-branches-l3-bench` | Fresh terminal independent review complete ACCEPT; report `research/antigravity/reviews/REV-RADAR-BENCH-203DD41.md`, negative cases disclosed | Stop after archive; report remains available without live review pane |
| `45995169-c259-41d2-b9af-a03da7c9665f` / sb-reviewer-sdk | `/home/alexey/git/agent-branches-l2-client` | Fresh terminal ACCEPT, 15/15 +9 adversarial probes; report committed `5eff85c`; notified head, declaration released | Stop after archive; completed independent review |
| `2738157e-cf52-490b-9c12-df1fa7b88a84` / sb-reviewer-adoption | `/home/alexey/git/agent-branches-adopt` | Fresh terminal review finished REQUEST_CHANGES; report `REV-FORK-ADOPTION-FCD7985.md` preserved; later head `1658d54` addresses review. Terminal records plaintext-token scratch issue | Stop after archive and head confirmation remediation ownership exists; unresolved defect does not require this completed reviewer to remain open |
| `06a6e276-18f5-4abe-b66e-aee30d4e91a4` / ui | `/home/alexey/git/cloudflare-agent-git` | Fresh terminal completed signup CSS `61de6e7`, rendered412/1280, notified publication, edit declaration released, empty composer | Conditional stop after archive if no explicit human UI retention; publication head owns integration |

## Do not classify as completed merely from idle

| Native UUID / tag | Workspace | Remaining evidence/dependency | Action |
|---|---|---|---|
| `37e342aa-25e8-4ff8-b479-e6612f867fc6` / muse-reviewer-webhook | `/home/alexey/git/agent-branches-webhook` | Terminal ends “backend temporarily overloaded” after source reads; registry review f3f06d2 running. No completed verdict shown | Head transfers/cancels stale review against obsolete pin, then archive/close; do not count failure as accepted review |
| `31436338-ef83-4187-9593-a50cb7d46d45` / zcode-a14-gate | `/home/alexey/git/agent-branches-adopt` | Latest visible terminal completed f6e5c22 gate. Registry later integration assignment cancelled to prevent duplicate writer; historical task rows conflict | Strong closure candidate after head confirms cancellation covers all new ownership; preserve report, do not revive cancelled writer |
| `2f838a7e-bd66-4d4a-9417-384d43c7e2a7` / zcode-metrics-repro | `/home/alexey/git/cloudflare-agent-git` | Fresh startup pane untouched, reported state None; held-notready assignment transferred to alternative metrics worker, delivered/reviewed later | Explicitly cancel stale pending original, archive/close. Startup empty is not native promptready |
| `96a4693f-2fa6-4a5f-a67f-9c251d847645` / ad-independent-reviewer | `/home/alexey/git/agent-dashboard` | Recent AD-R1 ownership/first action; native snapshot idle cannot prove verdict received/integrated | Keep until dashboard head reconciles current review and continuation |
| `fa49c91e-913a-46f4-b3c7-cdaef14eeb0f` / ad-frontend-exec | `/home/alexey/git/agent-dashboard` | AD-F1 current owned frontend task, first-tool evidence; idle alone not acceptance | Head checks actual result and integration, close once independently accepted or transferred |
| `82f06339-353c-4c21-84aa-01e57c7b040f` / ad-backend-exec | `/home/alexey/git/agent-dashboard` | AD-B1 registered running, waiting native state; repair/AD-R2 acceptance pending | Preserve until head checkpoint; inspect waiting reason, no blind pane input |
| `76619348-0102-4c04-a03b-3a14d8891d27` / quota-launcher-core-2 | `/home/alexey/git/agent-quota-launcher` | Reported working; current product owned executor | Keep; no stop based on stale timing |

The registry contains historical running and completed aliases for reused UUIDs and current TASKS has no exact references to the old worker UUIDs above. Reconcile by native identity plus latest real completion/assignment, not tag spelling or old registry status.

## Sessions absent on subsequent fresh read

Fresh native captures returned **“no matching session”** for `54b13484-5651-4492-9f9c-7956ef71466d` muse-ui-auth; `0e11d6e4-ea48-4795-8d49-e732940c5c84` muse-radar-bench; `4abc725c-b6ef-4ae6-af9c-978c31cdf151` zcode-recovery-test; `5df4e39f-f173-4fe1-890e-2e43e903b159` zcode-shortlist-gate; `0d04303a-34d6-49ef-bcc7-3ebd971f5491` readiness-recovery-executor; `ab8ad22c-5f03-472d-b414-cebc81870159` muse-reviewer-auth-ui. They existed in initial snapshot. This audit did not stop them and does not establish who stopped them, whether teardown succeeded, or whether histories were archived. Principal should reconcile actual closure receipts and archives rather than rerun kill blindly. Old recovery/shortlist UUIDs had historical pending tasks; removal does not prove their tasks complete.

## Retain with explicit purpose

Retain genuine principal `93cf28f2`, interactive integration/head `46fdb644`, publication head `088a2387`, dashboard head `c7a75f76`, launcher head `6be4c247`, coordination head `81e8010c`: cross-project monitoring/integration/dispatch responsibilities. Retain experiment-metrics `6be74ef3`, experiment-supervision `3038209d`, quota platform coordinator `fd00445b`, quota sidecar `7f611faa` as services, not model-worker utilization. Retain desktop interface `79ffb8c7`; unrelated workspace sessions are out of scope. Old grok-head `d85e5cd8`, ZCode head `64049aa2` and exiting principal-snapshot-recovery `5d47d025` require owner reconciliation before retention/closure; old head-role is not sufficient reason to stay open indefinitely if its queue is reassigned. Never submit protected human drafts, including stopped Claude conversation.

## Native feature intake

Recurring manual work should become an explicit lifecycle feature: close completed executor while archiving private history/terminal/native ownership receipts; show why a head/service remains retained; expire abandoned startup assignments with transfer evidence; remove live worker slot without erasing durable agent mailbox identity. Session lifecycle and mailbox/agent lifecycle are distinct. The proposed independent public message-bus project can retain routing/ACK/task identity for headless executors without requiring terminal sessions. Prove no lost pending work, no head/service surprise termination, protected drafts unchanged, and history restore before enabling automatic cleanup.
