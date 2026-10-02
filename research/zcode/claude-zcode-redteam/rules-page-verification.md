# Rules page + PDF verification (claude-zcode-redteam, independent pass)

Fetched 2026-10-02 ~20:30-20:40 CEST by this delegate. Two sources, fetched separately: (a) https://www.cloudflare.com/git-competition (challenge page), (b) https://www.cloudflare.com/documents/build-next-gen-git-platform-competition-terms.pdf (downloaded to /tmp, `pdftotext -layout`, 4 pages). This independently confirms claude-principal's rules-verification.md (E-C009..E-C015); new IDs E-RZ2xx below.

## Challenge page (E-RZ201..204)
- E-RZ201 "Submit by October 14" — no time/timezone on the page itself; PDF is the authority for cutoff time.
- E-RZ202 "Send a 5 to 10 minute demo, open source code, and instructions to run it by October 14."
- E-RZ203 "Selected teams are announced October 16. We will fly up to two members from each team to Connect." Three finalists.
- E-RZ204 First place: "$25K in Cloudflare credits, plus invitations to the VIP speaker dinner." Page's "View Rules" links to the same terms PDF.

## Official rules PDF (E-RZ205..216, verbatim-anchored)
- E-RZ205 Contest period: begin **October 1, 2026 9:00 AM EDT**, end **October 14, 2026 11:59 PM PDT** (sponsor clock authoritative). = Oct 15, 08:59 CEST.
- E-RZ206 Eligibility (s.3): legal resident of **US or Canada**, 18+ as of Start Time. "VOID OUTSIDE OF THE UNITED STATES AND CANADA". Also excluded: sanctioned parties; Cloudflare employees/officers/directors + immediate family/household; **employees of government departments/agencies/public sector enterprises/state-owned entities**. → Eligibility question for user/orchestrator stands (user is presumably EU-resident: research/prototyping unaffected, but *entry* would need an eligible US/Canada entrant; no submission authorized).
- E-RZ207 Entry (s.4): via application form on competition website + 5-10 min video + repo + run instructions; received by end of Contest Period; **one submission per entrant**; "Persons may not enter using robotic, programmed, or any other automated means of entry" (agents build the project; a human submits).
- E-RZ208 Platform requirement: "must use Cloudflare's developer platform, including Cloudflare Workers and Artifacts, to build their Project, which must enable multiple agents working on changes concurrently."
- E-RZ209 License: MIT / Apache-2.0 / BSD-2-Clause / BSD-3-Clause + LICENSE file in repo.
- E-RZ210 Content limits: no personal attacks "on anyone or any discernible product, including competitor products" (demo must not disparage GitHub etc.); no weapons/sexual/political/illegal content.
- E-RZ211 Judging (s.6), 1-5 each: originality/quality of prototype for agent-oriented software collaboration **50%**; effectiveness of multi-agent **concurrency, coordination, context preservation, review, conflict handling** **25%**; ease of use/product UX **25%**. Tie-break: highest originality.
- E-RZ212 Finalists: three (3), notified in advance, **10 minutes live on stage**, Cloudflare Connect, **Moscone West, San Francisco, October 21, 2026**; travel/hotel for up to 2 reps (not transferable; passports/visas/incidentals on entrant).
- E-RZ213 Winner must be **physically present** at Connect to be eligible; announced on stage; same judging criteria.
- E-RZ214 Prize: $25,000 USD Cloudflare credits **valid 12 months from award** + VIP dinner invite (ARV $200). Taxes on winner.
- E-RZ215 **Submissions are not confidential** (s.9): "Sponsor and its affiliates develop products and services that may be similar to or compete with Projects, and nothing in these Official Rules restricts Sponsor from independently developing, acquiring, or marketing such products or services." Entrants retain project IP; sponsor gets promo rights over video/presentation only. → Strategic implication: treat our repo (public, MIT) as visible to Cloudflare; differentiation must come from execution + demo, not secrecy.
- E-RZ216 Governance: California law, JAMS arbitration SF; disputes class-action-waived.

## Cross-check vs challenge page + blog
Page "announced October 16" (E-RZ203) vs PDF "notified in advance of Cloudflare Connect" — consistent; no conflict. Blog E-C003 "October 14" consistent with PDF cutoff. No discrepancies found between the three sources.

## Red flags for our plan
1. Eligibility (E-RZ206) is the only genuine blocker-class unknown for *entering*; user decision, not ours. Everything else is buildable.
2. Oct 16 finalist announcement is 2 days after cutoff → judges review quickly; repo must be self-explanatory (run instructions first).
3. Winner must fly to SF Oct 21 — flag to user early (travel feasibility).
4. "No personal attacks on any discernible product": competitor-matrix language in the demo video must stay factual/positive.
