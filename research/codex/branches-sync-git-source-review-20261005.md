# Principal source challenge: branches sync git candidate1e57ed3

Read-only inspection of /home/alexey/git/agent-branches/.local/scale50/wt-branches-sync at1e57ed3; no principal harness execution or product edits. HOLD integration and shared-repo dogfood until head-owned correction/negative review.

1. sync_git.py excludes forbidden paths from new staging but invokes ordinary `git commit -m`, which includes all previously staged paths. An already-staged secret or peer file can still enter the checkpoint. Claimed staged-secret verification iterates only `to_stage`, not the real index. Independent test must stage a forbidden file before command, then prove no commit/push/change of that index.
2. Failed push executes `git reset HEAD~1` without an exclusive lease or positive source/commit receipt guard. This removes the recovery checkpoint and can rewind a concurrent actor's commit. Preserve the committed checkpoint and report retryable unsynced status; no implicit reset.
3. A clean tree with existing unpushed commits returns noop instead of pushing, and absent/error remoteSHA becomes `in_sync=True`. This contradicts one-command synchronization of existing changes. Compare/query failures must remain unknown/error; clean-but-ahead must actually push non-force and verify remote.
4. After push, remote mismatch still returns status=synced/verified=false, and CLI prints [SYNCED]. Distinguish verified synchronization from push-success/unverified state and fail truthfully.
5. `git status --porcelain=v1` split-line/quote parsing corrupts filenames with spaces, quotes/newlines and renames. Use native NUL records and test exact paths. Current broad source-extension staging is not an acknowledged peer-path lease.
6. No Git flock or bounded subprocess timeouts found in initial module. Git common-dir lock should coordinate this tool's own operations across worktrees without becoming a competing product-wide lease service; preserve original index and peer actors. Existing paths/name-only secret rules are not a proof arbitrary source payloads contain no secrets.

Owner: QL recoveredhead a86056b5 delegates correction and distinct independent reviewer; Ant recoveryhead5e1abcdb canonical integration release remains required. Useful fixes supply real autonomous task inflow. Tomorrow demo remains a target, not accepted feature.
