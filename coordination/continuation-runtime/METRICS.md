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

## Tracker availability and human request coverage — 7 October

[Verbatim instruction](../../experiment/human-tracker-availability-agents-commits-20261007.txt), canonical task `human-tracker-availability-agents-commits-20261007`. Root recorded this task through the existing guarded atomic writer, preserving all277 prior IDs; implementation ownership/adoption is coordinated through principal and current heads, not granted by this document.

- Every known human instruction source needs a visible canonical task mapping or explicit constraint/supersession mapping with reason and linked implementation tasks. Retain exact request text/source/time, owner ACK, first action, next due, executed recovery, independent acceptance and human-delivery status. Instructions that constrain many tasks are linked policies, not fake executable jobs. Reconcile source files and conversation intake, not only filename matches; unknown mappings remain visible. Coverage numerator is reconciled sources, denominator is the enumerated known corpus with cutoff and any inaccessible conversation gaps.
- The existing private tracker is `http://127.0.0.1:8766/` through authorized host-local access/SSH forwarding. Availability must cover a usable page, task API, canonical-store identity, fresh data and a task drilldown. HTTP200 alone is not freshness or complete request coverage. Win35 access must be verified independently; desktop access is not proof of Win35 access.
- Record success/failure and latency for both UI/API and age of task/metrics snapshots. Agreed availability/freshness SLOs, failure detection and owner recovery bounds require adoption and installed evidence. Repair/reuse existing singleton restart and forwarding paths; no duplicate daemon. A durable last-known task copy plus Git recovery is the offline fallback, explicitly timestamped stale and read-only until reconciliation. Preserve writes in canonical obligations; never silently fork an offline authoritative store. Do not promise literal100% uptime.
- Show current worker/subagent ACTIVE separately from live processes and working principals/heads/services. Deduplicate host/provider/session/generation and parent-child attribution; require actual recent useful execution and exact as-of/coverage. Missing unregistered/harness/Win35 coverage keeps the fleet count unknown rather than zero. Show accepted executable READY reserve and target50 alongside current known/unknown categories.
- Count commits by repository and SHA in hourly Berlin buckets and aligned rolling24h windows. Declare canonical branch/source pin, event-time choice (Git committer timestamp for this series), merge policy and local-versus-pushed coverage. Distinguish unique non-merge source commits, merge/integration commits and accepted task results; mirror copies of one SHA count once globally. Record newly observed/reachable commits separately when timestamp rewriting/rebases affect historical buckets. A zero from one HEAD's reachable history is scoped evidence, not proof that no other branch/host committed.
- Track created/open/executing/review/accepted/delivered/reopened tasks and transition age; misses remain linked to actual recovery steps/owners/dues. Agent and commit counts are activity measures, not substitutes for accepted useful outcomes. Each metric links its source/window/coverage and recovery task when stale or missing.

Initial diagnosis: existing desktop and Hetzner tracker HTTP200; served277 rows before intake. A51-file filename scan found34 sources without literal references in served JSON, requiring semantic/register reconciliation rather than a claim34requests are absent. Collector05:36:43UTC showed4 registered live principal/head processes, zero fresh working hooks and8 unregistered live observations; useful fleet ACTIVE remains unknown. These dated observations are not current counts.

## Existing delivery lanes

1. Dashboard owner: bind canonical acceptance/firsttool/terminal events to project-window statistics and provenance drilldown; distinct negative QA for duplicates/reopens/unknown historic timestamps. **Ownership ACK pending**.
2. Publication owner: consume the same sanitized aggregate contract for meaningful cards and in-report per-project closedtask overview, retaining actualunknowns. **Ownership ACK pending**.
3. Launcher/supervisor owner: enforce task-transition/currentowner and durable event publication through existing tools; Ant’s current C3110 source scope covers only its acknowledged supervision lane. Cross-project source grants are not inferred.
