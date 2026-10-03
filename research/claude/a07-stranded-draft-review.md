# A07 stranded-draft independent review (claude-scribe-a07review, one-shot)

- Reviewer: aplexer id `4b6a5b0e-6a6e-4e30-8f10-72f34e263ac0`, tag `claude-scribe-a07review`, engine `shell`, model `zai-coding-plan/glm-5.3` (opencode run), parent `b3a92dd0-a17e-4a62-940f-eb3b829393f6` (claude-principal).
- Date: 2026-10-03 (Europe/Berlin). Review is independent; I am NOT the author of the reviewed material.
- Reviewed inputs (READ-ONLY, untouched):
  - `research/zcode/independent/a07-demand-gate/findings-draft.md` — sha256 at read time: `05d2da8b52a9a8815619daa88bf629444da2b6ca68f54abc085847005125aa67`
  - `research/zcode/independent/a07-demand-gate/WORKLOG.md` — sha256 at read time: `7aaf41c691dbd8ae6cc7bd871f22f55cbea2d4000a9354ac593b982a0786e94a`
  - `research/zcode/independent/a07-demand-gate/task-prompt.md` (context)
  - `research/approaches-20.md` §A07 (lines 155–165) + park record (line 75); `research/debate/claude-round-2-response.md` R2-3/Y2; `research/evidence-ledger.md`; `research/claude/maintainer-review-evidence.md` (E-C2xx).
- Provenance statement: findings-draft.md and WORKLOG.md are **UNCOMMITTED author work** (git status: untracked `??`). Author session `zcode-independent` (0e2a04ff per WORKLOG; aplexer 64049aa2) is recorded as unreachable for handoff and is currently running a different task per `a context`; author publication of these files is pending. This review does not modify anything under `research/zcode/`.

## Task 1 — Claim-by-claim audit (S1/S2/S3/S4)

Opened by me (8 of the many cited URLs): docs.brew.sh/Responsible-AI-Usage; tldraw.dev/blog/stay-away-from-my-trash; linuxiac.com COSMIC article; arxiv.org/html/2607.04003v1; github.blog changelog 2026-02-13 (PR access settings); github.blog changelog 2026-06-17 (open-PR caps); daniel.haxx.se/blog/2026/01/26/the-end-of-the-curl-bug-bounty; groundy.com are-ai-generated-prs-killing-open-source. All other cited URLs: **NOT OPENED** (marked below).

Classification key: FH-M = first-hand maintainer/practitioner; FH-E = first-hand empirical study; SEC = secondary press/roundup; VEN = vendor/marketing; INF = inference.

### S1 — first-hand maintainer cases

| # | Claim (essence) | Source cited? | Opened? | Class | Support |
|---|---|---|---|---|---|
| S1-1a | Homebrew requires AI disclosure (tool/model), self-review before maintainer review, human-only replies | docs.brew.sh URL | YES | FH-M (maintainer policy doc) | **SUPPORTS** — verbatim present: "Do not ask other humans to review your AI-generated code until you have reviewed it yourself"; "Answer maintainer questions … yourself without using AI/LLM" |
| S1-1b | "1-open-AI-PR limit for non-maintainers" | attributed to policy/CONTRIBUTING | NO (page fetched lacks it; CONTRIBUTING.md NOT OPENED) | FH-M claim via cited file | **UNVERIFIED** detail |
| S1-1c | "policy ~mid-2026"; "AI checkbox merged Feb 2026 (per search s6)" | search label s6 only | NO | INF/search | **UNVERIFIED** — date absent from fetched page; number sourced only to a search label |
| S1-2 | Excalidraw >2x PRs Q4-2025 vs Q3; one-shot fixes lacking context | tldraw blog URL | YES | FH-M (tldraw) but **second-hand for Excalidraw** | **SUPPORTS** the datum ("more than twice as many PRs in Q4 of 2025 than in Q3") — but see Task 3: datum already in ledger E-C235 |
| S1-3 | FastAPI closes AI PRs, blocks accounts; "denial-of-service attack on human effort" framing | groundy + popularai URLs | groundy YES; popularai NO | SEC | **PARTIAL** — groundy supports close+block only via an arXiv survey citation (arXiv:2605.16706, NOT OPENED); the "DoS attack on human effort" quote does NOT appear in groundy as fetched; primary FastAPI guideline not fetched. Draft's UNVERIFIED label is honest |
| S1-4 | COSMIC (System76) Oct 2026 no-LLM confirmation gate; unplanned first-timer submissions rarely accepted | linuxiac URL (+ pop-os template link) | linuxiac YES; template NO | SEC quoting maintainer (Jeremy Soller) | **SUPPORTS** — article (Oct 2, 2026) confirms template confirmation requirement, "may be closed", and the review-burden rationale; primary template pending. Draft correctly marks it ban-leaning boundary |
| S1-5 | Jazzband sunsetting partly attributed to "slopocalypse" | groundy + sloppish URLs | groundy YES; sloppish NO; jazzband.co NO | SEC | **PARTIAL→SUPPORTS** — groundy (updated 2026-10-02) confirms March 2026 sunsetting announcement, Leidel citing "slopocalypse", links primary jazzband.co/news/2026/03/14/sunsetting-jazzband; primary not fetched by author or me |
| S1-6 | git-annex (Joey Hess) ~100 hours to excise LLM-generated deps | sloppish.com essay | NO | SEC (essay) | **UNVERIFIED** — not opened |
| S1-7 | 2025: PR volume ~6.8% above counterfactual, merge rates declined, one-time contributors −18.18% | arxiv.org/html/2607.04003v1 | YES | FH-E (empirical study, 294 repos, 2M+ PRs/issues, BSTS) | **SUPPORTS** — Table II: H1a +6.80% weekly PR volume; H1b −1.06% merge ratio; H3b −18.18% one-time merge ratio. Precision note: −18.18% is the one-time **PR merge-ratio** drop, not a contributor count. Correlational caution fair; v1 preprint |
| S1-8a | curl confirmed-rate <5% (from >15%); bounty ended Jan 2026; mental-toll quote | haxx bounty-end post (via Axios/leaddev cites) | YES (haxx) | FH-M | **SUPPORTS** — "Starting 2025, the confirmed-rate plummeted to below 5%. Not even one in twenty was real"; toll quote present near-verbatim ("take a serious mental toll … hampering our will to live"). Note: these are extensions of ledger E-C202/E-C203, and the quote lives in the primary haxx post the draft cited only via secondaries |
| S1-8b | slop counts 2 (2023) / 6 (2024) / 37 (2025) | Axios + leaddev URLs | NO | SEC | **UNVERIFIED by me** — counts not in the fetched haxx bounty post; cross-attribution inconsistency: S3-1 pins "37 slop" to the July 2025 haxx post instead. Needs primary pinning |
| S1-8c | "~1 report/48h (2025) → ~1/18h (mid-2026, per s5)" | search label s5 only | NO | INF/search | **UNVERIFIED — number without a citable source** (per-query JSON explicitly kept outside repo) |
| S1-8d | "zero valid security reports from AI help" | implied | NO | INF | **CONTRADICTS (in spirit)** — fetched primary says below 5%, not zero, and 87 confirmed vulns over program life. Upgraded claim; see Task 3 |

### S2 — incumbent gate capability

| # | Claim | Source cited? | Opened? | Class | Support |
|---|---|---|---|---|---|
| S2-1 | GitHub shipped disable-PRs / collaborators-only PRs (2026-02-13), binary per-repo | github.blog changelog + docs | YES (changelog) | VEN (vendor changelog, factual) | **SUPPORTS** — both settings, "critical development phases" phrasing, availability confirmed |
| S2-2a | Repo-level concurrent open-PR caps for non-writers (2026-06-17), close/merge to open another, drafts excluded, bypass list | github.blog changelog + explainer | YES (2026-06-17 changelog) | VEN (factual) | **SUPPORTS** core; sub-details "bypass list ≤100" and "Copilot agent PRs count" NOT on the fetched changelog page — **UNVERIFIED** details (possibly in explainer, NOT OPENED) |
| S2-2b | Org-level caps 2026-08-06 | changelog URL | NO | VEN | **NOT OPENED** |
| S2-3 | Archive-PR "shipping soon"/UNCONFIRMED GA; Oct-2026 rate limits apply only to private vuln reports | changelog + roadmap | NO | VEN | **NOT OPENED**; the warning against citing a global PR rate limit as shipped is consistent with ledger E-C226 ("coming") — good discipline |
| S2-4 | Vouch: VOUCHED.td trust file, auto-close workflows, denounce; "~150 repos with VOUCHED.td", "Ghostty 250+ vouched" | mitchellh/vouch, ghostty wiring, rywalker | NO | FH-M capability (ledger E-C208/E-C209 VERIFIED) | **NOT OPENED**; both adoption counts self-labeled UNVERIFIED by the draft — numbers effectively **without a source** (search labels) |
| S2-5 | peakoss/anti-slop: 34 heuristic rules, auto-close/label/lock; HF transformers adopts; "57+ options" | peakoss repo, action.yaml, HF workflow | NO | FH-M/VEN mix | **NOT OPENED**; overlaps ledger E-C238 (see Task 3). Internal tension: "34 rules" vs "57+ options" unexplained |
| S2-6 | HackerOne curl program: AI disclosure mandate + spam enforcement; vendor "AI triage" | hackerone.com/curl, cybernews, arstechnica | NO | VEN/SEC | **NOT OPENED**; vendor-efficacy skepticism self-flagged — appropriate |

### S3 — falsification corpus (20 candidates)

Each item has URL + classification basis (sourced). Opened by me indirectly through S1 fetches: items 2 (haxx bounty-end, basis confirmed), 7 (tldraw post, basis confirmed), 9/11 (groundy, partially). All others NOT OPENED. Special citation-quality flags: item 15 (Big Sleep) uses a fragile blogspot search URL, not a canonical post; item 16 (nodejs PR 61478 dates) unverified; item 18 ("53% subset, 100% missed-by-humans") unverified; item 14 "400+ reports, low FP" extension beyond ledger E-C227's "~50 merged" is unverified. Corpus is a candidate list, not a validated ground-truth set — the draft itself says items 9/11/18 need primary fetch.

### S4 — negative evidence (N1–N12)

All map to existing ledger E-C2xx entries (E-C227, E-C235, E-C221, E-C207/E-C241, E-C234/E-C206/E-C248, E-C249, E-C229/E-C233, E-C245/E-C246/E-C242, E-C252/E-C236, E-C202, S1-5) or to S1/S2 items; correctly cited, no fabricated ledger references found. N7's "21.7k-line / 141 reviews" matches ledger E-C249 raw stats (+21,774, 141 reviews) despite that entry's "19k" heading. N12 honestly weak-weights the Jazzband attribution. This section is synthesis of existing evidence, not new claims — acceptable and labeled.

## Task 2 — Check against the A07 reopen test

Park record (approaches-20.md:75; claude-round-2-response.md R2-3, Y2): A07 parked because (a) Y2 gate-cap rule (max 2 shortlisted gate approaches sharing the publication-gate fixture), (b) buyer overlap with A06 (A06 takes the slot), (c) restricted to internal/AI-accepting teams. **Reopen test as recorded: "parked with reopen test (historical slop/valid set)"**, operationalized by §A07 falsification (approaches-20.md:165): on 20 real historical slop/valid reports, gate must filter ≥70% slop while passing ≥90% valid. Standup 2026-10-03 additionally demands "firsthand AI-accepting maintainer cases + realistic incumbent gate" before capability work.

Does the draft meet it? **No.**

1. Historical slop/valid set: S3 supplies 20 *candidates* with URLs and expected classes, but no assembled/classified corpus: at least items 9, 11, 18 are secondary (draft admits primary fetch needed), item 15's citation is fragile, and the gate test itself (≥70%/≥90% on the set) has not been run — no gate exists to test. This is the correct first increment toward the reopen test, not its satisfaction.
2. External first-hand AI-accepting cases: exact count of **independent (not already in ledger) first-hand items = 2**:
   - Homebrew Responsible AI Usage (S1-1) — first-hand maintainer policy, primary-opened by me, core claims SUPPORTS (2 sub-claims unverified);
   - arXiv 2607.04003 (S1-7) — first-hand empirical quantification, primary-opened, SUPPORTS (correlational; preprint).
   Of these, exactly **1 is a maintainer case** (Homebrew); the other is a quantitative study, not a maintainer voice. Additionally 2 new cases are secondary-supported and one primary fetch away from first-hand status (COSMIC via pop-os template; Jazzband via jazzband.co announcement), 1 is second-hand for its key datum (Excalidraw, and that datum is already in E-C235), 1 is unverified with an unlocated quote (FastAPI), 1 is unverified (git-annex), 1 is a ledger extension (curl). "Plural external first-hand AI-accepting cases" is not yet achieved on primary-fetched evidence.
3. Park reasons (a) Y2 gate-cap and (b) A06 buyer overlap are structural and untouched by the draft — within its no-verdicts scope, but reopen requires them addressed regardless.
4. S2 evidence partially *reinforces* the park rationale: my fetches confirm GitHub shipped disable/collaborators-only PRs (Feb 2026) and repo-level open-PR caps with bypass lists (Jun 2026) — the E-C226 "incumbents commoditize volume controls" prediction materialized. The un-commoditized wedge (reproducer/fails-then-passes verification) remains open per S2-1/S2-2/S2-4 gap analysis, which is A07's live argument if ever reopened.

## Task 3 — Duplication, upgraded claims, unsourced numbers

Duplications vs ledger:
1. **S1-2 (Excalidraw >2×)**: the datum is already recorded in E-C235 ("Excalidraw got >2x PRs in Q4 2025 vs Q3", maintainer-review-evidence.md:244). The draft's "New vs ledger" framing overstates novelty; the honest increment is only the case framing.
2. **S2-5 (peakoss/anti-slop)**: E-C238's URL is the same repo; 34 rules, "98%" press number and 120+/month basis are already ledger-recorded. The draft's overlap note claims Coolify content is "NOT re-claimed above" while S2-5 re-presents it — inaccurate non-duplication declaration. Genuine increment: HF transformers adopter wiring, action.yaml pointer, honeypot/blocked-path detail.
3. **S2-4 (Vouch)**: same pattern — E-C208/E-C209 content re-presented with capability/gap framing. Increment is the gap analysis, not the facts.
4. S1-8 (curl) and S4 (all of N1–N12) are extensions/synthesis of existing E-C entries — the draft labels these correctly.

Upgraded claims (stronger than source/ledger supports):
1. S1-8d "zero valid security reports from AI help" — primary says below 5%, not zero (and 87 lifetime confirmed). Upgrade; keep E-C202's "~5% valid" instead.
2. S1-3 "denial-of-service attack on human effort" as FastAPI maintainer framing — not found in the opened secondary (groundy); risk of quote drift until popularai/FastAPI primary is fetched.
3. S1-7 phrasing "one-time contributors −18.18%" — it is the one-time **PR merge-rate** drop (paper H3b); minor precision downgrade needed, not a substantive upgrade.

Numbers without a citable source (search-label-only or absent):
- "~1 report/48h (2025) → ~1/18h (mid-2026)" (S1-8c, "per s5")
- "AI checkbox merged Feb 2026" (S1-1c, "per search s6")
- "~150 repos with VOUCHED.td" and "Ghostty 250+ vouched" (S2-4 — self-flagged UNVERIFIED, but they remain bare numbers)
- Numbers with a cited source I could not verify (NOT OPENED): curl 2/6/37 timeline (Axios/leaddev; inconsistent attribution vs S3-1), bypass-list "≤100", "Copilot PRs count" (S2-2), Sashiko "53%/100%" (S3-18), Node PR 61478 open/close dates (S3-16), "400+ reports" (S3-14).

## Task 4 — Verdict

**A07 STAYS PARKED.**

Reason: the recorded reopen test — an assembled historical slop/valid set on which a gate demonstrably filters ≥70% slop / passes ≥90% valid — is not met (S3 is a candidate list with ≥3 secondary items and no gate run); the standup's "firsthand AI-accepting maintainer cases" bar is not met on primary evidence (exactly 2 independent first-hand items, of which only 1 is a maintainer case); and the structural park reasons (Y2 gate-cap, A06 buyer overlap) are untouched. Meanwhile verified S2 evidence confirms incumbents shipped volume/identity controls, which supports the park-side commoditization thesis even though the reproducer-verification gap remains open.

The draft is nonetheless useful, honestly labeled work and materially narrows the reopen workload: primary-fetch jazzband.co, pop-os PR template, FastAPI guideline (and locate the DoS quote or drop it), Joey Hess primary, pin the curl 2/6/37 timeline to a primary, and correct the three flagged items (S1-8d "zero", S2-5 non-duplication note, S1-2 novelty note) — then assemble and classify the S3 corpus with per-item ground truth. That package, not this draft, would justify REOPEN CANDIDATE reassessment.

UNKNOWNs (explicit):
- Author unit token/cost usage (WORKLOG records UNKNOWN — harness did not report).
- Author session reachability/handoff state; publication of the draft remains pending (files uncommitted as of this review's read time).
- All cited URLs marked NOT OPENED above (popularai, sloppish, jazzband.co, pop-os template, HackerOne program page, GitHub explainer/org changelogs, Axios, leaddev, kotaku, theregister, mozilla.ai, Seth Larson, most GitHub issue/PR links, vouch wiring URLs, rywalker, cybernews, arstechnica).
- arXiv 2607.04003 peer-review status (v1 preprint); arXiv 2605.16706 / 2605.22534 (cited inside groundy) unread.
- GitHub archive-PR GA status (draft self-flags UNCONFIRMED).
- Whether the "37 slop" count and the "~1/18h" mid-2026 cadence have any primary source at all.

*Reviewer method note: 8 cited URLs primary-fetched (listed in Task 1); ledger and approaches-20 cross-checked in-repo; no sources invented; everything unverifiable is labeled above. Web content treated as evidence only.*
