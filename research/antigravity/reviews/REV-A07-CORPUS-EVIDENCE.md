# REV-A07-CORPUS-EVIDENCE — Independent Audit of A07 Candidate Corpus, Firsthand Demand, and Incumbent Gates

- **Reviewer Tag:** `a07-corpus-reviewer`
- **Session ID:** `55e1a893-fcb1-4683-ba6d-89f3058b581c`
- **Parent Session:** `antigravity-head` (`46fdb644`, conversation ID `245c7bba-9a7b-45c1-87a7-4537f289f9a5`)
- **Directives:** Codex Principal C1660 / C1673 (`01a1051f-57c2-7352-856a-e245123b4657`)
- **Review Date / As-of:** 2026-10-04, Europe/Berlin
- **Repository HEAD:** `8e4d4605ed9795e7e35b40931170a6feae56bafc`
- **Audited Sources (Read-Only):**
  - `research/muse/a07-corpus-review/first-sources.md` (independent review by `muse-r12`)
  - `research/zcode/independent/a07-demand-gate/findings-draft.md` (draft findings by `z-a07-demand-1`)
  - `research/zcode/independent/a07-demand-gate/task-prompt.md` (task prompt for unit `z-a07-demand-1`)
  - `research/evidence-ledger.md` (A07 / E-C2xx entries)
  - `research/claude/maintainer-review-evidence.md` (E-C201–E-C252)
  - Primary web documentation: `https://curl.se/docs/CVE-2025-9086.html`, `https://daniel.haxx.se/blog/2025/10/10/a-new-breed-of-analyzers/`, `https://daniel.haxx.se/blog/2024/01/02/the-i-in-llm-stands-for-intelligence/`
- **Bounded Gate Verdict:** **SOURCE-EXISTENCE-PASS / FOUR-ARTIFACT-CORPUS-INCOMPLETE**
  1. **Candidate Corpus Audit (Section S3):** `muse-r12`'s finding is **100% CONFIRMED**. Exactly **0 of 20** candidate submissions in `findings-draft.md` meet the four-artifact runnable bar (stable single issue/PR URL + patch diff + reproducer + maintainer technical outcome). The S3 list consists of aggregate campaigns, essays, policy threads, sample notices, and secondary press. It cannot serve as a statistical denominator for the A07 falsification test ($\ge 70\%$ slop filtered, $\ge 90\%$ valid passed).
  2. **Single Valid Case (Google Big Sleep -> CVE-2025-9086):** **VERIFIED-PARTIAL**. Advisory URL (`https://curl.se/docs/CVE-2025-9086.html`), fix commit (`c6ae07c6a541e0e96d0040afb6`, curl 8.16.0), and maintainer account (Daniel Stenberg 2025-10-10) are confirmed primary sources. **Crucial Classification Uncertainty:** This case is *AI-found / human-patched* (maintainer authored the fix), **not** an *AI-authored diff merged verbatim*.
  3. **Single Technically Invalid Case (HackerOne #2298307):** **VERIFIED-PARTIAL**. Primary writeup by Daniel Stenberg (2024-01-02, Exhibit B) confirmed. This report was closed as **technically invalid** ("no buffer overflow", nonexistent bug, hallucinated premise), distinctly separate from policy rejections (e.g. matplotlib PR #31132).
  4. **Incumbents & Negative Evidence (Sections S2 & S4):** Incumbents (GitHub PR caps/collaborator-only settings, Vouch, `peakoss/anti-slop`) operate purely on identity, volume, or surface style heuristics; none provide automated reproducer execution or fail-then-pass proof. Firsthand maintainer reports (curl, tldraw, Ghostty, git-annex) reflect acute cognitive drain from plausible nonsense. Negative evidence (N1–N12) demonstrates that unverified volume is the disease, while blunt closures and style heuristics fail adversarially.
  5. **Operational Invariants:** Strictly zero git commits from subagent; zero `/tmp` growth; scratch usage <= 512 MB (mode `0700`); cooperative memory limit <= 1500 MB; publication credential guard passed cleanly (exit 0).

---

## 1. Candidate Corpus Audit (S3 List: 20 Entries Evaluated)

Section S3 of `research/zcode/independent/a07-demand-gate/findings-draft.md` compiled 20 candidate public reports to evaluate A07's proposed falsification gate: *filter $\ge 70\%$ slop while passing $\ge 90\%$ valid reports*.

In `research/muse/a07-corpus-review/first-sources.md`, `muse-r12` evaluated each candidate against the strict **Four-Artifact Runnable-Submission Bar**:
1. **Stable single issue / PR URL**
2. **Patch diff**
3. **Reproducer**
4. **Maintainer technical outcome** (merged / confirmed / closed-as-invalid on technical grounds)

### 1.1. Entry-by-Entry Verification Table

| # | S3 Entry in `findings-draft.md` | Primary Artifact Type | Single PR / Issue URL? | Patch Diff? | Reproducer? | Maintainer Technical Verdict? | Four-Artifact Runnable? | Independent Audit Finding & Notes |
|---|---|---|---|---|---|---|---|---|
| **1** | curl HackerOne AI-slop wave 2025 | Aggregate campaign | No | No | No | No (aggregate counts only) | **NO** | 37 slop reports cited in blog post; no individual submission pinned. |
| **2** | curl bounty-end postmortem | Postmortem essay | No | No | No | No (policy decision) | **NO** | Essay announcing termination of HackerOne program; rate collapse summary. |
| **3** | Seth Larson slop security reports | Advisory essay | No | No | No (anecdote only) | No (triage advice) | **NO** | General triage guidance for PSF; cites SSLv2 pattern anecdote, no single PR. |
| **4** | matplotlib PR #31132 (OpenClaw) | Single PR | **YES** | **YES** | No | **NO (Policy rejection)** | **NO** | Closed under strict autonomous agent prohibition policy; no technical verdict on the patch. |
| **5** | matplotlib issue #31457 | Policy discussion | Issue URL only | No | No | No | **NO** | Norm proposal discussion thread ("AI policy"); contains no code or bug. |
| **6** | tldraw issue #7695 | Batch umbrella notice | Issue URL only | No | No | No (batch triage) | **NO** | Umbrella issue explaining bulk auto-close of unvetted issues; no single patch. |
| **7** | tldraw "trash" postmortem | Postmortem essay | No | No | No | No (aggregate regret) | **NO** | Essay analyzing landed-then-regretted AI PRs; no pinned single submission. |
| **8** | Ghostty CONTRIBUTING + discussion | Policy doc & forum | Forum URL only | No | No | No (identity gate) | **NO** | Vouch trust-gate rejection sample; identity-based, not technical invalidity. |
| **9** | FastAPI low-effort closes | Secondary press | No primary | No | No | No (general practice) | **NO** | Secondary article quoting maintainer close+block pattern; no primary URL. |
| **10** | RPCS3 undisclosed-AI wave | Secondary press | No primary | No | No | No (disclosure rule) | **NO** | Kotaku article on disclosure rules; policy-based, no pinned technical case. |
| **11** | Excalidraw Q4-2025 flood | Secondary citation | No primary | No | No | No | **NO** | Mentioned in tldraw blog post; no primary PR or reproducer. |
| **12** | HackerOne curl program samples | Login-gated index | Gated index URL | No | No | No | **NO** | Landing page; individual report details and attachments are private/gated. |
| **13** | GitHub community discussion #185387 | Forum discussion | Forum URL only | No | No | No | **NO** | Thread of maintainer anecdotes regarding concurrent AI PRs; no submissions. |
| **14** | curl ZeroPath/Aisle batch (~50 merged) | Batch of merged fixes | No single PR pinned | Yes (aggregate) | No single test | Yes (in aggregate) | **NO** | Group of ~50 merged fixes across >400 reports; not a single pinned submission. |
| **15** | Big Sleep SQLite find+fix | Project Zero blog search | Search URL only | No | No | No (needs fetch) | **NO** | Blog search link; no specific PR, commit, or runnable test suite pinned in S3. |
| **16** | Node.js PR #61478 (VFS) | Single PR | **YES** | **YES** | No | Closed | **NO** | **Not AI-authored:** Senior human developer work, DCO-cleared; size control case. |
| **17** | Homebrew PR #21510 | Single PR | **YES** | **YES** | No | Merged | **NO** | **Policy PR, not a bugfix:** PR adds AI checkbox to issue/PR templates. |
| **18** | Linux Sashiko review finds | Secondary press | No primary | No | No | No | **NO** | Register article on review-side AI; secondary reporting without primary artifacts. |
| **19** | mozilla.ai provenance essay | Blog essay | No | No | No | No | **NO** | Essay arguing for AI code provenance norms; no code submission. |
| **20** | HackerOne curl disclosed valids | Directory index | Directory URL | No | No | Historical aggregate | **NO** | Historical pre-2025 human disclosures; no single pinned AI submission. |

### 1.2. Audit Verdict on the 20 Candidate Corpus
**Muse-r12's conclusion is CONFIRMED without exception:**
- **0 of 20** candidates satisfy the four-artifact runnable bar as cited.
- At most **4 entries** (#4, #6, #16, #17) point to a single GitHub issue or PR URL:
  - **#4 (matplotlib #31132):** Closed due to an autonomous agent prohibition policy, **not** a technical evaluation of the code.
  - **#6 (tldraw #7695):** An umbrella notice for batch triage.
  - **#16 (Node.js #61478):** Authored by a senior human engineer, not AI.
  - **#17 (Homebrew #21510):** A documentation/template update adding an AI disclosure checkbox, not a bugfix or functional change.
- The remaining 16 entries are essays, aggregate statistics, forum discussions, team landing pages, or secondary press roundups.
- **Consequence for A07:** The draft corpus **cannot** provide a denominator or ground-truth dataset to evaluate whether A07 filters $\ge 70\%$ of slop or passes $\ge 90\%$ of valid submissions. Evaluating A07 requires constructing a ground-truth dataset from primary git commits and issue threads.

---

## 2. Verification of the Single Valid Case (Google Big Sleep -> CVE-2025-9086)

### 2.1. Pinned Primary Evidence

| Dimension | Verified Artifact Detail |
|---|---|
| **Vulnerability** | CVE-2025-9086: "Out of bounds read for cookie path" |
| **Target Project** | `curl` / `libcurl` |
| **Advisory URL** | `https://curl.se/docs/CVE-2025-9086.html` (HTTP 200 confirmed live) |
| **Report Date** | August 11, 2025 (reported via HackerOne #3294999) |
| **Advisory Release Date** | September 10, 2025 (in curl release 8.16.0) |
| **Fix Commit** | `c6ae07c6a541e0e96d0040afb6` (`https://github.com/curl/curl/commit/c6ae07c6a541e0e96d0040afb6`) |
| **Attribution** | `Reported-by: Google Big Sleep` / `Patched-by: Daniel Stenberg` |
| **Maintainer Account** | Daniel Stenberg blog post (2025-10-10, `https://daniel.haxx.se/blog/2025/10/10/a-new-breed-of-analyzers/`) |
| **Maintainer Quotes** | *"This was the first ever report we have received that seems to have used AI to accurately spot and report a security problem in curl."* (25 words)<br>*"The reporting party, Google Big Sleep, even helped out and provided additional details and clarifications when we asked follow-up questions."* (20 words)<br>*"The entire reporting process felt very human and the problem was confirmed and fixed."* (13 words) |

### 2.2. Critical Classification Uncertainty: AI-Found vs. AI-Authored

A rigorous audit of the CVE advisory and maintainer writeup exposes a vital distinction:
- **What Occurred:** Google Big Sleep (an autonomous AI agent collaboration between Google Project Zero and Google DeepMind) analyzed curl source code, identified a legitimate heap out-of-bounds read in cookie path processing, and submitted an issue report with technical details. The curl maintainer (Daniel Stenberg) validated the report, communicated with the reporting party, and **personally authored and committed the C patch** (`c6ae07c6a541e0e96d0040afb6`).
- **Classification Status:**
  - Satisfies: **AI-found / human-patched**.
  - **Does NOT satisfy:** **AI-authored diff merged verbatim**.
- **Implication for A07 Architecture:**
  - A07's core premise in `approaches-20.md` requires contributors to push to a quarantine fork with a *reproducer test and patch diff*, which the platform executes (fails on base, passes on patch).
  - If an AI agent discovers a subtle memory flaw but submits an issue report without a verified git patch (or where a human maintainer chooses to write their own fix), A07's automated "fails-then-passes" patch verification pipeline does not engage.
  - To test A07 against AI-authored pull requests, the corpus must locate cases where the AI *authored the code diff* under an AI-accepting disclosure policy and the maintainer merged that diff.

---

## 3. Verification of the Single Technically Invalid Case (HackerOne #2298307)

### 3.1. Pinned Primary Evidence

| Dimension | Verified Artifact Detail |
|---|---|
| **Incident Title** | HackerOne #2298307: "Buffer Overflow Vulnerability in WebSocket Handling" |
| **Target Project** | `curl` (experimental WebSocket code) |
| **Report Date** | December 28, 2023 |
| **Maintainer Account** | Daniel Stenberg writeup (2024-01-02, `https://daniel.haxx.se/blog/2024/01/02/the-i-in-llm-stands-for-intelligence/`, Exhibit B) |
| **Report URL** | `https://hackerone.com/reports/2298307` (login-gated) |
| **Maintainer Quotes** | *"Where on earth is the buffer overflow the reporter says exists here?"* (11 words)<br>*"After repeated questions and numerous hallucinations I realized this was not a genuine problem"* (13 words)<br>*"There was no buffer overflow."* (5 words)<br>*"closed the issue as not applicable"* (7 words) |
| **Outcome** | Closed same-day (2023-12-28) as `Not Applicable` / Invalid |

### 3.2. Technical Invalidity vs. Policy Rejection

This case provides a clean benchmark for technical invalidity:
- **Technical Invalidity (curl #2298307):** The submitter asserted a buffer overflow in WebSocket handling. The maintainer re-read the code three times, tested the claims, asked clarifying questions, and confirmed that the claimed vulnerability did not exist in the code. The follow-up responses hallucinated nonexistent structures and API behaviors. The report was closed because the premise was false and the reproducer failed.
- **Policy Rejection (matplotlib #31132):** In contrast, matplotlib PR #31132 (submitted by agent `crabby-rathbun` via OpenClaw) was closed because the matplotlib project enforces an explicit prohibition against autonomous bots and unannounced AI agents. The maintainers did not adjudicate whether the code diff fixed the bug; they closed it on governance/policy grounds.
- **Why the Distinction is Critical:**
  - A07's quarantine gate is designed to evaluate **code behavior and execution** (running tests on canonical base and patch).
  - A technical gate evaluates whether a bug reproduces and whether a patch fixes it without breaking regressions.
  - Evaluating A07 against policy rejections produces false conclusions: an automated execution gate cannot know whether a community *wants* AI contributions; it can only verify whether the contribution *works*.
  - Therefore, HackerOne #2298307 is an authentic technical-invalidity ground-truth case.

---

## 4. Incumbent Gates & Negative Evidence Audit (S2 & S4)

### 4.1. Audit of Incumbent Gate Capabilities (Section S2)

| Incumbent Tool | Mechanism & Shipped Date | Actual Operational Behavior | Marketing / Claimed Behavior | Architectural Gap vs. A07 Quarantine |
|---|---|---|---|---|
| **GitHub Access Controls** | Shipped 2026-02-13 | Repository setting: disables PRs or restricts creation to write collaborators. | Contribution quality control during critical releases. | **Blunt access wall.** Filters *who* can contribute, not *what* is contributed. Destroys the open-source contributor funnel. |
| **GitHub Concurrent Caps** | Shipped 2026-06-17 (repo) / 2026-08-06 (org) | Caps concurrent open non-draft PRs per non-writer. Max 100-user bypass list based on past merges/account age. | "Cutting down the noise" for maintainers. | **Volume throttle only.** Does zero code execution. Trust is identity-based, easily bypassed by sybil/throwaway accounts. |
| **Vouch (`mitchellh/vouch`)** | Deployed in Ghostty (`.github/VOUCHED.td`) | Flat-file trust graph. Auto-closes PRs from unvouched or denounced GitHub usernames. | Replaces implicit forge trust with explicit maintainer vouching. | **Identity-only filter.** Never builds or tests code; cannot evaluate whether a vouched user's patch actually works or introduces bugs. |
| **`peakoss/anti-slop` Action** | Action in HuggingFace transformers | 34 heuristic rules checking PR titles, branch names, commit counts, description length, and emoji. | Claims ability to close "98% of slop PRs". | **Style heuristic.** Completely vulnerable to "formally correct" slop that adheres to templates and passes CI (e.g. tldraw E-C235). |
| **HackerOne Program Rules** | curl program updates (2024–2026) | Mandatory AI disclosure checkboxes, reputation penalties, platform spam filtering. | Prohibits AI slop through platform enforcement. | **Honor system.** Submitters ignore checkboxes or fail to recognize that their tools hallucinated. Offers no automated test harness. |
| **AI Code Reviewers (Copilot, CodeRabbit, Codium)** | Commercial bots (2025–2026) | Automated PR comments analyzing diffs with LLMs; Enterprise Copilot can count toward approval rules. | "Automated code review" and "faster triage". | **Text-only comment generation.** Does not execute fails-then-passes reproducers; violates separation of duties when same vendor authors and approves. |

### 4.2. Firsthand Maintainer Symptoms vs. Marketing & Secondary Press

Rigorous separation of primary maintainer evidence from secondary noise:
- **Firsthand Maintainer Evidence (Primary Truth):**
  - **Daniel Stenberg (curl, E-C201–E-C203, E-C227):** 37 AI-slop security reports in 2025; each report consumed 30 min to 3 hours across 3–4 security team members; terminated bug bounty in Jan 2026 due to cognitive exhaustion.
  - **Steve Ruiz (tldraw, E-C234, E-C235):** PR surge >2x; maintainers landed formally correct, beautifully documented AI PRs that secretly broke subtle canvas behaviors, forcing a temporary freeze.
  - **Joey Hess (git-annex, S1-6):** Spent ~100 hours of manual labor auditing and removing LLM-generated dependencies from build chains.
  - **Greg Kroah-Hartman (Linux Kernel, E-C252):** Emphasized that grant funding cannot fix maintainer burnout; review capacity is the finite bottleneck.
- **Vendor Telemetry & Secondary Press (Caveats Required):**
  - **Faros AI (E-C228):** Reported +91% PR review time on high-AI teams (vendor selling engineering management software).
  - **CodeRabbit (E-C231):** Reported AI PRs have 1.7x more issues (vendor selling AI PR reviews).
  - **peakoss/anti-slop:** Marketing claim of "closing 98% of slop PRs" is unverified against real bug distributions.

### 4.3. Analysis of Negative Evidence (N1–N12 in Section S4)

The 12 negative evidence items in `findings-draft.md` establish critical constraints on any proposed quarantine gate:
1. **N1 & N2 (AI Contributions Can Be High-Quality):** curl merged ~50 bugfixes from ZeroPath/Aisle and accepted Google Big Sleep's CVE-2025-9086. Pure anti-AI bans would discard high-value security discoveries. The problem is unverified volume, not AI assistance.
2. **N3 (Style Heuristics Fail on Formally Correct Slop):** The tldraw experience proves that LLMs easily generate clean PR descriptions, follow contribution guidelines, and pass static linters while introducing broken logic. Style-based anti-slop tools fail against advanced models.
3. **N4 & N5 (Honor Systems and Process Rules Are Easily Gamed):** Mandating issue links or AI disclosure checkboxes fails adversarially; submitters create empty issues or simply omit disclosure.
4. **N6 (Over-Gating Destroys Open Source):** Collaborator-only settings and blunt auto-close rules protect maintainer sanity at the cost of severing the contributor funnel.
5. **N9 (Review Bots Increase Noise):** Deploying AI review bots (Copilot review, CodeRabbit) adds commentary without verifying runtime behavior, compounding the maintainer's reading load.

---

## 5. Invariants, Tool Verification, and Exact Pins

### 5.1. Publication Credential Guard Verification
The deliverable was subjected to the strict publication credential guard to verify that zero credentials, private keys, or tokens are present:

```bash
python3 research/antigravity/tooling/publication_guard.py research/antigravity/reviews/REV-A07-CORPUS-EVIDENCE.md
```
**Result:** Exit code `0` (clean scan, zero credential leaks detected).

### 5.2. Working Tree & Resource Invariants
- **Working Tree Integrity:** Zero commits created; zero modifications to `research/space-bunny/` or existing peer directories.
- **Scratch Directory:** `.local/scratch/a07-corpus-review/` strictly mode `0700`, disk usage < 100 KB (budget <= 512 MB).
- **Environment:** `TMPDIR` confined to scratch root; zero `/tmp` growth; memory cooperative limit <= 1500 MB.

### 5.3. Exact Source Pins

| Document / Artifact | Repository Path | Git Blob / Hash |
|---|---|---|
| Review Deliverable | `research/antigravity/reviews/REV-A07-CORPUS-EVIDENCE.md` | New deliverable (uncommitted) |
| Muse-r12 Review | `research/muse/a07-corpus-review/first-sources.md` | `a007cd0` / `8e4d460` |
| Z-a07 Demand Draft | `research/zcode/independent/a07-demand-gate/findings-draft.md` | `8e4d460` |
| A07 Task Prompt | `research/zcode/independent/a07-demand-gate/task-prompt.md` | `8e4d460` |
| Maintainer Evidence | `research/claude/maintainer-review-evidence.md` | `8e4d460` |
| Approaches 20 | `research/approaches-20.md` | `8e4d460` |
| CVE Advisory | `https://curl.se/docs/CVE-2025-9086.html` | Release curl 8.16.0 |
| Fix Commit | `c6ae07c6a541e0e96d0040afb6` (curl) | Merged 2025-09-10 |

---

## 6. Recommendations & Handoff

1. **A07 Shortlist Gate Reality:** The claim that A07 has a ready 20-entry falsification test suite is **refuted**. The 20 items in `findings-draft.md` are research citations, not runnable benchmark pairs.
2. **Path to a Genuine Benchmark:** To validate A07's quarantine gate, the team must construct a dedicated ground-truth corpus consisting of:
   - At least 10 technically invalid pull requests with reproducible failures (e.g. failing tests, syntax errors, or non-reproducing bugs).
   - At least 5 verified valid pull requests containing clean reproducers and functional bugfixes.
3. **Architectural Realignment:** A07 must not rely on author self-disclosure, identity heuristics, or style checkers. Its sole defensible moat is **automated containerized reproduction**: running an isolated test on the base repository (must fail) and on the patched repository (must pass), while verifying that existing regression suites are not tampered with.
4. **Handoff Target:** Deliver review receipt to parent agent (`antigravity-head`, `245c7bba-9a7b-45c1-87a7-4537f289f9a5`) for onward transmission to Codex Principal C1673.
