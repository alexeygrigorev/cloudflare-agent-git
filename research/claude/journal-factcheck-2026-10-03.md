# Journal fact-check — 2026-10-03

Tasker: claude-principal 01a0ffd1. Checker: zcy-claude-scribe. Method: fetched the live pages on 2026-10-03 ~05:50 CEST, compared every claim about Claude-owned material against repo records at `c66a5c3` (the site's own build stamp is "Site built 2026-10-03 03:47:34 UTC · Source revision c66a5c32da32", i.e. the check is against the current site). No website files were edited.

Pages checked:
- https://alexeygrigorev.com/cloudflare-agent-git/ (landing)
- https://alexeygrigorev.com/cloudflare-agent-git/daily/2026-10-03/
- https://alexeygrigorev.com/cloudflare-agent-git/projects/live-integration-radar/
- https://alexeygrigorev.com/cloudflare-agent-git/projects/storage-aware-workspaces/
- https://alexeygrigorev.com/cloudflare-agent-git/projects/fork-tournament/ , .../change-story-review/ , .../durable-task-handoff/ (no claims on the checked topics)
- https://alexeygrigorev.com/cloudflare-agent-git/checklist/ , .../experiment/ , .../research/

## Discrepancies (2)

### F-1. Daily report: 48.17% attributed to "normalizing" the first run; the corrected fixture numbers 42.37%/36.05% are missing
- URL: https://alexeygrigorev.com/cloudflare-agent-git/daily/2026-10-03/
- Quoted sentence: "Antigravity's first test on a pair of tiny tasks saved 53.15%, but read-only files had suppressed Python bytecode. After normalizing for that, the saving dropped to 48.17% , below the 50% bar set in advance."
- Correct fact: correcting the original fixture (label/bytecode artifact) gave **42.37%/36.05% cache-inclusive — D1 FAIL** (E-A040 corrected). **48.17% is a separate clean-identical-cache N2 rerun** (E-A042), not the normalized first run. Both are below the 50% bar, so the conclusion "D1 not passed" is unaffected; the causal chain and the lowest corrected numbers are wrong. The A16 project landing states it correctly ("The corrected tiny-task N2 experiment measured normalized whole-footprint savings of 48.17%..."); the checklist page repeats the same 48.17%-as-normalized shorthand as the daily.
- Source: research/evidence-ledger.md v3 (A16 row, E-A040, E-A042); research/approaches-20.md v3 disposition A16; research/antigravity/ owner files cited there.
- Severity: medium (misattribution between two runs; no conclusion change).

### F-2. Daily report: "the bug isn't fixed" omits that the fix is merged on codex-zcode main but not deployed
- URL: https://alexeygrigorev.com/cloudflare-agent-git/daily/2026-10-03/
- Quoted sentence: "An agent wrote a regression test for the repair, which expected exactly one execution and observed zero. The test ended with 0 passed and 1 failed , so the bug isn't fixed."
- Correct fact: the zcodex double-exec fix **bf9d7ed is merged to codex-zcode main (owner-approved) but NOT deployed** — the installed `~/.local/lib/zcodex/zcodex` is still the 2026-09-26 build, pending a user build/install decision. So "isn't fixed" is true only of the installed binary; readers are given no merge-exists fact. The failed test itself is mis-bounded (expected one execution, observed zero — a harness/runtime test failure); the orchestrator explicitly records it as "not a verified duplicate-execution fix", and Codex oversight warns "Do not infer deployed executable state from a source merge". A correctly bounded rerun is listed as pending — the daily's own "Next experiments" says the same.
- Source: coordination/claude.md line 83 (2026-10-03 entry); research/orchestrator/heartbeat-20261003T0224.md; research/codex/oversight-resume-20261003.md; research/evidence-ledger.md T11.
- Severity: medium (omission of the merged-fix state; "isn't fixed" is defensible for the deployed binary only).

## Checked, matches

1. **A01 lost primary status (joint, 01a0fe88-0dc8).** Daily: "Claude proposed withdrawing A01 as primary. Codex accepted." Checklist: "both principals withdrew primary status after the fair live comparison showed no separation." Landing card: "Primary recommendation withdrawn." Matches approaches-20 v3 (A01 conditional, no longer primary; joint Grok D-G25 + 01a0fe86-e1e2 + ACCEPT 01a0fe88-0dc8). The pages retain A01 as a research hypothesis with reopen conditions, so "withdrawn" is not overstated.
2. **A14 folded into A01.** No A14 claim found on any fetched page — nothing to contradict. (Repo: A14 folded into A01 runtime verification, Codex 01a0fe3a-a47b / Claude ACCEPT 01a0fe3b-2151.)
3. **Slot 6 open, no six signoff.** Daily: "Codex keeps five hypotheses and leaves the sixth slot open. Neither principal has signed it." Landing: "Five hypotheses retained. A sixth slot remains open; no final shortlist has been signed." Checklist: "slot six is open. Identical-digest approval from both principals is still required." Matches ledger Open ("No signed shortlist digest... no SIGNOFF from either principal"). The linked research/shortlist-6.md exists in the repo.
4. **A16 D1 not passed.** A16 landing and checklist both state 48.17% < the registered >50% gate; correct conclusion, subject to F-1's run-attribution imprecision.
5. **Real-host U7 numbers.** Landing/experiment pages: 472 worktrees, 25 repos, 111.7 GiB physical union, 69.4 GiB = 62.1% deps/build, .venv 57.3 GiB, node_modules 7.9 GiB mostly shared, 264 merged-HEAD worktrees "doesn't make them safe to delete", no deletion authorized. All match research/claude/u7-real-worktree-measurement.md, including the errata story (~80% corrected to 62.1% after root arithmetic review). Daily's "16 GiB drop, 132→116 GiB, Rust target 39.65 GiB, earlier 24 GiB was a claim not a measurement" matches research/orchestrator/heartbeat-20261003T0224.md and coordination/antigravity.md (which recorded 132→115 GiB; the two recorded endpoints differ trivially by timestamp; the daily cites the orchestrator's 116).
6. **zcodex double-exec.** Reproduced-probe description is accurate; deployment state handled incorrectly — see F-2.
7. **Eligibility.** "US or Canadian residents, so my eligibility is unresolved" matches T10 (eligibility unresolved, not a research blocker).

## Notes
- Site build is current (built from c66a5c3, pushed minutes before the check); the discrepancies above are in the prose, not staleness.
- Daily byline "Written with Claude Opus" and the snapshot/disclaimer footers are consistent with the authorized writing workflow (user messages 27-30).
