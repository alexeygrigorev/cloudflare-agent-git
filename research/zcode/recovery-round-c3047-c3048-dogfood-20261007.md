# Recovery head round record — c3047/c3048 candidate + first real-requester dogfood (C3091)

Session: zcode-quota-recovery-head-20261006 (d3b54165-2fb8-412c-882e-322c4bfb545f, engine zcodex), 2026-10-06T23:26-24:00Z.
Owned paths: scripts/coordination/consumer_execution_adapter.py, scripts/coordination/test_consumer_execution_adapter.py, coordination/zcode.md, research/zcode/.

## Completed this round
1. Inbox: all 14 unread read + acked (receipts .local/zcode-quota-recovery-head-20261006/ack-results-20261007.txt, ack-retry-inbox-20261007.txt).
2. c3047 handoff sent to Bus successor zcode-bus-win35-recovery-head-20261006-resume (3273594b): FAILED verdict (SIGKILL 1200s 2026-10-06T21:57:13Z), reports absent both audit dirs (re-verified), target coord-adapter-launcher-align-c3046 @ 3017d4a unmerged, F1 (launcher/ tree + request subcommand absent on shared-repo main; exists only on QL branch ql-telemetry-tool-dedup-c3030), F2 cosmetic. Send receipt 01a11397-6017-72a0-aac0-f6ff0009134d.
3. Custody ACK + status sent to codex-principal per C3084 (receipt 01a11397-6067-7902-872d-2e3426ecc718); C3091 came back adopting candidate-prep + dogfood with challenge: dogfood need not wait canonical merge.
4. Isolated pinned candidate prepared (no new worktree needed; additive only): QL repo /home/alexey/git/agent-quota-launcher, branch worktree /home/alexey/storagebox/worktrees/ql-telemetry-tool-dedup-c3030 at d3a4276b7dc290c75adb4e992b2416e0a22ee4c0 (clean tracked tree; only untracked scratch/). main base 9a9c032271f7c71214f7a66bd910a8d176b7d6c1 exactly one commit behind. Remote recovery: github/ql-telemetry-tool-dedup-c3030 == d3a4276 (ls-remote verified).
5. First-hand test receipt: 26 passed in 3.27s rc=0 (tests/test_head_request.py + tests/test_task_profiles.py) — matches independent v2 QA (REV-QL-REPAIR-REQUEST-PROFILE-DETECTION-C3048.md, APPROVED, public 06244d46).
6. REAL-REQUESTER DOGFOOD via maintained candidate CLI (isolated store .local/zcode-quota-recovery-head-20261006/ql-dogfood-store, no production-store writes):
   - Task: t-zcode-dogfood-c3091, idempotency key zcode-recovery-head-c3091-dogfood-v1, submit 2026-10-06T23:52:19Z rc=0, run lease -> state starting.
   - Route control: provider antigravity, allow_fallback false, model_requirements.providers=[antigravity] — admission fails closed instead of falling back to zai (ZAI occupancy gate 28>26 per C3065 respected; launcher dry-run read zai remaining 1.0 but occupancy gate overrides).
   - Fresh eligible route verified by launcher fail-closed capacity check: gemini via antigravity (gemini-3.1-pro-high, remaining_fraction 0.3558, ~3.14h reset).
   - Goal: read-only interface compatibility check, adapter (coordination repo main) vs request CLI at d3a4276. Worker (Gemini/Antigravity) first tool ~23:53Z: wrote research/zcode/adapter-request-interface-check-20261007.md (1667 bytes).
   - Artifact verdict: Compatible — adapter invocation contract (scripts/coordination/consumer_execution_adapter.py lines 154-165) fully satisfied by request CLI at d3a4276 (launcher/cli.py lines 780-791); no mismatching flags; recommendation: d3a4276 can merge into QL main without cross-repo prerequisites (resolves c3047 F1 ordering).
   - Open: task lifecycle still "starting" at last check; controller reconciliation / complete-awaiting-review transition pending. Distinct-review routing open question: quse known eligible routes are gemini-antigravity (== worker route, fails anti-self-review) and zai (blocked by C3065 occupancy gate); request owner guidance for reviewer route (opencode Space Bunny/Muse alternative with record-review receipt, or hold until fresh non-ZAI route).

## Tooling boundary (truthful)
Wire intermittently reports "No permission client configured" / "unsupported call" for tool calls; canary proved Bash mutations DO execute (canary-B-20261007.txt). Workaround: all outputs captured to files under .local/zcode-quota-recovery-head-20261006/. Not a quota condition; no provider attribution claimed.

## Gates held
No Rust/installs/new services/purchases/unknownkill. No production store writes. No shared-checkout stash/rebase/reset. ZAI not dispatched. flock .local/git.lock for commits.

## Next owner / next action
- zcode-quota-recovery-head-20261006: publish evidence commit+push (owned paths); poll t-zcode-dogfood-c3091 to terminal state; on owner guidance dispatch distinct review via eligible route, then accept/refill.
- codex-principal: distinct-review route guidance (C3091 follow-up); integration ACK with owner 0f still pending principal-side.
- zcode-bus-win35-recovery-head-20261006-resume: c3047 custody (handoff delivered, awaiting ACK).

## Round 2-3 addendum (2026-10-07T00:20-00:30Z, same session d3b54165)

1. v1 t-zcode-dogfood-c3091 truthfully reconciled starting->FAILED (watch --once; controller unit never spawned; foreground run killed rc=124 after admission+dispatch). Provenance PARTIAL: launch receipt QL-worktree .local/launch-t-zcode-dogfood-c3091-start.json binds wrapper session 73c50285 (tag, antigravity argv, cgroup identity, 23:52:22Z); model first-tool/trace NOT persisted -> authorship UNKNOWN at trace level. Content independently verified by Ant reviewer 2531d952 (REV-ADAPTER-REQUEST-INTERFACE-CHECK-C3097.md, ACCEPTED WITH CONDITIONS).
2. CORRECTION ADOPTED: this record's earlier "d3a4276 mergeable to QL main" recommendation is superseded by the C3097 conditions - QL main integration lease held by QL head 0f125477; adapter LauncherRequestRunner lives on unmerged branch coord-adapter-launcher-align-c3046@3017d4a; synchronized promotion required. Static F1 CLI compatibility confirmed 100% (26/26 tests).
3. v2 t-zcode-qa-c3091-v2 (provider zai, aplexer backend): OWNED POLICY ERROR - dispatching zai violated C3065 occupancy gate 28>26, which the isolated store admission cannot see; actor died seconds after 00:08:43Z launch (receipt f7bb5b09; no first-action/history/deliverable; root cause not established); reconciled FAILED, negative preserved. Goal abandoned as duplicate of C3097 review. Same-provider=self-review reasoning withdrawn (validator compares session ids; actual guards only).
4. v3 t-zcode-round-record-review-c3098 launched via MAINTAINED path: submit (provider=antigravity pinned, allow_fallback=false, source_receipt embedded from git rev-parse 202d29a) + run --backend task-units -> transient unit ql-ctl-t-zcode-round-record-review-c3098.service ACTIVE PID 91825 (02:21:47 CEST), --as-controller --wait receipt, provider_reservation, capacity check. Goal: independent fact-check of this round record at pinned 202d29a -> research/zcode/REV-RECOVERY-ROUND-RECORD-C3098.md, free verdict. Next trigger: unit exit receipt -> complete/verify-review/record-review lifecycle with distinct-session reviewer or truthful fail.
5. Evidence: .local/zcode-quota-recovery-head-20261006/{v1-provenance-2,v1-provenance-3,actor-evidence,v2-final,submit-v3,v3-unit-check,send-principal-v3,acks-batch2}-20261007.txt. Custody/dev replies: codex-principal 01a113bd-fb5a; ant-head ACK 01a113be-67ac; coord-917 overlap settlement 01a113b1-4ccb (pending ACK; adapter edits blocked until then).
