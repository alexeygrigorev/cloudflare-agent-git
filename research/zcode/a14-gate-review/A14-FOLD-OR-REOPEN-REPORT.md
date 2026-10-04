# A14 gate — independent fold-or-reopen review of `label-binding-residual-repair`

- Reviewer: `zcode-a14-gate` (zcodex session 31436338), launched by `antigravity-head` under Codex Principal C1507.
- Mode: READ-ONLY on Space Bunny source and fixtures. All suites and probes were executed by this reviewer on disposable copies; the canonical payload was never mutated.
- Date: 2026-10-04. Workspace: `/home/alexey/git/cloudflare-agent-git`.
- Scratch/evidence logs: `.local/scratch/zcode-a14-review/` (private, not committed).

## Verdict

**FOLD — close the row as DELIVERED and independently verified.** The row's acceptance criterion ("narrow label-to-expected-overlay binding plus independent swapped-label negative, distinct from the missing/corrupt-input gate") is met at pinned commit `4937506`. No new defect was found that would justify a reopen. This is closure-on-acceptance, **not** rejection-as-flawed, and **not** an approval manufactured for the owner: the pending Muse re-review (`01a0ffe6-209e`) remains its own lane and is neither substituted nor pre-empted here.

Three recorded conditions for the fold are at the end of this report.

## Naming disambiguation (important)

`coordination/space-bunny.md` §"A14 — fold or reopen" (line 407) discusses a **different** A14: the *shortlist approach* "per-task isolation", which the principals are folding into A01 verification. That decision is owned by the principals and is out of scope here. Nothing in TASKS.json is literally named A14; this report gates the TASKS row `label-binding-residual-repair` (team a05, status `review`, updated 2026-10-03T04:02Z) that the C1507 directive labels "A14". Future coordination should use the row id, not "A14", to avoid exactly this collision.

## Pinned state and integrity

| Check | Method | Result |
|---|---|---|
| Pinned commit exists | `git log -1 4937506` | `4937506` "space-bunny round 14: Muse verdict received, counter-finding confirmed and fixed; 14/14 negatives" (2026-10-03 05:54:09 +0200) |
| Working tree == pinned | `git diff 4937506 HEAD -- research/space-bunny/repro/` | empty; `git status --porcelain` on the dir clean. No drift between pinned, HEAD (`858503c`), and disk. |
| Script hashes (out-of-band) | `sha256sum` | `replay.sh` `f91f1fe828d43cdc…a6581d82`; `negative-tests.sh` `1084cd3daeda37db…3e5a597c6` |
| Payload integrity | `sha256sum -c MANIFEST.sha256` | 21/21 OK. Note: MANIFEST covers payload only, **not** the two scripts or README — scripts are pinned via git and hashed above. |

## The Round-1 question: did replay callers ignore return code 2 / missing cases?

That defect is fixed and structurally pinned in the current script:

- Every dispatch captures the guard status explicitly: `rc=0; run_case … || rc=$?` / `compose_case … || rc=$?`, and any nonzero sets `setup_err=1` (`replay.sh:259-283`). A guard-aborted case is a run failure, exit 3 — it can no longer coexist with a success exit.
- A post-run structure check (`replay.sh:289-301`) requires exactly eight recorded rows, all eight expected labels, no duplicates, no gaps. A case that aborts before recording therefore cannot yield a "7-of-8, exit 0" summary — the Round-1 failure shape.
- Measured missing-case behavior: N1 missing overlay dir → **exit 3, `MISSING OVERLAY DIR`**; N2 missing oracle file (manifest skipped so the runtime guard is genuinely reached) → **exit 3, `MISSING ORACLE FILE`**. The negative harness's `check()` requires nonzero exit **and** the named reason (`negative-tests.sh:51-65`), so a regression to "silent skip / false success" would flip these cases to BAD rather than pass vacuously.

## The B2-equivalent: label→overlay binding and its negatives

- Binding implementation: `EXPECTED_HEAD` (`replay.sh:56-64`) derives the required executor SHA from the **label's** fixture/role via the canonical packet, never from the overlay argument. Enforced in `run_case` (`replay.sh:89-100`) and in `compose_case` for both A and B sides (`replay.sh:167-179`).
- N9d (single-arm swap `f1-A`→`arm1-signposted/B`) and N9e (compose A-side swap) both run under `skip_manifest`, so the integrity gate cannot preempt the runtime guard under test; observed **exit 3, `LABEL/OVERLAY MISMATCH` / `LABEL/OVERLAY MISMATCH (A)`**. Distinct from N9 (tampered payload → **exit 2, `MANIFEST FAILED`**): the swapped-label negatives exercise the label/head guard, not the corrupt-input gate — the acceptance wording holds.
- Non-vacuity, verified by mutation kill (my probe): forcing the binding off (`if [ -n "$want_head" ]` → `if [ -n "" ]`) with the same N9d swap and default guards yields **exit 0 with `f1-A PASS`**. The negative therefore genuinely kills the broken-binding mutation; it is not a test that passes for the wrong reason.

## `REPLAY_GUARDS_OFF=1` — the disclosed bypass, measured honestly

- Probe A: guards-off + the N9d swap → banner `!! REPLAY_GUARDS_OFF=1 - FIXTURE AND LABEL GUARDS ARE DISABLED IN THIS RUN !!` is printed and the run reports **exit 0 with 8/8 PASS rows**. The override genuinely reopens Muse's hole; a guards-off run can never support an integrity claim. It is opt-in, loud, and greppable; default is fail-closed (`replay.sh:29`).
- Probe B: guards-off + cross-fixture *single-arm* swap → **`FIXTURE MISMATCH`, exit 3**. `run_case`'s fixture guard is not gated by the flag — the banner's "FIXTURE AND LABEL GUARDS" wording overstates what is disabled (the compose fixture guard *is* gated; the single-arm one is not). The asymmetry fails in the safe direction. The provenance check is likewise ungated: N9b's franken tree is caught with `UNACCOUNTED PROVENANCE` even under guards-off (suite-measured).

## realtest scope, verified

`g3-no-symbol-overlap/results-real-agents.md` and `g3-non-discoverable/results-real-agents.md` record base/A/B/A+B all `rc=0` per fixture. `./replay.sh` executed by this reviewer reproduces exactly those eight outcomes (**8/8 PASS, exit 0**) from the published snapshots alone, MANIFEST-verified. Scope limits, accurately disclosed by the README rather than overstated: the `.head` SHAs (`685f3f88…`, `91d1b752…`, `4432c51d…`, `f616255a…`) are provenance labels only and are not resolvable objects in this repository, so reproduction is snapshot-level, not object-level; and the composed-arm SHAs from the live round 3 (`8a1b06c…`, `2a21c15…`) are historical records. The replay claim is accordingly "the published evidence reproduces", which is what it says.

## Full observed matrix (this reviewer's run, 2026-10-04)

`replay.sh`: 8/8 PASS, exit 0. `negative-tests.sh`: **14 passed, 0 bad, exit 0** — N1 3, N2 3, N3 3, N4 3(A), N5 3(B), N6 3, N7 4 TIMEOUT, N8 4 FAIL(rc=3), N9 2, N9b 3 provenance, N9c 3 provenance, N9d 3 label, N9e 3 label(A), N10 0. Every observed code matches the README's documented table.

## Conditions attached to the fold (non-blocking)

1. If the queued Muse re-review (`01a0ffe6-209e`) returns findings, they go to a **new** repair row — this harness's defect history is append-only by design; no silent edits to the pinned round.
2. The row's closing record should carry the guards-off residual disclosure: any external claim of "8/8 PASS" is binding only with `REPLAY_GUARDS_OFF` unset or `0`.
3. Optional polish, not a reopen trigger: align the banner wording with the actual gated set (single-arm fixture guard and provenance are not disabled), since the current text overstates the override's reach in the fail-safe direction.

## What would have triggered REOPEN (for the record)

Binding derived from the overlay argument rather than the label; N9d/N9e firing via byte-identity or manifest instead of the label guard; a guard-aborted case coexisting with a success exit; or a silent guard override. None of these is present at `4937506`.

---
*Reviewer conclusion only; peer approvals are neither claimed nor implied.*
