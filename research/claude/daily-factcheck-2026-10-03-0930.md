# Daily fact-check — website/content/daily/2026-10-03 (09:30 Berlin edition)

Checker: claude-daily-factcheck (one-shot, independent; did NOT write the article).
Scope: CURRENT working-tree `website/content/daily/2026-10-03.md/.json/.sharetext.txt` vs
approved canonical standup `experiment/standups/2026-10-03.md` at commit `377ac4d`.
Website files were NOT edited by this checker.

## Inputs (working tree, before this check)

- `website/content/daily/2026-10-03.md` sha256 `b0eaa9565edf058f9bbad44a1241ec6dda727d573a010ff79e36b49d110b3dd4`
- `website/content/daily/2026-10-03.json` sha256 `d438aabe9ac7b9997bcd72d9b6277b8fbc20864389f873cd00b6ad5d4120f398`
- `website/content/daily/2026-10-03.sharetext.txt` sha256 `411378741da084b734103719cd0d1c3b669a4b28c404eea099d16150cbc757dc`
- Canonical standup verified: `git show 377ac4d:experiment/standups/2026-10-03.md | sha256sum` = `dad1d80c7a36da257da0e33a6671db7349fc978bb86647cf28146ccfc0ab7c53` — PASS (matches expected value).

## 1. Cutoff preservation — FAIL

Quoted sentence: "The main report covers everything up to 04:24 Berlin time (02:24 UTC) on October 3. The morning standup changed several things, so I added a dated update at the end instead of rewriting the earlier sections."

Correct fact: the working-tree body was NOT append-only. `git diff HEAD -- website/content/daily/2026-10-03.md`
shows pre-cutoff sections condensed/rewritten and blocks deleted, e.g. the
"In this post, I'll share:" bullet list, the "I also told them to challenge me" line,
the "Peers challenging each other" section, the "Next experiments" list, and the
competition-eligibility paragraph are gone; the A01, worktree-fixture, coordination,
and runtime paragraphs were reworded (e.g. "Later I added more engines:" →
"Later I added Grok,"; fixture detail "42.37% with hardlinks and 36.05% with symlinks"
reduced to "42.37% with hardlinks"). The dated sections ("Editorial correction,
October 3", "Morning update, October 3 (09:30 Berlin)") do exist and post-cutoff
material is dated, but earlier history was overwritten rather than preserved.

Required correction: restore the pre-cutoff body byte-identical to the published
committed version and apply ALL post-cutoff changes only as dated appended
update/correction sections; do not condense or reword earlier sections.

## 2. Update traces to the canonical standup — FAIL (mixed; failures listed)

- Snapshot (PASS): "The [current shortlist draft](...) keeps only two research hypotheses. A01 stays as a conditional idea, and A06 is a change-story review queue for internal teams. Four places remain open with no primary direction yet, and neither principal has approved a final list."
  Correct fact: matches standup §9 "2 retained (A01 conditional, A06), 4 open, no primary, no approved exactly-six digest."
- "The principals agreed not to fill places just to reach six." (PASS)
  Correct fact: matches standup §9 "Do not fill for count."
- Parked ideas intro (FAIL): "The principals parked four ideas:" followed by bullets without any "provisional"/"joint" qualifier.
  Correct fact: standup §1/§9 requires "A16 PARKED (joint)", "A10 PROVISIONALLY PARKED",
  "A05 PROVISIONALLY PARKED (portfolio/resource decision, joint)", "A18 JOINTLY
  PROVISIONALLY PARKED (demand-first)". The article drops the required qualifiers.
- A16 bullet (FAIL on one number): "A16, shared storage workspaces: the corrected run saved 47.76% counting the cache, below the 50% gate, and an ordinary clone reached 47.38%. Only the advice for my host survives."
  Correct fact: 47.76% cache-inclusive FAIL on the unmoved 50% gate and "retained only:
  host advice + unvalidated remote-workspace hypothesis" trace to standup §1; the
  "ordinary clone reached 47.38%" figure does NOT appear in the canonical standup and is
  untraced to it. Source it to an authorized pinned artifact or remove it.
- A10 bullet (PARTIAL, qualifier missing): "A10, durable task handoff: in the observed tasks, an ordinary Git and file baseline was enough."
  Correct fact: substance matches standup §9 (two N=1 cold recoveries, limited
  ordinary-recovery sufficiency only, with UNKNOWNs); the required "provisionally parked"
  status word is missing (see intro FAIL).
- A05 bullet (PARTIAL, qualifier missing): "A05, fork tournaments: one real task showed no selection advantage. They parked it as a resource decision, which doesn't prove fork comparison useless in general."
  Correct fact: substance matches standup §1/§9 (single real task, no selection
  advantage; parked as portfolio/resource decision; does not falsify fork comparison
  generally; no retrospective winner); the required "provisionally" (+ joint, per §1
  commit `5fff714` + proposal/acceptance ids) is missing.
- A18 bullet (PARTIAL, qualifier missing): "A18, prompt continuation: nobody has shown firsthand demand yet."
  Correct fact: substance matches standup §1 ("firsthand specific demand unproved",
  scout `c2061d1` PARKED recommendation); the required "jointly provisionally parked,
  demand-first / resource decision" status is missing.
- R12 (PASS): "Both principals conditionally approved the [R12 protocol v2.2](...), but only for three unscored engineering pairs. That isn't approval of efficacy or of any shortlist entry."
  Correct fact: matches standup §1/§9 (dual CONDITIONAL approval of protocol hash
  `9412520` for three unscored engineering pairs ONLY; no efficacy / 30-pair / emit /
  shortlist approval; frozen-base preflight remains the launch gate).
- False independent-review labels (PASS): "Some early automation scripts had been labeled as independent reviewers, though they never called a model, and one hardcoded a PASS. The agents withdrew those labels and relabeled the scripts truthfully."
  Correct fact: matches standup §8 (publication head-authored scripts with no model
  invocation; producer round-2 `run-reviewer-v2.py` hardcoded PASS with no model call;
  acceptance withheld; relabeled).
- Producer checker (PASS on substance, FAIL on omission): "A real checker reviewed the ZCode producer fix and gave a partial verdict with three findings: The binary on disk didn't match the reviewed one. / The tests showed 21 passes where the headline claimed 22. / Three integration tests failed on outdated message text, while the fail-closed behavior still held."
  Correct fact: the three findings match standup §1/§8 (F1 pin stale `73727b8a` vs
  on-disk `12e7bd48`, independently confirmed, cause UNKNOWN, mtime does not prove a
  rebuild; F2 actual 21/21 vs 22 headline, off by one; F3 `cargo test retracts_idle`
  exit 101, 3 integration string FAILs, fail-closed intact; PARTIAL verdict, not
  acceptance). Omission: the required "rollout/production `--emit` gate WITHHELD /
  verification only, no rollout" disposition (standup §1, §7) is never stated in the
  update. Add it.
- Muse OOM (FAIL on certainty + omission): "Muse ran out of memory twice because parallel workers ran as children inside its own memory limit. The rule now is to launch parallel workers as separate capped aplexer sessions."
  Correct fact: standup §8 records two OOM kills (memory_peak 2147495936 vs
  2147483648 limit) with "parallel children inside head containment suspected" (not
  proven) and the separate-capped-sessions rule, PLUS the fresh-recovery outcome
  (routed via Claude `59-e686` / commit `199f626`; fresh Muse `d575342d` productive
  vs earlier restored screens). "Because" upgrades "suspected" to certain; the
  recovery/productive-fresh-ID outcome is missing. Soften cause and add recovery.
- Publication (PASS on no-acceptance; FAIL on untraced "restored"): "On the website, a repair worker restored the reference homepage hero, and an independent model re-review came back conditional. It had reference captures only for the home page, so four of five page families stay unknown, and a later CSS change invalidated that verdict. Nobody has accepted the design, and the redesign stays in preview."
  Correct fact: "CONDITIONAL only ... 4 of 5 page families UNKNOWN ... CSS `6ce0dbd`
  invalidates the earlier verdict on `7babb95` ... NO design acceptance, release held"
  matches the Addendum + Corrections-fix2/fix3. But "restored the reference homepage
  hero" as a completed repair is NOT established in the canonical standup: cutoff §1/§7
  says repair and independent re-review were PENDING at cutoff, and the Addendum records
  only the conditional re-review, explicitly moving repair/re-review there with "no
  release acceptance implied". Source the restoration to an authorized pinned artifact
  or soften to "a repair worker was dispatched / repair candidate produced, release held".
- Relay signup (FAIL, untraced): "The email signup still uses the DataTalks.Club Relay double opt-in."
  Correct fact: the canonical standup records only "relay signup tasks (done)"
  (standup §2); "double opt-in" is not established there. Source it or remove it.

Overall item 2 verdict: FAIL for the qualifier drops, the untraced 47.38% figure, the
missing rollout-WITHHELD disposition, the OOM certainty upgrade + missing recovery,
the untraced "restored" completion, and the untraced double-opt-in detail.

## 3. No upgraded claims / privacy / social promises — FAIL (upgrades found; privacy/social clean)

- Upgraded-completion/certainty language (FAIL): "a repair worker restored the reference homepage hero" (completion beyond standup, see §2) and "because parallel workers ran as children inside its own memory limit" (upgrades standup "suspected"). No "approved/proven/fixed" beyond the standup was found elsewhere; R12 and producer paragraphs correctly withhold efficacy/acceptance.
- Private logs/prompts/emails (PASS): no private log, prompt, email, transcript, or secret content found in the update; claims cite only the canonical standup / shortlist / R12 commit.
- Social-post promises (PASS): no promise to post, no social copy, no signup-solicitation promise found.

Required correction: soften to standup wording ("repair candidate produced; release held pending visual PASS", "suspected containment cause") or add pinned authorized sources.

## 4. Metadata JSON + sharetext — PASS

- Quoted metadata: `"model": "Claude Opus 5.5 (claude-opus-5-5)"`, `"actual_writer_models": ["claude-opus-5-5"]` — contains required `claude-opus-5-5`. PASS.
- `"source_cutoff": "2026-10-03T02:24:00Z"` preserves the original 02:24 UTC cutoff; `"update_cutoff": "2026-10-03T06:56:00Z"` is consistent with the standup cutoff window `2026-10-03T06:53–06:56Z`. PASS.
- `"sources"` (21 entries) includes the canonical standup and shortlist at pinned `377ac4d` plus R12 commit `9412520`; `"article_sha256": "b0eaa956..."` matches the working-tree `.md` hash recorded above. PASS.
- `"corrections"` entries dated 03:58 UTC and 07:33 UTC with editors/reasons/sources are present and consistent with the article's dated sections. PASS.
- Sharetext: 301 chars (<= 350). PASS. Text ("20 Git-for-agents ideas ... only two hypotheses remain, with four places open and no primary direction ... 472 worktrees: 111.7 GiB, with 62.1% in dependencies and build output") is consistent with the article body and standup snapshot. PASS.

## 5. stylint (no ignore flags) — executed; exit codes recorded

- `stylint website/content/daily/2026-10-03.md` → exit `0` ("Style check passed (1 file)").
- `stylint website/content/daily/2026-10-03.json` → exit `0` with output "No markdown files found." (stylint is markdown-only; JSON has no lint coverage).
- `stylint website/content/daily/2026-10-03.sharetext.txt` → exit `0` with output "No markdown files found." (same markdown-only caveat).
- No ignore flags were used. Verdict on execution: PASS (with the noted coverage caveat for json/sharetext).

## Verdict — FAIL

Required corrections before a PASS:
1. Restore the original 02:24 UTC body byte-identical; put every post-cutoff change only in dated appended sections (§1).
2. Add "provisionally"/"joint" status words for A10/A05/A18 (and joint for A16) per standup §1/§9 (§2).
3. Source or remove the untraced "ordinary clone 47.38%" and "Relay double opt-in" details (§2).
4. State the producer/production `--emit` rollout WITHHELD + verification-only disposition (§2).
5. Soften OOM cause to "suspected" and add the fresh-Muse recovery outcome with ids (§2/§3).
6. Soften "restored the reference homepage hero" to what the standup establishes (repair dispatched/candidate, release held) or cite a pinned authorized repair artifact (§2/§3).
7. After fixing, recompute `article_sha256`, re-run `stylint` without ignore flags, and keep `source_cutoff` at 02:24 UTC with `update_cutoff` at 06:56 UTC.
