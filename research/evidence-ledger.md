# Evidence ledger (integrated index)

Integrator: Claude principal (ownership per C-R1-OWN; Codex granted copy/reference permission for E-X items, message 01a0fdd7). Version 1, 2026-10-02 Europe/Berlin.

This file indexes evidence by pain theme. Full rows (URL, author, date, verbatim quote, persona, severity, workaround, verification status) live in the source files below; IDs are stable. Inclusion here does not establish prevalence: these are qualitative first-hand reports, vendor claims and docs. Promotional (Show HN / builder) items are marked weaker in the source files.

## Sources

| Prefix | File | Owner | Count | Verification method |
|---|---|---|---|---|
| E-C001-E-C015 | research/claude/source-announcement.md, rules-verification.md | Claude | 15 | Fetched announcement + rules PDF |
| E-C101-E-C170 | research/claude/hn-evidence.md | Claude | 70 | Exact-substring check against HN Algolia API |
| E-C201-E-C252 | research/claude/maintainer-review-evidence.md | Claude | 52 | 47 primary fetched; E-C236, E-C237, E-C241, E-C250, E-C252 secondary press only |
| E-C301-E-C365 | research/claude/workflows-competitors.md | Claude | 65 | Fetched docs/repos; E-C344, E-C348, E-C350 UNVERIFIED |
| E-C4xx | research/claude/reddit-crosscheck.md | Claude | pending | Lane still running at v1 |
| E-X001-E-X017 | research/codex/evidence.md | Codex | 17 | Opened bodies/API; Reddit absolute dates often unverified |
| E-G001-E-G007 | research/grok/challenge-r1.md | Grok | 7 | Opened docs/HN; E-G007 synthetic local measurement |
| E-A001-E-A012 | research/antigravity/evidence.md | Antigravity | 12 | See spot-check below |
| U7 | experiment/USER-INSTRUCTIONS.md message 7 | User | 1 | First-hand user statement |
| Orchestrator | research/orchestrator/social-evidence.md | Orchestrator | ~10 | Search-level X/LinkedIn paraphrases; arXiv 2607.04697 abstract |
| Pro | research/orchestrator/chatgpt-pro-registry.md | Orchestrator | 0 | All four investigations pending at v1; must be incorporated or recorded unavailable before sign-off |

### Claude spot-check of peer evidence (2026-10-02)
- E-A001 (HN 47390794, jovanaccount) and E-A002 (HN 45042294, sobukwelu): quotes confirmed via Algolia; both are promotional posts (own product/blog).
- E-A003: confirmed, but it is a commenter quoting an OpenAI concept; weak as pain evidence.
- E-A007 (HN 49158223, radarsu): post confirmed (Intentic.dev, moved agents into docker); "shared checkout corruption" not visible in the opening text; treat as PARTIAL.
- E-A010: cites a 2024-01-02 curl blog post for a claim about forge switching; the forge-switch statement in our ledger is E-C203 (2026). Treat E-A010's paraphrase as UNVERIFIED until the exact passage is shown.
- E-A012: no URL, cites "empirical studies" and "100% deterministic regression detection". EXCLUDED as evidence (no source).
- E-A004-E-A006, E-A008: duplicate official docs/rules already held as E-C305-E-C308, E-C014.

## Themes

### T1 Integrating parallel agent work (textual + semantic conflicts) — strongest, structural
- Pain: E-C101, E-C102, E-C103 (~1/3 time integrating), E-C104, E-C106, E-C107, E-C110, E-C111, E-C135, E-C158; E-X004 (concern), E-X008 (stale base, 60 branches); E-G004, E-G005 (decision conflict worktrees don't catch); E-A001, E-A002; Codex synthetic fixture (research/codex/local-validation.md); arXiv 2607.04697 (cross-agent pairs higher textual conflict rate but only 0.5% of co-active pairs — limits prevalence claims).
- Gap: nobody continuously integrates N heads (E-C320 best-of-n "does not merge changes back"; E-C358).
- Competitors: GitHub merge queue E-C341, Graphite/Mergify/Trunk/Aviator E-C342/E-C343, Copilot resolve conflicts E-C344, Weave E-C346, Foremerge (E-G004), Collide (orchestrator).
- Negative: modular architecture avoids conflicts (HN 46729649, not itemized); arXiv low co-activity rate.

### T2 Coordination before edits — medium, contested
- Pain/workarounds: E-C105, E-C109, E-C362, E-C328 (GitButler locks), E-C169, E-C108.
- Negative: E-C113 (coordination tooling doesn't earn its keep), E-C114 (informed agents ignore shared memory), E-C112 (scope unknowable upfront).

### T3 Review burden and contribution trust — strongest volume, crowded remedies
- OSS: E-C201-E-C203 (curl), E-C205 (GitHub "Eternal September"), E-C207-E-C209 (Ghostty/Vouch), E-C213 (LLVM extractive), E-C214 (kernel unverified reports), E-C219 (autonomous agent retaliation), E-C220 (1,836-vote block request), E-C223, E-C224, E-C234/E-C235 (tldraw), E-C238 (Coolify anti-slop), E-C249 (Node 21.7k-line PR); HN E-C121-E-C125, E-C152 ("DoS").
- Teams: E-C228 (Faros +91% review time, vendor), E-C230 (SO 66% "almost right"), E-C231, E-C232, E-C233 (DORA amplifier), E-C247 (reviewers want intent).
- Policy bloc (non-buyers): E-C210, E-C211, E-C212, E-C217, E-C218.
- Counter/competitors: E-C227 (curl merges ~50 AI-analyzer fixes), E-C250 (Sashiko), E-C242 (Cloudflare internal review 48k MRs), E-C243/E-C244 (Greptile, 79% nits), E-C245/E-C246 (Copilot review/approvals), E-C206/E-C226 (GitHub caps/kill-switch), E-C203 (forge switch won't help curl).

### T4 Destructive / unsafe git operations — structural part + incidental vendor bugs
- Structural: E-C135 (stash/reset races in shared tree), E-C136, E-C138, E-C140 (prompt rules ignored), E-C139, E-C143.
- Incidental (vendor bugs, several fixed): E-X006, E-X009, E-X010, E-X011 (fixed), E-X012; E-C137 (misattributed). See Claude challenge C2.
- Competitors: branch protection/rulesets, GitButler agentic safety E-C330, jj E-C331.

### T5 Provenance / why — wanted compact, transcripts rejected
- Pain: E-C161, E-C144, E-C129, E-C126/E-C127 (Assisted-by), E-C149, E-C214, E-C216.
- Rejection of transcripts: E-C145, E-C146, E-C147, E-C154, E-C155, E-C162, E-C163. Wanted: summarized choices E-C153.
- Competitors: Entire E-C336, Git AI E-C337, Agent Trace E-C335, SpecStory E-C338, kernel Assisted-by E-C339; Artifacts git notes E-C302/E-G002.

### T6 Verification loop, runtime and data isolation — strong, under-served for Workers
- E-C321 ("manually verifying everything is working"), E-C322, E-C363, E-C319, E-X002 (simulators/ports), E-X005 (serial app testing), E-G006 (shared Postgres; Wtdb), E-C141 (100x CI), E-C142 (batch CI), E-C139, E-C151.
- Primitives: Workers Builds previews per branch on connected repo E-C310/E-C007; CI SDK E-C311.

### T7 Workspace/worktree overhead and disk — first-hand user pain
- U7 (user); E-C157, E-C159, E-C160, E-C167, E-C168, E-C108, E-C361 (remote is the only integration point); worktree caps E-C318-E-C320.
- Measurements (synthetic, not user repos): E-G007 (deps tripled across worktrees; reflink unsupported on ext4), Codex storage-validation.md (sparse source savings dilute to 18.75% total), E-A009 duplicates E-G007.
- Caveat: git worktrees share the object DB (git-scm docs); bytes come from checkout + deps + build.

### T8 Negative evidence: "existing tools suffice"
- E-C116, E-C117, E-C118, E-C164, E-C170, E-C315, E-C352 (why not GitHub + worktrees), E-X007, E-X013, E-X014 (independent-task success; scoped to non-overlapping work, see C3), E-C148/E-C150 (jj), E-C356 (Terragon shut down 2026-02-09).

### T9 Platform constraints (Artifacts/Workers docs)
- No merge/diff/commit/ref-write in binding: E-C305, E-X015, E-A005. Push v1 receive-pack only, read/write tokens only: E-C307, E-G001. Post-hoc events: E-C308, E-G003. One repo per unit of work: E-C309, E-G002. Limits 1 GB/repo, 32 MB/blob: E-C306, E-A004. Billing date conflict Oct 14 (docs) vs Oct 15 (post): E-C311 vs E-C008. Cloudflare dogfoods session repos: E-C303.

### T10 Competition rules
- E-C009-E-C015, E-X017: deadline Oct 14 11:59 PM PDT; US/Canada 18+ (eligibility unresolved, not a research blocker); judging 50/25/25; no disparagement; LICENSE file; finalists live Oct 21.

## Open
- Reddit cross-check (E-C4xx) and ZCode red-team (research/zcode/claude-zcode-redteam/) to be indexed in v2.
- ChatGPT Pro results pending.
