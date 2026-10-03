# artifacts-spike WORKLOG — zc-artifacts-1

Executor: zc-artifacts-1 (ZCode/zcodex, warm path), parent session claude-principal (b3a92dd0).
Date: 2026-10-03, Europe/Berlin.
Worktree: /home/alexey/git/agent-branches-artifacts (branch proto/artifacts-spike, from origin/proto/l1-scaffold @ 3e9983b).
Scope: artifacts-spike/ only, plus one repo-root addition — `.githooks/pre-commit` (3 lines, added at
32bf65c as this worktree's commit hook; nothing pre-existing was overwritten). No Worker deploys. No
resources beyond namespace `agent-branches-dev`
and repos `demo-canonical`, `demo-agent-1`, `demo-agent-2` (left in place, tiny, for the next step).
Billing gate: Workers Paid confirmed; ops/storage billed from Oct 14 — keep total ops < 100 (target ~20),
repos each < a few KB.

## Identity (`a whoami --json`, full, 2026-10-03)

```json
{
  "schema_version": 1,
  "id": "14c7b83e-8a52-4754-a9c5-eee20de8bb36",
  "workspace": "/home/alexey/git/cloudflare-agent-git",
  "tag": "zc-artifacts-1",
  "engine": "shell",
  "parent_session": "b3a92dd0-a17e-4a62-940f-eb3b829393f6",
  "command": [
    "bash",
    "-lc",
    "cd /home/alexey/git/cloudflare-agent-git && ZCODE_WARM=1 timeout 60m zcodex exec --skip-git-repo-check \"$(cat .local/claude/ZC-ART1.md)\" > .local/claude/zc-art1.log 2>&1; echo \"RUN_EXIT=$?\" >> .local/claude/zc-art1.log"
  ],
  "cwd": "/home/alexey/git/cloudflare-agent-git",
  "env": {},
  "env_unset": [],
  "limits": {
    "memory_bytes": 1572864000
  },
  "history_bytes": 4194304,
  "created_at_ms": 1791046211862,
  "updated_at_ms": 1791046214802,
  "last_activity_ms": 1791046212009,
  "reported_state": "working",
  "reported_state_at_ms": 1791046214802,
  "phase": "running",
  "worker_pid": 4193971,
  "workload_pid": 4193974,
  "worker_cgroup": "/user.slice/user-1000.slice/session-8287.scope",
  "workload_cgroup": "/user.slice/user-1000.slice/user@1000.service/app.slice/aplexer-workload-14c7b83e-8a52-4754-a9c5-eee20de8bb36.scope",
  "containment_cgroup": "/sys/fs/cgroup/user.slice/user@1000.service/app.slice/aplexer-workload-14c7b83e-8a52-4754-a9c5-eee20de8bb36.scope",
  "containment_cgroup_identity": {
    "boot_id": "edbec548-453f-4111-b38e-e7c16d12aa93",
    "cgroup_namespace_device": 4,
    "cgroup_namespace_inode": 4026531835,
    "mount_namespace_device": 4,
    "mount_namespace_inode": 4026531841,
    "cgroup_mount_id": 33,
    "cgroup_root_device": 28,
    "cgroup_root_inode": 1
  },
  "containment_empty": false,
  "socket_path": "/run/user/1000/aplexer/sessions/14c7b83e-8a52-4754-a9c5-eee20de8bb36/control.sock",
  "history_path": "/home/alexey/.local/state/aplexer/sessions/14c7b83e-8a52-4754-a9c5-eee20de8bb36/history.bin"
}
```

## Method

- Docs read before any write: prototype/docs-notes.md (L1's five fetched pages) plus freshly fetched
  official pages saved as prototype/docs/new-{wrangler,rest-api,authentication,git-protocol,workers-binding}.md
  (fetched 2026-10-03 from developers.cloudflare.com/artifacts, markdown endpoints).
- Only documented APIs used: Artifacts REST (`/accounts/:id/artifacts/namespaces/...`), wrangler
  `artifacts` subcommands, git smart HTTP with Bearer `http.extraHeader` (never token-in-URL).
- Credentials: CLOUDFLARE_API_TOKEN/CLOUDFLARE_ACCOUNT_ID loaded from
  ~/.config/cloudflare/agent-branches.env (0600) per command; minted repo tokens stored at
  ~/.config/cloudflare/artifacts-spike-demo.env (0600, outside every git tree). GIT_TERMINAL_PROMPT=0 always.
- Redaction — **HISTORICAL as written; superseded post-review**: all evidence passed
  artifacts-spike/redact.py before landing in RESULTS.md — at the time scoped to `art_v1_*` tokens,
  API token, account id; the real `art_v2_x_` shape forced a generalized, fail-closed redactor and a
  transcript re-redaction (0 live-token patterns). Commit gate as actually run during the spike —
  **HISTORICAL**: `git diff --cached | grep -iE 'token|secret|bearer'` (a keyword grep that fires on
  benign lines and misses a bare live token) — superseded by `artifacts-spike/precommit-secret-scan.sh`
  (redact.py's token-shape patterns over staged diffs), installed as this worktree's pre-commit hook.
- Op counting convention: 1 op = 1 wrangler invocation hitting the API, 1 REST call, or 1 git network
  command (ls-remote/clone/push). A git command is 1+ HTTP requests internally; counted as one operation.
- Latency: wall-clock ms around each command (`date +%s%3N` deltas), local curl start-to-end.

## Log

- 2026-10-03: identity recorded; worktree created; docs read; plan fixed (ops ledger in RESULTS.md).
- 2026-10-03: STEP 1 executed — O1–O29 (**28 evidenced ops; O29 not captured**): namespace
  agent-branches-dev, repos demo-canonical /
  demo-agent-1 / demo-agent-2, base push (ff4decd:demo-target subtree, orphan, no .harness), fork×2,
  clone+1-line-commit+push+readback MATCH, lists (REST + wrangler CLI), token lifecycle incl.
  read-scope negative test (push rejected, HTTP 400). All evidence in RESULTS.md + appendix-transcript.md.
- 2026-10-03: review caught real tokens use prefix `art_v2_x_` (docs say `art_v1_`) — redact.py
  generalized, transcript re-redacted (0 live-token patterns); still-useful exposed canonical token
  revoke reported (O29 — **not captured; see RESULTS.md**). STEP 1 verdict PASS → PLAN-L1-REAL.md
  written (STEP 2).
- Next owner/action: claude-principal reviews RESULTS.md + PLAN-L1-REAL.md; ordered next steps §6
  (binding types reconciliation first, then bootstrap script, DO smoke, event subscription spike).
