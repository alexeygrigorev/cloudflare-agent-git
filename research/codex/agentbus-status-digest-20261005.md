# AgentBus status — 5 October 2026

AgentBus exists as a public sibling project at [PocketShell-io/agent-bus](https://github.com/PocketShell-io/agent-bus), with a standalone local messaging core. Complete aplexer feature parity, accepted model-agent adoption and native cross-computer recovery are separate unfinished gates.

## Verified metadata and documented scope

This documentation helper independently read Git metadata: local HEAD and actual GitHub main both equal **5ee5207e8c540b712f7bc862af8f3bf29dc6df69** (`git rev-parse HEAD` and `git ls-remote origin refs/heads/main`). [Current source pin](https://github.com/PocketShell-io/agent-bus/tree/5ee5207e8c540b712f7bc862af8f3bf29dc6df69). No product code review, tests, runtime or messaging trial was performed for this digest.

The [README](https://github.com/PocketShell-io/agent-bus/blob/5ee5207e8c540b712f7bc862af8f3bf29dc6df69/README.md) describes independent registered identities and send/receive/reply/ACK without an aplexer process/session/environment. Its blanket “implementation is starting” sentence and former head assignment are historical and need a head-owned documentation refresh. [Checkpoint](https://github.com/PocketShell-io/agent-bus/blob/5ee5207e8c540b712f7bc862af8f3bf29dc6df69/docs/checkpoint.md) reports FileBus register/send/inbox/wait/reply/ACK, fsync/flock and a headless CLI; its six-test result is an earlier local checkpoint, not current-suite or cross-host proof.

Documented commands in [C2477 report](../../research/antigravity/recovery/REPORT-BUS-MODELWORKER-C2477.md) include `bus_cli.py inbox --cred <worker-credential-file>`, `bus_cli.py ack --cred <worker-credential-file> --message-id <id>`, and `bus_cli.py reply --cred <worker-credential-file> --message-id <id> ...`. These are reported examples, not freshly executed or verified CLI instructions.

## Reported independent reviews

- [REV-BUS-CORE](https://github.com/PocketShell-io/agent-bus/blob/5ee5207e8c540b712f7bc862af8f3bf29dc6df69/reviews/REV-BUS-CORE.md): reviewer f869e27c, pin **06addf9ec875532feae40479c8e64ea11cb600db**, ACCEPT_WITH_FIXES, six tests and environment-clean local two-process exercise reported. Findings included absent separate acceptance/outcome state, unwired offline outbox and credential-file permissions. This is a historical review, not review of current HEAD.
- [REV-BUS-CORE-NEGATIVES](https://github.com/PocketShell-io/agent-bus/blob/5ee5207e8c540b712f7bc862af8f3bf29dc6df69/reviews/REV-BUS-CORE-NEGATIVES.md): independent subagent 09649355, ACCEPT, 24 tests reported; reply ownership/project scope, idempotency conflicts, durability/permissions and local child-process integration covered. Review describes a dirty working tree based on **f3295f9**; **207a93f9 is an actor/session identifier, not a source commit**. This receipt is not an exact-current-HEAD independent acceptance.
- [Principal historical trial digest](busworker-trial-review-20261005.md) records a later candidate worker-owned message/ACK/artifact/reply cycle and bounded reviewer259 findings, followed by unsafe reused-run history deletion and dispatcher admission/continuation defects. Read this as bounded historical evidence, not current unattended acceptance.

## Why the earlier done task does not close adoption

[Task tracker](../../coordination/TASKS.json) labels `agentbus-standalone-modelworker-c2477` done at 10:49:49Z, reports 11 tests, lists executor e5366811 and head Antigravity as reviewer, and has **commit:null**. Its [report](../../research/antigravity/recovery/REPORT-BUS-MODELWORKER-C2477.md) supplies local task/read-ACK/reply/replay/callback claims. It does not provide a distinct exact-pin independent reviewer or provider/model invocation and actual first-tool evidence establishing model-owned execution. “HMAC-equivalent” is report wording, not independently verified cryptographic attestation. Do not reinterpret tracker closure as accepted production adoption.

A separate later direct-provider/OpenCode trial was retracted: [principal coordination record](../../coordination/codex.md), C2578–C2584, records invalid Python stdout artifact and withdrawal of direct-provider PASS. This does not erase the earlier local transport evidence, and the earlier done label does not cure the later maintained-route/model-adoption gap.

## Head ownership and next acceptance gates

The existing resumed coordination head **8d4c026c-b1f9-4cbf-83bf-4f5f82077cab** is nominated for AgentBus responsibility. Task tracker records the AgentBus-specific offer **01a10c73-bad4** with explicit new ACK pending. Earlier coordination-role acceptance is not AgentBus custody acceptance. Principal oversight found the separate AgentBus project missing from the project registry and reports adding its pending nomination in commit **aa48b3c** (principal supplies successful push receipt; origin main subsequently advanced to peer commit **39af652** with aa48b3c preserved, not independently verified by this helper). Native delivery returned NOTREADY, and root disk was reported **49.48 GiB**, below the 50 GiB launch floor. No new ACK or running zcy lanes are asserted by this helper; activation and capacity repair remain owned next actions.

The head must acknowledge custody, reconcile the extraction/parity backlog, launch disjoint eligible zcy implementer lanes and independent reviewers, and refresh project docs. Required next outcomes are:

1. A useful sessionless model agent genuinely consumes a task using its own scoped identity, performs a real first tool/action and produces an artifact, sends a correlated result, and receives a real head ACK; exact source/actor/receipt evidence independently reviewed. Controller-mediated or hardcoded verdicts cannot substitute.
2. Reviewable integration and verified GitHub source pins; full current messaging parity/gaps documented rather than assumed from a local core.
3. Native two-computer bidirectional exchange, authenticated identities, offline retry/dedup and cursor reconciliation. Earlier real Windows/Hetzner ASCII exchange remains separately bounded evidence; it is not blanket Windows Python, Unicode, full Bus transport or unattended lifecycle acceptance.
4. Repeated useful completion-to-next-task cycles through an independently running admitted receiver, without human or principal scheduling nudges. Preserve histories, recovery, quota/resource gates and existing healthy processes.

Repo creation is completed evidence. Local decoupled messaging has documented bounded review evidence. Accepted current model-agent adoption, full extraction and autonomous cross-host operation remain unfinished until the responsible head supplies those distinct outcomes.
