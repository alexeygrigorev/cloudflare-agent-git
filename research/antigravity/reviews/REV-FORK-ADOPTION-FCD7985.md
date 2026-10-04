# Independent Review: Real Fork Adoption commit fcd7985

- **Reviewer**: sb-reviewer-adoption (Space Bunny, head: antigravity-head)
- **Commit under review**: `fcd7985` — "test(adoption): C1474 real fork adoption run — live verify + automated CI loop"
- **Artifacts reviewed**:
  - `research/antigravity/adoption/REAL-FORK-ADOPTION-REPORT.md` (113 lines)
  - `prototype/test/adoption.test.ts` (153 lines)
- **Date of review**: 2026-10-04 (UTC ~2026-10-03T23:57Z)
- **Checkout**: `/home/alexey/git/agent-branches-adopt`, branch `proto/ab-adoption`

## Verdict: REQUEST_CHANGES

The live run genuinely drove the Agent Branches workflow over real Git transport
(real commits, real bearer-auth push, real webhook delivery — all re-verified
below). But the commit's headline claim — **real development-task adoption** —
is not proven: the work product is two doc-note lines in disjoint files, a
transport smoke test, not a development task. The automated CI loop is a
**synthetic attestation fixture**, not an automated equivalent of the live run:
content-free commits, `tests.command: null` (nothing executed), no webhook leg,
no 409 case. And scratch hygiene fails: live bearer tokens remain in plaintext
under `/tmp`, nothing migrated to `.local/scratch/`.

## 1. Claim challenge: notes vs real code fix

**Finding 1 (live transport: CONFIRMED real).** The cited commits exist as real
git objects in the ephemeral sidecar repos and carry real content deltas:

- `aea84ba402f0bea1de71348a4d14fe722add577c` in
  `/tmp/ab-adoption-c1474/repos/repos/...-a-0003.git` —
  `docs: adoption note A`, `README.md | 1 +`, tree `f978eade…` vs base tree
  `e8d85c7b…` (verified via `rev-parse HEAD^{tree}` vs `HEAD~1^{tree}`).
- `d5bd65fa8aa015c7d0f242b0a9ffe4ba8c904ed8` in `...-b-0004.git` —
  new file `NOTES-adoption-b.md`, tree `ddc62fce…` vs base `e8d85c7b…`.
- `edit-push.sh` shows genuine `git -c http.extraHeader="Authorization: Bearer
  $TASK_TOKEN" push origin HEAD:main` for both clones; coordinator state
  (`coordinator-state.json`, `step8/9-task*-detail.txt`) records `pushes: 1`
  per agent and `unprocessedPushes: []`.

These commits are correctly absent from the canonical repo (`git show` → bad
object): they live in fork bare repos, as the design intends. No fabrication.

**Finding 2 (development-task adoption: NOT proven).** The entire work product is:

- README.md `+1 line`: `adoption note A (C1474): Agent Branches adopted for
  real task workflow …`
- New `NOTES-adoption-b.md`, 1 line: `adoption note B (C1474): independent
  agent B fork edit for pair check.`

Disjoint files, zero overlap, merge outcome predetermined; `merge-tree` clean
is a foregone conclusion, not evidence of conflict handling. No bug, no
behavior change, no source edit, no test guarding real functionality. The R3
`grep` assertions check only that the notes exist — they test the smoke, not a
task. A real adoption proof needs at minimum: a code fix (or conflicting edits
to the same file) plus a behavioral test that fails without the fix. **Required
correction**: relabel the verdict to scoped transport verification (e.g.
"WORKFLOW TRANSPORT CONFIRMED"), or add a genuine conflicting-edit/code-fix
pair to earn "ADOPTION CONFIRMED".

## 2. Automated loop: synthetic fixtures, not real test execution

**Finding 3 (test runs green — independently reproduced).** From `prototype/`:

- `npx vitest run test/adoption.test.ts` → **1 passed** (tests 637 ms, total
  2.36 s; report's "868 ms" is same-order timing variance, not material).
- `npx tsc --noEmit` → clean (exit 0).

**Finding 4 (step-6 `tests.command` is `null` — nothing is executed).**
`adoption.test.ts:118` submits
`policy: { merge: "git-merge-tree", tests: { command: null, budget_s: 15.0 } }`.
The coordinator **never executes** `tests.command` anywhere: no `spawn`/`execFile`
in `prototype/src`; `coordinator.ts:685-756` (`applyCheckResultsNow`) stores
whatever the runner reports with `accepted = input.results.length`
(self-attestation by design — trusted runner). The live run's R3 `grep`
assertions were executor-side manual shell, not coordinator-enforced; the CI
test does not even do that. The `clean` verdict in CI is a stored claim, not
an executed result. The report's "full-vector 0.1 check → pair `clean`"
wording omits this.

**Finding 5 (`sidecarCommit` makes content-free commits).**
`prototype/test/helpers.ts:16-27` → `sidecar.mjs:346-367` (`commitOn`):
reuses the tip tree verbatim (`rev-parse <tip>^{tree}`) and mints a
`commit-tree` with only a new message. CI "fork edits" advance heads with
**tree-identical commits — zero file change**. The test would pass if the
agents produced no work product at all.

**Finding 6 (webhook leg has zero CI coverage).** CI advances heads via direct
`POST /events/push` under the agent token; the sidecar post-receive webhook —
the live run's headline result (`unprocessedPushes: []`) — is never exercised.
The file's own header comment (lines 12-15) discloses this mapping honestly;
the report's "automates the loop for CI" overclaims it. **Required correction**:
disclose all four limits (null command, tree-identical commits, no webhook,
no 409 stale-gate assertion — CI submits only the full vector) in the report's
"Automated regression coverage" section, or strengthen the test (assert trees
differ; add a partial-vector 409 case; cover webhook delivery).

## 3. Mutation coverage (what the CI test would NOT catch)

| Mutation | Caught? |
|---|---|
| Agent produces empty/tree-identical edit | **No** — `sidecarCommit` itself is tree-identical; no tree-diff assertion |
| Runner fabricates `clean` without running any test | **No** — `command: null` accepted; coordinator stores verbatim |
| Post-receive webhook silently drops a push | **No** — CI bypasses webhook via direct `POST /events/push` |
| 409 full-vector stale gate regresses to accept partial vectors | **No** — only full-vector submission asserted |
| Cross-agent token reuse (403) regresses to accept | Yes — `crossAgent` 403 asserted |
| Wrong runner token accepted (401) regresses | Yes — `badRunner` 401 asserted |
| Push provenance not recorded (`pushes`, heads) | Yes — heads/pushes/`unprocessedPushes` asserted |
| Task payload shape (fork remote, ref, base==head, `art_v1_` token) | Yes — integrity loop asserted |

4 of 8 meaningful mutations escape. The auth/provenance half is solid; the
adoption/execution half is uncovered.

## 4. Scratch hygiene: FAIL (C1487)

`/tmp/ab-adoption-c1474/` remains **fully in place**: repos, work clones, logs,
raw payloads, and — critically — **live bearer tokens in plaintext**:
`admin.token`, `runner.token`, `sidecar.token` (33 B each), plus tokens
embedded in `step2-taskA.txt` / `step3-taskB.txt` (consumed by `edit-push.sh`
via grep). `.local/` does not exist anywhere in this worktree — nothing was
migrated to `.local/scratch/`. (The string `C1487` appears nowhere in this
worktree; judged against the task requirement text. Note the vitest harness
itself already writes to `…/.local/scratch/…` per `global-setup` output — the
live-run artifacts are the unmigrated remainder.) **Required correction**:
migrate or remove `/tmp/ab-adoption-c1474` (tokens at minimum must be revoked/
deleted, not left world-readable-parented in `/tmp`), and update the report's
"Scratch/evidence dir" + "Reproduction" paths to `.local/scratch/`.

## 5. Minor accuracy notes (non-blocking)

- Report `expiresAt 2026-10-04T00:43:47Z` vs run window 23:43–23:50Z: consistent
  with TTL 3600. Fine.
- Stray `task-0001`/`task-0002` attributed to harness double-execution: plausible
  and honestly disclosed; canonical run used `task-0003`/`task-0004`. The 2-agent
  → 409 → full-4-agent → 200 recovery matches `coordinator.ts:645` full-map
  semantics. No dispute.
- `contract 0.1.4` wire claim not independently re-verified; out of scope.

## Required changes before ACCEPT

1. Relabel `ADOPTION CONFIRMED` to the proven scope (transport/workflow
   verification), or land a real conflicting-edit/code-fix pair with a
   behavioral test.
2. Correct the "Automated regression coverage" section: disclose `command:
   null` self-attestation, tree-identical `sidecarCommit`, no webhook leg, no
   409 assertion — or fix the test to cover them.
3. Remediate `/tmp/ab-adoption-c1474` (delete/revoke plaintext tokens, migrate
   durable evidence to `.local/scratch/`) and update report paths.

## Reproduction (reviewer)

```bash
cd /home/alexey/git/agent-branches-adopt/prototype
npx vitest run test/adoption.test.ts   # 1 passed
npx tsc --noEmit                        # clean
git --git-dir=/tmp/ab-adoption-c1474/repos/repos/agent-branches-canonical-ed14c7b6-zcode-adoption-a-0003.git show HEAD
grep -rn "accepted: input.results.length" src/core/coordinator.ts
ls /tmp/ab-adoption-c1474/*.token
```

---
*Independent review; evidence re-verified by direct inspection, not inferred
from the report. Peer work preserved; no peer-owned files modified.*
