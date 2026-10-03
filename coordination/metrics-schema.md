# Agent operations metrics schema

Schemas are version 1. Public registries contain intended ownership and sanitized work descriptions; runtime observations and native provider usage stay private.

`coordination/TEAM-REGISTRY.json`:

```json
{"schema_version":1,"updated_at":"ISO8601","teams":[{"id":"a06","name":"Change-story review","head_tag":"grok-head","principal_tags":["codex-principal"],"agents":[{"tag":"grok-head","role":"head","session_id":"full UUID","workspace":"/absolute/workspace","mode":"interactive"}]}]}
```

Roles `principal`, `head`, `executor`, `subagent` are counted as agents. `service`, `observer`, `writer`, `scribe` are helper roles excluded from executor/agent totals. A missing or unknown role is reported separately. The collector accepts an optional top-level `agents` list for shared oversight. Teams reflect explicit registry ownership, not the launcher's `parent_session`: launching another head does not make its team the launcher's team.

Exact registered session ID wins if live. Otherwise a unique live same-workspace tag is selected and labeled as a fallback. Multiple live tag matches are ambiguous and not silently selected. Missing/dead agents stay visible. Live unregistered experiment-workspace sessions are listed under `unregistered`; unrelated workspaces are ignored unless explicitly registered.

`coordination/TASKS.json`:

```json
{"schema_version":1,"tasks":[{"id":"A06-01","team_id":"a06","owner_tag":"grok-head","status":"ready","updated_at":"ISO8601","evidence_paths":["research/grok/result.md"],"blocked_on":[],"next_action":"Evaluate prospective comparison","reviewer_tag":"muse-reviewer","acceptance_status":"pending"}]}
```

Statuses: `queued`, `ready`, `running`, `review`, `blocked`, `done`, `cancelled`. All task metadata is supplied by owners/principals and is not verified merely by registration. Keep status current; store actual output paths and independent acceptance evidence. A completed turn is not automatically a done project. A blocker needs an owner, dependencies, next action, and useful independent work where available.

Private observations `.local/metrics/latest.json` include timestamp, aggregated counts, per-team counts, selected session identity/resolution, genuine `/proc` liveness excluding zombies, hook state/age, task links, file metadata, native usage observations, host load/free disk, errors and explicit coverage limits. Hook working is distinct from PID live and from useful progress. Stale hook flags use a five-minute threshold; timestamp freshness never authorizes pane delivery or overrides a protected draft. `reported_state_at_ms` is preferred; absent that, activity time is a explicitly labeled proxy.

Private history is sampled every minute. Token observations are deduplicated by native source/conversation ID. Usage/cost fields absent at source remain null. Native Codex cumulative totals can include history before the observer existed; exporter subtracts the first observed total to report the observation interval separately. Nested native subagents need their own exact conversation identity; they are not inferred from process count or parent cumulative tokens. Quota remaining is a separate resource signal, never a token count/cost estimate.

The private dashboard binds 127.0.0.1:8766 and is accessed through an SSH tunnel. Do not deploy `.local/metrics`, raw transcripts, private provider results, or this internal dashboard data to the public journal. Public reports may include deliberately reviewed aggregate findings with scope and caveats.


Additional private fields: `observation` contains the first observation timestamp, distinct conversation baselines/latest counters/deltas, sampled task-state durations and newly observed transitions; `quota` contains cached actual account windows and errors; `aggregate.roles` separates principals/heads/executors/subagents. `reported_idle`, `stale_hook`, `state_unknown`, `fresh_hook_working` and `longest_observed_idle_seconds` are operational observations. `task-transitions.jsonl` preserves raw status transitions with `start_before_observer: unknown` for the initial sighting. History is compressed in verified owned chunks without deleting samples, with a retention manifest and 256 MiB ceiling. Owner metadata may be appended with `record_usage.py` using actual cumulative counters and stable provider event IDs; it is labeled unverified and does not replace available direct native telemetry. No OpenCode/Grok/Gemini token adapter is claimed merely because a process exists.

Exporter evidence coverage records distinct observed registered files, missing paths and unsupported directories. Missing-only or unregistered evidence is null, not zero accepted outcomes. Archive rotations verify SHA256 and length of original versus decompressed content before unlinking the metrics-owned original; manifest hashes remain available and failed pending archives preserve source data.
