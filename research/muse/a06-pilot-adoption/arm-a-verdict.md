# muse-r18 ARM-A verdict: ca1 pilot-adoption review (ordinary format)

## 0. Reviewer identity (first action)

- `aplexer whoami --json`: id `628655de-ff93-4aae-9e47-6326324bc6d6`, tag `muse-r18`,
  engine `shell`, workspace `/home/alexey/git/cloudflare-agent-git`,
  parent session `d575342d-1c1f-4c31-a3d1-a295d6d08873` (head: muse-reviewer).
- whoami JSON carries no model field. Model/route for this review, from tasking
  context: `opencode-go/muse-spark-1.3-contributor` (worker engine shell).
- No prior context on ca1. Reviewed ONLY the listed evidence packet; where
  something could not be verified from listed sources it is recorded as
  not-verified, not hunted elsewhere.
- All writes confined to `research/muse/a06-pilot-adoption/arm-a-verdict.md`
  (+ scratch `.local/muse-r18/`). Everything else treated READ-ONLY. No `/tmp` used.

## 1. Decision: REJECT (failing criterion C2; C4 also not met)

Question: should ca1 (candidate binary sha256
`ca1e8030da0efb62504d1777a6f2a60358b002c1c0b1ace3a7268e817e5bbcd1`)
be adopted for use on ONE existing head? I advise; the head owner decides.

| Criterion | Finding | Basis |
|---|---|---|
| (C1) all pins verifiable | **PASS** | Candidate + rollback hashes self-verified MATCH (§2); JSON/report internal shas consistent; r17 staged-file hash matches brief value |
| (C2) no open safety concern on the delivery path | **FAIL** | r17 `SAFETY-CONCERN-CONFIRMED` stands unrefuted anywhere in the packet (see D1) |
| (C3) rollback path exists and is hash-verified | **PASS** | `/home/alexey/.local/bin/aplexer` sha256 self-verified MATCH, read-only (§2) |
| (C4) scope bounded to one named head with monitoring | **FAIL** (secondary) | No listed evidence names an existing head as the adoption target or states a monitoring plan (see D3) |

ADOPT requires ALL criteria. C2 fails, so the decision is **REJECT**.
C4 independently also fails. This is not a TIE: the C2 evidence is decisive,
not ambiguous.

## 2. Pin verification (commands run myself, outputs recorded)

1. `date -u +%FT%TZ` → `2026-10-03T08:49:05Z` (review start reference).
2. `sha256sum .local/producer-review/bin/aplexer-b4-variant-a` →
   `ca1e8030da0efb62504d1777a6f2a60358b002c1c0b1ace3a7268e817e5bbcd1` —
   **MATCH**es the ca1 question pin and `pilot_results.json` candidate sha.
3. `sha256sum /home/alexey/.local/bin/aplexer` →
   `8d49a216d43c70843bc07705f4c11eb13f3eb51646d5c6fc204ce0796ce618c4` —
   **MATCH**es the expected rollback pin (read-only check, nothing executed).
4. `sha256sum .local/pilot-ca1/PILOT-REPORT.md .local/pilot-ca1/pilot_results.json` →
   `6d8721213005226740e225148fe1170a2758df3723226d64d1457a76cf2d78f9` /
   `2b110b4195a87b8ae572a51c8912e2e6383765f5173051848b720a246acd97a7`
   (recorded so the ARM-B counterpart reviews byte-identical artifacts).
5. `git status --porcelain -- .local/pilot-ca1/` → empty output, exit 0
   (reviewer mutated nothing in the pilot tree).
6. `sha256sum .local/muse-r17/drivers.rs` →
   `68c6d462214f8f5687ef2f8f40024ab02d7ba35f9199a0a0b02d5a7cd3d7f496` —
   **MATCH**es the hash r17's brief expected (no MISMATCH-HOLD; r17 line refs trusted).
7. JSON/report internal consistency (computed, not trusted):
   candidate/rollback shas in JSON match pins; Test 1 arithmetic
   `1791017039118 <= 1791017040156 <= 1791017061406` → True;
   `deliver_exit_code` 1 in both report and JSON (the frozen 0-vs-1 conflict
   r14 flagged as E6 is resolved in these refined artifacts); `summary: ALL_PASS`.
8. DB copy-first check: listed `.local/pilot-ca1/data/opencode/` (now contains
   `opencode.db` **plus** `-shm`/`-wal`, unlike r14's frozen single-file state);
   copied `opencode.db` to `.local/muse-r18/pilot-copy.db`, queried read-only,
   then deleted the copy. Observed: 1 session (`ses_eff35bb8dffetYQ0aauR2uX2qo`,
   same id as r14's frozen session), 41 messages / 154 parts (growth vs r14's
   25/94). Limitation recorded honestly: the WAL/SHM sidecars were NOT copied,
   so this is a possibly-partial view; and the refined report's pilot session ids
   (`9872860a…`/`6df2a4dd…`) are aplexer-session ids in a different namespace, so
   this check neither corroborates nor refutes the refined Test 1 chronology/PTY
   claims. Harness logs and PTY byte captures are not in the packet.

## 3. Per-source assessment (ordinary Git/source/test evidence)

- **PILOT-REPORT.md + pilot_results.json (refined shape).** These are NOT the
  frozen artifacts r14 reviewed: they carry `test1_active_tool_negative` with
  `db_tool_start_ms`/`probe_deliver_ms`/`db_tool_end_ms`, child PID 2712264,
  and `zero_bytes_leaked_verified: true` — exactly the fields r14 said were
  missing (E4/E5) and the harness (`run_pilot_test.py`, sleep 20, PID gate,
  `start<=deliver<=end` assert) r14 noted as in-progress. They read as the
  requested owner rerun. BUT no owner statement in the listed packet explicitly
  links these artifacts to r14's PENDING-OWNER-RERUN or attests the rerun
  conditions; and per §2 item 8 I could not independently corroborate the Test 1
  chronology or zero-leakage claims from listed sources. Status: **reported,
  internally consistent, not independently corroborated.**
- **r14 (`PENDING-OWNER-RERUN`).** Pins/spec/rollback (E1–E3), both receiving
  cycles + ordering (E7–E9), identities (E10) were CONFIRMED on frozen evidence;
  E4/E5 pending rerun; E6 exit-code conflict + stale manifest sizes flagged for
  the owner. The refined artifacts appear to answer E4–E6, subject to the
  corroboration caveat above. r14's CONFIRMED items are accepted as stated
  (not re-executed; re-verifying the full DB forensics is outside this
  adoption decision's needs given §D1).
- **r17 (`SAFETY-CONCERN-CONFIRMED`).** Mechanism-level finding on the staged
  `drivers.rs`: `tool.execute.after` unconditionally overwrites the session
  entry with `"idle"` on pending-drain (lines 293–294) without lifecycle
  authority; the aggregate then reports `idle` on bare 3500 ms tool-quiescence
  (lines 117–129) with no turn-completion event anywhere in the file and
  NO-MECHANISM-FOUND consumer composer guard; DB-copy arithmetic places a real
  7719 ms model-busy gap (6213 ms continuous reasoning, zero active tool) with
  the timer fire point landing mid-think. The one-gap rescue caveat (a +1051 ms
  step-start that would cancel the timer IF delivered as a plugin event) is
  timing luck, explicitly not a contractual guarantee. **Nothing anywhere else
  in the packet refutes, dispositions, or repairs this.** The refined pilot
  Test 1 covers only the active-child-tool negative (deliver refused while a
  tool runs); it does not exercise the reasoning-gap false-idle path at all.
  R10's 34 negatives probe call-key/FIFO/idempotency/limits, not the
  after→idle oracle. R13 covers disk-exhaustion guarding, not readiness.
  Hence C2 FAILS.
- **r10 + guard-reconciliation.** Producer sections (§§2–4, §6-cargo) PRESERVED
  as reported: fidelity 19/19, own negatives 34/34, retracts_idle 8/8, runtime
  1/1, all exit 0 (accepted as reported, not re-executed). Guard §5 prose
  WITHDRAWN (described the wrong revision); single APPROVE label WITHDRAWN as
  overstated; split stands: producer APPROVE / 66f guard CHANGES (final-measure
  fail-closed + post-completion growth gate missing in 66f). The producer
  APPROVE does not clear C2 (different mechanism).
- **r13 (R2 guard APPROVE).** R2 bytes (322 lines, sha256 `6ad17cad…c9b`)
  statically verified line-by-line with 3/3 negative tests at exit 0, pins
  unchanged. Scope explicitly covers R2 soundness only; files are
  uncommitted/ignored so rollout must pin by sha256. Does not bear on C2.

## 4. Defects found (with artifact refs)

- **D1 (decision-driving, open safety concern):** after→idle false-idle +
  missing composer guard. Refs: `.local/muse-r17/verdict.md` §§2–5,7;
  staged `.local/muse-r17/drivers.rs` lines 87–132, 246–297 (sha256 verified
  in §2 item 6). No listed evidence repairs or accepts the residual risk.
- **D2 (secondary, scope):** no named adoption-target head and no monitoring
  plan in any listed evidence. Refs: `.local/pilot-ca1/PILOT-REPORT.md`
  (isolation workspace + pilot session tags only — pilot confinement, not an
  adoption scope); `.local/muse-r14/verdict.md` §0 (owner `antigravity-head`
  holds pilot-tree edit — ownership of the experiment, not an adoption target).
- **D3 (non-blocking documentation, for owner):** r14's stale manifest size
  fields and frozen E6 conflict — E6 appears fixed in the refined artifacts
  (§2 item 7); manifest sizes not re-checked (manifest not in listed packet).
  Ref: `.local/muse-r14/verdict.md` §1 size-note, E6 row.
- **D4 (method caveat, mine):** refined Test 1 chronology + zero-leakage are
  taken as reported, not independently corroborated (§2 item 8). A future
  adoption case needs: harness run log with timestamps, PTY byte counts,
  and an explicit owner attestation linking the rerun to r14's pending items —
  plus disposition of D1 first.

## 5. Confidence and effort (honest record)

- **Confidence in REJECT: high** on the decision itself — D1 is a
  mechanism-level open safety concern on the delivery path, unrefuted within
  the packet, so C2 fails regardless of how Test 1 grounding resolves.
- **Confidence in Test-1 specifics: medium-low** — internally consistent as
  reported but not independently corroborated from listed sources (§2 item 8).
- **Wall-time:** ~4 minutes (2026-10-03 ~08:47–08:50 UTC; measured: 08:49:05Z mid-review, 08:50:20Z at send).
- **Tool calls used:** 14 (4 bash evidence/verify/send invocations + 7 file reads + 1 file write + 2 record-correction edits). Counted honestly, inclusive.
- **Model/route:** Muse Spark via `opencode-go/muse-spark-1.3-contributor`
  (shell-engine worker; whoami JSON carries no model field).
