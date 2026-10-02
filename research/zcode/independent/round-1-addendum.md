# ZCode independent round-1 addendum: peer responses, concessions, holds

Author: zcode-independent. Date: 2026-10-02. Supplements challenge-round-1.md. Peer response sources: research/debate/claude-round-1-response.md, research/debate/codex-round-1-external-responses.md (message IDs 01a0fde1-68f8, 01a0fde1-9923).

## Concessions (I withdraw or narrow)
- Z4 (merge if >70% shared primitives): WITHDRAWN. Codex is right: primitive overlap is a weak merging criterion; the correct unit is distinct user/job/output/decision/falsification test; merge only when ideas differ in presentation. Both principals already apply this.
- Z8 ("all prevention is post-hoc"): NARROWED. Authentication-time prevention at the canonical layer is real — withholding canonical write tokens means a raw client cannot corrupt canonical history at all (Codex). The precise boundary I hold: fork-level writes cannot be prevented pre-mutation; scope claims remain advisory unless enforcement binds the actual published diff. Codex agrees with this boundary.
- Z9 ("merges in Workers wasm or not at all"): WITHDRAWN as stated. A native Git runner in a Cloudflare CI sandbox or bounded local runner can merge over the documented Git protocol, with Workers orchestrating (Codex). I retain the budget warning: an external runner is the most likely Oct-13 surprise and must stay a scored feasibility line, which Codex accepts (verified external runner path + budget).
- Z10 (three agents as a requirement): CORRECTED. Two concurrent agents satisfy the source's "multiple agents" condition (E-C011 wording); ≥3 remains my demo-strength recommendation only, not a rules reading.
- Z1 (rubric): Claude confirmed the inversion empirically (A06 falls ~2→~13 under official 50/25/25) and adopted the contest-mirrored score; Codex's dual view (user-value research axes + separate contest-readiness view) is compatible and better than either single view. Z1 CLOSED as adopted-by-both in substance.

## Holds (I keep, narrowed)
- Z2 tension: unchanged; both principals' revisions (verification for AI-accepting buyers, policy bloc named non-buyer) resolve it as I asked.
- Z5: CLOSED in substance — distinct buyer/job/fixture/incumbent per approach; families are tags, not quotas (all three of us converged).
- Z9-budget and Z8-boundary as narrowed above.
- Z7 (provisional six): round-2 position — accept Claude's A09-as-shared-feature argument (receipts are infrastructure every gate needs, not a standalone buyer) and accept A03 reapplication standing or falling on the G5/C1 two-arm fixture comparison; A13 (session undo) and A19 (maintenance swarm) must still clear G2's distinct-fixture requirement (A19 currently shares A01's fixture).

## New user pain incorporation (worktree storage, orchestrator message USER-PAIN-WORKTREE-STORAGE-20261002)
- Independent challenge to lane A16 (storage efficiency): set the success threshold NOW, before more measurement: adopt only if measured physical-bytes savings exceed ~40% of total workspace surface at build/test parity and creation latency does not regress; otherwise park with a reopen criterion. Rationale: two independent measurements (Grok G8: 75% source but 18.75% total savings; Codex storage-validation: same dilution) suggest local tricks plateau; the differentiated version is lazy remote workspaces (Artifacts blobless hydration, E-C304) — which is also the version with a real buyer for agents that don't need local checkouts at all. Falsification test: 1/5/10/20-workspace fixture, physical vs apparent bytes, deps/build-dominant workload, shared-cache (pnpm store) as the killing baseline — if package-manager caches resolve the pain with less friction, no forge product survives.
- Constraint adopted: host volume ~96% full (Grok G8 note) — no head may spawn free-standing worktrees; use existing fixtures.

## Process note
This environment double-executes my shell commands under concurrency (duplicate commits 0621e1e/0716783, duplicated event line, nested-dir race). Content is correct; duplicates are cosmetic. I will keep commands idempotent and verify state rather than assume.
