# Acceptance review — C-ZCODE-ACCEPTANCE-REVIEW-2109 (delegate codex-feasibility-review, session cf3e7fb7)

2026-10-02, Europe/Berlin, written ~22:45–22:50 under the original 90m cap. Identity verified first: native `aplexer whoami` = `cf3e7fb7-53e0-4b7a-9fd5-9f44da7cc0a7` / `codex-feasibility-review` / this workspace. Review only; no reruns of old fixtures; Grok protocol/check/publisher treated as frozen comparator (read at commit 7ef2269/2f4681c state, files `research/grok/a01-fair-*.md|py`). Evaluator sanity is kept separate from model outcomes throughout: nothing below says anything about any agent's actual performance; no model outcome exists in evidence here.

## 1. Codex `feature-oracle.py` + `input-manifest.json` @171ff6c vs Claude C-P1

**Agreement (verified from `git show 171ff6c`):** rev2 implements C-P1 correction 1 — two-part acceptance. `feature-oracle.py` A functionally exercises caching (CountedValues read-count: repeated read must hit cache, write must invalidate) + requires `cache-notes.md`; B wraps `writer.put` with a forbidden wrapper and requires `update_many` to bypass the public put path + `bulk-notes.md`. README @171ff6c: "Passing common behavior while leaving the assigned optimization unimplemented does not complete the task"; completed A/B/combined require role feature acceptance; base is NOT required to pass role checks (correct — base passes common oracle, fails role checks, per manifest preflight). This closes C-P1's "notice arm passed by not doing the task" hole, and matches Grok's protocol scoring ("2x2; oracle pass with task fail is a failure").

**Real false-pass / limits found (all dated 2026-10-02):**

1. **B alias bypass (documented, but makes B pass provisional).** The forbidden-wrapper check monkeypatches the module attribute; a candidate that captured the original `put` into a private alias at import time (or inlines put logic under another name) never trips the wrapper and passes while arguably not implementing the intended structure. README itself concedes: "dynamic monkeypatching alone does not rule out a captured wrapper alias" and defers to "alias/callgraph … separate controller checks". Until that separate review is actually performed and recorded per candidate, B "task pass" is provisional, not established.
2. **A capacity/eviction never exercised.** The A check tests one key's cache+invalidation only; an unbounded cache with no 64-entry capacity/eviction passes. Same documented-deferred status: capacity review is a separate controller check; A "task pass" is provisional until it is run and recorded.
3. **Oracle visibility / overfit risk (not documented — new finding).** `input-manifest.json` lists `feature-oracle.py` among the input files, and the offered packet `.local/codex/a01-pilot-20261002/` contains `feature-oracle.py` and `oracle.py` at top level. If either is copied into the four agent worktrees, agents can read the exact probe keys (`feature-cache-row`, 41/42, `feature-bulk-row`) and hardcode them — a mechanical pass that is not the requested general behavior. Corrective, cheap: oracles stay controller-side; worktrees contain only task prompt + source files; record the exclusion in the run manifest. (Unknown whether Grok's prepare copies them in; verify before dispatch — do not assert.)
4. **Acceptance-record provenance gap (small).** Manifest records utc/seed_sha/file digests (good), but the per-candidate acceptance record should bind role + HEAD sha + tree digest + oracle/feature-oracle digests + utc + exit codes at check time, so "passed" is tied to an exact tree, per the packet's own receipt-identity principle (base/candidate/tree/policy version).

**Task-policy agreement verdict:** rev2 and C-P1 agree on two-part acceptance and 2x2; the disagreement is only in the two provisional gaps (1, 2) and the unaddressed visibility risk (3).

## 2. Grok fair protocol / `a01_fair_check.py` / `a01_fair_publish.py` as frozen comparator

**Sound equal-policy core:** identical task SHAs, prompts, interface (`a01-fair-interface.md` byte-identical), model `glm-5.3-flash`, 20-min timeout, 512M/64-pid caps, same common oracle SHA `56482a4b…`; only peer-byte publication differs (completion = `git show HEAD:file`, live = working tree incl. uncommitted, both suppressed when bytes equal seed so an untouched sibling is not fake WIP). Separate clones per arm (D-G24 workflow), seed preserved, scratch + private bundle retained. N=1 explicitly not the Y1 gate. This is a fair comparator.

**Task-policy disagreements vs Codex rev2 (weaker thresholds — the datapoint, not a defect):**
- Grok A task pass = notes nonempty + `reader.py` differs from seed; `cache_observable` recorded but **not required** ("the task allows a correct bypass"). Codex A requires functional caching + invalidation. So Grok-A-pass ⊅ Codex-A-pass.
- Grok B task pass = notes + `writer.py` differs + `update_many` of 3 keys calls put **< 3 times** (counting wrapper). Codex B requires **zero** public-put calls (forbidden wrapper) plus visible values. A 2-put candidate passes Grok and fails Codex.
- Same alias/capacity blind spots as Codex's checker (documented in protocol only as recording, not gating).
- **Corrective consequence:** run BOTH checkers per candidate; report both 2x2 columns; where they disagree the disagreement is the result. A Grok-only task pass must not be labeled rev2-accepted. (Grok's own protocol already requires "task pass and oracle pass both required" — this is about which task check governs.)
- Provenance: check JSONL should include HEAD sha/tree digest per invocation per §1.4; ORACLE/SEED paths are hardcoded to the frozen scratch `/tmp/grok-a01-fair-20261002` — fine for a frozen comparator, but the acceptance record must survive scratch release via the retained bundle.

## 3. Evaluator sanity vs model outcomes (kept separate)

Codex manifest `preflight_scope`: "checker sanity only; constructed positive control cleaned, never offered as a model candidate/outcome" — correct and sufficient design. Grok: "Scratch self-test passed before dispatch" — same separation. Neither preflight nor self-test is evidence about agents. N=1 pair ≠ uptake proof (README, D-G24). This review found checker limits only; it establishes nothing about either arm's model behavior.

## 4. Compact corrective request (no further simulated uptake)

1. Before dispatch: verify agent worktrees contain no oracle/feature-oracle copies; record the exclusion in the run manifest (fixes finding 3).
2. Per-candidate acceptance record binds role + HEAD + tree digest + checker digests + utc (fixes 4).
3. Actually perform and record the deferred alias/callgraph and capacity/eviction reviews for any accepted candidate (upgrades 1–2 from provisional to established), or relabel passes "provisional pending structural review".
4. Run both checkers; report joint 2x2; disagreements are datapoints (fixes §2 disagreement).

## 5. Publishing answer (explicit, as asked)

**Yes — the reviewed packet files (research/codex/a01-live/ at 171ff6c: feature-oracle.py, input-manifest.json, README, task-a/b) may be published by Codex unchanged after sanitization.** I found no credentials, private config, or personal data in them; sanitization should only strip machine-local absolute paths (e.g., `/tmp/grok-a01-fair-20261002`, `/home/alexey/...`, `.local/...` references) and keep the digests. This is an **ownership handoff acknowledgment only — not shortlist approval** of A01 or any approach.

## 6. Withdrawals and supersessions (dated 2026-10-02)

- **Withdrawn:** my earlier blanket worker-UI advice tied to user steering messages 21/22 (interactive-only executors). README @171ff6c's "head-chosen genuinely bound headless or interactive task executors" is the better rule and supersedes it.
- **Superseded:** the missing-notice-receipt concern from the earlier smoke round — superseded by Grok's delivered fair-pilot result/protocol (receipt + retained bundle defined). Diagnose stalled old sessions only for record-keeping, not as a gate.
- All findings above are dated 2026-10-02, Europe/Berlin, and are based on read-only inspection of committed files; no fixtures rerun, no model outcomes evaluated.

## 7. Own inbox this round (read-only)

- claude-principal `01a0fe4a-4640-…bc3b`: MUTUAL-CHECK ACCEPTED (token processed once); next check = delivered pilot result or 2026-10-03 09:00; asks this packet to challenge `research/claude/u7-real-worktree-measurement.md` (f76be38) — **received, not yet done** (outside this assignment's scope/time); recorded as an explicit reply, not agreement by me.
- zcode-independent `01a0fe57-8772-…` (+duplicate `…8b25`, both marked processed once): ZCODE-HARNESS-ACK — harness/run ownership ACK + pilot registration ACK, agrees with the three smoke deviations. Explicit reply; ownership handoff now acknowledged on both sides.
- No ACKs sent by me from the inbox path; the single genuine send this round is the delivery notice/reply to the current codex-principal (recorded in status.md with full ID).

## 8. Delivery notice (recorded after send)

Single genuine reply/delivery notice sent to the current codex-principal via `aplexer message reply 01a0fe5d-0429-7b92-bf0f-c23712e0a537` (genuine tag, own identity, once; raw JSON in /tmp/cf3e7fb7-relay-logs/acceptance-review-reply.json). Full message ID: `UNPARSED`. rc/delivery recorded in the JSON; no other sends this round.

## 8. Delivery notice (recorded after send)

Single genuine reply/delivery notice sent to the current codex-principal via `aplexer message reply 01a0fe5d-0429-7b92-bf0f-c23712e0a537` (genuine tag, own identity, once; raw JSON in /tmp/cf3e7fb7-relay-logs/acceptance-review-reply.json). Full message ID: `UNPARSED`. rc/delivery recorded in the JSON; no other sends this round.
