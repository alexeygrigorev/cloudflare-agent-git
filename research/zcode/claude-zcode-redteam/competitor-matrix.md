# Competitor matrix — delta (claude-zcode-redteam, 2026-10-02)

This is a delta on claude-principal's matrix (workflows-competitors.md, E-C3xx) and Codex's differentiation table — not a duplicate. Rows the principals' matrix lacks, with my verification status.

| Product | Multi-agent-git relevant capability | Licence / access | Gap for concurrent agents | My verification |
|---|---|---|---|---|
| **CodeRabbit** (docs.coderabbit.ai) | AI PR review: line-by-line feedback, summaries, and "Triage — a self-updating cross-repository queue that prioritizes pull requests by value and risk"; free for OSS | Service closed | PR-shaped, single-change review; no competing-attempts comparison, no merge arbitration, no agent-facing concurrency surface | E-RZ301: docs site + Triage description confirmed via search 2026-10-02; capability pages not fetched |
| Graphite AI reviewer ("Diamond") | AI review on GitHub PRs | Service closed | Same PR-shaped limit as CodeRabbit | UNVERIFIED — name/product not fetched this pass; verify before citing |
| Greptile | AI code-review bot on PRs | Service closed | Same category as CodeRabbit | UNVERIFIED — not fetched |
| Cloudflare git notes (blog claim) | Notes/metadata on git objects "without mutating the objects" (E-C302) | n/a (platform feature) | No notes method in current binding/REST docs (E-RZ101/102) — usable via plain git refs only | Discrepancy verified by me across fetched docs today |

Rows to *demote* in the principal's matrix (consistency, not contradiction): none found — spot checks of the table's structure against my independently fetched Artifacts facts (binding/REST/git-protocol/events/limits/pricing) agree with E-C305..E-C312.

Coverage gaps in both principals' current scans (candidates for R2, not blockers):
1. **Review-market lane (seeds 6/8/20) has no competitor row except implicitly** — CodeRabbit/Graphite/Greptile belong there before any shortlist decision.
2. **OSS agent platforms with their own git workflows** (e.g. OpenHands) unexamined — they integrate agents to git without a forge; relevant to "platform vs library" positioning.
3. **Foremerge / Entire** are covered by Codex (fetched) — cross-accepted, no duplication needed.

Sources: docs.coderabbit.ai (search-confirmed); all Artifacts facts per artifacts-capabilities.md E-RZ1xx (fetched 2026-10-02).
