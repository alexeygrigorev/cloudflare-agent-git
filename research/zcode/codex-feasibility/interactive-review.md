# Interactive review round — codex-feasibility-review (2026-10-02 late)

Independent bounded correction/review of my owned packet. Not a principal or implementation lane; no new empirical run.

**Identity record (before any messaging):** native `aplexer whoami` = session `cf3e7fb7-53e0-4b7a-9fd5-9f44da7cc0a7`, selector `/home/alexey/git/cloudflare-agent-git:codex-feasibility-review`. Verified at session start; no `--from` overrides; no pane injection. The earlier inbox read/ACK round (3 messages, all read-acked, no semantic replies) ran under the inherited binding `338df944/codex-principal`; per the process correction in research/codex/zcode-guidance-review.md that was a **misbinding** — read-ACK does not establish agreement, and this delegate does not access the principal mailbox without explicit coordination. The current session is genuinely separate.

**Scope kept:** only `research/zcode/codex-feasibility/*.md` edited; peer files untouched; no subagents, installs, worktrees, purchases, Cloudflare calls, commits, or pushes; reads + Markdown only.

## Corrections applied (guidance-review items 1–5 + current directives)

1. **Legacy fetched labels retired.** All `[F]` markers converted to `[R]` (recorded-but-unverified) across feasibility.md, failure-cases.md, mvp.md; §1/§2 headers no longer claim "verified"; my original fetch results were never recoverable, so nothing is claimed as independently fetched by me. Doc-absence claims scoped to the inspected pages (not proven API-absence).
2. **Contradictory recommendation deleted.** feasibility §3.3 no longer suggests keying receipts on after-SHA or timestamp ordering. Receipts now carry the full tuple incl. `policyVersion + policyCommitSha + policyDigest`, `oracleDigest`, `environmentDigest`, `runnerIdentity`, `attemptId`, `generation`; append-only, chained by `parentReceiptId`, validated against Git ancestry. Generation ordering explicit (merged tree of gen k = base of gen k+1); policy versions monotonic, human-approved, never compared across. Delivery-dedup key includes generation + policy digest and is invalidated on either change (FC-4).
3. **Fence hardened against crash/lease expiry.** Publisher must present a current lease/generation and current policy version; superseded generation/policy rejected **even when canonical HEAD is unmoved** (feasibility §3.2, FC-2, mvp cut list). Head re-check + non-force FF alone is not lease authorization.
4. **v1-scoped filter qualification.** "filter/include-tag unsupported" now scoped to documented **v1** capabilities; Artifacts v2 negotiation untested [U]; ArtifactFS blobless hydration with eager fallback recorded [X: E-X021]; no blobless assumption or budgeting without measurement (feasibility §2, FC-7, spike-plan §1.1). Sparse checkout remains a legitimate existing control.
5. **Independent oracle.** Verdict computed only by the platform-owned runner on the baseline-owned policy; oracle version pinned by digest in every receipt; identical oracle + acceptance checks across A03 arms; candidates never self-certify (feasibility §3.3, FC-11, mvp, spike-plan §4).
6. **HMAC scope corrected.** Platform-side integrity only; explicitly **not public proof**; independent public verification would need an asymmetric signing path or trusted verifier (not implemented); signing secret never disclosed (FC-5, mvp).
7. **readOnly-canonical replacement downgraded** to an unresolved contingency: not implemented, not validated, repository-identity-changing, dependent on an undesigned publication contract (feasibility §3.2/§5, FC-2, mvp unknowns).
8. **MVP one-liner corrected:** no longer "receipt proving commit + passing tests"; attests the trusted runner's observed result (mvp.md).
9. **Boundary fix:** spike S1 no longer proposes extending peer-owned `research/codex/merge-fixture.py`; implementation requires a named isolated worktree scope or an acknowledged handoff (spike-plan §3).
10. **Sample-size honesty:** A03 tie = "no observed benefit in this sample," never statistical equivalence; parity must be measured by actually running builds/tests; usage reported when available, unknown otherwise (spike-plan §2–§4).

## A14 and A01 incorporation (my files only)

- **A14 incumbent/negative control** folded into comparative-spike-plan §2 and new §6.1: the real incumbent is Cloudflare Workers Previews with automatic per-Preview Durable Object/Container isolation and distinct D1/KV bindings (E-X023, docs updated Sep 22); Version URLs (production resources) are the trap. Recorded local fixture: shared-binding clobber reproduced; ordinary separate-resources control passes with no new platform; no measured product advantage. Falsification = beat the real Previews baseline; remote comparisons use real Previews, never misconfigured Version URLs.
- **A01 uptake-protocol clarifications critiqued** in comparative-spike-plan §6.2 (dedup/generation operationalization, pre-registered count-funnel definitions and prevention/recovery boundary, equal-conditions + sample-size honesty, behavior-adjustment metric). No edits to `research/zcode/independent/a01-uptake-protocol.md`.

## No fake results, no consensus

No spike, dry run, or measurement was executed by me; all plans remain plans. Nothing claims or assumes consensus — shortlist and lane decisions are principal-level. Eligibility (US/Canada residency of any entrant) and billing start (Oct 14 [R] vs Oct 15 [X]) remain unresolved and are kept explicit.

## Remaining unverified (explicit)

- Every `[R]` item in my packet (my original fetches never verifiable): blog/rules/terms specifics, binding/REST signatures, preview caps/defaults, Sandbox example details, pricing numbers.
- Artifacts remote semantics (spike S4, deferred, needs credentials): force-push/non-FF acceptance (fence load-bearing), `ls-remote`/ref listing, `refs/notes/*` acceptance and fork survival, `defaultBranchOnly`-unset behavior, event delivery in practice, isomorphic-git memory ceiling.
- v2/ArtifactFS lazy transfer and retained bytes — untested anywhere in this repo.
- A16 real-repo storage/parity numbers (S2) and A03 arm outcomes (S3) — planned, not run.
- Sandbox snapshot/persistence semantics; preview-per-branch provisioning for forks.

**Delivery notices:** sent to `desktop-orchestrator` and `codex-principal` after whoami verification (durable inbox delivery, no pane injection); IDs not captured in send output except the follow-up correction notice `01a0fe1c-c7c7-7a61-baa3-5ff5ddf7ea33` — recorded in status.md §Delivery record.
