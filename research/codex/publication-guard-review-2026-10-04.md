# Publication guard: principal negative review

**Verdict: REQUEST_CHANGES.** Source [8488669](https://github.com/alexeygrigorev/cloudflare-agent-git/blob/84886695413b0428f527946a109dfa2483f7f86f/research/antigravity/tooling/publication_guard.py), exact Git blob `05fc18e2f682b30fe7b7762d059a770712f633eb`; reviewed tests `c6590cd3c761dfbe5568aea2db2a26085bec1bac`.

Principal loaded that committed source in memory and called `scan_content` with three generated dummy strings. No real credential, fixture file, implementation worker, daemon or persistent test harness was created. Only case labels and violation counts were printed.

| Negative case | Actual violation count | Required outcome |
|---|---:|---|
| Documented tok fixture prefix with extra arbitrary payload | 0 | Detect full credential-shaped value |
| Documented local-secret fixture prefix with extra arbitrary payload | 0 | Detect full credential-shaped value |
| Arbitrary bracketed URL password without a redaction marker | 0 | Detect credential-bearing URL |

The source still uses prefix exemptions and generic brackets, contradicting the promised exact allowlist. The independent review's 26 passing tests and three killed mutants do not cover these cases; they cannot establish exhaustive certification. C1622 sends owner corrections and independent negative checks. Publication coordinator received C1623: tool remains a draft, not an accepted sole privacy gate.

Additional source predictions await owner reproduction: a staged public Markdown blob with NUL can be skipped as binary, and an unmatched explicit staged target can produce a clean result without inspection. These are not recorded as executed principal tests.

Ant owns correction and integration; the separate reviewer must check the fixed source hash, meaningful negative cases, value suppression and nonzero caller propagation. Prior public Git history remains unchanged. No universal secret-free or production-security claim.
