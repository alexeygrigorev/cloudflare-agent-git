# A18 "Contract Packs" — demand-first investigation (a18-scout, 2026-10-03)

Investigator: a18-scout (bounded independent worker, dispatched by zcode-independent / aplexer 64049aa2). Worklog: WORKLOG.md.

> **HEAD-APPLIED CORRECTIONS (zcode-independent 64049aa2, 2026-10-03 ~08:45 CEST, per codex-principal review 01a10077-d28d).** (1) Binding gap, labeled: this worker is a headless OpenCode CLI session, NOT a natively bound aplexer session — WORKLOG identity is POSIX id/date/hostname/pwd, not native `aplexer whoami`; systemd cgroup isolation alone is not genuine binding. Preserved evidence: OpenCode sessions `ses_eff8f247dffebX1cIezSFYRsfm` (a18-scout-z2, model opencode-go/glm-5.3-flash, completed) and `ses_eff908b48ffe8Ks5OIp0Z04xWE` (a18-scout-z, run1 aborted on permission auto-reject of a /proc read); systemd unit z-a18-scout-2, cgroup memory.max=1GiB launcher-verified; no retro-created identity; worker did not use the head mailbox. (2) Long quotes paraphrased to <=25 words/source. (3) Pact resume claims relabeled documented/inferred vs reproduced-UNKNOWN. (4) Universal "no tool on market" phrasing removed. (5) PARKED labeled a scout recommendation, pending principal verification. (6) Demand-scope note added. Usage section corrected with harness-reported numbers. All searches performed 2026-10-03 via HN Algolia API, docs.pact.io fetches, and web search; negative-evidence queries listed at the end.

## Demand evidence (first-hand, URL + date required)

Scope note (head-applied): D1–D8 evidence provider+SDK+consumer contract-change breakage in general; none of them directly evidences demand specific to tooling for concurrent-agent or interrupted contract-pack publication. That narrower demand remains UNDEMONSTRATED here.

D1. **Provider silently changed the OpenAI-compat contract under a pinned SDK — production broke with zero code change.**
- URL/date: https://discuss.ai.google.dev/t/openai-sdk-compatibility-suddenly-stopped-working/104345 (2025-09-13)
- Quote (first-hand, trimmed): "without no code change, redeployment, or anything at all in terms of code, it stopped working and broke my app" — followed by a bare `400` BadRequestError.
- Persona: solo/small dev using Gemini's OpenAI SDK compatibility layer with structured-output JSON schemas.
- Workaround: "ended up switching to Gemini's Node.js SDK"; another poster debugging found removing `items: {type: 'number'}` in a nested array restored it. Multi-day confusion, "no hint" from the error.
- Severity/frequency: multiple "same since 9/13" replies within days; severity = full outage of model calls in production.
- Verified: first-hand thread with engineer-follower replies. Symptom matches provider-side behavioral change not announced in the SDK.

D2. **SDK upgrade shipped incompatible request parameters — consumer who upgraded provider got broken calls in the older SDK.**
- URL/date: https://github.com/vercel/ai/issues/7856 (opened 2025-08-07, closed 2025-08-08 with v4 backport 1.3.34)
- Quotes: "`UnsupportedModelVersionError`: AI SDK 4 only supports models that implement specification version 'v1'" ; "`AI_APICallError: Unsupported parameter: 'max_tokens' is not supported with this model. Use 'max_completion_tokens' instead.`"; "this is a pretty big issue for us too. We're in the process of migrating to v5, but with all the breaking changes this isn't trivial"
- Persona: teams on Vercel AI SDK v4 whose provider (OpenAI GPT-5) changed the parameter contract (max_tokens→max_completion_tokens).
- Workaround: backport release `@ai-sdk/openai` 1.3.34; users pin it.
- Severity: hit within hours of GPT-5 launch, +14 👍, downstream dupes (planetarium agent8 #409/#410, Oct 2025).

D3. **Full SDK+consumer migration shipped together, passed CI with mocks, broke in production through a cross-layer serialization contract.**
- URL/date: https://mgregersen.dk/blog-migrate-openai-sdk-to-vercel-ai-sdk/ (2026-03-29)
- Quote (first-hand, trimmed): "By Friday morning, every LLM call in production was failing." + "We reverted the entire migration." — root cause per the post: a Zod `.url()` schema the AI SDK's OpenAI provider silently rejected.
- Persona: engineer migrating provider SDK (OpenAI → AI SDK) in one PR; nightly batch LLM jobs.
- Root cause: "The issue didn't surface in tests because our test fixtures used hardcoded responses. The Zod serialization only fails when the schema is sent to the actual OpenAI API."
- Workarounds/lessons: migrate one call site at a time; integrate against the real API per schema pattern; keep both SDKs during transition; add tracing.
- Severity: full production fail, same-week revert and rework.

D4. **SDK v5 release broke tool-calling layer for everyone upgrading; users temporarily disabled tools.**
- URL/date: https://github.com/vercel/ai/issues/9165 (Sep 2025; closed as usage error, but shows the excel flow)
- Quote: "completetly breaks tool calling functionality… blocking production applications… We've temporarily disabled tools to use the latest models."
- Persona: "our codebase" — teams on ai v5 raising type `"None"` 400s from OpenAI. Severity: high (all tools), short-lived; verified maintainer response.
- Related migration burden: community reports 200-file migrations to absorb one SDK breaking chain (https://web3nomad.com/p/how-we-migrated-atypicaai-to-ai-sdk-v5-without-breaking-10m-chat-histories, 2025-10-07, first-hand migration log; plus official large codemod suite https://github.com/vercel/ai/commit/4e018544943086b8eb582e63a5ffe75454d28019, 2025-07-14).

D5. **Upstream service modified contracts "obviously not back-compatible", forcing constant adapter churn.**
- URL/date: https://www.reddit.com/r/ExperiencedDevs/comments/15h9adm/writing_integration_testsunits_tests_for/ (2023-08-03)
- Quote (first-hand, OP is the affected engineer, trimmed): upstream "modify contracts that are obviously not back-compatible", leaving them in a "constant state of schema changes at the integration points."
- Persona: orchestration-team backend dev downstream of an upstream they don't control. Workaround: adapter pattern + integration tests. Frequency: recurring ("constant state").

D6. **A field rename slipped through review, broke two downstream services, discovered a week later.**
- URL/date: https://www.reddit.com/r/devops/comments/1rckhdf/a_harmless_field_rename_in_a_pr_broke_two/ (2026-02-23)
- Quote (first-hand): "Had a PR slip through last month where someone renamed a response field… broke two downstream services, nobody caught it for a week."
- Workaround: "we ended up adding openapi spec diffing to CI after that… but it only catches the obvious stuff… not behavioral things."
- Persona: platform/API team; small-to-mid company; severity: a week of silent downstream breakage.

D7. **Third-party vendor renamed a response field; service kept "succeeding" with bad data; garbage written overnight.**
- URL/date: https://www.reddit.com/r/Backend/comments/1vh8iig/silent_3rd_party_api_broke_found_out_from_a/ (2026-09-03)
- Quote (first-hand, on-call author, trimmed): "Our service didn't error. It just kept succeeding with bad/missing data."
- Workaround already in place that failed: "payload validation, some contract tests, pin deps, someone supposedly reads changelogs. Still ate shit."
- Persona: small startup backend/on-call. Severity: bad data + customer discovery.

D8. **Teams abandon Pact/Specmatic for a lightweight self-built schema-diff check because the broker toolchain is "a total ball ache".**
- URL/date: https://www.reddit.com/r/ExperiencedDevs/comments/1vp2vbp/api_compatibility_testing/ (2026-08-15, thread title "[ Removed by moderator ]", content preserved in search index)
- Quote (first-hand, trimmed): Pact+Specmatic integration testing was "a total ball ache"; the team replaced it with an in-house schema-diff utility covering 8 core APIs in under a second, with no broker services.
- Persona: front-end/BFF/cross-team lead. Implication: broker infrastructure cost is a real adoption blocker even inside teams that know Pact.

## Incumbent behavior (configured Pact stack, judged on concurrent-agent + interrupted-publication workflow)

Sources: https://docs.pact.io/pact_broker/can_i_deploy (fetched 2026-10-03), https://docs.pact.io/pact_broker/advanced_topics/pending_pacts (fetched 2026-10-03), https://github.com/pact-foundation/pact-specification/issues/105 (2023-08→2024), https://github.com/pact-foundation/pact_broker/blob/7c1c3044fef0c365ae9264c22b99b0c83509668e/CHANGELOG.md (retrieved via search 2026-10-03), https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue (official docs, fetched via search 2026-10-03).

(a) **Bad tuple about to deploy.** The Pact Matrix records every (consumer version, provider version, verification result) pair; the can-i-deploy doc shows it returning an explicit verdict against the deployed environment ("we are safe to deploy version 22 or 23 to prod, but not any of the versions after"). If a consumer/pact version has never been successfully verified by the compatible provider branch, can-i-deploy fails — the tuple is rejected by the configured gate, not by convention. The pending-pacts feature limits false positives: "the build will only fail when it needs to prevent a breakage to an existing integration", i.e. it still rejects the dangerous direction (provider serving a previously-supported contract incorrectly). GitHub's merge queue enforces the same at merge time: "the queue runs changes against "the latest version of the target branch" with required checks enforced" — paraphrase of the official doc — and failed checks remove the PR from the queue with a logged reason.

Similarly, breaking-contract PRs that test fine in isolation but fail against the integration head are caught: the merge-queue group instead of `pull_request` checks is exactly the mechanism that rejects bad combined tuples. The pending-pacts doc also shows the negative-flow protection: a consumer's feature-branch pact that introduces a new interaction does not break the provider's build, but its failed verification is still published so can-i-deploy blocks the consumer — the consumer is gated, the provider is not unfairly gated.

(b) **Interrupted publication midway.** The configured stack has real recovery semantics:
- Pact content identity is content-addressed (pact-version SHA), so republishing after an interrupted run converges to the same artifact id; the broker changelog records "handle overwritten revisions in database rather than code" — overlapping/aborted publications are handled in the data layer, not left as phantom matrix entries.
- Pending pacts treat "first successful verification of a pact version by a particular branch" as the acceptance point; verifications that never complete simply remain unknown, and can-i-deploy fails closed on unknown integrations (its changelog shows it adding "a warning message if there are interactions missing verification test results"). A retry then fills the slot idempotently.
- WIP pacts follow the same shape: "if a pact was successfully verified because it was included as a WIP pact, keep it as WIP" — an interrupted verification does not flip state to "accepted"; the flip only happens on the first *successful* publish. Fail-closed + idempotent republish = clean resume.
- Merge queue: "A merge queue will wait for required checks to be reported before it can proceed"; a timed-out group is removed from the queue (status check timeout setting) and the PR can be re-added, resuming safely. Atomics are at the merge level: temporary `merge_group` branches are collapsed/merged only on passing checks.

Real user reports of these flows also document the residual frictions, not acceptance of bad tuples: pact-specification issue #105 (2023-08-17) records (i) can-i-deploy's JSON response does not expose whether the blocking pact is *pending*, so ops can't distinguish "someone deployed illegally" from "real incompatibility"; (ii) when pending pacts + WIP hide junit failures, "unless the dev is intimately familiar with pact, they assume that everything is ok and could potentially merge a PR that is actually not going to let them deploy" — i.e. an auto-merge PR passes CI then is blocked at deploy; (iii) async/SNS/SQS role confusion flips the correct deployment order. Maintainer response points to a feature request still open as of June 2024 (pact-foundation/roadmap issue #88, "Support pending interactions in can-i-deploy"). The merge-queue doc notes that reordering ("jumping to the top") causes "a full rebuild of all in-progress pull requests" — a real concurrency cost, also handled in user workarounds at https://boinkor.net/2023/11/neat-github-actions-patterns-for-github-merge-queues/ (2023-11-16, first-hand CI design write-up).

## Falsifier verdict

**PARKED** — scout recommendation only; pending principal verification, not a principal-verified kill.

Justification against the required criteria, both met by the *configured* incumbent:
1. **Rejects a bad tuple:** Yes. It is not a strawman; the matrix + can-i-deploy is the actual gating mechanism and fails closed on any unverified integration (docs.pact.io/pact_broker/can_i_deploy, retrieved 2026-10-03; pending_pacts doc shows the fail-closed/fail-for-real split). D1/D2/D3-style breakages correspond to tuple dimensions a team that configured Pact would either capture (request parameter and schema contracts are exactly what Pact interactions encode) or, if the team *didn't* configure them, that dimension is a configuration miss outside this falsifier's scope, not demonstrated evidence of an incumbent capability gap, and the falsifier explicitly forbids strawman tuples.
2. **Resumes cleanly after an interrupted publication:** DOCUMENTED-YES, REPRODUCED: UNKNOWN (doc + changelog inference only; no runtime reproduction was performed). Content-addressed pact artifacts + "first successful verification" acceptance + unknown-fails-closed make interrupted runs idempotent and safe to retry (pending_pacts doc; broker changelog "handle overwritten revisions in database"; WIP "keep it as WIP" behavior). Merge queue restores to pre-group state on failure/timeout, no partial merge.

The cited residual gaps found (pending-status invisibility in can-i-deploy JSON in issue #105 / roadmap #88; PR merges that can't subsequently deploy; merge-queue rebuild on reordering) are visibility/velocity frictions around an *already-rejecting* gate, not acceptance of bad tuples and not corrupted resume after interruption. They are product-quality knocks against Pact, corroborated by D8's "ball ache" exit, but they do not establish the specific A18-eligible gap posed by the falsifier.

No invented evidence here; a literal pass would have been "did not find cited gaps". A18's central packaged-tuple idea targets a problem that the configured incumbent already structurally covers when teams wire the dimensions in.

## Sources (URL + date + type)

- https://docs.pact.io/pact_broker/can_i_deploy — fetched 2026-10-03 — official docs.
- https://docs.pact.io/pact_broker/advanced_topics/pending_pacts — fetched 2026-10-03 — official docs.
- https://github.com/pact-foundation/pact-specification/issues/105 — 2023-08-17→2024 — user+maintainer thread.
- https://github.com/pact-foundation/roadmap/issues/88 — mentioned 2024-06 — feature tracker.
- https://github.com/pact-foundation/pact_broker/blob/7c1c3044fef0c365ae9264c22b99b0c83509668e/CHANGELOG.md — retrieved 2026-10-03 — repo changelog.
- https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue — official docs, retrieved 2026-10-03.
- https://boinkor.net/2023/11/neat-github-actions-patterns-for-github-merge-queues/ — 2023-11-16 — practitioner blog.
- https://discuss.ai.google.dev/t/openai-sdk-compatibility-suddenly-stopped-working/104345 — 2025-09-13 — first-hand user thread.
- https://github.com/vercel/ai/issues/7856 — 2025-08-07 — first-hand issue thread, maintainer-responded.
- https://github.com/vercel/ai/issues/9165 — Sep 2025 — first-hand, maintainer-responded.
- https://mgregersen.dk/blog-migrate-openai-sdk-to-vercel-ai-sdk/ — 2026-03-29 — practitioner post-mortem.
- https://web3nomad.com/p/how-we-migrated-atypicaai-to-ai-sdk-v5-without-breaking-10m-chat-histories — 2025-10-07 — practitioner post-mortem.
- https://github.com/vercel/ai/commit/4e018544943086b8eb582e63a5ffe75454d28019 — 2025-07-14 — repo commit (codemod evidence of scale).
- https://www.reddit.com/r/ExperiencedDevs/comments/15h9adm/writing_integration_testsunits_tests_for/ — 2023-08-03 — first-hand QA thread.
- https://www.reddit.com/r/devops/comments/1rckhdf/a_harmless_field_rename_in_a_pr_broke_two/ — 2026-02-23 — first-hand incident report.
- https://www.reddit.com/r/Backend/comments/1vh8iig/silent_3rd_party_api_broke_found_out_from_a/ — 2026-09-03 — first-hand incident report.
- https://www.reddit.com/r/ExperiencedDevs/comments/1vp2vbp/api_compatibility_testing/ — 2026-08-15 — first-hand (thread later moderator-removed; content recovered via search index).
- https://github.com/BerriAI/litellm/issues/19216 — 2026-01-16 — repo issue (parameter/routing contract).
- https://forum.langchain.com/t/lag-between-providers-docs-and-python-langchain-package-releases/3046 — 2026-02-27 — user forum thread.

## Coverage and gaps (negative evidence included)

Negative searches (no relevant first-hand A18-style demand about *tooling* for this flow):
- HN Algolia comment search `provider deprecation broke our build` — one plausible-but-off-hit (2020 Ember, https://news.ycombinator.com/item?id=23031544, 2020-04-30); no model-provider contract-pack complaint.
- HN Algolia comment search `contract pack model provider` — zero relevant hits (six unrelated stories).
- Reddit searches surfaced incidents (D5–D7) but **no thread about tooling that fixes cross-layer provider+SDK+consumer contract coordination as a package**; nearest is Specmatic/Pact adoption discussion in D5-D8.
- Stack-overflow style docs gaps: docs.pact.io tombstones and breaking_changes URLs returned 404 (routings changed); I did not find a public "tombstones" doc page at my URLs. That's an investigation gap, not an incumbent gap. Known area from changelog terms used above.
- Not searched in depth: Slack/Discord communities (OpenAI, Pact Slack), LangChain Discord — no access. Gaps here could reveal more First-hand reactions to silent cutoff behavior changes about to be released (worth a follow-up if A18 reopens).

What is NOT covered: no new cloud/cloudflare specific sytheses; no code prototype; no token billing data exposed by this harness — so cost/usage remains unknown below.

## Usage

- Tokens/cost (head-corrected from harness DB, opencode-reported, not an account statement): session ses_eff8f247 (z2) 6,507 output tokens / $0.026052; aborted run ses_eff908b48 314 / $0.002946. Whether these match provider-side accounting: UNKNOWN.
- Wall time: started 06:26 UTC, finish before 07:15 UTC on 2026-10-03 (~45 min bound respected).
