# What to read, and why

Use this map to make a decision, not to reread the experiment's history. Current task state and received owner evidence outrank old snapshots. Latest explicit human steering outranks earlier defaults.

| Document | Why it is needed | When to consult it |
|---|---|---|
| GitHub issues; legacy TASKS.json; TEAM-REGISTRY.json | Find the obligation, due checkpoint and genuine current owner. Registry labels alone do not prove custody or activity. | Every check: select actionable/due tasks and their owners; do not dump the whole ledger. GitHub issues are the trackers (per project, team-owned; principal high-level tasks in this repository); TASKS.json is a legacy ledger being migrated. |
| [ROLE-CONTRACT.md](ROLE-CONTRACT.md) | Decide who may execute, review, recover or release, and whose handoff is required. | Startup; role/custody change; authority uncertainty. Recurring checks verify the current compact contract. |
| [OPERATING-MODEL.md](OPERATING-MODEL.md) | Decide the next operation after completion, failure or a dependency. | Startup and changes; stalled flow or cross-team handoff. |
| [USER-STEERING.md](USER-STEERING.md) | Establish current goals and explicit overrides without replaying old instructions. | Every check and new human instruction; follow linked verbatim sources when wording matters. |
| [RESOURCE-POLICY.md](RESOURCE-POLICY.md) | Decide whether a proposed launch/recovery is admitted. | Every check and before dispatch; fetch fresh measurements, never reuse sample balances. |
| [SCALE50-RECOVERY-PLAN.md](SCALE50-RECOVERY-PLAN.md) | Compare the five repair streams and due commitments to target 50. | Every existing 30-minute check while the target is unresolved. |
| [REQUEST-TO-OUTCOME.md](continuation-runtime/REQUEST-TO-OUTCOME.md) | Identify which transition failed and the recovery obligation. | Every check; drill into a missing ACK/action/review/delivery/continuation. |
| [ENFORCEMENT.md](continuation-runtime/ENFORCEMENT.md) | Determine what proof a control still owes. | Every check for changed/affected gates; before accepting deployment or autonomy claims. |
| [COMPREHENSIVE-DESIGN.md](continuation-runtime/COMPREHENSIVE-DESIGN.md) | Human review of the overall design and later article brief. | Design review/iteration; not routine status polling. |
| [Tracker selection](../research/orchestrator/TASK-TRACKER-SELECTION-20261007.md) | Choose and pilot a usable tracker. | Tracker selection, migration and cutover. |
| METRICS.md / TEAM-INTERACTION-ENFORCEMENT.md / HEAD-TASK-LOOP.md | Exact metric semantics, operation gates or maintained external-executor loop. | Only the relevant measurement, gate or dispatch/review question. |
| Historical reports, verbatim intakes, source audits | Establish provenance, disputed cause or exact earlier decision. | A specific investigation; never treat archived deadlines/identities as current. |

## The check

1. Read fresh outcomes and actionable task/owner state. Verify current recipient and evidence cutoff.
2. Choose three consequential gaps; diagnose and act through existing received owners. If the previous remedy produced no action, change it based on evidence.
3. Record actual result, task/owner, next action/due, verification and durable trigger. Delivery or a promised fix is not execution.
4. Show accepted results/reports and meaningful recovery or missed commitments. Keep unchanged non-actionable state quiet; preserve the explicitly requested unresolved50 checkpoint.

Read current compact policies; consult detailed history only to answer a concrete question. Do not append incident narratives to operating documents or automation prompts. Preserve history in tasks, dated reports and version control.
