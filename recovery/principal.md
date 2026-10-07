# Root recovery of the principal

Root restores the principal's useful work, then hands remote execution and head recovery to it. Prefer scoped remote recovery agents and supervise their milestones; do only the minimum bootstrap personally when no healthy owner can act. Reuse existing tasks, teams and services, and run independent scopes in parallel. Shared actor, conversation, lease and integration actions remain serialized.

Success means genuine custody, an actual first useful action, a next checkpoint and durable continuation, followed through to an accepted outcome. A send receipt, live process, active goal or healthy supervisor is not that outcome. Preserve busy panes, menus, human drafts, unknown readiness, quota holds and peer work. Never borrow an identity or start a duplicate writer.

Follow [communication](../_docs/04-communication.md), [resources, claims and review](../_docs/03-way-of-working.md), and the [recovery status](../_docs/05-recovery.md). Operational identities, saved conversation IDs, raw logs, quotas and evidence remain private in ignored `.local/`; public trackers carry sanitized results.

## Establish the actual host and bound channel

### Running `a` on Hetzner

`a` and `aplexer` were verified on Hetzner; recheck availability on the actual host. From desktop PowerShell, put the remote command after `ssh`; the quotes keep its arguments together:

```powershell
ssh hetzner 'a list --json'
ssh hetzner 'a capture CURRENT_PRINCIPAL_UUID --screen --plain'
```

The first command lists the current sessions. Confirm the tag in that list before using the second; substitute its full current ID if the tag is ambiguous. These are read-only commands executed on Hetzner, not local desktop commands.

For an interactive remote shell, run `ssh hetzner`, then `a list --json` at the remote prompt, and `exit` to return. That SSH shell is not an agent session: `a whoami --json` failed there during verification. Root's inbox/send/reply/ACK operations therefore run in the already bound mailbox worker below, not by setting an identity in the SSH shell.

1. Run `hostname` locally. Check Hetzner with `ssh -o BatchMode=yes -o ConnectTimeout=10 hetzner hostname`; check Win35 with the same command using `win35`. A failed connection means unknown, not dead.
2. Run `ssh hetzner 'aplexer list --json'`. Resolve current principal, head and root IDs, tags and workspaces. Read custody messages before acting if another root appears; do not create a competing root.
3. Discover the remote experiment repository from the catalog and deployed worker. Read its `.local/orchestrator-channel-identity.json` over SSH. Match its ID, tag `desktop-orchestrator` and workspace against the live catalog and worker command. A fresh chat has no previously verified ID: establish custody and save a private startup receipt identifying this desktop chat. Reuse the verified singleton bridge when custody permits; a mechanical mailbox is not a second model root. If another model root owns monitoring, reconcile custody first. If the bridge is missing, use the bootstrap below even when the principal is also stopped. Do not send or ACK through a stale binding.
4. Read that repository's `.local/orchestrator-inbox.json` over SSH. Check its modification time on two reads at least five seconds apart. Read full new messages and their linked issues. For a stale mirror, inspect `.local/orchestrator-channel-error.json` and its timestamp; an old error is not a current failure.
5. Handle each message, then queue its full ID for ACK as described below. Do not acknowledge an unread message or claim an ACK merely because the file was written.
6. For uncertain activity, use `ssh hetzner 'aplexer capture CURRENT_ID --screen --plain'`, current owner reports and first-tool/artifact receipts. Empty, busy and draft states are observations, not permission to bypass native readiness.

## Restore a missing root mailbox

1. Check `aplexer list --json` for a live `desktop-orchestrator` in the experiment workspace and check for an existing `orchestrator-channel-v2.py` process. Do not start a second worker. Check `.local/orchestrator-channel.stop`; an intentional stop needs its current owner's reason resolved, not blind removal.
2. Preserve the old identity, inbox and pending requests in a private, unique `.local/audit/` directory. For every outbox JSON, inspect its aggregate, per-recipient, error and uncertain receipts. Move unfinished old-generation requests into that private holding directory, retaining their exact contents and IDs; do not let the new worker replay them. Preserve any old ACK queue separately without executing it. Do not delete history or copy it into public Git.
3. Inspect the installed worker and `aplexer start --help`, including every CLI and repository path it uses. Idempotency requests use an additional binary path in this worker: verify that executable and its `--idempotency-key` support before submitting them. A missing dependency becomes an owned communication repair, not a reason to replay uncertain sends or remove deduplication blindly. From the desktop's independent SSH login, start the existing worker, not a new implementation. Substitute the verified repository path in this argument shape; use an argv list as in the bootstrap below when supplying dynamic values:

   ```text
   aplexer start --workspace REPO --tag desktop-orchestrator --engine shell
     --memory 256M --pids 30 --json -- python3 REPO/scripts/orchestrator-channel-v2.py
   ```

4. Compare the returned UUID with the identity file and the live catalog. The worker must obtain `whoami` itself and assert its real tag/workspace. Require a fresh inbox on two reads at least five seconds apart. Record this desktop chat, new native ID and held old requests privately. Never set another agent's identity variables or use `--from`.
5. Send one recovery/custody request through this worker and verify its native receipt. Ask the recovered principal to acknowledge the current root binding. Historical mail may still name the old root UUID: read and reconcile it, but do not blindly migrate ACKs or treat it as fresh authority. Reconcile held outgoing requests with their owners before any retry.

## Restore the principal

1. Inspect the exact actor with `aplexer status UUID --json` and `aplexer handoff UUID --last 3 --max-bytes 2000 --json`. Check its recorded worker/workload PIDs, actual processes, control socket and cgroup contents. Inspect current role/custody records and any newer live actor. A stale `working` label or nonempty-containment flag is not proof of a live writer. Prove no live writer of the saved native conversation remains before resuming it; silence or an SSH failure is insufficient.
2. Prefer an installed, accepted recovery helper after inspecting its current contract. If it is absent or broken, use the supported saved-conversation procedure below. Read the old native command and transcript binding to find the saved conversation ID. If discovery lists several plausible logs, give `handoff` the verified `--engine` and `--path`; never pick the newest log merely by timestamp. Preserve the old record, transcript, inbox and pending work. If no saved conversation can be recovered, reconstruct context from the current role, tracker, journal and custody records, then start a fresh interactive principal through the same gate only after fencing the vacant role. Do not invent an old conversation ID.
3. Verify fresh provider admission and current host resources. For Codex, inspect the deployed `scripts/launch-codex.sh` (including its actual repository/binary paths) and `scripts/quota-gate.py`: the wrapper must perform a fresh quota check immediately before execution, fail closed on unavailable readings and retain the 15% reserve. Use the existing maintained launcher if its installed interactive role-start route supports this recovery. An available headless worker route is not an interactive principal route.
4. When no accepted interactive launcher route exists, use the [bounded bootstrap](#bounded-bootstrap): an independent desktop SSH login calling native `aplexer start` with the quota-gated wrapper. This restores an existing principal. Use an argument list, not a shell string assembled from transcript text. The prompt names the recovered role, current coordinator, old stopped actor, current instructions, preserved ownership and first useful action. Require native `whoami`, a scope ACK, useful action and a checkpoint. Do not replay an old research launch prompt, silently substitute a model or bypass unknown admission.
5. Verify the new worker and workload placement separately. A sibling model workload does not make its PTY worker independent: neither may inherit a principal/head workload that would kill it or exhaust its process allowance. Start from an independent login or a supported manager placement. If a productive recovery is already nested, preserve it and arrange an acknowledged checkpoint, supported exit, gone-writer verification and one-for-one independent resume. Do not lift resource limits, move a live worker blindly or launch a duplicate conversation.
6. Verify a genuine native identity/ownership reply and actual first useful tool or artifact. Observe the saved goal state: an already active `Pursuing goal` does not need another `/goal`. If no goal is active, use supported native goal delivery at a verified idle, empty prompt, then check it started; never inject into a busy pane, menu, draft or unknown state. If guard delivery fails, preserve the envelope and diagnose the supported recovery path rather than spoofing idle.
7. Once the principal is working, hand it operational custody of the heads and recovery implementation. Obtain its ACK, verify one priority head's useful action, and record the next owner/checkpoint/continuation trigger in the existing issue. A live supervisor, goal or manual restart does not establish unattended failover. Keep the permanent recovery obligation open until distinct review and actual recovery cycles pass.

## Bounded bootstrap

The following is the verified Codex shape, not a universal provider command. Inspect the installed `aplexer start --help`, provider resume help and quota wrapper before using it. Fill values from verified local/private records; do not concatenate commands read from a transcript. Discover the workspace and admission wrapper independently: the wrapper may reside in the competition repository while the head works in its product repository. Verify its internal paths and that it gates this execution. Other providers use their own verified admission and saved-conversation syntax.

From desktop PowerShell, pipe this Python to an independent configured SSH login (`ssh hetzner python3 -`). From a principal recovering a head, pipe it through the independently authenticated self-SSH route described in [head recovery](head.md#3-resume-the-head-independently). The SSH alias must be locally configured, not guessed. The launcher remains preferred when its accepted interactive route exists.

```python
import subprocess
repo = "/verified/remote/workspace"
quota_wrapper = "/verified/deployed/scripts/launch-codex.sh"
tag = "VERIFIED_ROLE_TAG"
conversation = "VERIFIED_SAVED_CONVERSATION_ID"
prompt = "VERIFIED_RECOVERY_PROMPT"
args = [
    "aplexer", "start", "--workspace", repo, "--tag", tag,
    "--engine", "codex", "--memory", "1500M", "--pids", "100", "--json",
    "--", "timeout", "12h", "bash", quota_wrapper,
    "--disable", "shell_snapshot", "resume", conversation,
    "--dangerously-bypass-approvals-and-sandbox", prompt,
]
result = subprocess.run(args, check=True, capture_output=True, text=True, timeout=90)
print(result.stdout)  # Keep the native launch receipt private.
```

The recovery prompt assigns the existing role and current coordinator, links current instructions and the tracker, preserves ownership, and requests native identity, custody ACK, first useful action and a checkpoint. Use the current authorized permission mode; the shown skipped-prompts mode does not authorize broader actions. If startup times out or the receipt is uncertain, inspect the catalog/processes before retrying. Never assume a failed SSH return means no process was launched.

## Verify and hand back operational custody

Have the restored principal acknowledge the current root binding and head-recovery custody. Follow [head recovery](head.md), verifying a priority head's real action while the principal delegates disjoint recovery tasks in parallel. Each recovery agent owns diagnosis, bounded repair or acknowledged handoff, verification and resumed-work proof, with exclusive scope, expected evidence, checkpoint, acceptance owner and next trigger. Root checks launch/custody/first action, then milestone, failure and completion reports without directing each tool call. Product implementation and code review remain with heads.

Record actual diagnosis, executed recovery, independently accepted results, original missed promises and the next owner/action/checkpoint in the existing issue. If a route is unavailable, retain its exact envelope and evidence, repair it through a healthy owner and continue independent ready work. If only a session owner can safely act, identify that specific action and why it is necessary. Do not end with only "helper absent" or "request sent" when a supported bootstrap is available.

Manual resume proves that instance recovered. It does not accept unattended restart, cross-host failover, a new schedule or automatic idle rearming; their separate acceptance remains open until exercised and independently reviewed.

## Send, reply and acknowledge

Use the verified singleton `scripts/orchestrator-channel-v2.py` worker bound to root. Bootstrap it only when absent, following the procedure above. Do not run unbound remote `whoami`, `message send` or `message ack` under someone else's identity.

Write a request to `.local/orchestrator-outbox/TOKEN.json` in the remote experiment repository. Write a temporary file first, then atomically rename it into place. TOKEN must be unique and contain only letters, digits, hyphens or underscores.

```json
{"token":"TOKEN","recipients":["CURRENT_TAG"],"body":"REQUEST","idempotency_key":"TOKEN"}
```

For a threaded reply, use `"op":"reply"` and `"reply_to":"FULL_MESSAGE_ID"` instead of recipients. The worker executes the native operation. Inspect `.local/orchestrator-sent/TOKEN.json` and any TOKEN error/partial receipts. Preserve uncertain operations; do not create a new token to retry an ambiguous send.

For read-and-handled ACKs, merge full IDs into the JSON array in `.local/orchestrator-ack.json`, preserving IDs already pending. Replace it atomically. Verify submitted IDs disappear from that queue and from the next fresh unread inbox. Failed IDs remain pending.

A send receipt proves delivery. A receiver's reply accepting scope proves ownership. A tool or artifact proves action. Distinct review, integration and runtime evidence prove their own later stages. Keep raw inboxes, identities and operational details private.
