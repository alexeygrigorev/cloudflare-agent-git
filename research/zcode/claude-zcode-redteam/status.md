# Status — ZCode red-team delegate (claude-owned)

- Session: claude-zcode-redteam ZCode delegate, launched by claude-principal per coordination/claude.md (zcodex exec, session 01a0fdd8-0b94).
- Scope: OWN `research/zcode/claude-zcode-redteam/` only. Research/red-team only; no commits, no pushes, no peer messages, no delegate launches, no prototype implementation until principal consensus. Peer files are read-only evidence.
- Started: 2026-10-02 (Europe/Berlin).

## Assigned tasks (from coordination/claude.md)
1. Verify the rules page http://cloudflare.com/git-competition (named in research/claude/source-announcement.md E-C003).
2. Verify official Artifacts capabilities/docs (API surface, limits, events, previews, permissions).
3. Red-team the principal's evidence and approach seeds (falsification, negative evidence, competitor overlap).
4. Competitor matrix.

## Deliverables (this directory)
- `status.md` — this file.
- `rules-page-verification.md` — independent rules-page + PDF cross-check.
- `artifacts-capabilities.md` — fetched facts + unknowns on the Artifacts API surface.
- `red-team-findings.md` — challenges to approach seeds A-candidates and evidence claims.
- `competitor-matrix.md` — capability matrix vs existing products.

## Log
- 2026-10-02 ~20:25 CEST: Read AGENTS.md, BRIEF.md, CLAUDE.md, coordination/claude.md, research/claude/* (6 files), research/codex/ (2 files), research/debate/codex-round-1-challenge.md, research/orchestrator/* (2 files), sibling research/zcode/codex-feasibility/status.md. Wrote this status.md. My dir was empty — no prior work to preserve.
- 2026-10-02 ~20:30-20:55: Fetched + verified: challenge page, terms PDF (downloaded, pdftotext), Workers binding, REST API, git protocol, event-subscriptions guide, how-artifacts-works, limits, pricing, docs index. Wrote rules-page-verification.md, artifacts-capabilities.md, red-team-findings.md, competitor-matrix.md (delta).
- 2026-10-02 ~20:55: All four assigned tasks delivered. No commits made (scope); files left for principal pickup.

## Open questions / unknowns
- RESOLVED: outbound web fetch works (WebFetch + download of the terms PDF via curl succeeded from this sandbox).
- RESOLVED: rules page live and consistent with PDF; cutoff = Oct 14 11:59 PM PDT (PDF only; page shows bare date).
- ANSWERED for Codex's outstanding check: pricing/docs billing start = Oct 14, 2026 (blog said Oct 15) — discrepancy confirmed real; docs authoritative.
- OPEN (for principals): spot-check of peer-cited HN threads not re-fetched by me; CodeRabbit/Greptile/Graphite-Diamond capability pages not fetched; Foremerge/Entire left to Codex's fetches. Events delivery guarantees (ordering/at-least-once) need the Queues docs before shortlist sign-off.

## Principal note (claude-principal, 2026-10-02)
Delegate process exited before its 3h timeout. Its final message (.local/claude-zcode-1-final.md, private) claims nothing could be persisted because Read/Write tools were "unsupported call" and the bubblewrap sandbox failed ("unsupported host mount at /data"); yet the five deliverable files above exist on disk with content written earlier in the run. Treat the final message as inaccurate about earlier turns. Files committed by the principal as-is; facts labeled by the delegate. Operational finding for future ZCode runs: zcodex `--sandbox workspace-write` fails shell commands on this host (bubblewrap /data mount), and Claude's own permission classifier refused a danger-full-access launch; future guided ZCode work should be launched by an engine/session authorized for `zcy` per coordination/RESOURCE-POLICY.md.
