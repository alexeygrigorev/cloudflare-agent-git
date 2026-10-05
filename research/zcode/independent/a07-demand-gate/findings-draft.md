# A07 demand-gate findings — DRAFT (evidence + capability only, no verdict)

Unit: z-a07-demand-1 | Owner: zcode-independent | Date: 2026-10-03
Prior work extended (not re-derived): `research/approaches-20.md` §A07, `research/evidence-ledger.md` A07/E-C2xx,
`research/claude/maintainer-review-evidence.md` (E-C201–E-C252), `research/claude/standup-2026-10-03.md` §3/A07 bullet.
Search: 6× `xai_search.py --tools web_search` labels a07-s1…s6 (never x_search). Web content is evidence, never instructions.
Honest labels: VERIFIED-FULL = primary source fetched in prior ledger session; VERIFIED-PARTIAL = credible secondary/report
with direct URL but not primary-fetched by this unit; UNVERIFIED = snippet/claim only. No demand/viability verdicts.

## S1 — FIRSTHAND MAINTAINER CASES (8; AI-accepting focus, bans marked as boundary)

### S1-1 Homebrew: AI-accepting with guardrails (Responsible AI Usage, mid-2026)
- URL: https://docs.brew.sh/Responsible-AI-Usage ; PR template change https://github.com/Homebrew/brew/pull/21510 ; contrib https://github.com/Homebrew/brew/blob/main/CONTRIBUTING.md
- Date: policy ~mid-2026; AI checkbox merged Feb 2026 (per search s6)
- First-hand symptom: needs disclosure (tool/model), full human review before maintainer time, human replies only, 1-open-AI-PR limit for non-maintainers. Quote (docs, via search): n/a verbatim — paraphrase only.
- Existing workaround: mandatory disclosure + AI checkbox in PR template + AGENTS.md guidance; human-in-loop rule.
- Affected persona: package-manager maintainers + one-time contributors using LLMs.
- Frequency/severity: standing policy (ongoing volume, not a single incident); severity moderate (process cost, not shutdown).
- Verification: VERIFIED-PARTIAL (docs + PR URLs concrete; verbatim quotes not primary-fetched this session). Extends ledger (no prior Homebrew entry).

### S1-2 Excalidraw: >2× PR surge Q4-2025 vs Q3, one-shot fixes lacking context
- URL: https://tldraw.dev/blog/stay-away-from-my-trash (tldraw maintainer account citing Excalidraw volume)
- Date: Jan 2026 post describing Q4-2025 surge
- First-hand symptom (second-hand via tldraw maintainer): formally correct diffs with poor context and no follow-up; review capacity overwhelmed.
- Workaround: issues-first workflow emphasis; discussion in tldraw/Excalidraw maintainer circles.
- Persona: company-backed OSS canvas maintainers.
- Frequency/severity: >2× quarterly PR volume; severity high (review queue regime change).
- Verification: VERIFIED-PARTIAL (tldraw post is primary and ledger-VERIFIED as E-C235; Excalidraw numbers inside it not independently fetched). New vs ledger (ledger cites Excalidraw only in passing).

### S1-3 FastAPI: repeated automated submissions framed as "denial-of-service attack on human effort"
- URL: https://groundy.com/articles/are-ai-generated-prs-killing-open-source/ (reporting maintainer framing); https://www.popularai.org/p/ai-generated-pull-requests-open-source-maintainers
- Date: 2025–2026 coverage
- Symptom: low-effort AI PRs closed on sight; repeat accounts blocked.
- Workaround: close + block; explicit low-quality-PR guidelines.
- Persona: single-maintainer-led framework project.
- Frequency/severity: recurrent; severity moderate-high.
- Verification: UNVERIFIED (maintainer quote via secondary roundup; primary FastAPI guideline page not fetched). Flagged as follow-up fetch.

### S1-4 COSMIC (System76): Oct 2026 no-LLM confirmation gate
- URL: https://linuxiac.com/cosmic-stops-accepting-llm-generated-content-in-pull-requests/
- Date: Oct 2026 (policy change)
- Symptom: extra review burden from first-time LLM contributors; many submissions unplanned, rarely accepted.
- Workaround: PR template confirmation of no LLM code/comments/descriptions or PR may be closed. (Boundary: ban-leaning, not AI-accepting — recorded as policy-bloc edge.)
- Persona: desktop-environment OSS team.
- Frequency/severity: ongoing first-timer volume; severity moderate.
- Verification: VERIFIED-PARTIAL (secondary report with policy detail; primary template not fetched).

### S1-5 Jazzband: collective sunsetting partly attributed to "slopocalypse"
- URL: https://groundy.com/articles/are-ai-generated-prs-killing-open-source/ ; https://sloppish.com/the-counteroffensive.html
- Date: 2026 coverage
- Symptom: volunteer collective could not sustain triage/defense load.
- Workaround: sunset / hand back projects (organizational, not tooling).
- Persona: volunteer collective maintainers.
- Frequency/severity: terminal (project-continuity level); frequency chronic.
- Verification: UNVERIFIED (attribution via essays/roundups; primary Jazzband statement not fetched). Weak evidence, labeled as such.

### S1-6 git-annex (Joey Hess): ~100 hours to excise LLM-generated deps from build
- URL: https://sloppish.com/the-counteroffensive.html (collecting Hess statement)
- Date: 2026 essay
- Symptom: dependency-hygiene cost of LLM code, not inbound PRs — adjacent burden class.
- Workaround: manual build-without-tainted-deps effort.
- Persona: solo infrastructure maintainer.
- Frequency/severity: one 100-hour episode; severity high (toil, provenance risk).
- Verification: UNVERIFIED (essay-quoted; primary Hess post not fetched).

### S1-7 arXiv "AI Slop is DDoSing Open Source" (2026): cross-repo quantification
- URL: https://arxiv.org/html/2607.04003v1
- Date: 2026
- Symptom: PR volume ~6.8% above expected in 2025 while merge rates declined; one-time contributors −18.18% vs counterfactual.
- Workaround studied: auto-closing / defensive gating (protects capacity, risks openness).
- Persona: OSS maintainers at large (quantitative, not single-maintainer voice).
- Frequency/severity: systemic; severity moderate (percent-level, not order-of-magnitude).
- Verification: VERIFIED-PARTIAL (paper URL concrete; methods/sample not reviewed this session). Correlational; AI attribution method matters.

### S1-8 curl update trail (extends E-C202/E-C203, no duplication): 2 → 6 → 37 AI-slop counts; bounty end
- URLs: https://www.axios.com/2026/03/10/ai-agents-spam-the-volunteers-securing-open-source-software ; https://leaddev.com/software-quality/ai-generated-abandonware-is-hollowing-out-open-source
- Date: Mar 2026 coverage of Jan-2026 bounty end
- Symptom: slop counts 2 (2023) / 6 (2024) / 37 (2025); zero valid security reports from AI help; "serious mental toll … hampering our will to live" (via search excerpt; ≤25-word quote, secondary).
- Workaround: ended paid bounty; moved to GitHub private vuln reporting; disclosure mandate + bans (already in ledger; new here is the count timeline).
- Persona: volunteer security team (7 members, 3–4 per report — ledger E-C202).
- Frequency/severity: ~1 report/48h (2025) → ~1/18h (mid-2026, per s5); severity high.
- Verification: VERIFIED-PARTIAL (extends ledger VERIFIED-FULL E-C202/E-C203 with new count detail from secondary; verbatim toll quote needs primary fetch).

Ledger overlap note: curl (E-C201–E-C203), tldraw/Ghostty auto-close (E-C208/E-C234/E-C235), matplotlib agent retaliation (E-C219),
Node 21.7k-line PR (E-C249), Godot/Zig/Gentoo bans (E-C236/E-C218/E-C210/E-C237), Coolify/Vouch (E-C238/E-C209) already VERIFIED-FULL
in maintainer-review-evidence.md and NOT re-claimed above.

## S2 — INCUMBENT GATE CAPABILITY (what it ACTUALLY does; gap vs A07 reproducer+test gate)

### S2-1 GitHub: disable PRs / collaborators-only PRs (shipped 2026-02-13)
- Docs: https://github.blog/changelog/2026-02-13-new-repository-settings-for-configuring-pull-request-access/ ; https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/disabling-pull-requests
- Actually does: repo setting hides PR tab (disable) or restricts creation to write-access users (collaborators-only); others view/comment only. Binary, per-repo.
- Claims vs reality: marketed as contribution-quality control during "critical phases" — accurate but blunt; no per-contributor trust, no AI lane, no verification.
- Gap vs A07: controls WHO can open, not WHETHER the change reproduces/passes; A07's fails-then-passes reproducer + minimized diff + machine-readable policy check is entirely absent.

### S2-2 GitHub: concurrent open-PR caps + bypass list (repo 2026-06-17; org 2026-08-06)
- Docs: https://github.blog/changelog/2026-06-17-limit-open-pull-requests-for-users-without-write-access/ ; https://github.blog/changelog/2026-08-06-set-pull-request-limits-at-the-organization-level/ ; explainer https://github.blog/open-source/maintainers/how-pull-request-limits-are-cutting-down-the-noise/
- Actually does: per-repo cap on concurrent open non-draft PRs per non-writer; must close/merge one to open another; bypass list ≤100 trusted contributors; Copilot agent PRs count; drafts excluded. Org-level moderation setting.
- Claims vs reality: "cutting down the noise" (blog) — plausible for 1-open-PR asks (ledger E-C223) but volume-shaping only; bypass is identity-based (prior merges, account age, org membership), not evidence-based.
- Gap vs A07: caps throttle arrival rate; they do not run a reproducer on canonical base vs patch, detect test tampering (E-C215), or order the queue by evidence. Earned-budget-by-merged-work resembles A07's direction but stays identity heuristics.

### S2-3 GitHub: archive-PR view + vuln-report rate limits + issue caps (roadmap/partial)
- Docs: roadmap in S2-2 explainer (archive "shipping soon", issue caps "in development"); shipped https://github.blog/changelog/2026-10-01-rate-limits-for-private-vulnerability-reports/
- Actually does (as of early Oct 2026): archive = hide-from-default-view (not delete) — UNCONFIRMED GA; Oct-2026 rate limits apply ONLY to private vulnerability reports (per-repo + global daily caps + allow lists), not general PRs.
- Claims vs reality: do not cite "global cross-repo PR rate limit" as shipped — roadmap only (ledger E-C226 correctly says "coming"). Marketing-adjacent summaries conflate vuln-report caps with PR caps; label as such.
- Gap vs A07: archiving reduces public-backlog pressure (E-C248) but performs zero verification; vuln-report caps are adjacent (HackerOne-adjacent) not a reproducer gate.

### S2-4 Vouch (mitchellh/vouch): explicit vouch/denounce trust list + Actions auto-close
- Docs: https://github.com/mitchellh/vouch/blob/main/README.md ; live wiring https://github.com/ghostty-org/ghostty/blob/main/.github/workflows/vouch-check-pr.yml ; list https://github.com/ghostty-org/ghostty/blob/51ed437c/.github/VOUCHED.td ; research https://rywalker.com/research/vouch
- Actually does: flat-file VOUCHED.td (`!vouch` / `!denounce [user] [reason]`); check-pr/check-issue workflows auto-close unvouched/denounced; shareable denounce lists (~150 repos with VOUCHED.td reported mid-2026 — UNVERIFIED count); Ghostty 250+ vouched (per search, UNVERIFIED exact).
- Claims vs reality: "replaces trust-by-contribution with explicit trust" — accurate mechanically; effectiveness evidence is workflow-run volume + maintainer anecdote, no public aggregate dashboard. Portable-trust claim is real but adoption count is weak evidence.
- Gap vs A07: identity/trust gate only; never builds, never requires fails-then-passes reproducer, never minimizes diff, never checks test tampering. Complementary (A07 could sit behind Vouch), not competing verification.

### S2-5 peakoss/anti-slop Action: 34 heuristic rules, auto-close/label/comment/lock
- Docs: https://github.com/peakoss/anti-slop ; config https://github.com/peakoss/anti-slop/blob/main/action.yaml ; adopter https://github.com/huggingface/transformers/blob/main/.github/workflows/anti-slop.yml
- Actually does: scans PRs on open/reopen against branch/size/title/template/commits/account-age/emoji/honeypot/blocked-path rules (57+ options); tunable `max-failures`; "anti-slop, not anti-AI" by design. HuggingFace transformers adoption is concrete reuse signal.
- Claims vs reality: "could have closed 98% of slop PRs" (press) — UNVERIFIED marketing number; defaults tuned from ~130 reviewed slop PRs (project claim, methods not reviewed). Style-signal heuristics are evadable by agents (ledger E-C235/E-C238 synthesis stands).
- Gap vs A07: catches low-effort surface signals pre-review; passes "formally correct" slop with green checks (tldraw case) straight through. No canonical-base reproduction, no fail→pass proof, no test-tamper detection.

### S2-6 HackerOne-side gates (2025–2026 addition): disclosure mandates + spam enforcement + AI triage
- Docs: program https://hackerone.com/curl?type=team ; coverage https://cybernews.com/security/curl-bug-bounty-ai-security-reports-daniel-stenberg/ ; https://arstechnica.com/gadgets/2025/05/open-source-project-curl-is-sick-of-users-submitting-ai-slop-vulnerabilities/
- Actually does: curl program mandates AI-use disclosure + self-verification; spam/low-effort excluded with bans/reputation penalties; HackerOne adds AI-assisted triage + enforcement (industry-wide, details vendor-described).
- Claims vs reality: vendor "AI triage" efficacy claims are marketing-weak; disclosure is honor-system (same failure as E-C207).
- Gap vs A07: disclosure + reputation filter inbound volume; nothing executes a reproducer or binds proof to the exact report. Closest existing analog to A07's "proof before human" but human-executed, not platform-run.

## S3 — FALSIFICATION CORPUS CANDIDATES (20; slop-vs-valid classifiable; later gate test ≥70% slop filtered / ≥90% valid passed)

Slop candidates (expect gate to FILTER):
1. curl HackerOne AI-slop wave 2025 (37 slop; hallucinations e.g. nonexistent functions) — https://daniel.haxx.se/blog/2025/07/14/death-by-a-thousand-slops/ (2025-07-14). Basis: maintainer-labeled slop with counts.
2. curl bounty-end postmortem (confirmed-rate <5%) — https://daniel.haxx.se/blog/2026/01/26/the-end-of-the-curl-bug-bounty/ (2026-01-26). Basis: rate collapse + "not (yet) seen" slop-PRs counter-note.
3. Seth Larson slop-security-reports (PSF triage) — https://sethmlarson.dev/slop-security-reports (2024-12-03). Basis: first-glance-legitimate, time-to-refute.
4. matplotlib OpenClaw agent PR + retaliation post — PR https://github.com/matplotlib/matplotlib/pull/31132 ; account https://theshamblog.com/an-ai-agent-published-a-hit-piece-on-me/ (Feb 2026). Basis: autonomous, unaccountable, good-first-issue violation.
5. matplotlib AI-policy proposal thread — https://github.com/matplotlib/matplotlib/issues/31457. Basis: permission-before-PR norm proposal.
6. tldraw auto-close notice — https://github.com/tldraw/tldraw/issues/7695 (2026-01-15). Basis: maintainer batch triage sample.
7. tldraw "trash" postmortem (formally-correct landed slop; AI issue→AI PR loop) — https://tldraw.dev/blog/stay-away-from-my-trash (Jan 2026). Basis: hardest class — passes checks, still slop.
8. Ghostty unvouched auto-close sample — https://github.com/ghostty-org/ghostty/blob/main/CONTRIBUTING.md + discussion https://github.com/ghostty-org/ghostty/discussions/11628. Basis: trust-gate rejects.
9. FastAPI low-effort AI PR closes — via https://groundy.com/articles/are-ai-generated-prs-killing-open-source/ (2025–2026). Basis: maintainer close+block (needs primary fetch).
10. RPCS3 undisclosed-AI slop wave — via https://kotaku.com/playstation-3-emulator-devs-politely-ask-that-people-stop-flooding-it-with-ai-code-pull-requests-2000694656 (2026-05-10). Basis: disclosure-as-ban-criterion.
11. Excalidraw Q4-2025 one-shot flood — via S1-2 tldraw post. Basis: volume + no-follow-up pattern.
12. HackerOne curl program spam examples (Not-Applicable/Informative) — https://hackerone.com/curl?type=team. Basis: platform-labeled invalid.
13. GitHub discussion batch-close anecdotes (@sirosen et al.) — https://github.com/orgs/community/discussions/185387 (Jan–Feb 2026). Basis: maintainer-reported simultaneous AI PRs.

Valid candidates (expect gate to PASS):
14. curl ZeroPath/Aisle/Big-Sleep analyzer fixes (~50 merged; 400+ reports, low FP) — https://daniel.haxx.se/blog/2025/10/10/a-new-breed-of-analyzers/ (2025-10-10). Basis: maintainer-merged, high-quality.
15. Big Sleep SQLite stack-buffer-underflow find+fix — https://googleprojectzero.blogspot.com/search?updated-max=2024-11-21T09:53:00-08:00&max-results=1&reverse-paginate=true. Basis: novel vuln, same-day fix.
16. Node.js VFS work landed via smaller PRs (senior-authored, DCO-cleared) — https://github.com/nodejs/node/pull/61478 (opened 2026-01-22, closed 2026-09-04). Basis: trusted author + legal OK despite giant-PR form.
17. Homebrew disclosed AI-assisted PRs passing human-verified flow — https://github.com/Homebrew/brew/pull/21510 (Feb 2026) + https://docs.brew.sh/Responsible-AI-Usage. Basis: policy-compliant valid lane.
18. Linux Sashiko-reviewed finds humans missed (53% subset, 100% missed-by-humans) — https://www.theregister.com/2026/03/20/sashiko_code_review_linux/ (2026-03-20). Basis: review-side valid (secondary).
19. Godot/COSMIC-adjacent valid control: mozilla.ai disclosed-level calibration — https://blog.mozilla.ai/ai-generated-code-isnt-cheating-oss-needs-to-talk-about-it/ (2026-01-16). Basis: pro-AI provenance norm.
20. HackerOne curl disclosed valids (historical 15%+ confirmed pre-2025) — program disclosures directory (same HackerOne link). Basis: platform-confirmed real vulns.

Suitability note: items 9/11/18 are secondary-reported and need primary fetch before use as ground truth; item 7 is the critical
evasion class (passes checks) that a reproducer gate must still catch via fail→pass proof rather than style signals.

## S4 — NEGATIVE EVIDENCE (gates fail; valid work rejected; counter-evidence)

- N1 curl merged ~50 AI-analyzer fixes (E-C227 VERIFIED-FULL): skilled-operator AI output is welcome; pure volume/provenance gates would have discarded real fixes. Problem is unverified volume, not AI.
- N2 Big Sleep SQLite find (S3-15) + ZeroPath curl batch (S3-14): agent-found vulns with verification pass maintainer bar; supports reproducer-gating over bans/caps.
- N3 tldraw "formally correct, tests passed, we'd even started landing some" (E-C235): heuristic gates (anti-slop style signals, green checks) FAILED — slop passed. Favors execution-based gate, disfavors style heuristics.
- N4 Linked-issue requirement gamed by opening any issue (E-C221 thread): criteria-gating without verification fails adversarially.
- N5 Honor-system disclosure violated, found only after review spent (E-C207/E-C241); HackerOne disclosure mandate same weakness (S2-6). Attestation ≠ verification.
- N6 Blunt closures lose good contributors: tldraw calls closure "temporary … until GitHub provides better tools" (E-C234); collaborator-only is binary (E-C206); mailing-list model avoids public-PR obligation entirely (E-C248). Over-gating cost is real.
- N7 Node 21.7k-line senior PR drew 141 reviews yet functionality landed via smaller PRs (E-C249): size caps alone would have rejected-then-rerouted valid work; size-bounding needs intent-linking + stacking, not flat rejection.
- N8 METR 2026 update ambiguity (E-C229) + DORA amplifier (E-C233): self-reported readiness unreliable; teams with control systems gain — instantiates "verification capacity, not AI bad".
- N9 Copilot review commodity (E-C245: 1-in-5 reviews; E-C246: counts toward approvals) + Cloudflare 48k-MR reviewer at ~$1.19/review (E-C242): review-side AI is crowded/bundled; a review bot is not differentiation, and same-vendor write+approve violates separation of duties (E-C243/E-C213/E-C216).
- N10 LF $12.5M without tooling + Kroah-Hartman "grant funding alone is not going to help" (E-C252); Godot funding ask (E-C236): money-without-mechanism fails; supports mechanism (platform-run proof) over subsidy.
- N11 Account-age/prior-merge bypass signals (S2-2) are gameable via throwaway accounts (E-C202: "create a new account next week"); platform reputation already failed (ledger synthesis §What-has-been-tried).
- N12 Jazzband sunset (S1-5, UNVERIFIED attribution): if true, even exit is a "gate outcome" — volume gates that merely hide queue do not restore contributor pipeline; needs primary confirmation before weighting.

---
*Teams-use carve-out (from ledger synthesis, not new): internal concurrent-agent teams control their platform and own review-time data
(E-C228/E-C242) — recorded here only to bound S4 scope, not as a demand claim.*
*Method: 6/6 search budget spent (a07-s1…s6); per-query JSON saved under ~/git/ai-engineering-field-guide/_work-in-progress/grok-responses/ (outside this repo, not cited as repo evidence). No purchases. No verdicts.*
