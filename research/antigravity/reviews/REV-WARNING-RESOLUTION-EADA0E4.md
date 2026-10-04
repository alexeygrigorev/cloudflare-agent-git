# REV-WARNING-RESOLUTION-EADA0E4 — Independent Review of proto/actor-warning-resolution

- **Reviewer:** zcode-recovery-test (ZCode/zcodex, session 4abc725c), assigned by antigravity-head (46fdb644) via aplexer 01a104d5-ae78-7093-955e-6a891121b7f2
- **As-of:** 2026-10-04, Europe/Berlin
- **Verdict: PASS WITHIN NARROW SCOPE.** Per the C1579 critique this refines the broader "PASS WITH FINDINGS" framing of REV-ACTOR-COMMITS-9EC-D56 (ab30df8): what is verified here is (a) no regressions from the actor changes, (b) both C1571 fixes are real and effective, (c) new/updated tests pass and their guards kill mutants. This is **not** full feature acceptance: residual input-validation gaps and one test blind spot remain (§3, §4).

## 1. Identity

| Item | Value |
|---|---|
| Branch tip | `proto/actor-warning-resolution` = `eada0e44194359f5a9eb39d0d9b97724e5690aa7` (verified on `origin` via ls-remote) |
| Tree | `3f24dabadba1231b9e6dd97f8b5e3c26d8dff10f` |
| Parents | `9ec79dbcc5eb…` (actor alpha) + `d56689841b78…` (actor beta) — a true merge |
| Subject | `feat(client): integrate inspect_token_metadata and calculate_jitter, resolve concurrent conflict` |
| Diffstat | `agent_branches/client.py` +20/−1, `tests/test_client.py` +25/−1 |

This commit is the hand-merge that REV-ACTOR-COMMITS-9EC-D56 §6 (F2) required: `git merge-tree 9ec79db d566898` had shown guaranteed conflicts in both files; this resolution integrates both helpers and both tests plus the C1571 fixes.

## 2. C1571 fix verification (code-level, then behavioral)

**F4 fix — `art_v1_` prefix accepted.** `inspect_token_metadata` now checks `any(token.startswith(p) for p in ("tok_", "task-", "sidecar-", "art_v1_"))`. Measured: `inspect_token_metadata("art_v1_abcdef12345")` → `{'valid_prefix': True, 'segments': 3, 'length': 18}`; `no-prefix-here` → `valid_prefix: False`; empty/non-string still raise `ValueError`. `test_21` now asserts the `art_v1_` case.

**F5 fix — strict `max_delay` ceiling.** `calculate_jitter` now returns `min(max_delay, round(delay + jitter, 4))` — the cap is applied *after* jitter. Measured: `calculate_jitter(8)` at defaults → **2.0 ≤ 2.0** (was 2.02 at d566898). `test_22` now asserts `calculate_jitter(8, max_delay=2.0) <= 2.0`.

**Sandbox robustness (also in this commit).** `run_cli` falls back to `[sys.executable, "-m", "agent_branches.cli"]` when the `agent-branches` launcher file is absent, and `test_04_git_utils_robustness` auto-initializes a git repo when `.git` is missing. Consequence: the 7 CLI-dependent failures that pre-dated both actor commits (`test_02,03,05,06,10,12,13` — missing launcher in base/alpha/beta trees) **now pass**.

**Suite result (this commit): `python3 -m unittest tests/test_client.py` → Ran 22 tests, OK (0 failures, 0 errors)** — confirmed twice in separate runs; base was 20 tests / 7 failures, alpha and beta 21 / 7. Delta vs base: +2 tests, −7 failures, +0 new failures.

## 3. Edge-case measurements (pristine tree)

- **Overflow boundary:** first `OverflowError` ("int too large to convert to float") at `attempt=1024`; last OK `attempt=1023` → 2.0. Cause: `base_delay * (2 ** attempt)` is evaluated before the cap. Residual defect (unreachable with sane retry caps; severity low). Options if wanted: short-circuit when `delay >= max_delay`, or clamp the exponent.
- **Remaining input-validation gaps (F5 family, not addressed by this commit):** `base_delay=-1` → returns `-1.0`; `max_delay=-5` (attempt 3) → returns `-5.0`; `max_delay=nan` → returns `nan` (propagates). Negative/non-finite bounds are accepted silently.
- **Determinism:** outputs identical across 50 repeated calls (attempts 0–49). No `random` import.
- **Prefix negative:** invalid prefix → `valid_prefix: False` (asserted behaviorally).

## 4. Behavioral mutation testing

All mutations are syntactically valid Python (`py_compile` verified before each test run), applied to a detached worktree at exactly `eada0e4`, and restored after each run — post-run `hash-object agent_branches/client.py` = `1c2cc37c08325d09ded2816c562aa4f8fa0fc99e` = `eada0e4:agent_branches/client.py` (byte-identical).

| ID | Mutation (behavioral change) | Canary observed | Target test | Result |
|---|---|---|---|---|
| MA | Remove `"art_v1_"` from prefix tuple | `art_v1_valid=False` | `test_21` | **KILLED** (failed) |
| MB | `return round(delay + jitter, 4)` (outer `min` dropped) | `jitter(8)=12.8` (> 2.0) | `test_22` | **KILLED** (failed) |
| MC | Guard `if attempt < 0:` → `if attempt < -1:` (−1 no longer raises) | `jitter(-1)=0.045`, no ValueError | `test_22` | **KILLED** (failed) |
| MD (probe) | `jitter = 0.0` (jitter removed, cap kept) | `jitter(8)=2.0`, valid | `test_22` | **SURVIVED** (still OK) |

Blind-spot note (residual, non-blocking): `test_22` does not pin jitter presence or exact values (exponential growth alone satisfies `j1 > j0`, and `jitter=0` stays under the cap), so MD survives. Exact-value assertions (e.g. `calculate_jitter(1, base_delay=0.1) == 0.21`) would close it. Kill summary this commit: MA, MB, MC killed; MD survives.

## 5. Verdict refinement per C1579

ab30df8 reviewed the two actor commits in isolation and said "PASS WITH FINDINGS"; C1571 then confirmed two real defects (F4 false-negative prefix, F5 ceiling violation). This commit fixes both, merges the conflicting lines, and repairs the suite's sandbox fragility. **Narrow-scope claims actually supported by evidence:** no regressions (22/22 vs 21/7-failures), C1571 fixes effective, new guards mutation-killed. **Claims explicitly not made:** full feature acceptance, production readiness, or that the helper family is fully validated — the §3 validation gaps (negative/non-finite bounds, overflow ≥1024) and §4 MD blind spot remain open for the owners.

## 6. Process note (evidence integrity, disclosed)

During evidence gathering, a concurrent duplicate execution of this same task plan was observed operating on the same scratch paths (worktree-creation races, and one cross-contaminated measurement snapshot showing min-less-mutant values, e.g. `jitter(8)=12.82`, `last OK=4.49e306`, phase-shifted mutation canaries). That snapshot was **discarded**; the retained evidence set is internally consistent *only* for pristine code (ceiling 2.0 + NaN propagation + suite 22/22 including the ceiling assertion are jointly impossible under the min-less mutant), and the final blob-identity check above rules out any lingering mutation. All quantitative results were re-taken in a session-private worktree `.local/scratch/zc-4abc725c-eada0e4/wt`; the shared `zcode-rev-eada0e4` worktree was left untouched for the concurrent actor.

## 7. Invariants

- Memory: all test/mutation runs under `ulimit -v 1500000` (1500 MB cooperative cap).
- Zero Rust builds, zero global installs, zero dependency changes; `TMPDIR` under `.local/scratch/`.
- No secrets: synthetic token strings only; report contains hashes, paths, measured numbers.
- Scratch: private worktree removed after publication; nothing in the canonical tree modified except this report.
- Reproduction: `git fetch origin proto/actor-warning-resolution && git worktree add --detach <dir> eada0e4 && cd <dir> && python3 -m unittest -v tests/test_client.py`; mutations are single-line substitutions as tabulated in §4.
