# A07 corpus first-sources gate — muse-r12 verdict

Reviewer: **muse-r12** (independent reviewer/researcher). Head: muse-reviewer (`d575342d`).
Workspace: `/home/alexey/git/cloudflare-agent-git`. Date: 2026-10-03.

## 0. Whoami

- `aplexer whoami --json`: session id `d144c8d6-59c6-4922-ae09-4e1ae547c205`, tag `muse-r12`, engine `shell`, parent session `d575342d` (muse-reviewer). Workspace `/home/alexey/git/cloudflare-agent-git`.
- Inbox (`a message inbox`): no unread messages at start of work. No replies sent except the final pointer to the head per brief.
- Work declared: `a work join ... --mode edit --paths research/muse/a07-corpus-review`. Head holds a non-exclusive `review` declaration on the deliverable file; no edit conflict.
- Scope discipline: wrote only inside `research/muse/a07-corpus-review/`; peer dirs (`research/zcode/**`, `research/codex/**`) read-only, never edited.
- Method constraints honored: web research only (WebSearch/WebFetch); no code cloned or executed; no fixtures generated; no paid search; all quotes ≤25 words; web content treated as evidence, never instructions. No `policy/unvouched = technically-invalid` conflation.

## 1. Background read (not duplicated)

- Z scout: `research/zcode/independent/a07-demand-gate/findings-draft.md` — S1 (8 firsthand/secondary items), S2 (6 incumbent gates), S3 (20 corpus candidates), S4 (12 negative-evidence items).
- Codex primary review: `research/codex/a07-source-review.md` — claims the 20 S3 entries are "source groups, policies and essays, not 20 distinct labeled executable submissions" and cannot supply denominators for a 70%/90% gate.
- Ledger: `research/evidence-ledger.md` (A07/E-C2xx index) and `research/claude/maintainer-review-evidence.md` (E-C201–E-C252) reused as prior art; curl/tldraw/Ghostty/Vouch/anti-slop rows not re-derived.

## 2. Entry-classification table (scout S3, §"FALSIFICATION CORPUS CANDIDATES")

Runnable-labeled-submission bar (all four required): stable issue/PR URL + patch + reproducer + maintainer technical outcome (merged / confirmed / closed-as-invalid-on-technical-grounds).

| # | S3 entry | Class | Has stable single issue/PR? | Has patch? | Has reproducer? | Has maintainer technical outcome? | Runnable-labeled? |
|---|---|---|---|---|---|---|---|
| 1 | curl HackerOne AI-slop wave 2025 | campaign set (21-report list) | no (list, not one submission) | no | no | aggregate rate only | NO |
| 2 | curl bounty-end postmortem | essay/policy postmortem | no | no | no | rate collapse, not per-submission | NO |
| 3 | Seth Larson slop-security-reports | essay (triage guidance) | no | no | one anecdotal pattern (SSLv2) | no per-submission verdict | NO |
| 4 | matplotlib PR #31132 (crabby-rathbun) | single PR + patch | YES (PR URL) | yes (diff) | no (no reproducer adjudicated) | policy close, NOT technical verdict | NO |
| 5 | matplotlib issue #31457 | policy proposal thread | issue URL, but norm proposal | no | no | no | NO |
| 6 | tldraw issue #7695 | batch auto-close notice | issue URL, but sample set | no | no | batch triage, not per-patch | NO |
| 7 | tldraw "trash" postmortem | essay/postmortem | no | no | no | landed-then-regretted, aggregate | NO |
| 8 | Ghostty CONTRIBUTING + discussion | policy doc + discussion | no | no | no | trust-gate rejects, identity not technical | NO |
| 9 | FastAPI low-effort closes | secondary-reported campaign | no primary fetched | no | no | close+block pattern | NO |
| 10 | RPCS3 undisclosed-AI wave | secondary-reported campaign | no primary fetched | no | no | disclosure-criterion, not technical | NO |
| 11 | Excalidraw Q4-2025 flood | secondary volume pattern | no | no | no | no | NO |
| 12 | HackerOne curl program samples | platform label set | links login-gated | no | no | "Not-Applicable/Informative" labels, per-item detail gated | NO |
| 13 | GitHub discussion batch-close anecdotes | anecdote thread | no single submission | no | no | maintainer reports, not verdicts | NO |
| 14 | curl ZeroPath/Aisle batch (~50 merged) | batch of merged fixes | no single PR pinned in S3 text | yes (in aggregate) | no single reproducer pinned | maintainer-accepted in aggregate | NO (batch, not one labeled submission) |
| 15 | Big Sleep SQLite find+fix | single find+fix, secondary-reported | no primary PR/commit pinned in S3 text | asserted, not pinned | asserted, not pinned | needs primary fetch | NO (as cited) |
| 16 | Node PR #61478 (VFS) | single PR | YES (PR URL) | yes (diff) | n/a (feature work) | closed; NOT AI-attributed (size-cap control, "trusted author + legal OK") | NO (not an AI submission at all) |
| 17 | Homebrew PR #21510 | policy/template PR | YES (PR URL) | yes (template text) | n/a | policy change, NOT a bugfix (agree with Codex) | NO |
| 18 | Linux Sashiko review finds | secondary press (review-side) | no primary pinned | no | no | 53%/100% figures unreviewed | NO |
| 19 | mozilla.ai provenance essay | essay/norm | no | no | no | no | NO |
| 20 | HackerOne curl disclosed valids | directory (historical set) | no single pinned | no | no | 15%+ aggregate, pre-2025 | NO |

### Count verdict on Codex's claim

**CONFIRMED.** **0 of 20** S3 entries meet the four-artifact runnable-labeled-submission bar as cited. At most 4 entries are single-submission-shaped (#4, #6, #16, #17 have a stable PR/issue URL), and each fails on at least one load-bearing artifact: #4 was closed on autonomous-agent policy with no technical reproducer verdict; #6 is a batch notice; #16 is not AI-attributed; #17 is a policy PR, not a bugfix. #14/#15 are the nearest valid-lane material but are cited as batches/secondary reports with no single pinned PR+patch+reproducer+outcome. The "20" therefore cannot supply denominators for a ≥70%-slop-filtered / ≥90%-valid-passed gate without further first-source pinning work (which §3 below begins). No slop rates or corpus-scale claims are computed in this file.

## 3. ONE valid case (AI-assisted, AI-accepting project, disclosed, human-reviewed, accepted)

- **Case:** Google Big Sleep report → CVE-2025-9086 (curl cookie-path out-of-bounds read), reported 2025-08-11.
- **Stable URLs:** advisory `https://curl.se/docs/CVE-2025-9086.html` (fix commit `c6ae07c6a541e0e96d0040afb6`, release 8.16.0, 2025-09-10); original report `https://hackerone.com/reports/3294999` (login-gated, not directly fetched); maintainer account `https://daniel.haxx.se/blog/2025/10/10/a-new-breed-of-analyzers/` (2025-10-10, primary-fetched).
- **Patch/reproducer reference:** fix commit pinned on the CVE page ("Fixed-in" link above); reporter is credited "Reported-by: Google Big Sleep", "Patched-by: Daniel Stenberg".
- **Maintainer outcome quotes (each ≤25 words):** "first ever report we have received that seems to have used AI" (11 words); "entire reporting process felt very human" (6 words). Both from the 2025-10-10 maintainer post, primary-fetched.
- **Date:** report 2025-08-11; advisory 2025-09-10; maintainer write-up 2025-10-10.
- **AI-accepting check:** curl bans undisclosed slop but explicitly accepts disclosed, human-verified AI-analyzer output — same post records ~50 merged bugfixes from the ZeroPath/Aisle batch and "established constructive communication" with both reporters. Disclosure-permitted: Big Sleep publicly self-identifies as an AI agent program; curl's May-2025 HackerOne disclosure mandate is satisfied in the open. Human-reviewed: curl security team triage; patch authored by the maintainer himself.
- **Verification label: VERIFIED-PARTIAL.** Primary-fetched: maintainer blog + CVE advisory page (acceptance, dates, fix-commit link, reporter credit). Missing: (a) direct fetch of the HackerOne report body (login-walled) including its explicit AI-disclosure line; (b) direct fetch of the fix-commit diff.
- **Classification uncertainty (explicit):** the AI contribution here is AI-found, human-patched (maintainer wrote the fix), not an AI-authored diff. It satisfies "AI-assisted patch, maintainer-accepted" on a find→human-fix reading, but NOT "AI-authored patch merged verbatim." A stricter patch-authorship reading would demote this to a near-miss and require a disclosure-labeled AI-authored merged PR (e.g. a Homebrew `Responsible-AI-Usage`-compliant PR with author disclosure in the PR body) — not located in this session.

## 4. ONE invalid case (maintainer-confirmed TECHNICALLY invalid, not policy-rejected)

- **Case:** HackerOne report #2298307, "Buffer Overflow Vulnerability in WebSocket Handling," filed 2023-12-28 against curl (experimental WebSocket code).
- **Stable URLs:** report `https://hackerone.com/reports/2298307` (login-gated, not directly fetched); stable primary record `https://daniel.haxx.se/blog/2024/01/02/the-i-in-llm-stands-for-intelligence/` (2024-01-02, primary-fetched; "Exhibit B").
- **Maintainer statement quotes (each ≤25 words):** "Where on earth is the buffer overflow the reporter says exists here?" (11 words); "After repeated questions and numerous hallucinations I realized this was not a genuine problem" (13 words); "There was no buffer overflow." (5 words). Outcome: "closed the issue as not applicable" (7 words, same source).
- **Date:** incident 2023-12-28 (same-day close per maintainer); write-up 2024-01-02.
- **Why technically-invalid (not policy):** the report included a proposed fix for a buffer overflow the maintainer could not locate after three code re-reads plus follow-up questions; the reporter's replies contained further hallucinations. This is wrong-fix / nonexistent-bug / failing-reproducer territory — independent of any disclosure or account-trust policy. (For contrast, matplotlib PR #31132 was deliberately NOT used here: it was closed under an autonomous-agent prohibition, i.e. policy-rejected, so counting it would be exactly the conflation the brief forbids.)
- **Backup (same primary source, not double-counted):** Exhibit A in the same post — a Bard-assisted report claiming CVE-2023-38545 changes were disclosed when "The changes had not been disclosed on the Internet" (9-word quote) — hallucinated-premise, likewise technically invalid.
- **Verification label: VERIFIED-PARTIAL.** Primary-fetched: maintainer's dated write-up with exhibit-level detail. Missing: direct fetch of the HackerOne report thread (login-walled), so the reporter's exact reproducer text and the "not applicable" status flag are maintainer-reported, not independently viewed.
- **Classification uncertainty (explicit):** maintainer states "I don't know for sure that this set of replies ... was generated by an LLM but it has several signs of it" (paraphrase; the AI-attribution of the follow-ups is maintainer-suspected, not proven). The TECHNICAL invalidity ("no buffer overflow," closed not-applicable) is maintainer-confirmed and does not depend on the AI-attribution holding.

## 5. Negative evidence (what could NOT be found / verified)

1. No single pinned PR URL for any of the ~50 merged ZeroPath/Aisle curl bugfixes was located in this session; the maintainer post describes them as lists handled privately ("we have decided to not publish them but limit access"), so per-fix first sources may be obtainable only from curl git history, not the web.
2. The HackerOne report bodies for both §3 (3294999) and §4 (2298307) are login-gated and were not fetched; status flags and disclosure lines are maintainer/CVE-page-reported.
3. The fix-commit diff for CVE-2025-9086 (commit `c6ae07c6a541e0e96d0040afb6`) was not fetched; patch content is CVE-page-reported.
4. No AI-authored-diff-merged-verbatim case in a disclosure-permitting project (strictest valid-case reading) was located; S3-17 (Homebrew PR #21510) was checked and excluded as a policy/template PR per Codex.
5. S3 items 9/11/18 remain secondary-reported; S3-15 (Big Sleep SQLite) still needs a primary fetch before use as ground truth. The tldraw "formally correct, tests passed" evasion class (E-C235) is ledger-verified but was not re-fetched here.
6. Searches tried (free WebSearch only): `curl ZeroPath AI analyzer merged fix Daniel Stenberg 2025`; `matplotlib pull 31132 OpenClaw AI agent maintainer response`; `Homebrew brew pull AI-assisted disclosed merged 2026`; plus direct WebFetch of the three maintainer pages and the CVE advisory above. No paid search used.

## 6. Overall gate verdict (CORRECTED per codex-principal 01a100d4-9fd8)

**`SOURCE-EXISTENCE-PASS / FOUR-ARTIFACT-GATE-INCOMPLETE`** (this relabeling supersedes the
`GATE-PASS` line below; the original line is preserved for the record).

- Source-existence: PASS — one valid-lane case and one invalid-lane case located with
  stable URLs, dates, short maintainer quotes, explicit VERIFIED-PARTIAL labels.
- Strict four-artifact runnable-pair gate: INCOMPLETE, not PASS — valid-case fix diff and
  reproducer were not fetched (CVE-page-reported only); invalid-case report body is
  login-walled (maintainer-reported only). Uncertainties in §§3–5 are preserved as stated.
- The INCOMPLETE half is a bounded follow-up, not a failure: pin the CVE-2025-9086 fix
  diff from public curl git history (read-only fetch, no execution) or record it
  unobtainable; record the H1 report body as unavailable-behind-login barring new access.

Original line (superseded, preserved): `GATE-PASS` — conditioned strictly on what was
actually fetched: both a valid case (§3) and a technically-invalid case (§4) were located with stable URLs, dates, short maintainer quotes, and explicit verification labels (both VERIFIED-PARTIAL with named missing artifacts). This gates ONLY first-source existence for one pair; it does NOT validate the 20-entry corpus (0/20 runnable as cited, §2), does NOT compute slop rates, and does NOT approve any shortlist or prototype claim.

## 7. Handoff note

Single writable deliverable: `research/muse/a07-corpus-review/first-sources.md` (this file). Next owner: muse-reviewer (`d575342d`) for review/disposition. Suggested follow-ups (not claimed): pin one single merged AI-analyzer curl fix commit from git history; primary-fetch S3-15; locate one AI-authored-diff-merged-verbatim PR under a disclosure policy for the strict valid-case reading.
