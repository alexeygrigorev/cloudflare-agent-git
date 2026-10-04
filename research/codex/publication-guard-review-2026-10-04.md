# Publication guard: principal negative review

**Historical verdict on the original source: REQUEST_CHANGES.** Source [8488669](https://github.com/alexeygrigorev/cloudflare-agent-git/blob/84886695413b0428f527946a109dfa2483f7f86f/research/antigravity/tooling/publication_guard.py), exact Git blob `05fc18e2f682b30fe7b7762d059a770712f633eb`; reviewed tests `c6590cd3c761dfbe5568aea2db2a26085bec1bac`.

Principal loaded that committed source in memory and called `scan_content` with three generated dummy strings. No real credential, fixture file, implementation worker, daemon or persistent test harness was created. Only case labels and violation counts were printed.

| Negative case | Actual violation count | Required outcome |
|---|---:|---|
| Documented tok fixture prefix with extra arbitrary payload | 0 | Detect full credential-shaped value |
| Documented local-secret fixture prefix with extra arbitrary payload | 0 | Detect full credential-shaped value |
| Arbitrary bracketed URL password without a redaction marker | 0 | Detect credential-bearing URL |

The source still uses prefix exemptions and generic brackets, contradicting the promised exact allowlist. The independent review's 26 passing tests and three killed mutants do not cover these cases; they cannot establish exhaustive certification. C1622 sends owner corrections and independent negative checks. Publication coordinator received C1623: tool remains a draft, not an accepted sole privacy gate.

Additional source predictions await owner reproduction: a staged public Markdown blob with NUL can be skipped as binary, and an unmatched explicit staged target can produce a clean result without inspection. These are not recorded as executed principal tests.

Ant owns correction and integration; the separate reviewer must check the fixed source hash, meaningful negative cases, value suppression and nonzero caller propagation. Prior public Git history remains unchanged. No universal secret-free or production-security claim.

## Corrected source and bounded adoption

The corrected [source in f9c2050](https://github.com/alexeygrigorev/cloudflare-agent-git/blob/f9c2050/research/antigravity/tooling/publication_guard.py) is Git blob `db69e55339b8c94884d2fcbb521a510675814e27`; test blob is `e3b235d0c2f60b3a49a70a6041582f09979bec0f`. Repeating the same three principal in-memory cases on this committed source produced **one violation per case**. No real credentials or persistent test fixtures were used.

I mistakenly associated those results with the review's initial `0f4cdbfb` label in message C1629. C1630 immediately corrected that association and withheld hash-specific acceptance. The named object was absent from Git. The [reconciled independent review in 817700e](https://github.com/alexeygrigorev/cloudflare-agent-git/blob/817700e/research/antigravity/reviews/REV-PUBLICATION-GUARD.md) reran against actual `db69e553`: reported 32 tests passing and negative CLI checks including staged NUL text and unmatched explicit staged paths returning operational error. These are independent reviewer results, not additional principal test executions.

**Current verdict: bounded acceptance of the corrected source as a publication tripwire alongside manual review.** The previously demonstrated bypasses are detected. This does not establish universal credential detection, whole-repository privacy or removal from historical Git commits. Seven selected reports in the review are not the entire repository.

Actual internal use: principal invoked this exact guard against `research/codex/publication-guard-review-2026-10-04.md` and `research/codex/auth-integration-evidence-2026-10-04.md`; exit code **0**, no diagnostics. C1637 and C1638 sent the bounded verdict to the implementation head and publication coordinator. The latter's DRAFT/manual-review operating label remains appropriate; no release or deployment approval follows.
