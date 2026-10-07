# GitHub task tracker

The human decided on 7 October 2026: “let's use github as a task tracker - have a subagent move all the tasks there with proper tags”. The later instruction controls routing: “each project will have a separate task tracker. the team will be reponsible for owning it. the principal will be reponsible for the high-level taks and it's tasks will be in this repo”. Use public, ordinary GitHub issues, without GitHub Projects or additional authentication scopes. Push authorized documentation directly to main; no PR is required for this administrative migration.

## Destinations and ownership

| Scope | Verified public issue repository | Accountable team |
| --- | --- | --- |
| Agent Branches | [alexeygrigorev/agent-branches](https://github.com/alexeygrigorev/agent-branches/issues) | Branches team |
| Agent Dashboard | [alexeygrigorev/agent-dashboard](https://github.com/alexeygrigorev/agent-dashboard/issues) | Dashboard team |
| Agent Quota Launcher | [alexeygrigorev/agent-quota-launcher](https://github.com/alexeygrigorev/agent-quota-launcher/issues) | Launcher team |
| Agent Coordination | [alexeygrigorev/agent-coordination](https://github.com/alexeygrigorev/agent-coordination/issues) | Coordination team |
| Agent Bus | [PocketShell-io/agent-bus](https://github.com/PocketShell-io/agent-bus/issues) | Bus team |
| Principal oversight, cross-project dependencies and research | [alexeygrigorev/cloudflare-agent-git](https://github.com/alexeygrigorev/cloudflare-agent-git/issues) | Principals |

Git remotes and GitHub visibility metadata were checked; Launcher uses its `github` remote. An issue assignment does not grant a source lease or prove a head accepted ownership. Ambiguous historical scope needs reconciliation, not an invented product owner. Link principal dependency issues to product issues rather than copying the same executable task across trackers.

## Everyday use

```sh
gh issue list --repo OWNER/REPO --state open --label project:PROJECT
gh issue create --repo OWNER/REPO --title 'Concrete task outcome' --body-file task.md --label project:PROJECT,type:feature,status:queued,priority:unspecified
gh issue edit NUMBER --repo OWNER/REPO --add-label status:in-progress --remove-label status:queued
gh issue comment NUMBER --repo OWNER/REPO --body-file outcome.md
gh issue close NUMBER --repo OWNER/REPO --reason completed
gh issue reopen NUMBER --repo OWNER/REPO
```

Before claiming work, record current owner/lease, owned paths, dependencies and checkpoint using the supported coordination mechanism. Current aplexer claims remain in effect; Agent Bus replaces them only when its actual supported API is accepted. Heads request external executors through the maintained Agent Quota Launcher, verify first useful action and terminal artifact, obtain distinct review of the exact immutable pin, repair negative verdicts, integrate and continue with the next useful task. An issue labelled running or ready is not admission, execution or capacity evidence.

Close new tasks only after the required outcome and review evidence exists. Include source/artifact/review digests and integration or runtime proof where the contract requires it. Completed-awaiting-review remains open. Reopen failed acceptance instead of concealing it. Preserve the original deadline, missed checks, failures and changed scope in the issue history.

## Labels

Migration provisions these labels in each destination as needed:

- `project:agent-branches`, `project:agent-dashboard`, `project:agent-quota-launcher`, `project:agent-coordination`, `project:agent-bus`; principal scopes also use `project:portfolio`, `project:publication`, `project:continuation-runtime` and `project:infrastructure`.
- `type:feature`, `type:review`, `type:recovery`, `type:operations`, `type:documentation`.
- `status:queued`, `status:in-progress`, `status:review`, `status:blocked`, `status:legacy-closed`.
- `priority:p0` maps explicit critical priority; `priority:p1` maps explicit high priority; `priority:unspecified` preserves missing priority.
- `migration:legacy-task`, `evidence:needs-audit` and, for historical closed declarations, `closure:legacy-record`.

Project and type classification describe routing, not fresh ownership acceptance. Keep the stable legacy marker when editing or transferring an issue.

## Migration and statistics

Retain TASKS.json and DELIVERY-BACKLOG.json as original snapshots; creating issues does not silently cut over installed readers, collectors or services. The migration manifest maps stable legacy IDs to destination issue URLs. Each body carries `tracker-migration:v1 legacy-id=...`; reruns reuse that marker and never create another issue for the same ID. Backlog references are reconciled against the unique task union.

Public issue bodies contain sanitized task identity and outcome contract, not raw operational bodies, credentials, host configuration, transcripts or private authentication. Keep detailed provenance and beforeimages private. Historical closed declarations are labelled `closure:legacy-record` and `evidence:needs-audit`; their migration closure is not a newly accepted result. Unknown historical completion timestamps remain unknown.

Daily reports show created/open/accepted-resolved counts per project and overall, plus a short accepted closed-task overview. Separate migration-created issues and administrative legacy closures from genuine work completed in the reporting window. Deduplicate by legacy task ID; report duplicates, cancellations and reopenings separately. Active agents require actual model action evidence, commits require unique SHAs, and unknown usage remains unknown. Put statistics inside the report, with links to source issues and evidence.

## Synchronous native /goal activation

The human requested documentation of the synchronous control mechanism: “you can set goals by sending the sync message”. An inbox message containing `/goal` does not activate a native goal.

The authorized session owner first verifies the current session/tag and a genuinely empty, idle command boundary with no protected human draft or menu. Use the guarded session path, for example:

```sh
aplexer message send --to CURRENT_TAG --pane --raw --or-inbox '/goal Concrete bounded outcome'
```

`--raw` preserves slash-command interpretation. Inspect the actual delivery result and then the native goal-active indicator. Inbox fallback, NOTREADY, delivery alone or a quoted `/goal` is not activation. Defer at a busy or draft-protected boundary; never use an unguarded send to bypass readiness. Preserve existing work and the original queued message. The administrative migration helper does not send commands to a pane.

At this documentation checkpoint, the Claude head has a protected draft and native goal activation is unverified. Native goals complement an independently surviving continuation guardian; they do not prove recovery after head death. See [HEAD-TASK-LOOP](continuation-runtime/HEAD-TASK-LOOP.md) and [Continuation Runtime](continuation-runtime/README.md).
