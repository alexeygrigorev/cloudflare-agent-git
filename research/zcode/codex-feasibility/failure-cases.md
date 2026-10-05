# Failure cases — adversarial analysis of the proposed platform design

Author: ZCode feasibility/red-team delegate (codex-owned), 2026-10-02.
Companion to `feasibility.md` ([R]/[X]/[P]/[U] conventions defined there; legacy `[R]` = [R] recorded-but-unverified). Each case: trigger → what actually happens → mitigation → residual risk.

## FC-1. Shared write token, shared repo: silent branch overwrite
Trigger: Two agents on the same repo receive the same (or each their own repo-wide) `write` token. Agent A pushes `main` at SHA X; Agent B, built on stale state, pushes `main` with force (or the platform auto-merges carelessly).
What happens: Artifacts tokens have **no branch or path scoping** [R, auth guide] and there is **no branch protection** feature documented anywhere [U-absence]. Any holder of a write token can move any ref. If force-push is accepted (undocumented [U]), B erases A's commits with no server-side guard, and `log()` would only show it if someone looks.
Mitigation: never share write tokens; one repo per agent; `main` in agent forks is irrelevant — only the integrator (platform-held token) touches baseline `main`. Invalidate on `token.revoked` events.
Residual risk: platform token itself is all-powerful; compromise of the integrator Worker = full baseline control. Keep it in a DO with audit notes.

## FC-2. Concurrent integrations: read-modify-write race on baseline `main`
Trigger: Two proposals pass tests simultaneously; two integration Workers clone `main` at SHA X, each merges its proposal, both push.
What happens: Without coordination, first push wins, second is rejected as non-fast-forward (presumed standard receive-pack [U]) or, worse, the platform code "handles" the rejection by force-pushing (FC-1). The Artifacts repo being a single routed instance does NOT make our clone→merge→push cycle atomic — atomicity must come from us.
Mitigation: one Durable Object per baseline repo serializes the integrate cycle (lock → fetch → merge → test → push → receipt → unlock) — but DO serialization alone is NOT sufficient: it does not fix a stale canonical head, nor a stale writer (an integrator that crashed, lost its lease, and later wakes with a still-valid canonical token). The publication fence is: canonical write token held ONLY by the publisher path; re-read the remote head immediately before push; push as a **non-force fast-forward from the exact tested merged SHA**; head moved → approval stale → reject and re-integrate (feasibility.md §3.2). Additionally, the publisher must hold a **current publisher lease/generation and the currently approved policy version**: a superseded generation or policy is rejected **even if HEAD has not moved** — an unchanged head does not authorize a stale publisher. Contingent on receive-pack rejecting non-FF updates [U — spike item 1].
Residual risk: if non-FF pushes are accepted by Artifacts, the FF fence fails → canonical protection needs a different mechanism; the readOnly-canonical + publish-by-replacement idea is an unresolved contingency only — not implemented, changes repository identity, needs a stable publication contract. Lock holder crash mid-cycle → lease expiry, generation rejection and the head re-check together cover the stale writer.

## FC-3. Stale-base merge cascade under test-time drift
Trigger: Proposal P is based on main@X. While P's tests run (real suites take minutes in a Sandbox), another proposal merges, `main` → Y.
What happens: P's receipt, if generated before re-merge, attests to tests that ran against code that is no longer what would ship — provenance theater. With 15-min consumer wall-clock limits [R] and multi-minute test suites, this window is realistic during a live demo.
Mitigation: receipt must pin `{baseSha, proposalSha, mergedSha}`; after merge to Y, re-run the test gate on the merged result before pushing and mark the receipt `verdict: merged-tested@mergedSha`. Never report a green result for a superseded merge.
Residual risk: repeated invalidation under heavy concurrent merges — bound demo to 3 agents.

## FC-4. Event duplication/reordering corrupts the receipt ledger
Trigger: `cf.artifacts.repo.pushed` events arrive twice (at-least-once [R]) or out of order (no ordering guarantee [R]); consumer concurrency 250 [R].
What happens: Duplicate receipts for one push; a `before`/`after` chain reconstructed in arrival order shows impossible histories; receipts for different attempts/policies collide if keyed on `(repoId, afterSha)` alone.
Mitigation: two distinct keys, never conflated — (a) event-delivery dedup key (Queues is at-least-once [X]) to absorb duplicate deliveries — the dedup key must include publisher generation and policy digest and be invalidated when either changes, so a new generation's re-emitted notice is never suppressed; (b) receipt identity = the full tuple `{baseSha, candidateSha, mergedSha, mergedTreeHash, policyVersion, environmentDigest, runnerIdentity, attemptId}` (feasibility.md §3.3) — an after-SHA alone cannot identify a receipt. Causal ordering comes from Git ancestry (parent links, before/after chains); event timestamps order the UI display only and never prove Git ordering. Treat `commitsTruncated=true` [R] as "fetch full log via REST before writing receipt".
Residual risk: none serious — this is bookkeeping, but demos look bad when the ledger visibly doubles.

## FC-5. Provenance notes that don't travel
Trigger: Receipts written as git notes on agent-fork commits; reviewer clones baseline; platform forks agent repos with `defaultBranchOnly: true` for integration.
What happens: Notes live on `refs/notes/*` [R]; `defaultBranchOnly` forks plausibly drop non-branch refs [U]; `log()` is first-parent [R] and never surfaces notes. Reviewer sees clean commits with zero provenance. Also: any agent with a write token can write *any* note, including forging another agent's receipt note (no note-level auth).
Mitigation: anchor authoritative receipts on the **baseline** repo (written by integrator only), cross-reference agent-side notes; treat in-fork notes as untrusted claims; verify against the D1 ledger, HMAC-integrity-protected by the platform. Scope claim: HMAC gives **platform-side integrity checking only** — it is NOT public proof and proves nothing to a third party; independent public verification would require an asymmetric signing path or a trusted verifier, which the MVP does not implement, and the signing secret is never disclosed. The attestation covers the producer and integrity of the **runner result** — evidence that runner R ran policy P on tree T and observed exit E, NOT proof the code is correct.

## FC-11. Candidate tampers with the acceptance policy (tests) to green-light itself
Trigger: A candidate agent, under pressure to land, modifies the acceptance suite in its fork (weakens assertions, skips failing cases) or submits a self-authored "green" result.
What happens: Nothing in Artifacts stops it — the fork write token is repo-wide [R], and a push event is post-hoc [X: engineering-feasibility.md] so it enforces nothing pre-push. Without platform control of the policy, "tests passed" is the agent grading its own homework.
Mitigation: the acceptance policy is baseline-owned and versioned; the publisher runs policy vN from the approved baseline over the merged tree through the **independent oracle** (platform-owned runner + baseline-owned checks; candidates never self-certify) — candidate-side test changes never enter the gate; every receipt records the policy version + policyCommitSha and oracleDigest used; policy evolution for intended API changes requires explicit human approval and a version bump (research/codex/local-validation.md). A receipt whose `policyVersion` mismatches the current approved version is invalid on its face.
Residual risk: a malicious candidate can still poison its own fork's context/notes — treated as untrusted claims (FC-5); the gate only ever reads baseline policy + merged tree.
Residual risk: judges may poke agent repos directly — keep agent-side notes honest but clearly labeled as claims.

## FC-6. Preview publishing leaks work-in-progress (or evaporates)
Trigger: Demo relies on Workers Builds branch previews to show agent branches live; previews default to public [R]; judges or competitors hit the URL; later, more than 100/500 previews accumulate across the demo → oldest auto-deleted [R].
What happens: (a) unreleased agent work is publicly readable — for a platform *about* permission-scoped publishing, a judge catching this is a credibility kill; (b) the demo URL cited in the video 404s by the time judges click it.
Mitigation: Cloudflare Access on preview hostnames [R]; deep-link deployment URLs (immutable per deploy [R]) in the video description; cap preview churn (or serve agent branches only through the platform Worker's own auth and skip raw previews in the demo).
Residual risk: Access adds sign-in friction for judges — use one-time access or show the platform UI instead.

## FC-7. isomorphic-git memory blowup in the integrator
Trigger: Integrator Worker uses isomorphic-git (official example [R]) on a baseline that grows during the demo (commits every second × 3 agents × hours + binary assets).
What happens: Whole working tree lives in a Map-based MemoryFS [R]; Workers isolate memory (~128 MB class [U — platform limit page, not re-verified]) is exhausted; integrator throws mid-merge; with FC-2's lock held, integration stalls.
Mitigation: keep demo repos tiny (<5 MB working tree); run merges for anything bigger in a Sandbox container; stream test logs to R2 (32 MB blob cap [R] makes in-repo logs unsafe anyway); shallow fetch where possible (v1 shallow documented [R]; `filter` documented unsupported among optional **v1** capabilities — v2/ArtifactFS filtering untested [U], E-X021, so no partial-clone assumption either way).
Residual risk: low if repos stay small; enforce with a pre-merge size guard via `readTree`.

## FC-8. Beta churn + billing boundary at the deadline
Trigger: Any dependency on Artifacts behaviors not yet stable; competition ends Oct 14 11:59 PM PDT; billing begins Oct 14 or 15 (conflicting sources [R]); Workers Paid is a hard prerequisite [R].
What happens: An API/schema change between now and submission breaks the demo the week it matters; a lapse in Workers Paid makes the entire platform (Artifacts binding + Sandboxes) dead on arrival.
Mitigation: pin wrangler/SDK versions; run the demo against recorded fixtures as fallback; keep account funded on Workers Paid through Oct 21 (finalist demos); verify billing date from the dashboard, not docs.
Residual risk: beta is beta; nothing we can do beyond fallbacks.

## FC-9. "Concurrent" agents that are actually serial (judging risk, not a bug)
Trigger: Implementation convenience — one agent runs to completion, then the next; or agents are just sequential cron ticks.
What happens: This fails the explicit minimum bar "multiple agents working on changes concurrently" [R] and 25% of judging (concurrency/coordination) [R]. Worst case: technically meeting submission rules while scoring poorly.
Mitigation: the demo must show **at least two actual concurrently running coding agents** — real agent CLI processes (e.g., two different headless coding-agent CLIs) alive at the same wall-clock time, visibly interleaved pushes (distinct `pushed` events within the same minute), at least one live conflict handled by the integrator. Scripted task-runner loops are acceptable only for pipeline bring-up and must be clearly labeled synthetic fixtures — they are never presented as the competition demo. Prove liveness with a wall-clock overlay in the video. Any destructive-overwrite "villain scene" runs only on a disposable throwaway demo repo, explicitly labeled — never on user branches or any canonical state holding real work.
Residual risk: none if demo script enforces it.

## FC-10. Eligibility and scope facts (not failures of design, but of entry)
Trigger: The terms restrict entry to adult legal residents of the US/Canada [X: E-X017, research/codex/evidence.md]; whether the user or any collaborator meets this is NOT established by repo evidence — a Europe/Berlin timezone is not evidence of residency either way. Also: submissions are non-confidential and Cloudflare may build competing products [R].
What happens: Eligibility is unresolved; if an ineligible entry were made anyway, disqualification is possible per terms [R]; effort optimizing for prizes could be wasted. Per user steering (coordination/USER-STEERING.md; experiment/USER-INSTRUCTIONS.md message 6): continue the work, assess broad product value separately from contest constraints, do not represent eligibility as established, and note the user may find an eligible US collaborator.
Mitigation/decision: not mine to make. Record the unknown; the orchestrator/user decides between (a) entry attempt pending an eligible entrant, (b) portfolio/demo build judged by our own criteria. AGENTS.md requires truthful reporting; eligibility stays explicitly open.
Residual risk: minimal if handled as (b) until an eligible entrant exists.

## Top unknowns to resolve with a 30-minute spike (two shells, one repo)
1. Non-fast-forward push → expect reject; force-push → record whether allowed (FC-1/3.2).
2. `git push origin HEAD:refs/heads/agent-a` branch creation; `git ls-remote` listing (3.1).
3. Notes: push `refs/notes/commits`, fork with `defaultBranchOnly:true`, check notes presence (FC-5).
4. `pushed` event end-to-end: wrangler queues subscription → consumer receives schema v1 (FC-4).
5. isomorphic-git commit+push from a Worker under `wrangler dev` with `remote = true` [R] (FC-7).
