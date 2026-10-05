# muse-r19 ARM-B verdict (evidence-card format): ca1 pilot-adoption review

## 1. Whoami
- `aplexer whoami --json`: id `2187da3c-2841-42b3-8c99-477c6de8e599`, tag `muse-r19`, engine `shell`, workspace `/home/alexey/git/cloudflare-agent-git`, parent session `d575342d-1c1f-4c31-a3d1-a295d6d08873` (head `muse-reviewer`).
- Model/route (honest): this worker was launched by the parent's command line as `opencode run ... -m opencode-go/muse-spark-1.3-contributor`; I have no separate model-introspection tool, so I record the route as `opencode-go/muse-spark-1.3-contributor` via aplexer shell engine. No other model identity was observable from inside.
- Scope observed: evidence-card ONLY (`research/muse/a06-pilot-adoption/evidence-card.md`) + read-only `sha256sum` of the two pinned binaries. No other evidence files opened.

## 2. Decision: REJECT
Question: should ca1 (candidate binary sha256 `ca1e8030da0efb62504d1777a6f2a60358b002c1c0b1ace3a7268e817e5bbcd1`) be adopted for use on ONE existing head?

**Decision: REJECT** (primary failing criterion **C2**; **C4** also fails on the card as written; **C1** only partially self-verified — see mapping).

### Criterion mapping
- **(C1) all pins verifiable — PARTIAL / NOT FULLY ESTABLISHED by me.**
  - Candidate binary: VERIFIED by me. `sha256sum .local/producer-review/bin/aplexer-b4-variant-a` → `ca1e8030da0efb62504d1777a6f2a60358b002c1c0b1ace3a7268e817e5bbcd1` (matches card; size 79382632 B matches card's 79,382,632 B).
  - Rollback CLI: VERIFIED by me. `sha256sum /home/alexey/.local/bin/aplexer` → `8d49a216d43c70843bc07705f4c11eb13f3eb51646d5c6fc204ce0796ce618c4` (matches card; size 7487016 B matches card's 7,487,016 B).
  - Pilot-spec pin (`research/antigravity/r12-scoped-ca1-pilot-verification.md == git show 3a82375` byte-for-byte): NOT verified by me — verifying it would require opening another evidence file / running `git show`, which the brief prohibits ("You may NOT open any other evidence files"). So on the card alone, this leg of C1 is asserted-but-unverified by this reviewer. I do not count this against C1 as a failure, but C1 is not fully self-established.
  - Therefore C1 alone does not license ADOPT, but it is not the rejection ground.
- **(C2) no open safety concern on the delivery path — FAILS → rejection ground.**
  - The card's own E3 states an open, mechanism-level delivery-path hazard: `tool.execute.after` with pending drained sets session `idle` without lifecycle authority; aggregate reports `idle` after bare 3500 ms tool-quiescence; no turn-completion event; no composer/deliver guard found; a real 7719 ms model-busy gap (6213 ms continuous reasoning, zero active tool) contains the timer fire point ~4.2 s before the next tool start; failing direction is **fail-OPEN** (premature `idle` invites mid-turn delivery).
  - E2 adds a second open item on the same path: fail-closed `not-ready` rejection DURING confirmed active child-tool execution is PENDING (owner rerun in progress), with the frozen rejection grounded on a pre-sleep harness timestamp (~22.5 s before the sleep tool window), i.e. grounding on the active-tool window not established.
  - E4 adds a third: the 66f-committed guard script has CHANGES (no post-completion growth gate; final-measurement WARNING not fail-closed).
  - Any one of these is an "open safety concern on the delivery path". All three point the same way. C2 fails.
- **(C3) rollback path exists and is hash-verified — HOLDS (to the extent the card + hashes can show).**
  - Rollback CLI pin verified by me (hash above). Existence confirmed via `ls -l` (present, executable). The card does not describe a rollback *procedure*, only the pin — I record that limitation but do not fail C3 on it, since the criterion as written ("rollback path exists and is hash-verified") is satisfied at the pin level.
- **(C4) scope bounded to one named head with monitoring — FAILS (card as written).**
  - The card names NO head and describes NO monitoring plan. The criterion requires "one named head with monitoring". On the card alone, C4 is unmet (missing, not contradicted). This is an independent second ground for non-adoption; the primary ground remains C2.

Since ADOPT requires ALL of C1–C4 and C2 fails (with C4 also failing), the only compliant outcomes are REJECT or TIE. I choose **REJECT over TIE** because E3 is not an ambiguity or a missing-data tie — it is a stated, mechanism-backed, fail-open delivery hazard with gap arithmetic, which directly violates C2 as written.

## 3. Defects / card-clarity issues found (findings ABOUT THE CARD; nothing fetched beyond it)
1. **E1 candidate path incomplete:** gives only the directory (`.local/producer-review/bin/`, "not the pilot dir") — the exact filename (`aplexer-b4-variant-a`) is recoverable only from the brief, not the card alone. Minor.
2. **E4 references out-of-card material:** "see full note" with no note in the card. A card-format reviewer cannot evaluate the guard CHANGES beyond the parenthetical. (Recorded, not fetched.)
3. **E4 R2-guard pin value missing:** says repaired R2 guard is "pin by sha256 only, re-verify on copy" but gives NO sha256 value in the card, so that pin is unverifiable from the card.
4. **`66f` unexplained:** "66f-committed guard script" — presumably a commit prefix, but the card never expands it; combined with (2), the guard-status leg is hard to audit from the card alone.
5. **Pilot-spec pin is short-hash + equality claim:** `git show 3a82375` (short hash, no full digest, no byte count/hash of the spec file itself in the card). Within ARM-B rules the reviewer cannot verify it without opening other files.
6. **E2 report-vs-JSON discrepancy:** "report says deliver exit 0 vs JSON says 1 (JSON consistent with harness)" — the card asserts which side is authoritative but a card-only reviewer cannot check; plus "manifest size fields stale (hashes authoritative)" is a doc defect that slightly weakens reliance on card-quoted sizes (I relied on my own `ls -l`, which matched).
7. **No head / no monitoring / no rollback procedure in card:** forces C4 to fail as "missing". If the experiment intends C4 to be satisfiable, the card template needs named-head + monitoring + rollback-procedure fields.

No other defects asserted. I did not hunt for evidence for or against beyond the card + hashes, per instructions; "missing" items above are card-clarity findings, not external claims.

## 4. Confidence
- **High** that REJECT-on-C2 is the correct mapping of the card to the criteria as written (E3's fail-OPEN false-`idle` mechanism is explicit and directly contradicts C2).
- **Medium** on the overall adoption judgment in the real world (as opposed to on-the-card), precisely because ARM-B restricts me to the card + two hashes — I inspected no raw sources, logs, or code, and the PENDING rerun (E2) could in principle change the picture later. Within the question asked ("judge only on the card + your hash checks"), REJECT is clearly correct.

## 5. Effort (honest)
- Wall-time: ~4 minutes (2026-10-03 ~08:45–08:49Z; `date -u` read 2026-10-03T08:48:59Z just before writing).
- Tool calls used: 5 total — (1) `aplexer whoami --json`, (2) read `evidence-card.md`, (3) `sha256sum`+`ls -l` of both binaries (one bash call), (4) `date -u` + `ls -l` of the adoption dir (one bash call; dir listing only, did NOT open `preregistration.md` or any other evidence file), (5) writing this verdict file. The queued `a message send` notification next is an additional step after the file exists.
- Pin-verification commands + outputs (read-only hashing; no binaries executed):
  - `sha256sum .local/producer-review/bin/aplexer-b4-variant-a` → `ca1e8030da0efb62504d1777a6f2a60358b002c1c0b1ace3a7268e817e5bbcd1  .local/producer-review/bin/aplexer-b4-variant-a`
  - `ls -l .local/producer-review/bin/aplexer-b4-variant-a` → `-rwxrwxr-x 1 alexey alexey 79382632 Oct  3 09:34 ...` (note: host mtime displayed in local tz; size matches card)
  - `sha256sum /home/alexey/.local/bin/aplexer` → `8d49a216d43c70843bc07705f4c11eb13f3eb51646d5c6fc204ce0796ce618c4  /home/alexey/.local/bin/aplexer`
  - `ls -l /home/alexey/.local/bin/aplexer` → `-rwxr-xr-x 1 alexey alexey 7487016 Oct  2 22:53 ...` (size matches card)
- Model/route: `opencode-go/muse-spark-1.3-contributor` (from parent launch command; see §1).
