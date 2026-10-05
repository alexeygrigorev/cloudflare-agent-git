# Smallest testable MVP — recommendation (doable by Oct 14)

Author: ZCode feasibility/red-team delegate (codex-owned), 2026-10-02. Research only; build waits for principal consensus.
Design constraints honored: Workers + Artifacts required [R]; "multiple agents working on changes concurrently" is the minimum bar and 25% of judging [R]; permissive license; 5–10 min video + run instructions; must be demonstrable live.

## Name / one-liner
**Consensus Grove** (placeholder): a Git platform where every agent gets its own fork-grove, and a single gatekeeper grows the trunk — nothing lands on `main` without a provenance receipt: an attestation by the platform's trusted runner that the accepted policy ran over a specific merged tree and observed a specific result (it attests the runner result, not code correctness).

## Architecture (primitives recorded in feasibility.md §2 — recorded from docs, not independently re-verified)
```
                  ┌──────────────────────────── Workers (platform) ───────────────────────────┐
 task board UI ──▶│ /sessions: create baseline repo (ARTIFACTS.create)                         │
 (Workers static  │ /agents/{id}: fork baseline → agent repo; mint write token ttl=3600;       │
  assets + D1)    │   spawn Sandbox container (git-repo-per-sandbox pattern [R]); inject remote │
                  │ integrator DO: lock per baseline; on cf.artifacts.repo.pushed [R] via       │
                  │   Queues event subscription [R]: fetch proposal → 3-way merge [P] → run     │
                  │   tests in Sandbox [R] → push main → write receipt (git note on baseline    │
                  │   [F-endorsed] + D1 row, HMAC-signed [P])                                   │
                  └────────────────────────────────────────────────────────────────────────────┘
 Storage: Artifacts (code, notes, context files) + D1 (task board, receipt ledger) + R2 (test logs, >32MB-safe)
 Agents: **≥2 actual concurrently running coding agents** (real headless agent-CLI processes, e.g., two different vendors) in Sandboxes — actually concurrent processes [R: Sandboxes host real agents]. Scripted task-runner loops are bring-up-only and always labeled synthetic fixtures; the competition demo runs real agents (FC-9).
```
Identity/auth: platform session → per-agent short-lived repo-scoped write tokens [R]; everyone else read-only [R]; publishing to `main` only via integrator [P]; demo previews Cloudflare Access-gated [R].

## Why this shape (and not alternatives)
- Fork-per-agent instead of branch-per-agent: it is Cloudflare's own best practice [R], makes isolation structural, and dodges the no-branch-listing gap (each agent repo is addressable by name).
- A Durable-Object integrator instead of server-side merge: Artifacts has no merge API [R]; the DO lock serializes publishers, and the publication fence (canonical token held only by the publisher + remote-head re-check + non-force fast-forward, FC-2/feasibility §3.2) is what actually blocks stale heads and stale writers — the lock alone does not.
- Git notes + D1 receipts: notes are officially endorsed agent metadata [R]; D1 makes the demo dashboard trivial; HMAC gives platform-side integrity of the runner result only — not public proof (independent public verification would need an asymmetric signing path or a trusted verifier; not in the MVP, secret never disclosed) — and never code correctness. Receipt identity = full tuple {base, candidate, merged SHAs, merged tree, policy version + policyCommitSha, oracleDigest, environment digest, runner identity, attemptId, generation} (FC-4/feasibility §3.3).
- Policy gate: acceptance tests are baseline-owned and versioned; candidates cannot pass by altering their own tests; human-approved policy bumps for intended API changes only (FC-11).
- Real concurrency via Sandboxes, not simulated timers: judges score concurrency 25% [R]; Sandboxes officially host coding agents [R].

## MVP cut list (build order, ~12 days)
1. **Day 1–2 — pre-flight spike** (failure-cases.md §top-unknowns): non-FF/force-push behavior, branch creation + ls-remote, notes push/fetch + fork behavior, queues `pushed` event end-to-end, isomorphic-git push from `wrangler dev` (`remote = true` [R]). Go/no-go gate.
2. **Day 3–4 — platform skeleton**: wrangler config with `artifacts` + `sandbox` + D1 bindings; `/sessions` (baseline create) + `/agents/{id}` (fork + token + sandbox spawn). Two concurrent sandboxes cloning/editing/pushing distinct files = first end-to-end concurrent proof.
3. **Day 5–6 — integrator DO + receipts**: queue consumer → DO lock + publication fence (current publisher lease/generation + current policy version + head re-check, non-force FF — a stale generation/policy is rejected even if HEAD is unmoved) → merge → test gate running the **baseline-owned, versioned policy suite** — for bring-up, a deterministic synthetic fixture (pattern: research/codex/merge-fixture.py), clearly labeled synthetic, never presented as the competition demo → push + note + D1 receipt with the full identity tuple. Handles one conflict with reject-receipt.
4. **Day 7–8 — real agents (mandatory for the demo, not optional polish)**: run ≥2 real headless coding-agent CLIs concurrently inside Sandboxes on tiny issues, same pipeline. Synthetic scripted runners may remain only for labeled bring-up, never the demo (FC-9).
5. **Day 9 — task board UI**: D1-backed board showing agents live (sandbox heartbeats), branch activity stream (`pushed` events), receipt cards (commit SHA ✓ tests ✓/✗, agent, base→merged).
6. **Day 10 — permission story**: token TTLs, revocation button, Access-gated preview of landed `main`, read-token reviewer view.
7. **Day 11 — demo polish + video**: script below; record; LICENSE (MIT) + run instructions (`npm create cloudflare` scaffold path, wrangler deploy, three env vars).
8. **Day 12 — buffer** (beta churn FC-8, video retakes).

Demo repos stay <5 MB (FC-7); test logs to R2; receipts identified by the full identity tuple, event-delivery dedup handled separately (FC-4).

## 5–10 minute demo script (maps to judging weights)
1. 0:00–1:00 Problem: agents clobber each other on shared Git; show FC-1 live on a **disposable throwaway demo repo, explicitly labeled** — never on user branches or canonical state holding real work (FC-9 rule) — the villain scene. [originality framing]
2. 1:00–2:30 Create session: baseline repo appears (Artifacts), **≥2 real coding-agent CLIs** spawn in visible Sandboxes and start working — wall-clock overlay proves simultaneity. [concurrency 25%]
3. 2:30–5:00 Live pushes → `pushed` events stream on the board → integrator merges A (tests pass, receipt lands, `main` advances), rejects B (conflict receipt with exact overlapping hunks), rebases C onto the new `main` and re-runs tests before landing. [concurrency + conflict handling]
4. 5:00–7:00 Provenance: click a `main` commit → git note + signed receipt (full identity tuple: base→merged SHAs, merged tree, policy version + policy commit digest, oracle digest, environment digest, runner identity; test log link in R2); `git clone` the baseline, `git notes show` on camera. Receipt attests the runner result — the narration must not claim it proves correctness. [originality + trust]
5. 7:00–8:30 Permissions: agent token expires mid-session (revocation button) → push fails cleanly; Access-gated preview URL of landed work. [ease-of-use/UX 25%]
6. 8:30–9:30 Handoff: "continue this task" forks the session repo with a handoff note; new agent resumes with full context visible. [context preservation]
7. 9:30–10:00 Run instructions + architecture one-pager. Never claim Artifacts enforces branch-level permissions — the platform does (credibility guard, FC-6/§3.4).

## Explicit unknowns carried into the build (spike or accept risk)
Force-push/non-FF semantics (load-bearing for the publication fence — if non-FF pushes are accepted, canonical protection needs a different mechanism; the readOnly-canonical replacement idea is an unimplemented contingency, not a fallback); notes survival across forks; `defaultBranchOnly` unset behavior (tags/notes); queues event schema + delivery semantics; isomorphic-git memory ceiling; exact billing-start date (Oct 14 [R, pricing page] vs Oct 15 [X, announcement E-X016]) — unresolved, keep explicit; **eligibility UNRESOLVED** — terms restrict entry to adult US/Canada legal residents [X: E-X017], user residency/collaborator status unknown, do not represent eligibility as established (FC-10); Workers Paid must stay active through Oct 21 if finalist.
