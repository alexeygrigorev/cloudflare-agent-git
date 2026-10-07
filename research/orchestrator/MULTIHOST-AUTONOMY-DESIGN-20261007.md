# Autonomous agent work across computers: design research

Authority: [human request](../../experiment/human-multihost-autonomy-design-research-20261007.txt). Recommended operating contract: [multi-host process](../../coordination/continuation-runtime/MULTIHOST-PROCESS.md). Research date7October2026; sources are primary engineering reports, specifications and documentation. This recommends a design for our constraints, not a universal best architecture or proof that it is installed.

## Finding and challenge

The strongest fit is a durable, task-driven control plane with scoped host execution and bounded agent reasoning. Keep ownership, deadlines, side-effect identity, review and continuation outside an individual model conversation. Let models choose how to solve substantive tasks; mechanical controls determine who may act and what constitutes completion. A failed or compacted conversation must not erase its obligation.

The human's process diagnosis is supported by missed handoffs, vanished intake records and reminder-dependent continuation. However, having separate components does not prove integration: secure Win35 transport, authoritative loaded store, every acceptance entry point, epoch enforcement and absent-root recovery still need actual proof. More instructions cannot replace missing controls. Conversely, installing another orchestration framework would not automatically fix process adoption.

## Primary evidence and limits

| Source | Evidence or mechanism | Adaptation and limitation |
|---|---|---|
| [Anthropic: Building effective agents](https://www.anthropic.com/engineering/building-effective-agents) | Composable workflows, dynamic orchestrator-workers and evaluator-optimizer patterns; choose complexity by measured benefit | Heads decompose uncertain tasks; deterministic admission/acceptance gates surround them. More agents are not automatically better. The2024 article itself points to newer harness work; it is a pattern reference, not current platform installation advice. |
| [Anthropic: Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) | Incremental tasks, environment setup and durable artifacts bridge separate context windows | Each successor gets verified source, acceptance checklist, progress and next action. Compaction alone is not recovery. The example is application development, not multi-host consensus or universal autonomy. |
| [Anthropic: Harness design for long-running application development](https://www.anthropic.com/engineering/harness-design-long-running-apps) | Planner/generator/evaluator roles, structured handoffs and component-by-component evaluation | Use head/implementer/distinct reviewer with bounded repair loops; stress-test whether each control helps. Do not adopt a fixed three-agent cap or treat reported application examples as guarantees for our providers. |
| [Microsoft Research: Magentic-One](https://www.microsoft.com/en-us/research/articles/magentic-one-a-generalist-multi-agent-system-for-solving-complex-tasks/) | Separate task plan/facts/guesses from progress/assignments; replan when progress stalls | Distinguish confirmed cause from hypothesis, compare current evidence to plan, change route after bounded stagnation. Its model orchestrator and benchmark results do not provide our durable custody, host fencing or failover guarantees. |
| [Anthropic: Scaling Managed Agents](https://www.anthropic.com/engineering/managed-agents) | Separates durable session history, harness and execution environment; context can be reconstructed from stored events | Keep task/event/context references durable and execution host replaceable. Borrow separation, not its hosted service; no new purchase/platform migration. Protect credentials through scoped local execution, not transcripts. |
| [Temporal: Tasks](https://docs.temporal.io/tasks) and [worker performance](https://docs.temporal.io/develop/worker-performance) | Workers retrieve queued work; scheduled and started events differ; slots/polling affect throughput | Outbound host executors claim compatible owned tasks and report actual first action. Queue depth is not worker activity. Reuse maintained launcher/supervisor; no Temporal deployment is required. |
| [A2A specification](https://a2a-protocol.org/latest/specification/) | Explicit task lifecycle, artifacts, task retrieval/streams and authenticated asynchronous updates | Adapt stable task/context IDs, artifact references and separate protocol state. Behind-NAT hosts can use outbound access to existing authenticated infrastructure; do not assume inbound webhook reachability. Protocol COMPLETED does not mean independent semantic acceptance, and a task protocol is not a durable scheduler. Pin a reviewed specification version if compatibility is implemented. |
| [Kubernetes Leases](https://kubernetes.io/docs/concepts/architecture/leases/) | Node presence and leader-election coordination are distinct lease uses | Separate host liveness from useful task progress and role custody. Lease expiry alone cannot fence a paused writer; target-side epoch checks remain essential. Borrow semantics without installing Kubernetes. |
| [Raft paper](https://raft.github.io/raft.pdf) | Majority election/commit supports consistent replicated logs across failure | A two-voter system requires both for majority; it cannot tolerate one lost voter and keep that quorum. Our inference: prefer one explicit authority with protected host execution initially; do not claim automatic two-host highly available authority. A third voter/store is a later justified decision, not an authorized new service here. |
| [Anthropic: Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents) | Evaluate environment outcome, trajectories and repeated trials rather than the agent's success narrative | Test actual artifacts, independent acceptance and successor action across faults. Record all failures, intervention counts and denominators. Self-reported success or one happy-path run is insufficient. |

Existing [request-outcome research](REQUEST-OUTCOME-RESEARCH-20261007.md) supplies additional primary evidence on transactional outbox, idempotent retries, fencing, timeouts and SRE objectives. Those mechanisms remain necessary below the reasoning layer.

## Architecture comparison

| Design | Benefits | Failure modes/cost | Fit for this project |
|---|---|---|---|
| One long-lived root conversation | Simple context and direction | Root exit/context loss stops work; human must rescue; serial dispatch/review bottleneck | Human interface and oversight only, not runtime authority |
| Central durable task authority, workers on multiple hosts | One task history, explicit claims/review, easy dedup and audit; outbound worker access | Authority outage limits new shared claims; needs persistence, recovery and fencing | Best immediate substrate; declare availability limits and allow pre-authorized disjoint local work |
| Hierarchical heads with durable shared task contracts | Scales decomposition/review across existing products; local host fit | Unreceived handoffs, central principal dependency and hidden head queues | Best reasoning/ownership topology when head-independent obligations and recovery are enforced |
| Peer-to-peer agent mesh | Flexible discovery and local autonomy | Conflicting writers, unclear integration authority, duplicate effects, expensive reconciliation | Useful research/read-only peers; avoid shared mutable execution without authority/fencing |
| Federated host-local queues plus eventual merge | Disjoint local work survives disconnected hosts | Duplicate assignment/integration, stale quota reservations, merge conflicts | Conditional fallback for explicitly leased isolated work; never two offline canonical writers |
| Full durable workflow framework or consensus cluster | Mature failure machinery and replication | New deployment/operations/cost/migration; adapters and semantics still required | Reference/future option only after smallest maintained implementation is falsified |

These are reasoned tradeoffs, not measured comparative benchmark rankings. Combine the second and third rows: one durable authority for obligations, existing product heads for decomposition, and local maintained executors for useful work.

## Process decisions that change behavior

1. Durable obligations survive model turns and host restarts. Completion creates review; acceptance creates continuation; delivery remains owned until shown to the human.
2. Capability and health matching are explicit. Never dispatch based on host name, a stale catalog or a presumed free promotion. Reserve shared account capacity once across hosts.
3. Handoffs carry compact reconstructable context and exact evidence. Do not copy a live model session or secrets as if that transfers identity/authority.
4. Separate transport delivery, read ACK, scope acceptance, first action, terminal artifact, independent review, integration and human delivery. Each can fail independently.
5. Disconnects have a declared policy. Continue only already scoped disjoint work within verifiable gates; no new shared lease or integration from stale state. Reconnect reconciles exact cursor/intent/outcomes before retry or transfer.
6. Recover a role with current identity and fenced exclusive custody, not by launching another named agent. Keep human drafts and old histories recoverable.
7. Tune parallelism and plan length by accepted throughput, review delay, failure recovery and account constraints. Fifty useful concurrent workers remains a target, not an excuse for duplicate work or fixed splits.
8. Repeated human reminders and manual rescues are defects with owners and evidence, not the process's normal control loop.

## Current project evidence and executed response

Principal semantic adoption ACK `01a114e4-91f7-7443-adce-c99fe4bc248d` adopts the request-state obligations as an operating pilot and challenges5/10/15-minute defaults. It proposes event-driven work plus <=60-second due checks in the existing supervisor; installed enforcement and exact head deadlines remain open. It corrected a moving-time mailbox filter to fixed-start/unread-ID reconciliation after missing pending instructions. These are adopted process/diagnosis steps, not a deployment receipt.

During this research the two root intake tasks previously observed in live279-row TASKS were absent after the checkout moved to `b736b61`; the file returned to277 rows before this research intake was appended. The responsible write/sync path is unknown. Root recovered the exact two missing records from maintained private metrics snapshots, appended only those through the existing guarded writer and lock, preserved every current row, and recorded native recovery coordination. Result:280 canonical rows including this research intake. Served refresh and permanent writer/checkout prevention require separate verification. This is why every writer and repository-sync path must preserve runtime obligations; a guard helper alone is insufficient.

## Acceptance experiment

Use an actual existing intake-linked task split into disjoint Win35 and Hetzner artifacts, then a distinct reviewer and integration through the owning head. Confirm first actions, immutable outcomes and exact current ownership. Run repeated completion→review→acceptance→next first-action cycles without desktop nudges. Inject worker loss, reviewer loss, host disconnect/reconnect, principal absence, duplicate envelope, lost effect receipt, stale generation and tracker-source checkout. Require no lost request/duplicate writer, safe protected states, actual recovery and human delivery. An offline authority must produce explicit limited operation, not invented availability.

Success measures: independently accepted outcomes per elapsed time, intervention-free eligible cycles, owner/start/review/delivery latency, recovery-to-resumed-action time, request-loss/duplicate-effect count, queue/review age, tracker freshness/availability and useful actor coverage. Show per-repo SHA commits as supporting activity; never optimize commit/token volume alone. Report trial count/windows/coverage/failures and accepted maximum concurrency. Small-cycle autonomy and scale50 are separate acceptance gates.
