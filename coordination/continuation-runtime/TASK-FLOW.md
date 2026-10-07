# Continuation Runtime task flow

This is a process contract alongside [AGENTS](../../AGENTS.md), [roles](../ROLE-CONTRACT.md), [operating model](../OPERATING-MODEL.md) and [canonical tasks](../TASKS.json). Current enforcement is **partial**: task contracts, actual model firsttools, terminal states and distinct reviews exist, but stale labels, multiple stores, manual acceptance and missed refill/recovery remain documented failures. Writing this contract does not prove launcher/dashboard/supervisor enforcement.

## State transitions and durable evidence

| Transition | Required evidence and owner | Hold/recovery behavior |
|---|---|---|
| Proposed→claimed | Genuine current head/worker identity and received scopeACK; substantive intake-linked goal, owned paths, immutable source, current lease epoch, reviewer contract, checkpoint and fresh admission | UnACKed proposals stay proposals. Lease/source/main silence never grants ownership |
| Claimed→executing | Maintained task/controller invocation, exact provider/model/source receipt/workspace, actual model firsttool timestamp and bounded process/resource admission | PID/queued/running label alone is not execution. Head diagnoses missing firsttool and selects verified alternative work |
| Executing→terminal awaitingreview | Actual provider terminal/artifact digest, source tree/commit, result/exit/timeout provenance, preserved logs privately, cleaned bounded owned units | Collectedunit defaultzero/partial output/head prose cannot substitute for provider success. Failed/cancelled attempts remain separate |
| Awaitingreview→independent outcome | Distinct actual reviewer identity/firsttool, pinned artifact/source digest and freely chosen verdict; negative cases and immutable review hash | Self/stale/reused/forced/automated-only review cannot be counted as independent model QA. Source-test acceptance does not prove loaded runtime |
| Accepted→resolved | Owning head accepts exact independent outcome, task’s own semantic acceptance criteria satisfied, source/publication/runtime limits explicit, durable accepted-event timestamp | completed-awaiting-review excluded. Localfixture/source-only work resolves only its bounded task, not a larger adoption/HA goal |
| Resolved→disjointrefill | Head chooses next substantive independent contract, fresh scope/admission and genuine next worker firsttool without principal/desktop taskdispatch | No arbitrary refill jobs; continue disjoint eligible useful work while a dependency or review is held |
| Failure/block→recovered | Named owner, confirmedcause vs hypothesis, executed remedy, deadline/check, independent verification and dependent-work resume event | Stale escalation to dead owner must trigger actual current-owner/custody recovery; another reminder or blocker-only final is insufficient |

Every event binds taskID, actor/session/invocation, lease epoch/current owner, occurrenceUTC/source clock, source/artifact/review digests and evidence level. Every open row names nextaction, actual owner checkpoint or explicit unknown, blocking dependency and remedy. Principal monitoring deadlines remain separate from a head’s promise. Preserve original MISSES and reopen history; do not import whole historical ledgers or backdate acceptance.

## Ownership and implementation

Ant’s received C3110 supervision scope owns its runtime repair lane. Launcher, Dashboard and publication source/integration remain with their actually acknowledged owners. Dashboard/public task-flow enforcement and metric tasks are proposed pending their genuine owners’ ACKs; this document does not extend Ant’s source lease. Heads delegate implementers and separate reviewers. Principals monitor events, dependencies and acceptance truth, not product code.

The required independent acceptance includes exact-current-owner/stale-owner/PID-reuse/generation/duplicate/cancel/reopen negatives, protected draft/busy/unknown readiness, actual terminal→distinctQA→useful successor, and verified recovery after both principal and desktop are absent. Existing services, safety gates and ordinary Git recovery remain; no duplicate scheduler.
