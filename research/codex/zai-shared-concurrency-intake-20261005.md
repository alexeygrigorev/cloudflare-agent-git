# Shared ZAI concurrency — human intake, 5 October 2026

Exact human requests relayed by the principal:

> zai is reporting rate limiting. how many zai agents are we running in parallel? check this project and projects outside to know the total

> we will use this number as the max number of concurrent sessions for zai

## Measurement and policy boundaries

The requested limit is shared across projects using the account on this host, including nonnative and headless sessions. It is not a separate allowance for each project. Count each genuine backend actor once, excluding its launcher/wrapper duplicates. Preserve unrelated work and private payloads; this intake authorizes counting and admission policy, not killing current jobs or changing unrelated services.

The principal confirmed the human-approved ceiling is **26**, the host-wide backend count first presented at 18:05:18 UTC. This fixed ceiling must not rise automatically when later launches increase occupancy. At 18:06:13 UTC the independently checked live backend total was **28**: ai-shipping-labs 12, dataops 8, lukurban.github.io 2, pocketshell 1, ZCode container contexts 5, competition 0. Fourteen zcodex frontends, including seven childless frontends, were not added as duplicate backend actors. These are observation-time counts, not current or useful ACTIVE-work claims.

Shared configuration evidence identified provider zcode/default provider zai/model glm-5.3-flash/host api.z.ai. Individual routes and active API-call totals remain unknown; six OpenCode processes were ambiguous and not asserted to be confirmed ZAI actors. Cross-machine account occupancy is unknown. Distinguish live sessions reserving rate capacity from useful ACTIVE executors: idle/retry-blocked sessions may still reserve capacity, and unknown backend state must not create assumed free slots. Remaining plan quota does not establish rate capacity.

The verified observation was two above the adopted ceiling: block new ZAI admissions and preserve existing work, without killing jobs. Fresh occupancy and atomic reservations are required before resuming admissions; do not ratchet the ceiling to 28 or treat unknown cross-machine use as zero.

## Ownership and acceptance

The proposed implementation owner is the existing QL head (750), requested through genuine principal message `01a10d3e-4b8b`; Ant head (d78) was notified through `01a10d3e-4be7`. Actual ownership ACK, independently reviewed implementation and runtime admission receipts remain pending. Principals route the outcome through the head rather than implement a governor themselves. Require atomic shared reservations, fresh host/account occupancy, release only after proven exit, bounded 429 cooldown respecting Retry-After, and eligible alternative-provider routing. Retain the Grok cutoff and all other resource, quota, identity, privacy and spending rules.

No enforcement is established by this source document. Record the final audited count with its observation time and scope, the adopted ceiling separately from measured occupancy, the head's actual ACK, exact implementation/reviewer pins, and the next runtime verification trigger. No new service, cloud spend, raw-provider bypass or termination of current jobs is authorized here.
