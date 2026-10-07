# Enforcement and acceptance ledger

Read [request contract](REQUEST-TO-OUTCOME.md) and [research/source audit](../../research/orchestrator/REQUEST-OUTCOME-RESEARCH-20261007.md). As of 7 October 2026 this is **partially implemented, not end-to-end enforced**. This ledger specifies what must reject, persist, recover and prove the workflow; it is not a deployment receipt.

## Controls in the maintained path

| Layer | Required mechanical enforcement | Existing evidence and gap | Accountable implementation route |
|---|---|---|---|
| Human intake/canonical tracker | One stable request, task mapping and transition evidence; all production writers use CAS/history and semantic validation | `tasks_guard.py` protects concurrent updates/history, but comprehensive caller wiring and semantic gates are unproved. Principal reported local300/published277 rows: preserve/audit lineages rather than overwrite | Principal coordinates existing tracker/guard owner and scoped reconciliation with Ant; new task IDs/owner ACKs pending |
| Assignment/delivery | Atomically persist state plus notification obligation, replay stable intent IDs and recipient dedup; ACK is a separate semantic event | Persistent outbox/receipts exist; separate JSON writes do not establish atomic transaction. Ambiguous intent needs reconciliation | Existing Bus/supervisor owners; no second messaging service |
| Launcher admission/acceptance | Authoritative loaded config/store, current owner epoch, fresh quota/reservations and first action; every acceptance API validates pinned independent review | Store state gates and review validator exist; inspected CLI acceptance bypasses validator. Reviewer string alone is insufficient | Existing QL owner retains source lease; principal arranged read-only receipt/controller audit through current Ant while QL is menu/quota protected |
| Refill | Acceptance commits an outstanding continuation obligation; failed dispatch persists recovery owner/due instead of disappearing into successful exit | Source can print refill errors while accept returns zero; installed durable recovery unproved | QL/refill head with separate reviewer; retain existing scale50 repair rows |
| Deadlines/recovery | Check owner ACK, first action, progress, review and delivery dues; execute bounded repair/handoff and verify resumed action | Supervisor delivery/idle checks exist, but full transition deadlines are unproved | Ant `cfdc18a9-0946-4770-8aee-cf50a35bfaa7`, received C3110 scope ACK `01a11477-8f11`; task `t-supervision-idle-wake-and-failover-c3110` |
| Failover/safe readiness | Target-side epoch fencing, genuine successor custody, fail-closed unknown readiness/draft/quota; reconcile unreceipted intent | Source risks found in `failover_integration.py`; subsequent source repair `c552765` and distinct acceptance reported at07:35 Berlin. Loaded behavior and absent-root cycles still unproved | Current Ant task `t-supervision-failover-failclosed-c3110` plus existing `ROLE-FAILOVER-SUPERVISOR-ADOPTION-20261006`, `ROLE-FAILOVER-LAUNCHER-FENCING-20261006`, independent-watchers/live-acceptance rows; protect current leases |
| Win35 transport | Reviewed actual HTTPS endpoint/enrollment, device-local protected credential, outbound receiver, real useful task/reply and reconnect proof | Receiver source and separate local transport results exist; supplied URL remains a placeholder. Independent Gemini review began and found digest mismatch | Bus `3273594b-3244-45f6-87af-a6a72af7acb4`, received ACK `01a114c7-3387`; existing C3120 lane and `bus-win35-win35bootstrap-01`; desktop performs authorized bootstrap only after real reviewed inputs |
| Visibility/human delivery | Same evidence powers request latency/misses/orphans/manual interventions and report-delivery obligation | Aggregate running labels/daemon ticks are not accepted outcomes; dashboard owner adoption pending | Principal coordinates existing Dashboard/publication owners; root owns result shown to human |

No source lease is granted by this table. Listed proposed extensions require genuine current owner ACK, canonical task mapping and dated checkpoint. The principal must record these through the guarded tracker, preserving earlier misses. Timing proposals are adopted separately; do not display them as running timers.

## Coordination actually executed

- Exact human request and proposed contract delivered to current principal `93cf28f2-2872-411c-a5da-179e1b83b59f`, native envelope `01a114d3-0439-74d0-a82b-a07cc0772ee5`. Process scope/threshold adoption ACK is still pending at this ledger cutoff.
- Source risks delivered to principal and genuine Ant owner in `01a114d4-cffe` / `01a114d4-d04f`. Principal response `01a114d6-d360-7762-beee-8fcd563c4329`, 05:29:45 UTC / 07:29:45 Berlin, confirms independent Ant request `01a114d5-eabe`, asks Bus to pause only its new unreviewed wake timer pending guard review, preserves the actual reviewer/service, and records canonical CAS commit `9c9c074` with all300 local IDs preserved. The reported277 published rows remain a separate lineage investigation, not a proved overwrite culprit.
- Principal reports independent Gemini task `bus-win35-disc01-security-review-01`, native633cc548, real first action and a negative digest check. It also requested healthy Ant read-only QL coverage `01a114d4-93f0` while preserving the live protected QL head. These are executed coordination/review steps; no final transport or enforcement acceptance follows.
- Ant checkpoint `01a114db-aa1c-71d3-8fb9-bd9692f46214`, 05:35:02 UTC / 07:35:02 Berlin, reports landed repair `c55276548ecabbfeb63684779186752af731b347`, actual task `t-supervision-failover-failclosed-c3110`, four targeted and54 service tests passing, and distinct reviewer `bff4faca-da21-4077-808f-2aee6422a592` accepting the pinned repair. The source commit is present in the fetched repository. Ant reports None-state refusal, contradiction/draft/menu checks, fresh quota and mandatory send idempotency. This is a meaningful executed source repair and reported independent source acceptance, not proof that every running process loaded it or that useful failover cycles succeeded. Ant also acknowledges scoped QL read-only and C2710 ledger-reconciliation handoffs.

## Release proof, not just source proof

For each control retain reviewed commit/artifact hash, exact installed binary/module/config/store path, loaded version evidence, test actor/generation/epoch, terminal outcome and independent acceptance. On-disk edits or a restart alone are insufficient. Compare all active writers and entry points; a guarded helper cannot enforce callers that bypass it.

Required acceptance cases, delegated through the existing heads and independent reviewers:

1. Reconcile every known human ask to a canonical task, completed evidence or explicit supersession; missing rows fail intake coverage.
2. Crash after assignment commit before send: restart recovers one logical obligation. Duplicate delivery does not duplicate execution; changed payload with same intent ID is rejected.
3. Owner ACK without first action and stalled execution trigger actual bounded diagnosis/handoff; preserve the miss and demonstrate resumed useful model action.
4. Expired owner, PID reuse and paused old generation cannot dispatch/integrate after a fenced successor takes custody. Busy/draft/unknown/quota-error cases remain safely held, with independent useful work continuing.
5. An external effect succeeds but receipt is lost: reconcile actual effect before retry. No blind replay of uncertain non-idempotent mutations.
6. Direct acceptance API, self-review, missing required witness and artifact changed after review are rejected; exact independent review permits only its scoped outcome.
7. Concurrent canonical writers preserve IDs/history and reject stale hashes/epochs. Reconcile the current300/277 lineage discrepancy with explicit scope and evidence, not wholesale import.
8. Forced refill failure persists a recovery obligation; repair produces the next real first action. Predecessor acceptance and continuation failure remain separately visible.
9. With desktop and principal absent, demonstrate at least two useful model completion → distinct review → accepted result → next first-action cycles; inject a recoverable failure and prove exclusive safe custody/recovery. Toy bus consumers or timer ticks fail this test.
10. Physical Win35↔Hetzner secure transport completes useful task/reply/review/continuation and survives offline/reconnect/retry with envelope dedup/cursor reconciliation, genuine identity and privacy.
11. A ready publication is proactively delivered once with verified public URL, short summary and fresh generated illustration evidence; draft readiness does not clear delivery.

Keep private fault logs/transcripts and credentials out of public Git. Publish sanitized outcomes/limits only. Existing resource and financial boundaries apply to the tests; no routine root product QA or duplicate services.

## Measurement and failure consequences

Track request-to-owner/start/accepted/delivered latency, outstanding due obligations, orphaned/stale owners, failed refill, repair-to-resumed-action time and human reminders/manual rescues. Bind measurement to request/task/generation and report window/coverage/unknowns. A drop in reminders with actual accepted useful outcomes is the success signal; fewer alerts without coverage is not.

An overdue transition produces a persistent recovery task/obligation with current owner, executed mitigation, next due and evidence. An unavailable primary activates the reviewed received backup/fencing path. Repeated misses require principal course correction and root follow-through, not another identical reminder. The contract is declared enforced only after production caller coverage, loaded release proof and the live acceptance cases above are independently accepted. Until then report the missing gate honestly and carry out the next owned implementation/repair step.
