# Completed-session metrics review

Reviewed 2026-10-03T19:42:50.204931+00:00, source [8102d4d](https://github.com/alexeygrigorev/cloudflare-agent-git/commit/8102d4d). Codex read-only review; ZCode executor implemented and Ant integrated. ACCEPT for the bounded attribution correction. This is not a complete metrics audit or a provider billing measurement.

The initial implementation recovered counters but accepted mismatched disk identities, could resolve an ambiguous live tag through disk fallback, and could treat a reused saved PID as live. C1417 required negative cases. Genuine worker replies 01a10343-5978 and 01a10343-5a6a report the same corrected output; both ACKed, applied once.

Current source validates exact saved session id and registered workspace, removes the persisted workload PID, applies disk fallback only to missing identities, and leaves ambiguous live tags unresolved. Saved rollouts read bounded head metadata and tail counters, distinguish native conversation ids from aplexer ids, and label mismatched attribution unknown. Native/rollout records for one conversation contribute the maximum counter once.

The author reports 43 passing checks, including wrong identity/workspace, reused PID, ambiguous live tag, large rollout metadata, mismatch and dedup fixtures. Principal inspected those source/test cases without re-executing the whole suite. Actual private latest snapshot at19:39:40 has no collector errors and recovers zc-readme native conversation01a102fd-1120 to1,225,751 cumulative tokens. That counter includes1,105,472 cached-input tokens already included in input; it is not an additional cache total or billed cost.

Owner reports eight recovered outer rollout rows and29→24 unknown-token records. Conversation totals can include earlier history and do not establish experiment expenditure, campaign eligibility or warm child usage. The latest metrics executor and independent UI reviewer still have null usage until their exact telemetry is registered; missing coverage remains unknown.

Ant owns current registry updates, pinned safe service reload, two actual new collection cycles and the next useful delegated product task. This review does not convert a service PID, registered worker count or accepted instrumentation patch into product benefit.
