# Independent challenge: five Pro outputs vs the six-approach shortlist (Muse view, 1 page)

Scope: pro-angle-1..5.md (model-generated, no benchmarks run, citations need checks)
vs shortlist-6.md draft 3 (A01/A14/A16/A05/A06/A10, unapproved, live-gate pending).

## Where the mapping is strong
- Pro-1 Counterexample Merge Lab → A01 Live Integration Radar. Faithful: both demand
  the fixed-harness interaction proof (base+A, base+B pass; combined fails) and both
  name the merge queue as the falsifier. Keep.
- Pro-2 Decision Arena → A05 fork tournament. Faithful, including hidden tests and
  reviewer selection. Keep, but Pro-2's "evidence receipts" foundation is load-bearing
  and A05's comparator (who judges, tie/neither handling) is still vague.
- Pro-3 Recovery Capsule → A10 durable handoff. Faithful, and Pro-3's kill-test
  (one agent dies mid-task, replacement resumes without reviving obsolete
  instructions) is sharper than A10's current MVP wording — import it verbatim.
- Pro-5 runnable-workspace cost → A16. Faithful, and Pro-5's unit-of-analysis
  correction (optimize editable/buildable/testable workspace lifetime, not fork
  size) should constrain A16's metrics.

## Correction (round 2): Task Passports IS parked with rationale — my "silent drop" claim was wrong
Claude's consultation-2026-10-02 §1 (which I had not read) challenges Passports on
the record — no first-hand demand in any ledger, weak on the 25% concurrency
criterion, context-starvation failure mode, small U7 effect — and parks it as an
A12 refinement with explicit reopen tests R-TP1..R-TP4 (evidence / absence-vs-clone
/ usefulness / leak). Codex agrees per the Claude checkpoint. I retract challenge
1 below as stated and accept the parking with two standing notes: (a) R-TP2 (Grok
R5-1 falsifier) is well-posed and cheap — run it early so a pass can actually
contest A06/A10 slots per the agreed rule; (b) first substitute for a failing A10
remains Contract Packs (A18/Pact incumbent), not Passports, per Claude — agreed.
My A14-fold and A01 action-rate-gate points stand and concur with space-bunny's
independent challenges; heartbeat-1950 directs these be addressed before signoff,
which I am not giving.

## The remaining challenge (originally item 2; item 1 retracted above)
1. **Pro-4's primary (Task Passports: per-task scoped repos + revocable contracts)
   has no home in the shortlist.** The draft's rationale for excluding it is not
   written down anywhere I could find. Scoped-repos is arguably the most
   differentiated of the five Pro recommendations (least overlap with merge
   queue/Pact/previews) and the most Cloudflare-natural (Artifacts forks already
   partition code; passports add the access boundary). If it was cut for Oct-14
   feasibility, say so with a kill-test; if it was cut on novelty, that contradicts
   Pro-4's competitor analysis. Silent drops are how selection bias enters.
   Falsifier: two agents on one codebase, one with a passport-scoped fork, show a
   task the scoped agent completes without ever receiving the restricted path, and
   a publish attempt outside scope that the gateway rejects. If scoping adds no
   measurable leakage/remediation win over fork-per-task, park it.
2. **A14 and A06 look like the weakest novelty stories and both lack a live
   discriminator.** Codex's own draft admits A14's isolation result is currently
   matched by the ordinary control (fold-into-A01 proposed) and A06's summaries are
   "commodity" versus CodeRabbit/Copilot review. Pro-1..4 each warn against exactly
   these traps (another dashboard, another review bot). Retaining both while
   Pro-4's top pick is absent risks a shortlist optimized for feasibility over
   differentiation — which inverts the judging weights (50% originality). My
   bias: cut one of A14/A06 (A14 is the天然 fold candidate per the draft's own
   kill clause) and trial Task Passports as the sixth, or record why not.

## Falsification risks across all six
- Every lane's gate ("two actual coding agents", "live uptake", "hidden tests")
   is still pending; the shortlist is currently a hypothesis set, which the draft
   honestly states. The danger is calendar, not logic: with gates due Oct 5–8 and
   no cloud credentials authorized yet, at most 2–3 lanes can plausibly pass.
   Rank the gates by cheapest-first (A01 uptake comparison and A16 two-task byte
   comparison need no cloud) and kill loudly rather than carrying six
   half-evidenced lanes to Oct 13.
- Pro citations (arXiv replay stats, LinkedIn checklists, vendor benchmark claims)
  are correctly labeled unverified in pro-angle-1 and the heartbeat; the shortlist
  inherits them as E-evidence. Fine as priors, but no approach should cite a rate
  (e.g. 41.7% cross-platform conflicts) as demand evidence — the sample is
  stratified PR history, not a market.
