# Approach seeds and scoring rubric (Claude, draft R1)

Status: HYPOTHESES. Written before evidence lanes landed so the evidence can falsify them. Each seed must be tied to cited pains (E-C/E-X IDs) before entering research/approaches-20.md; seeds without evidence get dropped or merged.

## Scoring rubric (each 1-5; weights reflect official judging E-C014 plus BRIEF axes)

| Axis | Weight | 5 means |
|---|---|---|
| Pain | 20% | Repeated first-hand reports, high severity, several personas |
| Evidence quality | 10% | Verified first-hand threads/issues, not marketing |
| Novelty vs existing products | 20% | Nobody ships it; not "GitHub + agents" (judges: originality 50%) |
| Cloudflare fit | 15% | Needs Artifacts per-agent repos/fork/events/tokens, Workers/DO; hard to do elsewhere |
| Feasibility by Oct 14 | 15% | Two humans+agents can ship a working MVP in ~10 days on beta APIs |
| Demo strength | 15% | Visibly concurrent agents, conflict + review + context in 5-10 min |
| Adoption | 5% | Plausible users after the contest |

Total = weighted sum, x20 to give /100. Scores are inputs to debate, not agreement.

## Seeds (to be validated)

1. Intent ledger / claim board: agents declare intent (files, symbols, goal) before editing; a Durable Object arbitrates overlapping claims; conflicts surface pre-edit, not at merge.
2. Speculative merge train: every agent fork is continuously rebased onto a virtual integration branch; conflicts detected in seconds; trains bisect failures.
3. Semantic/structural conflict resolver: AST-level merge of concurrent agent changes, with an agent resolver that has both intents as context.
4. Tournament / best-of-N: N agents attempt same task in forked repos; Workers Previews per fork; judge agent + human pick winner; losing diffs mined for ideas.
5. Why-graph provenance: every commit links to intent, prompt, transcript, tool calls, test evidence (stored as Artifacts context repo); `git blame` answers "why".
6. Review triage for humans: risk-scored, intent-grouped review queue that collapses N agent PRs into reviewable "change stories"; reviewer attention budget.
7. Maintainer shield: inbound AI-contribution gate for OSS: contributions land in quarantined forks; agent reproduces, tests, minimizes, and only verified ones reach maintainers.
8. Agent-to-agent code review market: reviewer agents with distinct lenses (security, perf, API) comment on push events; disagreements escalated.
9. Context repos: per-task "context branch" holding plans, decisions and memory that travels with the code branch; next agent resumes from it.
10. Live coordination channel bound to repo: pub/sub (DO websockets) so agents broadcast "I'm changing X" and subscribe to changes on paths they depend on.
11. Policy/capability-scoped tokens: per-agent repo-scoped short-lived tokens, path-level write policies enforced by a Worker Git proxy; audit trail.
12. Ephemeral environment per agent branch: push -> Workers Preview -> agent self-verifies against live preview; preview URLs in review.
13. Stacked micro-changes by default: agents emit small stacked commits; platform auto-rebases stacks across agents and lands bottom-up.
14. Dependency-update swarm: many agents each own one dependency bump in parallel forks; platform batches compatible ones.
15. Spec-first repo: spec/intents are first-class objects; code changes are verified against spec deltas; reviewers review spec diffs.
16. Rollback/undo ledger for agents: operation log (jj-style) across all agent forks; one-click revert of an agent's whole session footprint.
17. Cross-repo change orchestration: one intent fans out to forks of many repos (millions of repos scale); atomic multi-repo landing.
18. Human-in-the-loop arbitration UI: "air traffic control" dashboard of live agents, conflicts, claims, merges.
19. Test-impact sharding: platform computes which tests each agent change affects and runs only those per fork via events.
20. Reputation/trust scoring for agents: track each agent config's merge/revert history; route review effort by trust.
21. Git-native task board: issues as branches/forks; picking a task = forking; done = merged; no separate tracker.
22. Prompt-to-PR replay: deterministic replay of an agent session from stored context to regenerate a change on new base instead of resolving conflicts textually ("re-derive, don't rebase").

Seed 22 ("re-derive, don't rebase") is my current novelty favourite: when two agents conflict, the platform re-runs the later agent's intent on top of the merged base rather than resolving text. Needs evidence that textual conflict resolution by agents is a real pain and that intent capture is feasible.
