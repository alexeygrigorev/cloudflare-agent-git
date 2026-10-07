# Metrics

These are the things we track. Every number is measured, never estimated, and an unknown number stays unknown, not zero. The same definitions feed the dashboard, the daily report and the public site. Raw transcripts, credentials and private identifiers stay private. Public views show sanitized summaries.

## Outcome

- Resolved tasks: unique task IDs accepted in the window, counted once, at the owning head's acceptance event with a distinct review. Work awaiting review, labels, failed or cancelled attempts, duplicates and open parents do not count. Reopens are recorded separately. Show a short overview of what the resolved tasks delivered, per project.
- Tasks created: unique IDs with a real creation event in the window.
- Open tasks: unresolved IDs at a stated time, by status. Queued, in review and blocked tasks are open.
- Features done: accepted features per product.

## Founder involvement

- Founder messages: the number of messages the founder sends, per day and per week. This is the metric we minimise. Fewer messages means the team is running on its own.
- Founder reminders and manual rescues: each time the founder has to chase or rescue something. The target is zero.

## Agents

- Active agents: deduplicated useful workers with recent first-tool, progress or terminal evidence, counted against the target of 50. Heads, services, controllers, queued and ended agents are excluded. If coverage is unknown the count is unknown.
- Agents run: distinct agents by real identity with evidence of work (commits, tests, reviews), never process IDs or role names. Report a minimum and say which coverage is unknown.
- Ready reserve: accepted, executable, ready tasks, against the backlog needed to keep 50 busy.

## Activity

- Commits: unique SHAs per repository, in hourly Berlin-time buckets and over a rolling 24 hours, by committer time. Merges are counted separately and mirrors once. Commits are activity, not accepted results.
- Task transitions: age of created, executing, in review, accepted, delivered and reopened tasks. Recovery latency.
- Time: observed hook time is an observation, not productive or billable time.

## Cost and usage

- Tokens used: measured provider tokens, per product and per team, by hour. Cached input and reasoning tokens are subsets when the harness says so. Usage not measured for a harness is unknown. Known usage is a lower bound, never the total spend.
- Cost: measured cost against the USD 5 a month cloud budget. A provider's list-price estimate is not a bill.
- Provider quota: a reading of what is left in an account, never usage and never cost.

## Host

- Free disk, memory and CPU load per host, and the memory used per worker.

## Windows

- Rolling 24 hours, calendar day with its time zone, and 30 minutes. Every number shows its start, end and the time the data was read.
- Hourly history per project and per team, shown with readable charts on the dashboard and the public site.

## Where they are tracked

- Collector: `scripts/metrics/collect.py` in this repo takes a metadata-only observation of the fleet every minute and keeps the data private, in `.local/metrics/` on the host. It runs as a service on the Hetzner host.
- Private live dashboard: the collector serves it on port 8766, bound to localhost on Hetzner. Open it from your computer with `ssh -N -L 8766:127.0.0.1:8766 hetzner` and then http://127.0.0.1:8766/. It shows agents by role, task states, idle and stale counts, host load and free disk, token usage and provider quota readings.
- Agent Dashboard: the product in `~/git/agent-dashboard` (GitHub alexeygrigorev/agent-dashboard) turns those observations into the hourly history, usage accounting and accepted-feature tracking per project and per team.
- Public site: the hourly history is published as charts at https://alexeygrigorev.com/cloudflare-agent-git/history/, built by `website/history.py`. It shows sanitized summaries only.
- Tasks: counted from the GitHub issues of each project. Commits: counted from git. Founder messages: counted from the files in `_docs/founder-journal/messages/`.

