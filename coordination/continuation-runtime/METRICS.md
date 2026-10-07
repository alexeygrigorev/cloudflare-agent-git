# Continuation Runtime metrics

The primary outcome measure is **unique accepted resolved task IDs in a stated window**, not sessions, tool calls, commits alone or running labels. Metrics are definitions and pending integrations, not measured totals or proof of current enforcement. Read [task flow](TASK-FLOW.md) and use first-party canonical events with proven custody/source/artifact/review bindings.

## Resolved-task numerator

Count each distinct taskID once when its semantic acceptance is actually satisfied and the canonical owning-head acceptance event binds a distinct reviewer/artifact digest. Select by the event’s actual accepted/resolved UTC timestamp and declared window. Exclude completed-awaiting-review, queued/starting/running labels, cancelled/failed attempts, deterministic checks mislabelled as modelreview, duplicate aliases and open parent goals merely containing a source-accepted child.

A reopened task is recorded separately and does not create a second unique ID for the same window. Show resolution events/re-resolutions separately if useful; retain failed attempts/reopen reasons. Historical closed labels with unknown acceptance timestamps stay **unknown**, never backfilled to ingestion time or now. Missing source/review/time provenance is an explicit excluded/unknown category.

## Aligned project-window report

| Metric | Definition | Required caveat/drilldown |
|---|---|---|
| Tasks created | Unique canonical IDs with genuine created-event time in window | Aliases/dedup and unknown historical creationtime separate |
| Open tasks | Point-in-time nonresolved taskIDs at stated as_of, status categories separated | Proposed, blocked, review, failed-remedy and currentowner freshness visible |
| Resolved tasks | Unique acceptedresolved IDs in window under the numerator contract | Short acceptedfeature/closedtask overview per project, source/runtime acceptance scope |
| Active agents | Current deduplicated useful executor identities backed by actual firsttools/progress/terminal events | Heads/principals/controllers/services/queues/endedexcluded, coverage and unknowns shown; timestamp not future |
| Commits | Unique actual Git SHAs in the same project/window | Authorship/remote/source-tree pin, task linkage; merge/repeatedSHA not duplicatework credit; not resolution substitute |
| Provider/outcome | Actual routed model/account evidence and useful accepted/failed/cancelled/review outcomes | Quota percentages not token/cost; unknown usage/cost staysunknown |

Use rolling24h, calendar-day with timezone, and30-minute activity windows. Label exact start/endUTC, localdisplayzone and data_as_of; compare tasks/agents/commits within the same project/window. Daily reader-facing reports retain meaningful outcome cards and include taskcreated/open/closed/resolved statistics **inside the report**, not as its title. Existing public website/dashboard integration remains head-owned with received ACK pending; no new competing edition/writer/scheduler.

Public views contain sanitized project/task summaries, timestamps, outcome explanations and intended source links. Keep raw transcripts, backend credentials, private host/device/account/actor identifiers, pending envelopes and process details private. Private drilldown may use actual task/actor/source/review records under access controls. Source of truth is linked canonical TASKS/events, not a copied second ledger.

## Proposed delivery lanes

1. Dashboard owner: bind canonical acceptance/firsttool/terminal events to project-window statistics and provenance drilldown; distinct negative QA for duplicates/reopens/unknown historic timestamps. **Ownership ACK pending**.
2. Publication owner: consume the same sanitized aggregate contract for meaningful cards and in-report per-project closedtask overview, retaining actualunknowns. **Ownership ACK pending**.
3. Launcher/supervisor owner: enforce task-transition/currentowner and durable event publication through existing tools; Ant’s current C3110 source scope covers only its acknowledged supervision lane. Cross-project source grants are not inferred.
