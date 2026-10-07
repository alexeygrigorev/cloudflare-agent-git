# Choose a usable tracker

7 October 2026. **Recommendation: GitHub Issues + one private cross-product Project**, with operational issues in private storage. No migration or new access granted yet.

**Why read this:** choose the task interface and agree a pilot/cutover. Routine checks need filtered actionable tasks; this selection report is not a status ledger.

## What it must support

| Requirement | Record/view |
|---|---|
| Preserve every human ask | Parent issue with original source/date/acceptance; linked tasks or constraint/supersession |
| Received responsibility | Current head, actual owner ACK and recovery owner; account assignee is not agent identity |
| Progress and deadlines | Next action, exactUTC due, first tool and latest useful evidence; date-only board fields are insufficient for minute deadlines |
| Dependencies and recovery | Sub-issues/blocking links; executed diagnosis/repair/result and next owner/due |
| Independent acceptance/delivery | Exact artifact/reviewer receipt, integration/release and human-visible result |
| Continuation | Persistent successor/repair obligation and actual next first action |

Views: **Needs action now**, Human requests, Executable ready, Execution, Review/delivery and Outcomes by product. Each check queries consequential overdue/unowned/stalled/recovery gaps rather than reading hundreds of records. The maintained adapter computes ACK/action age and exact dues; do not claim native board dates enforce them.

Actual284-row audit found nonempty due_checkpoint59 and next_trigger14, alongside other uneven fields. These are recorded-field coverage, not proof that all remaining tasks lack semantic equivalents. Reconcile before migration; importing old labels as accepted facts would preserve the process defect.

## Compared options

| Tracker | Fit / decision |
|---|---|
| GitHub Issues+Projects | Saved views, custom fields, issue dependencies/hierarchy, code links, API/CLI and existing account. Best initial fit; resolve Projects permission and private operational repository. |
| Linear | Good UI/API; free250issues/2teams below284records and four separately owned products. Consider if an existing paid workspace removes this constraint. |
| Plane | API/self-hosting; additional PostgreSQL/Redis/RabbitMQ/storage/application operations. Consider only if self-hosting is required. |
| New custom dashboard/database | Tailored queries but recreates UI/history/permissions/availability work. Prefer established task interface. |

Existing gh repository reads succeed; Project query fails for missing read:project. Existing product repositories are public: a private Project does not make their issues private. Keep operational actor details/private handoff evidence in private storage; no secrets/transcripts in issues. No purchases or broad credential changes are implied.

## Pilot and cutover

1. Principal obtains existing integration/dashboard owner and distinct reviewer ACK, scope/task/due; resolve appropriate scoped Project access and private operational storage.
2. Prepare per-ID migration manifest preserving history/unknowns and source cutoff. Configure the six views. Do not create duplicate execution tasks.
3. Pilot five existing obligations: launcher-store authority, standup delivery, physicalWin35 acceptance, scale recovery and team gates. Demonstrate both-host query/update plus capture→ACK→action→repair→distinct review→acceptance→delivery→successor.
4. Test duplicates, concurrent writes, offline/API failure, stale ownership and missing review. Verify a readable human board and coordinator filtered queries.
5. Reconcile in-flight deltas and allIDs at an acknowledged safe checkpoint, verify export/restore, then switch maintained writers/readers/checkup prompt together. Until then TASKS.json is canonical; afterwards export/backup only. No permanent two writable authorities.

A board does not enforce scope/epoch/quota/review. The maintained launcher/Bus/supervisor must validate consequential operations; direct manual closure is audited/reconciled and cannot prove accepted delivery. Avoid PR closing keywords clearing obligations before required review/delivery. Reconcile uncertain API writes by stable IDs before retry. Outage fallback is timestamped read-only plus pending intents, not another authority.

Success: checks find and recover actual gaps without human reminders, and cutover loses no request/history. Creating a board alone is not success. Agent/commit metrics remain evidence-backed instrumentation linked to tasks, not counts inferred from cards.

Sources: [GitHub Projects](https://docs.github.com/en/issues/planning-and-tracking-with-projects/learning-about-projects/about-projects), [Issues](https://docs.github.com/en/issues/tracking-your-work-with-issues/learning-about-issues/about-issues), [API/scopes](https://docs.github.com/en/issues/planning-and-tracking-with-projects/automating-your-project/using-the-api-to-manage-projects), [visibility](https://docs.github.com/en/issues/planning-and-tracking-with-projects/managing-your-project/managing-visibility-of-your-projects), [Linear pricing](https://linear.app/pricing), [Plane architecture](https://developers.plane.so/self-hosting/self-hosting-101). Verified7 October 2026; this is a workflow-fit judgment, not a benchmark.
