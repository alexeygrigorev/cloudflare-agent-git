# Cloudflare Infrastructure Cost and Operational Budget

## Primary Documentation Sources

All pricing and plan thresholds come directly from official Cloudflare documentation:
- [Cloudflare Artifacts pricing](https://developers.cloudflare.com/artifacts/platform/pricing/)
- [Cloudflare Workers pricing](https://developers.cloudflare.com/workers/platform/pricing/)
- [Cloudflare Durable Objects pricing](https://developers.cloudflare.com/durable-objects/platform/pricing/)

## Cloudflare Pricing Structure

These pricing terms govern our edge deployment architecture (Worker API gateway + SQLite-backed Durable Object coordinator + Cloudflare Artifacts binding namespace `agent-branches-dev`):

Cloudflare Artifacts pricing:
- Plan requirement: Workers Paid subscription only ($5.00/month account base).
- Included monthly allowance: 10,000 operations per month and 1 GB-month storage.
- Additional usage rates: Overages cost $0.15 per 1,000 operations and $0.50 per GB-month.
- Billing schedule: Billing for Artifacts starts on 14 October 2026 (this marks the product billing start date, not an account subscription renewal).
- Compute usage: The deployment uses no Workers AI compute or additional paid add-ons.

Workers and Durable Objects have separate pricing, including requests that return HTTP 429. Artifacts limits don't provide an aggregate invoice guarantee.

The deployment operator must measure existing shared account usage, including `agenthub`, before checking whether this entry fits the available allowance.

## Software Budget Controls

The Cloudflare adapter is designed to reserve budget before each binding or Git gateway call:
- Planned operation caps: Design enforces a limit of 200 operations per UTC day and 6,000 operations per calendar month.
- Included operations: The quota counts every binding call, including get, capability checks, polls, failed attempts, git operations, and deletes. The system persists counts before executing each call.
- Storage guardrails: Limits allow at most 4 application repositories, a cumulative upload ceiling of 16 MiB, and a request body ceiling of 256 KiB.
- Status: These controls are deployed. The live Worker reports `dailyCap=200`, `monthlyCap=6000`, `maxRepos=4`, `maxTotalBytes=16 MiB` and `maxBodyBytes=256 KiB` on its budget endpoint, and returns HTTP 429 once a cap is reached. The hard ceilings are compiled into `budget.ts`, so config vars can only lower them. Bearer requests are also rate-limited per token.

## Live deployment (13 October 2026)

- URL: https://agent-branches.cloudflare-ai-agent-de9ca0.workers.dev (Worker `agent-branches`, version `e962956f`; Durable Object `Coordinator`; Artifacts namespace `agent-branches-dev`).
- Plan: the founder confirmed Workers Paid on 13 October 2026 (USD 5.00/month base, already paid and shared with `agenthub`). Nothing was bought and the plan was not changed.
- Live smoke: the full run passed on 13 October 2026 (all 14 checks) using **60 Artifacts operations**. Earlier partial runs, which uncovered smoke-client contract mismatches that are now fixed, used 4, 4, 10 and 60 operations. Total on deploy day: 138 of the 200 daily cap and 138 of the 6,000 monthly cap. The client refuses to start without 90 ops of headroom.
- Cost estimate: the 6,000/month cap is below the 10,000 operations/month included with Artifacts, and stored data stays at or under 16 MiB, well inside the included 1 GB-month. Worker and Durable Object requests at demo volume are covered by the Workers Paid allowance. Expected extra cost is USD 0.00 on top of the USD 5.00 base. Worst case: if `agenthub` already used the whole included Artifacts allowance, this entry would add at most 6,000 x USD 0.15/1,000 = USD 0.90/month.
