# 20 approaches (Claude integration, v2.1)

Owner: Claude principal. Date: 2026-10-02 (Europe/Berlin). Status: v2.1 = v2 (sha256 edd5f34f) plus body fixes R-A/R-B/R-C from zcode-independent and Pro/ArtifactFS qualifications; no scoring or selection change. Task Passports (Pro 4) is assessed in research/claude/consultation-2026-10-02.md, NOT merged here. v1 digest per Codex: c68de131. No peer has approved anything in this file; scores below are Claude's alone. Codex scores independently (research/codex/), other heads challenge in their own files.

Evidence IDs: E-C### Claude (research/claude/*.md), E-X### Codex (research/codex/evidence.md), E-A### Antigravity (research/antigravity/evidence.md), user message 7 = U7 (experiment/USER-INSTRUCTIONS.md). Seeds from research/claude/approach-seeds.md were merged or dropped as noted at the end.

## Scoring (revised after Z1 from zcode-independent and C-R1-BROAD from Codex)

Two separate verdicts, so contest constraints do not kill long-term ideas (user message 6):

**Contest score /100** mirrors official judging (E-C014): `20 x (0.5*Orig + 0.25*Conc + 0.25*UX)`, each 1-5.
- Orig = originality and prototype quality vs existing products (E-C3xx competitor matrix).
- Conc = how visibly it exercises "concurrency, coordination, context preservation, review, and conflict handling".
- UX = can a judge understand and try it in a 5-10 minute video.

**Gates and side columns** (not weighted into contest score):
- Pain gate: S (strong, several first-hand verified reports across personas), M (some first-hand), W (speculative/vendor only).
- Feas = feasibility of a real concurrent-agent MVP by 2026-10-14 on documented primitives (no merge API E-C305, post-hoc events E-C307/E-C308, 1 GB repo E-C306), 1-5.
- CF = Cloudflare fit: needs Artifacts/Workers in a way hard to copy on GitHub, 1-5.
- LTV = long-term product value regardless of contest (pain x adoption x defensibility), 1-5.

Families (Z5): F1 integration/coordination, F2 candidate selection, F3 review burden, F4 provenance/context, F5 safety/permissions, F6 runtime verification, F7 workspace storage, F8 scale/multi-repo, F9 autonomy policy.

Common architecture vocabulary: **canonical repo** (only the platform publisher holds write token), **agent fork** (`ARTIFACTS.fork()` per task, repo-scoped write token with TTL, E-C305), **push consumer** (Queue consumer Worker for `cf.artifacts.repo.pushed`, E-C006/E-C308), **coordinator DO** (Durable Object per canonical repo holding live state), **runner** (Sandbox/Container or CI SDK job that does git merge/test, because no merge API exists, E-C305; E-X015).

## Summary table

| ID | Name | Fam | Pain | Orig | Conc | UX | Contest | Feas | CF | LTV |
|---|---|---|---|---|---|---|---|---|---|---|
| A01 | Live Integration Radar | F1 | S | 4 | 5 | 4 | 85 | 3 | 5 | 4 |
| A02 | Lease-bound claims enforced at landing | F1 | M | 3 | 5 | 3 | 70 | 4 | 4 | 3 |
| A03 | Merged-state gate + bounded intent reapplication | F1 | M | 4 | 5 | 3 | 80 | 2 | 4 | 4 |
| A04 | Semantic contract sentinel | F1 | M | 4 | 4 | 3 | 75 | 2 | 3 | 4 |
| A05 | Fork tournament with verified landing | F2 | M | 4 | 4 | 5 | 85 | 4 | 5 | 3 |
| A06 | Change-story review queue | F3 | S | 3 | 3 | 4 | 65 | 4 | 3 | 4 |
| A07 | Maintainer inbound quarantine | F3 | S | 4 | 3 | 4 | 75 | 3 | 4 | 4 |
| A08 | Independent reviewer panel on push | F3 | M | 2 | 3 | 3 | 50 | 5 | 3 | 2 |
| A09 | Exact-SHA verification receipts | F4 | M | 3 | 3 | 3 | 60 | 4 | 4 | 4 |
| A10 | Durable handoff / context branch | F4 | M | 3 | 4 | 3 | 65 | 4 | 4 | 3 |
| A11 | Merge decision ledger ("why this one won") | F4 | M | 4 | 3 | 3 | 70 | 4 | 4 | 3 |
| A12 | Quarantine forks + capability tokens | F5 | S | 3 | 4 | 3 | 65 | 4 | 5 | 4 |
| A13 | Session footprint undo across forks | F5 | S | 4 | 3 | 4 | 75 | 3 | 4 | 3 |
| A14 | Preview-per-agent runtime isolation | F6 | S | 3 | 4 | 5 | 75 | 3 | 5 | 4 |
| A15 | Push-triggered fast verification lane | F6 | M | 2 | 3 | 3 | 50 | 3 | 4 | 3 |
| A16 | Zero-checkout lazy agent workspaces | F7 | S (U7) | 4 | 3 | 3 | 70 | 2 | 4 | 5 |
| A17 | Fork-is-the-task board | F1/F9 | W | 3 | 3 | 4 | 65 | 5 | 4 | 2 |
| A18 | Multi-repo change sets with recovery | F8 | M | 4 | 4 | 3 | 75 | 2 | 5 | 4 |
| A19 | Maintenance swarm with batch landing | F8 | M | 3 | 5 | 4 | 75 | 4 | 5 | 3 |
| A20 | Earned-autonomy policy per agent config | F9 | W | 3 | 3 | 3 | 60 | 4 | 3 | 3 |

v1 provisional six (A01, A05, A07, A14, A13, A19) is SUPERSEDED. v2 Claude provisional six after Y2 gate-cap rule and R2-3 dispositions: A01 (conditional primary, R2-1/Y1 tests), A14, A16 (remote/comparative spike; Orig 4 only for remote mode), A05 (conditional), A06, A10. Parked with reopen tests: A13, A07, A19 (folded into A01 batch mode), A03 (G5 fixture), A04, A18. Codex's independent scores: research/codex/rankings-round-1.md. Input to Codex's shortlist, not a vote.

v2 corrections: A16 must not claim blobless/partial clone (Artifacts lists `filter` unsupported, E-G001); A01 kill test adds median push-to-flag <=60 s at N=3 (Y1) and live WIP-warning uptake (Codex R2-1); every approach adopts an agent-facing API as primary surface (ZCode red-team D1) and an explicit 'why plain worktrees + merge queue lose' fixture (D3).

---

## A01 Live Integration Radar (F1)

- Target user: team lead / solo power user running 3-20 coding agents on one codebase.
- Job: know within seconds when two live agents' work stops composing, before either finishes.
- Cited pain: integrating parallel work is the top HN pain, one operator spends ~1/3 of time helping agents merge (E-C103; also E-C101, E-C102, E-C104, E-C110, E-C135); vendors isolate but "does not merge changes back" (E-C320); clean textual merge + failing combined test is real (E-X004 concern, Codex fixture research/codex/local-validation.md); nobody continuously integrates N heads (workflows synthesis gap 1).
- Workflow: each agent works in its own fork and pushes WIP often. Every push triggers a trial merge of all live heads (pairwise + full octopus) against canonical head in the runner, plus fast tests. The coordinator DO posts "A and C now conflict on src/auth.ts (textual)" or "merged state fails test X (semantic)" to the affected agents via an MCP tool/HTTP endpoint and to a live web radar. Agents can call `whats_live()` to see siblings' touched paths before editing.
- Architecture: agent forks + push consumer Worker -> Workflow -> runner (Sandbox/Container with real git) computing merge matrix; coordinator DO stores matrix and fan-outs via WebSocket; Workers UI renders matrix; notes on canonical repo record integration results.
- MVP: 3 real agents (Claude Code, Codex, ZCode) on a small Worker app; radar shows a textual conflict and a semantic (clean-merge, failing test) conflict appear live; agents get notified and adjust.
- Risks: runner cost/latency with N^2 merges (cap N, incremental); notification ignored by agents (E-C114 informed agents ignore shared memory); overlap with merge queues (E-C341).
- Competitors: GitHub merge queue (post-hoc, PR-level, E-C341), Collide (collision awareness, vendor, research/orchestrator/social-evidence.md), Foremerge (advisory intent, X2), GitButler locks (local, E-C328), Weave (merge driver, E-C346).
- Falsification: on 10 replayed parallel task pairs, if radar does not flag a real conflict earlier than "at PR time" in >=50% of conflicting pairs, or agents ignore warnings so outcomes equal plain worktrees, kill.

## A02 Lease-bound claims enforced at landing (F1)

- Target user: teams that already use file-ownership conventions for agents (E-X001 workaround).
- Job: stop two agents from silently doing overlapping work.
- Cited pain: homegrown merge locks/intent logs (E-C105, E-C109, E-C362); prompt-only rules ignored (E-C136, E-C140); shell bypass of guards (E-X012). Counter: claims don't earn their keep (E-C113), scope not knowable upfront (E-C112).
- Workflow: agent claims paths/symbols with a lease (TTL, renewable) via MCP; overlapping claims are allowed but negotiated; landing rejects any diff touching paths outside the agent's claim or under another active lease unless the human approves.
- Architecture: coordinator DO holds leases; landing Worker compares fork diff (runner) against leases; canonical publish only via platform token.
- MVP: two agents request overlapping claims; second is redirected; a third agent edits outside claim and is quarantined at landing.
- Risks: Foremerge already specifies this protocol (X2); claim granularity wrong; agents over-claim.
- Competitors: Foremerge, GitButler locks, CODEOWNERS.
- Falsification: expired-lease/remote-publisher race (Codex X2): if a racing publisher can land a diff inside another's live lease, or if claims reduce conflicts by <30% vs no claims on replayed tasks, kill.

## A03 Merged-state gate + bounded intent reapplication (F1)

- Target user: teams whose agents produce individually green branches that break when combined.
- Job: land the combination safely; when a candidate breaks the combined state, regenerate it on the fresh base instead of hand-resolving.
- Cited pain: E-X004, E-X008 (60 branches on stale base), E-C101 (would rather rewrite than resolve), E-C103; fixture research/codex/local-validation.md.
- Workflow: candidate held unchanged; runner tests canonical+candidate; on failure, the original versioned task contract is re-run by an agent in a new fork from the new base; scope drift is diffed against the first attempt; human approves if intent/test policy changed; receipt records parent attempt.
- Architecture: Workflows for the loop; forks for each attempt; runner; DO for queue; git notes for receipts.
- MVP: two agents; A lands; B's clean-merge breaks; platform re-runs B's contract on fresh base, passes, lands with receipt.
- Risks: nondeterminism, O(N) serial latency, scope drift (E-A002, Antigravity critique; Codex X5); expensive; demo may look like a merge queue.
- Competitors: GitHub merge queue + "@copilot resolve conflicts" (E-C344), Agent Merge (VS Code, social-evidence), Graphite.
- Falsification: on tasks with hidden acceptance criteria or flaky tests, if reapplication changes scope without detection in >1 of 5 runs, or median loop >15 min, kill as a product (keep as feature).

## A04 Semantic contract sentinel (F1) — maps Antigravity CEIP

- Target user: teams with shared internal APIs touched by several agents.
- Job: catch zero-conflict semantic breakages before landing.
- Cited pain: E-A001, E-X004, Codex fixture; E-C106 (modularity is not enough).
- Workflow: when an agent changes an exported symbol, the platform extracts the contract (signature + existing tests/call sites) and runs sibling agents' new call sites against it in the runner; violations notify both agents.
- Architecture: runner with language tooling (TS first); push consumer; DO for contract index.
- MVP: TypeScript repo, A changes behavior of `greet()`, B adds caller; sentinel flags it pre-landing.
- Risks: language-specific, heavy; "proof" overclaims (agent-written invariants can be wrong); Weave/AST merge overlap.
- Competitors: type checkers + CI, Weave, merge queue.
- Falsification: if a plain "run full test suite on merged state" (A01/A03) catches every case the sentinel catches on 10 fixtures, it adds no value; kill.

## A05 Fork tournament with verified landing (F2)

- Target user: developers who already run best-of-N (Cursor /best-of-n, Agent HQ) and pick manually.
- Job: get N attempts at one task, compare them by behavior, land one, keep the rest as evidence.
- Cited pain: best-of-n "does not merge changes back" (E-C320); comparing attempts is manual and drift shows late (E-C323); review is the bottleneck (E-C326, E-C364).
- Workflow: task spawns N forks; each agent works; each candidate gets a live preview URL and test results; a judge agent + rubric produces a ranked comparison of behavior (screenshots/API diffs), human picks or auto-pick under policy; winner lands via platform publisher; losers kept read-only with "why rejected" note (feeds A11).
- Architecture: `fork()` per candidate (cheap, E-C301/E-C309), push consumer, Workers Builds previews or CI SDK per candidate (E-C310 caveat: previews per branch on connected repo -> mirror candidates as branches into one integration repo), DO for tournament state, UI.
- MVP: 3 agents implement the same small feature; side-by-side previews; judge ranking; one-click land.
- Risks: cost (N x tokens, E-C110, E-C141); previews per fork not automatic (E-C310); "Cursor already does it" perception.
- Competitors: Cursor best-of-n, Agent HQ multiple agents, Codex cloud multiple attempts.
- Falsification: if human picks of the judge's top-1 agree <50% with blind human review, or tournament never beats single attempt on hidden tests in 5 tasks, kill.

## A06 Change-story review queue (F3)

- Target user: reviewer facing dozens of agent changes per day at work.
- Job: review intent and risk, not raw diffs.
- Cited pain: review time +91% (E-C228), "almost right" (E-C230), reviewers want intent not diff chapters (E-C247), huge PRs (E-C122, E-C249), rubber-stamping risk; counter: AI review comments mostly nits (E-C244).
- Workflow: each agent change arrives as a "story": stated intent, risk tier (paths touched, blast radius), evidence (tests, preview), compact decision summary (E-C153); low-risk tier auto-lands with receipt; high-risk queued; reviewer has attention budget.
- Architecture: push consumer + runner for evidence; DO queue; UI; notes for story metadata.
- MVP: 5 agent changes; queue triages into auto-land vs review; reviewer clears queue in minutes.
- Risks: crowded (Graphite Diamond, CodeRabbit, Copilot review E-C245/E-C246, Stage E-C247); risk tiering can be wrong.
- Competitors: Copilot review, CodeRabbit, Graphite, Stage, PostHog pr-approval-agent.
- Falsification: if reviewers using stories are not >=30% faster with equal defect catch rate on a seeded-bug set, kill.

## A07 Maintainer inbound quarantine (F3)

- Target user: OSS maintainers of AI-accepting projects (not the AI-banning bloc E-C210-E-C218).
- Job: accept agent contributions without paying review cost for slop.
- Cited pain: curl ~20% slop, 5% valid (E-C202, E-C203); GitHub "Eternal September" (E-C205); tldraw/Ghostty auto-close (E-C208, E-C234); 1-open-PR asks (E-C223); "DoS" (E-C152); effort asymmetry (E-C121). Counter: curl merges ~50 AI-analyzer fixes (E-C227) -> verified AI work is welcome.
- Workflow: contributors (human or agent) push to a quarantine fork, never a PR. Platform requires a reproducer + test, runs it on canonical base and on the patch (fails-then-passes), minimizes diff, checks the project's machine-readable AI policy (E-C225), and only then surfaces a compact card to maintainers. Non-reproducing submissions never reach a human.
- Architecture: fork per submission with write token; runner; DO per project inbox; UI; policy file in repo.
- MVP: 5 submissions from agents (2 slop, 1 duplicate, 2 real fixes); maintainer sees 2 verified cards.
- Risks: projects with no tests; adoption requires moving off GitHub (mirror mode needed); GitHub roadmap caps (E-C226) commoditize volume controls but not verification.
- Competitors: GitHub PR controls (E-C206, E-C226), Vouch (E-C209), Coolify anti-slop Action (E-C238).
- Falsification: on 20 real historical slop/valid reports (public curl/HackerOne disclosures), if the gate does not filter >=70% of slop while passing >=90% of valid, kill.

## A08 Independent reviewer panel on push (F3)

- Target user: teams wanting independent AI review per push.
- Job: catch bugs before humans review.
- Cited pain: reviewer must be independent of the author agent (E-C243); prompt injection via PR content (E-C131); PostHog qa-swarm practice (social-evidence).
- Workflow: push event -> N lens reviewers (security, perf, API) in isolated read-only forks; disagreements escalate.
- Architecture: read-only fork (`readOnly`, E-C305) per reviewer; push consumer; Workflows.
- MVP: 3 reviewers comment on agent pushes.
- Risks: crowded, nits (E-C244), low originality.
- Competitors: Copilot review, CodeRabbit, Greptile, Cloudflare internal review (E-C242).
- Falsification: seeded-bug benchmark vs Copilot review; if not better, kill. Kept for completeness; likely feature of A06.

## A09 Exact-SHA verification receipts (F4)

- Target user: maintainers/reviewers who need to trust "tests passed" claims.
- Job: verify in <60 s what was tested, on which exact merge SHA, under which policy, by whom (a trusted runner, not the agent).
- Cited pain: provenance wanted as compact decisions not transcripts (E-C153 vs E-C154/E-C155); "deliver code you have proven to work" (E-C239); kernel "unverified reports" / Assisted-by (E-C214); Codex X3.
- Workflow: runner signs a receipt {source SHA, base SHA, merged SHA, test policy version, results, environment digest} stored as git note; UI and CLI `verify` check signature and recompute merged SHA.
- Architecture: runner + Worker signing key (secrets), git notes in Artifacts (E-C302), verify endpoint.
- MVP: agent claims green; receipt shows tests ran on stale base; platform rejects; after rerun receipt verifies.
- Risks: receipts as feature not product; signing key management; competitors (Sigstore/SLSA attestations, GitHub artifact attestations).
- Competitors: SLSA/in-toto, GitHub attestations, Entire checkpoints (E-C336), Git AI (E-C337).
- Falsification: if a reviewer cannot detect a tampered or stale receipt in <60 s in a blind test, kill.

## A10 Durable handoff / context branch (F4)

- Target user: long-running agent tasks that span sessions or agents.
- Job: next agent resumes with plan, decisions, open questions and exact base.
- Cited pain: subagent worktree lacked newly committed plan state (E-X003); stale base (E-X008); losing why (E-C161).
- Workflow: each task has a context repo/branch (plan.md, decisions, failed attempts) bound to the code fork; handoff preflight verifies base SHA and context version; next agent gets both.
- Architecture: paired Artifacts repos (code + context), Artifacts already advertises "versioned storage for code and agent context" (source-announcement); DO task state.
- MVP: agent 1 runs out of budget mid-task; agent 2 (different vendor) resumes from context branch and finishes.
- Risks: Entire/SpecStory overlap; context rot; Cloudflare dogfoods session repos (E-C303).
- Competitors: Entire, SpecStory, Claude Code memory files.
- Falsification (v2.1, R-C/G-R4-2): on 5 restart/drift tasks, must beat the strongest baseline = same-commit plan file + Entire checkpoint resume + git log (not git log alone) on correct-base recovery, preserved acceptance and time; note default clones drop git notes (Grok R4-2), so metadata must survive clone. Otherwise park.

## A11 Merge decision ledger (F4)

- Target user: future maintainers and agents doing code archaeology.
- Job: answer "why is the code this way and what alternatives were rejected" for any line.
- Cited pain: E-C161; Agent Trace leaves rebase/storage open (E-C335); "why" in announcement (E-C005); workflows gap 5 (provenance that survives integration).
- Workflow: every landing records chosen candidate, rejected candidates (links to read-only forks), conflict resolutions, reviewer decision, as Agent-Trace-compatible notes; `why <file:line>` walks blame -> ledger.
- Architecture: git notes (E-C302), read-only forks for losers, Worker query API, UI.
- MVP: after a tournament (A05) or conflict, `why` shows the losing alternative and reason.
- Risks: value appears late (not in a 5-min demo); depends on A05/A01 producing decisions.
- Competitors: Entire why/blame (experimental, Codex C-R1-ENG), Git AI, Agent Trace.
- Falsification: if in a blind archaeology task the ledger does not change the engineer's answer vs plain blame+PR text, kill.

## A12 Quarantine forks + capability tokens (F5) — maps Antigravity EQ-2PP

- Target user: anyone giving agents write access to valuable repos.
- Job: make destructive agent git ops structurally impossible on canonical history.
- Cited pain: force-push/reset/stash races (E-C135, E-C136, E-C138); wrong-checkout writes (E-X006, E-X009); unrelated deletions (E-X010); prompt rules ignored (E-C140).
- Workflow: agents only ever get a TTL write token to their own fork; canonical has a single publisher; publication = platform re-validates head and fast-forwards; every token mint/revoke audited.
- Architecture: `fork()`, `createToken(scope, ttl)`, `revokeToken()` (E-C305); publisher Worker + runner; audit log in D1.
- MVP: rogue agent runs `git push --force` and `reset --hard`; canonical untouched; footprint visible.
- Risks: it is Cloudflare's own recommended practice (E-C309) -> low originality; same as GitHub forks + branch protection.
- Competitors: GitHub forks/branch protection/rulesets, GitButler agentic safety (E-C330).
- Falsification: if any documented path lets a raw git client modify canonical state, or if equivalent GitHub setup takes <10 min, product value is low; keep as primitive.

## A13 Session footprint undo across forks (F5)

- Target user: operator after an agent run went wrong.
- Job: atomically see and revert everything one agent session did, across forks, branches, and landed commits.
- Cited pain: losing work / destructive ops (E-X001, E-X010, E-C138); jj op log used for this locally (E-C331, E-C148).
- Workflow: platform records every ref change by agent identity (it is the only publisher), builds an operation log; `undo session S` computes revert commits for landed changes and deletes/archives forks; shows dependency impact (other agents built on S).
- Architecture: op log in DO/D1, git notes; runner for revert; tokens per session give attribution.
- MVP: 3 agents; one corrupts behavior; one-click undo of its session while keeping others' later work.
- Risks: reverting work others depend on (needs A01 matrix); jj competition locally.
- Competitors: jj op log, GitButler undo, git reflog.
- Falsification: if undo leaves the repo broken (tests) in >1 of 5 scenarios where later work depended on the undone session, scope down.

## A14 Preview-per-agent runtime isolation (F6)

- Target user: web/Workers developers running parallel agents who must verify running behavior.
- Job: each agent change has its own live URL and its own data, no port/DB collisions.
- Cited pain: top complaint "manually verifying everything is working" (E-C321); ports/DBs/secrets per worktree (E-C319, E-C322, E-C363); runtime collisions (E-X002, E-X005); slow batch CI feedback (E-C142).
- Workflow: agent pushes; platform builds a Worker preview with isolated D1/KV (seeded fixture); agent calls `verify(url)` with Playwright-like checks; reviewers click the URL linked from the commit.
- Architecture: Workers Builds Artifacts integration (E-C007, E-C310: previews per branch on connected repo, so mirror agent forks to branches of one integration repo) or CI SDK (E-C311); per-preview D1 databases.
- MVP: 3 agents change the same app; 3 live preview URLs with separate data; one regression caught by its preview.
- Risks: preview limits per Worker; only Workers apps; "Vercel/Netlify previews exist".
- Competitors: Vercel/Netlify/Cloudflare Pages previews (human PR oriented), simfleet (mobile, E-X002).
- Falsification: Z6 — if per-agent preview URLs for fork-per-agent cannot be made to work by Oct 7, pivot to data isolation only.

## A15 Push-triggered fast verification lane (F6)

- Target user: agents that need seconds-level feedback instead of batch CI.
- Job: run only affected tests on every push and report back to the agent.
- Cited pain: CI usage 100x (E-C141), Actions batch-only (E-C142), agents miss red CI (E-C139).
- Workflow: push event -> test impact analysis -> runner executes subset -> result posted to agent MCP channel.
- Architecture: push consumer, runner, cache of dependency graph in R2.
- MVP: agent loop with sub-30 s feedback vs full CI.
- Risks: test impact analysis is hard; existing (Nx, Bazel, Launchable); low originality.
- Competitors: Nx affected, Bazel, Launchable, Depot CI.
- Falsification: if impacted-subset misses >5% of failures on a seeded set, kill.

## A16 Zero-checkout lazy agent workspaces (F7) — reserved for user pain U7

- Target user: developers running many agents locally whose worktrees eat disk (U7; E-C168, E-C135, E-C319 deps reinstalled per worktree).
- Job: give each agent an isolated writable workspace whose physical cost is proportional to what it changes, not to repo + deps size.
- Cited pain: U7 (first-hand, user); E-C157, E-C167, E-C168; Codex/Cursor cap worktrees at 15/25 (workflows lane). Orchestrator note: git worktrees already share the object DB; bytes likely in deps/build outputs — must measure (research/orchestrator/worktree-storage-pain.md).
- Workflow: agent workspace = Artifacts fork (server) + local lazy materialization: sparse checkout (working-tree savings only; Artifacts documents v1 `filter` unsupported, E-G001; v2/ArtifactFS lazy hydration documented but untested by us, E-X021), deps from one shared immutable store (pnpm), private writable build outputs per task; commit = push to fork. Remote mode: agent runs in a Sandbox against its fork, moving (not removing) allocation to the cloud; local and remote bytes reported separately.
- Architecture: Artifacts fork + token; local mode (sparse checkout of a full clone — Artifacts does not support `filter`, E-G001 — plus shared immutable deps store) or Cloudflare Sandbox workspace; Worker API for file reads (E-C305 readFile).
- MVP: measurement harness: 1/5/10/20 workspaces of a real JS repo, physical bytes (du --apparent vs physical, btrfs/xfs reflink), creation latency, build/test parity, for: plain worktrees, sparse worktrees + npm, sparse worktrees + pnpm shared store (killing baseline; Codex measured pnpm two-tree union 229.6 MiB vs 459.0 MiB summed on one small Worker starter, package-storage-validation.md), ArtifactFS (incumbent control, E-X021), reflink only where the FS supports it (ext4 here does not, E-G007), Artifacts-remote sandbox (local + remote bytes).
- Risks: local tools may already solve it (pnpm, reflinks) -> product value is the integration and remote mode; FS portability; not obviously "Git platform" to judges.
- Competitors: git worktree/sparse-checkout, pnpm, ArtifactFS (E-X021), Worktrunk (copies ignored deps/caches per worktree, cited in pro-angle-5), Nix store, Dagger container-use, devcontainers, Cursor/Codex cloud agents.
- Falsification (v2.1, Y3 threshold): the Artifacts-specific mode must cut total physical bytes (source + store + build outputs + logs, local plus remote reported separately) by >40% versus sparse worktrees + pnpm shared store at build/test parity with two concurrent writable tasks; otherwise park the product, keep a "workspace doctor" (configure pnpm/sparse/cleanup) as the user-facing answer to U7. ArtifactFS must also be beaten or it is the incumbent.

## A17 Fork-is-the-task board (F1/F9)

- Target user: small teams dispatching agent tasks.
- Job: no separate tracker: claiming a task = forking, status = fork state, done = landed.
- Cited pain: weak; manual orchestration overhead (social-evidence sawyerhood, search-level); Vibe Kanban popularity (E-C357) shows demand but crowded.
- Workflow/architecture: tasks are repos with metadata; DO board; UI.
- MVP: kanban driven by Artifacts events.
- Risks: crowded (Vibe Kanban, Conductor, Linear+agents); derivative.
- Falsification: if users prefer existing kanban + worktrees in a 3-person trial, kill. Retained as UX shell candidate rather than product.

## A18 Multi-repo change sets with recovery (F8)

- Target user: platform teams changing APIs across many services/repos.
- Job: one intent fans out to forks of many repos; lands in dependency order with a recovery protocol (not atomic promise, per Codex X6).
- Cited pain: worktrees break across repos, "the git remote becomes the only integration point" (E-C361); multi-repo coordination (E-C108).
- Workflow: change set object lists repos + order; agents work per repo fork; platform tests consumers against producer candidate; lands in order; on failure, rolls forward/back per protocol.
- Architecture: Artifacts scale to millions of repos (source-announcement); DO per change set; runner.
- MVP: 3 repos (lib, service, client); API rename landed in order with consumer tests.
- Risks: large protocol; demo complexity; schedule risk (X6).
- Competitors: Sourcegraph Batch Changes, multi-gitter, Renovate groups.
- Falsification: if the recovery protocol cannot restore consistency after an injected mid-sequence failure, kill.

## A19 Maintenance swarm with batch landing (F8)

- Target user: teams with backlog of upgrades, lint fixes, migrations.
- Job: let 10-50 agents each take one maintenance item concurrently and land compatible ones together.
- Cited pain: agents do routine maintenance (announcement framing); CI cost of many small PRs (E-C141); merge queue as bottleneck. Evidence is moderate.
- Workflow: platform splits a migration into items; each agent gets a fork; trial-merges batches (from A01 machinery), lands compatible batches, re-queues failures.
- Architecture: forks, push consumer, runner batch merges, DO scheduler, UI showing swarm.
- MVP: 10 agents fix 10 lint/dep items concurrently; platform lands in 2-3 batches.
- Risks: Renovate/Dependabot grouping; agents trivial vs real tasks; looks like a demo of A01.
- Competitors: Renovate, Dependabot, Sourcegraph Batch Changes, merge queues with batching.
- Falsification: if batch landing does not cut total wall time/CI runs vs serial merge queue by >=40%, kill.

## A20 Earned-autonomy policy per agent config (F9)

- Target user: engineering managers deciding how much to trust each agent setup.
- Job: let low-risk changes from agent configs with good track records auto-land; route others to humans.
- Cited pain: Copilot approvals counting toward required approvals (E-C246) shows demand; review fatigue (E-C228). Counter: reputation dies on disposable accounts (E-C202) — applies to inbound, less to internal configs.
- Workflow: platform tracks per agent-config (model+prompt+tools hash) land/revert/defect rates; policy maps risk tier x trust to autonomy.
- Architecture: D1 stats, publisher policy, notes.
- MVP: two configs; one earns auto-land, other demoted after revert.
- Risks: needs history to be meaningful (demo weak); gaming.
- Falsification: if trust score does not predict reverts better than path-risk alone on historical data, kill.

---

## Seed disposition (honest merges, Z5)

- Seed 1 (intent ledger) -> A02. Seed 10 (live pub/sub channel) merged into A01 (same coordinator DO and notifications; >70% overlap). Seed 2 (speculative merge train) -> A01 (continuous) and A19 (batching). Seed 3 (AST resolver) dropped as standalone: Weave and "@copilot resolve conflicts" exist (E-C344, E-C346); retained inside A04. Seed 4 -> A05. Seed 5 (why-graph) split into A09 (receipts) and A11 (decision ledger), dropping transcript capture (Entire/SpecStory own it; E-C154/E-C155 reject transcripts). Seed 6 -> A06. Seed 7 -> A07. Seed 8 -> A08. Seed 9 -> A10. Seed 11 -> A12 (no Git receive-pack proxy, X6). Seed 12 -> A14. Seed 13 (stacked micro-changes) dropped: Graphite/GitHub stacked PRs (E-C342, E-C348). Seed 14 -> A19. Seed 15 (spec-first repo) merged into A03's versioned task contract. Seed 16 -> A13. Seed 17 -> A18. Seed 18 (air-traffic dashboard) dropped as product per Antigravity Fallacy A; becomes UX surface shared by A01/A05/A19. Seed 19 -> A15. Seed 20 -> A20. Seed 21 -> A17. Seed 22 (re-derive) -> A03 as bounded intent reapplication (Codex X5 constraints accepted).
- Added from peers/user: A04 (Antigravity CEIP), A12 (Antigravity EQ-2PP), A16 (user U7 / C-R1-STORAGE), A09 (Codex receipts).

## Open items for v2
- Integrate maintainer-lane synthesis (E-C2xx), Reddit cross-check (E-C4xx), ZCode red-team, Codex independent scores, pending ChatGPT Pro results (research/orchestrator/chatgpt-pro-registry.md: all four pending at time of writing).
- Spot-verify E-A### before ledger integration.
