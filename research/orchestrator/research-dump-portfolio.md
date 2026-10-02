# Existing portfolio ideas applicable to the agent-Git experiment

Read-only review, 2026-10-02. Source: public `alexeygrigorev/research-dump`, supplied root baseline `5b7d3be`. Inspected the Astra 100-idea index, all 100 titles, selected relevant cards and source register, monetization strategy and relevant cards, Product Shipping course plan and interview playbook. No remote edits, model launches, contact with prospects or external revalidation. These are archived research hypotheses, not evidence that Alexey read particular books. The book-focused agent should establish reading provenance separately.

The current experiment's `research/shortlist-6.md` draft 5 retains A01, A16, A05, A06 and A10; A14 is folded into A01 and slot six is open. Neither principal has approved a final shortlist. Recommendations below do not fill that slot or imply agreement.

## Five high-fit applications

### 1. Environment Doctor / Dependency Domino Map → A16 workspace doctor

Existing ideas: Tutorial Environment Doctor (original ID 55), Dependency Domino Map (56), and Repo Time Machine (11). Sources: `strategy/astra-challenge/ideas-001-025.md:5–15`, `:41–51`, `:101–111`.

Use the first two as the entry workflow for the user's disk pain: an authorized read-only inventory separates physical source, Git, dependency, cache and output bytes; suggests one bounded isolated experiment; proves the resulting workspace still builds and keeps independent writable state. Dependency Domino Map contributes consumer-level tests after changing environment or package setup. The archive does not directly establish a worktree-storage market: this is an adaptation to new first-hand evidence, not an archived finding about disk usage.

Concrete next test: two new small real-project workspaces, identical feature tasks, one ordinary setup and one shared immutable dependency setup. Count unique allocated bytes and startup plus real build/test completion; deliberate source and dependency mutation tests. Never hardlink writable source. Compare against existing pnpm/venv tools before building a cloud Git substitute.

Falsifier: ordinary package/cache configuration reaches the same footprint and task outcome with less setup, or shared dependencies permit cross-task mutation. Keep a helpful diagnostic if the larger infrastructure product fails.

### 2. Agent Handoff Capsule + Reproducibility Passport → A10 / aplexer actual recovery

Original IDs 61 and 49; `ideas-001-025.md:17–27`, `:137–147`. The archive explicitly says another summary is insufficient; the receiver must really continue with the right constraints. The passport is supposed to be a tested replay package, not a manifest with unavailable data.

Apply immediately to genuine aplexer head/executor handoffs: accepted task, exact code state, owner generation, unresolved decisions and checked results. Preserve allowed dirty/untracked work and private recovery state; distinguish delivery, receipt and accepted ownership. Existing Git/agent native resume remains the control.

Concrete test: interrupt a real task, advance canonical in a sibling, restart a different agent, then independently check correct base, preserved constraints and finished feature. Include a stale sender, duplicate delivery and lost reply. Compare to a committed plan plus Git log/native resume, and current Entire capability before novelty claims.

Falsifier: metadata exists but task continuation violates constraints, or the baseline recovers equally well with lower effort. No need to make Task Passports a sixth product merely because an old idea has a similar name.

### 3. Fair Comparison Referee + Agent Crash Test → experiment integrity and protocol validation

Original IDs 50 and 41; `ideas-026-050.md:53–63`, `:209–219`. Fair Comparison Referee is already proposed as a component of ML Detective, not a separate app. Agent Crash Test specifies lost response, repeated tool call and inspection of actual state.

Use this as a common testing method across A01, A05 and aplexer. It fits the experiment's concrete asymmetric-pilot and fake-binding problems better than another model-debate framework. Freeze equal tasks/model/tool access/budget and a protected task-completion oracle before either arm; retain actual candidates until independent replay. For messages, test genuine identity, thread links, idempotency and persistent state under response loss/restart.

Concrete next test: repaired A01 trial with equal instructions/test access, actual concurrent writer tasks, both safety and role completion, recorded warning-consume-action timestamps and replayable candidate refs. Separately run genuine-bound aplexer reply/retry/restart tests against the reconciled build.

Falsifier: benefit disappears when equal policy is enforced, warnings do not change behavior, or retry duplicates effects/misroutes the owner. A recovered test, not another proposal or persuasive argument, determines progress.

### 4. Data Contract Negotiator + Semantic Git Merge → test A18/A01 intent compatibility

Original IDs 34 and 32; `ideas-001-025.md:125–135`, `ideas-076-100.md:101–111`. The latter was evidence class C: semantic-merge pain was only indirectly supported. Its bounded proposal is one intent test for one conflict, not arbitrary automated merge.

Use one producer/consumer API change as a realistic input to A01 composed-behavior tests or the proposed A18 Contract Packs. This contributes a narrow buyer job and a task pair, not independent novelty. The current experiment already treats configured Pact version combinations as a serious baseline.

Concrete test: two agents change producer/consumer concurrently; ordinary tests pass separately; an independently specified consumer contract must catch composed incompatibility. Add interrupted publication and exact-head recovery only where that is the demonstrated unmet job.

Falsifier: configured existing contract CI catches the same issue at the same actionable time, or the agent workflow has no improvement beyond storing the contract. Do not count this as slot six until separately supported.

### 5. Repo Time Machine → a narrow first-user segment, backed by observed engineering adoption

Original ID 11 is the archive's leading idea: restore an old educational ML repo and its intended result, not just imports. It is naturally adjacent to A16 environment diagnosis and A10 replay. `strategy/astra-challenge/README.md:75–85` explicitly merges this family with Tutorial Environment Doctor, Book Exercise Modernizer and Course Maintenance Radar; four names do not warrant four teams/products.

Use an authorized real older Zoomcamp/example repo as a candidate workload where Alexey has relevant expertise and distribution. This can provide first external users and realistic reproducibility tasks without a broad new Git platform. The commercial route is the archived AI-assisted engineering adoption sprint / hands-on developer research, not an assumption that audience reach converts to SaaS demand (`strategy/monetization/ideas-001-050.md:71–93`).

Concrete test: one real old repo, baseline ordinary coding agent and candidate replay workflow under equal tools/budget; reproduce failure, fix minimally and rerun in a fresh environment with independently accepted output. Then observe three opt-in practitioners attempting the same real job, as the Product Shipping plan recommends (`courses/product-shipping/course-plan.md:64–71`). Recruitment/outreach is a proposed next step, not performed here.

Falsifier: fixes are generic and equally easy with an ordinary agent, required assets cannot be restored, or external participants do not experience the problem. Keep the workload as a benchmark rather than forcing a business.

## Challenges and evidence limitations

- The archive already challenges multiplying parallel agents: Parallel Futures, original ID 4, says additional agents can amplify attention/review pain and proposes comparing alternatives for one task (`ideas-051-075.md:41–51`). Prefer a few discriminating experiments to many heads repeating proposals.
- Astra archive source strength is uneven: 19 full-text/comment reads and 66 snippets, shared sources across ideas, unresolved contradictory depth labels, no reliable X corpus (`README.md:43–58`). Class A means problem signal, not solution demand or willingness to pay. Do not inherit ranks as statistical evidence.
- Handoff corroboration S50 is recorded as a firsthand compaction complaint; S51/S52 are excerpt-only and S51's technical explanation is unverified (`sources.md:497–525`). Reopen the underlying pages if used in public claims.
- Agent Crash Test's S77 is vendor promotion with comments of unknown independence (`sources.md:767–775`). Strong internal failure reproduction can justify fixing our tool, but does not manufacture market prevalence.
- Monetization scores, prices and ROI are analyst assumptions dated September 7 (`strategy/monetization/report.md:3`). Quse-style team dashboards and PocketShell remote-agent features both have negative modeled economic surplus (`ideas-051-100.md:47–61`); this is not a forecast, but it directly challenges making every useful internal tool a paid product. Basic SSH access already has alternatives in the archive.
- The course plan stresses one full user scenario, early main-flow events/errors, three external tests and measurable value/cost (`course-plan.md:64–71`). Adopt these practices now; do not copy unrelated course scheduling or business targets into experiment requirements.

Suggested sequencing: use fair-comparison/crash-testing as shared method immediately; run A16 and A10 bounded tests in parallel; use one real repo-recovery task as the external entry; leave contract integration as a narrow discriminating challenger. This is a proposal for principals to accept or challenge, not final consensus.
