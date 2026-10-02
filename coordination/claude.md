# Claude principal coordination

Session: aplexer tag claude-principal (92336dc8), workspace /home/alexey/git/cloudflare-agent-git. Peer: codex-principal (338df944).

## Ownership (agreed C-R1-OWN, Codex msg 01a0fdd7, my ACK reply 01a0fdd8-957e)
- Claude: research/claude/, coordination/claude.md, research/debate/claude-*.md, research/approaches-20.md, research/evidence-ledger.md (integrator; Codex granted permission to copy/reference its cited evidence without editing its files).
- Codex: research/codex/, coordination/codex.md, research/debate/codex-*.md, research/shortlist-6.md, research/consensus.md integration, research/prototype-plan.md.
- ZCode delegates: research/zcode/claude-zcode-redteam/ (mine), research/zcode/codex-feasibility/ (Codex).
- Evidence IDs: Claude E-C###, Codex E-X###. Approaches A01-A20.

## Lanes
- Claude: HN, Git workflows, maintainers/review burden, competitors; light Reddit cross-check.
- Codex: Reddit, agent coordination, context/provenance, safety, Artifacts engineering feasibility.

## Status log
- 2026-10-02 R1: fetched announcement (research/claude/source-announcement.md). Independently verified official rules PDF (research/claude/rules-verification.md) — confirms Codex C-R1-RULES: deadline Oct 14 11:59 PM PDT; eligibility US/Canada legal residents 18+; judging 50/25/25.
- ZCode delegate claude-zcode-redteam launched 2026-10-02 (zcodex exec, workspace-write sandbox, timeout 3h; prompt .local/claude-zcode-1.prompt; private log .local/claude-zcode-1.log). Tasks: rules, Artifacts capabilities, red-team, competitor matrix. Note: first launch attempt with danger-full-access was refused by my permission classifier; relaunched with workspace-write sandbox (network for shell commands may be limited inside the sandbox; ZCode's own web search is internal).
- Research lanes in progress (subagents): hn-evidence.md, maintainer-review-evidence.md, workflows-competitors.md, reddit-crosscheck.md.

- R1 later: committed hn-evidence (70), workflows-competitors (65), maintainer-review (52); approaches-20.md v1 (7fb6915); debate response + challenge C1-C6 (71d5a14); evidence-ledger.md v1 (index, peer spot-checks: E-A012 excluded, E-A010 unverified).
- Messages handled (replied+acked): Codex C-R1-OWN/EVIDENCE/CHALLENGE/ENG/BROAD/STORAGE/STORAGE-MEASURED/RULES; orchestrator handoff + worktree pain; antigravity A-R1, A-R2 (A-R2 pending answer in round 2); zcode-independent Z-R1 (two copies processed once); grok G-R1-CRIT.
- Key positions: contest score = official 50/25/25; LTV separate column; reject bounded intent reapplication as spine until G5 two-arm fixture; provisional Claude six (not a vote): A01, A05, A07, A14, A13, A19. Antigravity's six differs: A01, A04, A12, A14, A16, A03.
- UX ownership (Z10): proposed Claude owns shared UX surface; awaiting Codex.
- Host disk ~96% full (Grok E-G007): do not create worktrees casually; delegates must use small fixtures.

- Spike S-C1 (77738c3): research/claude/spike-a01-merge-matrix.md.
- RESOURCE POLICY (user msgs 8-13, coordination/RESOURCE-POLICY.md, ACKed 01a0fde8-698f): Claude used sparingly; no new Claude subagents; no automatic Claude relaunch. Reddit subagent stopped (rate-limited, 0 items) and recorded as source limitation.

## Resume checklist (for any later Claude consultation)
1. `aplexer message inbox --json`; answer Codex scoring of A01-A20 and round-2 challenges (cap 3 items each, C6).
2. Answer Antigravity A-R2 (research/antigravity/round-2-challenge.md): it proposes six A01, A04(CIP), A12, A14, A16, A03; argues against A05/A07/A13/A19. Not yet answered.
3. Commit ZCode delegate outputs in research/zcode/claude-zcode-redteam/ (delegate does not commit). Delegate: zcodex exec, PID 2748719, timeout 3h from ~20:19 CEST, log .local/claude-zcode-1.log.
4. Update approaches-20.md to v2 with dispositions (merge/park/drop) and Codex/peer scores; then sign the shortlist digest independently only if the six text matches.
5. After consensus: guide ZCode (zcy/zcodex, per RESOURCE-POLICY) prototype plans/spikes in isolated worktrees; host disk ~97% full, use small fixtures.

## Requests / open questions for orchestrator
- ELIGIBILITY: Official rules s.3 restrict entrants to legal residents of US/Canada (E-C010). Orchestrator/user must determine eligibility. Research continues; no submission authorized.

## Pending with Codex
- Send A01-A20 candidate list and round-1 challenge request once evidence lanes land.
