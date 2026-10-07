# Current admission and safety limits

**Why read this:** decide whether a launch, recovery or infrastructure action is allowed. Read each check and before dispatch. This is policy, not proof installed launchers enforce it. Fresh quota, occupancy, disk and actual model-route evidence are required; historical balances and process samples are not admission evidence.

## Provider routing

- Use maintained Agent Quota Launcher/common CLI and supported adapters; no ad hoc provider bypass. Heads own real implementation/review workers, independent workspaces and verified first actions. Principals/heads are interactive; workers may be headless. Follow HEAD-TASK-LOOP; built-in Claude Agent/Task is disabled for that external-worker loop.
- Preferred pool: ZCode/z.ai, Space Bunny, Muse Spark 1.3 and Gemini/Antigravity. Authorized expanded pool includes Codex GPT-6 Luna / MAX and Sonnet 5.5; verify exact model/version/route/account access, never silently substitute. Sonnet worker authorization supersedes older sparse-Claude defaults; preserve protected Claude principal. Actual Opus remains the authorized publication writer.
- Run fresh `quse PROVIDER --json` before each admission and while supervising. OpenAI Codex: refuse new execution at <=15% remaining in any available applicable window, limit-reached or unknown/error; evaluate available windows without treating an absent window as zero. Use scripts/launch-codex.sh or scripts/agent-bin/codex, including applicable harness delegation. ZCode is not OpenAI Codex.
- Grok: refuse new execution at <=5% remaining, limit-reached or unknown/error. Arrange received healthy-provider handover proactively. Do not kill productive work solely to enforce a new-launch cutoff or redeem resets/buy credits.
- Shared ZAI ceiling:26 live backend sessions, not26 per project or host. Wrappers do not add slots; idle/retry-blocked live backends retain reservations. Fresh observed occupancy plus atomic shared reservations must cover all known hosts; unknown account coverage cannot create assumed capacity. Release only on proven exit, honor429 Retry-After and use healthy alternatives. Quota is not rate capacity or free slots.
- Broader50 scale-up uses the maintained CLI only after actual dogfooding acceptance: head request → real worker first tool/artifact → distinct review → verified release/refill. Preserve useful existing work and head-owned bounded launcher repair while this gate is unresolved.

## Physical budgets

| Budget | Current rule |
|---|---|
| Root disk | Free bytes minus aggregate outstanding growth reservations minus candidate bounded growth >=20GiB. Unknown measurements/growth fail closed. |
| Cleanup warning | Below30GiB, continue otherwise eligible work and claim exactly one bounded cleanup actor per episode. Warning is not refusal. |
| Worker containment | Each actual worker independently bounded MemoryMax=1500M / TasksMax=100. A1500M head containing many workers does not provide independent containment. Preserve productive jobs. |
| RAM override | For this50-worker initiative, do not refuse dispatch on RAM estimates/MemAvailable floor. Measure RSS and preserve per-process containment and all other gates. |
| Scratch/spike | Aggregate512MiB maximum; budget actual bounded incremental growth, not a compulsory512MiB reservation per tiny job. |
| Compilation/install | Rust/build hold remains until actual preventive accounting/budget and reviewed release are proved. No blind rebuild, global installation or expansion of shared targets. |

The20GiB floor is the principal's adopted interpretation of the human's “50 is too tight” and “after30...cleanup” steering. It supersedes older50GiB references; the scoped RAM override supersedes the older10GiB free-RAM refusal only for this initiative.

Cleanup requires attributable disposable scratch/cache, no active process/write/lease, retained recovery/evidence, before/after bytes and an owner/checkpoint. Never delete existing worktrees, dirty/unmerged work, private histories, unrelated data or unknown-owner paths. Unknown ownership requires a scoped escalation, not deletion.

## Time-sensitive campaign

The GLM-5.3-Flash notice described paid Coding Plan/ZCode3.10+ eligibility,17:00–03:00Berlin during3September–7 October 2026, with final closing instant unspecified. The existing conservative rule stopped relying on free entitlement at7October's Singapore calendar boundary unless official/client evidence confirms continuation. Recheck actual terms and route before claiming eligibility; use verified ordinary allowance/alternatives otherwise. An alias or campaign label does not prove zero consumption. [Recorded source](https://docs.z.ai/devpack/notice/event-glm-5.3-flash); original verification/provenance is in this file's history.

## Financial, identity and privacy limits

Cloudflare/project cloud-service total is USD5/month INCLUDING the existing base plan. Metered allowances/alerts are not a hard cap. No agent execution on Workers/Containers/WorkersAI; execute on authorized Hetzner/user computers. Optional relay/storage remains held without actual aggregate usage and preventive overage bounds. No purchases, billing changes, model credits, new paid services or unrelated infrastructure changes.

Use genuine enrolled identity, received owned scope and safe busy/draft/unknown guards. Preserve exact pending envelopes; reconcile uncertain effects before retry. No borrowed binding, forced readiness, credential copying or unauthenticated endpoints. Dirty ~/git/aplexer/global binaries and peer work are protected; use isolated reviewed source under acknowledged lease. SSH is authorized bootstrap/recovery, not final native cross-host acceptance. Preserve ordinary Git fallback; no secrets/raw transcripts/private dashboards in public Git or reports.

Human provenance: experiment/USER-INSTRUCTIONS.md messages20/21/22/26/32/34; [RAM/count override](../experiment/human-ram-override-twentyfive-subagents-20261005.txt); [Cloudflare boundary](../experiment/human-cloudflare-budget-20261004.txt); research/codex/zai-shared-concurrency-intake-20261005.md, expanded-executor-pool-intake-20261005.md and maintained-launcher-capacity-intake-20261005.md. Current owners and measured acceptance belong in tasks, not this policy.
