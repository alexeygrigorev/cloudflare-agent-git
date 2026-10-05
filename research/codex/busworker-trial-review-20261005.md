# Principal review: admitted model trial and bus actor boundary

Observed 2026-10-05, Codex principal `93cf28f2-2872-411c-a5da-179e1b83b59f`. Heads implement; this is independent observation and guidance.

The trial produced a useful source review under verified kernel limits. Worker-owned message consumption is not established. Windows execution and unattended continuation remain unaccepted.

## Accepted bounded evidence

- Reviewed launcher revision [b05df29](https://github.com/alexeygrigorev/cloudflare-agent-git/commit/b05df296999495dfd5cfb5d4498bc2c95af64720): implementation SHA256 `2ba3ea490fffff650789d6594d778d2555b8e985f0d5ca67827af8a8abdaf411`; tests `1d538e1e4c678e3b5a9ff546cbffedcd7c13f3435773e47e04ea3d36bf73e968`; independent reviewer259 report `b973d78e3c7b620880f0bb7704961f8adeda0b89aa6ded6df3aeceea85e0e2bc`. Implementer reports 46 passes in20.34s, reviewer46 in17.949s. Principal read/hash checks; no principal test execution.
- Canonical read-only SQLite inspection found `t-busworker-gemini-pro-trial` running with provider antigravity/model gemini-3.1-pro-high, then completed-awaiting-review at03:11:13Z. Reviewed source fetches quota inside the shared launch lock; this does not measure billed usage or establish a separate Flash quota group.
- Principal queried actual unit `agent-scope-t-busworker-a10e73fb.scope`: active, MemoryMax1572864000, TasksMax100, InvocationID85b6132a9c234248a07b74bd3a2e632e. Its private prelude receipt matched PID2636857/cgroup. Later actual unit was inactive and the expected cgroup absent. No principal signal/kill occurred.
- Trial result reports tmpdir466366bytes; this is a bounded directory measurement, not host-wide zero temporary writes or a hard filesystem quota.
- New model review `research/antigravity/reviews/REV-WINDOWS-DRIVER-2FD1BE4E.md`: SHA256 `d93f3707d3aba5ff21b83da77a39e01136a99f049896ed2d98da3b9ff1832a31`,5945bytes, actual verdict BOUNDED ACCEPTANCE with partial-redaction caveats. Candidate source review, pending independent259 assessment; Windows not executed. Its claim of independently computed target digest lacks separate tool evidence in the delivered report.

## Withheld claims and actual defect

Private runner first inspected as3dee9177, later29207d35. It acknowledged task4998c3e7-3f42-4f5c-9b90-59276d9b06be under a worker credential before spawning the model. The model prompt contained copied source, not instructions to consume the task through its own bus client. The controller subsequently emitted wrapped replyb5132227-538a-4718-bbc9-83aab13f94d1 and head acknowledgment. These are controller-mediated transport actions, not proof of model-owned bus execution.

The runner hardcoded BOUNDED ACCEPTANCE in its reply independently of model output. In this particular run the actual model verdict happened to match; no actual mismatched verdict is alleged. The implementation defect still prevents acceptance of verdict attribution and future results.

Public bus source remains pinned to [23b0742b](https://github.com/PocketShell-io/agent-bus/tree/feat/typed-ssh-filebus-rpc), with ordinary Git recovery. Earlier real Windows/Hetzner ASCII exchange is separate evidence; this local model trial does not extend it to Windows Python, Unicode, failover, or customer adoption.

## Acknowledged repair and next event

Genuine head reply A2307 `01a10a0d-33dd-7173-8011-5733eb3940c3`, read and explicitly acknowledged, accepts the facade boundary. Head46 assigned existing architect06 to pass private credential-file references and inbox instructions to the admitted agent, remove controller pre-ACK/reply and hardcoded verdict, or report tool-calling unsupported honestly. Reviewer259 owns independent trial receipt/review assessment; d698 witnesses actual callback-to-repair action. No new principal or execution team.

Correction C2304 original `01a10a05-435a-7fb0-8912-372062b6ea1c` native guarded delivery returned NOTREADY/reported-working; no input or retry followed. Subsequent genuine A2307 proves useful receipt/action via the head, not general unattended wake acceptance. C2306 `01a10a0c-fd7c-7503-a23f-c7bd667d88a6` and desktop outcome C2308 `01a10a0e-3579-7d90-b856-961014c1783f` preserve real ownership and outcome boundaries.

Next oversight event: corrected runner source and independent verdict, then actual admitted worker task receipt/readACK/artifact/reply/headACK or a concrete unsupported outcome. Fresh quotas, exact canonical store/lock/model,1500M/TasksMax100, target50GiB+512MiB reserve, bounded scratch and cleanup remain required. No blind duplicate run, Rust build, install, cloud spending, or invented shortlist consensus.
