# Scale-50 recovery plan and half-hour follow-through

Authority: the human accepted the repair proposal on 6 October 2026 and requested documentation and follow-through at every existing 30-minute coordinator check. Verbatim instruction: `experiment/human-scale50-solution-followthrough-20261006.txt`.

This is the operational plan. Analysis outputs are evidence, not unanimous consensus or accepted product implementation. The target remains **50 distinct concurrently active useful task workers**, including genuine implementation/review harness subagents. Principals, heads acting only as coordinators, services, controllers, idle, queued and completed actors do not count. Historical milestones are dated observations, never current fleet state. Current coverage gaps remain unknown.

## Repair streams

| Stream | Required action | Existing canonical tasks | Acceptance evidence |
|---|---|---|---|
| Running configuration and store | Reconcile the existing producers and task stores, identify authoritative state, load reviewed settings, preserve other histories, correct task-local cwd/TMPDIR and timeout mismatches; prevent duplicate cleanup producers | scale50-A-dispatch-repair | Exact loaded source/configuration/store; a useful real task completes under intended settings; independent acceptance; preserved recovery history |
| Safe communication and continuation | Repair genuine readiness inputs, current recipient custody, generation fencing, durable pending delivery and completion callbacks through the existing supervisor | scale50-12, scale50-21 | Fresh generation-bound readiness; busy/draft/unknown negative cases remain blocked; actual owner receives and consumes completion; recoverable acknowledged handoff |
| Executable backlog and refill | Maintain current owner ACKs, substantive independent goals, isolated scopes, reviewers and dependency contracts; refill disjoint useful work without waiting for desktop | scale50-B-ready-allocation, scale50-D-dispatch-refill | Ready count backed by executable contracts; real completion → distinct acceptance → next useful model first action; unrelated work proceeds while dependent review remains gated |
| Measured provider capacity and stages | Use the maintained launcher with fresh quotas, health and shared occupancy; stage useful concurrent execution through 10, 25 and 50 and replenish ready reserve | scale50-C-capacity-stages, scale50-06 | Timestamped actual actors, first actions/current progress, provider breakdown, failures, coverage, accepted outputs and repeated continuation; no invented fixed provider split |
| Truthful current state and accountability | Reconcile actor/task/provider/session/invocation/generation and terminal state; regenerate current views and show unknowns; keep recovery tasks usable | scale50-E-roster-accountability, scale50-31 | Current useful-execution evidence, dedup and terminal reconciliation, stale/future/PID-reuse negatives, explicit measurement scope; historical snapshots do not remain current |

Principals coordinate portfolio dependencies and current head custody. Heads own dispatch, implementation, separate review, acceptance, integration and refill. Desktop checks coordinate follow-through; desktop does not become the scheduler, product reviewer or release gate. Repair the existing supervisor/controller path before adding anything; no duplicate watchers, monitors, teams or writers.

Every repair row needs a current genuine owner ACK, concrete next action, dependency, due checkpoint and acceptance criterion in `coordination/TASKS.json`. Preserve superseded owners and failed receipts as history. The role named in the table is not itself an ownership ACK. Missing/stale ownership is an actionable coordination problem that the principal must resolve.

## Problem report: actions already taken

A blocker-only report is insufficient. Each problem or missed metric must include:

1. **Problem and impact:** canonical task ID; target versus timestamped actual; measurement coverage; confirmed cause versus hypothesis.
2. **Owner:** genuine current owner and affected task/team, with acknowledged custody.
3. **Executed steps:** diagnosis, repair, safe workaround, alternative route or handoff already attempted; relevant pinned evidence and failed attempts retained.
4. **Result:** what happened, independent verification status, and whether useful work resumed. A plan or passing source test is not runtime recovery.
5. **Next step:** named owner, dependency and explicit due checkpoint, acceptance evidence and continuation/recovery trigger.
6. **Independent work:** what useful eligible work continued while this dependency was being resolved.

If safe attempted recovery still fails, report that failure truthfully with these fields; do not fabricate resolution or bypass authority. Escalate only genuine missing authority/access or material human decisions after bounded authorized mitigation. Routine repair does not wait for a human or desktop check.

Suggested compact report:

> Task | target / actual / time / coverage | problem and confirmed cause or hypothesis | owner ACK | actions already taken + evidence | result / independent review / resumed work | next action + owner + due checkpoint | durable trigger

## Existing 30-minute coordinator check

Reuse `cloudflare-git-competition-orchestration`, ACTIVE every 30 minutes in desktop chat `01a11004-f49b-7ee1-a01c-49d31e8c7231`. Do not create another automation. Follow `coordination/ROLE-CONTRACT.md` and current governance.

At each check:

- Read this plan, current tracker/registry and fresh genuine returned principal/head outcomes. Verify current recipients before messaging.
- Compare each repair stream and its last due checkpoint with actual returned evidence. Distinguish delivered request, ownership ACK, first useful action, implementation, separate acceptance, loaded runtime and repeat continuation.
- Request or relay current deduplicated useful-worker count/50, coverage, executable ready reserve, accepted output, and the problem-report fields above. Never reuse historical counts or claim a ready label proves executable work.
- For a miss, incomplete problem-only report, stale ownership or missing evidence, coordinate the current principal/head to perform bounded mitigation or an acknowledged handoff, record it in the existing tracker and return executed steps/results and the next checkpoint. Do not redispatch already owned work or duplicate a service.
- Continue existing useful work and verify the next durable remote trigger. Communication delivery is not execution or acceptance; unknown remains unknown.
- Notify the human of meaningful progress, missed checkpoints with concrete corrective action, failures, recoveries or required decisions. Do not flood the human with unchanged state. An unresolved target with missing current evidence must be stated honestly when providing its requested checkpoint report.

The 30-minute check is accountability and coordination, not a prerequisite for remote progress. Remote event-driven completion/review/failure handling must keep work flowing between checks. Existing daily standup, publication and report-delivery obligations retain their ownership and schedules.

## Retained constraints and rejected remedies

Apply current `RESOURCE-POLICY.md` and later human steering. Preserve genuine identity, private histories, ordinary Git recovery, per-process containment, fresh provider quota gates, projected disk/scratch growth, financial limits and Rust/build holds. The initiative-specific RAM override remains; memory ceilings are not reservations. ZAI's shared occupancy ceiling is not guaranteed free slots or a global worker cap. The scale coordination helper is GPT-6 Luna at max effort, as explicitly requested; it is not a counted useful worker.

Do not deliver to an unknown composer on timeout, transfer stale readiness across generations, bypass disk admission for supposedly read-only model work, remove dependency acceptance/independent review, infer worker death from transcript timestamps, or treat PID/transcript recency alone as proof of current useful execution. The exact October 5 head-loss cause and any unsupported capacity extrapolation remain qualified until independently evidenced.

The five analysts supplied critiques and model-authored responses that corrected several initial claims. Exhaustive successful revised-input reads were verified for the two Gemini analysts; the three ZAI response input records include unsupported Read calls and require supported-read corroboration. Preserve that provenance limitation rather than claim unanimous receipt-backed consensus. The operational fixes proceed through owned implementation and independent review without waiting for forced research unanimity.
