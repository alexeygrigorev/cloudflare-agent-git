# Enforcing team roles and interaction obligations

Authority: [human steering](../../experiment/human-team-interaction-enforcement-20261007.txt), [role contract](../ROLE-CONTRACT.md), [operating model](../OPERATING-MODEL.md), [team registry](../TEAM-REGISTRY.json). Read [request process](REQUEST-TO-OUTCOME.md) and [multi-host process](MULTIHOST-PROCESS.md). **Current status: selective source controls, no demonstrated comprehensive production enforcement.** This is a concrete implementation/acceptance contract, not a new team, policy service or granted edit-scope claim.

## Diagnosis

Rules describe who should do what, but the inspected normal tool paths do not consistently reject actions that violate them. The registry's initial/historical mappings and yesterday's update do not establish genuine current head custody. Reading registry fields to route notifications is not checking permission to dispatch, mutate, review or accept a task.

There are two different enforcement problems: disallowed actions must be denied at the actual operation boundary; required interactions must become durable obligations with owners, deadlines and recovery. A permission gate cannot make a silent head follow up, and a reminder cannot prevent self-review or a stale writer.

## Source evidence, not installed claims

| Inspected path | Existing control | Missing proof/control |
|---|---|---|
| `scripts/delivery/tasks_guard.py` | CAS, IDs/history preservation, atomic locked writer | No full trusted role/team/current-custody/parent/scope/epoch permission gate; all production and checkout writers must use it |
| `scripts/supervision/service.py` | Reads registry teams/projects and resolves routing; readiness/send checks | Routing metadata is not current action authorization; comprehensive due obligations and role checks not established |
| `scripts/supervision/terminal_consumer.py` | Optional session membership and matching invocation/session/tag; distinct reviewer check | No comprehensive role/team/parent/scope-ACK/epoch validation. `expected_owner` is optional and inspected ingest path does not supply it |
| Launcher `launcher/consumer_fencing.py` | Admission and runtime epoch validation helpers | Inspected ordinary launcher CLI/watch/task-unit caller search found no established invocation outside this module; helper existence is not coverage |
| Launcher `launcher/review_receipt.py` and CLI acceptance | Pinned distinct-review validator exists in explicit validation routes | Inspected ordinary `accept` calls store acceptance directly; every acceptance entry point needs the same validation |
| AgentBus `coordination/bus.py`, CLI | Token/project/recipient checks and optional parent-token registration | Authentication/project isolation do not prove team-role action permission, real delegation relationship or current scope custody |
| ROLE-CONTRACT/OPERATING-MODEL startup and interactions | Detailed role boundaries/read receipts/handoff/continuation requirements | Primarily process text; real loaded gate coverage, interaction deadlines and recovery acceptance remain unproved |

The audit is read-only and ran no product tests or deployments. Results refer to inspected source, not necessarily loaded processes. Current protected owners must review exact pins and ordinary callers independently before changing runtime behavior.

## Trusted operation contract

Each consequential operation must present a trusted actor binding plus resource-specific authority: actual native/enrolled identity, host/session/generation, role/team/real parent, request/task/attempt, current scope ACK/lease epoch, allowed action/resource/edit scope, policy version and evidence. Validate identity from the bound process/enrollment, not a caller-supplied role label, environment alias or borrowed sender ID. A parent's scope does not automatically grant its child every permission.

Required rule: allow an action only when current verified identity, delegated scope, resource ownership, valid epoch and operation prerequisites authorize it. Missing/contradictory/expired evidence denies the affected action and creates an owned recovery obligation. Recheck at dispatch, write and integration time; a launch-time check alone cannot fence later stale activity. Keep read-only discovery and independently authorized useful work available.

This design follows [OWASP authorization guidance](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html): apply default denial and check each request rather than relying on one guarded UI. [NIST SP800-162](https://csrc.nist.gov/pubs/sp/800/162/upd2/final) supports checking actor, resource, requested operation and current environmental attributes. Our adaptation is a small shared validator in existing tools, not a mandate to install an IAM framework.

## Operation matrix

| Role | Authorized process actions within received scope | Required denied boundary |
|---|---|---|
| Root | Capture intake, research/process docs, monitor, bounded recovery, authorized local tasks/browser capability and human delivery | No inherited product edit-scope claim, routine personal product QA/release bottleneck or borrowed principal identity |
| Principal | Plan priorities, assign scoped work through heads, monitor/challenge outcomes, coordinate cross-team handoffs and administrative tracker updates | No routine product implementation or personal product-code review; no automatic transfer of protected head leases |
| Head | Decompose tasks, delegate/register actual children, choose eligible routes, accept distinct review, integrate within edit-scope claim and own refill/recovery | No self-review, fabricated workers, unreceived peer scope, duplicate writer or default sole implementation replacing its team |
| Executor | Implement/test assigned task, produce pinned result and hand it back | No own-result acceptance, reviewer identity, peer task mutation, principal mailbox or undelegated paths |
| Independent reviewer | Inspect pinned candidate, execute relevant checks and return independent verdict | No candidate mutation, own-output review, another actor's receipt or unpinned artifact acceptance |
| Supervisor/collector | Perform specifically configured mechanical transitions, due checks, routing and observations under service authority | No model verdict, fabricated role/custody/readiness, automatic source-main permission or silent overwrite |

Authority comes from current human instruction and genuine scoped handoffs. Later explicit human overrides are recorded and bounded; an LLM cannot manufacture an exception. Do not add routine principal approval for every permitted operation. Once a valid scope is accepted, the existing maintained path should permit it automatically under fresh gates.

## Interaction obligations

| Event | Persistent obligation and current owner | Completion evidence |
|---|---|---|
| Assignment | Sender retains custody until genuine recipient scope ACK; then receiving head/executor owns first action | Original envelope/cursor, received semantic scope and actual next tool/action |
| Delegation | Head records actual child/parent, team, task, paths, admission and due; checks launch/progress | Genuine child identity and task-bound first action; names/PIDs alone insufficient |
| Worker terminal | Head routes a pinned independent review and continues other useful owned work | Distinct reviewer action/verdict; terminal result does not close the request |
| Review rejection | Head/executor owns bounded repair and new pinned review | Executed correction, independent recheck and resumed work |
| Acceptance | Integration and useful successor obligations are retained separately | Exact accepted revision, permitted integration, next useful first action |
| Dependency/stall/failure | Current recovery owner diagnoses and acts, or arranges received scoped handoff | Confirmed cause vs hypothesis, action already executed/result, verification/resume, next owner/dependency/due |
| Principal/head absence | Existing reviewed fenced backup custody, preserving envelopes/history and protected states | Exclusive current epoch, real successor ACK and useful continuation; never timeout alone |
| Human outcome/report | Root retains delivery obligation | Accepted result shown, or verified published URL and brief summary under existing publication gates |

Apply task-specific adopted deadlines and event-driven due scans in the existing supervisor. Proposed5/10/15-minute defaults and <=60s scans remain distinct from observed installed timers. Peer challenges/mutual checks are recorded substantive obligations at agreed checkpoints, not token-burning automated chatter. Required startup read receipts bind policy digest and actual tool access; they prove access, not comprehension or compliance by themselves.

## Repair routing and acceptance

Principal coordinates current owner ACKs and canonical task mappings. Extend existing C2710/guard reconciliation for identity/transition writer coverage; QL fencing/acceptance/refill lanes for normal launcher callers; Ant C3110 for actual readiness/epoch/due/recovery; Bus C3120 for scoped cross-host action authority; existing Dashboard/collector for violations and obligation age. Cross-product edit-scope claims remain protected. This mapping is proposed scope until owners accept; the root intake task remains open through actual coordination and outcomes.

Separate implementer and reviewer through existing heads. Require a permission matrix exercised on actual ordinary entry points: direct CLI/API bypass, stale or fabricated role/parent, unACKed scope, wrong team/project/paths, old epoch, self-review, mutated artifact, invalid transition and source checkout dropping obligations. Preserve positive legitimate delegation and parallel work, protected busy/draft/unknown negatives, independent review and recovery with principal/root absent. Record exact source/installed/config/store pins, loaded controls, actor/evidence and verdict; source tests alone do not establish runtime enforcement.

## Enforcement boundary

These gates can enforce operations that pass through the maintained tools. Agents with unrestricted access as the same operating-system user can bypass them via shell/file writes; documenting roles cannot prevent that. Record bypass coverage explicitly. Where current authorization permits, heads should restrict consequential effects to scoped execution/tool interfaces and task workspaces; broader host permission changes require an owned reviewed plan, not an unapproved global lockdown. Track any remaining direct-shell boundary as an unresolved control, not claim universal prevention.

Measure denied unauthorized actions, missing obligations, unreceived handoffs, stale owners, failed review/refill, time to actual recovery and accepted outcomes. Missing monitoring coverage stays unknown. A registry, a reading checklist or an added policy document cannot be called enforced until every relevant normal entry point and the declared bypass boundary are accounted for and independently accepted.
