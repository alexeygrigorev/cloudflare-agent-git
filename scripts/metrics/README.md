# Private experiment metrics

`python3 scripts/metrics/collect.py` takes one metadata-only observation. `--loop --serve --interval 60 --port 8766` runs the observer and a dashboard bound **only to 127.0.0.1**, with a singleton flock. This service does not dispatch workers, change agent state, overwrite drafts, or redeem quota resets.

Access from the desktop:

```text
ssh -N -L 8766:127.0.0.1:8766 hetzner
http://127.0.0.1:8766/
```

Data stays private in `.local/metrics/`: `latest.json`, dated snapshot JSONL, locks and optional exports. Files use mode 600 and directory mode 700. History uses verified gzip chunk rotations after 2 MiB and at day boundaries. All snapshot bytes are preserved; only metrics-owned uncompressed originals are replaced after original/decompressed SHA256 and byte-count verification. A retention manifest records every archive. The 256 MiB total hard cap preserves existing history and pauses new appends with a latest-snapshot error; it never deletes experimental data or existing worktrees. Compression is expected to keep a 14-day metadata-only experiment well below the cap; monitor the actual manifest, not a promise. Keep the service alive through its genuine `experiment-metrics` aplexer session. The dashboard source is public, its collected data is **not**.

```text
python3 scripts/metrics/export.py --output .local/metrics/experiment-summary.json
python3 -m unittest discover -s scripts/metrics -p 'test_metrics.py'
```

The exporter separates lifetime conversation cumulative tokens from tokens added during observation. Time is sampled hook-state time, not productive/billable time. CPU/RSS cover the workload root process only; descendants are not secretly counted as additional agents.

Useful measures: registered/live/freshness counts, per-team ownership, tasks ready/running/review/blocked/done, dependencies and next actions, registered evidence file size/mtime, partial provider token observations, observation coverage, memory/CPU metadata, disk free space and host load. Supervision status is read from `.local/supervision/status.json`. Independently accepted outcomes require task evidence/reviewer signoff; raw tokens/commits are not a productivity leaderboard.

Native Codex usage comes from the existing saved `transcript.json` binding and the latest cumulative `token_count` event in a bounded 2 MiB tail. Conversation IDs deduplicate resumed sessions. Cached input and reasoning tokens are subsets when the native harness says so, not additional tokens added to the total. If no event is observed, usage is null. Claude completed writer results may be explicitly registered using `telemetry: {type: "claude-result", path: ".local/journal/first-writer-response.json"}`. Their provider list-price cost is an estimate, **not a subscription charge/bill**. OpenCode, Grok, Gemini and native harness subagents without an exact telemetry binding remain unknown, not zero. No credentials, message contents or raw transcripts are retained.


The live dashboard separates principal/head/executor/subagent counts, reported idle, stale/unknown state and longest sampled idle. It shows CPU/RSS, host load/free GiB, raw task statuses including noncanonical values, task transition history, native input/output/cache counter breakdown, first-observed baselines and observation-interval token deltas. Provider windows are read through real `quse` calls at most every five minutes and show query errors; account quota never becomes cost or agent usage. Hook seconds are observations, not productive work.

Register missing harness usage only from actual metadata (never estimate counters):

```text
python3 scripts/metrics/record_usage.py --event-id PROVIDER_EVENT_ID --conversation-id NATIVE_ID --tag EXACT_AGENT_TAG --team-id TEAM_ID --provider PROVIDER --model MODEL --input-tokens 100 --output-tokens 20 --total-tokens 120
```

Counters must be cumulative for the exact native conversation. Duplicate stable event IDs are ignored only if metadata is identical; conflicting reuse fails. This owner-registered source is labeled as not independently verified, used only when native direct usage is missing, and keeps cost unknown. Raw prompts are forbidden. Register parent/team identity in TEAM-REGISTRY, not by assigning the launcher's whole usage to every subagent. Provider native conversation usage may include nested delegate billing; report scope to avoid treating parent and child estimates as independent bills.

Evidence export counts distinct currently observed registered files, with missing files, unsupported directory paths and out-of-scope paths reported separately. No registration or missing-only coverage yields null, not a claim of zero outcomes. Evidence counts do not establish authorship or acceptance. Archive verification hashes original and decompressed bytes before replacement; failed pending archives retain the original and are excluded from export, and the manifest retains compressed/source SHA256.

Compressed historical snapshots preserve sanitized registered evidence file metadata and the task contract: team/owner/state, next action, acceptance status/reviewer, evidence paths, dependencies, assignment acknowledgement and update time. These link historical observations to outcomes and tests without storing prompts or transcript bodies. The serialized task is owner-maintained evidence, not independently verified completion.

Live evidence cells show observed distinct file counts with coverage labels; directory-only, missing-only or unregistered evidence remains unknown. Directory paths are reported unsupported and never recursively scanned. Historical snapshots retain the same coverage labels.
