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
- Status: These controls are planned software safeguards in the prototype design, not already proven in production.

## Deployment checks

Deployment requires these checks:
- Implementation acceptance: Genuine Cloudflare Workers, SQLite-backed Durable Objects, real Cloudflare Artifacts, and runtime code caps remain pending acceptance.
- Conditional deployment: the deployment operator handles deployment conditionally from a clean GitHub clone, subject to the total $5.00/month shared account budget (including the existing Paid base shared with `agenthub`).
- Measurement status: The actual live deployment URL and real operational metrics remain unknown until the deployment operator completes live predeploy verification.
