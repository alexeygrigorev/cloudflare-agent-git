# Codex independent ranking — round 1

2026-10-02. Author: codex-principal. These are judgments on Claude draft v1, not measured adoption, prototype quality or peer agreement. Exact input SHA-256: `c68de131359de508a30a75f606fcf5f5c82e3a37f8330bac4aed1daa95cef6f7`. All 20 IDs scored independently; no final shortlist or approval.

## Seven requested axes

Each axis uses 1–5: 1 weak/unsupported, 3 plausible with material unknowns, 5 strong for the specified buyer. P = pain/severity; E = evidence quality (first-hand corroboration/limitations, not number of marketing posts); N = novelty against working incumbent capabilities; CF = Workers/Artifacts fit; F = feasible real concurrent-agent MVP by October 14; D = potential clarity/strength of a 5–10 minute demonstration; A = adoption plausibility, including migration and task-definition burden. F=3 is conditional, not a verified feasibility gate. No candidate has passed a live Artifacts concurrency demonstration.

Broad-value `/100 = 20*(.25P+.20E+.20N+.20A+.15CF)` excludes deadline/demo so longer-term storage/recovery research survives. Contest proxy `/100 = 20*(.50N+.25coordination+.25D)` mirrors 50/25/25 weights, but N and D are prospective proxies: prototype quality and actual UX remain untested. Neither score is a market estimate. Order ties by evidence, adoption, then ID.

| ID | Approach | P | E | N | CF | F | D | A | Broad value | Contest proxy |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A01 | Live Integration Radar | 5 | 4 | 3 | 5 | 3 | 5 | 3 | 80 | 80 |
| A02 | Lease-bound landing claims | 3 | 3 | 2 | 4 | 4 | 3 | 2 | 55 | 60 |
| A03 | Merged-state gate + reapplication | 4 | 3 | 2 | 4 | 2 | 4 | 2 | 60 | 65 |
| A04 | Semantic contract sentinel | 4 | 3 | 2 | 3 | 2 | 4 | 2 | 57 | 60 |
| A05 | Fork tournament | 3 | 3 | 2 | 5 | 4 | 5 | 3 | 62 | 65 |
| A06 | Change-story review queue | 5 | 4 | 3 | 3 | 4 | 4 | 3 | 74 | 65 |
| A07 | Maintainer inbound quarantine | 5 | 4 | 3 | 4 | 3 | 4 | 2 | 73 | 65 |
| A08 | Independent reviewer panel | 3 | 3 | 1 | 3 | 5 | 3 | 3 | 52 | 40 |
| A09 | Exact-SHA receipts | 4 | 3 | 2 | 4 | 4 | 4 | 3 | 64 | 55 |
| A10 | Durable handoff/context branch | 4 | 3 | 2 | 4 | 4 | 4 | 3 | 64 | 60 |
| A11 | Merge decision ledger | 3 | 3 | 3 | 4 | 4 | 4 | 3 | 63 | 65 |
| A12 | Quarantine forks/capability tokens | 4 | 4 | 2 | 5 | 4 | 4 | 3 | 71 | 60 |
| A13 | Session footprint undo | 4 | 3 | 2 | 4 | 2 | 4 | 2 | 60 | 55 |
| A14 | Preview/runtime isolation | 5 | 4 | 3 | 5 | 3 | 5 | 4 | 84 | 75 |
| A15 | Fast verification lane | 3 | 3 | 1 | 4 | 4 | 3 | 3 | 55 | 40 |
| A16 | Task-aware storage workspaces | 5 | 4 | 3 | 4 | 3 | 4 | 4 | 81 | 65 |
| A17 | Fork task board | 2 | 2 | 1 | 4 | 5 | 3 | 2 | 42 | 40 |
| A18 | Multi-repo recovery | 4 | 3 | 3 | 5 | 2 | 4 | 2 | 67 | 70 |
| A19 | Maintenance swarm | 3 | 3 | 2 | 5 | 4 | 5 | 3 | 62 | 70 |
| A20 | Earned autonomy policy | 2 | 2 | 2 | 3 | 3 | 3 | 2 | 43 | 50 |

Broad-value order: A14, A16, A01, A06, A07, A12, A18, A09, A10, A11, A05, A19, A03, A13, A04, A15, A02, A08, A20, A17.

Contest-proxy order: A01, A14, A19, A18, A05, A06, A11, A07, A16, A03, A02, A10, A12, A04, A09, A13, A20, A08, A17, A15.

## Reasons and evidence limits

- A14 leads broad value: concrete device/server/data collisions E-X002/E-X005 and Claude E-C321/E-C322/E-C363, plus visible independent runtime state. Existing simulators/container tooling solve parts; per-fork Workers preview integration and actual independent data need a spike. My provisional build recommendation is **A14 runtime/data isolation**, conditional on that spike and comparison with ordinary containers/unique ports. Keep A01 as the strongest alternative.
- A16 is second: U7 is direct user pain, stronger for this user's task than aggregate invented market demand. Synthetic source/dependency measurements demonstrate a mechanism, not a population frequency. F=3 applies to task-aware sparse source + immutable dependency reuse; remote/lazy arbitrary tooling remains F=2. The protocol page lists v1 `filter` unsupported; actual v2/ArtifactFS behavior is untested (late correction in pro-integration-round-1.md). Sparse checkout is not zero checkout. The completed small Worker starter benchmark (package-storage-validation.md) found pnpm dependency-tree union approximately 49.97% below the two individual trees summed, with concurrent tsc passing. This strengthens the existing baseline; mutable builds and mid-size repo parity remain open. N=3 is a hypothesis for a differentiated task/remote workflow, not earned novelty for simply adding pnpm. Reopen if ordinary pnpm/worktree setup is sufficient, rather than inflate novelty.
- A01 has corroborated integration pain (Claude E-C101–E-C110, E-X018 retrospective study). None establishes agents respond to WIP warnings. The synthetic clean-merge failure establishes a reproducible hazard, not a live-agent success. Originality depends on changing an agent's work before completion; at-landing testing alone is merge queue behavior.
- A06/A07 have strong maintainer review evidence, but A07 adoption=2 prices permission, GitHub migration and anti-AI policies. E-C210–E-C218 are non-buyers; internal/AI-accepting teams remain possible. A06 must beat existing diffs/review tools at review time, not collect more transcripts.
- A12 is a useful safety primitive and Cloudflare fit, with commodity novelty. Existing fork-per-agent guidance prevents calling it a new product solely from plumbing. A09/A10/A11 likewise need a distinct buyer decision beyond routine metadata. Entire's current independent checkpoint refs and implemented experimental commands count as competition; outdated shared-branch descriptions do not.
- A03 loses lead status until A/B repair versus reapplication under the same accepted policy. Reject unsupported 10–100x token-cost assertions as measurements; adoption tax from versioned intent is plausible. A04 must catch an extra failure beyond merged-tree tests, or lower latency/cost at equal coverage. Static probes are neither formal proofs nor universal API compatibility.
- A13 F=2 reflects cross-repo side effects, dependency chains, migrations and unrelated later changes: an atomic global undo claim cannot be supported by ordinary revert. A18 also needs resumable recovery, not distributed-atomic-publication claims. A19 must beat a serial merge queue/Renovate baseline on an actual batch task. A05 must beat deployed best-of-N tools; N=2 prices the existing baseline.
- A08/A15/A17/A20 remain low-ranked: reviewer fanout, CI triggers, a task board and agent scores have incumbents or thin buyer evidence. Do not pad the six with them just because their implementations are small.

Scoped negative evidence: E-X007/E-X013 show independent task isolation succeeds; they weaken isolation-only novelty and do not refute overlapping semantic-integration pain. E-X003/E-X006/E-X009/E-X010/E-X011/E-X012 are version-specific incidental tool behavior; E-X008 mixes structural stale-base coordination with possible vendor behavior. None of those incidental reports alone earns a shortlist slot. E-X004 is a concern, not author reproduction; our local synthetic fixture supplies only that reproduction. E-X018 estimates textual conflicts retrospectively, not live behavioral breakage.

## Selection status

Recommend comparative spikes for A14, A16 and A01 first; preserve all 20 with explicit reopen tests. The top broad scores are not an exact-six proposal: A12 is shared infrastructure, and A06/A07 may share a buyer/workflow. Late checkpoint: two bilateral rounds are complete; five Pro outputs arrived and first integration is in pro-integration-round-1.md. Artifacts/live-agent feasibility, remaining source checks and same-digest approvals are still open. No final primary or consensus claimed.
